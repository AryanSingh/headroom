"""Serializable domain models for provider-neutral orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, cast


class Capability(str, Enum):
    REASONING = "reasoning"
    THINKING = "thinking"
    STREAMING = "streaming"
    TOOL_CALLING = "tool_calling"
    VISION = "vision"
    IMAGE_GENERATION = "image_generation"
    EMBEDDINGS = "embeddings"
    STRUCTURED_OUTPUTS = "structured_outputs"
    JSON_MODE = "json_mode"
    LONG_CONTEXT = "long_context"
    AUDIO = "audio"
    MCP = "mcp"


class TaskType(str, Enum):
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    TESTING = "testing"
    REVIEW = "review"
    RESEARCH = "research"
    DOCUMENTATION = "documentation"
    LONG_CONTEXT_ANALYSIS = "long_context_analysis"
    SECURITY_REVIEW = "security_review"


class RoutingMode(str, Enum):
    STRICT = "strict"
    RELAXED = "relaxed"


class RoutingPolicy(str, Enum):
    ROLE_LOCKED = "role_locked"
    MANUAL = "manual"
    FASTEST = "fastest"
    CHEAPEST = "cheapest"
    HIGHEST_QUALITY = "highest_quality"
    BALANCED = "balanced"


class FallbackTrigger(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_FAILURE = "auth_failure"
    QUOTA_EXHAUSTED = "quota_exhausted"
    PROVIDER_OUTAGE = "provider_outage"
    UNSUPPORTED_CAPABILITIES = "unsupported_capabilities"
    MODEL_DEPRECATED = "model_deprecated"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class ProviderAccount:
    id: str
    provider: str
    display_name: str = ""
    auth_method: str = "api_key"
    credential_ref: str | None = None
    base_url: str | None = None
    organization_id: str | None = None
    workspace_id: str | None = None
    custom_headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelRecord:
    provider: str
    id: str
    display_name: str = ""
    account_id: str | None = None
    capabilities: set[str] = field(default_factory=set)
    context_length: int = 0
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    latency_ms: float | None = None
    reliability: float | None = None
    available: bool = True
    deprecated: bool = False
    recommended_usage: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.id}"

    @property
    def deployment_key(self) -> str:
        """Unique execution target, including the account when one exists."""
        if self.account_id:
            return f"{self.provider}:{self.account_id}:{self.id}"
        return self.key

    def supports(self, required: set[str]) -> bool:
        return required.issubset(self.capabilities)


@dataclass
class Role:
    id: str
    name: str
    description: str = ""
    required_capabilities: set[str] = field(default_factory=set)


@dataclass
class RoutingProfile:
    """Versioned, user-facing intent mapped to a role and hard constraints."""

    id: str
    role: str
    version: str = "1"
    description: str = ""
    required_capabilities: set[str] = field(default_factory=set)
    allowed_providers: set[str] = field(default_factory=set)
    max_cost_usd: float | None = None


@dataclass
class RouteBinding:
    """A deterministic assignment.

    ``selectors`` may contain any user-defined dimensions.  Common dimensions
    are agent, workflow, command, skill, task_type, repository, workspace, and
    organization.  A binding with more matching selectors wins; ties use the
    documented precedence and finally the stable binding id.
    """

    id: str
    model: str
    role: str | None = None
    selectors: dict[str, str] = field(default_factory=dict)
    fallback_chain: list[str] = field(default_factory=list)
    # Explicitly interchangeable deployments of the same provider/model.
    # These may differ by account or region, but never by model identity.
    equivalent_deployments: list[str] = field(default_factory=list)
    required_capabilities: set[str] = field(default_factory=set)
    enabled: bool = True


@dataclass
class RoutingSettings:
    mode: str = RoutingMode.STRICT.value
    policy: str = RoutingPolicy.ROLE_LOCKED.value
    retries: int = 1
    timeout_seconds: float = 120.0
    fallback_triggers: set[str] = field(
        default_factory=lambda: {trigger.value for trigger in FallbackTrigger}
    )
    global_fallback_chain: list[str] = field(default_factory=list)
    # Empty allow-lists mean unrestricted. Non-empty values are hard upper
    # bounds; callers may narrow them but can never broaden them.
    allowed_providers: set[str] = field(default_factory=set)
    allowed_regions: set[str] = field(default_factory=set)
    allowed_data_classifications: set[str] = field(default_factory=set)
    policy_version: str = "1"


@dataclass
class OrchestrationConfig:
    version: int = 1
    providers: list[ProviderAccount] = field(default_factory=list)
    models: list[ModelRecord] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)
    profiles: list[RoutingProfile] = field(default_factory=list)
    bindings: list[RouteBinding] = field(default_factory=list)
    settings: RoutingSettings = field(default_factory=RoutingSettings)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingRequest:
    profile: str | None = None
    task_type: str | None = None
    role: str | None = None
    requested_model: str | None = None
    requested_provider: str | None = None
    required_capabilities: set[str] = field(default_factory=set)
    selectors: dict[str, str] = field(default_factory=dict)
    mode: str | None = None
    policy: str | None = None
    request_id: str = ""
    allowed_providers: set[str] = field(default_factory=set)
    allowed_regions: set[str] = field(default_factory=set)
    allowed_data_classifications: set[str] = field(default_factory=set)
    data_classification: str | None = None
    estimated_input_tokens: int | None = None
    estimated_output_tokens: int | None = None
    max_cost_usd: float | None = None
    policy_version: str = "1"


@dataclass
class RoutingDecision:
    request_id: str
    role: str | None
    assigned_model: str | None
    actual_model: str
    provider: str
    account_id: str | None
    binding_id: str | None
    mode: str
    policy: str
    reason: str
    fallback_used: bool = False
    fallback_trigger: str | None = None
    fallback_from: str | None = None
    candidates: list[str] = field(default_factory=list)
    attempted_deployments: list[str] = field(default_factory=list)
    required_capabilities: set[str] = field(default_factory=set)
    policy_constraints: dict[str, Any] = field(default_factory=dict)
    selection_evidence: dict[str, Any] = field(default_factory=dict)
    receipt_version: int = 1


@dataclass
class ExecutionRecord:
    request_id: str
    requested_role: str | None
    assigned_model: str | None
    actual_model: str
    provider: str
    account_id: str | None
    binding_id: str | None
    routing_reason: str
    mode: str
    policy: str
    started_at: str
    latency_ms: float = 0.0
    cost_usd: float | None = None
    retries: int = 0
    fallback_used: bool = False
    fallback_trigger: str | None = None
    fallback_from: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_hit: bool | None = None
    error: str | None = None
    policy_version: str = "1"
    policy_constraints: dict[str, Any] = field(default_factory=dict)
    task_type: str | None = None


@dataclass
class OutcomeRecord:
    """Privacy-safe result signals linked to one completed execution."""

    request_id: str
    task_type: str
    verified: bool | None = None
    review_accepted: bool | None = None
    retry_required: bool | None = None
    reverted: bool | None = None
    developer_rating: int | None = None
    recorded_at: str = ""


def _enum_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(_enum_value(item) for item in value)
    if isinstance(value, list):
        return [_enum_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _enum_value(item) for key, item in value.items()}
    return value


def to_dict(value: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", _enum_value(asdict(value)))


def _construct(cls: type[Any], payload: dict[str, Any]) -> Any:
    accepted = {item.name for item in fields(cls)}
    return cls(**{key: value for key, value in payload.items() if key in accepted})


def config_from_dict(payload: dict[str, Any]) -> OrchestrationConfig:
    migrated = dict(payload)
    version = int(migrated.get("version", 1))
    if version > 1:
        raise ValueError(f"Unsupported orchestration config version: {version}")
    return OrchestrationConfig(
        version=1,
        providers=[_construct(ProviderAccount, item) for item in migrated.get("providers", [])],
        models=[
            ModelRecord(
                **{
                    **{key: value for key, value in item.items() if key != "capabilities"},
                    "capabilities": set(item.get("capabilities", [])),
                }
            )
            for item in migrated.get("models", [])
        ],
        roles=[
            Role(
                **{
                    **{key: value for key, value in item.items() if key != "required_capabilities"},
                    "required_capabilities": set(item.get("required_capabilities", [])),
                }
            )
            for item in migrated.get("roles", [])
        ],
        profiles=[
            RoutingProfile(
                **{
                    **{
                        key: value
                        for key, value in item.items()
                        if key not in {"required_capabilities", "allowed_providers"}
                    },
                    "required_capabilities": set(item.get("required_capabilities", [])),
                    "allowed_providers": set(item.get("allowed_providers", [])),
                }
            )
            for item in migrated.get("profiles", [])
        ],
        bindings=[
            RouteBinding(
                **{
                    **{key: value for key, value in item.items() if key != "required_capabilities"},
                    "required_capabilities": set(item.get("required_capabilities", [])),
                }
            )
            for item in migrated.get("bindings", [])
        ],
        settings=RoutingSettings(
            **{
                **{
                    key: value
                    for key, value in migrated.get("settings", {}).items()
                    if key not in {
                        "fallback_triggers",
                        "allowed_providers",
                        "allowed_regions",
                        "allowed_data_classifications",
                    }
                },
                "fallback_triggers": set(
                    migrated.get("settings", {}).get(
                        "fallback_triggers", [trigger.value for trigger in FallbackTrigger]
                    )
                ),
                "allowed_providers": set(
                    migrated.get("settings", {}).get("allowed_providers", [])
                ),
                "allowed_regions": set(migrated.get("settings", {}).get("allowed_regions", [])),
                "allowed_data_classifications": set(
                    migrated.get("settings", {}).get("allowed_data_classifications", [])
                ),
            }
        ),
        metadata=dict(migrated.get("metadata", {})),
    )
