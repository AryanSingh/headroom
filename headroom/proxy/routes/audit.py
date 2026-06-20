# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for the EE audit-log proxy.

Blocker-1: the EE ``/v1/audit/*`` endpoints were previously mounted
without admin auth or RBAC. This factory applies the auth dependencies
from ``server.py`` so audit-log writes and reads require the
audit role.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)


def create_audit_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the EE audit router with auth dependencies applied."""
    router = APIRouter()

    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        dependencies.append(Depends(require_rbac_permission("audit.read")))
    if not dependencies:
        logger.warning(
            "create_audit_router built without auth dependencies — "
            "/v1/audit/* will be reachable without auth."
        )

    try:
        from headroom_ee.audit.api import router as audit_inner_router

        router.include_router(audit_inner_router, dependencies=dependencies)
        logger.info(
            "Enterprise Audit API routes loaded (auth_deps=%d).",
            len(dependencies),
        )
    except ImportError:
        logger.debug(
            "Enterprise audit module (headroom_ee) not found. "
            "Audit routes disabled."
        )

    return router


__all__ = ["create_audit_router"]
