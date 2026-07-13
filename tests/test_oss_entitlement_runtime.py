"""Regression coverage for the OSS Docker runtime entitlement boundary."""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient


def test_missing_commercial_distribution_uses_fail_closed_checker(
    monkeypatch,
) -> None:
    """An OSS install starts the proxy but does not grant commercial routes."""
    from cutctx.proxy import server
    from cutctx.proxy.server import ProxyConfig, create_app

    monkeypatch.setitem(sys.modules, "cutctx.entitlements", None)
    checker = server._load_entitlement_checker("enterprise")
    assert checker.plan_name == "builder"
    assert checker.is_entitled("audit_logs") is False

    monkeypatch.setattr(server, "_load_entitlement_checker", lambda _plan: checker)
    config = ProxyConfig(
        admin_api_key="oss-runtime-key",
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
    )
    with TestClient(create_app(config)) as client:
        response = client.get("/health")
        assert response.status_code == 200
        entitlements = client.get(
            "/entitlements",
            headers={"X-Cutctx-Admin-Key": "oss-runtime-key"},
        )
        assert entitlements.status_code == 200
        assert entitlements.json()["current_tier"] == "builder"
        assert entitlements.json()["features"] == {}
