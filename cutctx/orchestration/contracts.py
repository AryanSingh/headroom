"""Versioned workload contracts for coding-agent routing intent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from .models import OrchestrationConfig


class ContractLifecycle(str, Enum):
    DRAFT = "draft"
    SHADOW = "shadow"
    CANARY = "canary"
    ACTIVE = "active"
    PAUSED = "paused"
    RETIRED = "retired"


class ContractObjectiveType(str, Enum):
    EXACT_ASSIGNMENT = "exact_assignment"
    LOWEST_COST_WITHIN_QUALITY_SLA = "lowest_cost_within_quality_sla"
    LOWEST_LATENCY_WITHIN_QUALITY_BUDGET = "lowest_latency_within_quality_budget"
    HIGHEST_QUALITY_WITHIN_BUDGET = "highest_quality_within_budget"
    RELIABILITY_FIRST = "reliability_first"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ContractRequirements:
    required_capabilities: set[str] = field(default_factory=set)
    minimum_context_tokens: int | None = None
    minimum_output_tokens: int | None = None
    allowed_providers: set[str] = field(default_factory=set)
    allowed_accounts: set[str] = field(default_factory=set)
    allowed_regions: set[str] = field(default_factory=set)
    allowed_data_classifications: set[str] = field(default_factory=set)
    retention_policy: str | None = None


@dataclass(frozen=True)
class ContractObjective:
    type: str = ContractObjectiveType.EXACT_ASSIGNMENT.value
    quality_floor: float = 1.0
    maximum_cost_usd: float | None = None
    maximum_ttft_ms: float | None = None
    maximum_total_latency_ms: float | None = None
    weights: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ReliabilityBudget:
    connect_timeout_seconds: float = 10.0
    first_token_timeout_seconds: float = 30.0
    attempt_timeout_seconds: float = 120.0
    stream_idle_timeout_seconds: float = 30.0
    total_deadline_seconds: float = 240.0
    attempts_per_deployment: int = 2
    maximum_deployments: int = 1
    fallback_triggers: set[str] = field(default_factory=set)
    maximum_fallback_cost_usd: float | None = None


@dataclass(frozen=True)
class ContractEvaluationPolicy:
    accepted_outcome_signals: set[str] = field(default_factory=set)
    minimum_samples: int = 20
    unsafe_quality_floor: float = 0.8
    maximum_unsafe_rate: float = 0.01
    canary_percentage: float = 0.1
    automatic_rollback_conditions: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkloadContract:
    id: str
    name: str
    version: str
    state: str = ContractLifecycle.DRAFT.value
    description: str = ""
    role_aliases: tuple[str, ...] = ()
    selectors: dict[str, str] = field(default_factory=dict)
    task_types: set[str] = field(default_factory=set)
    baseline_model: str | None = None
    fallback_models: tuple[str, ...] = ()
    requirements: ContractRequirements = field(default_factory=ContractRequirements)
    objective: ContractObjective = field(default_factory=ContractObjective)
    reliability: ReliabilityBudget = field(default_factory=ReliabilityBudget)
    evaluation: ContractEvaluationPolicy = field(default_factory=ContractEvaluationPolicy)


def _require_keys(payload: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"Unknown {label} fields: {', '.join(sorted(unknown))}")


def _bounded(value: Any, *, name: str, minimum: float, maximum: float) -> float:
    parsed = float(value)
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
    return parsed


def _positive(value: Any, *, name: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(_serialize(item) for item in value)
    if isinstance(value, tuple):
        return [_serialize(item) for item in value]
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


def contract_to_dict(contract: WorkloadContract) -> dict[str, Any]:
    return _serialize(asdict(contract))


def contract_from_dict(payload: dict[str, Any]) -> WorkloadContract:
    _require_keys(
        payload,
        {
            "id",
            "name",
            "version",
            "state",
            "description",
            "role_aliases",
            "selectors",
            "task_types",
            "baseline_model",
            "fallback_models",
            "requirements",
            "objective",
            "reliability",
            "evaluation",
        },
        "contract",
    )
    contract_id = str(payload.get("id", "")).strip()
    name = str(payload.get("name", "")).strip()
    version = str(payload.get("version", "")).strip()
    if not contract_id:
        raise ValueError("Contract id must not be empty")
    if not name:
        raise ValueError("Contract name must not be empty")
    if not version:
        raise ValueError("Contract version must not be empty")

    state = str(payload.get("state", ContractLifecycle.DRAFT.value))
    if state not in {item.value for item in ContractLifecycle}:
        raise ValueError(f"Unknown contract lifecycle: {state}")

    requirements_payload = dict(payload.get("requirements", {}))
    _require_keys(
        requirements_payload,
        {
            "required_capabilities",
            "minimum_context_tokens",
            "minimum_output_tokens",
            "allowed_providers",
            "allowed_accounts",
            "allowed_regions",
            "allowed_data_classifications",
            "retention_policy",
        },
        "requirements",
    )
    requirements = ContractRequirements(
        required_capabilities=set(requirements_payload.get("required_capabilities", [])),
        minimum_context_tokens=requirements_payload.get("minimum_context_tokens"),
        minimum_output_tokens=requirements_payload.get("minimum_output_tokens"),
        allowed_providers=set(requirements_payload.get("allowed_providers", [])),
        allowed_accounts=set(requirements_payload.get("allowed_accounts", [])),
        allowed_regions=set(requirements_payload.get("allowed_regions", [])),
        allowed_data_classifications=set(
            requirements_payload.get("allowed_data_classifications", [])
        ),
        retention_policy=requirements_payload.get("retention_policy"),
    )

    objective_payload = dict(payload.get("objective", {}))
    _require_keys(
        objective_payload,
        {
            "type",
            "quality_floor",
            "maximum_cost_usd",
            "maximum_ttft_ms",
            "maximum_total_latency_ms",
            "weights",
        },
        "objective",
    )
    objective_type = str(
        objective_payload.get("type", ContractObjectiveType.EXACT_ASSIGNMENT.value)
    )
    if objective_type not in {item.value for item in ContractObjectiveType}:
        raise ValueError(f"Unknown contract objective: {objective_type}")
    objective = ContractObjective(
        type=objective_type,
        quality_floor=_bounded(
            objective_payload.get("quality_floor", 1.0),
            name="quality_floor",
            minimum=0,
            maximum=1,
        ),
        maximum_cost_usd=objective_payload.get("maximum_cost_usd"),
        maximum_ttft_ms=objective_payload.get("maximum_ttft_ms"),
        maximum_total_latency_ms=objective_payload.get("maximum_total_latency_ms"),
        weights={str(key): float(value) for key, value in objective_payload.get("weights", {}).items()},
    )

    reliability_payload = dict(payload.get("reliability", {}))
    _require_keys(
        reliability_payload,
        {
            "connect_timeout_seconds",
            "first_token_timeout_seconds",
            "attempt_timeout_seconds",
            "stream_idle_timeout_seconds",
            "total_deadline_seconds",
            "attempts_per_deployment",
            "maximum_deployments",
            "fallback_triggers",
            "maximum_fallback_cost_usd",
        },
        "reliability",
    )
    attempts = int(reliability_payload.get("attempts_per_deployment", 2))
    deployments = int(reliability_payload.get("maximum_deployments", 1))
    if not 1 <= attempts <= 10:
        raise ValueError("attempts_per_deployment must be between 1 and 10")
    if not 1 <= deployments <= 10:
        raise ValueError("maximum_deployments must be between 1 and 10")
    reliability = ReliabilityBudget(
        connect_timeout_seconds=_positive(
            reliability_payload.get("connect_timeout_seconds", 10.0),
            name="connect_timeout_seconds",
        ),
        first_token_timeout_seconds=_positive(
            reliability_payload.get("first_token_timeout_seconds", 30.0),
            name="first_token_timeout_seconds",
        ),
        attempt_timeout_seconds=_positive(
            reliability_payload.get("attempt_timeout_seconds", 120.0),
            name="attempt_timeout_seconds",
        ),
        stream_idle_timeout_seconds=_positive(
            reliability_payload.get("stream_idle_timeout_seconds", 30.0),
            name="stream_idle_timeout_seconds",
        ),
        total_deadline_seconds=_positive(
            reliability_payload.get("total_deadline_seconds", 240.0),
            name="total_deadline_seconds",
        ),
        attempts_per_deployment=attempts,
        maximum_deployments=deployments,
        fallback_triggers=set(reliability_payload.get("fallback_triggers", [])),
        maximum_fallback_cost_usd=reliability_payload.get("maximum_fallback_cost_usd"),
    )

    evaluation_payload = dict(payload.get("evaluation", {}))
    _require_keys(
        evaluation_payload,
        {
            "accepted_outcome_signals",
            "minimum_samples",
            "unsafe_quality_floor",
            "maximum_unsafe_rate",
            "canary_percentage",
            "automatic_rollback_conditions",
        },
        "evaluation",
    )
    minimum_samples = int(evaluation_payload.get("minimum_samples", 20))
    if minimum_samples < 1:
        raise ValueError("minimum_samples must be positive")
    evaluation = ContractEvaluationPolicy(
        accepted_outcome_signals=set(evaluation_payload.get("accepted_outcome_signals", [])),
        minimum_samples=minimum_samples,
        unsafe_quality_floor=_bounded(
            evaluation_payload.get("unsafe_quality_floor", 0.8),
            name="unsafe_quality_floor",
            minimum=0,
            maximum=1,
        ),
        maximum_unsafe_rate=_bounded(
            evaluation_payload.get("maximum_unsafe_rate", 0.01),
            name="maximum_unsafe_rate",
            minimum=0,
            maximum=1,
        ),
        canary_percentage=_bounded(
            evaluation_payload.get("canary_percentage", 0.1),
            name="canary_percentage",
            minimum=0,
            maximum=1,
        ),
        automatic_rollback_conditions={
            str(key): float(value)
            for key, value in evaluation_payload.get(
                "automatic_rollback_conditions", {}
            ).items()
        },
    )

    return WorkloadContract(
        id=contract_id,
        name=name,
        version=version,
        state=state,
        description=str(payload.get("description", "")),
        role_aliases=tuple(str(value) for value in payload.get("role_aliases", [])),
        selectors={str(key): str(value) for key, value in payload.get("selectors", {}).items()},
        task_types=set(payload.get("task_types", [])),
        baseline_model=(
            str(payload["baseline_model"])
            if payload.get("baseline_model") is not None
            else None
        ),
        fallback_models=tuple(str(value) for value in payload.get("fallback_models", [])),
        requirements=requirements,
        objective=objective,
        reliability=reliability,
        evaluation=evaluation,
    )


def legacy_contracts_from_config(config: OrchestrationConfig) -> list[WorkloadContract]:
    contracts: list[WorkloadContract] = []
    for role in config.roles:
        bindings = sorted(
            (
                binding
                for binding in config.bindings
                if binding.enabled and binding.role and binding.role.casefold() == role.id.casefold()
            ),
            key=lambda binding: (bool(binding.selectors), binding.id),
        )
        default = bindings[0] if bindings else None
        fallback_models = (
            *tuple(default.fallback_chain if default else ()),
            *tuple(config.settings.global_fallback_chain),
        )
        attempts_per_deployment = config.settings.retries + 1
        maximum_deployments = 1 + len(fallback_models)
        contracts.append(
            WorkloadContract(
                id=role.id,
                name=role.name,
                version="legacy-1",
                state=ContractLifecycle.ACTIVE.value,
                description=role.description,
                role_aliases=(role.id, role.name),
                baseline_model=default.model if default else None,
                fallback_models=fallback_models,
                requirements=ContractRequirements(
                    required_capabilities={
                        *role.required_capabilities,
                        *(default.required_capabilities if default else set()),
                    },
                    allowed_providers=set(config.settings.allowed_providers),
                    allowed_regions=set(config.settings.allowed_regions),
                    allowed_data_classifications=set(
                        config.settings.allowed_data_classifications
                    ),
                ),
                objective=ContractObjective(
                    type=ContractObjectiveType.EXACT_ASSIGNMENT.value,
                    quality_floor=1.0,
                ),
                reliability=ReliabilityBudget(
                    attempt_timeout_seconds=config.settings.timeout_seconds,
                    total_deadline_seconds=(
                        config.settings.timeout_seconds
                        * attempts_per_deployment
                        * maximum_deployments
                    ),
                    attempts_per_deployment=attempts_per_deployment,
                    maximum_deployments=maximum_deployments,
                    fallback_triggers=set(config.settings.fallback_triggers),
                ),
            )
        )
    return contracts


__all__ = [
    "ContractEvaluationPolicy",
    "ContractLifecycle",
    "ContractObjective",
    "ContractObjectiveType",
    "ContractRequirements",
    "ReliabilityBudget",
    "WorkloadContract",
    "contract_from_dict",
    "contract_to_dict",
    "legacy_contracts_from_config",
]
