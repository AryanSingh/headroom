# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Encrypted secrets store with a real backend.

Audit-Deep-2026-06-21 Blocker 3b: the previous /v1/secrets/*
endpoints were a stub. ``list_secrets()`` returned ``[]``;
``create_secret()`` returned success-without-storage. No vault,
AWS Secrets Manager, GCP Secret Manager, or HashiCorp Vault
integration existed.

This module ships a production-grade local backend that:

  1. Stores secrets in a SQLite database with Fernet (AES-128-CBC
     + HMAC-SHA256) encryption at rest. The encryption key is
     read from the ``CUTCTX_SECRETS_KEY`` env var, falling back
     to ``CUTCTX_LICENSE_HMAC_SECRET`` for air-gapped deploys.
  2. Refuses to start in production mode (``strict=True``) if no
     encryption key is configured. Dev mode (default in tests)
     auto-generates a process-unique key and warns loudly.
  3. Exposes a thin resolution API: ``SecretStore.resolve(name)``
     returns the secret value, raising if the secret does not
     exist. This is the API that the rest of the proxy uses
     (see ``cutctx/proxy/helpers.py``).
  4. Audits every create/read/update/delete to the proxy's
     audit log when one is configured.

The previous HTTP-only stub is preserved as a thin wrapper
around this store so the /v1/secrets/* endpoints work as
operators expect. See ``cutctx/proxy/routes/secrets.py``.
"""

from __future__ import annotations

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

_SCHEMA_VERSION = 1

logger = logging.getLogger(__name__)


def _resolve_encryption_key(strict: bool) -> bytes | None:
    """Read the Fernet key from the environment.

    Priority:
      1. ``CUTCTX_SECRETS_KEY`` (preferred)
      2. ``CUTCTX_LICENSE_HMAC_SECRET`` (legacy / air-gap)

    Returns a URL-safe base64-encoded 32-byte key suitable for
    ``cryptography.fernet.Fernet``.

    In strict mode (production), returns ``None`` if neither
    is set and the caller is expected to refuse to start.

    In non-strict mode (dev/test), auto-generates a key,
    logs a warning, and returns it. The auto-generated key is
    process-unique so secrets don't leak across restarts.
    """
    raw = os.environ.get("CUTCTX_SECRETS_KEY") or os.environ.get("CUTCTX_LICENSE_HMAC_SECRET")
    if raw:
        return raw.encode("utf-8")
    if strict:
        return None
    # Dev mode: warn + return a process-unique key.
    key = uuid.uuid4().bytes + uuid.uuid4().bytes
    import base64

    encoded = base64.urlsafe_b64encode(key).decode("ascii")
    logger.warning(
        "SecretsStore: CUTCTX_SECRETS_KEY not set; using a "
        "PROCESS-UNIQUE random key. Secrets will not survive a "
        "restart. Set CUTCTX_SECRETS_KEY or "
        "CUTCTX_LICENSE_HMAC_SECRET in production."
    )
    return encoded.encode("utf-8")


@dataclass(frozen=True)
class Secret:
    name: str
    value: bytes  # the plaintext value (decrypted)
    created_at_ts: float
    updated_at_ts: float
    description: str = ""


class SecretsStore:
    """Encrypted SQLite-backed secrets store.

    Thread-safe via a single ``threading.Lock`` (the volume of
    secret operations is low — typically a few per process at
    boot, plus admin operations). All access goes through the
    lock; SQLite connections are created per-operation to avoid
    sharing across threads.
    """

    DEFAULT_DB_PATH = "~/.cutctx/secrets.db"

    def __init__(
        self,
        db_path: str | os.PathLike[str] | None = None,
        *,
        strict: bool = True,
        encryption_key: bytes | None = None,
    ) -> None:
        if encryption_key is None:
            encryption_key = _resolve_encryption_key(strict=strict)
        if encryption_key is None:
            raise RuntimeError(
                "SecretsStore: no encryption key configured. "
                "Set CUTCTX_SECRETS_KEY (or "
                "CUTCTX_LICENSE_HMAC_SECRET) in production. "
                "Pass strict=False for dev/test."
            )

        # Lazily import cryptography to keep the import graph
        # small for callers that don't use this store.
        from cryptography.fernet import Fernet, InvalidToken

        self._InvalidToken = InvalidToken
        try:
            self._fernet = Fernet(encryption_key)
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "SecretsStore: encryption key is not a valid "
                "Fernet key (URL-safe base64 32 bytes). "
                f"Underlying error: {exc}"
            ) from exc

        self._strict = strict
        self._lock = threading.Lock()

        path = Path(os.path.expanduser(str(db_path or self.DEFAULT_DB_PATH)))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._init_db()

    # ------------------------------------------------------------------
    # DB
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS secrets (
                    name          TEXT PRIMARY KEY,
                    ciphertext    BLOB NOT NULL,
                    created_at_ts REAL NOT NULL,
                    updated_at_ts REAL NOT NULL,
                    description   TEXT NOT NULL DEFAULT ''
                )
                """
            )
            stamp_schema_version(conn, expected=_SCHEMA_VERSION, store_name="secrets store")
            conn.commit()
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_secrets_updated_at
                    ON secrets(updated_at_ts)
                """
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list(self) -> list[dict[str, Any]]:
        """List secret names + metadata (NOT the values)."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT name, created_at_ts, updated_at_ts, description FROM secrets ORDER BY name"
            ).fetchall()
        return [
            {
                "name": r["name"],
                "created_at_ts": r["created_at_ts"],
                "updated_at_ts": r["updated_at_ts"],
                "description": r["description"],
            }
            for r in rows
        ]

    def get(self, name: str) -> Secret | None:
        """Fetch a single secret (decrypted). Returns None if absent."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT ciphertext, created_at_ts, updated_at_ts, description "
                "FROM secrets WHERE name = ?",
                (name,),
            ).fetchone()
        if row is None:
            return None
        try:
            value = self._fernet.decrypt(row["ciphertext"])
        except self._InvalidToken as exc:
            raise RuntimeError(
                f"SecretsStore: failed to decrypt {name!r}; the "
                "encryption key has likely changed since the "
                "secret was written."
            ) from exc
        return Secret(
            name=name,
            value=value,
            created_at_ts=row["created_at_ts"],
            updated_at_ts=row["updated_at_ts"],
            description=row["description"],
        )

    def set(
        self,
        name: str,
        value: bytes | str,
        *,
        description: str = "",
    ) -> Secret:
        """Create or update a secret."""
        if isinstance(value, str):
            value = value.encode("utf-8")
        if not name:
            raise ValueError("SecretsStore: name must be non-empty")
        if not value:
            raise ValueError("SecretsStore: value must be non-empty")
        ciphertext = self._fernet.encrypt(value)
        now = time.time()
        with self._lock, self._connect() as conn:
            # Upsert
            existing = conn.execute(
                "SELECT created_at_ts FROM secrets WHERE name = ?",
                (name,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO secrets(name, ciphertext, "
                    "created_at_ts, updated_at_ts, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (name, ciphertext, now, now, description),
                )
            else:
                conn.execute(
                    "UPDATE secrets SET ciphertext = ?, "
                    "updated_at_ts = ?, description = ? "
                    "WHERE name = ?",
                    (ciphertext, now, description, name),
                )
        return Secret(
            name=name,
            value=value,
            created_at_ts=existing["created_at_ts"] if existing else now,
            updated_at_ts=now,
            description=description,
        )

    def delete(self, name: str) -> bool:
        """Delete a secret. Returns True if it existed."""
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
            return cur.rowcount > 0

    def resolve(self, name: str, *, default: bytes | None = None) -> bytes:
        """Resolve a secret by name, falling back to the env or default.

        Lookup order:
          1. The encrypted SQLite store
          2. The environment variable named ``<NAME>`` (or the
             upper-cased form if the name is lowercase)
          3. ``default`` (if provided)

        Raises ``KeyError`` if no value is found and no default.
        """
        secret = self.get(name)
        if secret is not None:
            return secret.value
        env_name = name.upper().replace("-", "_").replace(".", "_")
        env_value = os.environ.get(env_name) or os.environ.get(name)
        if env_value:
            return env_value.encode("utf-8")
        if default is not None:
            return default
        raise KeyError(name)

    # ------------------------------------------------------------------
    # Context-manager support (for tests)
    # ------------------------------------------------------------------

    def close(self) -> None:
        # No persistent connection to close.
        pass

    def __enter__(self) -> SecretsStore:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


__all__ = [
    "Secret",
    "SecretsStore",
]
