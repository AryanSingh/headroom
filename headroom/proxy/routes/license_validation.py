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


from pydantic import BaseModel

class ActivateRequest(BaseModel):
    license_key: str
    instance_id: str

@router.post("/v1/license/activate")
async def activate_license(req: ActivateRequest) -> dict:
    """Activate a proxy instance."""
    from headroom.billing.license_db import get_license_db

    db = get_license_db()
    result = db.validate(req.license_key)
    if not result["valid"]:
        raise HTTPException(status_code=403, detail=result)
        
    db.activate_instance(req.license_key, req.instance_id)
    return {"status": "ok"}


@router.get("/v1/license/crl")
async def get_crl() -> dict:
    """Get the Certificate Revocation List (CRL)."""
    from headroom.billing.license_db import get_license_db

    db = get_license_db()
    return {"revoked": db.get_crl()}


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
