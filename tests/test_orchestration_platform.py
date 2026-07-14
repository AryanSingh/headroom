from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from cutctx.orchestration.audit import ReceiptAuditStore
from cutctx.orchestration.config import LayeredConfigStore
from cutctx.orchestration.credentials import EncryptedCredentialStore, ResolverBackedCredentialStore
from cutctx.orchestration.engine import DeterministicRoutingEngine, RoutingUnavailableError
from cutctx.orchestration.evaluation import RoutingEvaluationCase, evaluate_routing_cases
from cutctx.orchestration.models import (
    Capability,
    ExecutionRecord,
    ModelRecord,
    OrchestrationConfig,
    OutcomeRecord,
    ProviderAccount,
    Role,
    RouteBinding,
    RoutingMode,
    RoutingProfile,
    RoutingRequest,
    RoutingSettings,
)
from cutctx.orchestration.policy_bundle import (
    compile_policy_bundle,
    sign_policy_bundle,
    verify_policy_bundle,
)
from cutctx.orchestration.providers import (
    HTTPProviderAdapter,
    LiteLLMProviderAdapter,
    ProviderAdapterRegistry,
    ProviderHealth,
    ProviderSpec,
    builtin_provider_registry,
)
from cutctx.orchestration.registry import DynamicModelRegistry
from cutctx.orchestration.scheduler import (
    SchedulerGuardrails,
    canary_assignment,
    detect_quality_drift,
    recommend_schedule,
)
from cutctx.orchestration.service import OrchestrationService, build_orchestration_service
from cutctx.orchestration.telemetry import ExecutionTelemetryStore, OutcomeTelemetryStore
from cutctx.orchestration.workflow import TaskSpec, WorkflowSpec, WorkflowStateStore
from cutctx.proxy.model_router import prepare_model_routing
from cutctx.proxy.routes.orchestration import create_orchestration_router
from cutctx.proxy.savings_metadata import extract_savings_metadata


def _model(
    provider: str,
    model: str,
    *,
    account_id: str | None = None,
    capabilities: set[str] | None = None,
    available: bool = True,
) -> ModelRecord:
    return ModelRecord(
        provider=provider,
        id=model,
        account_id=account_id,
        capabilities=capabilities or {Capability.STREAMING.value, Capability.TOOL_CALLING.value},
        available=available,
    )


def _engine(config: OrchestrationConfig, *models: ModelRecord) -> DeterministicRoutingEngine:
    registry = DynamicModelRegistry()
    for model in models:
        registry.register(model)
    return DeterministicRoutingEngine(config, registry)


def test_given_role_assignment_when_routing_then_assigned_model_is_enforced() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="implementer", name="Implementer")],
        bindings=[
            RouteBinding(
                id="implementer-kimi",
                role="implementer",
                model="kimi:kimi-2.7",
                fallback_chain=["openai:gpt-5.4-mini"],
            )
        ],
        settings=RoutingSettings(mode=RoutingMode.STRICT.value),
    )
    engine = _engine(
        config,
        _model("kimi", "kimi-2.7"),
        _model("openai", "gpt-5.4-mini"),
    )

    decision = engine.route(RoutingRequest(role="Implementer"))

    assert decision.actual_model == "kimi-2.7"
    assert decision.provider == "kimi"
    assert decision.fallback_used is False
    assert decision.binding_id == "implementer-kimi"


def test_versioned_routing_profile_resolves_role_and_narrows_budget(tmp_path: Path) -> None:
    model = _model("openai", "gpt-5.4-mini", account_id="openai-main")
    model.input_cost_per_million = 1.0
    model.output_cost_per_million = 1.0
    config = OrchestrationConfig(
        providers=[ProviderAccount(id="openai-main", provider="openai")],
        roles=[Role(id="implementer", name="Implementer")],
        profiles=[
            RoutingProfile(
                id="implementer",
                role="implementer",
                version="2026-07",
                required_capabilities={Capability.TOOL_CALLING.value},
                allowed_providers={"openai"},
                max_cost_usd=0.2,
            )
        ],
        bindings=[RouteBinding(id="implementer", role="implementer", model="openai:gpt-5.4-mini")],
    )
    service = OrchestrationService(
        config_store=LayeredConfigStore(),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
    )
    service.config = config
    service.model_registry.register(model)
    service.engine = DeterministicRoutingEngine(
        config, service.model_registry, require_configured_accounts=True
    )

    decision = service.route(
        RoutingRequest(
            profile="implementer", estimated_input_tokens=100, estimated_output_tokens=100
        )
    )

    assert decision.role == "implementer"
    assert decision.policy_constraints["allowed_providers"] == ["openai"]
    assert service.routing_profiles()[0]["version"] == "2026-07"


def test_routing_receipt_enforces_provider_residency_data_and_cost_constraints() -> None:
    primary = _model("openai", "gpt-5.4-mini")
    primary.metadata.update({"region": "us", "data_classifications": ["internal"]})
    primary.input_cost_per_million = 2.0
    primary.output_cost_per_million = 8.0
    fallback = _model("anthropic", "claude-review")
    fallback.metadata.update({"region": "eu", "data_classifications": ["confidential"]})
    fallback.input_cost_per_million = 1.0
    fallback.output_cost_per_million = 4.0
    config = OrchestrationConfig(
        roles=[Role(id="reviewer", name="Reviewer")],
        bindings=[
            RouteBinding(
                id="reviewer-primary",
                role="reviewer",
                model="openai:gpt-5.4-mini",
                fallback_chain=["anthropic:claude-review"],
            )
        ],
        settings=RoutingSettings(mode="relaxed"),
    )

    decision = _engine(config, primary, fallback).route(
        RoutingRequest(
            role="reviewer",
            allowed_providers={"anthropic"},
            allowed_regions={"eu"},
            data_classification="confidential",
            estimated_input_tokens=100_000,
            estimated_output_tokens=10_000,
            max_cost_usd=0.2,
        )
    )

    assert decision.provider == "anthropic"
    assert decision.fallback_used is True
    assert decision.receipt_version == 1
    assert decision.policy_constraints == {
        "allowed_providers": ["anthropic"],
        "allowed_regions": ["eu"],
        "allowed_data_classifications": [],
        "data_classification": "confidential",
        "estimated_input_tokens": 100_000,
        "estimated_output_tokens": 10_000,
        "max_cost_usd": 0.2,
        "policy_version": "1",
    }
    assert decision.selection_evidence["rejected"] == [
        {"model": "openai:gpt-5.4-mini", "reason": "provider_not_allowed"}
    ]


def test_cost_ceiling_requires_token_estimate() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[RouteBinding(id="worker", role="worker", model="openai:gpt-5.4-mini")],
    )

    with pytest.raises(ValueError, match="requires estimated_input_tokens"):
        _engine(config, _model("openai", "gpt-5.4-mini")).route(
            RoutingRequest(role="worker", max_cost_usd=1.0)
        )


def test_policy_bundle_is_stable_and_ed25519_verifiable() -> None:
    config = OrchestrationConfig(
        providers=[ProviderAccount(id="openai-main", provider="openai")],
        settings=RoutingSettings(allowed_providers={"openai"}, policy_version="org-2026-07"),
    )
    bundle = compile_policy_bundle(config)
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )

    token = sign_policy_bundle(bundle, kid="org-key-1", private_key_hex=private_bytes.hex())

    assert bundle["bundle_version"] == 1
    assert bundle["policy_version"] == "org-2026-07"
    assert verify_policy_bundle(bundle, token=token, public_keys={"org-key-1": public_bytes.hex()})
    assert not verify_policy_bundle(
        {**bundle, "policy_version": "tampered"},
        token=token,
        public_keys={"org-key-1": public_bytes.hex()},
    )


