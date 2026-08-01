# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""SQLite-backed license database for the hosted license portal."""

from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import time
from pathlib import Path

from cutctx.storage.sqlite_schema import register_migration, stamp_schema_version

logger = logging.getLogger(__name__)

#: Env override for the licence DB location, matching the convention used by
#: the other EE stores (CUTCTX_ORG_DB_PATH, CUTCTX_AUDIT_DB_PATH,
#: CUTCTX_RBAC_DB_PATH, CUTCTX_SCIM_DB_PATH).
LICENSE_DB_ENV = "CUTCTX_LICENSE_DB_PATH"
LICENSE_DELIVERY_STALE_SECONDS = 300

_SCHEMA_VERSION = 2


def resolve_db_path() -> Path:
    """Resolve the licence DB path, honouring the env override.

    Resolved on **every call**, not once at import. The previous module-level
    ``_DB_PATH = Path.home() / ".cutctx" / "licenses.db"`` was evaluated when
    the module was first imported, which had two consequences:

    * the path could not be overridden at all — this was the only EE store
      without an env override; and
    * it silently captured whatever ``HOME`` happened to be at import time. In
      a combined pytest session, importing this module during collection froze
      the path to the developer's real ``~/.cutctx/licenses.db``, so tests read
      and mutated real licence data. Three licensing tests failed only in that
      configuration, because seats had been consumed and trial tokens marked
      used by earlier runs.
    """
    override = os.environ.get(LICENSE_DB_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cutctx" / "licenses.db"


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

CREATE TABLE IF NOT EXISTS license_deliveries (
    license_key TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL,
    tier TEXT NOT NULL,
    seats INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at REAL NOT NULL,
    claimed_at REAL,
    claim_token TEXT,
    delivered_at REAL
);
"""


def _enforce_subscription_uniqueness(conn: sqlite3.Connection) -> None:
    """Keep one deterministic association before installing the unique index."""
    duplicate_ids = conn.execute(
        """SELECT stripe_subscription_id FROM licenses
           WHERE stripe_subscription_id IS NOT NULL AND stripe_subscription_id <> ''
           GROUP BY stripe_subscription_id HAVING count(*) > 1"""
    ).fetchall()
    for (subscription_id,) in duplicate_ids:
        canonical = conn.execute(
            """SELECT license_key FROM licenses WHERE stripe_subscription_id = ?
               ORDER BY created_at ASC, license_key ASC LIMIT 1""",
            (subscription_id,),
        ).fetchone()
        duplicates = conn.execute(
            """SELECT license_key FROM licenses
               WHERE stripe_subscription_id = ? AND license_key <> ?""",
            (subscription_id, canonical[0]),
        ).fetchall()
        reason = (
            "duplicate subscription association detached during license database migration "
            f"for subscription {subscription_id!r}; operator review required"
        )
        revoked_at = time.time()
        for (license_key,) in duplicates:
            conn.execute(
                """INSERT INTO revocations (license_key, revoked_at, reason) VALUES (?, ?, ?)
                   ON CONFLICT(license_key) DO UPDATE SET revoked_at=excluded.revoked_at,
                       reason=excluded.reason""",
                (license_key, revoked_at, reason),
            )
        conn.execute(
            """UPDATE licenses SET stripe_subscription_id = NULL, active = 0
               WHERE stripe_subscription_id = ? AND license_key <> ?""",
            (subscription_id, canonical[0]),
        )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS licenses_stripe_subscription_id_unique
           ON licenses(stripe_subscription_id)
           WHERE stripe_subscription_id IS NOT NULL AND stripe_subscription_id <> ''"""
    )


