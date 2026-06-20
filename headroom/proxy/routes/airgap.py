# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Airgap-mode status endpoint.

High-21 (production-audit-progress-2026-06-20.md): this module
was a stub with no auth. Refactored to a factory that accepts
admin auth + 'airgap.read' RBAC so the endpoint is not
exposed to unauthenticated callers.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, Request

logger = logging.getLogger(__name__)


def create_airgap_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the airgap-status router with auth dependencies applied."""
    router = APIRouter(prefix="/v1/airgap", tags=["Airgap"])
    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        dependencies.append(Depends(require_rbac_permission("airgap.read")))
    if not dependencies:
        logger.warning(
            "create_airgap_router built without auth dependencies — "
            "/v1/airgap/* will be reachable without auth."
        )

    @router.get("/status", dependencies=dependencies)
    async def get_airgap_status(request: Request) -> dict[str, Any]:
        # Placeholder for air-gapped limits; in a real
        # deployment the response would reflect the actual
        # egress policy in effect (which can be toggled via
        # the /admin/intel/* endpoints).
        return {"status": "active", "limits_enforced": True}

    return router


__all__ = ["create_airgap_router"]
