import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/license", tags=["License"])

try:
    from headroom_ee.billing.license_db import get_license_db
except ImportError:
    # If EE isn't installed, return an error for all endpoints
    def get_license_db() -> Any:
        raise HTTPException(status_code=501, detail="Enterprise billing module not installed")

class ActivateRequest(BaseModel):
    license_key: str
    instance_id: str

@router.post("/activate")
async def activate_license(req: ActivateRequest) -> dict:
    db = get_license_db()
    if db.is_revoked(req.license_key):
        raise HTTPException(status_code=403, detail="License revoked")
    record = db.get(req.license_key)
    if not record or not record.active:
        raise HTTPException(status_code=401, detail="Invalid license")

    success = db.activate_instance(req.license_key, req.instance_id)
    if not success:
        return {"status": "already_activated"}
    return {"status": "activated"}

@router.get("/crl")
async def get_crl() -> dict:
    db = get_license_db()
    crl = db.get_crl()
    return {"revoked": crl}

class CheckoutSeatRequest(BaseModel):
    license_key: str
    user_id: str
    lease_duration: float = 3600.0

@router.post("/checkout-seat")
async def checkout_seat(req: CheckoutSeatRequest) -> dict:
    db = get_license_db()
    if db.is_revoked(req.license_key):
        raise HTTPException(status_code=403, detail="License revoked")
    success = db.checkout_seat(req.license_key, req.user_id, req.lease_duration)
    if not success:
        raise HTTPException(status_code=429, detail="No seats available")
    return {"status": "seat_leased"}

class StartTrialRequest(BaseModel):
    trial_token: str
    customer_email: str
    duration: float = 14 * 86400.0

@router.post("/start-trial")
async def start_trial(req: StartTrialRequest) -> dict:
    db = get_license_db()
    success = db.start_trial(req.trial_token, req.customer_email, req.duration)
    if not success:
        raise HTTPException(status_code=409, detail="Trial already exists")
    return {"status": "trial_started"}

class CheckTrialRequest(BaseModel):
    trial_token: str

@router.post("/check-trial")
async def check_trial(req: CheckTrialRequest) -> dict:
    db = get_license_db()
    active = db.is_trial_active(req.trial_token)
    return {"active": active}
