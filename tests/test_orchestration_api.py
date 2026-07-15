from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cutctx.proxy.model_routing_evals import ModelRoutingEvalRecord, ModelRoutingEvalStore
from cutctx.proxy.models import ProxyConfig
from cutctx.proxy.server import create_app


def _routing_eval_record(request_id: str, confidence: float, quality: float, savings: float):
    return ModelRoutingEvalRecord(
        request_id=request_id,
        prompt_hash="a" * 64,
        source_model="gpt-5.5",
        candidate_model="gpt-5.4-mini",
        scorer="test",
        confidence=confidence,
        quality_score=quality,
        source_cost_usd=1.0,
        candidate_cost_usd=1.0 - savings,
        segments={"client": "codex", "workspace_hash": "b" * 64},
    )


def _contract_payload(*, version: str = "1", baseline_model: str = "openai:gpt-5.4-mini"):
    return {
        "id": "implementation",
        "name": "Implementation",
        "version": version,
        "state": "draft",
        "role_aliases": ["worker"],
        "baseline_model": baseline_model,
        "requirements": {"required_capabilities": ["reasoning"]},
        "evaluation": {"minimum_samples": 2, "maximum_unsafe_rate": 0},
    }


def test_orchestration_contract_draft_simulation_and_lifecycle_api(
    tmp_path: Path, monkeypatch
) -> None:
    config_path = tmp_path / "orchestration.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": [{"id": "openai-main", "provider": "openai"}],
                "roles": [{"id": "worker", "name": "Worker"}],
                "models": [
                    {
                        "provider": "openai",
                        "model": "gpt-5.4-mini",
                        "account_id": "openai-main",
                        "capabilities": ["reasoning"],
                    }
                ],
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
        unauthorized = client.get("/v1/orchestration/contracts")
        assert unauthorized.status_code in {401, 403}

        empty = client.get("/v1/orchestration/contracts", headers=headers)
        assert empty.status_code == 200
        assert empty.json() == {"contracts": [], "revision": 0}

        saved = client.put(
            "/v1/orchestration/contracts/implementation/draft",
            headers=headers,
            json={"contract": _contract_payload(), "expected_revision": 0},
        )
        assert saved.status_code == 201
        assert saved.json()["contract"]["version"] == "1"
        assert saved.json()["revision"] == 1

        fetched = client.get(
            "/v1/orchestration/contracts/implementation/versions/1", headers=headers
        )
        assert fetched.status_code == 200
        assert fetched.json()["contract"]["id"] == "implementation"

        simulation = client.post(
            "/v1/orchestration/contracts/implementation/simulate",
            headers=headers,
            json={
                "contract": _contract_payload(version="2"),
                "scenario": {"role": "implementation", "request_id": "preview-1"},
            },
        )
        assert simulation.status_code == 200, simulation.text
        assert simulation.json()["executed"] is False
        assert simulation.json()["draft_receipt"]["contract_version"] == "2"

        shadow = client.post(
            "/v1/orchestration/contracts/implementation/versions/1/shadow",
            headers=headers,
        )
        assert shadow.status_code == 200
        assert shadow.json()["contract"]["state"] == "shadow"

        promotion = client.post(
            "/v1/orchestration/contracts/implementation/versions/1/promote",
            headers=headers,
        )
        assert promotion.status_code == 409
        assert promotion.json()["detail"]["reason"] == "insufficient_evidence"

        conflict = client.put(
            "/v1/orchestration/contracts/implementation/draft",
            headers=headers,
            json={"contract": _contract_payload(version="2"), "expected_revision": 0},
        )
        assert conflict.status_code == 409


