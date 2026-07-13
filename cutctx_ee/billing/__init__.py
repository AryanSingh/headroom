# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Cutctx billing infrastructure.

Provides functions to generate checkout URLs and handle billing portal access
by communicating with the PitchToShip API, plus sub-modules for license DB
and Stripe webhook handling.
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
_PLAN_TO_TIER = {plan: tier for tier, plan in TIER_TO_PLAN.items()}


def _direct_stripe_checkout_url(plan: str, email: str | None, billing: str) -> str | None:
    """Create a Stripe Checkout session when all direct-billing inputs exist."""
    secret = os.environ.get("STRIPE_SECRET_KEY")
    tier = _PLAN_TO_TIER.get(plan)
    price_id = os.environ.get(f"CUTCTX_STRIPE_PRICE_{tier.upper()}_{billing.upper()}") if tier else None
    if not secret or not price_id:
        return None
    import httpx

    data = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": os.environ.get("CUTCTX_STRIPE_SUCCESS_URL", "https://cutctx.com/billing/success?session_id={CHECKOUT_SESSION_ID}"),
        "cancel_url": os.environ.get("CUTCTX_STRIPE_CANCEL_URL", "https://cutctx.com/pricing"),
    }
    if email:
        data["customer_email"] = email.strip()
    response = httpx.post("https://api.stripe.com/v1/checkout/sessions", data=data, auth=(secret, ""), timeout=10.0)
    response.raise_for_status()
    url = response.json().get("url")
    if not isinstance(url, str) or not url.startswith("https://checkout.stripe.com/"):
        raise RuntimeError("Stripe Checkout did not return a valid hosted checkout URL")
    return url


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
    # Validate plan
    if plan not in ["starter", "studio", "portfolio"]:
        logger.warning("Unknown plan %r, defaulting to starter", plan)
        plan = "starter"

    # Validate billing
    if billing not in ["monthly", "annual"]:
        logger.warning("Unknown billing %r, defaulting to annual", billing)
        billing = "annual"

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not available; falling back to checkout page URL")
        return f"{PITCHTOSHIP_BASE_URL}/checkout?plan={plan}"

    try:
        direct_url = _direct_stripe_checkout_url(plan, email, billing)
        if direct_url:
            return direct_url
    except Exception as e:
        logger.warning("Direct Stripe checkout failed: %s", e)

    api_url = f"{PITCHTOSHIP_BASE_URL}/api/billing/checkout"
    payload: dict = {"plan": plan, "billing": billing}
    if email:
        payload["email"] = email.strip()

    try:
        response = httpx.post(api_url, json=payload, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        if "url" in data:
            logger.info("Got checkout URL from pitchtoship for plan=%s", plan)
            return data["url"]
        logger.warning("PitchToShip response missing 'url' field, falling back")
        return f"{PITCHTOSHIP_BASE_URL}/checkout?plan={plan}"
    except Exception as e:
        logger.warning("Failed to get checkout URL from pitchtoship: %s, falling back", e)
        return f"{PITCHTOSHIP_BASE_URL}/checkout?plan={plan}"


def get_portal_url(email: str) -> str:
    """Get a customer billing portal URL from PitchToShip API.

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
            logger.info("Got billing portal URL from pitchtoship for email=%s", email)
            return data["url"]
        logger.warning("PitchToShip response missing 'url' field for portal, falling back")
        return f"{PITCHTOSHIP_BASE_URL}/billing"
    except Exception as e:
        logger.warning("Failed to get billing portal URL from pitchtoship: %s, falling back", e)
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
