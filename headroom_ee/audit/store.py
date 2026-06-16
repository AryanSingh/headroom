import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, desc
from sqlalchemy.orm import sessionmaker

from headroom_ee.audit.models import AuditEvent, Base


class AuditStore:
    """Tamper-evident append-only audit log store."""

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.secret_key = os.environ.get("HEADROOM_AUDIT_SECRET_KEY", "dev-secret-key").encode()

    def _compute_hash(
        self,
        tenant_id: str,
        actor: str,
        action: str,
        payload_json: str,
        timestamp_iso: str,
        previous_hash: str | None,
    ) -> str:
        """Compute HMAC SHA-256 hash for the event."""
        # A simple hash chain: H(secret + previous_hash + fields)
        hasher = hashlib.sha256()
        hasher.update(self.secret_key)
        if previous_hash:
            hasher.update(previous_hash.encode())
        hasher.update(tenant_id.encode())
        hasher.update(actor.encode())
        hasher.update(action.encode())
        hasher.update(payload_json.encode())
        hasher.update(timestamp_iso.encode())
        return hasher.hexdigest()

    def append_event(
        self, tenant_id: str, actor: str, action: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
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

    def get_events(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
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
