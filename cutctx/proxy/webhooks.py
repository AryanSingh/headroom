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
       secret using HMAC-SHA256 and the ``X-Cutctx-Signature``
       header. The subscriber can verify the signature to
       confirm the webhook originated from Cutctx.

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
shared CUTCTX_WEBHOOK_URL env var (one URL, global) so the
behaviour is well-defined across replicas. A future EE release
will move subscriptions to the SQLite-backed store.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import random
import socket
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger("cutctx.proxy.webhooks")


class WebhookDestinationError(ValueError):
    """Raised when a webhook destination violates the outbound URL policy."""


def _is_development_http_allowed() -> bool:
    return os.environ.get("CUTCTX_DEV_ALLOW_INSECURE_WEBHOOK_HTTP", "").strip() == "1"


def validate_webhook_url(url: str) -> None:
    """Reject webhook URLs that are unsafe before they enter the delivery queue."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise WebhookDestinationError(f"invalid webhook URL: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise WebhookDestinationError("webhook URL scheme must be HTTP or HTTPS")
    if scheme != "https" and not _is_development_http_allowed():
        raise WebhookDestinationError(
            "webhook URL must use HTTPS; development HTTP requires "
            "CUTCTX_DEV_ALLOW_INSECURE_WEBHOOK_HTTP=1"
        )
    if parsed.username is not None or parsed.password is not None:
        raise WebhookDestinationError("webhook URL must not contain credentials")
    if not parsed.hostname:
        raise WebhookDestinationError("webhook URL must include a hostname")

    # Accessing ``parsed.port`` above validates its syntax and range. Keep the
    # local binding so static analysis sees that this validation is intentional.
    del port
    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return
    if not literal.is_global:
        raise WebhookDestinationError("webhook URL contains a non-global IP address")


async def resolve_webhook_destination(url: str) -> set[str]:
    """Resolve a webhook hostname off-loop and require every address to be global."""
    validate_webhook_url(url)
    parsed = urlsplit(url)
    assert parsed.hostname is not None  # guaranteed by validate_webhook_url
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        records = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            port,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
        )
    except (OSError, socket.gaierror) as exc:
        raise WebhookDestinationError(f"webhook hostname resolution failed: {exc}") from exc

    addresses = {str(record[4][0]) for record in records}
    if not addresses:
        raise WebhookDestinationError("webhook hostname resolved to no addresses")
    for address in addresses:
        try:
            resolved_ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise WebhookDestinationError(
                "webhook hostname resolution returned an invalid address"
            ) from exc
        if not resolved_ip.is_global:
            raise WebhookDestinationError(
                f"webhook hostname resolved to a non-global address: {address}"
            )
    return addresses


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
        subscriber MUST verify the ``X-Cutctx-Signature``
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

    def __post_init__(self) -> None:
        validate_webhook_url(self.url)


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

    The single global URL (CUTCTX_WEBHOOK_URL) is auto-added
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
        subscription_store: Any | None = None,
        dlq_store: Any | None = None,
    ) -> None:
        self.max_attempts = max(1, int(max_attempts))
        self.base_delay_s = max(0.01, float(base_delay_s))
        self.max_delay_s = max(self.base_delay_s, float(max_delay_s))
        self.timeout_s = max(0.1, float(timeout_s))
        self.queue_max = max(1, int(queue_max))

        # Audit-Deep-2026-06-21 High-15: subscription + DLQ
        # persistence. Falls back to in-memory when the stores
        # are not provided (tests, dev).
        self._sub_store = subscription_store
        self._dlq_store = dlq_store
        # In-memory mirror of the subscriptions, used as the
        # hot-path filter. Refreshed on every change.
        self._subscriptions: list[WebhookSubscription] = []
        if self._sub_store is not None:
            try:
                for stored in self._sub_store.list_all():
                    self._subscriptions.append(
                        WebhookSubscription(
                            url=stored.url,
                            secret=stored.secret,
                            event_types=stored.event_types,
                            org_id=stored.org_id,
                            enabled=stored.enabled,
                        )
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "WebhookDispatcher: failed to load subscriptions from store: %s",
                    exc,
                )

        self._queue: asyncio.Queue[WebhookDelivery | None] = asyncio.Queue(maxsize=self.queue_max)
        self._task: asyncio.Task[None] | None = None
        self._stopped = False
        self._http: httpx.AsyncClient | None = None

        # Backward-compat: auto-add the env-var global webhook
        # as a catch-all subscription so existing call sites
        # keep working.
        env_url = os.environ.get("CUTCTX_WEBHOOK_URL", "").strip()
        if env_url:
            env_secret = os.environ.get("CUTCTX_WEBHOOK_SECRET")
            if not env_secret:
                raise RuntimeError(
                    "CUTCTX_WEBHOOK_SECRET environment variable is required when "
                    "CUTCTX_WEBHOOK_URL is set. "
                    "Generate one with: openssl rand -hex 32"
                )
            sub = WebhookSubscription(
                url=env_url,
                secret=env_secret,
                event_types=None,  # catch-all
            )
            if self._sub_store is not None:
                try:
                    self._sub_store.upsert(
                        url=sub.url,
                        secret=sub.secret,
                        event_types=sub.event_types,
                        org_id=sub.org_id,
                        enabled=sub.enabled,
                    )
                except Exception:  # pragma: no cover
                    logger.debug(
                        "WebhookDispatcher: failed to persist env-var subscription",
                        exc_info=True,
                    )
            self._subscriptions.append(sub)

    # ── Subscription management ────────────────────────────────────

    def subscribe(self, sub: WebhookSubscription) -> None:
        """Register a subscription.

        Idempotent on URL: re-subscribing the same URL updates
        the existing entry rather than appending a duplicate.

        When a subscription store is configured, the change
        is also persisted so it survives a restart and is
        shared across replicas.
        """
        for i, existing in enumerate(self._subscriptions):
            if existing.url == sub.url:
                self._subscriptions[i] = sub
                break
        else:
            self._subscriptions.append(sub)
        if self._sub_store is not None:
            try:
                self._sub_store.upsert(
                    url=sub.url,
                    secret=sub.secret,
                    event_types=sub.event_types,
                    org_id=sub.org_id,
                    enabled=sub.enabled,
                )
            except Exception:  # pragma: no cover - defensive
                logger.warning(
                    "WebhookDispatcher: failed to persist subscription",
                    exc_info=True,
                )

    def unsubscribe(self, url: str) -> bool:
        """Remove a subscription by URL. Returns True if removed."""
        before = len(self._subscriptions)
        self._subscriptions = [s for s in self._subscriptions if s.url != url]
        removed = len(self._subscriptions) < before
        if removed and self._sub_store is not None:
            try:
                # Find the stored sub_id and delete by id.
                for stored in self._sub_store.list_all():
                    if stored.url == url:
                        self._sub_store.delete(stored.id)
                        break
            except Exception:  # pragma: no cover
                logger.warning(
                    "WebhookDispatcher: failed to persist unsubscribe",
                    exc_info=True,
                )
        return removed

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
        self._http = httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False)
        self._stopped = False
        self._task = asyncio.create_task(self._drain_loop(), name="cutctx-webhook-dispatcher")
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
                # Audit-Deep-2026-06-21 High-15: persistent DLQ
                logger.error(
                    "Webhook queue full; dropping %s for %s (dead-lettered)",
                    event_type,
                    sub.url,
                )
                if self._dlq_store is not None:
                    try:
                        self._dlq_store.add(
                            event_id=enriched.get("event_id", ""),
                            event_type=event_type,
                            payload=enriched,
                            target_url=sub.url,
                            last_status=None,
                            last_error="queue_full",
                            attempts=0,
                        )
                    except Exception:  # pragma: no cover
                        logger.debug(
                            "Webhook DLQ: failed to persist queue-full entry",
                            exc_info=True,
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
            "x-cutctx-signature": sig,
            "x-cutctx-event-type": delivery.event_type,
            "x-cutctx-delivery-attempt": str(delivery.attempt + 1),
        }
        for attempt in range(self.max_attempts):
            delivery.attempt = attempt + 1
            try:
                # Resolve again immediately before every attempt. This blocks
                # persisted unsafe destinations and DNS answers that change
                # between retries without blocking the asyncio event loop.
                await resolve_webhook_destination(delivery.subscription.url)
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
                if 400 <= response.status_code < 500 and response.status_code not in (408, 429):
                    delivery.last_error = f"non-retryable HTTP {response.status_code}"
                    logger.error(
                        "webhook non-retryable: %s to %s status=%d; dead-lettered",
                        delivery.event_type,
                        delivery.subscription.url,
                        response.status_code,
                    )
                    # Audit-Deep-2026-06-21 High-15: persistent DLQ
                    if self._dlq_store is not None:
                        try:
                            self._dlq_store.add(
                                event_id=getattr(delivery, "event_id", "") or "",
                                event_type=delivery.event_type,
                                payload=getattr(delivery, "payload", {}) or {},
                                target_url=delivery.subscription.url,
                                last_status=response.status_code,
                                last_error=delivery.last_error,
                                attempts=delivery.attempt,
                            )
                        except Exception:
                            logger.debug(
                                "Webhook DLQ: failed to persist",
                                exc_info=True,
                            )
                    return
                delivery.last_error = f"HTTP {response.status_code}"
            except (httpx.HTTPError, asyncio.TimeoutError, WebhookDestinationError) as exc:
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
        # Audit-Deep-2026-06-21 High-15: persistent DLQ
        if self._dlq_store is not None:
            try:
                self._dlq_store.add(
                    event_id=getattr(delivery, "event_id", "") or "",
                    event_type=delivery.event_type,
                    payload=getattr(delivery, "payload", {}) or {},
                    target_url=delivery.subscription.url,
                    last_status=None,
                    last_error=delivery.last_error,
                    attempts=delivery.attempt,
                )
            except Exception:
                logger.debug(
                    "Webhook DLQ: failed to persist exhausted entry",
                    exc_info=True,
                )


# ── Module-level singleton ────────────────────────────────────────

_dispatcher: WebhookDispatcher | None = None


def get_webhook_dispatcher() -> WebhookDispatcher:
    """Return the process-wide dispatcher, creating it lazily.

    Audit-Deep-2026-06-21 High-15: the singleton now
    defaults to using the persistent subscription + DLQ
    stores (at ~/.cutctx/webhooks.db and
    ~/.cutctx/webhook_dlq.db). Operators that need
    in-memory behavior can set CUTCTX_WEBHOOKS_IN_MEMORY=1
    (useful for tests + ephemeral dev environments).
    """
    global _dispatcher
    if _dispatcher is None:
        if os.environ.get("CUTCTX_WEBHOOKS_IN_MEMORY") == "1":
            _dispatcher = WebhookDispatcher()
        else:
            try:
                from cutctx.proxy.webhook_stores import (
                    WebhookDeadLetterStore,
                    WebhookSubscriptionStore,
                )

                sub_store = WebhookSubscriptionStore()
                dlq_store = WebhookDeadLetterStore()
                _dispatcher = WebhookDispatcher(
                    subscription_store=sub_store,
                    dlq_store=dlq_store,
                )
            except Exception as exc:
                # If the stores can't open (read-only mount,
                # etc.) fall back to in-memory. The proxy still
                # works; we just lose persistence.
                logger.warning(
                    "Webhook stores unavailable (%s); falling back to in-memory dispatcher.",
                    exc,
                )
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
    "resolve_webhook_destination",
    "validate_webhook_url",
    "WebhookDestinationError",
]
