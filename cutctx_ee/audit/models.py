# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AuditEvent(Base):
    """A tamper-evident audit log event."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Who did what
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)

    # Event data
    payload = Column(JSON, nullable=False)

    # Cryptographic chaining
    previous_hash = Column(String, nullable=True)  # Null for the first event in a chain
    event_hash = Column(String, nullable=False, unique=True)