def test_external_secret_resolver_is_preferred_without_enumerating_its_namespace(
    tmp_path: Path,
) -> None:
    class Resolver:
        def resolve(self, reference: str) -> dict[str, Any] | None:
            return {"api_key": "managed-secret"} if reference == "vault:team/openai" else None

    fallback = EncryptedCredentialStore(tmp_path / "credentials.enc")
    fallback.put("provider:openai", {"api_key": "local-secret"})
    store = ResolverBackedCredentialStore(Resolver(), fallback=fallback)

    assert store.get("vault:team/openai") == {"api_key": "managed-secret"}
    assert store.get("provider:openai") == {"api_key": "local-secret"}
    assert store.references() == ["provider:openai"]


def test_provider_catalog_marks_private_local_deployments_explicitly() -> None:
    catalog = {spec.id: spec for spec in builtin_provider_registry().specs()}

    assert catalog["ollama"].local is True
    assert catalog["ollama"].auth_methods == ("none",)
    assert catalog["lmstudio"].local is True
    assert catalog["openai-compatible"].local is False


def test_receipt_audit_chain_is_exportable_and_detects_tampering(tmp_path: Path) -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[RouteBinding(id="worker", role="worker", model="openai:gpt-5.4-mini")],
    )
    decision = _engine(config, _model("openai", "gpt-5.4-mini")).route(
        RoutingRequest(role="worker")
    )
    audit_path = tmp_path / "receipts.jsonl"
    store = ReceiptAuditStore(audit_path, key="high-entropy-test-key")
    event = store.append(decision, execution_id="execution-1")

    assert event["receipt"]["request_id"] == decision.request_id
    assert store.verify() is True
    assert "execution-1" in store.export_jsonl()
    audit_path.write_text(
        audit_path.read_text(encoding="utf-8").replace("gpt-5.4-mini", "tampered"), encoding="utf-8"
    )
    assert store.verify() is False
    with pytest.raises(ValueError, match="refusing to append"):
        store.append(decision, execution_id="execution-2")


def test_scheduler_recommends_only_observed_verified_policy_eligible_deployments(
    tmp_path: Path,
) -> None:
    model = _model("openai", "gpt-5.4-mini", account_id="openai-main")
    config = OrchestrationConfig(
        providers=[ProviderAccount(id="openai-main", provider="openai")],
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(id="worker", role="worker", model="openai:openai-main:gpt-5.4-mini")
        ],
    )
    service = OrchestrationService(
        config_store=LayeredConfigStore(),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
    )
    service.config = config
    service.model_registry.register(model)
    service.engine = DeterministicRoutingEngine(
        config, service.model_registry, require_configured_accounts=True
    )
    for index in range(3):
        request_id = f"worker-{index}"
        service.telemetry.record(
            ExecutionRecord(
                request_id=request_id,
                requested_role="worker",
                assigned_model="openai:openai-main:gpt-5.4-mini",
                actual_model="gpt-5.4-mini",
                provider="openai",
                account_id="openai-main",
                binding_id="worker",
                routing_reason="deterministic_assignment",
                mode="strict",
                policy="role_locked",
                started_at="2026-07-13T00:00:00Z",
                task_type="implementation",
            )
        )
        service.record_outcome(
            OutcomeRecord(request_id=request_id, task_type="implementation", verified=True)
        )

    recommendation = recommend_schedule(
        service,
        RoutingRequest(role="worker", task_type="implementation", request_id="canary-1"),
        guardrails=SchedulerGuardrails(
            min_observations=3, min_quality_score=1.0, canary_sample_rate=0.5
        ),
    )

    assert recommendation["mode"] == "recommendation_only"
    assert recommendation["provider_calls"] == 0
    assert recommendation["recommendation"]["deployment"] == "openai:openai-main:gpt-5.4-mini"
    assert canary_assignment("canary-1", 0.5) is canary_assignment("canary-1", 0.5)


def test_scheduler_drift_detection_is_advisory_and_requires_two_windows() -> None:
    outcomes = OutcomeTelemetryStore()
    service = SimpleNamespace(outcome_telemetry=outcomes)
    for index in range(4):
        outcomes.record(
            OutcomeRecord(
                request_id=f"review-{index}",
                task_type="review",
                verified=index < 2,
            )
        )

    report = detect_quality_drift(service, task_type="review", window_size=2, max_quality_drop=0.4)

    assert report["mode"] == "advisory_only"
    assert report["prior_quality_score"] == 1.0
    assert report["recent_quality_score"] == 0.0
    assert report["alert"] is True
    assert (
        detect_quality_drift(service, task_type="implementation", window_size=2)["status"]
        == "insufficient_evidence"
    )


def test_offline_routing_evaluation_is_prompt_free_and_makes_no_provider_calls(
    tmp_path: Path,
) -> None:
    model = _model("openai", "gpt-5.4-mini", account_id="openai-main")
    config = OrchestrationConfig(
        providers=[ProviderAccount(id="openai-main", provider="openai")],
        roles=[Role(id="worker", name="Worker")],
        bindings=[RouteBinding(id="worker", role="worker", model="openai:gpt-5.4-mini")],
    )
    service = OrchestrationService(
        config_store=LayeredConfigStore(),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
    )
    service.config = config
    service.model_registry.register(model)
    service.engine = DeterministicRoutingEngine(
        config, service.model_registry, require_configured_accounts=True
    )

    evaluation = evaluate_routing_cases(
        service,
        [
            RoutingEvaluationCase(
                id="worker-case",
                request=RoutingRequest(role="worker", task_type="implementation"),
                candidate_model="gpt-4o",
            )
        ],
    )

    assert evaluation["provider_calls"] == 0
    assert evaluation["case_count"] == 1
    assert evaluation["results"][0]["executed"] is False


def test_strict_mode_refuses_unavailable_assignment_without_using_fallback() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="implementer", name="Implementer")],
        bindings=[
            RouteBinding(
                id="locked",
                role="implementer",
                model="kimi:kimi-2.7",
                fallback_chain=["openai:gpt-5.4-mini"],
            )
        ],
        settings=RoutingSettings(mode="strict"),
    )
    engine = _engine(
        config,
        _model("kimi", "kimi-2.7", available=False),
        _model("openai", "gpt-5.4-mini"),
    )

    with pytest.raises(RoutingUnavailableError) as error:
        engine.route(RoutingRequest(role="implementer"))

    assert error.value.assigned_model == "kimi:kimi-2.7"
    assert error.value.reason == "unavailable"


def test_request_cannot_relax_configured_strict_mode() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="strict-worker",
                role="worker",
                model="openai:model-a",
                fallback_chain=["openai:model-b"],
            )
        ],
        settings=RoutingSettings(mode="strict", policy="role_locked"),
    )
    engine = _engine(
        config,
        _model("openai", "model-a", available=False),
        _model("openai", "model-b"),
    )

    with pytest.raises(RoutingUnavailableError):
        engine.route(RoutingRequest(role="worker", mode="relaxed", policy="balanced"))

    preview = engine.route(
        RoutingRequest(role="worker", mode="relaxed", policy="balanced"),
        allow_overrides=True,
    )
    assert preview.actual_model == "model-b"
    assert preview.mode == "relaxed"


def test_relaxed_mode_uses_explicit_fallback_and_explains_why() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="implementer", name="Implementer")],
        bindings=[
            RouteBinding(
                id="relaxed",
                role="implementer",
                model="kimi:kimi-2.7",
                fallback_chain=["openai:gpt-5.4-mini"],
            )
        ],
        settings=RoutingSettings(mode="relaxed"),
    )
    engine = _engine(
        config,
        _model("kimi", "kimi-2.7", available=False),
        _model("openai", "gpt-5.4-mini"),
    )

    decision = engine.route(RoutingRequest(role="implementer"))

    assert decision.assigned_model == "kimi:kimi-2.7"
    assert decision.actual_model == "gpt-5.4-mini"
    assert decision.fallback_used is True
    assert decision.fallback_trigger == "unavailable"


