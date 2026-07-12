"""Versioned provider-neutral trace for every model-routing decision."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MODEL_ROUTING_TRACE_KEY = "model_routing_trace"
MODEL_ROUTING_TRACE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ModelRoutingDecisionTrace:
    request_id: str
    mechanism: str
    requested_model: str
    effective_model: str
    reason: str
    applied: bool
    assigned_model: str | None = None
    provider: str | None = None
    account_id: str | None = None
    role: str | None = None
    binding_id: str | None = None
    policy: str | None = None
    mode: str | None = None
    scorer: str | None = None
    confidence: float | None = None
    candidates: list[str] = field(default_factory=list)
    rejected_candidates: list[dict[str, str]] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    fallback_used: bool = False
    fallback_trigger: str | None = None
    fallback_from: str | None = None
    attempted_deployments: list[str] = field(default_factory=list)
    transport: dict[str, Any] = field(default_factory=dict)
    selection_evidence: dict[str, Any] = field(default_factory=dict)
    schema_version: int = MODEL_ROUTING_TRACE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def attach_model_routing_trace(
    metadata: dict[str, dict[str, Any]],
    trace: ModelRoutingDecisionTrace,
) -> dict[str, dict[str, Any]]:
    metadata[MODEL_ROUTING_TRACE_KEY] = trace.to_dict()
    return metadata


__all__ = [
    "MODEL_ROUTING_TRACE_KEY",
    "MODEL_ROUTING_TRACE_SCHEMA_VERSION",
    "ModelRoutingDecisionTrace",
    "attach_model_routing_trace",
]
