# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Headroom Labs.
"""FastAPI router for provider failover management endpoints.

Endpoints
---------
GET  /v1/providers
    List all configured providers and their health status.

POST /v1/providers/{name}/disable
    Manually mark a provider as unhealthy (admin).

POST /v1/providers/{name}/enable
    Re-enable a previously disabled provider (admin).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger("headroom.proxy.routes.failover")

# The router is created without an injected FailoverRouter reference;
# the server wires it up by calling ``create_failover_router(failover_router=…)``.


def create_failover_router(failover_router: Any) -> APIRouter:
    """Return a populated ``APIRouter`` with the failover management endpoints.

    Parameters
    ----------
    failover_router:
        A :class:`~headroom.proxy.routing.FailoverRouter` instance.  Typed as
        ``Any`` here to avoid a hard import dependency in environments where the
        routing package is not installed.
    """
    router = APIRouter(tags=["providers"])

    # ── GET /v1/providers ─────────────────────────────────────────────────

    @router.get("/v1/providers", summary="List provider health status")
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

    # ── POST /v1/providers/{name}/disable ─────────────────────────────────

    @router.post("/v1/providers/{name}/disable", summary="Manually disable a provider")
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

    # ── POST /v1/providers/{name}/enable ──────────────────────────────────

    @router.post("/v1/providers/{name}/enable", summary="Manually enable a provider")
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
