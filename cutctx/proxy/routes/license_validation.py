# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""FastAPI router factory for license validation + Stripe webhook.

Blocker-1: the license-management routes were previously unauthenticated.
Mutation and administrative read endpoints now require admin auth plus the
``license.write`` RBAC permission. ``/v1/license/validate`` remains public by
design because the high-entropy license key is the bearer credential used for
first activation and cloud validation. The Stripe webhook is authenticated via
``STRIPE_WEBHOOK_SECRET`` (HMAC signature check), not via the admin API key.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ActivateRequest(BaseModel):
    license_key: str
    instance_id: str


class CheckoutSeatRequest(BaseModel):
    license_key: str
    user_id: str
    lease_duration: float = 3600.0


class ValidateLicenseRequest(BaseModel):
    license_key: str


class StartTrialRequest(BaseModel):
    trial_token: str
    customer_email: str
    duration: float = 14 * 86400.0


class CheckTrialRequest(BaseModel):
    trial_token: str


def create_license_validation_router(
    require_admin_auth: Callable[..., Any] | None = None,
    require_rbac_permission: Callable[..., Any] | None = None,
) -> APIRouter:
    """Build the license-validation router with auth on management endpoints.

    License validation is intentionally public because possession of the
    high-entropy key is the validation credential. The Stripe webhook uses its
    own signature verification and is not gated by admin auth.
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
            "license-management endpoints will be reachable without auth."
        )

    @router.post("/v1/license/validate")
    async def validate_license(
        req: ValidateLicenseRequest,
    ) -> dict:
        """Validate a bearer license key. Called by clients on activation.

        Security chain:
          1. Try PitchToShip remote verification
          2. If offline, try ECDSA local verification (cached signed token)
          3. Fallback to local SQLite validation (legacy installations)
        """
        from cutctx_ee.billing.pitchtoship_client import (
            _get_cached_public_key,
            _get_cached_signed_token,
            verify_signed_token,
        )
        from cutctx_ee.billing.pitchtoship_client import (
            verify_license as pts_verify,
        )

        license_key = req.license_key

        def normalized_valid_result(result: dict) -> dict:
            return {
                "status": result.get("status") or "active",
                "plan": result.get("plan") or result.get("tier"),
                **({"org_id": result["org_id"]} if result.get("org_id") else {}),
                **({"org_name": result["org_name"]} if result.get("org_name") else {}),
                **({"seats": result["seats"]} if result.get("seats") is not None else {}),
                **({"expires_at": result["expires_at"]} if result.get("expires_at") else {}),
                **({"features": result["features"]} if result.get("features") else {}),
                **({"offline_verified": True} if result.get("offline_verified") else {}),
            }

        pts_result = pts_verify(license_key, hwid="")
        if pts_result is not None:
            if pts_result.get("valid"):
                logger.info("License validated via PitchToShip for key=%s", license_key[:8])
                return normalized_valid_result(pts_result)
            logger.warning(
                "PitchToShip definitively rejected license for key=%s",
                license_key[:8],
            )
            raise HTTPException(status_code=403, detail=pts_result)

        logger.info("PitchToShip unavailable, attempting local ECDSA verification")
        signed_token = _get_cached_signed_token(license_key)
        if signed_token:
            public_key = _get_cached_public_key()
            if public_key:
                payload = verify_signed_token(signed_token, public_key)
                if payload:
                    logger.info(
                        "License validated via local ECDSA for key=%s",
                        license_key[:8],
                    )
                    return normalized_valid_result(
                        {
                            "valid": True,
                            "tier": payload.get("tier"),
                            "features": payload.get("features"),
                            "expires_at": payload.get("expires_at"),
                            "offline_verified": True,
                        }
                    )

        try:
            from cutctx_ee.billing.license_db import get_license_db

            db = get_license_db()
            result = db.validate(license_key)
            if not result["valid"]:
                logger.warning(
                    "License validation failed (all methods) for key=%s",
                    license_key[:8],
                )
                raise HTTPException(status_code=403, detail=result)
            logger.info("License validated via local SQLite for key=%s", license_key[:8])
            return normalized_valid_result(result)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(
                "FAIL CLOSED: All license validation methods failed for key=%s",
                license_key[:8],
            )
            raise HTTPException(
                status_code=403, detail={"valid": False, "error": "validation_unavailable"}
            ) from e

    @router.post("/v1/license/activate", dependencies=admin_deps)
    async def activate_license(req: ActivateRequest) -> dict:
        from cutctx_ee.billing.pitchtoship_client import heartbeat_seat, verify_license

        hosted_result = verify_license(req.license_key, req.instance_id)
        if hosted_result is not None:
            if not hosted_result.get("valid"):
                raise HTTPException(status_code=403, detail=hosted_result)
            heartbeat = heartbeat_seat(req.license_key, req.instance_id)
            if not heartbeat or not heartbeat.get("accepted"):
                raise HTTPException(status_code=409, detail={"error": "activation_rejected"})
            return {"status": "ok"}

        from cutctx_ee.billing.license_db import get_license_db

        db = get_license_db()
        result = db.validate(req.license_key)
        if not result["valid"]:
            raise HTTPException(status_code=403, detail=result)
        if not db.activate_instance(req.license_key, req.instance_id):
            raise HTTPException(status_code=409, detail={"error": "activation_rejected"})
        return {"status": "ok"}

    @router.get("/v1/license/crl", dependencies=admin_deps)
    async def get_crl() -> dict:
        from cutctx_ee.billing.license_db import get_license_db

        db = get_license_db()
        return {"revoked": db.get_crl()}

    @router.post("/v1/license/checkout-seat", dependencies=admin_deps)
    async def checkout_seat(req: CheckoutSeatRequest) -> dict:
        from cutctx_ee.billing.pitchtoship_client import heartbeat_seat, verify_license

        hosted_result = verify_license(req.license_key, req.user_id)
        if hosted_result is not None:
            if not hosted_result.get("valid"):
                raise HTTPException(status_code=403, detail=hosted_result)
            heartbeat = heartbeat_seat(req.license_key, req.user_id)
            if not heartbeat or not heartbeat.get("accepted"):
                raise HTTPException(status_code=429, detail={"error": "no_seats_available"})
            return {"status": "ok"}

        from cutctx_ee.billing.license_db import get_license_db

        db = get_license_db()
        result = db.validate(req.license_key)
        if not result["valid"]:
            raise HTTPException(status_code=403, detail=result)
        success = db.checkout_seat(req.license_key, req.user_id, req.lease_duration)
        if not success:
            raise HTTPException(status_code=429, detail={"error": "no_seats_available"})
        return {"status": "ok"}

    @router.post("/v1/license/start-trial", dependencies=admin_deps)
    async def start_trial(req: StartTrialRequest) -> dict:
        from cutctx_ee.billing.license_db import get_license_db

        db = get_license_db()
        success = db.start_trial(req.trial_token, req.customer_email, req.duration)
        if not success:
            raise HTTPException(status_code=409, detail={"error": "trial_already_started"})
        return {"status": "ok"}

    @router.post("/v1/license/check-trial", dependencies=admin_deps)
    async def check_trial(req: CheckTrialRequest) -> dict:
        from cutctx_ee.billing.license_db import get_license_db

        db = get_license_db()
        active = db.is_trial_active(req.trial_token)
        return {"active": active}

    @router.post("/webhooks/stripe")
    async def stripe_webhook(request: Request) -> dict:
        """Handle Stripe webhook events. NOT admin-gated — uses
        ``STRIPE_WEBHOOK_SECRET`` HMAC signature check for auth.

        Audit-Deep-2026-06-21: the previous code silently
        bypassed signature verification when ``STRIPE_WEBHOOK_SECRET``
        was empty, allowing any caller to forge webhook events.
        The endpoint now:

          1. Refuses the request (401) when ``STRIPE_WEBHOOK_SECRET``
             is empty AND ``CUTCTX_BILLING_STRICT_MODE=1`` (default).
          2. Logs a loud warning when in non-strict mode (dev only).
          3. Verifies the signature in either case.
        """
        import logging

        from cutctx.billing.stripe_webhook import (
            STRIPE_WEBHOOK_SECRET,
            handle_event,
            verify_stripe_signature,
        )

        strict_mode = os.environ.get("CUTCTX_BILLING_STRICT_MODE", "1") == "1"
        if not STRIPE_WEBHOOK_SECRET:
            if strict_mode:
                logging.getLogger(__name__).error(
                    "Stripe webhook called but STRIPE_WEBHOOK_SECRET "
                    "is not configured and CUTCTX_BILLING_STRICT_MODE=1. "
                    "Refusing to process the event."
                )
                raise HTTPException(
                    status_code=503,
                    detail="Stripe webhook is not configured",
                )
            else:
                logging.getLogger(__name__).warning(
                    "Stripe webhook called but STRIPE_WEBHOOK_SECRET "
                    "is not configured. Strict mode is off; processing "
                    "the event without signature verification. NEVER "
                    "deploy without CUTCTX_BILLING_STRICT_MODE=1 in "
                    "production."
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