def test_fallback_chain_never_revisits_a_failed_deployment() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker-chain",
                role="worker",
                model="openai:model-a",
                fallback_chain=["openai:model-b", "openai:model-c"],
            )
        ],
        settings=RoutingSettings(mode="relaxed"),
    )
    engine = _engine(
        config,
        _model("openai", "model-a"),
        _model("openai", "model-b"),
        _model("openai", "model-c"),
    )

    first = engine.route(RoutingRequest(role="worker"))
    second = engine.fallback(first, "provider_outage")
    third = engine.fallback(second, "provider_outage")

    assert [
        first.actual_model,
        second.actual_model,
        third.actual_model,
    ] == ["model-a", "model-b", "model-c"]
    with pytest.raises(RoutingUnavailableError):
        engine.fallback(third, "provider_outage")


def test_same_model_on_multiple_accounts_requires_an_exact_deployment() -> None:
    registry = DynamicModelRegistry()
    registry.register(_model("openai", "shared-model"))
    registry.register(_model("openai", "shared-model", account_id="account-a"))
    registry.register(_model("openai", "shared-model", account_id="account-b"))
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker-account-a",
                role="worker",
                model="openai:account-a:shared-model",
            )
        ],
    )

    assert registry.get("openai:shared-model") is None
    assert len([model for model in registry.list() if model.id == "shared-model"]) == 2
    decision = DeterministicRoutingEngine(config, registry).route(RoutingRequest(role="worker"))
    assert decision.account_id == "account-a"


def test_explicit_equivalent_deployments_select_best_reliability_in_strict_mode() -> None:
    primary = _model("openai", "shared-model", account_id="account-a")
    primary.latency_ms = 900
    primary.metadata.update(
        {"health_score": 0.8, "rate_limit_headroom": 0.2, "budget_headroom": 0.7}
    )
    equivalent = _model("openai", "shared-model", account_id="account-b")
    equivalent.latency_ms = 120
    equivalent.metadata.update(
        {"health_score": 0.99, "rate_limit_headroom": 0.9, "budget_headroom": 0.9}
    )
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker-equivalents",
                role="worker",
                model="openai:account-a:shared-model",
                equivalent_deployments=["openai:account-b:shared-model"],
            )
        ],
        settings=RoutingSettings(mode="strict"),
    )
    engine = _engine(config, primary, equivalent)

    decision = engine.route(RoutingRequest(role="worker"))

    assert decision.actual_model == "shared-model"
    assert decision.account_id == "account-b"
    assert decision.fallback_used is False
    assert decision.reason == "equivalent_deployment_selected"
    assert decision.selection_evidence["strategy"] == "equivalent_reliability"
    assert decision.selection_evidence["selected"] == "openai:account-b:shared-model"


def test_weighted_equivalents_are_stable_and_cover_each_positive_weight_target() -> None:
    primary = _model("openai", "shared", account_id="account-a")
    equivalent = _model("openai", "shared", account_id="account-b")
    binding = RouteBinding(
        id="worker",
        role="worker",
        model=primary.deployment_key,
        equivalent_deployments=[equivalent.deployment_key],
        equivalent_deployment_weights={
            primary.deployment_key: 1.0,
            equivalent.deployment_key: 1.0,
        },
    )
    engine = _engine(
        OrchestrationConfig(roles=[Role(id="worker", name="Worker")], bindings=[binding]),
        primary,
        equivalent,
    )

    repeated = [
        engine.route(RoutingRequest(role="worker", request_id="stable")).account_id for _ in range(2)
    ]
    selected = {
        engine.route(RoutingRequest(role="worker", request_id=f"cohort-{index}")).account_id
        for index in range(100)
    }

    assert repeated == [repeated[0], repeated[0]]
    assert selected == {"account-a", "account-b"}
    assert (
        engine.route(RoutingRequest(role="worker", request_id="stable")).selection_evidence["strategy"]
        == "equivalent_weighted"
    )


def test_weighted_selection_excludes_a_cooled_deployment() -> None:
    primary = _model("openai", "shared", account_id="account-a")
    equivalent = _model("openai", "shared", account_id="account-b")
    registry = DynamicModelRegistry()
    registry.register(primary)
    registry.register(equivalent)
    registry.cool_down(primary.deployment_key, 30)
    binding = RouteBinding(
        id="worker",
        role="worker",
        model=primary.deployment_key,
        equivalent_deployments=[equivalent.deployment_key],
        equivalent_deployment_weights={
            primary.deployment_key: 1.0,
            equivalent.deployment_key: 1.0,
        },
    )
    engine = DeterministicRoutingEngine(
        OrchestrationConfig(roles=[Role(id="worker", name="Worker")], bindings=[binding]),
        registry,
    )

    decision = engine.route(RoutingRequest(role="worker", request_id="cooled"))

    assert decision.account_id == "account-b"
    assert decision.selection_evidence["strategy"] == "equivalent_weighted"
    assert {"model": primary.deployment_key, "reason": "cooling_down"} in decision.selection_evidence["rejected"]


def test_equivalent_set_cannot_substitute_a_different_model() -> None:
    primary = _model("openai", "model-a", account_id="account-a", available=False)
    different = _model("openai", "model-b", account_id="account-b")
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="invalid-equivalent",
                role="worker",
                model="openai:account-a:model-a",
                equivalent_deployments=["openai:account-b:model-b"],
            )
        ],
        settings=RoutingSettings(mode="strict"),
    )
    engine = _engine(config, primary, different)

    with pytest.raises(RoutingUnavailableError) as error:
        engine.route(RoutingRequest(role="worker"))

    assert error.value.reason == "unavailable"


def test_binding_rejects_invalid_or_non_equivalent_deployment_weights(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.bindings[0].equivalent_deployment_weights = {
        "anthropic:anthropic-main:claude-worker": 1.0
    }

    with pytest.raises(ValueError, match="equivalent deployment weights"):
        service.replace_config(service.config)


def test_unavailable_primary_can_use_explicit_same_model_equivalent_but_not_fallback() -> None:
    primary = _model("openai", "shared-model", account_id="account-a", available=False)
    equivalent = _model("openai", "shared-model", account_id="account-b")
    fallback = _model("anthropic", "different-model")
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker-equivalents",
                role="worker",
                model="openai:account-a:shared-model",
                equivalent_deployments=["openai:account-b:shared-model"],
                fallback_chain=["anthropic:different-model"],
            )
        ],
        settings=RoutingSettings(mode="strict"),
    )
    decision = _engine(config, primary, equivalent, fallback).route(RoutingRequest(role="worker"))

    assert decision.account_id == "account-b"
    assert decision.fallback_used is False
    assert decision.provider == "openai"


def test_runtime_signal_updates_are_bounded_atomic_and_change_equivalent_selection() -> None:
    registry = DynamicModelRegistry()
    registry.register(_model("openai", "shared-model", account_id="account-a"))
    registry.register(_model("openai", "shared-model", account_id="account-b"))
    registry.update_runtime_signals(
        "openai:account-a:shared-model",
        health_score=0.7,
        latency_ms=700,
        rate_limit_headroom=0.1,
        budget_headroom=0.1,
    )
    updated = registry.update_runtime_signals(
        "openai:account-b:shared-model",
        health_score=2.0,
        latency_ms=80,
        rate_limit_headroom=5.0,
        budget_headroom=0.8,
    )
    assert updated.metadata["health_score"] == 1.0
    assert updated.metadata["rate_limit_headroom"] == 1.0

    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="runtime-ranked",
                role="worker",
                model="openai:account-a:shared-model",
                equivalent_deployments=["openai:account-b:shared-model"],
            )
        ],
    )
    decision = DeterministicRoutingEngine(config, registry).route(RoutingRequest(role="worker"))
    assert decision.account_id == "account-b"

    with pytest.raises(ValueError, match="finite"):
        registry.update_runtime_signals("openai:account-b:shared-model", health_score=float("nan"))


