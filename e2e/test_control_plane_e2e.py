import pytest
from fastapi.testclient import TestClient

from headroom.proxy.server import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)

def test_license_crl(client: TestClient) -> None:
    # Test that the control plane license endpoints are wired up
    # We may get a 501 or empty depending on EE
    response = client.get("/v1/license/crl")
    assert response.status_code in [200, 501]

def test_spend_events(client: TestClient) -> None:
    # Test that spend endpoints are wired up
    response = client.post("/v1/spend/events", json={
        "events": [
            {
                "org_id": "test-org",
                "workspace_id": "test-workspace",
                "model": "claude-3",
                "input_tokens": 100,
                "output_tokens": 200,
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "request_id": "req-1"
            }
        ]
    })
    assert response.status_code in [202, 501]

def test_policies(client: TestClient) -> None:
    # Test that policy endpoints are wired up
    response = client.post("/v1/policies", json={
        "org_id": "test-org",
        "require_compression": True
    })
    assert response.status_code in [200, 501]

def test_audit_events(client: TestClient) -> None:
    # Test that audit endpoints are wired up
    response = client.post("/v1/audit/events", json={
        "tenant_id": "test-org",
        "actor": "user-1",
        "action": "test.action",
        "payload": {"key": "value"}
    })
    assert response.status_code in [200, 501]
