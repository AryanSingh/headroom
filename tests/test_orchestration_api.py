from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def test_orchestration_admin_api_config_models_and_strict_preview(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "orchestration.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": [
                    {
                        "id": "openai-main",
                        "provider": "openai",
                        "custom_headers": {"x-tenant": "private-tenant"},
                    }
                ],
                "roles": [{"id": "worker", "name": "Worker"}],
                "bindings": [
                    {
                        "id": "worker-mini",
                        "role": "worker",
                        "model": "openai:gpt-5.4-mini",
                    }
                ],
                "settings": {"mode": "strict", "policy": "role_locked"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_CONFIG", str(config_path))
    app = create_app(
        ProxyConfig(
            backend="mock",
            cache_enabled=False,
            admin_api_key="admin_12345",
            prefix_freeze_db_path=str(tmp_path / "prefix-tracker.db"),
        )
    )
    headers = {"x-cutctx-admin-key": "admin_12345"}

    with TestClient(app) as client:
        unauthorized = client.get("/v1/orchestration/config")
        assert unauthorized.status_code in {401, 403}

        config = client.get("/v1/orchestration/config", headers=headers)
        assert config.status_code == 200
        assert config.json()["roles"][0]["id"] == "worker"
        assert config.json()["providers"][0]["custom_headers"] == {"x-tenant": "********"}
        assert "private-tenant" not in config.text

        saved = client.put(
            "/v1/orchestration/config",
            headers=headers,
            json=config.json(),
        )
        assert saved.status_code == 200
        assert "private-tenant" not in saved.text
        persisted = json.loads(config_path.read_text(encoding="utf-8"))
        assert persisted["providers"][0]["custom_headers"]["x-tenant"] == "private-tenant"

        models = client.get("/v1/orchestration/models", headers=headers)
        assert models.status_code == 200
        assert any(model["key"] == "openai:gpt-5.4-mini" for model in models.json()["models"])

        preview = client.post(
            "/v1/orchestration/route",
            headers=headers,
            json={"role": "worker", "required_capabilities": ["reasoning"]},
        )
        assert preview.status_code == 200
        assert preview.json()["actual_model"] == "gpt-5.4-mini"
        assert preview.json()["provider"] == "openai"

        missing = client.post(
            "/v1/orchestration/route", headers=headers, json={"role": "unassigned"}
        )
        assert missing.status_code == 409
        assert missing.json()["detail"]["reason"] == "unassigned_role"

        malformed = client.post(
            "/v1/orchestration/route",
            headers=headers,
            json={"role": "worker", "required_capabilities": "reasoning"},
        )
        assert malformed.status_code in {400, 422}

        direct_execution = client.post(
            "/v1/orchestration/execute",
            headers=headers,
            json={"role": "worker", "messages": []},
        )
        assert direct_execution.status_code == 404
