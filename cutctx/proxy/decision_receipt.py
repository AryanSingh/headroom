"""Provider-neutral, privacy-safe request decision receipts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from cutctx import __version__

DECISION_RECEIPT_SCHEMA_VERSION = 1

_CONFIG_FINGERPRINT_FIELDS = (
    "min_tokens_to_crush",
    "ccr_inject_tool",
    "ccr_inject_marker",
    "ccr_handle_responses",
    "ccr_store_ttl_seconds",
    "cache_enabled",
    "cache_aligner_enabled",
    "prefix_freeze_enabled",
    "model_routing_preset",
    "workload_class",
    "context_budget_enabled",
    "context_budget_max_tokens",
    "context_budget_policy",
)

_REASON_EXPLANATIONS = {
    "confidence_below_threshold": (
        "Routing evidence was insufficient to justify a model change, so Cutctx retained "
        "the requested model."
    ),
    "target_missing_capabilities": (
        "The candidate lacked proof for one or more required capabilities, so Cutctx "
        "retained the requested model."
    ),
    "downgrade_blocked_unproven_transport": (
        "The target transport or account could not be proven safe, so Cutctx retained "
        "the requested model."
    ),
    "low_complexity": (
        "The request passed the configured safety and compatibility gates for the "
        "selected lower-cost model."
    ),
    "downgrade_applied": (
        "The request passed the configured safety and compatibility gates for the "
        "selected lower-cost model."
    ),
    "no_route_for_model": (
        "The active routing policy had no eligible target for the requested model."
    ),
    "account_transport_mismatch": (
        "The account's provider transport could not be proven compatible with the "
        "candidate model, so Cutctx retained the requested model."
    ),
    "calibrated_scorer_required": (
        "Routing requires a calibrated complexity scorer that was not available, so "
        "Cutctx retained the requested model."
    ),
    "cost_lookup_failed": (
        "Cutctx could not verify that the candidate model was cheaper, so it retained "
        "the requested model."
    ),
    "router_disabled": (
        "Model routing is turned off, so every request keeps its originally requested model."
    ),
    "router_error": (
        "An internal routing check failed safely, so Cutctx retained the requested model."
    ),
    "transport_mismatch": (
        "The provider transport for the candidate model did not match the request, so "
        "Cutctx retained the requested model."
    ),
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return [str(item) for item in value if item is not None]


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list | tuple):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _cache_status(*, observed: bool, hit: bool) -> str:
    if not observed:
        return "unobserved"
    return "hit" if hit else "miss"


def explain_routing_reason(
    reason: str | None,
    selection_evidence: Mapping[str, Any] | None = None,
) -> str:
    """Return stable, operator-facing copy for a routing reason code."""

    if reason == "workload_not_downgradeable":
        signals = set(_string_list((selection_evidence or {}).get("signals")))
        if "recent_tool_context" in signals:
            return (
                "Recent tool context was classified as high-risk, so Cutctx retained "
                "the requested model."
            )
        return (
            "The workload was classified as high-complexity or high-risk, so Cutctx "
            "retained the requested model."
        )
    if reason in _REASON_EXPLANATIONS:
        return _REASON_EXPLANATIONS[reason]
    if reason:
        return f"Cutctx recorded routing outcome '{reason}'. Review the evidence below for details."
    return "No model-routing decision was observed for this request."


def fingerprint_decision_config(config: Any | None) -> str | None:
    """Hash only allow-listed, non-secret controls that affect decisions."""

    if config is None:
        return None
    values = {name: getattr(config, name, None) for name in _CONFIG_FINGERPRINT_FIELDS}
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_decision_receipt(
    evidence: Mapping[str, Any],
    *,
    config: Any | None = None,
    payload_capture: str = "disabled",
) -> dict[str, Any]:
    """Normalize already-observed request evidence into schema version 1."""

    routing_trace = _mapping(evidence.get("routing_trace"))
    routing_summary = _mapping(evidence.get("routing_summary"))
    selection_evidence = _mapping(routing_trace.get("selection_evidence"))
    reason_value = routing_trace.get("reason") or routing_summary.get("reason")
    reason = str(reason_value) if reason_value else None
    routing_observed = bool(routing_trace or routing_summary)
    applied = bool(routing_trace.get("applied", routing_summary.get("routed", False)))
    routing_status = "applied" if applied else "retained" if routing_observed else "unobserved"

    transforms = _string_list(evidence.get("transforms"))
    decline_value = evidence.get("decline_reason")
    decline_reason = str(decline_value) if decline_value else None
    direct_saved = _integer(evidence.get("direct_tokens_saved"))
    compression_observed = any(
        key in evidence
        for key in ("input_tokens_original", "input_tokens_forwarded", "direct_tokens_saved")
    )
    compression_status = (
        "applied"
        if direct_saved > 0 or transforms
        else "abstained"
        if compression_observed and decline_reason
        else "not_evaluated"
        if compression_observed
        else "unobserved"
    )

    provider_observed = bool(evidence.get("provider_cache_observed", False))
    provider_read = _integer(evidence.get("provider_cache_read_tokens"))
    semantic_evaluated = bool(evidence.get("semantic_cache_evaluated", False))
    semantic_hit = bool(evidence.get("semantic_cache_hit", False))
    prefix_evaluated = bool(evidence.get("prefix_cache_evaluated", False))
    prefix_saved = _integer(evidence.get("prefix_cache_saved_tokens"))
    protected_tokens = _integer(evidence.get("cache_protected_tokens"))
    cache_protection_evaluated = bool(evidence.get("cache_protection_evaluated", False))

    ccr_references = [
        {
            "hash": str(item.get("hash")),
            "availability": str(item.get("availability") or "unobserved"),
            "expires_at": item.get("expires_at"),
        }
        for item in evidence.get("ccr_references") or []
        if isinstance(item, Mapping) and item.get("hash")
    ]
    ccr_outcome_value = evidence.get("ccr_retrieval_outcome")
    ccr_outcome = str(ccr_outcome_value) if ccr_outcome_value else None
    if any(item["availability"] == "available" for item in ccr_references):
        ccr_status = "available"
    elif ccr_references and all(item["availability"] == "expired" for item in ccr_references):
        ccr_status = "expired"
    elif ccr_references and all(item["availability"] == "missing" for item in ccr_references):
        ccr_status = "missing"
    elif ccr_references:
        ccr_status = "unobserved"
    else:
        ccr_status = "not_used"

    missing: list[str] = []
    if not routing_trace:
        missing.extend(("routing.confidence", "routing.rejected_candidates", "routing.transport"))
    if not provider_observed:
        missing.append("cache.provider_prompt_cache")
    if ccr_references and ccr_outcome is None:
        missing.append("ccr.retrieval_outcome")

    return {
        "schema_version": DECISION_RECEIPT_SCHEMA_VERSION,
        "request_id": evidence.get("request_id"),
        "observation": {
            "completeness": "complete" if not missing else "partial",
            "missing": sorted(set(missing)),
            "payload_capture": payload_capture,
        },
        "routing": {
            "status": routing_status,
            "reason": reason,
            "explanation": explain_routing_reason(reason, selection_evidence),
            "requested_model": routing_trace.get("requested_model")
            or routing_summary.get("requested_model")
            or evidence.get("requested_model"),
            "effective_model": routing_trace.get("effective_model")
            or routing_summary.get("actual_model")
            or evidence.get("effective_model"),
            "mechanism": routing_trace.get("mechanism"),
            "confidence": _float_or_none(routing_trace.get("confidence")),
            "scorer": routing_trace.get("scorer"),
            "required_capabilities": _string_list(routing_trace.get("required_capabilities")),
            "candidates": _string_list(routing_trace.get("candidates")),
            "rejected_candidates": _mapping_list(routing_trace.get("rejected_candidates")),
            "transport": _mapping(routing_trace.get("transport")),
            "selection_evidence": selection_evidence,
            "request_overrides": routing_summary.get("request_overrides"),
        },
        "compression": {
            "status": compression_status,
            "reason": decline_reason,
            "input_tokens_original": evidence.get("input_tokens_original"),
            "input_tokens_forwarded": evidence.get("input_tokens_forwarded"),
            "direct_tokens_saved": direct_saved,
            "transforms": transforms,
            "protected_content": {
                "cache_protected_tokens": protected_tokens,
                "signals": _string_list(selection_evidence.get("signals")),
            },
        },
        "cache": {
            "provider_prompt_cache": {
                "status": _cache_status(observed=provider_observed, hit=provider_read > 0),
                "read_tokens": provider_read,
                "write_tokens": _integer(evidence.get("provider_cache_write_tokens")),
                "inferred": bool(evidence.get("provider_cache_inferred", False)),
            },
            "semantic_response_cache": {
                "status": _cache_status(observed=semantic_evaluated, hit=semantic_hit),
                "saved_tokens": _integer(evidence.get("semantic_cache_saved_tokens")),
            },
            "self_hosted_prefix_cache": {
                "status": _cache_status(observed=prefix_evaluated, hit=prefix_saved > 0),
                "saved_tokens": prefix_saved,
            },
            "cache_safe_prefix": {
                "status": (
                    "protected"
                    if protected_tokens > 0
                    else "not_protected"
                    if cache_protection_evaluated
                    else "unobserved"
                ),
                "protected_tokens": protected_tokens,
            },
        },
        "ccr": {
            "status": ccr_status,
            "references": ccr_references,
            "retrieval_outcome": ccr_outcome
            or ("not_requested" if not ccr_references else "unobserved"),
        },
        "attribution": {
            "total_saved_tokens": _integer(evidence.get("total_saved_tokens")),
            "created_savings_tokens": _integer(evidence.get("created_savings_tokens")),
            "observed_provider_savings_tokens": _integer(
                evidence.get("observed_provider_savings_tokens")
            ),
            "by_source_tokens": _mapping(evidence.get("by_source_tokens")),
            "by_source_usd": _mapping(evidence.get("by_source_usd")),
            "savings_basis": evidence.get("savings_basis") or "estimated",
            "pricing_basis": evidence.get("pricing_basis") or "model_input_list_price",
        },
        "policy": {
            "routing_policy": routing_trace.get("policy"),
            "routing_mode": routing_trace.get("mode"),
            "config_fingerprint": fingerprint_decision_config(config),
            "cutctx_version": __version__,
        },
    }


def build_legacy_decision_receipt(
    log: Mapping[str, Any],
    *,
    payload_capture: str,
) -> dict[str, Any]:
    """Adapt a receipt-less historical request row without inventing evidence."""

    routing_summary = _mapping(log.get("routing_metadata"))
    provider_cache_tokens = _integer(log.get("cache_saved_tokens"))
    semantic_cache_tokens = _integer(log.get("semantic_cache_saved_tokens"))
    prefix_cache_tokens = _integer(log.get("self_hosted_prefix_cache_saved_tokens"))
    receipt = build_decision_receipt(
        {
            "request_id": log.get("request_id"),
            "requested_model": routing_summary.get("requested_model") or log.get("model"),
            "effective_model": log.get("model"),
            "routing_summary": routing_summary,
            "input_tokens_original": log.get("input_tokens_original"),
            "input_tokens_forwarded": log.get("input_tokens_optimized"),
            "direct_tokens_saved": log.get("tokens_saved"),
            "transforms": log.get("transforms_applied") or [],
            "decline_reason": log.get("decline_reason"),
            "provider_cache_observed": provider_cache_tokens > 0,
            "provider_cache_read_tokens": provider_cache_tokens,
            "semantic_cache_evaluated": semantic_cache_tokens > 0,
            "semantic_cache_hit": semantic_cache_tokens > 0,
            "semantic_cache_saved_tokens": semantic_cache_tokens,
            "prefix_cache_evaluated": prefix_cache_tokens > 0,
            "prefix_cache_saved_tokens": prefix_cache_tokens,
            "total_saved_tokens": log.get("total_saved_tokens"),
            "created_savings_tokens": log.get("created_savings_tokens"),
            "observed_provider_savings_tokens": log.get("observed_provider_savings_tokens"),
            "by_source_tokens": log.get("savings_by_source_tokens") or {},
            "by_source_usd": log.get("savings_by_source_usd") or {},
            "savings_basis": log.get("savings_basis"),
            "pricing_basis": log.get("pricing_basis"),
        },
        payload_capture=payload_capture,
    )
    receipt["observation"]["completeness"] = "legacy"
    receipt["observation"]["missing"] = sorted(
        set(receipt["observation"]["missing"])
        | {"routing.rejected_candidates", "routing.transport", "ccr.availability"}
    )
    return receipt


def build_minimal_decision_receipt(
    request_id: str,
    *,
    payload_capture: str,
    failure: str,
) -> dict[str, Any]:
    """Build a parseable partial receipt when the normalizer itself fails."""

    receipt = build_decision_receipt(
        {"request_id": request_id},
        payload_capture=payload_capture,
    )
    receipt["observation"]["completeness"] = "partial"
    receipt["observation"]["missing"] = [failure]
    return receipt


__all__ = [
    "DECISION_RECEIPT_SCHEMA_VERSION",
    "build_decision_receipt",
    "build_legacy_decision_receipt",
    "build_minimal_decision_receipt",
    "explain_routing_reason",
    "fingerprint_decision_config",
]
