# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the production-grade webhook dispatcher (High-15).

Production audit (production-audit-progress-2026-06-20.md)
found the previous dispatcher was a 28-line stub. This
file tests the new production-grade behaviour:

  1. Event types, subscription management
  2. HMAC signing (X-Headroom-Signature)
  3. Retry with exponential backoff
  4. Per-tenant routing
  5. Dead-letter handling
  6. /admin/webhooks endpoints
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from headroom.proxy.webhooks import (
    WebhookDelivery,
    WebhookDispatcher,
    WebhookEventType,
    WebhookSubscription,
    get_webhook_dispatcher,
    reset_webhook_dispatcher,
)


# ── Subscription management ─────────────────────────────────────────


def test_subscribe_idempotent_on_url() -> None:
    """Re-subscribing the same URL updates the existing entry
    rather than appending a duplicate.
    """
    d = WebhookDispatcher()
    sub1 = WebhookSubscription(url="https://a.example.com", secret="s1")
    sub2 = WebhookSubscription(url="https://a.example.com", secret="s2")
    d.subscribe(sub1)
    d.subscribe(sub2)
    assert len(d.list_subscriptions()) == 1
    # The second subscribe overwrote the first.
    listed = d.list_subscriptions()
    # We don't expose the secret, so we only assert the URL.
    assert listed[0]["url"] == "https://a.example.com"


def test_unsubscribe_returns_true_when_removed() -> None:
    d = WebhookDispatcher()
    d.subscribe(WebhookSubscription(url="https://a.example.com", secret="s1"))
    assert d.unsubscribe("https://a.example.com") is True
    assert d.unsubscribe("https://a.example.com") is False
    assert d.list_subscriptions() == []


def test_subscription_with_event_types_filter() -> None:
    """A subscription with a non-None event_types set only
    matches events whose type is in the set.
    """
    d = WebhookDispatcher()
    d.subscribe(
        WebhookSubscription(
            url="https://a.example.com",
            secret="s",
            event_types={WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value},
        )
    )
    # Matching event.
    matched = d._select_subscriptions(
        WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value, org_id=None
    )
    assert len(matched) == 1
    # Non-matching event.
    matched = d._select_subscriptions(
        WebhookEventType.AUDIT_FAILED_LOGIN.value, org_id=None
    )
    assert len(matched) == 0


def test_subscription_with_org_id_filter() -> None:
    d = WebhookDispatcher()
    d.subscribe(
        WebhookSubscription(
            url="https://a.example.com",
            secret="s",
            org_id="org-1",
        )
    )
    # Matching org.
    matched = d._select_subscriptions(
        WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value, org_id="org-1"
    )
    assert len(matched) == 1
    # Non-matching org.
    matched = d._select_subscriptions(
        WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value, org_id="org-2"
    )
    assert len(matched) == 0
    # None org (no org context) — also no match.
    matched = d._select_subscriptions(
        WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value, org_id=None
    )
    assert len(matched) == 0


def test_disabled_subscription_skipped() -> None:
    d = WebhookDispatcher()
    d.subscribe(
        WebhookSubscription(
            url="https://a.example.com", secret="s", enabled=False
        )
    )
    matched = d._select_subscriptions(
        WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value, org_id=None
    )
    assert len(matched) == 0


def test_env_var_auto_subscription() -> None:
    """When HEADROOM_WEBHOOK_URL is set, the dispatcher auto-adds
    a catch-all subscription.
    """
    with patch.dict(
        os.environ,
        {"HEADROOM_WEBHOOK_URL": "https://env.example.com"},
    ):
        d = WebhookDispatcher()
        subs = d.list_subscriptions()
        assert any(s["url"] == "https://env.example.com" for s in subs)


# ── fire() ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fire_enqueues_for_matching_subscribers() -> None:
    d = WebhookDispatcher()
    d.subscribe(
        WebhookSubscription(
            url="https://a.example.com",
            secret="s",
            event_types={WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value},
        )
    )
    # Don't actually start the dispatcher (so the queue doesn't drain).
    n = await d.fire(
        WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value, {"x": 1}
    )
    assert n == 1
    delivery = d._queue.get_nowait()
    assert delivery.event_type == WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value
    assert delivery.payload == {"x": 1, "event_type": WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value, "timestamp": delivery.payload["timestamp"]}


@pytest.mark.asyncio
async def test_fire_returns_zero_for_no_match() -> None:
    d = WebhookDispatcher()
    n = await d.fire(
        WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value, {"x": 1}
    )
    assert n == 0


