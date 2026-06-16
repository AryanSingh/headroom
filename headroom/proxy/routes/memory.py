"""Team Memory Service routes (EE proxy).

This is a thin Apache-licensed wrapper that proxies to the proprietary
memory service in `headroom_ee`.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter()

def _get_ee_router() -> APIRouter:
    try:
        from headroom_ee.memory_service.api import router as ee_router
        return ee_router
    except ImportError as e:
        logger.error(f"Failed to import headroom_ee.memory_service.api: {e}")
        raise HTTPException(
            status_code=501,
            detail="Team Memory Service is an Enterprise Edition feature."
        )

@router.post("/v1/memory/sync")
async def sync_memory(request: Request) -> Any:
    """Proxy for memory sync."""
    ee = _get_ee_router()
    # Find the corresponding route
    for route in ee.routes:
        if getattr(route, "path", "") == "/v1/memory/sync":
            return await route.endpoint(request=request) # type: ignore
    raise HTTPException(status_code=404, detail="Route not found in EE module")

@router.post("/v1/memory/query")
async def query_memory(request: Request) -> Any:
    """Proxy for memory query."""
    ee = _get_ee_router()
    for route in ee.routes:
        if getattr(route, "path", "") == "/v1/memory/query":
            return await route.endpoint(request=request) # type: ignore
    raise HTTPException(status_code=404, detail="Route not found in EE module")
