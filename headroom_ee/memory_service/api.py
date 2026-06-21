# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from headroom_ee.memory_service.store import MemoryStore

_store: MemoryStore | None = None


def get_store() -> MemoryStore:
    if _store is None:
        raise HTTPException(status_code=500, detail="Memory store not initialized")
    return _store


router = APIRouter(prefix="/v1/memory", tags=["Team Memory"])


class SyncRequest(BaseModel):
    org_id: str
    workspace_id: str | None = None
    since_watermark: float
    local_deltas: list[dict[str, Any]]


class SyncResponse(BaseModel):
    server_deltas: list[dict[str, Any]]
    new_watermark: float


@router.post("/sync", response_model=SyncResponse)
async def sync_memory(req: SyncRequest, store: MemoryStore = Depends(get_store)) -> SyncResponse:
    """Synchronize local client memories with the team server."""
    try:
        result = store.sync(
            org_id=req.org_id,
            workspace_id=req.workspace_id,
            since_watermark=req.since_watermark,
            local_deltas=req.local_deltas,
        )
        return SyncResponse(
            server_deltas=result["server_deltas"], new_watermark=result["new_watermark"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class ReviewRequest(BaseModel):
    org_id: str
    memory_id: str
    action: str  # "APPROVE", "DEPRECATE", "PROPOSE"


@router.post("/review")
async def review_memory(
    request: Request,
    req: ReviewRequest,
    store: MemoryStore = Depends(get_store),
) -> dict[str, Any]:
    """Review a memory candidate (curator only).

    Audit-Deep-2026-06-21 Blocker 3c: the previous code had
    explicit TODOs admitting no RBAC and no audit emission. The
    endpoint now:

      1. Resolves the audit actor via the shared helper
         (sso: > key: > admin hierarchy).
      2. Emits a ``memory.<action>`` audit event (APPROVE /
         DEPRECATE / PROPOSE) to the audit store when one is
         configured.
      3. RBAC enforcement still lives at the route mount layer
         (see ``headroom/proxy/routes/memory.py`` which gates
         this entire router with ``memory.write`` permission).
         The audit is a defense-in-depth: even if a future call
         path bypasses the auth gate, the audit log records who
         acted.
    """
    from headroom.proxy.routes.admin import _resolve_audit_actor

    actor = _resolve_audit_actor(request)
    try:
        store.update_review_state(
            org_id=req.org_id,
            memory_id=req.memory_id,
            new_state=req.action.upper()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Audit emission (best-effort; never let an audit failure
    # roll back the review).
    try:
        from headroom_ee.audit.api import get_store as get_audit_store

        audit_store = get_audit_store()
        audit_store.append_event(
            tenant_id=req.org_id,
            actor=actor,
            action=f"memory.{req.action.lower()}",
            payload={"memory_id": req.memory_id},
        )
    except Exception:
        # Audit store not configured (OSS-only deployment) or
        # transient failure. The review itself succeeded.
        pass

    return {
        "status": "success",
        "memory_id": req.memory_id,
        "state": req.action.upper(),
        "actor": actor,
    }