def test_registry_cooldown_is_deployment_scoped_persisted_and_expires(tmp_path: Path) -> None:
    cache = tmp_path / "models.json"
    registry = DynamicModelRegistry(cache)
    registry.register_many(
        [
            _model("openai", "shared", account_id="account-a"),
            _model("openai", "shared", account_id="account-b"),
        ]
    )

    registry.cool_down("openai:account-a:shared", 30, now=100.0)

    assert registry.cooldown_remaining_seconds("openai:account-a:shared", now=110.0) == 20.0
    assert registry.cooldown_remaining_seconds("openai:account-b:shared", now=110.0) is None
    restored = DynamicModelRegistry(cache)
    assert restored.cooldown_remaining_seconds("openai:account-a:shared", now=110.0) == 20.0
    assert restored.cooldown_remaining_seconds("openai:account-a:shared", now=131.0) is None


def test_cooling_primary_selects_declared_same_model_equivalent_in_strict_mode() -> None:
    primary = _model("openai", "shared", account_id="account-a")
    equivalent = _model("openai", "shared", account_id="account-b")
    registry = DynamicModelRegistry()
    registry.register(primary)
    registry.register(equivalent)
    registry.cool_down(primary.deployment_key, 30)
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker",
                role="worker",
                model=primary.deployment_key,
                equivalent_deployments=[equivalent.deployment_key],
            )
        ],
        settings=RoutingSettings(mode="strict"),
    )

    decision = DeterministicRoutingEngine(config, registry).route(RoutingRequest(role="worker"))

    assert decision.account_id == "account-b"
    assert {"model": primary.deployment_key, "reason": "cooling_down"} in decision.selection_evidence["rejected"]


def test_malformed_cached_runtime_signals_use_safe_defaults() -> None:
    primary = _model("openai", "shared-model", account_id="account-a")
    primary.metadata.update({"health_score": "not-a-number", "rate_limit_headroom": None})
    equivalent = _model("openai", "shared-model", account_id="account-b")
    equivalent.metadata.update({"health_score": 0.5, "rate_limit_headroom": 0.5})
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="safe-defaults",
                role="worker",
                model="openai:account-a:shared-model",
                equivalent_deployments=["openai:account-b:shared-model"],
            )
        ],
    )

    decision = _engine(config, primary, equivalent).route(RoutingRequest(role="worker"))
    assert decision.actual_model == "shared-model"
    assert decision.selection_evidence["scores"]
    assert decision.actual_model == "shared-model"
    assert decision.fallback_used is False
    assert decision.fallback_trigger is None


def test_agent_binding_deterministically_overrides_role_binding() -> None:
    config = OrchestrationConfig(
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(id="role-default", role="worker", model="openai:gpt-5.4-mini"),
            RouteBinding(
                id="frontend-agent",
                role="worker",
                selectors={"agent": "frontend"},
                model="google:gemini-2.5-pro",
            ),
        ],
    )
    engine = _engine(
        config,
        _model("openai", "gpt-5.4-mini"),
        _model("google", "gemini-2.5-pro"),
    )

    decision = engine.route(RoutingRequest(role="worker", selectors={"agent": "frontend"}))

    assert decision.binding_id == "frontend-agent"
    assert decision.provider == "google"


def test_capability_check_never_infers_support_from_model_name() -> None:
    config = OrchestrationConfig(
        roles=[
            Role(
                id="visual",
                name="Visual Auditor",
                required_capabilities={Capability.VISION.value},
            )
        ],
        bindings=[RouteBinding(id="visual-model", role="visual", model="custom:looks-visual")],
    )
    engine = _engine(
        config,
        _model(
            "custom",
            "looks-visual",
            capabilities={Capability.STREAMING.value},
        ),
    )

    with pytest.raises(RoutingUnavailableError) as error:
        engine.route(RoutingRequest(role="visual"))

    assert error.value.reason == "unsupported_capabilities"


def test_layered_config_merges_entities_by_id_and_round_trips(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        '{"version":1,"roles":[{"id":"worker","name":"Worker"}],"settings":{"mode":"strict"}}',
        encoding="utf-8",
    )
    project_path.write_text(
        '{"version":1,"roles":[{"id":"worker","name":"Fast Worker"}],'
        '"settings":{"policy":"cheapest"}}',
        encoding="utf-8",
    )
    store = LayeredConfigStore({"global": global_path, "project": project_path})

    config = store.load()

    assert config.roles[0].name == "Fast Worker"
    assert config.settings.mode == "strict"
    assert config.settings.policy == "cheapest"
    store.save(config)
    assert store.load() == config


def test_layered_policy_allow_lists_can_only_narrow(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        json.dumps(
            {
                "version": 1,
                "settings": {
                    "allowed_providers": ["openai", "anthropic"],
                    "allowed_regions": ["eu", "us"],
                    "allowed_data_classifications": ["internal", "confidential"],
                    "policy_version": "org-2026-07",
                },
            }
        ),
        encoding="utf-8",
    )
    project_path.write_text(
        json.dumps(
            {
                "version": 1,
                "settings": {
                    "allowed_providers": ["anthropic", "google"],
                    "allowed_regions": ["eu"],
                    "allowed_data_classifications": ["confidential"],
                },
            }
        ),
        encoding="utf-8",
    )

    config = LayeredConfigStore({"global": global_path, "project": project_path}).load()

    assert config.settings.allowed_providers == {"anthropic"}
    assert config.settings.allowed_regions == {"eu"}
    assert config.settings.allowed_data_classifications == {"confidential"}
    assert config.settings.policy_version == "org-2026-07"


def test_service_policy_defaults_cannot_be_broadened_by_request(tmp_path: Path) -> None:
    config_path = tmp_path / "global.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": [{"id": "anthropic-main", "provider": "anthropic"}],
                "roles": [{"id": "reviewer", "name": "Reviewer"}],
                "bindings": [{"id": "reviewer", "role": "reviewer", "model": "anthropic:review"}],
                "settings": {
                    "allowed_providers": ["anthropic"],
                    "allowed_regions": ["eu"],
                    "allowed_data_classifications": ["confidential"],
                    "policy_version": "org-7",
                },
            }
        ),
        encoding="utf-8",
    )
    model = _model("anthropic", "review", account_id="anthropic-main")
    model.metadata.update(
        {
            "region": "eu",
            "data_classifications": ["confidential"],
            "capability_verified": True,
            "capability_verified_at": "2026-07-13T00:00:00Z",
        }
    )
    service = OrchestrationService(
        config_store=LayeredConfigStore({"global": config_path}),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
    )
    service.model_registry.register(model)

    decision = service.route(RoutingRequest(role="reviewer", data_classification="confidential"))

    assert decision.policy_constraints["allowed_providers"] == ["anthropic"]
    assert decision.policy_constraints["policy_version"] == "org-7"
    with pytest.raises(ValueError, match="do not satisfy"):
        service.route(RoutingRequest(role="reviewer", allowed_providers={"openai"}))


def test_layered_config_keeps_same_model_from_multiple_accounts(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        '{"version":1,"models":[{"provider":"openai","account_id":"a","id":"shared"}]}',
        encoding="utf-8",
    )
    project_path.write_text(
        '{"version":1,"models":[{"provider":"openai","account_id":"b","id":"shared"}]}',
        encoding="utf-8",
    )

    config = LayeredConfigStore({"global": global_path, "project": project_path}).load()

    assert {model.deployment_key for model in config.models} == {
        "openai:a:shared",
        "openai:b:shared",
    }


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (RoutingSettings(mode="unsafe"), "Unknown orchestration mode"),
        (RoutingSettings(policy="random"), "Unknown routing policy"),
        (RoutingSettings(retries=11), "retries"),
        (RoutingSettings(timeout_seconds=float("inf")), "timeout_seconds"),
        (RoutingSettings(deployment_cooldown_seconds=0), "deployment_cooldown_seconds"),
        (RoutingSettings(fallback_triggers={"invented"}), "fallback triggers"),
    ],
)
def test_invalid_routing_settings_are_rejected(
    tmp_path: Path,
    settings: RoutingSettings,
    message: str,
) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    invalid = OrchestrationConfig(
        providers=service.config.providers,
        roles=service.config.roles,
        bindings=service.config.bindings,
        settings=settings,
    )

    with pytest.raises(ValueError, match=message):
        service.replace_config(invalid)


