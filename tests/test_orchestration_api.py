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

        submitted = client.post(
            "/v1/orchestration/workflows",
            headers=headers,
            json={
                "id": "implement-feature",
                "idempotency_key": "request-123",
                "tasks": [
                    {"id": "plan", "role": "worker", "messages": []},
                    {
                        "id": "review",
                        "role": "worker",
                        "depends_on": ["plan"],
                        "messages": [],
                    },
                ],
            },
        )
        assert submitted.status_code == 201
        workflow = submitted.json()["workflow"]
        assert workflow["tasks"]["plan"]["status"] == "pending"
        assert workflow["task_specs"]["review"]["depends_on"] == ["plan"]

        fetched = client.get(
            f"/v1/orchestration/workflows/{workflow['id']}", headers=headers
        )
        assert fetched.status_code == 200
        assert fetched.json()["workflow"]["id"] == workflow["id"]

        duplicate = client.post(
            "/v1/orchestration/workflows",
            headers=headers,
            json={
                "id": "implement-feature",
                "idempotency_key": "request-123",
                "tasks": [
                    {"id": "plan", "role": "worker", "messages": []},
                    {
                        "id": "review",
                        "role": "worker",
                        "depends_on": ["plan"],
                        "messages": [],
                    },
                ],
            },
        )
        assert duplicate.status_code == 201
        assert duplicate.json()["workflow"]["id"] == workflow["id"]

        conflict = client.post(
            "/v1/orchestration/workflows",
            headers=headers,
            json={
                "id": "different-request",
                "idempotency_key": "request-123",
                "tasks": [{"id": "plan", "role": "worker", "messages": []}],
            },
        )
        assert conflict.status_code == 409

        cancelled = client.post(
            f"/v1/orchestration/workflows/{workflow['id']}/cancel", headers=headers
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["workflow"]["status"] == "cancelled"


def test_orchestration_provider_credentials_persist_across_restarts(
    tmp_path: Path, monkeypatch
) -> None:
    state_dir = tmp_path / "state"
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(state_dir))
    headers = {"x-cutctx-admin-key": "admin_12345"}

    monkeypatch.chdir(workspace_a)
    app = create_app(
        ProxyConfig(
            backend="mock",
            cache_enabled=False,
            admin_api_key="admin_12345",
            prefix_freeze_db_path=str(tmp_path / "prefix-tracker.db"),
        )
    )
    with TestClient(app) as client:
        saved = client.put(
            "/v1/orchestration/providers/openai-main",
            headers=headers,
            json={
                "provider": "openai",
                "display_name": "Primary OpenAI",
                "base_url": "https://api.openai.com/v1",
            },
        )
        assert saved.status_code == 200
        stored = client.put(
            "/v1/orchestration/providers/openai-main/credential",
            headers=headers,
            json={"api_key": "persist-me"},
        )
        assert stored.status_code == 200

    assert not (workspace_a / ".cutctx" / "orchestration.json").exists()

    monkeypatch.chdir(workspace_b)
    restarted = create_app(
        ProxyConfig(
            backend="mock",
            cache_enabled=False,
            admin_api_key="admin_12345",
            prefix_freeze_db_path=str(tmp_path / "prefix-tracker.db"),
        )
    )
    with TestClient(restarted) as client:
        providers = client.get("/v1/orchestration/providers", headers=headers)
        assert providers.status_code == 200
        assert providers.json()["accounts"] == [
            {
                "id": "openai-main",
                "provider": "openai",
                "display_name": "Primary OpenAI",
                "auth_method": "api_key",
                "credential_ref": "provider:openai-main",
                "base_url": "https://api.openai.com/v1",
                "organization_id": None,
                "workspace_id": None,
                "custom_headers": {},
                "enabled": True,
                "metadata": {},
                "credential_configured": True,
            }
        ]
