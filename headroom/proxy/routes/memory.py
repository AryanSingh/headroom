# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for the EE team-memory proxy.

Blocker-1: the EE ``/v1/memory/*`` endpoints were previously mounted
without admin auth or RBAC. The EE module's own auth TODO comments
(``headroom_ee/memory_service/api.py:36-85``) explicitly noted this gap.
This factory applies the auth dependencies from ``server.py`` so
memory sync and review require the operator role.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


def _get_ee_router() -> APIRouter:
    try:
        from headroom_ee.memory_service.api import router as ee_router
        return ee_router
    except ImportError as e:
        logger.error(f"Failed to import headroom_ee.memory_service.api: {e}")
        raise ImportError(
            "Team Memory Service is an Enterprise Edition feature. "
            "Install the headroom_ee package to enable it."
        ) from e


def _build_stub_router(
    dependencies: list[Any],
) -> APIRouter:
    """Build a stub router that returns 501 for every request under
    ``/v1/memory/{path:path}``.

    This is returned when the EE module is not installed so the
    application can start without crashing.  The 501 is issued at
    request time instead of at import/creation time.
    """
    router = APIRouter()

    @router.api_route(
        "/v1/memory/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        dependencies=dependencies,
    )
    async def _memory_stub() -> None:
        raise HTTPException(
            status_code=501,
            detail="Team Memory Service is an Enterprise Edition feature.",
        )

    logger.info(
        "Enterprise memory module not available; mounted stub 501 router."
    )
    return router


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

    try:
        ee_router = _get_ee_router()
        router.include_router(ee_router, dependencies=dependencies)
    except ImportError:
        stub = _build_stub_router(dependencies)
        router.include_router(stub)

    return router


__all__ = ["create_memory_router"]
