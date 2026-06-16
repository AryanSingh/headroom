# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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
