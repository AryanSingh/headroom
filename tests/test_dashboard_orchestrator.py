import pytest
from fastapi.testclient import TestClient
from cutctx.proxy.server import create_app
from cutctx.proxy.models import ProxyConfig

def test_admin_config_flags_orchestrator():
    config = ProxyConfig(
        backend="mock",
        cache_enabled=False,
    )
    app = create_app(config)
    with TestClient(app) as client:
        # Initial stats should show orchestrator as False (or correctly read it)
        stats = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        assert stats.status_code == 200
        assert "orchestrator" in stats.json()["config"]

        # Toggle it ON
        response = client.post(
            "/admin/config/flags",
            json={"orchestrator": True},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response.status_code == 200
        assert response.json()["config"]["orchestrator"] is True

        # Verify via /stats that it remains ON
        stats2 = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        assert stats2.json()["config"]["orchestrator"] is True

        # Toggle it OFF
        response2 = client.post(
            "/admin/config/flags",
            json={"orchestrator": False},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response2.status_code == 200
        assert response2.json()["config"]["orchestrator"] is False
