from __future__ import annotations

from dataclasses import replace

import pytest

from cutctx.orchestration.compiler import ContractCompilationError, compile_contract
from cutctx.orchestration.contracts import (
    ContractObjective,
    ContractRequirements,
    ReliabilityBudget,
    WorkloadContract,
)
from cutctx.orchestration.models import (
    ModelRecord,
    OrchestrationConfig,
    ProviderAccount,
    RoutingSettings,
)
from cutctx.orchestration.policy_bundle import compile_policy_bundle


def _implementation_contract() -> WorkloadContract:
    return WorkloadContract(
        id="implementation",
        name="Implementation",
        version="2",
        description="Implement and verify a coding task",
        selectors={"task_type": "implementation"},
        baseline_model="openai:primary:gpt-5",
        fallback_models=("openai:secondary:gpt-5",),
        requirements=ContractRequirements(
            required_capabilities={"tool_calling"},
            allowed_providers={"openai", "anthropic"},
            allowed_regions={"us", "eu"},
            allowed_data_classifications={"internal"},
        ),
        objective=ContractObjective(
            type="lowest_cost_within_quality_sla",
            quality_floor=0.95,
        ),
        reliability=ReliabilityBudget(
            attempt_timeout_seconds=30,
            total_deadline_seconds=60,
            attempts_per_deployment=1,
            maximum_deployments=2,
        ),
    )


def _infrastructure_config() -> OrchestrationConfig:
    return OrchestrationConfig(
        providers=[
            ProviderAccount(id="primary", provider="openai"),
            ProviderAccount(id="secondary", provider="openai"),
        ],
        settings=RoutingSettings(
            allowed_providers={"openai"},
            allowed_regions={"us"},
            allowed_data_classifications={"internal", "restricted"},
        ),
    )


def test_compiler_preserves_exact_assignment_and_hard_constraints() -> None:
    compiled = compile_contract(
        _implementation_contract(),
        _infrastructure_config(),
    )

    assert compiled.config.roles[0].id == "implementation"
    assert compiled.config.bindings[0].model == "openai:primary:gpt-5"
    assert compiled.config.bindings[0].fallback_chain == ["openai:secondary:gpt-5"]
    assert compiled.config.settings.allowed_providers == {"openai"}
    assert compiled.config.settings.allowed_regions == {"us"}
    assert compiled.config.settings.allowed_data_classifications == {"internal"}
    assert compiled.objective.type == "lowest_cost_within_quality_sla"
    assert compiled.policy_hash


def test_compiler_rejects_retry_plan_larger_than_total_deadline() -> None:
    contract = replace(
        _implementation_contract(),
        reliability=ReliabilityBudget(
            attempt_timeout_seconds=60,
            total_deadline_seconds=100,
            attempts_per_deployment=2,
            maximum_deployments=1,
        ),
    )

    with pytest.raises(ContractCompilationError, match="total deadline"):
        compile_contract(contract, _infrastructure_config())


def test_compiler_hash_is_stable_and_changes_with_enforcement_policy() -> None:
    contract = _implementation_contract()
    first = compile_contract(contract, _infrastructure_config())
    second = compile_contract(contract, _infrastructure_config())
    changed = compile_contract(
        replace(contract, objective=replace(contract.objective, quality_floor=0.97)),
        _infrastructure_config(),
    )

    assert first.policy_hash == second.policy_hash
    assert first.policy_hash != changed.policy_hash


def test_compiler_rejects_contract_allow_list_outside_infrastructure_boundary() -> None:
    contract = replace(
        _implementation_contract(),
        requirements=replace(
            _implementation_contract().requirements,
            allowed_providers={"anthropic"},
        ),
    )

    with pytest.raises(ContractCompilationError, match="allowed providers"):
        compile_contract(contract, _infrastructure_config())


def test_compiled_policy_bundle_carries_contract_identity_and_hash() -> None:
    compiled = compile_contract(_implementation_contract(), _infrastructure_config())

    bundle = compile_policy_bundle(compiled)

    assert bundle["contract"] == {
        "id": "implementation",
        "version": "2",
        "lifecycle_state": "draft",
        "policy_hash": compiled.policy_hash,
    }


def test_compiler_preserves_registered_models_when_accounts_are_implicit() -> None:
    infrastructure = _infrastructure_config()
    infrastructure.providers = []
    infrastructure.models = [
        ModelRecord(provider="openai", id="gpt-5", account_id="primary")
    ]

    compiled = compile_contract(_implementation_contract(), infrastructure)

    assert [model.deployment_key for model in compiled.config.models] == [
        "openai:primary:gpt-5"
    ]