def test_orchestration_routing_evidence_is_authenticated_private_and_read_only(
    tmp_path: Path, monkeypatch
) -> None:
    evidence_path = tmp_path / "private-customer-routing-evidence.jsonl"
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_EVAL_PATH", str(evidence_path))
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_MODE", "true")
    monkeypatch.setenv("CUTCTX_MODEL_ROUTING_SHADOW_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_DIR", str(tmp_path / "state"))
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
        unauthorized = client.get("/v1/orchestration/routing/evidence")
        assert unauthorized.status_code in {401, 403}

        empty = client.get(
            "/v1/orchestration/routing/evidence?minimum_samples=2&maximum_unsafe_rate=0",
            headers=headers,
        )
        assert empty.status_code == 200
        assert empty.json()["status"] == "no_evidence"
        assert empty.json()["shadow"] == {"enabled": True, "sample_rate": 0.25}
        assert empty.json()["scorer"] == {"status": "heuristic", "configured": False}

        store = ModelRoutingEvalStore(evidence_path)
        store.append(_routing_eval_record("safe-1", 0.95, 0.98, 0.4))
        store.append(_routing_eval_record("safe-2", 0.85, 0.92, 0.3))

        ready = client.get(
            "/v1/orchestration/routing/evidence?minimum_samples=2&maximum_unsafe_rate=0",
            headers=headers,
        )
        assert ready.status_code == 200
        payload = ready.json()
        assert payload["schema_version"] == 1
        assert payload["status"] == "ready"
        assert payload["recommendation"]["minimum_confidence"] == 0.85
        assert payload["recommendation"]["total_savings_usd"] == pytest.approx(0.7)
        assert str(evidence_path) not in ready.text
        assert "private-customer" not in ready.text


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
    monkeypatch.setenv("CUTCTX_ORCHESTRATION_AUDIT_KEY", "test-audit-key")
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

        manifest = client.get("/v1/orchestration/capability-manifest", headers=headers)
        assert manifest.status_code == 200
        assert manifest.json()["manifest_version"] == 1
        mini = next(
            item
            for item in manifest.json()["deployments"]
            if item["deployment_key"] == "openai:gpt-5.4-mini"
        )
        assert mini["verification"]["status"] == "advertised"

        harnesses = client.get("/v1/orchestration/harness-compatibility", headers=headers)
        assert harnesses.status_code == 200
        codex = next(item for item in harnesses.json()["harnesses"] if item["id"] == "codex")
        assert codex["hidden_session_sharing"] is False
        assert codex["artifact_handoffs"] is True

        bundle = client.get("/v1/orchestration/policy-bundle", headers=headers)
        assert bundle.status_code == 200
        assert bundle.json()["bundle_version"] == 1
        assert bundle.json()["bundle_hash"]

        receipt_audit = client.get("/v1/orchestration/receipt-audit/verify", headers=headers)
        assert receipt_audit.status_code == 200
        assert receipt_audit.json()["valid"] is True

        preview = client.post(
            "/v1/orchestration/route",
            headers=headers,
            json={"role": "worker", "required_capabilities": ["reasoning"]},
        )
        assert preview.status_code == 200
        assert preview.json()["actual_model"] == "gpt-5.4-mini"
        assert preview.json()["provider"] == "openai"
        assert preview.json()["receipt_version"] == 2

        constrained_preview = client.post(
            "/v1/orchestration/route",
            headers=headers,
            json={"role": "worker", "allowed_providers": ["openai"]},
        )
        assert constrained_preview.status_code == 200
        assert constrained_preview.json()["policy_constraints"]["allowed_providers"] == ["openai"]

        data_classification = client.post(
            "/v1/orchestration/route",
            headers=headers,
            json={
                "role": "worker",
                "data_classification": "internal",
                "allowed_data_classifications": ["internal"],
            },
        )
        assert data_classification.status_code == 409
        assert data_classification.json()["detail"]["reason"] == "data_classification_not_allowed"

        missing_estimate = client.post(
            "/v1/orchestration/route",
            headers=headers,
            json={"role": "worker", "max_cost_usd": 0.01},
        )
        assert missing_estimate.status_code == 400
        assert "requires estimated_input_tokens" in missing_estimate.json()["detail"]

        shadow = client.post(
            "/v1/orchestration/route/shadow",
            headers=headers,
            json={"role": "worker", "candidate_model": "gpt-4o", "provider": "openai"},
        )
        assert shadow.status_code == 200
        assert shadow.json()["executed"] is False
        assert shadow.json()["changed"] is True
        assert shadow.json()["baseline"]["actual_model"] == "gpt-5.4-mini"
        assert shadow.json()["candidate"]["actual_model"] == "gpt-4o"

        invalid_shadow = client.post(
            "/v1/orchestration/route/shadow",
            headers=headers,
            json={"role": "worker"},
        )
        assert invalid_shadow.status_code == 400

        scheduling = client.post(
            "/v1/orchestration/scheduler/recommend",
            headers=headers,
            json={"role": "worker", "task_type": "implementation", "min_observations": 1},
        )
        assert scheduling.status_code == 200
        assert scheduling.json()["mode"] == "recommendation_only"
        assert scheduling.json()["provider_calls"] == 0
        assert scheduling.json()["recommendation"] is None

        drift = client.post(
            "/v1/orchestration/scheduler/drift",
            headers=headers,
            json={"task_type": "implementation", "window_size": 1},
        )
        assert drift.status_code == 200
        assert drift.json()["status"] == "insufficient_evidence"

        outcome = client.post(
            "/v1/orchestration/outcomes",
            headers=headers,
            json={
                "request_id": "route-42",
                "task_type": "review",
                "verified": True,
                "review_accepted": True,
                "developer_rating": 5,
            },
        )
        assert outcome.status_code == 201
        assert outcome.json()["outcome"]["recorded_at"]
        assert "messages" not in outcome.json()["outcome"]
        outcomes = client.get("/v1/orchestration/outcomes", headers=headers)
        assert outcomes.status_code == 200
        assert outcomes.json()["outcomes"][0]["request_id"] == "route-42"

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

        fetched = client.get(f"/v1/orchestration/workflows/{workflow['id']}", headers=headers)
        assert fetched.status_code == 200
        assert fetched.json()["workflow"]["id"] == workflow["id"]

        gated = client.post(
            "/v1/orchestration/workflows",
            headers=headers,
            json={
                "id": "gated-review",
                "tasks": [
                    {
                        "id": "review",
                        "role": "worker",
                        "requires_approval": True,
                        "requires_verification": True,
                        "artifact": {
                            "repository_ref": "git:repo@abc",
                            "allowed_tools": ["read", "test"],
                            "provenance": {"source_harness": "codex"},
                        },
                    }
                ],
            },
        )
        assert gated.status_code == 201
        gated_workflow = gated.json()["workflow"]
        assert gated_workflow["tasks"]["review"]["status"] == "awaiting_approval"
        approved = client.post(
            f"/v1/orchestration/workflows/{gated_workflow['id']}/tasks/review/approve",
            headers=headers,
        )
        assert approved.status_code == 200
        assert approved.json()["workflow"]["tasks"]["review"]["approval_granted"] is True

        invalid_artifact = client.post(
            "/v1/orchestration/workflows",
            headers=headers,
            json={
                "id": "invalid-artifact",
                "tasks": [
                    {
                        "id": "review",
                        "role": "worker",
                        "artifact": {"unexpected": True},
                    }
                ],
            },
        )
        assert invalid_artifact.status_code == 400
        assert "Invalid task artifact" in invalid_artifact.json()["detail"]

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

        deleted = client.delete(
            "/v1/orchestration/providers/openai-main/credential", headers=headers
        )
        assert deleted.status_code == 200
        assert deleted.json() == {"account_id": "openai-main", "deleted": True}

        providers_after_delete = client.get("/v1/orchestration/providers", headers=headers)
        assert providers_after_delete.status_code == 200
        assert providers_after_delete.json()["accounts"][0]["credential_configured"] is False
