# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for license validation + Stripe webhook.

Blocker-1: the ``/v1/license/validate|activate|checkout-seat|start-trial|
check-trial|crl`` and ``/webhooks/stripe`` routes were previously
unauthenticated. License endpoints now require admin auth + the
``license.write`` RBAC permission. The Stripe webhook is
authenticated via ``STRIPE_WEBHOOK_SECRET`` (HMAC signature check),
not via the admin API key, so the admin auth dependency is NOT
applied to it.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def create_license_validation_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the license-validation router with auth dependencies applied
    to admin-facing endpoints. The Stripe webhook uses its own
    signature verification and is NOT gated by admin auth.
    """
    router = APIRouter()

    # Admin-gated dependencies for license-management endpoints.
    admin_deps: list[Any] = []
    if require_admin_auth is not None:
        admin_deps.append(Depends(require_admin_auth))
    if require_rbac_permission is not None:
        admin_deps.append(Depends(require_rbac_permission("license.write")))
    if not admin_deps:
        logger.warning(
            "create_license_validation_router built without auth dependencies — "
            "/v1/license/* will be reachable without auth."
        )

    @router.post("/v1/license/validate", dependencies=admin_deps)
    async def validate_license(
        x_license_key: str = Header(..., description="License key to validate"),
    ) -> dict:
        """Validate a license key. Called by the Rust proxy on startup.

        Security chain:
          1. Try PitchToShip remote verification
          2. If offline, try ECDSA local verification (cached signed token)
          3. Fallback to local SQLite validation (legacy installations)
        """
        from headroom_ee.billing.pitchtoship_client import (
            verify_license as pts_verify,
            verify_signed_token,
            _get_cached_public_key,
            _get_cached_signed_token,
        )

        pts_result = pts_verify(x_license_key, hwid="")
        if pts_result is not None:
            logger.info(
                "License validated via PitchToShip for key=%s", x_license_key[:8]
            )
            return pts_result

        logger.info("PitchToShip unavailable, attempting local ECDSA verification")
        signed_token = _get_cached_signed_token(x_license_key)
        if signed_token:
            public_key = _get_cached_public_key()
            if public_key:
                payload = verify_signed_token(signed_token, public_key)
                if payload:
                    logger.info(
                        "License validated via local ECDSA for key=%s",
                        x_license_key[:8],
                    )
                    return {
                        "valid": True,
                        "tier": payload.get("tier"),
                        "features": payload.get("features"),
                        "expires_at": payload.get("expires_at"),
                        "offline_verified": True,
                    }

        try:
            from headroom_ee.billing.license_db import get_license_db

            db = get_license_db()
            result = db.validate(x_license_key)
            if not result["valid"]:
                logger.warning(
                    "License validation failed (all methods) for key=%s",
                    x_license_key[:8],
                )
                raise HTTPException(status_code=403, detail=result)
            logger.info(
                "License validated via local SQLite for key=%s", x_license_key[:8]
            )
            return result
        except HTTPException:
            raise
        except Exception:
            logger.warning(
                "FAIL CLOSED: All license validation methods failed for key=%s",
                x_license_key[:8],
            )
            raise HTTPException(
                status_code=403, detail={"valid": False, "error": "validation_unavailable"}
            )

    class ActivateRequest(BaseModel):
        license_key: str
        instance_id: str

    @router.post("/v1/license/activate", dependencies=admin_deps)
    async def activate_license(req: ActivateRequest) -> dict:
        from headroom_ee.billing.license_db import get_license_db

        db = get_license_db()
        result = db.validate(req.license_key)
        if not result["valid"]:
            raise HTTPException(status_code=403, detail=result)
        db.activate_instance(req.license_key, req.instance_id)
        return {"status": "ok"}

    @router.get("/v1/license/crl", dependencies=admin_deps)
    async def get_crl() -> dict:
        from headroom_ee.billing.license_db import get_license_db

        db = get_license_db()
        return {"revoked": db.get_crl()}

    class CheckoutSeatRequest(BaseModel):
        license_key: str
        user_id: str
        lease_duration: float = 3600.0

    @router.post("/v1/license/checkout-seat", dependencies=admin_deps)
    async def checkout_seat(req: CheckoutSeatRequest) -> dict:
        from headroom_ee.billing.license_db import get_license_db

        db = get_license_db()
        result = db.validate(req.license_key)
        if not result["valid"]:
            raise HTTPException(status_code=403, detail=result)
        success = db.checkout_seat(req.license_key, req.user_id, req.lease_duration)
        if not success:
            raise HTTPException(
                status_code=429, detail={"error": "no_seats_available"}
            )
        return {"status": "ok"}

    class StartTrialRequest(BaseModel):
        trial_token: str
        customer_email: str
        duration: float = 14 * 86400.0

    @router.post("/v1/license/start-trial", dependencies=admin_deps)
    async def start_trial(req: StartTrialRequest) -> dict:
        from headroom_ee.billing.license_db import get_license_db

        db = get_license_db()
        success = db.start_trial(req.trial_token, req.customer_email, req.duration)
        if not success:
            raise HTTPException(
                status_code=409, detail={"error": "trial_already_started"}
            )
        return {"status": "ok"}

    class CheckTrialRequest(BaseModel):
        trial_token: str

    @router.post("/v1/license/check-trial", dependencies=admin_deps)
    async def check_trial(req: CheckTrialRequest) -> dict:
        from headroom_ee.billing.license_db import get_license_db

        db = get_license_db()
        active = db.is_trial_active(req.trial_token)
        return {"active": active}

    @router.post("/webhooks/stripe")
    async def stripe_webhook(request: Request) -> dict:
        """Handle Stripe webhook events. NOT admin-gated — uses
        ``STRIPE_WEBHOOK_SECRET`` HMAC signature check for auth.
        """
        from headroom.billing.stripe_webhook import (
            STRIPE_WEBHOOK_SECRET,
            handle_event,
            verify_stripe_signature,
        )

        payload = await request.body()
        stripe_signature = request.headers.get("stripe-signature", "")

        if STRIPE_WEBHOOK_SECRET:
            if not verify_stripe_signature(payload, stripe_signature):
                raise HTTPException(status_code=400, detail="Invalid signature")

        event = await request.json()
        return handle_event(event)

    return router


__all__ = ["create_license_validation_router"]
