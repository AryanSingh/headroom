"""Admin routes must import their live telemetry, TOIN, and CCR helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def _app() -> object:
    return create_app(
        ProxyConfig(
            admin_api_key="admin-runtime-key",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            entitlement_tier="enterprise",
        )
    )


def test_telemetry_route_uses_telemetry_collector_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = SimpleNamespace(get_stats=lambda: {"live": True})
    monkeypatch.setattr("cutctx.telemetry.collector.get_telemetry_collector", lambda: collector)

    with TestClient(_app()) as client:
        response = client.get(
            "/v1/telemetry", headers={"x-cutctx-admin-key": "admin-runtime-key"}
        )

    assert response.status_code == 200
    assert response.json() == {"live": True}


def test_toin_route_uses_toin_module(monkeypatch: pytest.MonkeyPatch) -> None:
    toin = SimpleNamespace(get_stats=lambda: {"patterns": 3})
    monkeypatch.setattr("cutctx.telemetry.toin.get_toin", lambda: toin)

    with TestClient(_app()) as client:
        response = client.get(
            "/v1/toin/stats", headers={"x-cutctx-admin-key": "admin-runtime-key"}
        )

    assert response.status_code == 200
    assert response.json() == {"patterns": 3}


def test_ccr_tool_call_route_uses_ccr_parser_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cutctx.ccr.tool_injection.parse_tool_call", lambda _call, _provider: (None, None)
    )

    with TestClient(_app()) as client:
        response = client.post(
            "/v1/retrieve/tool_call",
            json={"tool_call": {}, "provider": "anthropic"},
            headers={"x-cutctx-admin-key": "admin-runtime-key"},
        )

    assert response.status_code == 400
    assert "cutctx_retrieve" in response.text
