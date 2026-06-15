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
