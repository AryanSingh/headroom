import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


@pytest.fixture
def test_app():
    config = ProxyConfig(
        admin_api_key="test-admin-key",
    )
    return create_app(config)


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


def test_dashboard_html_auth_bypass(client):
    """
    Test that the /dashboard route serves HTML without requiring authentication.
    The React SPA needs to load the HTML payload first to read localStorage and
    present the auth UI if necessary. It should not return a 401 Unauthorized
    or an Invalid URL error for the base HTML request.
    """
    # 1. Request the dashboard without any auth headers or key parameter
    response = client.get("/dashboard")

    # 2. It should succeed and return HTML
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )
    assert "text/html" in response.headers.get("content-type", "")
    assert "<html" in response.text.lower() or "<!doctype html>" in response.text.lower()

    # 3. Ensure a sub-path also works (React Router support)
    response_sub = client.get("/dashboard/playground")
    assert response_sub.status_code == 200, (
        f"Expected 200 OK for subpath, got {response_sub.status_code}"
    )
    assert "text/html" in response_sub.headers.get("content-type", "")
