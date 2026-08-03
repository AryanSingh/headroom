# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for the EE team-memory proxy surface.

This module keeps the OSS proxy bootable when the enterprise memory package is
absent, while still enforcing admin auth and RBAC when the surface is mounted.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

logger = logging.getLogger(__name__)

# Claim names that carry the tenant a federated principal belongs to.
_ORG_CLAIM_NAMES = ("org_id", "organization_id", "tenant_id", "tid")

_TRUTHY = {"1", "true", "yes", "on"}


def resolve_principal_org(request: Request) -> str | None:
    """Resolve the org the authenticated principal is bound to.

    Audit C4: ``/v1/memory/query`` took its tenant scope from a
    caller-supplied ``org_id`` query parameter, so omitting the parameter
    returned every tenant's rows and passing another tenant's id returned
    theirs. Tenant scope must be derived from the principal, never from the
    request. Only server-set state is trusted here:

      1. ``request.state.cutctx_org_id`` — set by tenant-aware auth layers.
      2. The SSO claim set validated in ``server.py``
         (``request.state.cutctx_sso_claims``); the first of
         ``org_id`` / ``organization_id`` / ``tenant_id`` / ``tid`` wins.

    Returns ``None`` when the principal carries no tenant binding (e.g. the
    root admin key). Callers must read that as "no implicit scope" — never
    as "every tenant".
    """
    state_org = getattr(request.state, "cutctx_org_id", None)
    if state_org:
        return str(state_org)

    claims = getattr(request.state, "cutctx_sso_claims", None)
    raw_claims = getattr(claims, "raw_claims", None)
    if isinstance(raw_claims, dict):
        for name in _ORG_CLAIM_NAMES:
            value = raw_claims.get(name)
            if value:
                return str(value)
    return None


def required_memory_permission(request: Request) -> str:
    """Pick the RBAC permission a memory request needs.

    Safe reads stay on ``memory.read``. A read that names a tenant other than
    the principal's own — or asks for every tenant via ``all_orgs`` — is a
    cross-tenant read and needs the distinct ``memory.read.cross_org``
    permission. That permission is deliberately absent from the EE
    ``PERMISSION_MAP``, so it falls through to the ADMIN default; cross-org
    reads are therefore explicitly authorised rather than being what happens
    when a caller omits a parameter.
    """
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        return "memory.write"

    params = request.query_params
    if str(params.get("all_orgs", "")).strip().lower() in _TRUTHY:
        return "memory.read.cross_org"
    requested_org = str(params.get("org_id", "")).strip()
    if requested_org and requested_org != resolve_principal_org(request):
        return "memory.read.cross_org"
    return "memory.read"


def _get_ee_router() -> APIRouter:
    try:
        from cutctx_ee.memory_service.api import router as ee_router

        return ee_router
    except ImportError as exc:
        logger.error("Failed to import cutctx_ee.memory_service.api: %s", exc)
        raise ImportError(
            "Team Memory Service is an Enterprise Edition feature. "
            "Install the cutctx_ee package to enable it."
        ) from exc


def _build_stub_router(dependencies: list[Any]) -> APIRouter:
    """Build a router that returns 501 for all memory requests."""
    router = APIRouter()

    @router.api_route(
        "/v1/memory/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        dependencies=dependencies,
    )
    async def _memory_stub() -> None:
        raise HTTPException(
            status_code=501,
            detail="Team Memory Service is an Enterprise Edition feature.",
        )

    logger.info("Enterprise memory module not available; mounted stub 501 router.")
    return router


def _build_memory_permission_dependency(
    require_rbac_permission: Callable[[str], Any] | None,
) -> Callable[[Request], Any] | None:
    """Return a dependency that selects read vs write memory RBAC at runtime."""
    if require_rbac_permission is None:
        return None

    def _invoke_dependency(dependency: Any, request: Request) -> Any:
        if not callable(dependency):
            return dependency
        try:
            parameters = tuple(inspect.signature(dependency).parameters.values())
        except (TypeError, ValueError):
            return dependency(request)
        accepts_request = any(
            parameter.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.KEYWORD_ONLY,
                inspect.Parameter.VAR_KEYWORD,
            )
            for parameter in parameters
        )
        return dependency(request) if accepts_request else dependency()

    async def _check(request: Request) -> None:
        permission = required_memory_permission(request)
        dependency = require_rbac_permission(permission)
        result = _invoke_dependency(dependency, request)
        if inspect.isawaitable(result):
            await result

    return _check


def create_memory_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[[str], Any] | None = None,
) -> APIRouter:
    """Build the team-memory router with auth dependencies applied."""
    router = APIRouter()
    dependencies: list[Any] = []

    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))

    permission_dependency = _build_memory_permission_dependency(require_rbac_permission)
    if permission_dependency is not None:
        dependencies.append(Depends(permission_dependency))

    if not dependencies:
        logger.warning(
            "create_memory_router built without auth dependencies — "
            "/v1/memory/* will be reachable without auth."
        )

    try:
        ee_router = _get_ee_router()
        router.include_router(ee_router, dependencies=dependencies)
    except ImportError:
        stub = _build_stub_router(dependencies)
        router.include_router(stub)

    return router


__all__ = ["create_memory_router", "required_memory_permission", "resolve_principal_org"]