def _ensure_delivery_claim_lease(conn: sqlite3.Connection) -> None:
    """Add unshipped v2 lease fields to databases made by earlier v2 builds."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(license_deliveries)").fetchall()}
    if "claimed_at" not in columns:
        conn.execute("ALTER TABLE license_deliveries ADD COLUMN claimed_at REAL")
    if "claim_token" not in columns:
        conn.execute("ALTER TABLE license_deliveries ADD COLUMN claim_token TEXT")


@register_migration("license database", 1)
def _migrate_license_database_to_v1(conn: sqlite3.Connection) -> None:
    """Represent the original schema for unversioned historical databases."""


@register_migration("license database", 2)
def _migrate_license_database_to_v2(conn: sqlite3.Connection) -> None:
    """Install durable delivery state and a safe subscription uniqueness constraint."""
    _ensure_delivery_claim_lease(conn)
    _enforce_subscription_uniqueness(conn)


def get_license_db() -> LicenseDB:
    """Open the licence DB at its currently-configured path."""
    return LicenseDB(resolve_db_path())


class LicenseDB:
    """SQLite-backed license storage."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        stamp_schema_version(self._conn, expected=_SCHEMA_VERSION, store_name="license database")
        # New databases are stamped directly from version 0; legacy databases
        # run the migration above. Running this idempotently covers both paths.
        _ensure_delivery_claim_lease(self._conn)
        _enforce_subscription_uniqueness(self._conn)
        self._conn.commit()

    def upsert(self, record: object) -> None:
        """Insert or update a license record."""
        values = self._license_values(record)
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                """INSERT INTO licenses
                (license_key, tier, customer_email, seats, stripe_customer_id,
                 stripe_subscription_id, created_at, expires_at, active)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(license_key) DO UPDATE SET
                  tier=excluded.tier, customer_email=excluded.customer_email,
                  seats=excluded.seats, stripe_customer_id=excluded.stripe_customer_id,
                  stripe_subscription_id=excluded.stripe_subscription_id,
                  created_at=excluded.created_at, expires_at=excluded.expires_at,
                  active=excluded.active""",
                values,
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    @staticmethod
    def _license_values(record: object) -> tuple[object, ...]:
        """Return a normalized database tuple for records and legacy tuples."""
        if not hasattr(record, "license_key"):
            return tuple(record)  # type: ignore[arg-type]
        r = record
        return (
            r.license_key,
            r.tier,
            r.customer_email,
            r.seats,
            r.stripe_customer_id,
            r.stripe_subscription_id,
            r.created_at,
            r.expires_at,
            1 if r.active else 0,
        )

    def fulfill_checkout(self, record: object) -> tuple[object, bool]:
        """Persist a checkout exactly once for a Stripe subscription.

        ``BEGIN IMMEDIATE`` serializes the subscription lookup and insert
        across independent SQLite connections. Replayed or concurrent webhook
        deliveries receive the first issued license instead of minting a new
        key. Checkout sessions without a subscription ID remain one-time
        inserts because Stripe provides no stable subscription identity.
        """
        subscription_id = str(getattr(record, "stripe_subscription_id", "") or "")
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            if subscription_id:
                row = self._conn.execute(
                    "SELECT * FROM licenses WHERE stripe_subscription_id = ? LIMIT 1",
                    (subscription_id,),
                ).fetchone()
                if row:
                    cols = [
                        d[0]
                        for d in self._conn.execute("SELECT * FROM licenses LIMIT 0").description
                    ]
                    self._conn.commit()
                    return _LicenseRecord(**dict(zip(cols, row))), False

            self._conn.execute(
                """INSERT INTO licenses
                (license_key, tier, customer_email, seats, stripe_customer_id,
                 stripe_subscription_id, created_at, expires_at, active)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    record.license_key,
                    record.tier,
                    record.customer_email,
                    record.seats,
                    record.stripe_customer_id,
                    record.stripe_subscription_id,
                    record.created_at,
                    record.expires_at,
                    1 if record.active else 0,
                ),
            )
            self._queue_delivery(record)
            self._conn.commit()
            return record, True
        except sqlite3.IntegrityError:
            self._conn.rollback()
            # The index is the final authority if another writer committed a
            # matching subscription between our lookup and insert.
            if subscription_id:
                canonical = self.get_by_subscription_id(subscription_id)
                if canonical is not None:
                    return canonical, False
            raise
        except Exception:
            self._conn.rollback()
            raise

    def _queue_delivery(self, record: object) -> None:
        """Create a pending outbox entry while the license transaction is open."""
        self._conn.execute(
            """INSERT OR IGNORE INTO license_deliveries
            (license_key, customer_email, tier, seats, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)""",
            (
                record.license_key,
                record.customer_email,
                record.tier,
                record.seats,
                time.time(),
            ),
        )

    def claim_license_delivery(self, license_key: str) -> str | None:
        """Claim work and return its fencing token, or ``None`` if it is owned."""
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            claimed_at = time.time()
            claim_token = secrets.token_urlsafe(18)
            cursor = self._conn.execute(
                """UPDATE license_deliveries
                   SET status = 'sending', claimed_at = ?, claim_token = ?,
                       attempts = attempts + 1, last_error = NULL
                   WHERE license_key = ? AND status = 'pending'""",
                (claimed_at, claim_token, license_key),
            )
            if not cursor.rowcount:
                cursor = self._conn.execute(
                    """UPDATE license_deliveries
                       SET claimed_at = ?, claim_token = ?, attempts = attempts + 1, last_error = NULL
                       WHERE license_key = ? AND status = 'sending'
                         AND (claimed_at IS NULL OR claimed_at <= ?)""",
                    (
                        claimed_at,
                        claim_token,
                        license_key,
                        claimed_at - LICENSE_DELIVERY_STALE_SECONDS,
                    ),
                )
            self._conn.commit()
            return claim_token if cursor.rowcount else None
        except Exception:
            self._conn.rollback()
            raise

    def mark_license_delivery_delivered(self, license_key: str, claim_token: str) -> bool:
        """Record hook completion only when its current claim still owns the row."""
        cursor = self._conn.execute(
            """UPDATE license_deliveries
               SET status = 'delivered', delivered_at = ?, claimed_at = NULL, claim_token = NULL
               WHERE license_key = ? AND status = 'sending' AND claim_token = ?""",
            (time.time(), license_key, claim_token),
        )
        self._conn.commit()
        return bool(cursor.rowcount)

    def release_license_delivery(
        self, license_key: str, claim_token: str, error: Exception
    ) -> bool:
        """Release only the current owner's failed hook attempt for retry."""
        cursor = self._conn.execute(
            """UPDATE license_deliveries
               SET status = 'pending', claimed_at = NULL, claim_token = NULL, last_error = ?
               WHERE license_key = ? AND status = 'sending' AND claim_token = ?""",
            (str(error), license_key, claim_token),
        )
        self._conn.commit()
        return bool(cursor.rowcount)

    def get(self, license_key: str) -> object | None:
        """Retrieve a license by key."""
        row = self._conn.execute(
            "SELECT * FROM licenses WHERE license_key = ?", (license_key,)
        ).fetchone()
        if not row:
            return None
        cols = [d[0] for d in self._conn.execute("SELECT * FROM licenses LIMIT 0").description]
        return _LicenseRecord(**dict(zip(cols, row)))

    def get_by_subscription_id(self, subscription_id: str) -> object | None:
        """Retrieve a license by Stripe subscription ID."""
        row = self._conn.execute(
            "SELECT * FROM licenses WHERE stripe_subscription_id = ?",
            (subscription_id,),
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
        if self.is_revoked(license_key):
            return {"valid": False, "reason": "revoked"}

        parts = license_key.split("-")
        if len(parts) == 3:
            tier, random_id, sig = parts
            try:
                import cutctx._core as rust_core

                if not rust_core.verify_license_signature(
                    tier, random_id, record.stripe_customer_id, sig
                ):
                    return {"valid": False, "reason": "invalid_signature"}
            except ImportError:
                logger.warning("cutctx._core not found, cannot verify license signature")
                return {"valid": False, "reason": "signature_unverified"}
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
        """Record or renew a proxy instance activation against this license.

        Instance capacity is bounded by the licensed seat count. Renewing an
        already activated instance is idempotent and does not consume another
        slot.
        """
        try:
            # Lock before reading capacity so two connections cannot both see
            # the same free seat and insert competing leases.
            self._conn.execute("BEGIN IMMEDIATE")
            record = self.get(license_key)
            if not record:
                self._conn.rollback()
                return False
            if record.seats <= 0:
                self._conn.rollback()
                return False

            existing = self._conn.execute(
                "SELECT 1 FROM activations WHERE license_key = ? AND instance_id = ?",
                (license_key, instance_id),
            ).fetchone()
            if existing:
                self._conn.execute(
                    "UPDATE activations SET activated_at = ? WHERE license_key = ? AND instance_id = ?",
                    (time.time(), license_key, instance_id),
                )
                self._conn.commit()
                return True

            active_instances = self._conn.execute(
                "SELECT count(*) FROM activations WHERE license_key = ?",
                (license_key,),
            ).fetchone()[0]
            if active_instances >= record.seats:
                self._conn.rollback()
                return False

            self._conn.execute(
                "INSERT INTO activations (license_key, instance_id, activated_at) VALUES (?, ?, ?)",
                (license_key, instance_id, time.time()),
            )
            self._conn.commit()
            self._emit_audit(
                "license.activate_instance",
                {"license_key": license_key, "instance_id": instance_id},
            )
            return True
        except sqlite3.IntegrityError:
            self._conn.rollback()
            return False

    def _emit_audit(self, action: str, payload: dict) -> None:
        try:
            from cutctx_ee.audit.api import get_store as get_audit_store

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

    def deactivate_subscription(self, subscription_id: str) -> bool:
        """Deactivate the license attached to a cancelled subscription."""
        cursor = self._conn.execute(
            "UPDATE licenses SET active = 0 WHERE stripe_subscription_id = ?",
            (subscription_id,),
        )
        self._conn.commit()
        if cursor.rowcount:
            self._emit_audit(
                "license.subscription_deactivated",
                {"subscription_id": subscription_id},
            )
        return bool(cursor.rowcount)

    def extend_subscription(self, subscription_id: str, expires_at: float) -> bool:
        """Reactivate and extend a license after a verified paid invoice."""
        cursor = self._conn.execute(
            """UPDATE licenses SET expires_at = ?, active = 1
               WHERE stripe_subscription_id = ?""",
            (expires_at, subscription_id),
        )
        self._conn.commit()
        if cursor.rowcount:
            self._emit_audit(
                "license.subscription_extended",
                {"subscription_id": subscription_id, "expires_at": expires_at},
            )
        return bool(cursor.rowcount)

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
        try:
            # Lock before reading capacity so two connections cannot both see
            # the same free seat and insert competing leases.
            self._conn.execute("BEGIN IMMEDIATE")

            record = self.get(license_key)
            if not record or record.seats <= 0:
                self._conn.rollback()
                return False

            # Clean up expired leases inside the same write transaction.
            self._conn.execute("DELETE FROM seat_leases WHERE expires_at < ?", (now,))

            active_leases = self._conn.execute(
                "SELECT count(*) FROM seat_leases WHERE license_key = ?", (license_key,)
            ).fetchone()[0]

            # Check max seats. An existing user's lease may be renewed at
            # capacity without consuming another seat.
            if active_leases >= record.seats:
                user_lease = self._conn.execute(
                    "SELECT 1 FROM seat_leases WHERE license_key = ? AND user_id = ?",
                    (license_key, user_id),
                ).fetchone()
                if not user_lease:
                    self._conn.rollback()
                    return False

            self._conn.execute(
                """INSERT OR REPLACE INTO seat_leases (license_key, user_id, leased_at, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (license_key, user_id, now, now + lease_duration),
            )
            self._conn.commit()
        except sqlite3.Error:
            self._conn.rollback()
            return False

        self._emit_audit(
            "license.checkout_seat",
            {"license_key": license_key, "user_id": user_id, "duration": lease_duration},
        )
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
            self._emit_audit(
                "license.start_trial",
                {
                    "trial_token": trial_token,
                    "customer_email": customer_email,
                    "duration": duration,
                },
            )
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
