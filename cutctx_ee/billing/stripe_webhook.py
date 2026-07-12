# SPDX-License-Identifier: LicenseRef-Cutctx-Commercial
# Copyright (c) 2025-2026 Cutctx Labs. All rights reserved.
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
STRIPE_WEBHOOK_TOLERANCE_SECONDS = int(os.environ.get("STRIPE_WEBHOOK_TOLERANCE_SECONDS", "300"))

# Map Stripe Price IDs -> Cutctx tiers
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
    """Constant-time Stripe webhook signature verification with replay tolerance."""
    if not STRIPE_WEBHOOK_SECRET:
        raise ValueError("STRIPE_WEBHOOK_SECRET not configured")
    parts: dict[str, str] = {}
    for item in sig_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip()] = value.strip()
    timestamp_raw = parts.get("t", "")
    v1 = parts.get("v1", "")
    if not timestamp_raw or not v1:
        return False
    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        return False
    now = int(time.time())
    if abs(now - timestamp) > STRIPE_WEBHOOK_TOLERANCE_SECONDS:
        logger.warning(
            "Stripe webhook signature rejected due to timestamp tolerance: now=%s ts=%s tolerance=%s",
            now,
            timestamp,
            STRIPE_WEBHOOK_TOLERANCE_SECONDS,
        )
        return False
    signed = f"{timestamp}.".encode() + payload
    expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


def generate_license_key(tier: str, customer_id: str) -> str:
    """Generate a signed license key.

    Format: {tier}-{random_id}-{hmac_signature}
    The proxy verifies the HMAC before accepting the tier prefix.
    """
    random_id = secrets.token_hex(8)
    secret = os.environ.get("CUTCTX_LICENSE_HMAC_SECRET", "")
    if not secret:
        raise ValueError("CUTCTX_LICENSE_HMAC_SECRET not set")
    payload = f"{tier}:{random_id}:{customer_id}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{tier}-{random_id}-{sig}"


def handle_checkout_completed(event_data: dict[str, Any]) -> LicenseRecord:
    """Handle Stripe checkout.session.completed event.

    SECURITY: The tier is derived from the Stripe Price ID (via
    PRICE_TO_TIER) — NOT from session.metadata.tier, which the client
    controls in the Stripe Checkout UI. Reading tier from metadata lets
    an attacker self-assign enterprise tier by manipulating the
    Checkout form's hidden field. Seat count is likewise derived from
    the matched line-item quantity; checkout metadata is never an
    authorization source.
    """
    session = event_data["object"]
    customer_id = session["customer"]
    subscription_id = session.get("subscription", "")
    email = session.get("customer_details", {}).get("email", "")

    tier, seats = _resolve_plan_from_session(session)

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


def _resolve_plan_from_session(session: dict[str, Any]) -> tuple[str, int]:
    """Resolve tier and seats from a trusted Stripe line item.

    Returns the first tier that matches a configured price ID on the
    session's line_items. Unknown or absent prices fail closed: issuing
    even the cheapest paid license without a verified purchase would
    still be an authorization bypass.

    NEVER trust session.metadata.tier — see handle_checkout_completed
    for the attack model.
    """
    line_items = session.get("line_items") or session.get("display_items") or []
    if isinstance(line_items, dict):
        # Some Stripe payloads nest line_items under a "data" key
        line_items = line_items.get("data", [])
    for item in line_items:
        if not isinstance(item, dict):
            continue
        price = item.get("price") or {}
        price_id = price.get("id") if isinstance(price, dict) else None
        if not price_id:
            continue
        tier = PRICE_TO_TIER.get(price_id)
        if tier:
            try:
                seats = int(item.get("quantity", 1))
            except (TypeError, ValueError) as exc:
                raise ValueError("Stripe line-item quantity must be an integer") from exc
            if seats < 1:
                raise ValueError("Stripe line-item quantity must be at least 1")
            return tier, seats
    raise ValueError(
        "Checkout session has no recognized Stripe price ID; "
        "configure STRIPE_PRICE_TEAM/BUSINESS/ENTERPRISE and expand line_items"
    )


def handle_subscription_deleted(event_data: dict[str, Any]) -> None:
    """Handle customer.subscription.deleted — deactivate license."""
    subscription = event_data["object"]
    sub_id = subscription["id"]
    if not _get_db().deactivate_subscription(sub_id):
        logger.warning("Subscription %s: no license record found during cancellation", sub_id)
        return
    logger.info("Subscription deactivated: %s", sub_id)


def handle_invoice_paid(event_data: dict[str, Any]) -> None:
    """Extend the matching subscription to Stripe's paid-through timestamp."""
    invoice = event_data["object"]
    subscription_id = invoice.get("subscription")
    if isinstance(subscription_id, dict):
        subscription_id = subscription_id.get("id")
    if not subscription_id:
        raise ValueError("Paid invoice is missing a subscription ID")

    period_end = invoice.get("period_end")
    if period_end is None:
        lines = invoice.get("lines", {}).get("data", [])
        period_ends = [
            item.get("period", {}).get("end")
            for item in lines
            if isinstance(item, dict) and isinstance(item.get("period"), dict)
        ]
        period_end = max((value for value in period_ends if value is not None), default=None)
    if period_end is None:
        raise ValueError("Paid invoice is missing a billing period end")

    if not _get_db().extend_subscription(str(subscription_id), float(period_end)):
        logger.warning("Subscription %s: no license record found during renewal", subscription_id)
        return
    logger.info("Subscription extended: %s through %s", subscription_id, period_end)


def handle_subscription_updated(event_data: dict[str, Any]) -> None:
    """Handle customer.subscription.updated — update tier/seats.

    Extracts the first matching price ID from the subscription items,
    resolves the tier from PRICE_TO_TIER, reads the seat count from
    the item quantity, and updates the corresponding license record.
    Unknown prices fail closed and leave the existing license unchanged.
    """
    subscription = event_data["object"]
    sub_id = subscription["id"]
    logger.info("Subscription updated: %s", sub_id)

    items = subscription.get("items", {}).get("data", [])
    tier: str | None = None
    seats: int = 5

    for item in items:
        if not isinstance(item, dict):
            continue
        price = item.get("price") or {}
        price_id = price.get("id") if isinstance(price, dict) else None
        if not price_id:
            continue
        resolved = PRICE_TO_TIER.get(price_id)
        if resolved:
            tier = resolved
            seats = int(item.get("quantity", 1))
            break

    if tier is None:
        raise ValueError(
            f"Subscription {sub_id} has no recognized Stripe price ID; refusing tier update"
        )

    db = _get_db()
    record = db.get_by_subscription_id(sub_id)
    if record is None:
        logger.warning("Subscription %s: no license record found, skipping update", sub_id)
        return

    record.tier = tier
    record.seats = seats
    db.upsert(record)
    logger.info("License %s updated: tier=%s, seats=%d", record.license_key, tier, seats)


def _get_db():
    """Shortcut to get the license DB singleton."""
    from cutctx.billing.license_db import get_license_db

    return get_license_db()


def _save_license(record: LicenseRecord) -> None:
    """Save to license DB."""
    from cutctx.billing.license_db import get_license_db

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
        handle_invoice_paid(data)
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