def test_sensitive_custom_headers_must_use_encrypted_credentials(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.providers[0].custom_headers = {"authorization": "Bearer plaintext"}

    with pytest.raises(ValueError, match="encrypted credential payload"):
        service.replace_config(service.config)


def test_config_rejects_known_equivalent_that_changes_model_identity(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    invalid = OrchestrationConfig(
        providers=service.config.providers,
        models=[
            _model("openai", "model-a", account_id="openai-main"),
            _model("openai", "model-b", account_id="openai-main"),
        ],
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="bad-equivalence",
                role="worker",
                model="openai:openai-main:model-a",
                equivalent_deployments=["openai:openai-main:model-b"],
            )
        ],
    )

    with pytest.raises(ValueError, match="changes model identity"):
        service.replace_config(invalid)


def test_replace_config_validates_effective_layers_before_persisting(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        '{"version":1,"providers":[{"id":"main","provider":"openai"}]}',
        encoding="utf-8",
    )
    service = OrchestrationService(
        config_store=LayeredConfigStore({"global": global_path, "project": project_path}),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
        provider_registry=builtin_provider_registry(),
        telemetry=ExecutionTelemetryStore(),
    )
    global_path.write_text(
        '{"version":1,"providers":[{"id":"bad","provider":"unknown"}]}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown provider"):
        service.replace_config(OrchestrationConfig())
    assert not project_path.exists()


def test_replace_config_prunes_models_removed_from_configuration(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    configured = _model("openai", "temporary", account_id="openai-main")
    first = copy.deepcopy(service.config)
    first.models = [configured]
    service.replace_config(first)
    assert service.model_registry.get(configured.deployment_key) is not None

    second = copy.deepcopy(first)
    second.models = []
    service.replace_config(second)

    assert service.model_registry.get(configured.deployment_key) is None


def test_credentials_are_encrypted_and_support_multiple_accounts(tmp_path: Path) -> None:
    store = EncryptedCredentialStore(tmp_path / "credentials.enc")

    store.put("provider:one", {"api_key": "secret-one"})
    store.put("provider:two", {"api_key": "secret-two", "headers": {"x-org": "acme"}})

    encrypted = (tmp_path / "credentials.enc").read_bytes()
    assert b"secret-one" not in encrypted
    assert b"secret-two" not in encrypted
    assert store.references() == ["provider:one", "provider:two"]
    assert store.get("provider:two") == {
        "api_key": "secret-two",
        "headers": {"x-org": "acme"},
    }
    assert oct((tmp_path / "credentials.key").stat().st_mode & 0o777) == "0o600"


def test_credential_write_preserves_layered_config_boundaries(tmp_path: Path) -> None:
    global_path = tmp_path / "global.json"
    project_path = tmp_path / "project.json"
    global_path.write_text(
        json.dumps(
            {
                "version": 1,
                "providers": [
                    {"id": "shared-openai", "provider": "openai", "display_name": "Shared"}
                ],
                "settings": {"mode": "strict"},
            }
        ),
        encoding="utf-8",
    )
    service = OrchestrationService(
        config_store=LayeredConfigStore({"global": global_path, "project": project_path}),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
        provider_registry=builtin_provider_registry(),
        telemetry=ExecutionTelemetryStore(),
    )

    assert service.put_credential("shared-openai", {"api_key": "test-secret"}, layer="project") == (
        "provider:shared-openai"
    )

    assert json.loads(project_path.read_text(encoding="utf-8")) == {
        "version": 1,
        "providers": [{"id": "shared-openai", "credential_ref": "provider:shared-openai"}],
    }
    assert service.config.providers[0].provider == "openai"
    assert service.config.providers[0].credential_ref == "provider:shared-openai"
    assert service.config.settings.mode == "strict"


def test_provider_accounts_and_credentials_persist_across_restarts(
    tmp_path: Path, monkeypatch
) -> None:
    state_dir = tmp_path / "state"
    workspace_a = tmp_path / "workspace-a"
    workspace_b = tmp_path / "workspace-b"
    workspace_a.mkdir()
    workspace_b.mkdir()

    monkeypatch.chdir(workspace_a)
    service = build_orchestration_service(data_dir=state_dir)
    account_id = "openai-main"

    stored_account = service.put_account(
        account_id,
        {
            "provider": "openai",
            "display_name": "Primary OpenAI",
            "base_url": "https://api.openai.com/v1",
        },
    )
    reference = service.put_credential(account_id, {"api_key": "persist-me"})

    assert stored_account["id"] == account_id
    assert reference == "provider:openai-main"
    assert (
        json.loads((state_dir / "user.json").read_text(encoding="utf-8"))["providers"][0][
            "credential_ref"
        ]
        == reference
    )
    assert not (workspace_a / ".cutctx" / "orchestration.json").exists()

    monkeypatch.chdir(workspace_b)
    restarted = build_orchestration_service(data_dir=state_dir)

    assert restarted.accounts() == [
        {
            "id": account_id,
            "provider": "openai",
            "display_name": "Primary OpenAI",
            "auth_method": "api_key",
            "credential_ref": reference,
            "base_url": "https://api.openai.com/v1",
            "organization_id": None,
            "workspace_id": None,
            "custom_headers": {},
            "enabled": True,
            "metadata": {},
            "credential_configured": True,
        }
    ]


@pytest.mark.asyncio
async def test_provider_adapter_validates_credentials_discovers_models_and_invokes() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "dynamic-model",
                            "capabilities": ["vision", "tool_calling", "streaming"],
                            "context_length": 200000,
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    transport = httpx.MockTransport(respond)
    adapter = HTTPProviderAdapter(
        ProviderSpec(
            "custom-provider",
            "Custom Provider",
            default_base_url="https://provider.test",
        ),
        ProviderAccount(id="custom-main", provider="custom-provider"),
        {"api_key": "valid-key"},
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
    )

    health = await adapter.authenticate()
    models = await adapter.refresh_models()
    response = await adapter.invoke(
        {"model": "dynamic-model", "messages": [{"role": "user", "content": "hi"}]}
    )

    assert health.ok is True
    assert models[0].key == "custom-provider:dynamic-model"
    assert models[0].supports({"vision", "tool_calling"})
    assert response["choices"][0]["message"]["content"] == "ok"
    assert all(request.headers["authorization"] == "Bearer valid-key" for request in requests)


@pytest.mark.asyncio
async def test_provider_adapter_reports_invalid_credentials_without_leaking_key() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(401, text="invalid credential"))
    adapter = HTTPProviderAdapter(
        ProviderSpec("custom-provider", "Custom", default_base_url="https://provider.test"),
        ProviderAccount(id="custom-main", provider="custom-provider"),
        {"api_key": "do-not-leak"},
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
    )

    health = await adapter.authenticate()

    assert health.ok is False
    assert health.status == "authentication_failed"
    assert "do-not-leak" not in (health.detail or "")


@pytest.mark.asyncio
async def test_openai_compatible_api_base_does_not_duplicate_version_prefix() -> None:
    seen_urls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json={"data": []})

    adapter = HTTPProviderAdapter(
        ProviderSpec("external-gateway", "External Gateway"),
        ProviderAccount(
            id="gateway-main",
            provider="external-gateway",
            base_url="http://gateway.internal:8080/v1",
        ),
        None,
        client_factory=lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )

    await adapter.refresh_models()

    assert seen_urls == ["http://gateway.internal:8080/v1/models"]


class _DumpableResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return self.payload


