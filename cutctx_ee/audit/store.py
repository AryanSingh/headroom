# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

from cutctx_ee.audit.models import AuditEvent, Base

# Blocker-9 (production-audit-2026-06-20.md): the previous default was
# the literal "dev-secret-key" which makes the hash chain forgeable in
# any deployment that forgets to set CUTCTX_AUDIT_SECRET_KEY. The
# new behavior:
#   1. If CUTCTX_AUDIT_SECRET_KEY is set: use it.
#   2. If not set AND we're not in development mode: refuse to start
#      and raise RuntimeError.
#   3. If not set AND CUTCTX_ALLOW_DEV_AUDIT_KEY=1: log a loud
#      warning and use a process-unique random key (so different
#      processes can't share the chain — break-glass only).
_CUTCTX_DEV_ALLOW_ENV = "CUTCTX_ALLOW_DEV_AUDIT_KEY"
_CUTCTX_AUDIT_SECRET_ENV = "CUTCTX_AUDIT_SECRET_KEY"


class AuditStore:
    """Tamper-evident append-only audit log store."""

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.secret_key = self._resolve_secret_key()

    @staticmethod
    def _resolve_secret_key() -> bytes:
        env_key = os.environ.get(_CUTCTX_AUDIT_SECRET_ENV, "").strip()
        if env_key:
            return env_key.encode()
        if os.environ.get(_CUTCTX_DEV_ALLOW_ENV, "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            # Process-unique random key so an attacker who steals the
            # DB still cannot forge the chain. Loud warning so this
            # never ships to production silently.
            import secrets as _secrets

            key = _secrets.token_urlsafe(32)
            import logging

            logging.getLogger(__name__).warning(
                "CUTCTX_AUDIT_SECRET_KEY not set; "
                "CUTCTX_ALLOW_DEV_AUDIT_KEY=1 is set. "
                "Generated a process-unique random key. "
                "Set CUTCTX_AUDIT_SECRET_KEY in production for a "
                "stable, deployment-wide chain."
            )
            return key.encode()
        raise RuntimeError(
            "CUTCTX_AUDIT_SECRET_KEY is required for tamper-evident "
            "audit logging. Set it in the environment to a high-entropy "
            "random value (e.g. `python -c 'import secrets; "
            "print(secrets.token_urlsafe(32))'`). For local dev only, "
            "set CUTCTX_ALLOW_DEV_AUDIT_KEY=1 to opt in to a "
            "process-unique random key."
        )

    def _compute_hash(
        self,
        tenant_id: str,
        actor: str,
        action: str,
        payload_json: str,
        timestamp_iso: str,
        previous_hash: str = None,
    ) -> str:
        """Compute the current HMAC-SHA256 chain value for the event."""
        message = self._build_hmac_message(
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            payload_json=payload_json,
            timestamp_iso=timestamp_iso,
            previous_hash=previous_hash,
        )
        return hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()

    @staticmethod
    def _length_prefix(value: str) -> bytes:
        encoded = value.encode()
        return len(encoded).to_bytes(8, "big") + encoded

    @classmethod
    def _build_hmac_message(
        cls,
        tenant_id: str,
        actor: str,
        action: str,
        payload_json: str,
        timestamp_iso: str,
        previous_hash: str = None,
    ) -> bytes:
        prior = previous_hash.encode() if previous_hash else b"0" * 64
        return b"".join(
            (
                prior,
                cls._length_prefix(tenant_id),
                cls._length_prefix(actor),
                cls._length_prefix(action),
                cls._length_prefix(payload_json),
                cls._length_prefix(timestamp_iso),
            )
        )

    def append_event(self, tenant_id: str, actor: str, action: str, payload: dict) -> dict:
        """Append a new event to the audit log."""
        with self.SessionLocal() as session:
            # Get the last event for this tenant to get the previous hash
            # We must lock the table or handle concurrency in a real DB, but for SQLite this is fine
            last_event = (
                session.query(AuditEvent)
                .filter(AuditEvent.tenant_id == tenant_id)
                .order_by(desc(AuditEvent.id))
                .first()
            )

            previous_hash = last_event.event_hash if last_event else None

            timestamp = datetime.now(timezone.utc)
            payload_json = json.dumps(payload, sort_keys=True)

            event_hash = self._compute_hash(
                tenant_id=tenant_id,
                actor=actor,
                action=action,
                payload_json=payload_json,
                timestamp_iso=timestamp.isoformat(),
                previous_hash=previous_hash,  # type: ignore[arg-type]
            )

            event = AuditEvent(
                tenant_id=tenant_id,
                timestamp=timestamp,
                actor=actor,
                action=action,
                payload=payload,
                previous_hash=previous_hash,
                event_hash=event_hash,
            )
            session.add(event)
            session.commit()
            session.refresh(event)

            return {
                "id": event.id,
                "tenant_id": event.tenant_id,
                "timestamp": event.timestamp.isoformat(),
                "actor": event.actor,
                "action": event.action,
                "payload": event.payload,
                "previous_hash": event.previous_hash,
                "event_hash": event.event_hash,
            }

    def get_events(self, tenant_id: str, limit: int = 100) -> list:
        """Retrieve recent events for a tenant."""
        with self.SessionLocal() as session:
            events = (
                session.query(AuditEvent)
                .filter(AuditEvent.tenant_id == tenant_id)
                .order_by(desc(AuditEvent.id))
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": e.id,
                    "tenant_id": e.tenant_id,
                    "timestamp": e.timestamp.isoformat(),
                    "actor": e.actor,
                    "action": e.action,
                    "payload": e.payload,
                    "previous_hash": e.previous_hash,
                    "event_hash": e.event_hash,
                }
                for e in events
            ]

    def verify_chain(self, tenant_id: str) -> bool:
        """Verify the cryptographic integrity of the audit log for a tenant."""
        with self.SessionLocal() as session:
            # Fetch all in chronological order
            events = (
                session.query(AuditEvent)
                .filter(AuditEvent.tenant_id == tenant_id)
                .order_by(AuditEvent.id)
                .all()
            )

            expected_previous_hash = None
            for e in events:
                if e.previous_hash != expected_previous_hash:
                    return False

                payload_json = json.dumps(e.payload, sort_keys=True)
                computed_hash = self._compute_hash(
                    tenant_id=e.tenant_id,  # type: ignore[arg-type]
                    actor=e.actor,  # type: ignore[arg-type]
                    action=e.action,  # type: ignore[arg-type]
                    payload_json=payload_json,
                    timestamp_iso=e.timestamp.isoformat(),
                    previous_hash=e.previous_hash,  # type: ignore[arg-type]
                )

                if computed_hash != e.event_hash:
                    return False

                expected_previous_hash = e.event_hash

            return True
