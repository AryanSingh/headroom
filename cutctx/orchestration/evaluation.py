"""Deterministic, replayable routing evaluations with no provider calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import RoutingRequest
from .service import OrchestrationService


@dataclass(frozen=True)
class RoutingEvaluationCase:
    """A prompt-free route fixture suitable for source control or JSONL storage."""

    id: str
    request: RoutingRequest
    candidate_profile: str | None = None
    candidate_policy: str | None = None
    candidate_model: str | None = None


def evaluate_routing_cases(
    service: OrchestrationService,
    cases: list[RoutingEvaluationCase],
) -> dict[str, Any]:
    """Run a stable decision-only evaluation suite.

    Cases deliberately contain routing metadata rather than prompts, repository
    files, or model output. This keeps evaluations repeatable and safe to keep
    in a customer-controlled evidence store.
    """
    results: list[dict[str, Any]] = []
    changed = 0
    for case in cases:
        comparison = service.shadow_route(
            case.request,
            candidate_profile=case.candidate_profile,
            candidate_policy=case.candidate_policy,
            candidate_model=case.candidate_model,
        )
        changed += int(bool(comparison["changed"]))
        results.append({"id": case.id, **comparison})
    return {
        "evaluation_version": 1,
        "provider_calls": 0,
        "case_count": len(results),
        "changed_count": changed,
        "results": results,
    }


__all__ = ["RoutingEvaluationCase", "evaluate_routing_cases"]
