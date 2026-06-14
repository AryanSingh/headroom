"""Minimal SCIM-like provisioning store for enterprise admin integrations."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from headroom import paths as _paths

SCIM_DB_ENV = "HEADROOM_SCIM_DB_PATH"

# Defense-in-depth: validate SQL column names match safe identifier pattern.
_SAFE_COL_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_col_name(name: str) -> str:
    """Validate that a column name is a safe SQL identifier."""
    if not _SAFE_COL_RE.match(name):
        raise ValueError(f"Invalid SQL column name: {name!r}")
    return name


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class ScimStore:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.environ.get(SCIM_DB_ENV, "")
        if not db_path:
            db_path = str(_paths.workspace_dir() / "scim.db")
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._local = threading.local()
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                user_name TEXT UNIQUE NOT NULL,
                display_name TEXT,
                external_id TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                emails TEXT NOT NULL DEFAULT '[]',
                meta TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                display_name TEXT UNIQUE NOT NULL,
                external_id TEXT,
                members TEXT NOT NULL DEFAULT '[]',
                meta TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()

    def create_user(
        self,
        *,
        user_name: str,
        display_name: str | None = None,
        external_id: str | None = None,
        active: bool = True,
        emails: list[dict[str, Any]] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        user_id = _new_id()
        now = _now_iso()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                INSERT INTO users (
                    id, user_name, display_name, external_id, active,
                    emails, meta, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    user_name,
                    display_name,
                    external_id,
                    int(active),
                    json.dumps(emails or []),
                    json.dumps(meta or {}),
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_user(user_id)  # type: ignore[return-value]

    def list_users(self, *, user_name: str | None = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if user_name:
            rows = conn.execute(
                "SELECT * FROM users WHERE user_name = ? ORDER BY created_at",
                (user_name,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [self._row_to_user(r) for r in rows]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def update_user(self, user_id: str, **kwargs: Any) -> dict[str, Any] | None:
        allowed = {"user_name", "display_name", "external_id", "active", "emails", "meta"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_user(user_id)
        if "emails" in updates:
            updates["emails"] = json.dumps(updates["emails"] or [])
        if "meta" in updates:
            updates["meta"] = json.dumps(updates["meta"] or {})
        if "active" in updates:
            updates["active"] = int(bool(updates["active"]))
        updates["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{_validate_col_name(k)} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        with self._lock:
            conn = self._get_conn()
            conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
            conn.commit()
        return self.get_user(user_id)

    def delete_user(self, user_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            result = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return result.rowcount > 0

    def create_group(
        self,
        *,
        display_name: str,
        external_id: str | None = None,
        members: list[dict[str, Any]] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        group_id = _new_id()
        now = _now_iso()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                INSERT INTO groups (
                    id, display_name, external_id, members, meta, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group_id,
                    display_name,
                    external_id,
                    json.dumps(members or []),
                    json.dumps(meta or {}),
                    now,
                    now,
                ),
            )
            conn.commit()
        return self.get_group(group_id)  # type: ignore[return-value]

    def list_groups(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM groups ORDER BY created_at").fetchall()
        return [self._row_to_group(r) for r in rows]

    def get_group(self, group_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        return self._row_to_group(row) if row else None

    def update_group(self, group_id: str, **kwargs: Any) -> dict[str, Any] | None:
        allowed = {"display_name", "external_id", "members", "meta"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_group(group_id)
        if "members" in updates:
            updates["members"] = json.dumps(updates["members"] or [])
        if "meta" in updates:
            updates["meta"] = json.dumps(updates["meta"] or {})
        updates["updated_at"] = _now_iso()
        set_clause = ", ".join(f"{_validate_col_name(k)} = ?" for k in updates)
        values = list(updates.values()) + [group_id]
        with self._lock:
            conn = self._get_conn()
            conn.execute(f"UPDATE groups SET {set_clause} WHERE id = ?", values)
            conn.commit()
        return self.get_group(group_id)

    def delete_group(self, group_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            result = conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
            conn.commit()
            return result.rowcount > 0

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["active"] = bool(data.get("active", 0))
        for key in ("emails", "meta"):
            if isinstance(data.get(key), str):
                try:
                    data[key] = json.loads(data[key])
                except (TypeError, json.JSONDecodeError):
                    data[key] = [] if key == "emails" else {}
        return data

    @staticmethod
    def _row_to_group(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for key in ("members", "meta"):
            if isinstance(data.get(key), str):
                try:
                    data[key] = json.loads(data[key])
                except (TypeError, json.JSONDecodeError):
                    data[key] = [] if key == "members" else {}
        return data

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


_global_store: ScimStore | None = None
_global_lock = threading.Lock()


def get_scim_store(db_path: str | Path | None = None) -> ScimStore:
    global _global_store
    if _global_store is None:
        with _global_lock:
            if _global_store is None:
                _global_store = ScimStore(db_path=db_path)
    return _global_store


def reset_scim_store() -> None:
    global _global_store
    with _global_lock:
        if _global_store is not None:
            _global_store.close()
            _global_store = None
