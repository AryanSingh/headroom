# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from headroom_ee.audit.store import AuditStore

# Global store reference
_store: AuditStore | None = None


def get_store() -> AuditStore:
    if _store is None:
        raise HTTPException(status_code=500, detail="Audit store not initialized")
    return _store


router = APIRouter(prefix="/v1/audit", tags=["Audit"])


class AuditEventCreate(BaseModel):
    tenant_id: str
    actor: str
    action: str
    payload: dict[str, Any]


@router.post("/events")
async def append_event(
    event: AuditEventCreate,
    store: AuditStore = Depends(get_store),
) -> dict[str, Any]:
    """Append a new event to the audit log."""
    return store.append_event(
        tenant_id=event.tenant_id,
        actor=event.actor,
        action=event.action,
        payload=event.payload,
    )


@router.get("/events/{tenant_id}")
async def get_events(
    tenant_id: str,
    limit: int = 100,
    store: AuditStore = Depends(get_store),
) -> list[dict[str, Any]]:
    """Get recent audit events for a tenant."""
    return store.get_events(tenant_id=tenant_id, limit=limit)


@router.get("/verify/{tenant_id}")
async def verify_chain(
    tenant_id: str,
    store: AuditStore = Depends(get_store),
) -> dict[str, bool]:
    """Verify the cryptographic integrity of the audit log."""
    is_valid = store.verify_chain(tenant_id)
    return {"valid": is_valid}
