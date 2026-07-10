"""Production-grade, provider-neutral model orchestration.

The package deliberately has no dependency on the proxy request handlers.  It
can therefore be embedded by the proxy, SDKs, tests, or future workers without
pulling provider-specific transport details into routing policy.
"""

from .engine import DeterministicRoutingEngine, RoutingUnavailableError
from .models import (
    Capability,
    FallbackTrigger,
    ModelRecord,
    OrchestrationConfig,
    ProviderAccount,
    Role,
    RouteBinding,
    RoutingDecision,
    RoutingMode,
    RoutingPolicy,
    RoutingRequest,
)
from .service import OrchestrationService, build_orchestration_service

__all__ = [
    "Capability",
    "DeterministicRoutingEngine",
    "FallbackTrigger",
    "ModelRecord",
    "OrchestrationConfig",
    "OrchestrationService",
    "ProviderAccount",
    "Role",
    "RouteBinding",
    "RoutingDecision",
    "RoutingMode",
    "RoutingPolicy",
    "RoutingRequest",
    "RoutingUnavailableError",
    "build_orchestration_service",
]
