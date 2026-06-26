# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for the EE policy proxy.

Blocker-1: the EE ``/v1/policies/*`` endpoints were previously mounted
without admin auth or RBAC. This factory applies the auth dependencies
from ``server.py`` so policy mutations require the operator role.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)


def create_policy_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the EE policy router with auth dependencies applied."""
    router = APIRouter()

    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        dependencies.append(Depends(require_rbac_permission("policy.write")))
    if not dependencies:
        logger.warning(
            "create_policy_router built without auth dependencies — "
            "/v1/policies/* will be reachable without auth."
        )

    try:
        from cutctx_ee.policy.api import router as policy_inner_router

        router.include_router(policy_inner_router, dependencies=dependencies)
        logger.info(
            "Enterprise Policy API routes loaded (auth_deps=%d).",
            len(dependencies),
        )
    except ImportError:
        logger.debug(
            "Enterprise policy module (cutctx_ee) not found. "
            "Policy routes disabled."
        )

    return router


__all__ = ["create_policy_router"]
