"""Hosted CutCtx commerce links managed by PitchToShip.

PitchToShip owns Razorpay checkout, payment verification, license issuance,
and the customer account portal. CutCtx only builds deterministic links to
those hosted surfaces; it never creates payment orders or handles gateway
credentials.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlencode

logger = logging.getLogger("cutctx.billing")

PITCHTOSHIP_BASE_URL = os.environ.get(
    "PITCHTOSHIP_URL",
    "https://pitchtoship.com",
).rstrip("/")

TIER_TO_PLAN = {
    "team": "starter",
    "business": "studio",
    "enterprise": "portfolio",
}


def get_checkout_url(
    plan: str,
    email: str | None = None,
    billing: str = "annual",
) -> str:
    """Build a hosted PitchToShip Razorpay billing link."""
    if plan not in {"starter", "studio", "portfolio"}:
        logger.warning("Unknown plan %r, defaulting to starter", plan)
        plan = "starter"
    if billing not in {"monthly", "annual"}:
        logger.warning("Unknown billing %r, defaulting to annual", billing)
        billing = "annual"

    query = urlencode(
        {
            "product": "cutctx",
            "plan": plan,
            "billing": billing,
            **({"email": email.strip()} if email and email.strip() else {}),
        }
    )
    return f"{PITCHTOSHIP_BASE_URL}/billing?{query}"


def get_portal_url(email: str) -> str:
    """Build a hosted PitchToShip customer-account link."""
    if not email:
        return f"{PITCHTOSHIP_BASE_URL}/account"
    return f"{PITCHTOSHIP_BASE_URL}/account?{urlencode({'email': email.strip()})}"


def map_tier_to_plan(tier: str) -> str:
    """Map a CutCtx tier name to a PitchToShip plan key."""
    plan = TIER_TO_PLAN.get(tier.lower().strip())
    if plan is None:
        logger.warning("Unknown tier %r for mapping, defaulting to starter", tier)
        return "starter"
    return plan
