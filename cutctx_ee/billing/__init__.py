# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""CutCtx hosted commerce links for checkout and license recovery.

Self-serve checkout and license management live on cutctx.com and are backed
by Supabase Edge Functions. This module only builds safe deep links into those
surfaces — it never creates payment orders or handles gateway credentials.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlencode

logger = logging.getLogger("cutctx.billing")

CUTCTX_SITE_URL = os.environ.get(
    "CUTCTX_SITE_URL",
    os.environ.get("PITCHTOSHIP_URL", "https://cutctx.com"),
).rstrip("/")
# Backward-compatible alias — older call sites and env docs still use the name.
PITCHTOSHIP_BASE_URL = CUTCTX_SITE_URL

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
    """Build a CutCtx pricing deep link for the given plan.

    Checkout itself is completed on the pricing page via Supabase
    ``create-order`` / ``verify-payment``. This helper only deep-links there.
    """
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
    return f"{CUTCTX_SITE_URL}/pricing/?{query}"


def get_portal_url(email: str) -> str:
    """Build a CutCtx license-portal deep link."""
    if not email:
        return f"{CUTCTX_SITE_URL}/licenses/"
    return f"{CUTCTX_SITE_URL}/licenses/?{urlencode({'email': email.strip()})}"


def map_tier_to_plan(tier: str) -> str:
    """Map a CutCtx tier name to a hosted plan key."""
    plan = TIER_TO_PLAN.get(tier.lower().strip())
    if plan is None:
        logger.warning("Unknown tier %r for mapping, defaulting to starter", tier)
        return "starter"
    return plan
