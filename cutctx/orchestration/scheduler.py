"""Evidence-gated scheduling recommendations; never a live mutation path."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .engine import RoutingUnavailableError
from .models import RoutingRequest
from .service import OrchestrationService


@dataclass(frozen=True)
class SchedulerGuardrails:
    min_observations: int = 5
    min_quality_score: float = 0.8
    canary_sample_rate: float = 0.0


def canary_assignment(request_id: str, sample_rate: float) -> bool:
    """Deterministically assign a stable cohort; zero is the safe default."""
    if not request_id or sample_rate <= 0:
        return False
    if sample_rate >= 1:
        return True
    value = int(hashlib.sha256(request_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return value < sample_rate


def recommend_schedule(
    service: OrchestrationService,
    request: RoutingRequest,
    *,
    guardrails: SchedulerGuardrails = SchedulerGuardrails(),
) -> dict[str, Any]:
    """Return a recommendation from verified evidence without provider calls.

    The response expressly does not apply a route. Every candidate is resolved
    through `shadow_route`, so policy, residency, capability and cost guards
    remain authoritative.
    """
    baseline = service.route(request, allow_overrides=True)
    outcomes = {item.get("request_id"): item for item in service.outcome_telemetry.list(limit=1000)}
    evidence: dict[tuple[str, str, str | None], list[dict[str, Any]]] = {}
    for execution in service.telemetry.list(limit=1000):
        if request.task_type and execution.get("task_type") != request.task_type:
            continue
        outcome = outcomes.get(execution.get("request_id"))
        if outcome is None:
            continue
        key = (
            str(execution.get("provider")),
            str(execution.get("actual_model")),
            execution.get("account_id"),
        )
        evidence.setdefault(key, []).append(outcome)

    candidates: list[dict[str, Any]] = []
    for model in service.model_registry.list(available_only=True):
        try:
            comparison = service.shadow_route(request, candidate_model=model.deployment_key)
        except (RoutingUnavailableError, ValueError, RuntimeError):
            continue
        candidate = comparison["candidate"]
        key = (candidate["provider"], candidate["actual_model"], candidate["account_id"])
        signals = evidence.get(key, [])
        observations = len(signals)
        successful = sum(
            item.get("verified") is True
            and item.get("review_accepted") is not False
            and item.get("reverted") is not True
            for item in signals
        )
        quality = successful / observations if observations else 0.0
        eligible = observations >= guardrails.min_observations and quality >= guardrails.min_quality_score
        candidates.append(
            {
                "deployment": model.deployment_key,
                "provider": candidate["provider"],
                "model": candidate["actual_model"],
                "account_id": candidate["account_id"],
                "observations": observations,
                "quality_score": quality,
                "eligible": eligible,
            }
        )
    eligible = sorted(
        (item for item in candidates if item["eligible"]),
        key=lambda item: (-item["quality_score"], -item["observations"], item["deployment"]),
    )
    recommendation = eligible[0] if eligible else None
    return {
        "scheduler_version": 1,
        "mode": "recommendation_only",
        "provider_calls": 0,
        "baseline": baseline.actual_model,
        "canary_assigned": canary_assignment(request.request_id, guardrails.canary_sample_rate),
        "guardrails": {
            "min_observations": guardrails.min_observations,
            "min_quality_score": guardrails.min_quality_score,
            "canary_sample_rate": guardrails.canary_sample_rate,
        },
        "recommendation": recommendation,
        "candidates": candidates,
    }


def detect_quality_drift(
    service: OrchestrationService,
    *,
    task_type: str,
    window_size: int = 10,
    max_quality_drop: float = 0.15,
) -> dict[str, Any]:
    """Compare adjacent outcome windows and emit an advisory drift signal.

    No alert is emitted without two complete windows. The result is intended
    for dashboards or an operator-owned alert transport, never direct routing
    mutation or autonomous rollback.
    """
    if window_size < 1:
        raise ValueError("window_size must be at least one")
    if not 0 <= max_quality_drop <= 1:
        raise ValueError("max_quality_drop must be between zero and one")
    outcomes = [
        item
        for item in reversed(service.outcome_telemetry.list(limit=window_size * 2))
        if item.get("task_type") == task_type
    ]
    if len(outcomes) < window_size * 2:
        return {
            "drift_version": 1,
            "task_type": task_type,
            "status": "insufficient_evidence",
            "observations": len(outcomes),
            "required_observations": window_size * 2,
            "alert": False,
        }

    def quality(items: list[dict[str, Any]]) -> float:
        return sum(
            item.get("verified") is True
            and item.get("review_accepted") is not False
            and item.get("reverted") is not True
            for item in items
        ) / len(items)

    prior = quality(outcomes[:window_size])
    recent = quality(outcomes[-window_size:])
    drop = prior - recent
    return {
        "drift_version": 1,
        "task_type": task_type,
        "status": "evaluated",
        "prior_quality_score": prior,
        "recent_quality_score": recent,
        "quality_drop": drop,
        "max_quality_drop": max_quality_drop,
        "alert": drop > max_quality_drop,
        "mode": "advisory_only",
    }


__all__ = [
    "SchedulerGuardrails",
    "canary_assignment",
    "detect_quality_drift",
    "recommend_schedule",
]
