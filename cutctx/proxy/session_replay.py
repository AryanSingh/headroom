"""Flag-gated session replay event store.

WS8 alpha keeps replay default-off and bounded. It records structured events
only when ``CUTCTX_REPLAY=1`` so the normal proxy path performs no replay
writes.

Extended replay coverage (compression, retrieval, injection, CCR lifecycle,
and error/fallback states) is added through a ``ReplayPipelineExtension``
registered with the pipeline extension manager, and through direct helper
calls in handler code.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

from cutctx.pipeline import PipelineEvent, PipelineStage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplayEvent:
    timestamp: float
    session_id: str
    event_type: str
    surface: str
    request_id: str | None = None
    detail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["detail"] = self.detail or {}
        return payload


class ReplayEventStore:
    """Bounded in-memory event store keyed by session id."""

    def __init__(self, *, max_sessions: int = 256, max_events_per_session: int = 200) -> None:
        self.max_sessions = max_sessions
        self.max_events_per_session = max_events_per_session
        self._events: dict[str, deque[ReplayEvent]] = {}
        self._order: deque[str] = deque()
        self._lock = threading.Lock()

    def record(
        self,
        *,
        session_id: str,
        event_type: str,
        surface: str,
        request_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if not session_id:
            return
        with self._lock:
            if session_id not in self._events:
                self._events[session_id] = deque(maxlen=self.max_events_per_session)
                self._order.append(session_id)
                while len(self._order) > self.max_sessions:
                    evicted = self._order.popleft()
                    self._events.pop(evicted, None)
            self._events[session_id].append(
                ReplayEvent(
                    timestamp=time.time(),
                    session_id=session_id,
                    event_type=event_type,
                    surface=surface,
                    request_id=request_id,
                    detail=detail or {},
                )
            )

    def get(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            events = list(self._events.get(session_id, ()))
        return {
            "session_id": session_id,
            "event_count": len(events),
            "events": [event.to_dict() for event in events],
        }


_STORE: ReplayEventStore | None = None


def is_replay_enabled() -> bool:
    return os.environ.get("CUTCTX_REPLAY", "").strip().lower() in {"1", "true", "yes", "on"}


def get_replay_store() -> ReplayEventStore | None:
    global _STORE
    if not is_replay_enabled():
        return None
    if _STORE is None:
        _STORE = ReplayEventStore()
    return _STORE


def reset_replay_store() -> None:
    global _STORE
    _STORE = None


def record_replay_event(
    *,
    session_id: str,
    event_type: str,
    surface: str,
    request_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Safe one-shot replay recording — no-op when replay is disabled.

    Call from any handler or pipeline code to record a replay event without
    worrying about the store being None or replay being disabled.
    """
    store = get_replay_store()
    if store is not None:
        store.record(
            session_id=session_id,
            event_type=event_type,
            surface=surface,
            request_id=request_id,
            detail=detail,
        )


def record_for_pipeline(
    event_type: str,
    surface: str,
    session_id: str | None = None,
    request_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Record a replay event from pipeline extension code.

    Pipeline extensions don't always have a session_id. When absent, we
    record under a synthetic ``_pipeline`` session so the event still
    appears in the replay timeline.
    """
    record_replay_event(
        session_id=session_id or "_pipeline",
        event_type=event_type,
        surface=surface,
        request_id=request_id,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Pipeline extension — records compression/retrieval pipeline events
# ---------------------------------------------------------------------------


class ReplayPipelineExtension:
    """Pipeline extension that records canonical events to the replay store.

    Hooks into ``INPUT_COMPRESSED``, ``INPUT_REMEMBERED``, and
    ``RESPONSE_RECEIVED`` stages to record compression events, memory
    storage events, and response receipts in the replay timeline.

    Register by adding ``ReplayPipelineExtension`` to the proxy's
    pipeline extension list, or by declaring it as a Python entry point
    in ``pyproject.toml`` under ``[project.entry-points."cutctx.pipeline.extensions"]``.
    """

    def on_pipeline_event(self, event: PipelineEvent) -> PipelineEvent | None:
        if not is_replay_enabled():
            return event

        metadata = event.metadata or {}
        session_id = metadata.get("session_id") or metadata.get("project_id") or "_pipeline"
        request_id = metadata.get("request_id", "")

        if event.stage is PipelineStage.INPUT_COMPRESSED:
            tokens_before = metadata.get("tokens_before")
            tokens_after = metadata.get("tokens_after")
            if tokens_before is not None and tokens_before != 0:
                record_replay_event(
                    session_id=session_id,
                    event_type="compression",
                    surface="pipeline",
                    request_id=request_id,
                    detail={
                        "tokens_before": tokens_before,
                        "tokens_after": tokens_after,
                        "savings": (tokens_before or 0) - (tokens_after or 0),
                        "stage": event.stage.value,
                    },
                )

        elif event.stage is PipelineStage.RESPONSE_RECEIVED:
            tokens_used = metadata.get("tokens_after") or metadata.get("output_tokens")
            if tokens_used is not None:
                record_replay_event(
                    session_id=session_id,
                    event_type="response_received",
                    surface="pipeline",
                    request_id=request_id,
                    detail={
                        "tokens_used": tokens_used,
                        "model": metadata.get("model", ""),
                        "stage": event.stage.value,
                    },
                )

        return event
