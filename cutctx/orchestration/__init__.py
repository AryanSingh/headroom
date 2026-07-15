"""Production-grade, provider-neutral model orchestration.

The package deliberately has no dependency on the proxy request handlers.  It
can therefore be embedded by the proxy, SDKs, tests, or future workers without
pulling provider-specific transport details into routing policy.
"""

from .audit import ReceiptAuditStore
from .contracts import (
    ContractEvaluationPolicy,
    ContractLifecycle,
    ContractObjective,
    ContractObjectiveType,
    ContractRequirements,
    ReliabilityBudget,
    WorkloadContract,
    contract_from_dict,
    contract_to_dict,
    legacy_contracts_from_config,
)
from .credentials import CredentialStore, ExternalSecretResolver, ResolverBackedCredentialStore
from .engine import DeterministicRoutingEngine, RoutingUnavailableError
from .evaluation import RoutingEvaluationCase, evaluate_routing_cases
from .models import (
    Capability,
    FallbackTrigger,
    ModelRecord,
    OrchestrationConfig,
    OutcomeRecord,
    ProviderAccount,
    Role,
    RouteBinding,
    RoutingDecision,
    RoutingMode,
    RoutingPolicy,
    RoutingProfile,
    RoutingRequest,
    TaskType,
)
from .policy_bundle import compile_policy_bundle, sign_policy_bundle, verify_policy_bundle
from .service import OrchestrationService, build_orchestration_service
from .workflow import (
    TaskSpec,
    TaskState,
    WorkflowConflictError,
    WorkflowRunner,
    WorkflowSpec,
    WorkflowState,
    WorkflowStateStore,
    WorkflowValidationError,
)

__all__ = [
    "Capability",
    "ContractEvaluationPolicy",
    "ContractLifecycle",
    "ContractObjective",
    "ContractObjectiveType",
    "ContractRequirements",
    "CredentialStore",
    "ReceiptAuditStore",
    "compile_policy_bundle",
    "DeterministicRoutingEngine",
    "FallbackTrigger",
    "ExternalSecretResolver",
    "RoutingEvaluationCase",
    "evaluate_routing_cases",
    "ModelRecord",
    "OutcomeRecord",
    "OrchestrationConfig",
    "OrchestrationService",
    "ProviderAccount",
    "ReliabilityBudget",
    "Role",
    "RouteBinding",
    "RoutingDecision",
    "RoutingMode",
    "RoutingPolicy",
    "RoutingProfile",
    "ResolverBackedCredentialStore",
    "RoutingRequest",
    "TaskType",
    "RoutingUnavailableError",
    "sign_policy_bundle",
    "verify_policy_bundle",
    "build_orchestration_service",
    "TaskSpec",
    "TaskState",
    "WorkflowRunner",
    "WorkflowConflictError",
    "WorkflowSpec",
    "WorkflowState",
    "WorkflowStateStore",
    "WorkflowValidationError",
    "WorkloadContract",
    "contract_from_dict",
    "contract_to_dict",
    "legacy_contracts_from_config",
]
