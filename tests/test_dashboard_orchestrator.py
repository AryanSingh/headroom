from __future__ import annotations

import json

from fastapi.testclient import TestClient

from cutctx.proxy.model_router import ModelRouterConfig
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def test_legacy_admin_config_flags_orchestrator_surface() -> None:
    config = ProxyConfig(
        backend="mock",
        cache_enabled=False,
        admin_api_key="admin_12345",
    )
    app = create_app(config)

    with TestClient(app) as client:
        stats = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        assert stats.status_code == 200
        assert "orchestrator" in stats.json()["config"]

        response = client.post(
            "/admin/config/flags",
            json={"orchestrator": True},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response.status_code == 200
        assert response.json()["config"]["orchestrator"] is True
        assert response.json()["config"]["orchestrator_mode"] == "balanced"

        stats2 = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        payload2 = stats2.json()
        assert payload2["config"]["orchestrator"] is True
        assert payload2["model_routing"]["mode"] == "balanced"

        response2 = client.post(
            "/admin/config/flags",
            json={"orchestrator": False},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response2.status_code == 200
        assert response2.json()["config"]["orchestrator"] is False


def test_config_flags_can_enable_live_orchestrator_when_routes_are_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "CUTCTX_MODEL_ROUTING",
        json.dumps(
            {
                "enabled": True,
                "downgrade_when": "always",
                "routes": [
                    {
                        "source": "claude-opus-4-5",
                        "target": "claude-sonnet-4-5",
                        "source_cost_per_mtok": 15.0,
                        "target_cost_per_mtok": 3.0,
                    }
                ],
            }
        ),
    )
    config = ProxyConfig(
        backend="mock",
        cache_enabled=False,
        rate_limit_enabled=False,
        admin_api_key="admin_12345",
    )
    app = create_app(config)

    with TestClient(app) as client:
        initial = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        initial_model_routing = initial.json()["model_routing"]
        assert "requested" in initial_model_routing
        assert "available" in initial_model_routing
        assert "configured_routes" in initial_model_routing

        response = client.post(
            "/config/flags",
            json={"orchestrator": True},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response.status_code == 200
        assert response.json()["applied_live"]["orchestrator"]["enabled"] is True

        flags = client.get("/config/flags", headers={"x-cutctx-admin-key": "admin_12345"})
        orchestrator_state = flags.json()["live_toggleable"]["orchestrator"]
        assert orchestrator_state["enabled"] is True
        assert orchestrator_state["source"] == "runtime"

        stats = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        model_routing = stats.json()["model_routing"]
        assert "available" in model_routing
        assert "configured_routes" in model_routing
        config_state = stats.json()["config"]
        assert config_state["orchestrator"] is True


def test_config_flags_enable_orchestrator_uses_configured_preset_routes() -> None:
    config = ProxyConfig(
        backend="mock",
        cache_enabled=False,
        rate_limit_enabled=False,
        admin_api_key="admin_12345",
        model_routing_preset="codex-gpt54mini-high",
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/config/flags",
            json={"orchestrator": True},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )

        assert response.status_code == 200
        assert response.json()["applied_live"]["orchestrator"]["enabled"] is True

        stats = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        assert stats.status_code == 200

        payload = stats.json()
        assert payload["config"]["orchestrator"] is True
        assert payload["config"]["orchestrator_mode"] == "balanced"
        assert payload["model_routing"]["preset"] == "codex-gpt54mini-high"
        assert payload["model_routing"]["mode"] == "balanced"
        assert payload["model_routing"]["configured_routes"] == len(
            ModelRouterConfig.codex_gpt54mini_high_preset().routes
        )

        status = client.get(
            "/v1/orchestration/safe-savings/status",
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert status.status_code == 200
        assert status.json()["preset"] == "codex-gpt54mini-high"
        assert status.json()["route_count"] == len(
            ModelRouterConfig.codex_gpt54mini_high_preset().routes
        )


def test_config_flags_supports_balanced_and_aggressive_modes() -> None:
    config = ProxyConfig(
        backend="mock",
        cache_enabled=False,
        rate_limit_enabled=False,
        admin_api_key="admin_12345",
    )
    app = create_app(config)

    with TestClient(app) as client:
        response = client.post(
            "/config/flags",
            json={"orchestrator_mode": "balanced"},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response.status_code == 200
        assert response.json()["applied_live"]["orchestrator_mode"]["mode"] == "balanced"

        stats = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        payload = stats.json()
        assert payload["config"]["orchestrator"] is True
        assert payload["model_routing"]["mode"] == "balanced"
        assert payload["model_routing"]["preset"] == "codex-gpt54mini-high"

        response = client.post(
            "/config/flags",
            json={"orchestrator_mode": "aggressive"},
            headers={"x-cutctx-admin-key": "admin_12345"},
        )
        assert response.status_code == 200
        assert response.json()["applied_live"]["orchestrator_mode"]["mode"] == "aggressive"

        stats = client.get("/stats", headers={"x-cutctx-admin-key": "admin_12345"})
        payload = stats.json()
        assert payload["config"]["orchestrator"] is True
        assert payload["model_routing"]["mode"] == "aggressive"
        assert payload["model_routing"]["preset"] == "economy"
