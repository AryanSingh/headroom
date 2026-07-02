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
        permission = "memory.read" if request.method in {"GET", "HEAD", "OPTIONS"} else "memory.write"
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


__all__ = ["create_memory_router"]
