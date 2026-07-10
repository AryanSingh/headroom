"""Admin-auth regressions for CCR retrieve and feedback routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _app_with_admin_key(monkeypatch: pytest.MonkeyPatch):
    # conftest.py auto-injects the suite default admin key into TestClient.
    # Use a non-default key so these tests exercise the unauthenticated path.
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "route-auth-key")

    from cutctx.proxy.server import ProxyConfig, create_app

    return create_app(
        ProxyConfig(
            admin_api_key="route-auth-key",
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            entitlement_tier="enterprise",
        )
    )


def test_v1_retrieve_post_requires_admin_key(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app_with_admin_key(monkeypatch)

    with TestClient(app) as client:
        denied = client.post("/v1/retrieve", json={"hash": "missing"})
        assert denied.status_code in {401, 403}

        allowed = client.post(
            "/v1/retrieve",
            json={},
            headers={"x-cutctx-admin-key": "route-auth-key"},
        )
        assert allowed.status_code == 400
        assert "hash required" in allowed.text


def test_v1_feedback_requires_admin_key(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app_with_admin_key(monkeypatch)

    with TestClient(app) as client:
        denied = client.get("/v1/feedback")
        assert denied.status_code in {401, 403}

        allowed = client.get(
            "/v1/feedback",
            headers={"x-cutctx-admin-key": "route-auth-key"},
        )
        assert allowed.status_code == 200
        assert isinstance(allowed.json(), dict)


def test_v1_feedback_for_tool_requires_admin_key(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app_with_admin_key(monkeypatch)

    with TestClient(app) as client:
        denied = client.get("/v1/feedback/github_search")
        assert denied.status_code in {401, 403}

        allowed = client.get(
            "/v1/feedback/github_search",
            headers={"x-cutctx-admin-key": "route-auth-key"},
        )
        assert allowed.status_code == 200
        assert allowed.json()["tool_name"] == "github_search"
