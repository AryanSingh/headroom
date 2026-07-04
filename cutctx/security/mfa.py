# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""TOTP (RFC 6238) implementation for admin MFA.

Audit-Deep-2026-06-21 High-12: enterprise admin auth was a
single factor (admin key OR SSO). MFA closes the second-factor
gap using TOTP (RFC 6238) — the same algorithm used by Google
Authenticator, Authy, 1Password, etc. Operators enroll once via
the /v1/admin/mfa endpoint and authenticate subsequent
requests with a 6-digit code from their authenticator app.

The implementation is stdlib-only (hmac, hashlib, struct, time,
base64) so we do not need to add a new dependency. The spec
itself is small enough that this is reasonable.

The TOTP secret is stored alongside the RBAC store (we use the
same SQLite DB). The secret is base32-encoded per RFC 4648.

Threat model:
  - Replay: codes are valid for a 30-second window and
    cannot be reused (single-use enforced by a "last used"
    counter).
  - Phishing: codes are bound to the secret, which is bound
    to the admin's user_id.
  - Brute force: codes are 6 digits -> 10^6 = 1M codes; rate
    limiting at the HTTP layer caps attempts.
  - Clock skew: a 1-step window (±30s) on either side is
    accepted.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# RFC 6238 step size in seconds.
TOTP_STEP_S = 30
TOTP_DIGITS = 6
# Accept one step of clock drift on either side (±30s).
TOTP_WINDOW = 1


@dataclass(frozen=True)
class TotpCode:
    code: str
    remaining_s: int


def _base32_decode(s: str) -> bytes:
    """Decode base32 (RFC 4648) without padding, leniency."""
    pad = "=" * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s.upper() + pad)


def _base32_encode(b: bytes) -> str:
    """Encode bytes as base32 (RFC 4648), no padding."""
    return base64.b32encode(b).decode("ascii").rstrip("=")


def _hotp(secret: bytes, counter: int) -> str:
    """HOTP per RFC 4226.

    HMAC-SHA1(secret, counter_8byte_be) -> 4-byte dynamic
    truncation -> modulo 10**digits.
    """
    counter_bytes = struct.pack(">Q", counter)
    digest = hmac.new(secret, counter_bytes, hashlib.sha1).digest()
    # Dynamic truncation: low 4 bits of the last byte are the
    # offset into the digest where we take 4 bytes (big-endian).
    offset = digest[-1] & 0x0F
    code_int = (
        (digest[offset] & 0x7F) << 24
        | (digest[offset + 1] & 0xFF) << 16
        | (digest[offset + 2] & 0xFF) << 8
        | (digest[offset + 3] & 0xFF)
    ) % (10**TOTP_DIGITS)
    return f"{code_int:0{TOTP_DIGITS}d}"


def generate_secret() -> str:
    """Generate a fresh 160-bit (20-byte) TOTP secret.

    Returns the base32-encoded form, which is what the
    operator pastes into their authenticator app.
    """
    return _base32_encode(secrets.token_bytes(20))


def current_totp(secret_b32: str, *, now: float | None = None) -> TotpCode:
    """Return the TOTP code for the current 30-second window."""
    secret = _base32_decode(secret_b32)
    now = now if now is not None else time.time()
    counter = int(now) // TOTP_STEP_S
    code = _hotp(secret, counter)
    remaining = TOTP_STEP_S - (int(now) % TOTP_STEP_S)
    return TotpCode(code=code, remaining_s=remaining)


def verify_totp(
    secret_b32: str,
    code: str,
    *,
    now: float | None = None,
    last_used_counter: int | None = None,
) -> bool:
    """Verify a TOTP code.

    Audit-Deep-2026-06-21 High-12: a single-use counter
    (last_used_counter) prevents replay. Codes are valid for
    TOTP_WINDOW steps on either side of the current step to
    absorb clock skew.

    Returns True iff:
      - the code is 6 digits and parses as an int
      - the code matches the current step OR one of the
        surrounding steps
      - the matched step is strictly newer than the last
        used step (replay protection)
    """
    secret = _base32_decode(secret_b32)
    now = now if now is not None else time.time()
    counter = int(now) // TOTP_STEP_S
    # Coerce the user-supplied code into a 6-digit string.
    code = (code or "").strip()
    if len(code) != TOTP_DIGITS or not code.isdigit():
        return False
    for offset in range(-TOTP_WINDOW, TOTP_WINDOW + 1):
        candidate_counter = counter + offset
        if last_used_counter is not None and candidate_counter <= last_used_counter:
            # Already used (or older) -> reject to prevent replay
            continue
        if _hotp(secret, candidate_counter) == code:
            return True
    return False


# ── SQLite-backed MFA store ────────────────────────────────────────────────


class MfaStore:
    """SQLite-backed storage for MFA enrollments.

    Schema:
        mfa_enrollments(
            user_id       TEXT PRIMARY KEY,
            secret_b32    TEXT NOT NULL,
            enrolled_at   REAL NOT NULL,
            last_used_counter INTEGER NOT NULL DEFAULT 0
        )

    The store is colocated with the RBAC store in the same
    database file (~/.cutctx/rbac.db) so a single file
    backs both subsystems.
    """

    TABLE_NAME = "mfa_enrollments"

    def __init__(self, db_path: str | os.PathLike[str]) -> None:
        path = Path(str(db_path))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self):
        import sqlite3

        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    user_id           TEXT PRIMARY KEY,
                    secret_b32        TEXT NOT NULL,
                    enrolled_at       REAL NOT NULL,
                    last_used_counter INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def get(self, user_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                f"SELECT user_id, secret_b32, enrolled_at, last_used_counter "
                f"FROM {self.TABLE_NAME} WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "user_id": row["user_id"],
            "secret_b32": row["secret_b32"],
            "enrolled_at": row["enrolled_at"],
            "last_used_counter": row["last_used_counter"],
        }

    def enroll(self, user_id: str, secret_b32: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {self.TABLE_NAME}(user_id, secret_b32, enrolled_at, last_used_counter)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    secret_b32 = excluded.secret_b32,
                    enrolled_at = excluded.enrolled_at,
                    last_used_counter = 0
                """,
                (user_id, secret_b32, time.time()),
            )

    def revoke(self, user_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE user_id = ?",
                (user_id,),
            )
            return cur.rowcount > 0

    def consume_counter(self, user_id: str, counter: int) -> bool:
        """Atomically advance last_used_counter iff > current.

        Returns True iff the counter advanced (i.e. the code
        was fresh and is now single-use). Used after a
        successful verify() to prevent replay.
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"UPDATE {self.TABLE_NAME} SET last_used_counter = ? "
                f"WHERE user_id = ? AND last_used_counter < ?",
                (counter, user_id, counter),
            )
            return cur.rowcount > 0


__all__ = [
    "TotpCode",
    "MfaStore",
    "generate_secret",
    "current_totp",
    "verify_totp",
    "TOTP_STEP_S",
    "TOTP_DIGITS",
]
