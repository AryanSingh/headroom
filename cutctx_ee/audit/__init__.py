# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Structured audit event system for enterprise compliance.

Provides immutable, append-only audit logging for all administrative actions.
Events are stored in SQLite for durability and queryable via API endpoints.

Enterprise feature — gated on entitlement_tier >= ENTERPRISE.

Usage:
    from cutctx.audit import AuditLogger, AuditEvent

    logger = AuditLogger(db_path="/path/to/audit.db")
    await logger.log(AuditEvent(
        action="license.changed",
        actor="admin@example.com",
        detail={"old_plan": "team", "new_plan": "enterprise"},
    ))
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
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

from cutctx import paths as _paths
from cutctx.storage.sqlite_schema import stamp_schema_version

_SCHEMA_VERSION = 1

logger = logging.getLogger("cutctx.audit")

# Default audit DB location
AUDIT_DB_ENV = "CUTCTX_AUDIT_DB_PATH"

# Hash-chain (tamper-evidence) configuration. Shares the env contract with
# ``cutctx_ee.audit.store.AuditStore`` so a deployment configures one secret.
AUDIT_SECRET_ENV = "CUTCTX_AUDIT_SECRET_KEY"
AUDIT_DEV_ALLOW_ENV = "CUTCTX_ALLOW_DEV_AUDIT_KEY"


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
                ~/.cutctx/audit.db (or CUTCTX_AUDIT_DB_PATH env).
        """
        if db_path is None:
            db_path = os.environ.get(AUDIT_DB_ENV, "")
        if not db_path:
            db_path = str(_paths.workspace_dir() / "audit.db")
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._chain_key = self._resolve_chain_key()
        self._chain_mode = "hmac-sha256" if self._chain_key else "sha256"
        self._ensure_schema()

    # -- Tamper-evidence (hash chain) ---------------------------------------

    @staticmethod
    def _resolve_chain_key() -> bytes | None:
        """Resolve the HMAC key for the audit hash chain, or None.

        Unlike ``AuditStore``, this must never raise: ``AuditLogger`` is
        constructed unconditionally by the proxy, and refusing to start the
        whole server because a chain key is absent would be a worse outcome
        than an unkeyed chain. When no key is configured we fall back to a
        plain SHA-256 chain and say so honestly in ``verify_chain()``
        (``key_configured: False``, ``forgeable: True``) — an unkeyed chain
        still detects edits made without recomputing the chain, but an
        attacker with write access can recompute it.
        """
        env_key = os.environ.get(AUDIT_SECRET_ENV, "").strip()
        if env_key:
            return env_key.encode()
        return None

    @staticmethod
    def _length_prefix(value: Any) -> bytes:
        """Length-prefix a field so concatenation is unambiguous."""
        encoded = ("" if value is None else str(value)).encode()
        return len(encoded).to_bytes(8, "big") + encoded

    @classmethod
    def _chain_scope(cls, org_id: str | None) -> str:
        """Chain events per tenant; NULL org_id shares the default chain."""
        return org_id or ""

    def _compute_entry_hash(self, fields: dict[str, Any], prev_hash: str | None) -> str:
        """Compute this entry's chain value over every persisted column.

        Every column is bound, so altering any field of a stored row breaks
        verification. ``prev_hash`` links the row to its predecessor, so
        deleting or reordering rows breaks it too.
        """
        message = b"".join(
            (
                (prev_hash or "0" * 64).encode(),
                self._length_prefix(fields["event_id"]),
                self._length_prefix(fields["timestamp"]),
                self._length_prefix(fields["action"]),
                self._length_prefix(fields["actor"]),
                self._length_prefix(fields["org_id"]),
                self._length_prefix(fields["workspace_id"]),
                self._length_prefix(fields["project_id"]),
                self._length_prefix(fields["success"]),
                self._length_prefix(fields["ip_address"]),
                self._length_prefix(fields["user_agent"]),
                self._length_prefix(fields["detail"]),
            )
        )
        if self._chain_key:
            return hmac.new(self._chain_key, message, hashlib.sha256).hexdigest()
        return hashlib.sha256(message).hexdigest()

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
        # Tamper-evidence columns. Added via ALTER so existing audit DBs
        # migrate in place; pre-existing rows keep NULL hashes and are
        # reported as "unverifiable" (not "broken") by verify_chain().
        existing = {row[1] for row in conn.execute("PRAGMA table_info(audit_events)")}
        if "prev_hash" not in existing:
            conn.execute("ALTER TABLE audit_events ADD COLUMN prev_hash TEXT")
        if "entry_hash" not in existing:
            conn.execute("ALTER TABLE audit_events ADD COLUMN entry_hash TEXT")
        stamp_schema_version(conn, expected=_SCHEMA_VERSION, store_name="audit logger")
        conn.commit()

    def log(self, event: AuditEvent) -> None:
        """Append an audit event (synchronous, thread-safe).

        This is the synchronous entry point for use in non-async contexts.
        """
        with self._lock:
            try:
                conn = self._get_conn()
                fields = {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp,
                    "action": event.action,
                    "actor": event.actor,
                    "org_id": event.org_id,
                    "workspace_id": event.workspace_id,
                    "project_id": event.project_id,
                    "success": 1 if event.success else 0,
                    "ip_address": event.ip_address,
                    "user_agent": event.user_agent,
                    "detail": json.dumps(event.detail, ensure_ascii=False),
                }
                # Link this row to the tail of its tenant's chain.
                scope = self._chain_scope(event.org_id)
                tail = conn.execute(
                    """
                    SELECT entry_hash FROM audit_events
                    WHERE COALESCE(org_id, '') = ? AND entry_hash IS NOT NULL
                    ORDER BY rowid DESC LIMIT 1
                    """,
                    (scope,),
                ).fetchone()
                prev_hash = tail["entry_hash"] if tail else None
                entry_hash = self._compute_entry_hash(fields, prev_hash)
                conn.execute(
                    """
                    INSERT INTO audit_events
                    (event_id, timestamp, action, actor, org_id, workspace_id,
                     project_id, success, ip_address, user_agent, detail, created_at,
                     prev_hash, entry_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fields["event_id"],
                        fields["timestamp"],
                        fields["action"],
                        fields["actor"],
                        fields["org_id"],
                        fields["workspace_id"],
                        fields["project_id"],
                        fields["success"],
                        fields["ip_address"],
                        fields["user_agent"],
                        fields["detail"],
                        time.time(),
                        prev_hash,
                        entry_hash,
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

    def delete_for_actor(self, actor: str) -> int:
        """Delete every audit event for the supplied actor.

        GDPR/CCPA right-to-be-forgotten carve-out: DSR (Data
        Subject Request) processing is the only sanctioned path
        to remove audit rows. The class docstring's "append-only"
        statement is qualified by this DSR exception — the audit
        log is append-only for the operational integrity surface
        (tamper-evidence) but the DSR endpoint may purge rows
        belonging to a specific actor.

        Production deployments must additionally run a periodic
        VACUUM after bulk DSR deletes to reclaim disk space.

        Parameters
        ----------
        actor : str
            The actor identifier (matches the ``actor`` column).

        Returns
        -------
        int
            Number of rows deleted.
        """
        if not actor:
            return 0
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute("DELETE FROM audit_events WHERE actor = ?", (actor,))
            conn.commit()
            return cur.rowcount or 0

    def verify_chain(self, *, tenant_id: str | None = None) -> dict[str, Any]:
        """Recompute the audit hash chain and report the first break.

        H8: this method did not exist, so ``GET /audit/verify`` raised
        AttributeError and returned HTTP 500 on every call. It now performs
        genuine verification: for each tenant chain, rows are replayed in
        insertion order (``rowid``), each row's hash is recomputed from all
        of its persisted columns plus its predecessor's hash, and both the
        recomputed value and the stored ``prev_hash`` link are checked.

        Any single-field edit, deletion, reordering or insertion breaks the
        chain from that point on.

        Rows written before this feature existed have NULL hashes. They are
        counted as ``unverifiable`` rather than reported as tampering — the
        honest answer is "no evidence either way" for those rows.

        Returns a dict with ``ok``, the chain ``mode``, whether a secret key
        is configured, counts, and ``broken_at`` describing the offending
        entry id when verification fails.
        """
        result: dict[str, Any] = {
            "ok": True,
            "mode": self._chain_mode,
            "key_configured": self._chain_key is not None,
            # An unkeyed chain detects edits made without recomputing it, but
            # anyone with write access to the DB can forge it. Say so.
            "forgeable": self._chain_key is None,
            "tenant_id": tenant_id,
            "checked": 0,
            "unverifiable": 0,
            "chains": 0,
            "broken_at": None,
        }

        clauses = []
        params: list[Any] = []
        if tenant_id is not None:
            clauses.append("COALESCE(org_id, '') = ?")
            params.append(self._chain_scope(tenant_id))
        where = " AND ".join(clauses) if clauses else "1=1"

        conn = self._get_conn()
        rows = conn.execute(
            f"SELECT * FROM audit_events WHERE {where} ORDER BY rowid ASC",  # noqa: S608
            params,
        ).fetchall()

        tails: dict[str, str | None] = {}
        for row in rows:
            scope = self._chain_scope(row["org_id"])
            if row["entry_hash"] is None:
                result["unverifiable"] += 1
                continue
            if scope not in tails:
                tails[scope] = None
                result["chains"] += 1
            expected_prev = tails[scope]
            fields = {
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "action": row["action"],
                "actor": row["actor"],
                "org_id": row["org_id"],
                "workspace_id": row["workspace_id"],
                "project_id": row["project_id"],
                "success": row["success"],
                "ip_address": row["ip_address"],
                "user_agent": row["user_agent"],
                "detail": row["detail"],
            }
            if row["prev_hash"] != expected_prev:
                result["ok"] = False
                result["broken_at"] = {
                    "event_id": row["event_id"],
                    "scope": scope,
                    "reason": "prev_hash_mismatch",
                    "expected_prev_hash": expected_prev,
                    "stored_prev_hash": row["prev_hash"],
                }
                return result
            recomputed = self._compute_entry_hash(fields, row["prev_hash"])
            if not hmac.compare_digest(recomputed, row["entry_hash"]):
                result["ok"] = False
                result["broken_at"] = {
                    "event_id": row["event_id"],
                    "scope": scope,
                    "reason": "entry_hash_mismatch",
                    "expected_entry_hash": recomputed,
                    "stored_entry_hash": row["entry_hash"],
                }
                return result
            tails[scope] = row["entry_hash"]
            result["checked"] += 1

        return result

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
