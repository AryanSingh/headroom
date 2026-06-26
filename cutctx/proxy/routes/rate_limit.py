# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Rate-limit observability endpoint.

High-21 (production-audit-progress-2026-06-20.md): this module
was a stub with no auth. Refactored to a factory that accepts
admin auth + 'rate_limit.read' RBAC.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Request

logger = logging.getLogger(__name__)


def create_rate_limit_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the rate-limit observability router with auth applied."""
    router = APIRouter(prefix="/v1/rate_limit", tags=["Rate Limit"])
    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        dependencies.append(Depends(require_rbac_permission("rate_limit.read")))
    if not dependencies:
        logger.warning(
            "create_rate_limit_router built without auth dependencies — "
            "/v1/rate_limit/* will be reachable without auth."
        )

    @router.get("/stats", dependencies=dependencies)
    async def get_rate_limit_stats(request: Request) -> dict[str, Any]:
        # Reads the rate-limiter state from the proxy module
        # when one is configured. Returns an empty stats dict
        # when no rate limiter is configured.
        proxy = getattr(request.app.state, "proxy", None)
        rl = getattr(proxy, "rate_limiter", None) if proxy is not None else None
        if rl is None:
            return {"enabled": False, "stats": {}}
        try:
            stats = await rl.stats()
            return {"enabled": True, "stats": stats}
        except Exception as exc:  # noqa: BLE001
            logger.exception("rate_limit stats failed: %s", exc)
            return {"enabled": True, "stats": {}, "error": str(exc)}

    return router


__all__ = ["create_rate_limit_router"]
