from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.datastructures import Headers
from starlette.websockets import WebSocketDisconnect

from cutctx.providers.proxy_routes import register_provider_routes
from cutctx.proxy.client_auth import (
    ProxyClientAuthError,
    require_http_proxy_client,
    require_websocket_proxy_client,
)
from cutctx.proxy.models import ProxyConfig


def _request(*, headers: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(headers=Headers(headers or {}))


def _websocket(*, headers: dict[str, str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(headers=Headers(headers or {}))


def test_configured_proxy_key_is_required_without_consuming_authorization() -> None:
    config = ProxyConfig(proxy_api_key="proxy-secret")

    with pytest.raises(ProxyClientAuthError, match="proxy client credential"):
        require_http_proxy_client(
            _request(headers={"authorization": "Bearer upstream-provider-key"}),
            config,
        )

    require_http_proxy_client(
        _request(
            headers={
                "authorization": "Bearer upstream-provider-key",
                "x-cutctx-proxy-key": "proxy-secret",
            }
        ),
        config,
    )


def test_loopback_http_remains_zero_config_without_proxy_key() -> None:
    require_http_proxy_client(_request(), ProxyConfig(host="127.0.0.1"))


def test_non_loopback_http_requires_configured_proxy_key() -> None:
    with pytest.raises(ProxyClientAuthError, match="configure CUTCTX_PROXY_API_KEY"):
        require_http_proxy_client(_request(), ProxyConfig(host="0.0.0.0"))


def test_non_loopback_websocket_requires_configured_proxy_key() -> None:
    with pytest.raises(ProxyClientAuthError, match="configure CUTCTX_PROXY_API_KEY"):
        require_websocket_proxy_client(_websocket(), ProxyConfig(host="0.0.0.0"))


def test_websocket_rejects_cross_origin_browser_on_loopback() -> None:
    with pytest.raises(ProxyClientAuthError, match="WebSocket origin"):
        require_websocket_proxy_client(
            _websocket(
                headers={
                    "host": "127.0.0.1:8787",
                    "origin": "https://attacker.example",
                }
            ),
            ProxyConfig(host="127.0.0.1"),
        )


def test_websocket_accepts_explicit_trusted_origin() -> None:
    require_websocket_proxy_client(
        _websocket(
            headers={
                "host": "127.0.0.1:8787",
                "origin": "https://dashboard.example",
            }
        ),
        ProxyConfig(
            host="127.0.0.1",
            cors_origins=["https://dashboard.example"],
        ),
    )


def test_websocket_cli_without_origin_uses_dedicated_proxy_key() -> None:
    config = ProxyConfig(proxy_api_key="proxy-secret")
    with pytest.raises(ProxyClientAuthError, match="proxy client credential"):
        require_websocket_proxy_client(_websocket(), config)

    require_websocket_proxy_client(
        _websocket(headers={"x-cutctx-proxy-key": "proxy-secret"}),
        config,
    )


def test_provider_router_enforces_dedicated_proxy_key() -> None:
    app = FastAPI()
    proxy = SimpleNamespace(
        config=ProxyConfig(proxy_api_key="proxy-secret"),
        handle_openai_chat=AsyncMock(return_value=JSONResponse({"ok": True})),
    )
    register_provider_routes(app, proxy)

    with TestClient(app) as client:
        missing = client.post("/v1/chat/completions", json={"model": "gpt-test"})
        allowed = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-test"},
            headers={"x-cutctx-proxy-key": "proxy-secret"},
        )

    assert missing.status_code == 401
    assert allowed.status_code == 200
    assert proxy.handle_openai_chat.await_count == 1


def test_provider_router_rejects_untrusted_websocket_origin() -> None:
    app = FastAPI()
    proxy = SimpleNamespace(
        config=ProxyConfig(host="127.0.0.1"),
        handle_openai_responses_ws=AsyncMock(),
    )
    register_provider_routes(app, proxy)

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/v1/responses",
                headers={"origin": "https://attacker.example"},
            ):
                pass

    assert exc_info.value.code == 1008
    assert proxy.handle_openai_responses_ws.await_count == 0
