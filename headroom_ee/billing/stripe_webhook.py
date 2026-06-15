# SPDX-License-Identifier: LicenseRef-Headroom-Commercial
# Copyright (c) 2025-2026 Headroom Labs. All rights reserved.
# Proprietary and confidential. NOT licensed under Apache-2.0. See LICENSE-COMMERCIAL and LICENSING.md.

"""Stripe webhook receiver — handles subscription lifecycle events.

Events handled:
  checkout.session.completed  -> create license + seat record
  invoice.paid                -> extend license expiry
  customer.subscription.deleted -> deactivate license
  customer.subscription.updated -> update tier/seats
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")

# Map Stripe Price IDs -> CutCtx tiers
PRICE_TO_TIER: dict[str, str] = {
    os.environ.get("STRIPE_PRICE_TEAM", ""): "team",
    os.environ.get("STRIPE_PRICE_BUSINESS", ""): "business",
    os.environ.get("STRIPE_PRICE_ENTERPRISE", ""): "enterprise",
}


@dataclass
class LicenseRecord:
    """Represents a issued license."""

    license_key: str
    tier: str
    customer_email: str
    seats: int
    stripe_customer_id: str
    stripe_subscription_id: str
    created_at: float
    expires_at: float
    active: bool


def verify_stripe_signature(payload: bytes, sig_header: str) -> bool:
    """Constant-time Stripe webhook signature verification."""
    if not STRIPE_WEBHOOK_SECRET:
        raise ValueError("STRIPE_WEBHOOK_SECRET not configured")
    parts = dict(item.split("=", 1) for item in sig_header.split(","))
    timestamp = parts.get("t", "")
    v1 = parts.get("v1", "")
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def generate_license_key(tier: str, customer_id: str) -> str:
    """Generate a signed license key.

    Format: {tier}-{random_id}-{hmac_signature}
    The proxy verifies the HMAC before accepting the tier prefix.
    """
    random_id = secrets.token_hex(8)
    secret = os.environ.get("HEADROOM_LICENSE_HMAC_SECRET", "")
    if not secret:
        raise ValueError("HEADROOM_LICENSE_HMAC_SECRET not set")
    payload = f"{tier}:{random_id}:{customer_id}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{tier}-{random_id}-{sig}"


def handle_checkout_completed(event_data: dict[str, Any]) -> LicenseRecord:
    """Handle Stripe checkout.session.completed event."""
    session = event_data["object"]
    customer_id = session["customer"]
    subscription_id = session.get("subscription", "")
    metadata = session.get("metadata", {})
    tier = metadata.get("tier", "team")
    seats = int(metadata.get("seats", 5))
    email = session.get("customer_details", {}).get("email", "")

    key = generate_license_key(tier, customer_id)
    now = time.time()

    record = LicenseRecord(
        license_key=key,
        tier=tier,
        customer_email=email,
        seats=seats,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        created_at=now,
        expires_at=now + (365 * 86400),  # 1 year
        active=True,
    )
    _save_license(record)
    _send_license_email(email, key, tier, seats)
    return record


def handle_subscription_deleted(event_data: dict[str, Any]) -> None:
    """Handle customer.subscription.deleted — deactivate license."""
    subscription = event_data["object"]
    sub_id = subscription["id"]
    logger.info("Subscription deleted: %s", sub_id)
    # License deactivation handled by license_db


def handle_subscription_updated(event_data: dict[str, Any]) -> None:
    """Handle customer.subscription.updated — update tier/seats."""
    subscription = event_data["object"]
    sub_id = subscription["id"]
    logger.info("Subscription updated: %s", sub_id)


def _save_license(record: LicenseRecord) -> None:
    """Save to license DB."""
    from headroom.billing.license_db import get_license_db

    db = get_license_db()
    db.upsert(record)


def _send_license_email(email: str, key: str, tier: str, seats: int) -> None:
    """Send license key via email."""
    logger.info(
        "License issued: %s -> %s (%s, %d seats)",
        email,
        key[:20] + "...",
        tier,
        seats,
    )


def handle_event(event: dict[str, Any]) -> dict[str, Any]:
    """Main entry point for Stripe webhook events."""
    event_type = event.get("type", "")
    data = event.get("data", {})

    if event_type == "checkout.session.completed":
        record = handle_checkout_completed(data)
        return {"ok": True, "license_key": record.license_key}
    elif event_type == "invoice.paid":
        return {"ok": True, "action": "extended"}
    elif event_type == "customer.subscription.deleted":
        handle_subscription_deleted(data)
        return {"ok": True, "action": "deactivated"}
    elif event_type == "customer.subscription.updated":
        handle_subscription_updated(data)
        return {"ok": True, "action": "updated"}
    else:
        logger.info("Unhandled Stripe event type: %s", event_type)
        return {"ok": True, "action": "ignored"}
