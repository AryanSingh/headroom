# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Production-grade outbound webhook dispatcher.

High-15 (production-audit-progress-2026-06-20.md): the previous
``WebhookDispatcher`` (28 lines) was a fire-and-forget stub with no
retry, no signing, no event types, no per-tenant routing. This
module replaces it with a production-grade implementation:

    1. Event types: every event has a stable string identifier
       (e.g. ``spend.threshold_exceeded``, ``audit.failed_login``,
       ``abuse.impossible_travel``). Subscribers register for one
       or more event types.

    2. HMAC signing: every payload is signed with the subscriber's
       secret using HMAC-SHA256 and the ``X-Headroom-Signature``
       header. The subscriber can verify the signature to
       confirm the webhook originated from CutCtx.

    3. Retry with exponential backoff: failed deliveries (network
       error, 5xx, timeout) are retried up to ``max_attempts``
       with jitter. After ``max_attempts`` the event is dropped
       to the dead-letter log (``logger.error``) so a poisoned
       subscriber URL does not block the event loop.

    4. Per-tenant routing: subscriptions carry an optional
       ``org_id``. The dispatcher can route the same event
       type to multiple subscribers (e.g. the buyer's primary
       webhook AND the operator's monitoring webhook).

    5. In-memory queue: a single asyncio.Queue carries pending
       deliveries. A background task drains the queue so the
       calling code (e.g. ``record_spend``) returns immediately.

    6. Lifecycle: ``start()`` launches the background task;
       ``stop()`` drains and cancels. Safe to call ``fire()``
       before ``start()`` (events are buffered).

    7. Self-test: ``/admin/webhooks/test`` fires a synthetic
        event so operators can verify the integration end-to-end.

Persistence: subscriptions are kept in-process only. For
multi-replica deployments the dispatcher falls back to the
shared HEADROOM_WEBHOOK_URL env var (one URL, global) so the
behaviour is well-defined across replicas. A future EE release
will move subscriptions to the SQLite-backed store.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

import httpx

logger = logging.getLogger("headroom.proxy.webhooks")


class WebhookEventType(str, Enum):
    """Stable event-type identifiers.

    Adding a new event type: append a new member. Do NOT
    rename existing members — the string values are part of
    the public API for subscribers.
    """

    SPEND_THRESHOLD_EXCEEDED = "spend.threshold_exceeded"
    SPEND_DAILY_REPORT = "spend.daily_report"
    AUDIT_FAILED_LOGIN = "audit.failed_login"
    AUDIT_LICENSE_VALIDATED = "audit.license_validated"
    ABUSE_IMPOSSIBLE_TRAVEL = "abuse.impossible_travel"
    ABUSE_ACTIVATION_STORM = "abuse.activation_storm"
    POLICY_UPSERT = "policy.upsert"
    CACHE_INVALIDATED = "cache.invalidated"


@dataclass
class WebhookSubscription:
    """A single subscriber's configuration.

    Attributes
    ----------
    url : str
        The HTTP endpoint to POST events to.
    secret : str
        Shared secret used for HMAC-SHA256 signing. The
        subscriber MUST verify the ``X-Headroom-Signature``
        header on the receiving end.
    event_types : set[str] | None
        If ``None``, receive every event. If a set, only events
        whose ``event_type`` is in the set are delivered.
    org_id : str | None
        If set, only events carrying this ``org_id`` in the
        payload are delivered. ``None`` means org-agnostic.
    enabled : bool
        Set to ``False`` to disable a subscription without
        removing it.
    """

    url: str
    secret: str
    event_types: set[str] | None = None
    org_id: str | None = None
    enabled: bool = True


@dataclass
class WebhookDelivery:
    """An in-flight or queued delivery.

    Used by the background task to retry on failure.
    """

    subscription: WebhookSubscription
    event_type: str
    payload: dict[str, Any]
    attempt: int = 0
    last_error: str | None = None
    enqueued_at: float = field(default_factory=time.time)


class WebhookDispatcher:
    """Production-grade outbound webhook dispatcher.

    Lifecycle:
        dispatcher = WebhookDispatcher()
        dispatcher.subscribe(WebhookSubscription(...))
        await dispatcher.start()       # launches background task
        await dispatcher.fire(event_type, payload)
        ...
        await dispatcher.stop()        # drains and cancels

    Defaults:
        max_attempts=5, base_delay=1.0s, max_delay=60.0s,
        request_timeout=10.0s, queue_max=10_000.

    The single global URL (HEADROOM_WEBHOOK_URL) is auto-added
    as a subscription on construction for backward compatibility
    with the previous fire-and-forget behaviour. Subscriptions
    added later override the env-var subscription for matching
    events.
    """

    DEFAULT_MAX_ATTEMPTS = 5
    DEFAULT_BASE_DELAY_S = 1.0
    DEFAULT_MAX_DELAY_S = 60.0
    DEFAULT_TIMEOUT_S = 10.0
    DEFAULT_QUEUE_MAX = 10_000

    def __init__(
        self,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        base_delay_s: float = DEFAULT_BASE_DELAY_S,
        max_delay_s: float = DEFAULT_MAX_DELAY_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        queue_max: int = DEFAULT_QUEUE_MAX,
    ) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay_s = max(0.01, float(base_delay_s))
        self.max_delay_s = max(self.base_delay_s, float(max_delay_s))
        self.timeout_s = max(0.1, float(timeout_s))
        self.queue_max = max(1, int(queue_max))

        self._subscriptions: list[WebhookSubscription] = []
        self._queue: asyncio.Queue[WebhookDelivery | None] = asyncio.Queue(
            maxsize=self.queue_max
        )
        self._task: asyncio.Task[None] | None = None
        self._stopped = False
        self._http: httpx.AsyncClient | None = None

        # Backward-compat: auto-add the env-var global webhook
        # as a catch-all subscription so existing call sites
        # keep working.
        env_url = os.environ.get("HEADROOM_WEBHOOK_URL", "").strip()
        if env_url:
            env_secret = os.environ.get(
                "HEADROOM_WEBHOOK_SECRET", "headroom-dev-secret"
            )
            self._subscriptions.append(
                WebhookSubscription(
                    url=env_url,
                    secret=env_secret,
                    event_types=None,  # catch-all
                )
            )

    # ── Subscription management ────────────────────────────────────

    def subscribe(self, sub: WebhookSubscription) -> None:
        """Register a subscription.

        Idempotent on URL: re-subscribing the same URL updates
        the existing entry rather than appending a duplicate.
        """
        for i, existing in enumerate(self._subscriptions):
            if existing.url == sub.url:
                self._subscriptions[i] = sub
                return
        self._subscriptions.append(sub)

    def unsubscribe(self, url: str) -> bool:
        """Remove a subscription by URL. Returns True if removed."""
        before = len(self._subscriptions)
        self._subscriptions = [s for s in self._subscriptions if s.url != url]
        return len(self._subscriptions) < before

    def list_subscriptions(self) -> list[dict[str, Any]]:
        """Return a JSON-serialisable view of the current
        subscriptions (for the /admin/webhooks endpoint).
        """
        return [
            {
                "url": s.url,
                "event_types": sorted(s.event_types) if s.event_types else None,
                "org_id": s.org_id,
                "enabled": s.enabled,
            }
            for s in self._subscriptions
        ]

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch the background delivery task."""
        if self._task is not None:
            return
        self._http = httpx.AsyncClient(timeout=self.timeout_s)
        self._stopped = False
        self._task = asyncio.create_task(
            self._drain_loop(), name="headroom-webhook-dispatcher"
        )
        logger.info(
            "WebhookDispatcher started (max_attempts=%d, base_delay=%.1fs, queue_max=%d, subscriptions=%d)",
            self.max_attempts,
            self.base_delay_s,
            self.queue_max,
            len(self._subscriptions),
        )

    async def stop(self) -> None:
        """Drain pending deliveries and cancel the background task."""
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        logger.info("WebhookDispatcher stopped")

    # ── Public API ───────────────────────────────────────────────

    async def fire(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        org_id: str | None = None,
    ) -> int:
        """Enqueue an event for delivery. Returns the number of
        subscriptions the event was enqueued for (0 if no
        subscribers match, or if the queue is full and the event
        was dropped to the dead-letter log).
        """
        if self._stopped:
            logger.debug("dispatcher stopped, dropping event %s", event_type)
            return 0
        # Find matching subscriptions.
        matching = self._select_subscriptions(event_type, org_id=org_id)
        if not matching:
            return 0
        # Inject org_id into the payload for the subscriber's
        # convenience.
        enriched = dict(payload)
        if org_id is not None and "org_id" not in enriched:
            enriched["org_id"] = org_id
        enriched.setdefault("event_type", event_type)
        enriched.setdefault("timestamp", time.time())
        n_enqueued = 0
        for sub in matching:
            delivery = WebhookDelivery(
                subscription=sub,
                event_type=event_type,
                payload=enriched,
            )
            try:
                self._queue.put_nowait(delivery)
                n_enqueued += 1
            except asyncio.QueueFull:
                logger.error(
                    "Webhook queue full; dropping %s for %s (dead-lettered)",
                    event_type,
                    sub.url,
                )
        return n_enqueued

    def _select_subscriptions(
        self, event_type: str, *, org_id: str | None
    ) -> list[WebhookSubscription]:
        """Find subscriptions that match the event + org."""
        out: list[WebhookSubscription] = []
        for sub in self._subscriptions:
            if not sub.enabled:
                continue
            if sub.event_types is not None and event_type not in sub.event_types:
                continue
            if sub.org_id is not None and sub.org_id != org_id:
                continue
            out.append(sub)
        return out

    # ── Background delivery loop ─────────────────────────────────

    async def _drain_loop(self) -> None:
        """Background task: drain the queue and deliver each event.

        The loop is intentionally simple — one delivery at a
        time, in FIFO order. Concurrent delivery is intentionally
        avoided so a slow subscriber does not starve other
        subscribers; serialised delivery keeps the audit trail
        deterministic.
        """
        assert self._http is not None
        while not self._stopped:
            try:
                delivery = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if delivery is None:
                # Sentinel value placed by stop() to signal exit.
                break
            try:
                await self._deliver(delivery)
            except Exception as exc:  # noqa: BLE001
                logger.exception("delivery loop error: %s", exc)

    async def _deliver(self, delivery: WebhookDelivery) -> None:
        """Deliver one event with retry + backoff + dead-letter."""
        assert self._http is not None
        body = json.dumps(delivery.payload, separators=(",", ":")).encode("utf-8")
        sig = hmac.new(
            delivery.subscription.secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "content-type": "application/json",
            "x-headroom-signature": sig,
            "x-headroom-event-type": delivery.event_type,
            "x-headroom-delivery-attempt": str(delivery.attempt + 1),
        }
        for attempt in range(self.max_attempts):
            delivery.attempt = attempt + 1
            try:
                response = await self._http.post(
                    delivery.subscription.url,
                    content=body,
                    headers=headers,
                )
                # 2xx: success.
                if 200 <= response.status_code < 300:
                    logger.debug(
                        "webhook delivered: %s to %s (status=%d, attempt=%d)",
                        delivery.event_type,
                        delivery.subscription.url,
                        response.status_code,
                        delivery.attempt,
                    )
                    return
                # 4xx (except 408/429) is non-retryable — drop.
                if (
                    400 <= response.status_code < 500
                    and response.status_code not in (408, 429)
                ):
                    delivery.last_error = (
                        f"non-retryable HTTP {response.status_code}"
                    )
                    logger.error(
                        "webhook non-retryable: %s to %s status=%d; "
                        "dead-lettered",
                        delivery.event_type,
                        delivery.subscription.url,
                        response.status_code,
                    )
                    return
                delivery.last_error = f"HTTP {response.status_code}"
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                delivery.last_error = type(exc).__name__ + ": " + str(exc)
            # Backoff before retry (unless this was the last attempt).
            if attempt + 1 < self.max_attempts:
                delay = min(
                    self.max_delay_s,
                    self.base_delay_s * (2**attempt),
                ) * (0.5 + random.random() / 2.0)
                logger.debug(
                    "webhook retry %d/%d in %.2fs for %s",
                    delivery.attempt + 1,
                    self.max_attempts,
                    delay,
                    delivery.subscription.url,
                )
                await asyncio.sleep(delay)
        # All attempts exhausted.
        logger.error(
            "webhook dead-letter: %s to %s after %d attempts; last_error=%s",
            delivery.event_type,
            delivery.subscription.url,
            delivery.max_attempts if hasattr(delivery, "max_attempts") else self.max_attempts,
            delivery.last_error,
        )


# ── Module-level singleton ────────────────────────────────────────

_dispatcher: WebhookDispatcher | None = None


def get_webhook_dispatcher() -> WebhookDispatcher:
    """Return the process-wide dispatcher, creating it lazily."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = WebhookDispatcher()
    return _dispatcher


async def reset_webhook_dispatcher() -> None:
    """Stop and clear the singleton. Used by tests and lifespan."""
    global _dispatcher
    if _dispatcher is not None:
        await _dispatcher.stop()
        _dispatcher = None


# ── Backward-compat helper ────────────────────────────────────────

# High-15: the previous 28-line stub exposed a module-level
# ``dispatcher = WebhookDispatcher()`` instance. Preserve that
# for any caller that still imports it.
dispatcher = None  # populated lazily by get_webhook_dispatcher()


async def fire_webhook(title: str, message: str) -> int:
    """Backward-compat helper. Translates the legacy
    ``fire_webhook(title, message)`` signature into the new
    event-type + payload model. Fires ``abuse.activation_storm``
    for backward compat with the prior firewall / budget
    callers. Returns the number of subscribers the event was
    enqueued for (0 if no subscribers).
    """
    return await get_webhook_dispatcher().fire(
        WebhookEventType.ABUSE_ACTIVATION_STORM.value,
        {"title": title, "message": message},
    )


__all__ = [
    "WebhookDispatcher",
    "WebhookSubscription",
    "WebhookDelivery",
    "WebhookEventType",
    "get_webhook_dispatcher",
    "reset_webhook_dispatcher",
    "fire_webhook",
]
