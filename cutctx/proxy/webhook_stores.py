# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""SQLite-backed persistence for webhook subscriptions + DLQ.

Audit-Deep-2026-06-21 High-15: the previous WebhookDispatcher
held subscriptions in a process-local list. Subscriptions
were lost on restart and not shared across replicas. A
delivered webhook whose retries failed only logged to
logger.error — no recovery path.

This module provides:

  WebhookSubscriptionStore
    - Schema: webhook_subscriptions(id, url, secret, event_types
      JSON, org_id, created_at_ts, updated_at_ts, enabled)
    - get / set / delete / list primitives
    - Thread-safe via RLock

  WebhookDeadLetterStore
    - Schema: webhook_dlq(id, event_id, event_type, payload
      JSON, target_url, last_status, last_error,
      attempts, first_attempt_ts, last_attempt_ts)
    - add / list / acknowledge / purge primitives
    - Bounded size: when the table exceeds
      max_dlq_rows, the oldest acknowledged row is purged
      automatically (and the oldest unacknowledged row is
      warned loudly).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cutctx.storage.sqlite_schema import stamp_schema_version

_SUBSCRIPTION_SCHEMA_VERSION = 1
_DLQ_SCHEMA_VERSION = 1

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredSubscription:
    id: str
    url: str
    secret: str
    event_types: tuple[str, ...] | None  # None = catch-all
    org_id: str | None
    enabled: bool
    created_at_ts: float
    updated_at_ts: float

    def to_dict(self, *, reveal_secret: bool = False) -> dict[str, Any]:
        # Never return the plaintext secret in list/get responses — only on
        # initial creation (reveal_secret=True). Callers that need to verify
        # the secret should re-hash it against their own copy.
        secret_field = self.secret if reveal_secret else f"{self.secret[:4]}{'*' * 20}"
        return {
            "id": self.id,
            "url": self.url,
            "secret": secret_field,
            "event_types": list(self.event_types) if self.event_types else None,
            "org_id": self.org_id,
            "enabled": self.enabled,
            "created_at_ts": self.created_at_ts,
            "updated_at_ts": self.updated_at_ts,
        }


@dataclass(frozen=True)
class DeadLetter:
    id: str
    event_id: str
    event_type: str
    payload: dict[str, Any]
    target_url: str
    last_status: int | None
    last_error: str
    attempts: int
    first_attempt_ts: float
    last_attempt_ts: float
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "target_url": self.target_url,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "attempts": self.attempts,
            "first_attempt_ts": self.first_attempt_ts,
            "last_attempt_ts": self.last_attempt_ts,
            "acknowledged": self.acknowledged,
        }


