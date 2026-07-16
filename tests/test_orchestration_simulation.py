from __future__ import annotations

from pathlib import Path

from cutctx.orchestration.config import LayeredConfigStore
from cutctx.orchestration.contracts import (
    ContractRequirements,
    ReliabilityBudget,
    WorkloadContract,
)
from cutctx.orchestration.credentials import EncryptedCredentialStore
from cutctx.orchestration.engine import DeterministicRoutingEngine
from cutctx.orchestration.models import (
    ModelRecord,
    OrchestrationConfig,
    ProviderAccount,
    Role,
    RouteBinding,
    RoutingMode,
    RoutingRequest,
    RoutingSettings,
)
from cutctx.orchestration.registry import DynamicModelRegistry
from cutctx.orchestration.service import OrchestrationService


def _model(
    provider: str,
    model: str,
    *,
    account_id: str,
    capabilities: set[str] | None = None,
) -> ModelRecord:
    return ModelRecord(
        provider=provider,
        id=model,
        account_id=account_id,
        capabilities=capabilities or {"tool_calling"},
    )


def _service(tmp_path: Path) -> OrchestrationService:
    config = OrchestrationConfig(
        providers=[
            ProviderAccount(id="openai-main", provider="openai"),
            ProviderAccount(id="anthropic-main", provider="anthropic"),
        ],
        roles=[Role(id="implementation", name="Implementation")],
        bindings=[
            RouteBinding(
                id="implementation-live",
                role="implementation",
                model="openai:openai-main:gpt-5",
            )
        ],
        settings=RoutingSettings(mode=RoutingMode.RELAXED.value),
    )
    registry = DynamicModelRegistry()
    for model in (
        _model("openai", "gpt-5", account_id="openai-main"),
        _model("anthropic", "sonnet", account_id="anthropic-main"),
    ):
        registry.register(model)
    service = OrchestrationService(
        config_store=LayeredConfigStore(),
        credential_store=EncryptedCredentialStore(tmp_path / "credentials.enc"),
        model_registry=registry,
    )
    service.config = config
    service.engine = DeterministicRoutingEngine(
        config,
        registry,
        require_configured_accounts=True,
    )
    return service


def _draft_contract(
    *,
    baseline_model: str = "anthropic:anthropic-main:sonnet",
    fallback_models: tuple[str, ...] = (),
    required_capabilities: set[str] | None = None,
) -> WorkloadContract:
    return WorkloadContract(
        id="implementation",
        name="Implementation",
        version="2",
        baseline_model=baseline_model,
        fallback_models=fallback_models,
        requirements=ContractRequirements(
            required_capabilities=required_capabilities or {"tool_calling"},
            allowed_providers={"openai", "anthropic"},
        ),
        reliability=ReliabilityBudget(
            attempt_timeout_seconds=30,
            total_deadline_seconds=90,
            attempts_per_deployment=1,
            maximum_deployments=3,
        ),
    )


def test_simulation_uses_supplied_draft_without_mutating_live_service(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    request = RoutingRequest(role="implementation", request_id="req-1")
    live = service.route(request)

    result = service.simulate_contract(_draft_contract(), request)

    assert result.executed is False
    assert result.draft_receipt.selected_model == "anthropic:sonnet"
    assert result.live_receipt.selected_model == f"{live.provider}:{live.actual_model}"
    assert result.draft_receipt.contract_version == "2"
    assert result.draft_receipt.receipt_version == 2
    assert service.route(RoutingRequest(role="implementation")).actual_model == live.actual_model


def test_receipt_lists_every_rejected_candidate_with_stable_reason(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.model_registry.register(
        _model(
            "openai",
            "vision",
            account_id="openai-main",
            capabilities={"tool_calling", "vision"},
        )
    )
    service.model_registry.register(
        _model(
            "anthropic",
            "text-only",
            account_id="anthropic-main",
            capabilities={"tool_calling"},
        )
    )
    service.model_registry.register(
        _model(
            "anthropic",
            "vision",
            account_id="anthropic-main",
            capabilities={"tool_calling", "vision"},
        )
    )
    contract = _draft_contract(
        baseline_model="openai:openai-main:vision",
        fallback_models=(
            "anthropic:anthropic-main:text-only",
            "anthropic:anthropic-main:vision",
        ),
        required_capabilities={"tool_calling", "vision"},
    )

    result = service.simulate_contract(
        contract,
        RoutingRequest(
            role="implementation",
            request_id="req-rejections",
            allowed_providers={"anthropic"},
        ),
    )

    assert {item.reason for item in result.draft_receipt.rejected_candidates} >= {
        "provider_not_allowed",
        "unsupported_capabilities",
    }
    assert result.draft_receipt.selected_deployment == "anthropic:anthropic-main:vision"


def test_replay_contract_is_pure_and_preserves_request_order(tmp_path: Path) -> None:
    service = _service(tmp_path)
    requests = [
        RoutingRequest(role="implementation", request_id="req-1"),
        RoutingRequest(role="implementation", request_id="req-2"),
    ]

    results = service.replay_contract(_draft_contract(), requests)

    assert [result.draft_receipt.request_id for result in results] == ["req-1", "req-2"]
    assert all(result.executed is False for result in results)
