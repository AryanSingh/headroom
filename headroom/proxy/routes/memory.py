# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for the EE team-memory proxy.

Blocker-1: the EE ``/v1/memory/*`` endpoints were previously mounted
without admin auth or RBAC. The EE module's own auth TODO comments
(``headroom_ee/memory_service/api.py:36-85``) explicitly noted this gap.
This factory applies the auth dependencies from ``server.py`` so
memory sync/query/review require the operator role.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger(__name__)


def _get_ee_router() -> APIRouter:
    try:
        from headroom_ee.memory_service.api import router as ee_router
        return ee_router
    except ImportError as e:
        logger.error(f"Failed to import headroom_ee.memory_service.api: {e}")
        raise HTTPException(
            status_code=501,
            detail="Team Memory Service is an Enterprise Edition feature.",
        )


def create_memory_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the EE team-memory router with auth dependencies applied."""
    router = APIRouter()

    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        dependencies.append(Depends(require_rbac_permission("memory.write")))
    if not dependencies:
        logger.warning(
            "create_memory_router built without auth dependencies — "
            "/v1/memory/* will be reachable without auth."
        )

    @router.post(
        "/v1/memory/sync",
        dependencies=dependencies,
    )
    async def sync_memory(request: Request) -> Any:
        """Proxy for memory sync (authenticated)."""
        ee = _get_ee_router()
        for route in ee.routes:
            if getattr(route, "path", "") == "/v1/memory/sync":
                return await route.endpoint(request=request)  # type: ignore
        raise HTTPException(
            status_code=404, detail="Route not found in EE module"
        )

    @router.post(
        "/v1/memory/query",
        dependencies=dependencies,
    )
    async def query_memory(request: Request) -> Any:
        """Proxy for memory query (authenticated)."""
        ee = _get_ee_router()
        for route in ee.routes:
            if getattr(route, "path", "") == "/v1/memory/query":
                return await route.endpoint(request=request)  # type: ignore
        raise HTTPException(
            status_code=404, detail="Route not found in EE module"
        )

    return router


__all__ = ["create_memory_router"]
