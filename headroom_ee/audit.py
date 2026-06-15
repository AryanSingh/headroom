# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Structured audit event system for enterprise compliance.

Provides immutable, append-only audit logging for all administrative actions.
Events are stored in SQLite for durability and queryable via API endpoints.

Enterprise feature — gated on entitlement_tier >= ENTERPRISE.

Usage:
    from headroom.audit import AuditLogger, AuditEvent

    logger = AuditLogger(db_path="/path/to/audit.db")
    await logger.log(AuditEvent(
        action="license.changed",
        actor="admin@example.com",
        detail={"old_plan": "team", "new_plan": "enterprise"},
    ))
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from headroom import paths as _paths

logger = logging.getLogger("headroom.audit")

# Default audit DB location
AUDIT_DB_ENV = "HEADROOM_AUDIT_DB_PATH"


class AuditAction(str, Enum):
    """Standard audit action categories."""

    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_KEY_ROTATED = "auth.key_rotated"

    # License
    LICENSE_VALIDATED = "license.validated"
    LICENSE_CHANGED = "license.changed"
    LICENSE_EXPIRED = "license.expired"

    # Configuration
    CONFIG_CHANGED = "config.changed"
    CONFIG_EXPORTED = "config.exported"

    # Stats / data
    STATS_VIEWED = "stats.viewed"
    STATS_RESET = "stats.reset"
    STATS_EXPORTED = "stats.exported"
    REPORT_EXPORTED = "report.exported"

    # Entitlements
    ENTITLEMENT_CHECK = "entitlement.check"
    ENTITLEMENT_DENIED = "entitlement.denied"

    # Policy
    POLICY_CHANGED = "policy.changed"
    POLICY_VIEWED = "policy.viewed"

    # Retention
    RETENTION_CHANGED = "retention.changed"
    DATA_DELETED = "data.deleted"

    # System
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit event.

    Attributes:
        action: Event category (e.g. "license.changed").
        actor: Who performed the action (email, API key ID, "system").
        detail: Arbitrary JSON-serializable context.
        timestamp: ISO-8601 UTC timestamp (auto-set if omitted).
        event_id: Unique ID (auto-generated if omitted).
        org_id: Organization ID if applicable.
        workspace_id: Workspace ID if applicable.
        project_id: Project ID if applicable.
        success: Whether the action succeeded (default True).
        ip_address: Client IP if applicable.
        user_agent: Client user agent if applicable.
    """

    action: str
    actor: str
    detail: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    org_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None
    success: bool = True
    ip_address: str | None = None
    user_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON storage."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        """Deserialize from dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AuditLogger:
    """Append-only audit logger backed by SQLite.

    Thread-safe: writes are serialized via a lock. The SQLite connection
    is per-thread (thread-local) to avoid cross-thread sharing.

    The audit log is immutable — events can be appended and queried but
    never modified or deleted through this interface.
    """

    def __init__(self, db_path: str | Path | None = None):
        """Initialize the audit logger.

        Args:
            db_path: Path to SQLite database. Defaults to
                ~/.headroom/audit.db (or HEADROOM_AUDIT_DB_PATH env).
        """
        if db_path is None:
            db_path = os.environ.get(AUDIT_DB_ENV, "")
        if not db_path:
            db_path = str(_paths.workspace_dir() / "audit.db")
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a thread-local SQLite connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        """Create audit tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                org_id TEXT,
                workspace_id TEXT,
                project_id TEXT,
                success INTEGER NOT NULL DEFAULT 1,
                ip_address TEXT,
                user_agent TEXT,
                detail TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL DEFAULT (unixepoch())
            );

            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_events(timestamp);

            CREATE INDEX IF NOT EXISTS idx_audit_action
                ON audit_events(action);

            CREATE INDEX IF NOT EXISTS idx_audit_actor
                ON audit_events(actor);

            CREATE INDEX IF NOT EXISTS idx_audit_org
                ON audit_events(org_id);

            CREATE INDEX IF NOT EXISTS idx_audit_success
                ON audit_events(success);
            """
        )
        conn.commit()

    def log(self, event: AuditEvent) -> None:
        """Append an audit event (synchronous, thread-safe).

        This is the synchronous entry point for use in non-async contexts.
        """
        with self._lock:
            try:
                conn = self._get_conn()
                conn.execute(
                    """
                    INSERT INTO audit_events
                    (event_id, timestamp, action, actor, org_id, workspace_id,
                     project_id, success, ip_address, user_agent, detail, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.timestamp,
                        event.action,
                        event.actor,
                        event.org_id,
                        event.workspace_id,
                        event.project_id,
                        1 if event.success else 0,
                        event.ip_address,
                        event.user_agent,
                        json.dumps(event.detail, ensure_ascii=False),
                        time.time(),
                    ),
                )
                conn.commit()
            except Exception:
                logger.exception("Failed to write audit event %s", event.event_id)

    async def async_log(self, event: AuditEvent) -> None:
        """Append an audit event (async, offloaded to thread).

        Use this from async code to avoid blocking the event loop.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.log, event)

    def query(
        self,
        *,
        action: str | None = None,
        actor: str | None = None,
        org_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        success_only: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query audit events with optional filters.

        Returns list of event dicts, ordered by timestamp descending.
        """
        clauses = []
        params: list[Any] = []

        if action:
            clauses.append("action = ?")
            params.append(action)
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        if org_id:
            clauses.append("org_id = ?")
            params.append(org_id)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp <= ?")
            params.append(until)
        if success_only is not None:
            clauses.append("success = ?")
            params.append(1 if success_only else 0)

        where = " AND ".join(clauses) if clauses else "1=1"
        params.extend([limit, offset])

        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM audit_events WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            d["detail"] = json.loads(d.get("detail", "{}"))
            d["success"] = bool(d["success"])
            results.append(d)
        return results

    def count(self, *, action: str | None = None, org_id: str | None = None) -> int:
        """Count events matching optional filters."""
        clauses = []
        params: list[Any] = []
        if action:
            clauses.append("action = ?")
            params.append(action)
        if org_id:
            clauses.append("org_id = ?")
            params.append(org_id)

        where = " AND ".join(clauses) if clauses else "1=1"
        conn = self._get_conn()
        row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM audit_events WHERE {where}", params
        ).fetchone()
        return row["cnt"] if row else 0

    def export_jsonl(self, *, limit: int = 1000, **kwargs: Any) -> str:
        """Export events as newline-delimited JSON."""
        events = self.query(limit=limit, **kwargs)
        return "\n".join(json.dumps(e, ensure_ascii=False) for e in events)

    def close(self) -> None:
        """Close the thread-local database connection."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


# ---------------------------------------------------------------------------
# Module-level singleton (created lazily)
# ---------------------------------------------------------------------------

_global_logger: AuditLogger | None = None
_global_lock = threading.Lock()


def get_audit_logger(db_path: str | Path | None = None) -> AuditLogger:
    """Get or create the global audit logger singleton."""
    global _global_logger
    if _global_logger is None:
        with _global_lock:
            if _global_logger is None:
                _global_logger = AuditLogger(db_path=db_path)
    return _global_logger


def reset_audit_logger() -> None:
    """Reset the global singleton (for testing)."""
    global _global_logger
    with _global_lock:
        if _global_logger is not None:
            _global_logger.close()
            _global_logger = None


# Need os for env var access
import os  # noqa: E402
