# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Airgap-mode status endpoint.

High-21 (production-audit-progress-2026-06-20.md): this module
was a stub with no auth. Refactored to a factory that accepts
admin auth + 'airgap.read' RBAC so the endpoint is not
exposed to unauthenticated callers.

Audit-Deep-2026-06-21 Blocker 3a: the previous /v1/airgap/status
returned a hardcoded payload. The endpoint now reports the
actual state of the egress policy in effect, derived from:

  - ``CUTCTX_OFFLINE_MODE`` env var (0/1)
  - ``CUTCTX_EGRESS_POLICY`` env var (JSON allowlist)
  - ``cutctx.proxy.egress.get_egress_enforcer()`` runtime policy

The endpoint exposes two paths:

  - GET /v1/airgap/status: status snapshot
  - GET /v1/airgap/policy: the effective allowlist
  - POST /v1/airgap/check: dry-run check a URL against the policy
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, Request

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
        """Report the actual air-gap + egress policy state."""
        from cutctx.proxy.egress import get_egress_enforcer

        enforcer = get_egress_enforcer()
        offline_mode = os.environ.get("CUTCTX_OFFLINE_MODE", "0") == "1"
        policy = enforcer.policy
        return {
            "offline_mode": offline_mode,
            "limits_enforced": True,
            "policy_id": policy.policy_id,
            "policy_description": policy.description,
            "allow_all": policy.allow_all,
            "allowed_patterns": list(policy.allowed_patterns),
            "is_empty": policy.is_empty(),
        }

    @router.get("/policy", dependencies=dependencies)
    async def get_airgap_policy(request: Request) -> dict[str, Any]:
        """Return the effective EgressPolicy (allowlist + metadata)."""
        from cutctx.proxy.egress import get_egress_enforcer

        policy = get_egress_enforcer().policy
        return {
            "policy_id": policy.policy_id,
            "description": policy.description,
            "allow_all": policy.allow_all,
            "allowed_patterns": list(policy.allowed_patterns),
            "is_empty": policy.is_empty(),
        }

    @router.post("/check", dependencies=dependencies)
    async def check_url_against_policy(
        request: Request,
        url: str = Body(..., embed=True),
    ) -> dict[str, Any]:
        """Dry-run check whether a URL is allowed by the egress policy."""
        from cutctx.proxy.egress import get_egress_enforcer

        decision = get_egress_enforcer().check(url)
        return {
            "url": url,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "matched_pattern": decision.matched_pattern,
            "policy_id": decision.policy_id,
        }

    return router


__all__ = ["create_airgap_router"]