@pytest.mark.asyncio
async def test_litellm_adapter_normalizes_provider_and_protects_account_auth() -> None:
    calls: list[dict[str, Any]] = []

    async def completion(**kwargs: Any) -> _DumpableResponse:
        calls.append(kwargs)
        return _DumpableResponse(
            {
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            }
        )

    adapter = LiteLLMProviderAdapter(
        ProviderSpec(
            "openrouter",
            "OpenRouter",
            default_base_url="https://openrouter.ai/api",
            litellm_provider="openrouter",
        ),
        ProviderAccount(
            id="openrouter-main",
            provider="openrouter",
            base_url="https://gateway.example/v1",
            organization_id="org-1",
            custom_headers={"x-workspace": "acme"},
        ),
        {"api_key": "stored-key", "headers": {"x-account": "primary"}},
        completion_fn=completion,
    )

    response = await adapter.invoke(
        {
            "model": "anthropic/claude-sonnet-4",
            "messages": [{"role": "user", "content": "hello"}],
            "api_key": "request-must-not-override-storage",
            "base_url": "https://attacker.invalid",
        }
    )

    assert response["choices"][0]["message"]["content"] == "ok"
    assert calls == [
        {
            "messages": [{"role": "user", "content": "hello"}],
            "model": "openrouter/anthropic/claude-sonnet-4",
            "stream": False,
            "num_retries": 0,
            "fallbacks": [],
            "api_key": "stored-key",
            "base_url": "https://gateway.example/v1",
            "organization": "org-1",
            "extra_headers": {"x-workspace": "acme", "x-account": "primary"},
        }
    ]


@pytest.mark.asyncio
async def test_litellm_adapter_rejects_hidden_runtime_controls() -> None:
    async def completion(**kwargs: Any) -> _DumpableResponse:
        raise AssertionError("Completion must not be called for invalid parameters")

    adapter = LiteLLMProviderAdapter(
        ProviderSpec("custom", "Custom", litellm_provider="openai"),
        ProviderAccount(id="custom-main", provider="custom"),
        {"api_key": "stored-key"},
        completion_fn=completion,
    )

    with pytest.raises(ValueError, match="mock_response"):
        await adapter.invoke(
            {
                "model": "model-a",
                "messages": [{"role": "user", "content": "hello"}],
                "mock_response": "spoofed",
            }
        )


@pytest.mark.asyncio
async def test_litellm_adapter_uses_only_stored_cloud_runtime_fields() -> None:
    calls: list[dict[str, Any]] = []

    async def completion(**kwargs: Any) -> _DumpableResponse:
        calls.append(kwargs)
        return _DumpableResponse({"choices": []})

    adapter = LiteLLMProviderAdapter(
        ProviderSpec("bedrock", "Bedrock", litellm_provider="bedrock"),
        ProviderAccount(
            id="bedrock-main",
            provider="bedrock",
            metadata={"litellm": {"aws_region_name": "us-east-1"}},
        ),
        {},
        completion_fn=completion,
    )

    await adapter.invoke(
        {
            "model": "anthropic.claude-model",
            "messages": [{"role": "user", "content": "hello"}],
            "aws_region_name": "attacker-region-1",
        }
    )

    assert calls[0]["aws_region_name"] == "us-east-1"
    assert "attacker-region-1" not in str(calls[0])


@pytest.mark.asyncio
async def test_litellm_adapter_requires_explicit_environment_credential_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "process-global-key")
    adapter = LiteLLMProviderAdapter(
        ProviderSpec(
            "openai",
            "OpenAI",
            api_key_env="OPENAI_API_KEY",
            litellm_provider="openai",
        ),
        ProviderAccount(id="openai-main", provider="openai"),
        None,
        completion_fn=lambda **kwargs: None,
    )

    with pytest.raises(ValueError, match="no explicit credential"):
        await adapter.invoke(
            {
                "model": "gpt-model",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )


@pytest.mark.asyncio
async def test_google_discovery_normalizes_models_prefix() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"models": [{"name": "models/gemini-2.5-pro"}]},
        )
    )
    adapter = LiteLLMProviderAdapter(
        ProviderSpec(
            "google",
            "Google",
            api_style="google",
            default_base_url="https://provider.test",
            models_path="/v1beta/models",
            litellm_provider="gemini",
        ),
        ProviderAccount(id="google-main", provider="google"),
        None,
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
        model_info_fn=lambda *args, **kwargs: {},
        supported_params_fn=lambda *args, **kwargs: [],
    )

    models = await adapter.refresh_models()

    assert models[0].id == "gemini-2.5-pro"
    assert models[0].metadata["runtime_model"] == "gemini/gemini-2.5-pro"


@pytest.mark.asyncio
async def test_litellm_adapter_streams_openai_sse() -> None:
    async def completion(**kwargs: Any) -> AsyncIterator[_DumpableResponse]:
        assert kwargs["model"] == "openai/gpt-5.4-mini"
        assert kwargs["stream"] is True

        async def chunks() -> AsyncIterator[_DumpableResponse]:
            yield _DumpableResponse({"choices": [{"delta": {"content": "hello"}, "index": 0}]})

        return chunks()

    adapter = LiteLLMProviderAdapter(
        ProviderSpec("openai", "OpenAI", litellm_provider="openai"),
        ProviderAccount(id="openai-main", provider="openai"),
        {"api_key": "key"},
        completion_fn=completion,
    )

    chunks = [
        chunk
        async for chunk in adapter.stream(
            {
                "model": "gpt-5.4-mini",
                "messages": [{"role": "user", "content": "hello"}],
            }
        )
    ]

    assert chunks[-1] == b"data: [DONE]\n\n"
    assert b'"content": "hello"' in chunks[0]


@pytest.mark.asyncio
async def test_litellm_metadata_enriches_discovered_models_by_capability() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"id": "model-a"}]})
    )
    adapter = LiteLLMProviderAdapter(
        ProviderSpec(
            "openrouter",
            "OpenRouter",
            default_base_url="https://provider.test",
            litellm_provider="openrouter",
        ),
        ProviderAccount(id="openrouter-main", provider="openrouter"),
        {"api_key": "key"},
        client_factory=lambda **kwargs: httpx.AsyncClient(transport=transport, **kwargs),
        model_info_fn=lambda *args, **kwargs: {
            "max_input_tokens": 200_000,
            "max_output_tokens": 8_192,
            "input_cost_per_token": 0.000001,
            "output_cost_per_token": 0.000003,
            "supports_reasoning": True,
            "supports_vision": True,
        },
        supported_params_fn=lambda *args, **kwargs: [
            "tools",
            "response_format",
            "stream",
        ],
    )

    models = await adapter.refresh_models()

    assert models[0].capabilities >= {
        "reasoning",
        "vision",
        "tool_calling",
        "json_mode",
        "structured_outputs",
        "streaming",
        "long_context",
    }
    assert models[0].input_cost_per_million == 1.0
    assert models[0].output_cost_per_million == 3.0
    assert models[0].metadata["runtime_model"] == "openrouter/model-a"


def test_builtin_provider_registry_uses_litellm_runtime() -> None:
    registry = builtin_provider_registry()

    adapter = registry.create(
        ProviderAccount(id="google-main", provider="google"),
        {"api_key": "key"},
    )

    assert isinstance(adapter, LiteLLMProviderAdapter)
    assert adapter._runtime_model("gemini-2.5-pro") == "gemini/gemini-2.5-pro"


def test_builtin_provider_registry_exposes_opencode_go_gateway() -> None:
    registry = builtin_provider_registry()
    spec = next(item for item in registry.specs() if item.id == "opencode-go")
    adapter = registry.create(
        ProviderAccount(id="opencode-go-main", provider="opencode-go"),
        {"api_key": "key"},
    )

    assert spec.display_name == "OpenCode Go"
    assert spec.default_base_url == "https://opencode.ai/zen/go/v1"
    assert isinstance(adapter, LiteLLMProviderAdapter)
    assert adapter._runtime_model("deepseek-v4-flash") == "openai/deepseek-v4-flash"


