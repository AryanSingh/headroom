"""FastAPI route: license validation + Stripe webhook."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/license/validate")
async def validate_license(
    x_license_key: str = Header(..., description="License key to validate"),
) -> dict:
    """Validate a license key. Called by the Rust proxy on startup."""
    from headroom.billing.license_db import get_license_db

    db = get_license_db()
    result = db.validate(x_license_key)
    if not result["valid"]:
        raise HTTPException(status_code=403, detail=result)
    return result


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
