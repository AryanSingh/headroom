"""FastAPI route: license validation + Stripe webhook."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/license/validate")
async def validate_license(
    x_license_key: str = Header(..., description="License key to validate"),
) -> dict:
    """Validate a license key. Called by the Rust proxy on startup."""
    from headroom_ee.billing.license_db import get_license_db

    db = get_license_db()
    result = db.validate(x_license_key)
    if not result["valid"]:
        raise HTTPException(status_code=403, detail=result)
    return result


class ActivateRequest(BaseModel):
    license_key: str
    instance_id: str


@router.post("/v1/license/activate")
async def activate_license(req: ActivateRequest) -> dict:
    """Activate a proxy instance."""
    from headroom_ee.billing.license_db import get_license_db

    db = get_license_db()
    result = db.validate(req.license_key)
    if not result["valid"]:
        raise HTTPException(status_code=403, detail=result)

    db.activate_instance(req.license_key, req.instance_id)
    return {"status": "ok"}


@router.get("/v1/license/crl")
async def get_crl() -> dict:
    """Get the Certificate Revocation List (CRL)."""
    from headroom_ee.billing.license_db import get_license_db

    db = get_license_db()
    return {"revoked": db.get_crl()}


class CheckoutSeatRequest(BaseModel):
    license_key: str
    user_id: str
    lease_duration: float = 3600.0


@router.post("/v1/license/checkout-seat")
async def checkout_seat(req: CheckoutSeatRequest) -> dict:
    """Checkout or renew a seat lease."""
    from headroom_ee.billing.license_db import get_license_db

    db = get_license_db()
    result = db.validate(req.license_key)
    if not result["valid"]:
        raise HTTPException(status_code=403, detail=result)

    success = db.checkout_seat(req.license_key, req.user_id, req.lease_duration)
    if not success:
        raise HTTPException(status_code=429, detail={"error": "no_seats_available"})

    return {"status": "ok"}


class StartTrialRequest(BaseModel):
    trial_token: str
    customer_email: str
    duration: float = 14 * 86400.0


@router.post("/v1/license/start-trial")
async def start_trial(req: StartTrialRequest) -> dict:
    """Start a server-side trial."""
    from headroom_ee.billing.license_db import get_license_db

    db = get_license_db()

    success = db.start_trial(req.trial_token, req.customer_email, req.duration)
    if not success:
        raise HTTPException(status_code=409, detail={"error": "trial_already_started"})
    return {"status": "ok"}


class CheckTrialRequest(BaseModel):
    trial_token: str


@router.post("/v1/license/check-trial")
async def check_trial(req: CheckTrialRequest) -> dict:
    """Check if a trial is active."""
    from headroom_ee.billing.license_db import get_license_db

    db = get_license_db()

    active = db.is_trial_active(req.trial_token)
    return {"active": active}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict:
    """Handle Stripe webhook events."""
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