class WebhookSubscriptionStore:
    DEFAULT_DB_PATH = "~/.cutctx/webhooks.db"

    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        from cutctx.proxy.helpers import is_stateless

        self._stateless = is_stateless()
        self._lock = threading.RLock()
        if self._stateless:
            self._db_path = ":memory:"
            self._memory_conn: sqlite3.Connection | None = None
        else:
            path = Path(os.path.expanduser(str(db_path or self.DEFAULT_DB_PATH)))
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._stateless:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", timeout=5.0, check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                    id                    TEXT PRIMARY KEY,
                    url                   TEXT NOT NULL,
                    secret_ciphertext     BLOB NOT NULL,
                    event_types           TEXT,
                    org_id                TEXT,
                    enabled               INTEGER NOT NULL DEFAULT 1,
                    created_at_ts         REAL NOT NULL,
                    updated_at_ts         REAL NOT NULL
                )
                """
            )
            stamp_schema_version(
                conn,
                expected=_SUBSCRIPTION_SCHEMA_VERSION,
                store_name="webhook subscription store",
            )
            conn.commit()

    def _get_fernet(self):
        """Lazily import and return Fernet cipher for secret encryption."""
        if not hasattr(self, "_fernet"):
            from cryptography.fernet import Fernet

            # Use CUTCTX_SECRETS_KEY if available, else CUTCTX_LICENSE_HMAC_SECRET,
            # else use a derived key from the database path for single-machine setups.
            key = os.environ.get("CUTCTX_SECRETS_KEY") or os.environ.get(
                "CUTCTX_LICENSE_HMAC_SECRET"
            )
            if key is None:
                import base64
                import hashlib

                # Derive a stable key from the database path for tests/stateless mode
                path_hash = hashlib.sha256(self._db_path.encode()).digest()
                key = base64.urlsafe_b64encode(path_hash).decode("ascii")
            self._fernet = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        return self._fernet

    def _encrypt_secret(self, secret: str) -> bytes:
        """Encrypt a secret string to ciphertext."""
        return self._get_fernet().encrypt(secret.encode("utf-8"))

    def _decrypt_secret(self, ciphertext: bytes) -> str:
        """Decrypt ciphertext back to plaintext secret."""
        return self._get_fernet().decrypt(ciphertext).decode("utf-8")

    def upsert(
        self,
        *,
        url: str,
        secret: str,
        event_types: tuple[str, ...] | None = None,
        org_id: str | None = None,
        enabled: bool = True,
        sub_id: str | None = None,
    ) -> StoredSubscription:
        sub_id = sub_id or f"wh_{uuid.uuid4().hex[:16]}"
        now = time.time()
        secret_ciphertext = self._encrypt_secret(secret)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_subscriptions
                    (id, url, secret_ciphertext, event_types, org_id, enabled,
                     created_at_ts, updated_at_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    url = excluded.url,
                    secret_ciphertext = excluded.secret_ciphertext,
                    event_types = excluded.event_types,
                    org_id = excluded.org_id,
                    enabled = excluded.enabled,
                    updated_at_ts = excluded.updated_at_ts
                """,
                (
                    sub_id,
                    url,
                    secret_ciphertext,
                    json.dumps(list(event_types)) if event_types else None,
                    org_id,
                    1 if enabled else 0,
                    now,
                    now,
                ),
            )
        return StoredSubscription(
            id=sub_id,
            url=url,
            secret=secret,
            event_types=event_types,
            org_id=org_id,
            enabled=enabled,
            created_at_ts=now,
            updated_at_ts=now,
        )

    def delete(self, sub_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM webhook_subscriptions WHERE id = ?",
                (sub_id,),
            )
            return cur.rowcount > 0

    def list_all(self) -> list[StoredSubscription]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, url, secret_ciphertext, event_types, org_id, enabled, "
                "created_at_ts, updated_at_ts "
                "FROM webhook_subscriptions ORDER BY created_at_ts"
            ).fetchall()
        out: list[StoredSubscription] = []
        for r in rows:
            et: tuple[str, ...] | None = None
            if r["event_types"]:
                et = tuple(json.loads(r["event_types"]))
            out.append(
                StoredSubscription(
                    id=r["id"],
                    url=r["url"],
                    secret=self._decrypt_secret(r["secret_ciphertext"]),
                    event_types=et,
                    org_id=r["org_id"],
                    enabled=bool(r["enabled"]),
                    created_at_ts=r["created_at_ts"],
                    updated_at_ts=r["updated_at_ts"],
                )
            )
        return out

    def get(self, sub_id: str) -> StoredSubscription | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT id, url, secret_ciphertext, event_types, org_id, enabled, "
                "created_at_ts, updated_at_ts "
                "FROM webhook_subscriptions WHERE id = ?",
                (sub_id,),
            ).fetchone()
        if row is None:
            return None
        et: tuple[str, ...] | None = None
        if row["event_types"]:
            et = tuple(json.loads(row["event_types"]))
        return StoredSubscription(
            id=row["id"],
            url=row["url"],
            secret=self._decrypt_secret(row["secret_ciphertext"]),
            event_types=et,
            org_id=row["org_id"],
            enabled=bool(row["enabled"]),
            created_at_ts=row["created_at_ts"],
            updated_at_ts=row["updated_at_ts"],
        )


