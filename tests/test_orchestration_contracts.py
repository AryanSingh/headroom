from __future__ import annotations

import pytest

from cutctx.orchestration.contracts import (
    ContractLifecycle,
    WorkloadContract,
    contract_from_dict,
    contract_to_dict,
    legacy_contracts_from_config,
)
from cutctx.orchestration.models import OrchestrationConfig, Role, RouteBinding


def test_contract_round_trip_preserves_objective_and_reliability_budget() -> None:
    contract = contract_from_dict(
        {
            "id": "implementation",
            "name": "Implementation",
            "version": "1",
            "state": "draft",
            "role_aliases": ["worker"],
            "requirements": {"required_capabilities": ["tool_calling"]},
            "objective": {
                "type": "lowest_cost_within_quality_sla",
                "quality_floor": 0.95,
                "maximum_cost_usd": 0.4,
            },
            "reliability": {
                "attempt_timeout_seconds": 30,
                "total_deadline_seconds": 90,
                "attempts_per_deployment": 2,
                "maximum_deployments": 1,
            },
        }
    )

    assert isinstance(contract, WorkloadContract)
    assert contract.state == ContractLifecycle.DRAFT.value
    assert contract.objective.quality_floor == 0.95
    assert contract.reliability.total_deadline_seconds == 90
    assert contract_from_dict(contract_to_dict(contract)) == contract


def test_legacy_roles_convert_to_behavior_preserving_contracts() -> None:
    config = OrchestrationConfig(
        roles=[
            Role(
                id="worker",
                name="Worker",
                required_capabilities={"tool_calling"},
            )
        ],
        bindings=[
            RouteBinding(
                id="worker-default",
                role="worker",
                model="openai:gpt-5",
                fallback_chain=["anthropic:claude-sonnet"],
            )
        ],
    )
    config.settings.global_fallback_chain = ["google:gemini-pro"]

    contracts = legacy_contracts_from_config(config)

    assert len(contracts) == 1
    assert contracts[0].id == "worker"
    assert contracts[0].baseline_model == "openai:gpt-5"
    assert contracts[0].fallback_models == (
        "anthropic:claude-sonnet",
        "google:gemini-pro",
    )
    assert contracts[0].requirements.required_capabilities == {"tool_calling"}
    assert contracts[0].objective.type == "exact_assignment"
    assert contracts[0].reliability.maximum_deployments == 3
    assert contracts[0].reliability.total_deadline_seconds == 720


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("state", "unknown", "lifecycle"),
        ("objective.type", "magic", "objective"),
        ("objective.quality_floor", 1.1, "quality_floor"),
        ("reliability.attempts_per_deployment", 0, "attempts_per_deployment"),
        ("reliability.total_deadline_seconds", 0, "total_deadline_seconds"),
    ],
)
def test_contract_parser_rejects_invalid_policy_values(
    field: str,
    value: object,
    message: str,
) -> None:
    payload: dict[str, object] = {
        "id": "worker",
        "name": "Worker",
        "version": "1",
    }
    target = payload
    parts = field.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})  # type: ignore[assignment]
    target[parts[-1]] = value

    with pytest.raises(ValueError, match=message):
        contract_from_dict(payload)
