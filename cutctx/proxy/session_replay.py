"""Flag-gated session replay event store.

WS8 alpha keeps replay default-off and bounded. It records structured events
only when ``CUTCTX_REPLAY=1`` so the normal proxy path performs no replay
writes.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any


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
