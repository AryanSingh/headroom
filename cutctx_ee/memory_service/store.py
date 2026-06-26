# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

import time
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cutctx_ee.memory_service.models import Base, MemoryRecord


class MemoryStore:
    """Proprietary team memory store with sync capabilities."""

    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def sync(
        self,
        org_id: str,
        workspace_id: str | None,
        since_watermark: float,
        local_deltas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Merge local deltas with server. Returns new server deltas and a new watermark.
        """
        with self.SessionLocal() as session:
            now = time.time()

            # 1. Fetch server deltas (items updated since the client's watermark)
            query = session.query(MemoryRecord).filter(
                MemoryRecord.org_id == org_id, MemoryRecord.updated_at_ts > since_watermark
            )
            if workspace_id:
                query = query.filter(MemoryRecord.workspace_id == workspace_id)

            server_records = query.all()
            server_deltas = [self._record_to_dict(r) for r in server_records]

            # 2. Process local deltas (upsert)
            for delta in local_deltas:
                existing = (
                    session.query(MemoryRecord).filter_by(id=delta["id"], org_id=org_id).first()
                )
                if existing:
                    # Update fields that are mutable or append-only
                    self._update_record_from_dict(existing, delta)
                    existing.updated_at_ts = now
                else:
                    new_rec = self._dict_to_record(delta, org_id, workspace_id, now)
                    session.add(new_rec)

            session.commit()
            return {"server_deltas": server_deltas, "new_watermark": now}

    def update_review_state(self, org_id: str, memory_id: str, new_state: str) -> None:
        """Update the review state of a memory record."""
        with self.SessionLocal() as session:
            record = session.query(MemoryRecord).filter_by(id=memory_id, org_id=org_id).first()
            if not record:
                raise ValueError(f"Memory {memory_id} not found in org {org_id}")
            record.review_state = new_state
            record.updated_at_ts = time.time()
            session.commit()

    def _dict_to_record(
        self, data: dict[str, Any], org_id: str, workspace_id: str | None, updated_at: float
    ) -> MemoryRecord:
        return MemoryRecord(
            id=data["id"],
            updated_at_ts=updated_at,
            content=data.get("content", ""),
            org_id=org_id,
            workspace_id=workspace_id or data.get("workspace_id"),
            project_id=data.get("project_id"),
            user_id=data.get("user_id", ""),
            session_id=data.get("session_id"),
            agent_id=data.get("agent_id"),
            turn_id=data.get("turn_id"),
            created_at=self._parse_dt(data.get("created_at")),
            valid_from=self._parse_dt(data.get("valid_from")),
            valid_until=self._parse_dt(data.get("valid_until")),
            importance=data.get("importance", 0.5),
            value_score=data.get("value_score", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=self._parse_dt(data.get("last_accessed")),
            supersedes=data.get("supersedes"),
            superseded_by=data.get("superseded_by"),
            promoted_from=data.get("promoted_from"),
            promotion_chain=data.get("promotion_chain", []),
            provenance=data.get("provenance"),
            entity_refs=data.get("entity_refs", []),
            metadata_json=data.get("metadata", {}),
            embedding=data.get("embedding"),
        )

    def _update_record_from_dict(self, record: MemoryRecord, data: dict[str, Any]) -> None:
        # We only update fields that can legitimately change without a new ID.
        # Core identity and temporal creation fields stay immutable.
        record.valid_until = self._parse_dt(data.get("valid_until")) or record.valid_until
        record.superseded_by = data.get("superseded_by") or record.superseded_by
        record.access_count = max(record.access_count, data.get("access_count", 0))

        last_acc = self._parse_dt(data.get("last_accessed"))
        if last_acc:
            if not record.last_accessed or last_acc > record.last_accessed:
                record.last_accessed = last_acc

        record.importance = data.get("importance", record.importance)
        record.value_score = data.get("value_score", record.value_score)

        # Merge metadata
        if data.get("metadata"):
            merged = dict(record.metadata_json)
            merged.update(data["metadata"])
            record.metadata_json = merged

    def _record_to_dict(self, record: MemoryRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "content": record.content,
            "org_id": record.org_id,
            "workspace_id": record.workspace_id,
            "project_id": record.project_id,
            "user_id": record.user_id,
            "session_id": record.session_id,
            "agent_id": record.agent_id,
            "turn_id": record.turn_id,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "valid_from": record.valid_from.isoformat() if record.valid_from else None,
            "valid_until": record.valid_until.isoformat() if record.valid_until else None,
            "importance": record.importance,
            "value_score": record.value_score,
            "access_count": record.access_count,
            "last_accessed": record.last_accessed.isoformat() if record.last_accessed else None,
            "supersedes": record.supersedes,
            "superseded_by": record.superseded_by,
            "promoted_from": record.promoted_from,
            "promotion_chain": record.promotion_chain,
            "provenance": record.provenance,
            "entity_refs": record.entity_refs,
            "metadata": record.metadata_json,
            "embedding": record.embedding,
        }

    @staticmethod
    def _parse_dt(val: str | None) -> datetime | None:
        if not val:
            return None
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return None
