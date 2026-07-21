"""Checkout redirect and upgrade URL generation.

Provides checkout URLs for PitchToShip payment flow and upgrade links
that entitlement errors point users to.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from cutctx.billing import get_checkout_url, map_tier_to_plan

logger = logging.getLogger("cutctx.checkout")

_SUPPORTED_TIERS = {"team", "business", "enterprise"}

# Cutctx pricing page (fallback)
_PRICING_URL = "https://cutctx.com/pricing/"
_SUPPORT_EMAIL = "hello@aoexl.com"


def checkout_url(tier: str, org_id: str | None = None) -> str:
    """Generate a PitchToShip checkout URL for upgrading to the given tier.

    Args:
        tier: Target tier name ("team", "business", or "enterprise").
        org_id: Optional organization ID to include in the checkout redirect.

    Returns:
        Full checkout URL string.
    """
    normalized_tier = tier.lower().strip()
    if normalized_tier not in _SUPPORTED_TIERS:
        logger.warning("Unknown tier %r for checkout URL, falling back to pricing page", tier)
        return _PRICING_URL

    url = get_checkout_url(map_tier_to_plan(normalized_tier), billing="annual")
    if org_id:
        url = f"{url}&{urlencode({'org': org_id})}"

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