def test_litellm_status_codes_map_to_configured_fallback_triggers() -> None:
    class LiteLLMRateLimitError(Exception):
        status_code = 429

    assert OrchestrationService._classify_failure(LiteLLMRateLimitError()) == "rate_limit"


def test_direct_execution_route_is_explicitly_opt_in(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})

    default_paths = {route.path for route in create_orchestration_router(service).routes}
    enabled_paths = {
        route.path
        for route in create_orchestration_router(
            service,
            enable_direct_execution=True,
        ).routes
    }

    assert "/v1/orchestration/execute" not in default_paths
    assert "/v1/orchestration/execute" in enabled_paths
    assert "/v1/orchestration/workflows/{workflow_id}/run" not in default_paths
    assert "/v1/orchestration/workflows/{workflow_id}/run" in enabled_paths


@pytest.mark.asyncio
async def test_workflow_execution_uses_role_bound_service_and_persists_output(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, {"openai": {"answer": "implemented"}, "anthropic": {}})
    store = WorkflowStateStore(tmp_path / "workflows.json")
    spec = WorkflowSpec(
        id="implementation",
        tasks=[
            TaskSpec(
                id="implement",
                role="worker",
                payload={"messages": [{"role": "user", "content": "implement it"}]},
            )
        ],
    )
    workflow = store.submit(spec)

    state = await service.run_workflow(store, workflow.id, spec)

    assert state.status == "completed"
    assert state.tasks["implement"].result["routing"]["actual_model"] == "gpt-5.4-mini"
    assert state.tasks["implement"].result["response"] == {"answer": "implemented"}


class _FakeAdapter:
    def __init__(
        self,
        spec: ProviderSpec,
        account: ProviderAccount,
        credential: dict[str, Any] | None,
        behavior: dict[str, Any],
    ) -> None:
        self.spec = spec
        self.account = account
        self.credential = credential
        self.behavior = behavior

    async def authenticate(self) -> ProviderHealth:
        return ProviderHealth(True, "healthy", 1.0)

    async def health(self) -> ProviderHealth:
        return await self.authenticate()

    async def list_models(self) -> list[ModelRecord]:
        return await self.refresh_models()

    async def refresh_models(self) -> list[ModelRecord]:
        return [
            _model(
                self.account.provider, f"{self.account.provider}-model", account_id=self.account.id
            )
        ]

    async def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        outcome = self.behavior[self.account.provider]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def stream(self, request: dict[str, Any]) -> AsyncIterator[bytes]:
        outcome = self.behavior[self.account.provider]
        if isinstance(outcome, Exception):
            raise outcome
        yield f"{self.account.provider}:one".encode()
        yield b":two"

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> None:
        return None

    def estimate_latency(self, model: str) -> None:
        return None

    def capabilities(self, model: str) -> set[str]:
        return {Capability.STREAMING.value}


def _service(tmp_path: Path, behavior: dict[str, Any]) -> OrchestrationService:
    providers = ProviderAdapterRegistry()
    for provider in behavior:
        spec = ProviderSpec(provider, provider.title())
        providers.register(
            spec,
            lambda spec, account, credential, behavior=behavior: _FakeAdapter(
                spec, account, credential, behavior
            ),
        )
    service = OrchestrationService(
        config_store=LayeredConfigStore({"project": tmp_path / "config.json"}),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=DynamicModelRegistry(),
        provider_registry=providers,
        telemetry=ExecutionTelemetryStore(),
    )
    config = OrchestrationConfig(
        providers=[
            ProviderAccount(id="openai-main", provider="openai"),
            ProviderAccount(id="anthropic-main", provider="anthropic"),
        ],
        roles=[Role(id="worker", name="Worker")],
        bindings=[
            RouteBinding(
                id="worker-route",
                role="worker",
                model="openai:gpt-5.4-mini",
                fallback_chain=["anthropic:claude-worker"],
            )
        ],
        settings=RoutingSettings(mode="relaxed", retries=0),
    )
    service.model_registry.register(_model("openai", "gpt-5.4-mini", account_id="openai-main"))
    service.model_registry.register(
        _model("anthropic", "claude-worker", account_id="anthropic-main")
    )
    service.replace_config(config)
    return service


@pytest.mark.asyncio
async def test_execution_retries_provider_failure_through_configured_fallback(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path,
        {
            "openai": httpx.ReadTimeout("timeout"),
            "anthropic": {"content": [{"text": "ok"}], "usage": {"input_tokens": 4}},
        },
    )

    decision, response = await service.execute(
        RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
    )

    assert decision.provider == "anthropic"
    assert decision.fallback_used is True
    assert decision.fallback_trigger == "provider_outage"
    assert response["content"][0]["text"] == "ok"
    assert service.telemetry.list()[0]["actual_model"] == "claude-worker"


@pytest.mark.asyncio
async def test_retry_exhausted_failure_cools_only_failed_deployment_and_next_route_avoids_it(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path,
        {
            "openai": httpx.ReadTimeout("timeout"),
            "anthropic": {"content": []},
        },
    )
    service.config.settings.retries = 0
    service.config.settings.deployment_cooldown_seconds = 30

    decision, _response = await service.execute(RoutingRequest(role="worker"), messages=[])

    assert decision.provider == "anthropic"
    assert (
        service.model_registry.cooldown_remaining_seconds("openai:openai-main:gpt-5.4-mini")
        is not None
    )
    assert service.route(RoutingRequest(role="worker")).provider == "anthropic"


@pytest.mark.asyncio
async def test_execution_parameters_cannot_override_the_enforced_route(
    tmp_path: Path,
) -> None:
    service = _service(
        tmp_path,
        {"openai": {"choices": [{"message": {"content": "ok"}}]}, "anthropic": {}},
    )

    with pytest.raises(ValueError, match="model, provider"):
        await service.execute(
            RoutingRequest(role="worker"),
            messages=[{"role": "user", "content": "hello"}],
            parameters={"model": "attacker-model", "provider": "attacker"},
        )


