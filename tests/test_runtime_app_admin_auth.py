from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from cutctx.proxy.server import ProxyConfig, create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            admin_api_key="test-admin-key",
        )
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1",
        client=("127.0.0.1", 12345),
    ) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/stats", "/stats-history"])
def test_sensitive_surfaces_require_admin_auth_when_key_configured(
    client: TestClient,
    path: str,
) -> None:
    response = client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/stats", "/stats-history"])
def test_sensitive_surfaces_accept_admin_auth_when_key_configured(
    client: TestClient,
    path: str,
) -> None:
    response = client.get(path, headers={"X-Cutctx-Admin-Key": "test-admin-key"})
    assert response.status_code == 200


@pytest.mark.parametrize("path", ["/stats", "/stats-history"])
def test_sensitive_surfaces_accept_activated_license_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    monkeypatch.setattr(
        "cutctx.proxy.deployment_security.effective_license_key",
        lambda _config: "cutctx_faa8a7aeef684507aea4e67b24883e9f",
    )
    response = client.get(
        path,
        headers={"X-Cutctx-Admin-Key": "cutctx_faa8a7aeef684507aea4e67b24883e9f"},
    )
    assert response.status_code == 200


def test_sensitive_surfaces_do_not_accept_query_parameter_credentials(client: TestClient) -> None:
    response = client.get("/stats?key=test-admin-key")

    assert response.status_code == 401


def test_dashboard_bootstrap_token_exchanges_for_an_authenticated_cookie(
    client: TestClient,
) -> None:
    minted = client.post(
        "/admin/dashboard-sessions",
        headers={"X-Cutctx-Admin-Key": "test-admin-key"},
    )

    assert minted.status_code == 200
    token = minted.json()["bootstrap_token"]
    assert token != "test-admin-key"

    connected = client.get(f"/dashboard/connect?token={token}", follow_redirects=False)

    assert connected.status_code == 303
    assert connected.headers["location"] == "/dashboard"
    assert "HttpOnly" in connected.headers["set-cookie"]
    assert client.get("/stats").status_code == 200
    assert (
        client.get(f"/dashboard/connect?token={token}", follow_redirects=False).status_code == 401
    )


def test_dashboard_bootstrap_tokens_do_not_invalidate_other_opening_windows(
    client: TestClient,
) -> None:
    headers = {"X-Cutctx-Admin-Key": "test-admin-key"}
    first = client.post("/admin/dashboard-sessions", headers=headers).json()["bootstrap_token"]
    second = client.post("/admin/dashboard-sessions", headers=headers).json()["bootstrap_token"]

    assert (
        client.get(f"/dashboard/connect?token={first}", follow_redirects=False).status_code == 303
    )
    assert (
        client.get(f"/dashboard/connect?token={second}", follow_redirects=False).status_code == 303
    )


@pytest.mark.no_auto_admin
def test_local_write_route_does_not_trust_spoofed_admin_role(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    monkeypatch.delenv("CUTCTX_ALLOW_ROLE_HEADER", raising=False)
    app = create_app(
        ProxyConfig(
            optimize=False,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            admin_api_key=None,
        )
    )

    with TestClient(app, base_url="http://127.0.0.1") as local_client:
        response = local_client.post(
            "/stats/reset",
            headers={"X-Cutctx-Role": "admin"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["role"] == "viewer"
