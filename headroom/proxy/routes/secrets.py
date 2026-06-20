# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Secret-management endpoints.

High-21 (production-audit-progress-2026-06-20.md): this module
was a stub with no auth. Refactored to a factory that accepts
admin auth + 'secrets.read' / 'secrets.write' RBAC.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, Request

logger = logging.getLogger(__name__)


def create_secrets_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the secrets router with auth dependencies applied."""
    router = APIRouter(prefix="/v1/secrets", tags=["Secrets"])

    read_deps: list[Any] = []
    write_deps: list[Any] = []
    if require_admin_auth is not None:
        read_deps.append(Depends(require_admin_auth))
        write_deps.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        read_deps.append(Depends(require_rbac_permission("secrets.read")))
        write_deps.append(Depends(require_rbac_permission("secrets.write")))
    if not read_deps:
        logger.warning(
            "create_secrets_router built without auth dependencies — "
            "/v1/secrets/* will be reachable without auth."
        )

    @router.get("/", dependencies=read_deps)
    async def list_secrets(request: Request) -> list[dict[str, Any]]:
        # Placeholder for secret management. The actual
        # integration would query a vault backend; the
        # response shape is documented for the EE tier.
        return []

    @router.post("/", dependencies=write_deps)
    async def create_secret(
        request: Request, name: str, value: str
    ) -> dict[str, Any]:
        if not name or not value:
            return {"status": "error", "error": "name and value required"}
        return {"status": "success", "name": name}

    return router


__all__ = ["create_secrets_router"]
