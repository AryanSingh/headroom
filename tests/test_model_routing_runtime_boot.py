from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def test_model_routing_initializes_from_env_on_runtime_boot(monkeypatch) -> None:
    monkeypatch.setenv(
        "CUTCTX_MODEL_ROUTING",
        (
            '{"enabled":true,"downgrade_when":"always","routes":['
            '{"source":"gpt-5.4","target":"gpt-5.4-mini",'
            '"source_cost_per_mtok":10.0,"target_cost_per_mtok":2.0}]}'
        ),
    )

    config = ProxyConfig()
    config.admin_api_key = "test_admin"
    config.optimize = False
    config.cache_enabled = False
    config.rate_limit_enabled = False
    config.cost_tracking_enabled = False

    app = create_app(config)

    with TestClient(app) as client:
        stats = client.get(
            "/stats",
            headers={"X-Cutctx-Admin-Key": "test_admin"},
        )

        assert stats.status_code == 200, stats.text
        payload = stats.json()
        assert payload["config"]["orchestrator"] is True
        assert payload["config"]["orchestrator_mode"] == "custom"
        assert payload["model_routing"]["requested"] is True
        assert payload["model_routing"]["available"] is True
        assert payload["model_routing"]["configured_routes"] == 1
        assert payload["model_routing"]["mode"] == "custom"


def test_model_routing_preset_initializes_on_runtime_boot() -> None:
    config = ProxyConfig()
    config.admin_api_key = "test_admin"
    config.optimize = False
    config.cache_enabled = False
    config.rate_limit_enabled = False
    config.cost_tracking_enabled = False
    config.model_routing_preset = "codex-gpt54mini-high"

    app = create_app(config)

    with TestClient(app) as client:
        stats = client.get(
            "/stats",
            headers={"X-Cutctx-Admin-Key": "test_admin"},
        )

        assert stats.status_code == 200, stats.text
        payload = stats.json()
        assert payload["config"]["orchestrator"] is True
        assert payload["config"]["orchestrator_mode"] == "balanced"
        assert payload["model_routing"]["requested"] is True
        assert payload["model_routing"]["available"] is True
        assert payload["model_routing"]["configured_routes"] >= 2
        assert payload["model_routing"]["preset"] == "codex-gpt54mini-high"
        assert payload["model_routing"]["mode"] == "balanced"
