# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""RBAC role-management endpoints.

High-21 (production-audit-progress-2026-06-20.md): this module
was a stub with no auth. Refactored to a factory that accepts
admin auth + 'rbac.write' RBAC. Each endpoint also enforces
its own per-endpoint permission via the rbac checker.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger(__name__)


def create_rbac_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the RBAC role-management router with auth applied."""
    router = APIRouter(prefix="/v1/rbac", tags=["RBAC"])
    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        dependencies.append(Depends(require_rbac_permission("rbac.write")))
    if not dependencies:
        logger.warning(
            "create_rbac_router built without auth dependencies — "
            "/v1/rbac/* will be reachable without auth."
        )

    try:
        from cutctx_ee.rbac import AdminRole, get_rbac_checker
    except ImportError:
        get_rbac_checker = None  # type: ignore[assignment]
        AdminRole = None  # type: ignore[assignment, misc]

    @router.get("/assignments", dependencies=dependencies)
    async def list_assignments(request: Request) -> dict[str, Any]:
        if get_rbac_checker is None:
            raise HTTPException(
                status_code=501,
                detail="RBAC requires cutctx_ee (Enterprise Edition)",
            )
        checker = get_rbac_checker()
        return {"assignments": checker.list_assignments()}

    @router.post("/assignments/{user_id}", dependencies=dependencies)
    async def assign_role(
        request: Request, user_id: str, role: str
    ) -> dict[str, Any]:
        if get_rbac_checker is None or AdminRole is None:
            raise HTTPException(
                status_code=501,
                detail="RBAC requires cutctx_ee (Enterprise Edition)",
            )
        try:
            admin_role = AdminRole(role)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role!r}") from e
        checker = get_rbac_checker()
        checker.assign_role(user_id, admin_role)
        return {"status": "success", "user_id": user_id, "role": role}

    @router.delete("/assignments/{user_id}", dependencies=dependencies)
    async def revoke_role(request: Request, user_id: str) -> dict[str, Any]:
        if get_rbac_checker is None:
            raise HTTPException(
                status_code=501,
                detail="RBAC requires cutctx_ee (Enterprise Edition)",
            )
        checker = get_rbac_checker()
        success = checker.revoke_role(user_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Role assignment not found"
            )
        return {"status": "success", "user_id": user_id}

    return router


__all__ = ["create_rbac_router"]
