"""Pure compilation of workload contracts into executable routing policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace

from .contracts import (
    ContractEvaluationPolicy,
    ContractObjective,
    ReliabilityBudget,
    WorkloadContract,
    contract_to_dict,
)
from .models import OrchestrationConfig, Role, RouteBinding, to_dict


class ContractCompilationError(ValueError):
    """Raised when a contract cannot be compiled without violating policy."""


@dataclass(frozen=True)
class CompiledRoutingPolicy:
    contract_id: str
    contract_version: str
    lifecycle_state: str
    config: OrchestrationConfig
    objective: ContractObjective
    reliability: ReliabilityBudget
    evaluation: ContractEvaluationPolicy
    policy_hash: str


def _narrow_allow_list(
    name: str,
    *boundaries: set[str],
) -> set[str]:
    constrained = [set(boundary) for boundary in boundaries if boundary]
    if not constrained:
        return set()
    result = constrained[0]
    for boundary in constrained[1:]:
        result &= boundary
    if not result:
        raise ContractCompilationError(f"Contract {name} do not overlap policy boundaries")
    return result


def compile_contract(
    contract: WorkloadContract,
    infrastructure: OrchestrationConfig,
    organization_policy: OrchestrationConfig | None = None,
) -> CompiledRoutingPolicy:
    """Compile one immutable contract without mutating infrastructure state."""

    worst_case = (
        contract.reliability.attempt_timeout_seconds
        * contract.reliability.attempts_per_deployment
        * contract.reliability.maximum_deployments
    )
    if worst_case > contract.reliability.total_deadline_seconds:
        raise ContractCompilationError(
            f"Configured attempts require {worst_case:g}s but total deadline is "
            f"{contract.reliability.total_deadline_seconds:g}s"
        )

    organization_settings = organization_policy.settings if organization_policy else None
    allowed_providers = _narrow_allow_list(
        "allowed providers",
        infrastructure.settings.allowed_providers,
        organization_settings.allowed_providers if organization_settings else set(),
        contract.requirements.allowed_providers,
    )
    allowed_regions = _narrow_allow_list(
        "allowed regions",
        infrastructure.settings.allowed_regions,
        organization_settings.allowed_regions if organization_settings else set(),
        contract.requirements.allowed_regions,
    )
    allowed_data_classifications = _narrow_allow_list(
        "allowed data classifications",
        infrastructure.settings.allowed_data_classifications,
        (
            organization_settings.allowed_data_classifications
            if organization_settings
            else set()
        ),
        contract.requirements.allowed_data_classifications,
    )

    role = Role(
        id=contract.id,
        name=contract.name,
        description=contract.description,
        required_capabilities=set(contract.requirements.required_capabilities),
    )
    binding = RouteBinding(
        id=f"{contract.id}-default",
        role=contract.id,
        model=contract.baseline_model or "",
        selectors=dict(contract.selectors),
        fallback_chain=list(contract.fallback_models),
        required_capabilities=set(contract.requirements.required_capabilities),
    )
    settings = replace(
        infrastructure.settings,
        allowed_providers=allowed_providers,
        allowed_regions=allowed_regions,
        allowed_data_classifications=allowed_data_classifications,
        retries=contract.reliability.attempts_per_deployment - 1,
        timeout_seconds=contract.reliability.attempt_timeout_seconds,
        fallback_triggers=set(contract.reliability.fallback_triggers),
        global_fallback_chain=[],
        policy_version=f"contract:{contract.id}:{contract.version}",
    )

    providers = list(infrastructure.providers)
    if allowed_providers:
        providers = [account for account in providers if account.provider in allowed_providers]
    if contract.requirements.allowed_accounts:
        providers = [
            account for account in providers if account.id in contract.requirements.allowed_accounts
        ]
        if infrastructure.providers and not providers:
            raise ContractCompilationError(
                "Contract allowed accounts do not overlap infrastructure accounts"
            )
    provider_ids = {account.id for account in providers}
    models = [
        model
        for model in infrastructure.models
        if (not allowed_providers or model.provider in allowed_providers)
        and (
            not contract.requirements.allowed_accounts
            or model.account_id in contract.requirements.allowed_accounts
        )
        and (
            not infrastructure.providers
            or not model.account_id
            or model.account_id in provider_ids
        )
        and (
            contract.requirements.minimum_context_tokens is None
            or (model.max_input_tokens or model.context_length)
            >= contract.requirements.minimum_context_tokens
        )
        and (
            contract.requirements.minimum_output_tokens is None
            or (
                model.max_output_tokens is not None
                and model.max_output_tokens
                >= contract.requirements.minimum_output_tokens
            )
        )
    ]
    config = replace(
        infrastructure,
        providers=providers,
        models=models,
        roles=[role],
        profiles=[],
        bindings=[binding],
        settings=settings,
    )
    hash_payload = {
        "contract": contract_to_dict(contract),
        "config": to_dict(config),
    }
    policy_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CompiledRoutingPolicy(
        contract_id=contract.id,
        contract_version=contract.version,
        lifecycle_state=contract.state,
        config=config,
        objective=contract.objective,
        reliability=contract.reliability,
        evaluation=contract.evaluation,
        policy_hash=policy_hash,
    )


__all__ = [
    "CompiledRoutingPolicy",
    "ContractCompilationError",
    "compile_contract",
]
