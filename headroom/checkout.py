"""Checkout redirect and upgrade URL generation.

Provides checkout URLs for PitchToShip payment flow and upgrade links
that entitlement errors point users to.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

logger = logging.getLogger("headroom.checkout")

# PitchToShip checkout base URL
_PITCHTOSHIP_CHECKOUT_BASE = "https://pitchtoship.com/checkout"

# Product slugs per tier upgrade
_UPGRADE_PRODUCTS = {
    "team": "headroom-team",
    "business": "headroom-business",
    "enterprise": "headroom-enterprise",
}

# CutCtx pricing page (fallback)
_PRICING_URL = "https://cutctx.dev/pricing"
_SUPPORT_EMAIL = "hello@cutctx.dev"


def checkout_url(tier: str, org_id: str | None = None) -> str:
    """Generate a PitchToShip checkout URL for upgrading to the given tier.

    Args:
        tier: Target tier name ("team", "business", or "enterprise").
        org_id: Optional organization ID to include in the checkout redirect.

    Returns:
        Full checkout URL string.
    """
    product = _UPGRADE_PRODUCTS.get(tier.lower().strip())
    if product is None:
        logger.warning("Unknown tier %r for checkout URL, falling back to pricing page", tier)
        return _PRICING_URL

    params: dict[str, str] = {"product": product}
    if org_id:
        params["org"] = org_id

    url = f"{_PITCHTOSHIP_CHECKOUT_BASE}?{urlencode(params)}"
    logger.debug("Generated checkout URL for tier=%s: %s", tier, url)
    return url


def upgrade_url(current_tier: str, required_feature: str | None = None) -> str:
    """Return the best upgrade URL for a user on the given tier.

    Suggests the next tier up from the current tier. If the user is already
    at the highest tier, returns the pricing page.

    Args:
        current_tier: Current tier name (e.g., "builder", "team", "business").
        required_feature: Optional feature that was denied (for future use).

    Returns:
        URL string pointing to the appropriate upgrade page.
    """
    tier_order = ["builder", "team", "business", "enterprise"]
    current = current_tier.lower().strip()

    try:
        idx = tier_order.index(current)
    except ValueError:
        # Unknown tier — suggest team as default upgrade
        return checkout_url("team")

    # Suggest next tier up
    if idx < len(tier_order) - 1:
        next_tier = tier_order[idx + 1]
        return checkout_url(next_tier)

    # Already at top tier — show pricing page
    return _PRICING_URL


def support_url() -> str:
    """Return the support/contact URL."""
    return _SUPPORT_EMAIL


def pricing_url() -> str:
    """Return the public pricing page URL."""
    return _PRICING_URL
