# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for provider failover management endpoints.

Blocker-1: ``/v1/providers/{name}/disable|enable`` are admin operations
(docstring explicitly says "admin") but were previously reachable
without auth. The factory accepts the auth dependencies and applies
them to the destructive endpoints.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger("cutctx.proxy.routes.failover")


def create_failover_router(
    failover_router: Any,
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Return a populated ``APIRouter`` with the failover management endpoints.

    The destructive operations ``disable_provider`` and ``enable_provider``
    require admin auth + the ``providers.write`` RBAC permission. The
    read endpoint ``list_providers`` requires admin auth + ``providers.read``
    (so unauthenticated callers cannot enumerate which providers exist).
    """
    router = APIRouter(tags=["providers"])

    # Read endpoint: requires providers.read.
    read_deps: list[Any] = []
    if require_admin_auth is not None:
        read_deps.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        read_deps.append(Depends(require_rbac_permission("providers.read")))

    @router.get(
        "/v1/providers",
        summary="List provider health status",
        dependencies=read_deps,
    )
    async def list_providers() -> JSONResponse:
        """Return health status of all configured upstream providers."""
        try:
            status = failover_router.get_status()
        except Exception as exc:
            logger.exception("event=get_status_error error=%r", exc)
            raise HTTPException(
                status_code=500, detail="Failed to retrieve provider status"
            ) from exc
        return JSONResponse(content={"providers": status})

    # Destructive endpoints: require providers.write.
    write_deps: list[Any] = []
    if require_admin_auth is not None:
        write_deps.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        write_deps.append(Depends(require_rbac_permission("providers.write")))

    @router.post(
        "/v1/providers/{name}/disable",
        summary="Manually disable a provider",
        dependencies=write_deps,
    )
    async def disable_provider(name: str) -> JSONResponse:
        """Mark *name* as unhealthy so the failover router skips it."""
        try:
            found = failover_router.disable(name)
        except Exception as exc:
            logger.exception("event=disable_error provider=%s error=%r", name, exc)
            raise HTTPException(status_code=500, detail="Failed to disable provider") from exc
        if not found:
            raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
        logger.info("event=provider_disabled provider=%s via=admin_api", name)
        return JSONResponse(content={"provider": name, "healthy": False})

    @router.post(
        "/v1/providers/{name}/enable",
        summary="Manually enable a provider",
        dependencies=write_deps,
    )
    async def enable_provider(name: str) -> JSONResponse:
        """Re-enable a previously disabled provider."""
        try:
            found = failover_router.enable(name)
        except Exception as exc:
            logger.exception("event=enable_error provider=%s error=%r", name, exc)
            raise HTTPException(status_code=500, detail="Failed to enable provider") from exc
        if not found:
            raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
        logger.info("event=provider_enabled provider=%s via=admin_api", name)
        return JSONResponse(content={"provider": name, "healthy": True})

    return router


__all__ = ["create_failover_router"]
