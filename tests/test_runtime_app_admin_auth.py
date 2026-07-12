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


def test_sensitive_surfaces_do_not_accept_query_parameter_credentials(client: TestClient) -> None:
    response = client.get("/stats?key=test-admin-key")

    assert response.status_code == 401


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
