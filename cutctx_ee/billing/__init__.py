# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""CutCtx hosted commerce links managed by PitchToShip.

PitchToShip owns Razorpay checkout and customer account management. This
module creates safe hosted links and keeps payment secrets out of CutCtx.
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
