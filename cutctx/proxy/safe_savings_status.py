"""Privacy-safe presentation model for conservative model routing."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any

from cutctx.proxy.decision_receipt import explain_routing_reason
from cutctx.proxy.model_router import model_routing_mode_for_state

SAFE_SAVINGS_STATUS_SCHEMA_VERSION = 1
_TRUE_VALUES = {"1", "true", "yes", "on"}
_REASON_TITLES = {
    "account_transport_mismatch": "Account proof blocked routing",
    "calibrated_scorer_required": "Calibration required",
    "confidence_below_threshold": "Confidence protected the request",
    "cost_lookup_failed": "Cost proof unavailable",
    "downgrade_applied": "Safe route applied",
    "downgrade_blocked_unproven_transport": "Transport proof blocked routing",
    "no_route_for_model": "No exact route configured",
    "router_disabled": "Routing is off",
    "router_error": "Routing retained the requested model",
    "target_missing_capabilities": "Capability proof blocked routing",
    "transport_mismatch": "Provider transport blocked routing",
    "workload_not_downgradeable": "Workload retained on requested model",
}


def safe_savings_experience_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether the optional operator experience is discoverable."""
    values = os.environ if env is None else env
    return str(values.get("CUTCTX_SAFE_SAVINGS_EXPERIENCE", "")).strip().lower() in _TRUE_VALUES


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value if item is not None]


def explain_safe_savings_reason(
    reason: str | None,
    *,
    selection_evidence: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Return stable, human-readable copy without changing routing policy."""
    return {
        "title": _REASON_TITLES.get(reason or "", "Routing decision recorded"),
        "explanation": explain_routing_reason(reason, selection_evidence),
    }


def _route_status(route: Any, safe_targets: set[str]) -> dict[str, Any]:
    low_target = str(route.target)
    medium_target = str(route.medium_target) if route.medium_target else None
    return {
        "source_model": str(route.source),
        "low_target_model": low_target,
        "medium_target_model": medium_target,
        "low_target_capabilities": sorted(
            str(item) for item in (route.target_capabilities or set())
        ),
        "medium_target_capabilities": sorted(
            str(item) for item in (route.medium_target_capabilities or set())
        ),
        "low_target_transport_safe": low_target in safe_targets,
        "medium_target_transport_safe": bool(
            medium_target and medium_target in safe_targets
        ),
    }


def _latest_decision(
    recent_requests: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    for request in reversed(recent_requests):
        summary = request.get("routing_metadata")
        if not isinstance(summary, Mapping) or not summary:
            continue
        receipt = request.get("decision_receipt")
        receipt_routing = (
            receipt.get("routing")
            if isinstance(receipt, Mapping) and isinstance(receipt.get("routing"), Mapping)
            else {}
        )
        reason_value = summary.get("reason")
        reason = str(reason_value) if reason_value else None
        requested_model = summary.get("requested_model")
        effective_model = summary.get("actual_model") or request.get("model") or requested_model
        selection_evidence = (
            summary.get("selection_evidence")
            if isinstance(summary.get("selection_evidence"), Mapping)
            else receipt_routing.get("selection_evidence")
        )
        explanation = explain_safe_savings_reason(
            reason,
            selection_evidence=(
                selection_evidence if isinstance(selection_evidence, Mapping) else None
            ),
        )
        transport = summary.get("transport")
        if not isinstance(transport, Mapping):
            transport = receipt_routing.get("transport")
        required_capabilities = _string_list(summary.get("required_capabilities"))
        if not required_capabilities:
            required_capabilities = _string_list(receipt_routing.get("required_capabilities"))
        missing_capabilities = _string_list(summary.get("missing_capabilities"))
        if not missing_capabilities and reason == "target_missing_capabilities":
            missing_capabilities = _string_list(
                selection_evidence.get("signals") if isinstance(selection_evidence, Mapping) else None
            )
        signals = _string_list(summary.get("signals"))
        if not signals and isinstance(selection_evidence, Mapping):
            signals = _string_list(selection_evidence.get("signals"))
        return {
            "request_id": str(request.get("request_id") or ""),
            "requested_model": requested_model,
            "effective_model": effective_model,
            "candidate_model": summary.get("target_model") or effective_model,
            "applied": bool(summary.get("routed", False)),
            "reason": reason,
            **explanation,
            "scorer": summary.get("scorer") or receipt_routing.get("scorer"),
            "confidence": (
                summary.get("confidence")
                if summary.get("confidence") is not None
                else receipt_routing.get("confidence")
            ),
            "signals": signals,
            "required_capabilities": required_capabilities,
            "missing_capabilities": missing_capabilities,
            "transport": dict(transport) if isinstance(transport, Mapping) else {},
        }
    return None


def build_safe_savings_status(
    *,
    router: Any | None,
    preset: str | None,
    recent_requests: Sequence[Mapping[str, Any]] = (),
    experience_enabled: bool | None = None,
) -> dict[str, Any]:
    """Build an observational routing status without changing router state."""
    config = getattr(router, "config", None)
    routes = list(getattr(config, "routes", []) or [])
    enabled = bool(getattr(config, "enabled", False))
    safe_targets = {str(item) for item in (getattr(config, "transport_safe_targets", set()) or set())}
    return {
        "schema_version": SAFE_SAVINGS_STATUS_SCHEMA_VERSION,
        "experience_enabled": (
            safe_savings_experience_enabled()
            if experience_enabled is None
            else bool(experience_enabled)
        ),
        "enabled": enabled,
        "mode": model_routing_mode_for_state(
            enabled=enabled,
            preset=preset,
            route_count=len(routes),
        ),
        "preset": preset,
        "route_count": len(routes),
        "routes": [_route_status(route, safe_targets) for route in routes],
        "transport_safe_targets": sorted(safe_targets),
        "decision": _latest_decision(recent_requests),
        "rollback_available": enabled,
    }
