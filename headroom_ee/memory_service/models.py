# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class MemoryRecord(Base):
    """Server-side memory storage model."""

    __tablename__ = "memory_records"

    # Server tracking
    id = Column(String, primary_key=True)
    updated_at_ts = Column(Float, nullable=False, index=True)

    # Content
    content = Column(String, nullable=False)

    # Tenant Indices
    org_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, nullable=True, index=True)
    project_id = Column(String, nullable=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)
    agent_id = Column(String, nullable=True, index=True)
    turn_id = Column(String, nullable=True, index=True)

    # Temporal
    created_at = Column(DateTime, nullable=False)
    valid_from = Column(DateTime, nullable=False)
    valid_until = Column(DateTime, nullable=True)

    # Classification & Metrics
    importance = Column(Float, nullable=False, default=0.5)
    value_score = Column(Float, nullable=False, default=0.5)
    access_count = Column(Integer, nullable=False, default=0)
    last_accessed = Column(DateTime, nullable=True)
    review_state = Column(String, nullable=False, default="PROPOSED") # PROPOSED, APPROVED, DEPRECATED

    # Lineage (for supersession)
    supersedes = Column(String, nullable=True)
    superseded_by = Column(String, nullable=True)
    promoted_from = Column(String, nullable=True)

    # JSON Fields
    promotion_chain = Column(JSON, nullable=False, default=list)
    provenance = Column(JSON, nullable=True)
    entity_refs = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=False, default=dict)

    # Optional Embedding vector representation for future PG-vector compatibility
    # Stored as JSON array for now as we're using SQLite primarily in testing
    embedding = Column(JSON, nullable=True)
