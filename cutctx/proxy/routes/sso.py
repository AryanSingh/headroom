# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""SSO config and token-validation endpoints.

High-21 (production-audit-progress-2026-06-20.md): this module
was a stub with no auth. Refactored to a factory that accepts
admin auth + 'sso.read' / 'sso.write' RBAC.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger(__name__)


def create_sso_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the SSO router with auth dependencies applied."""
    router = APIRouter(prefix="/v1/sso", tags=["SSO"])

    read_deps: list[Any] = []
    write_deps: list[Any] = []
    if require_admin_auth is not None:
        read_deps.append(Depends(require_admin_auth))
        write_deps.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        read_deps.append(Depends(require_rbac_permission("sso.read")))
        write_deps.append(Depends(require_rbac_permission("sso.write")))
    if not read_deps:
        logger.warning(
            "create_sso_router built without auth dependencies — "
            "/v1/sso/* will be reachable without auth."
        )

    try:
        from cutctx_ee.sso import SsoConfig, SsoValidator
    except ImportError:
        SsoConfig = None  # type: ignore[assignment, misc]
        SsoValidator = None  # type: ignore[assignment, misc]

    @router.get("/config", dependencies=read_deps)
    async def get_sso_config(request: Request) -> dict[str, Any]:
        if SsoConfig is None:
            return {
                "sso_configured": False,
                "reason": "EE module not installed",
            }
        proxy = getattr(request.app.state, "proxy", None)
        sso_validator = getattr(proxy, "sso_validator", None) if proxy else None
        return {
            "sso_configured": sso_validator is not None,
            "provider": getattr(
                sso_validator, "provider_type", None
            ) if sso_validator is not None else None,
        }

    @router.post("/validate", dependencies=write_deps)
    async def validate_token(request: Request, token: str) -> dict[str, Any]:
        if SsoValidator is None:
            raise HTTPException(
                status_code=501,
                detail="SSO requires cutctx_ee (Enterprise Edition)",
            )
        proxy = getattr(request.app.state, "proxy", None)
        sso_validator = getattr(proxy, "sso_validator", None) if proxy else None
        if sso_validator is None:
            return {"valid": False, "error": "sso_not_configured"}
        try:
            claims = await sso_validator.validate_token(token)
            return {
                "valid": True,
                "subject": getattr(claims, "subject", None),
                "role": getattr(claims, "role", None),
            }
        except Exception as exc:  # noqa: BLE001
            return {"valid": False, "error": str(exc)}

    return router


__all__ = ["create_sso_router"]