def test_management_views_redact_custom_header_values(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.providers[0].custom_headers = {
        "authorization": "Bearer secret",
        "x-tenant": "private-tenant",
    }

    account = service.accounts()[0]
    public_config = service.public_config()

    assert account["custom_headers"] == {
        "authorization": "********",
        "x-tenant": "********",
    }
    assert "Bearer secret" not in str(public_config)


def test_provider_health_only_changes_the_matching_account_models() -> None:
    registry = DynamicModelRegistry()
    registry.register(_model("openai", "model-a", account_id="account-a"))
    registry.register(_model("openai", "model-a", account_id="account-b"))

    registry.mark_provider_available("openai", False, account_id="account-a")

    account_a = registry.get("openai:account-a:model-a")
    account_b = registry.get("openai:account-b:model-a")
    assert account_a is not None and account_a.available is False
    assert account_b is not None and account_b.available is True


@pytest.mark.asyncio
async def test_account_health_probe_updates_reliability_and_latency_signals(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    await service.refresh_models("openai-main")
    service.model_registry.cool_down("openai:openai-main:openai-model", 30)

    result = await service.test_account("openai-main")
    model = service.model_registry.get("openai:openai-main:openai-model")

    assert result["ok"] is True
    assert model is not None
    assert model.available is True
    assert model.reliability == 1.0
    assert model.latency_ms == pytest.approx(1.0)
    assert model.metadata["health_score"] == 1.0
    assert service.model_registry.cooldown_remaining_seconds(model.deployment_key) is None


def test_disabled_explicit_provider_account_cannot_execute(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    decision = service.route(RoutingRequest(role="worker"))
    service.config.providers[0].enabled = False

    with pytest.raises(RoutingUnavailableError) as error:
        service._execution_account(decision)

    assert error.value.reason == "unavailable"


def test_execution_telemetry_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "executions.jsonl"
    store = ExecutionTelemetryStore(path)
    store.record(
        ExecutionRecord(
            request_id="request-1",
            requested_role="worker",
            assigned_model="openai:model-a",
            actual_model="model-a",
            provider="openai",
            account_id="openai-main",
            binding_id="worker-route",
            routing_reason="deterministic_assignment",
            mode="strict",
            policy="role_locked",
            started_at="2026-07-10T00:00:00+00:00",
        )
    )

    reloaded = ExecutionTelemetryStore(path)

    assert reloaded.list()[0]["request_id"] == "request-1"


def test_execution_telemetry_redacts_upstream_credentials(tmp_path: Path) -> None:
    store = ExecutionTelemetryStore(tmp_path / "executions.jsonl")
    secret = "sk-live-never-persist"
    store.record(
        ExecutionRecord(
            request_id="request-secret",
            requested_role="worker",
            assigned_model=None,
            actual_model="model-a",
            provider="openai",
            account_id="openai-main",
            binding_id=None,
            routing_reason="provider_error",
            mode="strict",
            policy="role_locked",
            started_at="2026-07-10T00:00:00+00:00",
            error=f"Authorization: Bearer {secret}; api_key={secret}",
        )
    )

    serialized = (tmp_path / "executions.jsonl").read_text(encoding="utf-8")
    assert secret not in serialized
    assert "[REDACTED]" in serialized


@pytest.mark.asyncio
async def test_streaming_uses_the_assigned_provider(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    chunks = []

    async for decision, chunk in service.stream(
        RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
    ):
        chunks.append(chunk)

    assert decision.provider == "openai"
    assert b"".join(chunks) == b"openai:one:two"
    assert service.telemetry.list()[0]["provider"] == "openai"


@pytest.mark.asyncio
async def test_streaming_falls_back_only_before_the_first_byte(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        {"openai": httpx.ReadTimeout("timeout"), "anthropic": {}},
    )
    decisions: list[str] = []
    chunks: list[bytes] = []

    async for decision, chunk in service.stream(
        RoutingRequest(role="worker"),
        messages=[{"role": "user", "content": "hello"}],
    ):
        decisions.append(decision.provider)
        chunks.append(chunk)

    assert decisions == ["anthropic", "anthropic"]
    assert b"".join(chunks) == b"anthropic:one:two"
    execution = service.telemetry.list()[0]
    assert execution["fallback_used"] is True
    assert execution["fallback_trigger"] == "provider_outage"


@pytest.mark.asyncio
async def test_streaming_post_first_byte_failure_cools_deployment_without_switching_provider(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})

    class FailingAfterFirstByteAdapter:
        async def stream(self, _request):
            yield b"openai:first"
            raise httpx.ReadTimeout("timeout")

    service.adapter = lambda _account_id: FailingAfterFirstByteAdapter()  # type: ignore[method-assign]
    received: list[bytes] = []

    with pytest.raises(RuntimeError, match="failed during streaming"):
        async for _decision, chunk in service.stream(
            RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
        ):
            received.append(chunk)

    assert received == [b"openai:first"]
    assert (
        service.model_registry.cooldown_remaining_seconds("openai:openai-main:gpt-5.4-mini")
        is not None
    )


@pytest.mark.asyncio
async def test_streaming_falls_back_when_account_setup_fails_before_first_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    resolve_account = service._execution_account

    def fail_openai_setup(decision):
        if decision.provider == "openai":
            raise httpx.ReadTimeout("setup timeout")
        return resolve_account(decision)

    monkeypatch.setattr(service, "_execution_account", fail_openai_setup)
    chunks = [
        chunk
        async for _, chunk in service.stream(
            RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
        )
    ]

    assert b"".join(chunks) == b"anthropic:one:two"
    execution = service.telemetry.list()[0]
    assert execution["provider"] == "anthropic"
    assert execution["fallback_trigger"] == "provider_outage"


@pytest.mark.asyncio
async def test_streaming_uses_a_total_attempt_deadline_not_per_chunk_timeout(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.settings.timeout_seconds = 0.025

    class SlowAdapter:
        async def stream(self, _request):
            while True:
                await asyncio.sleep(0.01)
                yield b"chunk"

    service.adapter = lambda _account_id: SlowAdapter()  # type: ignore[method-assign]
    received = []
    with pytest.raises(RuntimeError, match="deadline exceeded"):
        async for _, chunk in service.stream(
            RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
        ):
            received.append(chunk)

    assert received
    assert "deadline exceeded" in service.telemetry.list()[0]["error"]


@pytest.mark.asyncio
async def test_streaming_cancellation_closes_iterator_and_records_execution(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    started = asyncio.Event()
    closed = asyncio.Event()

    class BlockingAdapter:
        async def stream(self, _request):
            started.set()
            try:
                await asyncio.Event().wait()
                yield b"unreachable"
            finally:
                closed.set()

    service.adapter = lambda _account_id: BlockingAdapter()  # type: ignore[method-assign]
    iterator = service.stream(
        RoutingRequest(role="worker"), messages=[{"role": "user", "content": "hello"}]
    )
    task = asyncio.create_task(anext(iterator))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert closed.is_set()
    execution = service.telemetry.list()[0]
    assert execution["error"] == "Streaming execution was cancelled"


def test_legacy_proxy_role_header_uses_orchestration_assignment(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    handler = type(
        "Handler",
        (),
        {
            "_orchestration_service": service,
            "_orchestration_account_id": "openai-main",
            "_model_router": None,
        },
    )()
    metadata = extract_savings_metadata(request_headers={"x-cutctx-role": "worker"})

    model, routed = prepare_model_routing(
        handler,
        "gpt-5.5",
        request_savings_metadata=metadata,
        transport_provider="openai",
    )

    assert model == "gpt-5.4-mini"
    assert routed["model_routing"]["role"] == "worker"
    assert routed["model_routing"]["request_overrides"] == {"reasoning": {"effort": "high"}}


def test_legacy_proxy_role_binding_does_not_downgrade_on_unproven_transport(
    tmp_path: Path,
) -> None:
    """A role binding must not swap in a model the wire mode can't prove supports.

    Codex Responses Lite / ChatGPT subscription transports set
    ``implicit_downgrade_allowed=False`` precisely because they can't prove an
    arbitrary target model is valid in that mode. Role bindings verify
    provider/account transport but say nothing about wire-mode compatibility,
    so they must respect the same guard instead of bypassing it.
    """
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    handler = type(
        "Handler",
        (),
        {
            "_orchestration_service": service,
            "_orchestration_account_id": "openai-main",
            "_model_router": None,
        },
    )()
    metadata = extract_savings_metadata(request_headers={"x-cutctx-role": "worker"})

    model, routed = prepare_model_routing(
        handler,
        "gpt-5.5",
        request_savings_metadata=metadata,
        transport_provider="openai",
        implicit_downgrade_allowed=False,
    )

    assert model == "gpt-5.5"
    assert routed["model_routing"]["target_model"] == "gpt-5.5"
    assert routed["model_routing"]["reason"] == "downgrade_blocked_unproven_transport"


def test_legacy_proxy_refuses_unproven_provider_account(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    handler = type(
        "Handler",
        (),
        {"_orchestration_service": service, "_model_router": None},
    )()

    with pytest.raises(RoutingUnavailableError) as error:
        prepare_model_routing(
            handler,
            "role:worker",
            transport_provider="openai",
        )

    assert error.value.reason == "account_transport_mismatch"


def test_legacy_proxy_refuses_cross_provider_assignment(tmp_path: Path) -> None:
    service = _service(tmp_path, {"openai": {}, "anthropic": {}})
    service.config.bindings[0].model = "anthropic:claude-worker"
    service.engine = DeterministicRoutingEngine(service.config, service.model_registry)
    handler = type("Handler", (), {"_orchestration_service": service, "_model_router": None})()

    with pytest.raises(RoutingUnavailableError) as error:
        prepare_model_routing(
            handler,
            "role:worker",
            transport_provider="openai",
        )

    assert error.value.reason == "transport_mismatch"
