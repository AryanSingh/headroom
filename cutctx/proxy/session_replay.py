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

import json
import logging
import math
import os
import sqlite3
import threading
import time
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cutctx.pipeline import PipelineEvent, PipelineStage

logger = logging.getLogger(__name__)

DEFAULT_REPLAY_RETENTION_DAYS = 7
RETENTION_CLEANUP_INTERVAL = 100
MAX_DETAIL_STRING_LENGTH = 200
MAX_MATCHED_RULES = 50


@dataclass(frozen=True)
class ReplayEvent:
    event_id: int
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


def reduce_replay_events(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Derive deterministic operational state from sanitized replay events."""

    state: dict[str, Any] = {
        "event_count": 0,
        "first_event_id": None,
        "last_event_id": None,
        "first_event_timestamp": None,
        "last_event_timestamp": None,
        "latest_request_id": None,
        "latest_model": None,
        "latest_stage": None,
        "event_type_counts": {},
        "compression": {"tokens_before": 0, "tokens_after": 0, "tokens_saved": 0},
        "prompt_count": 0,
        "input_message_count": 0,
        "input_token_count": 0,
        "llm_request_count": 0,
        "tool_call_count": 0,
        "tool_call_counts": {},
        "response_count": 0,
        "error_count": 0,
        "error_code_counts": {},
        "policy_block_count": 0,
        "policy_redaction_count": 0,
    }
    for event in events:
        event_type = event.get("event_type")
        if not isinstance(event_type, str):
            continue
        state["event_count"] += 1
        state["event_type_counts"][event_type] = state["event_type_counts"].get(event_type, 0) + 1
        for source, first_target, last_target in (
            ("event_id", "first_event_id", "last_event_id"),
            ("timestamp", "first_event_timestamp", "last_event_timestamp"),
        ):
            value = event.get(source)
            if isinstance(value, int | float) and not isinstance(value, bool):
                if state["event_count"] == 1:
                    state[first_target] = value
                state[last_target] = value
        request_id = event.get("request_id")
        if isinstance(request_id, str) and request_id:
            state["latest_request_id"] = request_id
        detail = event.get("detail")
        if not isinstance(detail, Mapping):
            detail = {}
        stage = detail.get("stage")
        if isinstance(stage, str):
            state["latest_stage"] = stage
        if event_type == "prompt_received":
            state["prompt_count"] += 1
            for source, target in (
                ("message_count", "input_message_count"),
                ("token_count", "input_token_count"),
            ):
                value = detail.get(source)
                if isinstance(value, int | float) and not isinstance(value, bool):
                    state[target] += value
            model = detail.get("model")
            if isinstance(model, str) and model:
                state["latest_model"] = model
        elif event_type == "compression":
            for source, target in (
                ("tokens_before", "tokens_before"),
                ("tokens_after", "tokens_after"),
                ("savings", "tokens_saved"),
            ):
                value = detail.get(source)
                if isinstance(value, int | float) and not isinstance(value, bool):
                    state["compression"][target] += value
        elif event_type == "llm_request_sent":
            state["llm_request_count"] += 1
            model = detail.get("model")
            if isinstance(model, str) and model:
                state["latest_model"] = model
        elif event_type == "tool_call_detected":
            state["tool_call_count"] += 1
            tool_name = detail.get("tool_name")
            if isinstance(tool_name, str) and tool_name:
                state["tool_call_counts"][tool_name] = (
                    state["tool_call_counts"].get(tool_name, 0) + 1
                )
        elif event_type == "response_received":
            state["response_count"] += 1
            model = detail.get("model")
            if isinstance(model, str) and model:
                state["latest_model"] = model
        elif event_type == "error":
            state["error_count"] += 1
            code = detail.get("code")
            if isinstance(code, str) and code:
                state["error_code_counts"][code] = state["error_code_counts"].get(code, 0) + 1
        elif event_type == "policy_blocked":
            state["policy_block_count"] += 1
        elif event_type == "policy_redacted":
            state["policy_redaction_count"] += 1
    return state


def _tool_names_from_response(response: Any, provider: str) -> list[str]:
    """Extract bounded tool names from provider envelopes, never arguments."""

    if not isinstance(response, Mapping):
        try:
            response = response.json()
        except (AttributeError, TypeError, ValueError):
            return []
    if not isinstance(response, Mapping):
        return []
    names: list[str] = []
    if provider == "openai":
        choices = response.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                message = choice.get("message") if isinstance(choice, Mapping) else None
                calls = message.get("tool_calls") if isinstance(message, Mapping) else None
                if isinstance(calls, list):
                    for call in calls:
                        function = call.get("function") if isinstance(call, Mapping) else None
                        name = function.get("name") if isinstance(function, Mapping) else None
                        if isinstance(name, str) and name:
                            names.append(name)
    elif provider == "anthropic":
        content = response.get("content")
        if isinstance(content, list):
            for block in content:
                if (
                    isinstance(block, Mapping)
                    and block.get("type") == "tool_use"
                    and isinstance(block.get("name"), str)
                    and block["name"]
                ):
                    names.append(block["name"])
    return names


class ReplayEventStore:
    """Append-only SQLite event store keyed by session id."""

    def __init__(
        self,
        *,
        db_path: Path | str | None = None,
        max_sessions: int = 256,
        max_events_per_session: int = 200,
        retention_days: int = DEFAULT_REPLAY_RETENTION_DAYS,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_replay_path()
        self.max_sessions = max_sessions
        self.max_events_per_session = max_events_per_session
        self.retention_days = retention_days
        self._appends_since_cleanup = 0
        self._lock = threading.Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS replay_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_ms INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    request_id TEXT,
                    detail_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_replay_events_session_order
                    ON replay_events(session_id, event_id);
                CREATE INDEX IF NOT EXISTS idx_replay_events_timestamp
                    ON replay_events(timestamp_ms);
                """
            )
            self._prune_expired(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=0.1)
        connection.execute("PRAGMA busy_timeout = 100")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def close(self) -> None:
        """Keep a compatibility close hook for callers owning a store."""

        return None

    def _prune_expired(self, connection: sqlite3.Connection) -> None:
        if self.retention_days <= 0:
            return
        cutoff_ms = int(time.time() * 1000) - self.retention_days * 86_400_000
        connection.execute("DELETE FROM replay_events WHERE timestamp_ms < ?", (cutoff_ms,))

    def _append(
        self,
        connection: sqlite3.Connection,
        *,
        timestamp_ms: int,
        session_id: str,
        event_type: str,
        surface: str,
        request_id: str | None,
        detail_json: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO replay_events (
                timestamp_ms, session_id, event_type, surface, request_id, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (timestamp_ms, session_id, event_type, surface, request_id, detail_json),
        )

    def _enforce_bounds(self, connection: sqlite3.Connection, session_id: str) -> None:
        if self.max_events_per_session > 0:
            connection.execute(
                """
                DELETE FROM replay_events
                WHERE session_id = ?
                  AND event_id NOT IN (
                      SELECT event_id
                      FROM replay_events
                      WHERE session_id = ?
                      ORDER BY event_id DESC
                      LIMIT ?
                  )
                """,
                (session_id, session_id, self.max_events_per_session),
            )
        if self.max_sessions > 0:
            sessions = connection.execute(
                "SELECT session_id FROM replay_events GROUP BY session_id ORDER BY MIN(event_id) ASC"
            ).fetchall()
            for (expired_session_id,) in sessions[: -self.max_sessions]:
                connection.execute(
                    "DELETE FROM replay_events WHERE session_id = ?", (expired_session_id,)
                )

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
        try:
            with self._lock, self._connect() as connection:
                self._append(
                    connection,
                    timestamp_ms=int(time.time() * 1000),
                    session_id=session_id,
                    event_type=event_type,
                    surface=surface,
                    request_id=request_id,
                    detail_json=json.dumps(
                        _sanitize_detail(event_type, detail),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                )
                self._enforce_bounds(connection, session_id)
                self._appends_since_cleanup += 1
                if self._appends_since_cleanup >= RETENTION_CLEANUP_INTERVAL:
                    self._prune_expired(connection)
                    self._appends_since_cleanup = 0
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            logger.warning("event=replay_record_failed reason=%s", type(exc).__name__)

    def get(self, session_id: str) -> dict[str, Any]:
        try:
            with self._lock, self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT event_id, timestamp_ms, session_id, event_type, surface, request_id, detail_json
                    FROM replay_events
                    WHERE session_id = ?
                    ORDER BY event_id ASC
                    """,
                    (session_id,),
                ).fetchall()
        except (OSError, sqlite3.Error) as exc:
            logger.warning("event=replay_read_failed reason=%s", type(exc).__name__)
            rows = []
        events: list[ReplayEvent] = []
        for row in rows:
            try:
                detail = json.loads(row[6])
            except (TypeError, json.JSONDecodeError):
                logger.warning("event=replay_row_skipped reason=invalid_detail_json")
                continue
            if not isinstance(detail, dict):
                logger.warning("event=replay_row_skipped reason=invalid_detail_shape")
                continue
            events.append(
                ReplayEvent(
                    event_id=row[0],
                    timestamp=row[1] / 1000,
                    session_id=row[2],
                    event_type=row[3],
                    surface=row[4],
                    request_id=row[5],
                    detail=detail,
                )
            )
        return {
            "session_id": session_id,
            "event_count": len(events),
            "events": [event.to_dict() for event in events],
        }

    def list_recent_sessions(self, *, limit: int = 50) -> dict[str, Any]:
        """Return bounded session summaries ordered by their latest event."""

        if limit < 1:
            return {"session_count": 0, "sessions": []}
        try:
            with self._lock, self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT session_id, COUNT(*) AS event_count, MAX(event_id) AS last_event_id
                    FROM replay_events
                    GROUP BY session_id
                    ORDER BY last_event_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        except (OSError, sqlite3.Error) as exc:
            logger.warning("event=replay_session_list_failed reason=%s", type(exc).__name__)
            rows = []
        sessions = [
            {"session_id": row[0], "event_count": row[1], "last_event_id": row[2]} for row in rows
        ]
        return {"session_count": len(sessions), "sessions": sessions}

    def recover_recent_session_states(self, *, limit: int = 50) -> dict[str, Any]:
        """Rebuild bounded operational state for the most recently active sessions.

        The journal remains the source of truth: this intentionally derives
        each state afresh instead of persisting another mutable projection.
        """

        sessions: list[dict[str, Any]] = []
        for summary in self.list_recent_sessions(limit=limit)["sessions"]:
            session_id = summary["session_id"]
            state = reduce_replay_events(self.get(session_id)["events"])
            sessions.append(
                {
                    "session_id": session_id,
                    "event_count": state["event_count"],
                    "first_event_id": state["first_event_id"],
                    "last_event_id": state["last_event_id"],
                    "compression": state["compression"],
                    "prompt_count": state["prompt_count"],
                    "input_message_count": state["input_message_count"],
                    "input_token_count": state["input_token_count"],
                    "llm_request_count": state["llm_request_count"],
                    "tool_call_count": state["tool_call_count"],
                    "tool_call_counts": state["tool_call_counts"],
                    "response_count": state["response_count"],
                    "error_count": state["error_count"],
                    "error_code_counts": state["error_code_counts"],
                }
            )
        return {"session_count": len(sessions), "sessions": sessions}


_STORE: ReplayEventStore | None = None


def _default_replay_path() -> Path:
    return Path.home() / ".cutctx" / "replay.sqlite3"


def _bounded_string(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > MAX_DETAIL_STRING_LENGTH:
        return None
    return value


def _safe_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value if math.isfinite(value) else None


def _sanitize_detail(event_type: str, detail: dict[str, Any] | None) -> dict[str, Any]:
    """Keep only structural fields that are safe to persist in replay data."""

    source = detail if isinstance(detail, dict) else {}
    if event_type in {"policy_blocked", "policy_redacted"}:
        rules = source.get("matched_rules")
        if not isinstance(rules, list):
            return {}
        safe_rules = [
            rule
            for raw_rule in rules[:MAX_MATCHED_RULES]
            if (rule := _bounded_string(raw_rule)) is not None
        ]
        return {"matched_rules": safe_rules}

    allowed: dict[str, tuple[str, ...]] = {
        "prompt_received": ("message_count", "token_count", "model", "provider"),
        "compression": ("tokens_before", "tokens_after", "savings", "stage"),
        "response_received": ("tokens_used", "model", "stage"),
        "llm_request_sent": ("model", "provider", "stage"),
        "tool_call_detected": ("tool_name",),
        "error": ("code",),
        "circuit_breaker_triggered": ("code", "cooldown_ms"),
    }
    result: dict[str, Any] = {}
    for key in allowed.get(event_type, ()):
        value = source.get(key)
        if key in {
            "tokens_before",
            "tokens_after",
            "savings",
            "tokens_used",
            "cooldown_ms",
            "message_count",
            "token_count",
        }:
            if (number := _safe_number(value)) is not None:
                result[key] = number
        elif (text := _bounded_string(value)) is not None:
            result[key] = text
    return result


def _replay_db_path_from_env() -> Path:
    configured = os.environ.get("CUTCTX_REPLAY_DB_PATH", "").strip()
    return Path(configured).expanduser() if configured else _default_replay_path()


def _replay_retention_days_from_env() -> int:
    value = os.environ.get("CUTCTX_REPLAY_RETENTION_DAYS", "").strip()
    if not value:
        return DEFAULT_REPLAY_RETENTION_DAYS
    try:
        return int(value)
    except ValueError:
        logger.warning("event=replay_config_invalid setting=CUTCTX_REPLAY_RETENTION_DAYS")
        return DEFAULT_REPLAY_RETENTION_DAYS


def is_replay_enabled() -> bool:
    return os.environ.get("CUTCTX_REPLAY", "").strip().lower() in {"1", "true", "yes", "on"}


def get_replay_store() -> ReplayEventStore | None:
    global _STORE
    if not is_replay_enabled():
        return None
    if _STORE is None:
        try:
            _STORE = ReplayEventStore(
                db_path=_replay_db_path_from_env(),
                retention_days=_replay_retention_days_from_env(),
            )
        except (OSError, sqlite3.Error) as exc:
            logger.warning("event=replay_init_failed reason=%s", type(exc).__name__)
            return None
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


def record_prompt_received(
    *,
    session_id: str,
    surface: str,
    request_id: str | None,
    message_count: int,
    token_count: int | float,
    model: str,
    provider: str,
) -> None:
    """Record bounded prompt metadata without retaining message content."""

    record_replay_event(
        session_id=session_id,
        event_type="prompt_received",
        surface=surface,
        request_id=request_id,
        detail={
            "message_count": message_count,
            "token_count": token_count,
            "model": model,
            "provider": provider,
        },
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
        request_id = metadata.get("request_id") or event.request_id

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

        elif event.stage is PipelineStage.PRE_SEND:
            record_replay_event(
                session_id=session_id,
                event_type="llm_request_sent",
                surface="pipeline",
                request_id=request_id,
                detail={
                    "model": event.model,
                    "provider": event.provider,
                    "stage": event.stage.value,
                },
            )

        elif event.stage is PipelineStage.RESPONSE_RECEIVED:
            status_code = metadata.get("status_code")
            if isinstance(status_code, int) and status_code >= 400:
                record_replay_event(
                    session_id=session_id,
                    event_type="error",
                    surface="pipeline",
                    request_id=request_id,
                    detail={"code": f"http_{status_code}"},
                )
            for tool_name in _tool_names_from_response(event.response, event.provider):
                record_replay_event(
                    session_id=session_id,
                    event_type="tool_call_detected",
                    surface="pipeline",
                    request_id=request_id,
                    detail={"tool_name": tool_name},
                )
            tokens_used = metadata.get("tokens_after") or metadata.get("output_tokens")
            record_replay_event(
                session_id=session_id,
                event_type="response_received",
                surface="pipeline",
                request_id=request_id,
                detail={
                    "tokens_used": tokens_used,
                    "model": event.model,
                    "stage": event.stage.value,
                },
            )

        return event
