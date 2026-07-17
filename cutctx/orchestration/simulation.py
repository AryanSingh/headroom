"""Pure contract simulation and schema-v2 decision receipts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .compiler import CompiledRoutingPolicy
from .models import RoutingDecision, to_dict


@dataclass(frozen=True)
class RejectedCandidate:
    model: str
    reason: str


@dataclass(frozen=True)
class ContractDecisionReceipt:
    request_id: str
    selected_model: str
    selected_deployment: str
    eligible_candidates: tuple[str, ...] = ()
    rejected_candidates: tuple[RejectedCandidate, ...] = ()
    contract_id: str | None = None
    contract_version: str | None = None
    contract_state: str | None = None
    policy_hash: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    reliability_budget: dict[str, Any] = field(default_factory=dict)
    receipt_version: int = 2


@dataclass(frozen=True)
class SimulationResult:
    live_receipt: ContractDecisionReceipt
    draft_receipt: ContractDecisionReceipt
    executed: bool = False
    changed: bool = False


def receipt_from_decision(
    decision: RoutingDecision,
    *,
    eligible_candidates: list[str] | None = None,
    rejected_candidates: list[dict[str, str]] | None = None,
    compiled: CompiledRoutingPolicy | None = None,
) -> ContractDecisionReceipt:
    selected_model = decision.selected_model or f"{decision.provider}:{decision.actual_model}"
    selected_deployment = decision.selected_deployment or (
        f"{decision.provider}:{decision.account_id}:{decision.actual_model}"
        if decision.account_id
        else selected_model
    )
    return ContractDecisionReceipt(
        request_id=decision.request_id,
        selected_model=selected_model,
        selected_deployment=selected_deployment,
        eligible_candidates=tuple(eligible_candidates or decision.eligible_candidates),
        rejected_candidates=tuple(
            RejectedCandidate(model=item["model"], reason=item["reason"])
            for item in (rejected_candidates or decision.rejected_candidates)
        ),
        contract_id=compiled.contract_id if compiled else decision.contract_id,
        contract_version=(compiled.contract_version if compiled else decision.contract_version),
        contract_state=compiled.lifecycle_state if compiled else decision.contract_state,
        policy_hash=compiled.policy_hash if compiled else decision.policy_hash,
        evidence=dict(decision.evidence or decision.selection_evidence),
        reliability_budget=(
            to_dict(compiled.reliability) if compiled else dict(decision.reliability_budget)
        ),
    )


def compare_decisions(
    *,
    live: ContractDecisionReceipt,
    draft: ContractDecisionReceipt,
) -> SimulationResult:
    return SimulationResult(
        live_receipt=live,
        draft_receipt=draft,
        executed=False,
        changed=live.selected_deployment != draft.selected_deployment,
    )


def receipt_from_unavailable(
    *,
    request_id: str,
    assigned_model: str | None,
    reason: str,
    message: str,
) -> ContractDecisionReceipt:
    """Represent an unavailable route without aborting a draft/live comparison."""
    rejected = RejectedCandidate(model=assigned_model, reason=reason) if assigned_model else None
    return ContractDecisionReceipt(
        request_id=request_id,
        selected_model="",
        selected_deployment="",
        rejected_candidates=(rejected,) if rejected is not None else (),
        evidence={"routing_error": message, "reason": reason},
    )


__all__ = [
    "ContractDecisionReceipt",
    "RejectedCandidate",
    "SimulationResult",
    "compare_decisions",
    "receipt_from_decision",
    "receipt_from_unavailable",
]