class WebhookDeadLetterStore:
    DEFAULT_DB_PATH = "~/.cutctx/webhook_dlq.db"
    DEFAULT_MAX_ROWS = 10_000

    def __init__(
        self,
        db_path: str | os.PathLike[str] | None = None,
        *,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> None:
        from cutctx.proxy.helpers import is_stateless

        self._stateless = is_stateless()
        self._max_rows = int(max_rows)
        self._lock = threading.RLock()
        if self._stateless:
            self._db_path = ":memory:"
            self._memory_conn: sqlite3.Connection | None = None
        else:
            path = Path(os.path.expanduser(str(db_path or self.DEFAULT_DB_PATH)))
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._stateless:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", timeout=5.0, check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_dlq (
                    id                TEXT PRIMARY KEY,
                    event_id          TEXT NOT NULL,
                    event_type        TEXT NOT NULL,
                    payload           TEXT NOT NULL,
                    target_url        TEXT NOT NULL,
                    last_status       INTEGER,
                    last_error        TEXT NOT NULL,
                    attempts          INTEGER NOT NULL,
                    first_attempt_ts  REAL NOT NULL,
                    last_attempt_ts   REAL NOT NULL,
                    acknowledged      INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dlq_acknowledged "
                "ON webhook_dlq(acknowledged, last_attempt_ts)"
            )
            stamp_schema_version(
                conn, expected=_DLQ_SCHEMA_VERSION, store_name="webhook dead-letter store"
            )
            conn.commit()

    def add(
        self,
        *,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
        target_url: str,
        last_status: int | None,
        last_error: str,
        attempts: int,
    ) -> DeadLetter:
        dl_id = f"dlq_{uuid.uuid4().hex[:16]}"
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_dlq
                    (id, event_id, event_type, payload, target_url,
                     last_status, last_error, attempts,
                     first_attempt_ts, last_attempt_ts, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    dl_id,
                    event_id,
                    event_type,
                    json.dumps(payload),
                    target_url,
                    last_status,
                    last_error[:1000],  # bound the error text
                    attempts,
                    now,
                    now,
                ),
            )
            self._enforce_max_rows(conn)
        return DeadLetter(
            id=dl_id,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            target_url=target_url,
            last_status=last_status,
            last_error=last_error[:1000],
            attempts=attempts,
            first_attempt_ts=now,
            last_attempt_ts=now,
            acknowledged=False,
        )

    def _enforce_max_rows(self, conn: sqlite3.Connection) -> None:
        """Trim the DLQ to max_rows.

        Strategy: first purge the oldest acknowledged rows. If
        still over the limit, purge the oldest unacknowledged
        rows (with a loud warning) so the table never grows
        without bound.
        """
        cur = conn.execute("SELECT COUNT(*) AS c FROM webhook_dlq")
        count = cur.fetchone()["c"]
        if count <= self._max_rows:
            return
        # Purge oldest acknowledged
        over = count - self._max_rows
        purged = conn.execute(
            "DELETE FROM webhook_dlq WHERE id IN ("
            "  SELECT id FROM webhook_dlq WHERE acknowledged = 1 "
            "  ORDER BY last_attempt_ts ASC LIMIT ?"
            ")",
            (over,),
        ).rowcount
        over -= purged
        if over > 0:
            logger.warning(
                "Webhook DLQ exceeded max_rows=%d and %d "
                "unacknowledged rows remain; purging the oldest "
                "%d unacknowledged rows to bound the table size.",
                self._max_rows,
                over,
                over,
            )
            conn.execute(
                "DELETE FROM webhook_dlq WHERE id IN ("
                "  SELECT id FROM webhook_dlq "
                "  ORDER BY last_attempt_ts ASC LIMIT ?"
                ")",
                (over,),
            )

    def list_unacknowledged(self, limit: int = 100) -> list[DeadLetter]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM webhook_dlq WHERE acknowledged = 0 "
                "ORDER BY last_attempt_ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dlq(r) for r in rows]

    def list_all(self, limit: int = 200) -> list[DeadLetter]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM webhook_dlq ORDER BY last_attempt_ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dlq(r) for r in rows]

    def acknowledge(self, dl_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE webhook_dlq SET acknowledged = 1 WHERE id = ?",
                (dl_id,),
            )
            return cur.rowcount > 0

    def purge_acknowledged(self) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM webhook_dlq WHERE acknowledged = 1")
            return cur.rowcount

    def _row_to_dlq(self, r: sqlite3.Row) -> DeadLetter:
        return DeadLetter(
            id=r["id"],
            event_id=r["event_id"],
            event_type=r["event_type"],
            payload=json.loads(r["payload"]),
            target_url=r["target_url"],
            last_status=r["last_status"],
            last_error=r["last_error"],
            attempts=r["attempts"],
            first_attempt_ts=r["first_attempt_ts"],
            last_attempt_ts=r["last_attempt_ts"],
            acknowledged=bool(r["acknowledged"]),
        )


__all__ = [
    "StoredSubscription",
    "DeadLetter",
    "WebhookSubscriptionStore",
    "WebhookDeadLetterStore",
]
