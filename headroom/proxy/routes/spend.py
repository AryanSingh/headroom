# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for the EE spend-ledger proxy.

Blocker-1 (production-audit-2026-06-20.md): the EE ``/v1/spend/*`` endpoints
were previously mounted without admin auth or RBAC. The factory accepts
the auth dependencies from ``server.py`` and applies them to every
router-level operation so a request must pass both gates before any
ledger endpoint runs.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends

logger = logging.getLogger(__name__)


def create_spend_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the EE spend-ledger router with auth dependencies applied.

    Both ``require_admin_auth`` and ``require_rbac_permission`` are
    passed in by ``server.py`` so the OSS module does not import the
    proprietary EE auth implementation. If either is ``None``, the
    router is built without that gate (so OSS-only deployments keep
    working) and a warning is logged.
    """
    router = APIRouter()

    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        # The spend ledger requires ``spend.read`` for any state-changing
        # or query endpoint. EE-side handlers may further refine per
        # route, but applying this default keeps every operation gated.
        dependencies.append(Depends(require_rbac_permission("spend.read")))
    if not dependencies:
        logger.warning(
            "create_spend_router built without auth dependencies — "
            "/v1/spend/* will be reachable without auth. "
            "This must be fixed in production deployments."
        )

    try:
        from headroom_ee.ledger.api import router as spend_inner_router

        router.include_router(spend_inner_router, dependencies=dependencies)
        logger.info(
            "Spend ledger API routes loaded (auth_deps=%d).",
            len(dependencies),
        )
    except ImportError:
        logger.debug(
            "Enterprise spend ledger module (headroom_ee) not found. "
            "Spend routes disabled."
        )

    return router


__all__ = ["create_spend_router"]
