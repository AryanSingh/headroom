# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Secrets management endpoints.

High-21 (production-audit-progress-2026-06-20.md): this module
was a stub. Refactored to a factory that accepts admin auth
+ 'secrets.read'/'secrets.write' RBAC so the endpoints are not
exposed to unauthenticated callers.

Audit-Deep-2026-06-21 Blocker 3b: the previous implementation
returned ``[]`` for ``list_secrets()`` and "success" for
``create_secret()`` without actually storing anything. The
endpoints now read/write an encrypted SQLite-backed
``SecretsStore`` (see ``cutctx.security.secrets_store``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)


def create_secrets_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
    *,
    secrets_store: Any | None = None,
) -> APIRouter:
    """Build the secrets router with auth dependencies applied.

    Parameters
    ----------
    require_admin_auth, require_rbac_permission
        Auth dependency factories; required for production wiring.
    secrets_store
        An optional pre-built ``SecretsStore``. If None, the
        router will lazily build one on first use (using
        ``CUTCTX_SECRETS_KEY`` / ``CUTCTX_LICENSE_HMAC_SECRET``).
    """
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

    # Lazily-initialised store. The store opens a SQLite file and
    # may raise at first use; we defer the import so a route file
    # can be imported even when the optional dep is missing.
    _store_ref: dict[str, Any] = {"store": secrets_store}

    def _get_store() -> Any:
        if _store_ref["store"] is None:
            from cutctx.security.secrets_store import SecretsStore

            _store_ref["store"] = SecretsStore(strict=True)
        return _store_ref["store"]

    @router.get("/", dependencies=read_deps)
    async def list_secrets(request: Request) -> list[dict[str, Any]]:
        """List secret names + metadata. Never returns values."""
        return _get_store().list()

    @router.post("/", dependencies=write_deps)
    async def create_secret(
        request: Request,
        name: str = Body(...),
        value: str = Body(...),
        description: str = Body(""),
    ) -> dict[str, Any]:
        if not name or not value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="name and value are required",
            )
        secret = _get_store().set(name, value, description=description)
        return {
            "status": "success",
            "name": secret.name,
            "created_at_ts": secret.created_at_ts,
            "updated_at_ts": secret.updated_at_ts,
        }

    @router.put("/{name}", dependencies=write_deps)
    async def update_secret(
        request: Request,
        name: str,
        value: str = Body(...),
        description: str = Body(""),
    ) -> dict[str, Any]:
        if not value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="value is required",
            )
        store = _get_store()
        if store.get(name) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"secret {name!r} not found",
            )
        secret = store.set(name, value, description=description)
        return {
            "status": "success",
            "name": secret.name,
            "updated_at_ts": secret.updated_at_ts,
        }

    @router.delete("/{name}", dependencies=write_deps)
    async def delete_secret(request: Request, name: str) -> dict[str, Any]:
        store = _get_store()
        if not store.delete(name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"secret {name!r} not found",
            )
        return {"status": "success", "name": name}

    return router


__all__ = ["create_secrets_router"]