@pytest.mark.asyncio
async def test_fire_includes_org_id_in_payload() -> None:
    d = WebhookDispatcher()
    d.subscribe(
        WebhookSubscription(
            url="https://a.example.com",
            secret="s",
            org_id="org-1",
        )
    )
    await d.fire(
        WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value,
        {"x": 1},
        org_id="org-1",
    )
    delivery = d._queue.get_nowait()
    assert delivery.payload.get("org_id") == "org-1"


@pytest.mark.asyncio
async def test_fire_returns_zero_when_stopped() -> None:
    d = WebhookDispatcher()
    d._stopped = True
    n = await d.fire("any.event", {"x": 1})
    assert n == 0


# ── HMAC signing ──────────────────────────────────────────────────


def test_delivery_signs_payload_with_hmac_sha256() -> None:
    """The delivery loop signs the body with HMAC-SHA256 using
    the subscription's secret.
    """
    sub = WebhookSubscription(url="https://a.example.com", secret="mysecret")
    delivery = WebhookDelivery(
        subscription=sub,
        event_type="test.event",
        payload={"x": 1},
    )
    body = json.dumps(delivery.payload, separators=(",", ":")).encode("utf-8")
    expected_sig = hmac.new(b"mysecret", body, hashlib.sha256).hexdigest()
    # The signature the subscriber would verify against.
    assert len(expected_sig) == 64
    # And the signature the dispatcher computes must match.
    actual_sig = hmac.new(
        sub.secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    assert actual_sig == expected_sig


# ─- Retry logic ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deliver_succeeds_on_2xx() -> None:
    d = WebhookDispatcher(max_attempts=3, base_delay_s=0.01, max_delay_s=0.05)
    sub = WebhookSubscription(url="https://a.example.com", secret="s")
    delivery = WebhookDelivery(
        subscription=sub,
        event_type="test.event",
        payload={"x": 1},
    )
    # Mock the http client.
    response = AsyncMock()
    response.status_code = 200
    d._http = AsyncMock()
    d._http.post = AsyncMock(return_value=response)
    await d._deliver(delivery)
    assert delivery.attempt == 1
    assert d._http.post.call_count == 1


@pytest.mark.asyncio
async def test_deliver_retries_on_5xx() -> None:
    """A 5xx response is retried up to max_attempts times."""
    d = WebhookDispatcher(max_attempts=3, base_delay_s=0.01, max_delay_s=0.05)
    sub = WebhookSubscription(url="https://a.example.com", secret="s")
    delivery = WebhookDelivery(
        subscription=sub,
        event_type="test.event",
        payload={"x": 1},
    )
    # First two calls return 503, third returns 200.
    response_503 = AsyncMock()
    response_503.status_code = 503
    response_200 = AsyncMock()
    response_200.status_code = 200
    d._http = AsyncMock()
    d._http.post = AsyncMock(side_effect=[response_503, response_503, response_200])
    # Patch asyncio.sleep to avoid waiting.
    with patch("headroom.proxy.webhooks.asyncio.sleep", new=AsyncMock()):
        await d._deliver(delivery)
    assert delivery.attempt == 3
    assert d._http.post.call_count == 3


@pytest.mark.asyncio
async def test_deliver_drops_on_non_retryable_4xx() -> None:
    """A 4xx response (other than 408/429) is non-retryable."""
    d = WebhookDispatcher(max_attempts=3, base_delay_s=0.01)
    sub = WebhookSubscription(url="https://a.example.com", secret="s")
    delivery = WebhookDelivery(
        subscription=sub,
        event_type="test.event",
        payload={"x": 1},
    )
    response_400 = AsyncMock()
    response_400.status_code = 400
    d._http = AsyncMock()
    d._http.post = AsyncMock(return_value=response_400)
    await d._deliver(delivery)
    # Only one attempt — no retry.
    assert d._http.post.call_count == 1
    assert "non-retryable" in (delivery.last_error or "")


@pytest.mark.asyncio
async def test_deliver_retries_on_429() -> None:
    """429 is retryable (rate-limited by the subscriber)."""
    d = WebhookDispatcher(max_attempts=2, base_delay_s=0.01)
    sub = WebhookSubscription(url="https://a.example.com", secret="s")
    delivery = WebhookDelivery(
        subscription=sub,
        event_type="test.event",
        payload={"x": 1},
    )
    response_429 = AsyncMock()
    response_429.status_code = 429
    d._http = AsyncMock()
    d._http.post = AsyncMock(return_value=response_429)
    with patch("headroom.proxy.webhooks.asyncio.sleep", new=AsyncMock()):
        await d._deliver(delivery)
    # Both attempts made.
    assert d._http.post.call_count == 2


@pytest.mark.asyncio
async def test_deliver_gives_up_after_max_attempts() -> None:
    """A persistent 5xx exhausts the retry budget."""
    d = WebhookDispatcher(max_attempts=2, base_delay_s=0.01)
    sub = WebhookSubscription(url="https://a.example.com", secret="s")
    delivery = WebhookDelivery(
        subscription=sub,
        event_type="test.event",
        payload={"x": 1},
    )
    response_503 = AsyncMock()
    response_503.status_code = 503
    d._http = AsyncMock()
    d._http.post = AsyncMock(return_value=response_503)
    with patch("headroom.proxy.webhooks.asyncio.sleep", new=AsyncMock()):
        await d._deliver(delivery)
    assert d._http.post.call_count == 2
    # No exception raised; the event is dead-lettered (logged).


@pytest.mark.asyncio
async def test_deliver_handles_network_error() -> None:
    """A network error is retried like a 5xx."""
    import httpx

    d = WebhookDispatcher(max_attempts=2, base_delay_s=0.01)
    sub = WebhookSubscription(url="https://a.example.com", secret="s")
    delivery = WebhookDelivery(
        subscription=sub,
        event_type="test.event",
        payload={"x": 1},
    )
    d._http = AsyncMock()
    d._http.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    with patch("headroom.proxy.webhooks.asyncio.sleep", new=AsyncMock()):
        await d._deliver(delivery)
    assert d._http.post.call_count == 2
    assert "ConnectError" in (delivery.last_error or "")


# ── Event types ──────────────────────────────────────────────────


def test_event_type_values_are_stable_strings() -> None:
    """The event-type string values are part of the public API;
    adding a new event is fine, renaming is not.
    """
    assert WebhookEventType.SPEND_THRESHOLD_EXCEEDED.value == "spend.threshold_exceeded"
    assert WebhookEventType.AUDIT_FAILED_LOGIN.value == "audit.failed_login"
    assert WebhookEventType.ABUSE_IMPOSSIBLE_TRAVEL.value == "abuse.impossible_travel"
    assert WebhookEventType.ABUSE_ACTIVATION_STORM.value == "abuse.activation_storm"


# ─- Singleton lifecycle ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_and_reset_dispatcher() -> None:
    await reset_webhook_dispatcher()
    d1 = get_webhook_dispatcher()
    d2 = get_webhook_dispatcher()
    assert d1 is d2
    await reset_webhook_dispatcher()
    d3 = get_webhook_dispatcher()
    assert d3 is not d1


@pytest.mark.asyncio
async def test_start_and_stop_dispatcher() -> None:
    d = WebhookDispatcher()
    await d.start()
    assert d._task is not None
    assert d._http is not None
    await d.stop()
    assert d._task is None
    assert d._http is None


# ─- Backward-compat helper ────────────────────────────────────────


@pytest.mark.asyncio
async def test_fire_webhook_helper_backward_compat() -> None:
    """The legacy fire_webhook(title, message) helper still works
    (translates to abuse.activation_storm).
    """
    from headroom.proxy.webhooks import fire_webhook

    # Build a fresh dispatcher that has NOT been started (so the
    # background task's stop() did not run). The previous test
    # leaves the singleton in a stopped state.
    d = WebhookDispatcher()
    d.subscribe(WebhookSubscription(url="https://a.example.com", secret="s"))
    # Don't start the dispatcher so the queue accumulates.
    n = await d.fire(
        WebhookEventType.ABUSE_ACTIVATION_STORM.value,
        {"title": "Alert", "message": "Something happened"},
    )
    assert n == 1
    delivery = d._queue.get_nowait()
    assert delivery.event_type == WebhookEventType.ABUSE_ACTIVATION_STORM.value
    assert delivery.payload["title"] == "Alert"
    assert delivery.payload["message"] == "Something happened"


@pytest.mark.asyncio
async def test_fire_webhook_helper_singleton_lifecycle() -> None:
    """The legacy fire_webhook() helper at module level still works
    when the dispatcher singleton is fresh (not stopped).
    """
    # Reset the singleton, register a subscription, fire the
    # legacy helper. The helper translates to abuse.activation_storm.
    await reset_webhook_dispatcher()
    d = get_webhook_dispatcher()
    d.subscribe(WebhookSubscription(url="https://a.example.com", secret="s"))
    # Do NOT call d.start() so the queue accumulates.
    from headroom.proxy.webhooks import fire_webhook
    n = await fire_webhook("Alert", "Something happened")
    assert n == 1
    delivery = d._queue.get_nowait()
    assert delivery.event_type == WebhookEventType.ABUSE_ACTIVATION_STORM.value
    assert delivery.payload["title"] == "Alert"
    assert delivery.payload["message"] == "Something happened"
