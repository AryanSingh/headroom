"""Billing integration with PitchToShip checkout system.

Provides functions to generate checkout URLs and handle billing portal access
by communicating with the PitchToShip API.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("cutctx.billing")

# PitchToShip base URL from environment or production default
PITCHTOSHIP_BASE_URL = os.environ.get(
    "PITCHTOSHIP_URL",
    "https://pitchtoship.com",
).rstrip("/")

# Map Cutctx tiers to pitchtoship plans
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
    """Get a Stripe Checkout URL from PitchToShip billing API.

    Calls the pitchtoship /api/billing/checkout endpoint and returns
    the Stripe redirect URL. On failure, falls back to returning the
    checkout page URL directly.

    Args:
        plan: Plan key ('starter', 'studio', or 'portfolio').
        email: Optional customer email for pre-fill.
        billing: Billing period ('monthly' or 'annual'). Defaults to 'annual'.

    Returns:
        Full Stripe Checkout URL string.
    """

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not available; falling back to checkout page URL")
        return f"{PITCHTOSHIP_BASE_URL}/checkout?plan={plan}"

    # Validate plan
    if plan not in ["starter", "studio", "portfolio"]:
        logger.warning("Unknown plan %r, defaulting to starter", plan)
        plan = "starter"

    # Validate billing
    if billing not in ["monthly", "annual"]:
        logger.warning("Unknown billing %r, defaulting to annual", billing)
        billing = "annual"

    # Call pitchtoship API
    api_url = f"{PITCHTOSHIP_BASE_URL}/api/billing/checkout"
    payload = {
        "plan": plan,
        "billing": billing,
    }
    if email:
        payload["email"] = email.strip()

    try:
        response = httpx.post(api_url, json=payload, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        if "url" in data:
            checkout_url = data["url"]
            logger.info("Got checkout URL from pitchtoship for plan=%s", plan)
            return checkout_url
        else:
            logger.warning("PitchToShip response missing 'url' field, falling back")
            return f"{PITCHTOSHIP_BASE_URL}/checkout?plan={plan}"

    except Exception as e:
        logger.warning("Failed to get checkout URL from pitchtoship: %s, falling back", e)
        # Graceful fallback: return the checkout page URL directly
        return f"{PITCHTOSHIP_BASE_URL}/checkout?plan={plan}"


def get_portal_url(email: str) -> str:
    """Get a customer billing portal URL from PitchToShip API.

    Calls the pitchtoship /api/billing/portal endpoint to retrieve
    the Stripe billing portal URL for the customer.

    Args:
        email: Customer email address.

    Returns:
        Full billing portal URL string.
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not available; cannot retrieve portal URL")
        return f"{PITCHTOSHIP_BASE_URL}/billing"

    if not email:
        logger.warning("No email provided for portal URL")
        return f"{PITCHTOSHIP_BASE_URL}/billing"

    api_url = f"{PITCHTOSHIP_BASE_URL}/api/billing/portal"
    payload = {"email": email.strip()}

    try:
        response = httpx.post(api_url, json=payload, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        if "url" in data:
            portal_url = data["url"]
            logger.info("Got billing portal URL from pitchtoship for email=%s", email)
            return portal_url
        else:
            logger.warning("PitchToShip response missing 'url' field for portal, falling back")
            return f"{PITCHTOSHIP_BASE_URL}/billing"

    except Exception as e:
        logger.warning("Failed to get billing portal URL from pitchtoship: %s, falling back", e)
        # Graceful fallback
        return f"{PITCHTOSHIP_BASE_URL}/billing"


def map_tier_to_plan(tier: str) -> str:
    """Map a Cutctx tier name to a pitchtoship plan key.

    Args:
        tier: Cutctx tier ('team', 'business', or 'enterprise').

    Returns:
        PitchToShip plan key ('starter', 'studio', or 'portfolio').
    """
    plan = TIER_TO_PLAN.get(tier.lower().strip())
    if plan is None:
        logger.warning("Unknown tier %r for mapping, defaulting to starter", tier)
        return "starter"
    return plan
