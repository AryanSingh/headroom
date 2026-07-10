from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.circuit_breaker import get_circuit_breaker
from cutctx.proxy.routing.failover import FailoverRouter, ProviderEndpoint
from cutctx.proxy.server import create_app


def _base_config() -> ProxyConfig:
    return ProxyConfig(
        admin_api_key="test_admin",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        log_requests=False,
        ccr_inject_tool=False,
        ccr_handle_responses=False,
        ccr_context_tracking=False,
        image_optimize=False,
    )


def test_failover_admin_api_lists_and_toggles_provider_health() -> None:
    app = create_app(_base_config())

    with TestClient(app) as client:
        headers = {"X-Cutctx-Admin-Key": "test_admin"}

        listed = client.get("/v1/providers", headers=headers)
        assert listed.status_code == 200, listed.text
        providers = listed.json()["providers"]
        assert providers
        assert providers[0]["name"] == "anthropic"
        assert providers[0]["healthy"] is True

        disabled = client.post("/v1/providers/anthropic/disable", headers=headers)
        assert disabled.status_code == 200, disabled.text
        assert disabled.json() == {"provider": "anthropic", "healthy": False}

        after_disable = client.get("/v1/providers", headers=headers)
        assert after_disable.status_code == 200, after_disable.text
        assert after_disable.json()["providers"][0]["healthy"] is False

        enabled = client.post("/v1/providers/anthropic/enable", headers=headers)
        assert enabled.status_code == 200, enabled.text
        assert enabled.json() == {"provider": "anthropic", "healthy": True}


class _HealthyClient:
    async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> httpx.Response:
        request = httpx.Request("POST", url, content=content, headers=headers)
        return httpx.Response(200, request=request, json={"ok": True})


class _FailingClient:
    async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> httpx.Response:
        request = httpx.Request("POST", url, content=content, headers=headers)
        raise httpx.ConnectError("provider offline", request=request)


def test_retry_request_updates_failover_router_health() -> None:
    app = create_app(_base_config())
    proxy = app.state.proxy
    proxy.failover_router = FailoverRouter(
        endpoints=[
            ProviderEndpoint(
                name="anthropic",
                base_url="https://api.anthropic.com",
                api_key_env="ANTHROPIC_API_KEY",
            )
        ],
        failure_threshold=1,
        cooldown_seconds=60.0,
    )

    telemetry_tags: dict[str, str] = {}

    proxy.http_client = _HealthyClient()
    asyncio.run(
        proxy._retry_request(
            method="POST",
            url="https://api.anthropic.com/v1/messages",
            headers={},
            body={"messages": [{"role": "user", "content": "hi"}]},
            telemetry_tags=telemetry_tags,
        )
    )
    assert proxy.failover_router.get_status()[0]["healthy"] is True
    assert telemetry_tags["upstream_provider"] == "anthropic"
    assert telemetry_tags["circuit_breaker_state"] == "closed"
    assert telemetry_tags["failover_active_provider"] == "anthropic"

    breaker = get_circuit_breaker("anthropic")
    breaker.failure_threshold = 1

    proxy.http_client = _FailingClient()
    with pytest.raises(httpx.ConnectError):
        asyncio.run(
            proxy._retry_request(
                method="POST",
                url="https://api.anthropic.com/v1/messages",
                headers={},
                body={"messages": [{"role": "user", "content": "hi"}]},
                telemetry_tags=telemetry_tags,
            )
        )

    assert proxy.failover_router.get_status()[0]["healthy"] is False
    assert telemetry_tags["fallback_provider"] == "anthropic"
    assert telemetry_tags["fallback_reason"] == "connect_error"
    assert telemetry_tags["circuit_breaker_state"] == "open"
