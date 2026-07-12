# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for license management endpoints.

Blocker-1: ``/v1/license/*`` and ``/activate``, ``/checkout-seat``,
``/start-trial``, ``/check-trial`` were previously reachable without
admin auth. The factory applies admin auth + the ``license.write``
RBAC permission.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def create_license_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the license-management router with auth dependencies applied."""
    router = APIRouter(prefix="/v1/license", tags=["License"])

    dependencies: list[Any] = []
    if require_admin_auth is not None:
        dependencies.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        dependencies.append(Depends(require_rbac_permission("license.write")))
    if not dependencies:
        logger.warning(
            "create_license_router built without auth dependencies — "
            "/v1/license/* will be reachable without auth."
        )

    try:
        from cutctx_ee.billing.license_db import get_license_db
    except ImportError:

        def get_license_db() -> Any:
            raise HTTPException(
                status_code=501,
                detail={
                    "message": "Enterprise billing module not installed",
                    "remediation": "License management requires cutctx-ee (enterprise edition). Install via: pip install cutctx-ai[ee] or contact sales@cutctx.io"
                }
            )

    class ActivateRequest(BaseModel):
        license_key: str
        instance_id: str

    @router.post("/activate", dependencies=dependencies)
    async def activate_license(req: ActivateRequest) -> dict:
        db = get_license_db()
        if db.is_revoked(req.license_key):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "License revoked",
                    "remediation": "Your license key has been revoked. Contact support@cutctx.io for assistance."
                }
            )
        record = db.get(req.license_key)
        if not record or not record.active:
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "Invalid license",
                    "remediation": "The license key is invalid or inactive. Verify the key is correct and hasn't expired. Contact sales@cutctx.io if you need a new license."
                }
            )
        success = db.activate_instance(req.license_key, req.instance_id)
        if not success:
            return {"status": "already_activated"}
        return {"status": "activated"}

    @router.get("/crl", dependencies=dependencies)
    async def get_crl() -> dict:
        db = get_license_db()
        crl = db.get_crl()
        return {"revoked": crl}

    class CheckoutSeatRequest(BaseModel):
        license_key: str
        user_id: str
        lease_duration: float = 3600.0

    @router.post("/checkout-seat", dependencies=dependencies)
    async def checkout_seat(req: CheckoutSeatRequest) -> dict:
        db = get_license_db()
        if db.is_revoked(req.license_key):
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "License revoked",
                    "remediation": "Your license key has been revoked. Contact support@cutctx.io for assistance."
                }
            )
        success = db.checkout_seat(req.license_key, req.user_id, req.lease_duration)
        if not success:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "No seats available",
                    "remediation": "Your license has no available seats. Upgrade your plan at https://cutctx.io/pricing or contact sales@cutctx.io"
                }
            )
        return {"status": "seat_leased"}

    class StartTrialRequest(BaseModel):
        trial_token: str
        customer_email: str
        duration: float = 14 * 86400.0

    @router.post("/start-trial", dependencies=dependencies)
    async def start_trial(req: StartTrialRequest) -> dict:
        db = get_license_db()
        success = db.start_trial(req.trial_token, req.customer_email, req.duration)
        if not success:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Trial already started",
                    "remediation": "This trial token has already been used. Issue a new token or contact sales@cutctx.io",
                },
            )
        return {"status": "trial_started"}

    class CheckTrialRequest(BaseModel):
        trial_token: str

    @router.post("/check-trial", dependencies=dependencies)
    async def check_trial(req: CheckTrialRequest) -> dict:
        db = get_license_db()
        active = db.is_trial_active(req.trial_token)
        return {"active": active}

    return router


__all__ = ["create_license_router"]
