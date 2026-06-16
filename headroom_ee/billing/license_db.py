# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""SQLite-backed license database for the hosted license portal."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

_DB_PATH = Path.home() / ".headroom" / "licenses.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS licenses (
    license_key TEXT PRIMARY KEY,
    tier TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    seats INTEGER NOT NULL DEFAULT 5,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    activated_at REAL NOT NULL,
    UNIQUE(license_key, instance_id)
);

CREATE TABLE IF NOT EXISTS revocations (
    license_key TEXT PRIMARY KEY,
    revoked_at REAL NOT NULL,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS seat_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    leased_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    UNIQUE(license_key, user_id)
);

CREATE TABLE IF NOT EXISTS trials (
    trial_token TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL,
    started_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
"""


def get_license_db() -> LicenseDB:
    """Get or create the singleton license DB."""
    return LicenseDB(_DB_PATH)


class LicenseDB:
    """SQLite-backed license storage."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)

    def upsert(self, record: object) -> None:
        """Insert or update a license record."""
        # Accept both LicenseRecord dataclass and raw tuple
        if hasattr(record, "license_key"):
            r = record
            self._conn.execute(
                """INSERT OR REPLACE INTO licenses
                (license_key, tier, customer_email, seats, stripe_customer_id,
                 stripe_subscription_id, created_at, expires_at, active)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    r.license_key,
                    r.tier,
                    r.customer_email,
                    r.seats,
                    r.stripe_customer_id,
                    r.stripe_subscription_id,
                    r.created_at,
                    r.expires_at,
                    1 if r.active else 0,
                ),
            )
        else:
            self._conn.execute(
                """INSERT OR REPLACE INTO licenses
                (license_key, tier, customer_email, seats, stripe_customer_id,
                 stripe_subscription_id, created_at, expires_at, active)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                record,
            )
        self._conn.commit()

    def get(self, license_key: str) -> object | None:
        """Retrieve a license by key."""
        row = self._conn.execute(
            "SELECT * FROM licenses WHERE license_key = ?", (license_key,)
        ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in self._conn.execute("SELECT * FROM licenses LIMIT 0").description]
        return _LicenseRecord(**dict(zip(cols, row)))

    def validate(self, license_key: str) -> dict:
        """API-friendly validation response."""
        record = self.get(license_key)
        if not record:
            return {"valid": False, "reason": "key_not_found"}
        if not record.active:
            return {"valid": False, "reason": "subscription_cancelled"}
        if record.expires_at < time.time():
            return {"valid": False, "reason": "expired"}
        return {
            "valid": True,
            "tier": record.tier,
            "seats": record.seats,
            "expires_at": record.expires_at,
        }

    def list_all(self) -> list[dict]:
        """List all licenses."""
        rows = self._conn.execute(
            "SELECT license_key, tier, customer_email, active, expires_at FROM licenses"
        ).fetchall()
        return [
            {
                "license_key": r[0],
                "tier": r[1],
                "customer_email": r[2],
                "active": bool(r[3]),
                "expires_at": r[4],
            }
            for r in rows
        ]

    def activate_instance(self, license_key: str, instance_id: str) -> bool:
        """Record a proxy instance activation against this license."""
        try:
            self._conn.execute(
                "INSERT INTO activations (license_key, instance_id, activated_at) VALUES (?, ?, ?)",
                (license_key, instance_id, time.time()),
            )
            self._conn.commit()
            self._emit_audit("license.activate_instance", {"license_key": license_key, "instance_id": instance_id})
            return True
        except sqlite3.IntegrityError:
            return False

    def _emit_audit(self, action: str, payload: dict) -> None:
        try:
            from headroom_ee.audit.api import get_store as get_audit_store
            store = get_audit_store()
            store.append_event(
                tenant_id="system",  # License actions are system-level
                actor="admin",
                action=action,
                payload=payload,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to emit audit event: {e}")

    def revoke_license(self, license_key: str, reason: str = "") -> None:
        """Revoke a license key (add to CRL)."""
        self._conn.execute(
            "INSERT OR REPLACE INTO revocations (license_key, revoked_at, reason) VALUES (?, ?, ?)",
            (license_key, time.time(), reason),
        )
        self._conn.commit()
        self._emit_audit("license.revoke", {"license_key": license_key, "reason": reason})

    def is_revoked(self, license_key: str) -> bool:
        """Check if a license is revoked."""
        row = self._conn.execute(
            "SELECT 1 FROM revocations WHERE license_key = ?", (license_key,)
        ).fetchone()
        return bool(row)

    def get_crl(self) -> list[str]:
        """Get all revoked license keys."""
        rows = self._conn.execute("SELECT license_key FROM revocations").fetchall()
        return [r[0] for r in rows]

    def checkout_seat(self, license_key: str, user_id: str, lease_duration: float) -> bool:
        """Checkout or renew a seat lease. Returns False if no seats available."""
        now = time.time()
        # Clean up expired leases
        self._conn.execute("DELETE FROM seat_leases WHERE expires_at < ?", (now,))

        # Check max seats
        record = self.get(license_key)
        if not record:
            return False

        active_leases = self._conn.execute(
            "SELECT count(*) FROM seat_leases WHERE license_key = ?", (license_key,)
        ).fetchone()[0]

        if record.seats > 0 and active_leases >= record.seats:
            # Check if user already has a lease (renew)
            user_lease = self._conn.execute(
                "SELECT 1 FROM seat_leases WHERE license_key = ? AND user_id = ?",
                (license_key, user_id),
            ).fetchone()
            if not user_lease:
                return False

        self._conn.execute(
            """INSERT OR REPLACE INTO seat_leases (license_key, user_id, leased_at, expires_at)
               VALUES (?, ?, ?, ?)""",
            (license_key, user_id, now, now + lease_duration),
        )
        self._conn.commit()
        self._emit_audit("license.checkout_seat", {"license_key": license_key, "user_id": user_id, "duration": lease_duration})
        return True

    def start_trial(self, trial_token: str, customer_email: str, duration: float) -> bool:
        """Start a new trial using a signed token."""
        now = time.time()
        try:
            self._conn.execute(
                "INSERT INTO trials (trial_token, customer_email, started_at, expires_at) VALUES (?, ?, ?, ?)",
                (trial_token, customer_email, now, now + duration),
            )
            self._conn.commit()
            self._emit_audit("license.start_trial", {"trial_token": trial_token, "customer_email": customer_email, "duration": duration})
            return True
        except sqlite3.IntegrityError:
            return False

    def is_trial_active(self, trial_token: str) -> bool:
        """Check if a trial is active and not expired."""
        row = self._conn.execute(
            "SELECT expires_at FROM trials WHERE trial_token = ?", (trial_token,)
        ).fetchone()
        if not row:
            return False
        return row[0] > time.time()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()


class _LicenseRecord:
    """Internal license record (mirrors LicenseRecord without import)."""

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            if k == "active":
                v = bool(v)
            object.__setattr__(self, k, v)
