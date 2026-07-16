from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from cutctx.proxy.routes.admin import WebhookSubscriptionInput
from cutctx.proxy.webhooks import (
    WebhookDelivery,
    WebhookDestinationError,
    WebhookDispatcher,
    WebhookSubscription,
    resolve_webhook_destination,
    validate_webhook_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://hooks.example.com/event",
        "https://user:password@hooks.example.com/event",
        "https://127.0.0.1/event",
        "https://10.0.0.7/event",
        "https://169.254.169.254/latest/meta-data",
        "https://192.0.2.1/event",
        "https://[::1]/event",
    ],
)
def test_webhook_url_policy_rejects_unsafe_destinations(url: str) -> None:
    with pytest.raises(WebhookDestinationError):
        validate_webhook_url(url)


def test_webhook_url_policy_requires_https_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CUTCTX_DEV_ALLOW_INSECURE_WEBHOOK_HTTP", raising=False)

    with pytest.raises(WebhookDestinationError, match="HTTPS"):
        validate_webhook_url("http://hooks.example.com/event")


def test_development_http_requires_narrow_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUTCTX_DEV_ALLOW_INSECURE_WEBHOOK_HTTP", "1")

    validate_webhook_url("http://hooks.example.com/event")


def test_admin_schema_rejects_unsafe_webhook_url() -> None:
    with pytest.raises(ValidationError):
        WebhookSubscriptionInput(
            url="https://127.0.0.1/internal",
            secret="long-enough-secret",
        )


@pytest.mark.asyncio
async def test_dns_resolution_runs_off_event_loop_and_rejects_non_global_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", 443)),
    ]
    to_thread = AsyncMock(return_value=resolved)
    monkeypatch.setattr(asyncio, "to_thread", to_thread)

    with pytest.raises(WebhookDestinationError, match="non-global"):
        await resolve_webhook_destination("https://hooks.example.com/event")

    to_thread.assert_awaited_once()


@pytest.mark.asyncio
async def test_delivery_revalidates_dns_before_each_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher = WebhookDispatcher(max_attempts=2, base_delay_s=0.01)
    delivery = WebhookDelivery(
        subscription=WebhookSubscription(
            url="https://hooks.example.com/event",
            secret="secret",
        ),
        event_type="test.event",
        payload={"ok": True},
    )
    response = AsyncMock(status_code=503)
    dispatcher._http = AsyncMock()
    dispatcher._http.post = AsyncMock(return_value=response)
    resolver = AsyncMock(
        side_effect=[
            {"93.184.216.34"},
            WebhookDestinationError("destination resolved to a non-global address"),
        ]
    )
    monkeypatch.setattr("cutctx.proxy.webhooks.resolve_webhook_destination", resolver)
    monkeypatch.setattr("cutctx.proxy.webhooks.asyncio.sleep", AsyncMock())

    await dispatcher._deliver(delivery)

    assert resolver.await_count == 2
    assert dispatcher._http.post.await_count == 1
    assert "non-global" in (delivery.last_error or "")


@pytest.mark.asyncio
async def test_http_client_keeps_redirects_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AsyncMock()
    async_client = MagicMock(return_value=client)
    monkeypatch.setattr("cutctx.proxy.webhooks.httpx.AsyncClient", async_client)
    dispatcher = WebhookDispatcher()

    await dispatcher.start()
    await dispatcher.stop()

    async_client.assert_called_once_with(timeout=dispatcher.timeout_s, follow_redirects=False)
