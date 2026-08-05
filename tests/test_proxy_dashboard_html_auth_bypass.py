import re
from collections import deque

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


def test_dashboard_runtime_serves_entry_and_imported_chunks(client):
    html_response = client.get("/dashboard")
    assert html_response.status_code == 200

    asset_urls = set(re.findall(r'(?:src|href)="(/assets/[^"]+\.(?:js|css))"', html_response.text))
    assert asset_urls

    pending = deque(sorted(url for url in asset_urls if url.endswith(".js")))
    discovered_imported_urls: set[str] = set()
    visited: set[str] = set()
    while pending:
        asset_url = pending.popleft()
        if asset_url in visited:
            continue
        visited.add(asset_url)
        response = client.get(asset_url)
        assert response.status_code == 200, asset_url
        for chunk in re.findall(r"""(?:from|import\()\s*["'`]\./([^"'`]+\.js)""", response.text):
            imported_url = f"/assets/{chunk}"
            discovered_imported_urls.add(imported_url)
            pending.append(imported_url)

    assert discovered_imported_urls
    assert discovered_imported_urls <= visited

    for asset_url in sorted(asset_urls - visited):
        response = client.get(asset_url)
        assert response.status_code == 200, asset_url
