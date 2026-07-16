from __future__ import annotations

from types import SimpleNamespace

from cutctx.proxy.decision_receipt import (
    DECISION_RECEIPT_SCHEMA_VERSION,
    build_decision_receipt,
    build_legacy_decision_receipt,
    build_minimal_decision_receipt,
    explain_routing_reason,
    fingerprint_decision_config,
)


def _complete_evidence() -> dict:
    return {
        "request_id": "req-1",
        "requested_model": "gpt-5.4",
        "effective_model": "gpt-5.4",
        "routing_trace": {
            "schema_version": 1,
            "mechanism": "optimization_preset",
            "requested_model": "gpt-5.4",
            "effective_model": "gpt-5.4",
            "reason": "workload_not_downgradeable",
            "applied": False,
            "confidence": 0.93,
            "scorer": "heuristic_v1",
            "required_capabilities": ["tool_calling"],
            "candidates": ["gpt-5.4-mini"],
            "rejected_candidates": [
                {
                    "candidate": "gpt-5.4-mini",
                    "reason": "workload_not_downgradeable",
                }
            ],
            "transport": {"target_proven": True},
            "selection_evidence": {
                "complexity": "high",
                "signals": ["recent_tool_context"],
            },
            "policy": "conservative",
            "mode": "safe",
        },
        "input_tokens_original": 1500,
        "input_tokens_forwarded": 1000,
        "direct_tokens_saved": 300,
        "transforms": ["smart_crusher"],
        "cache_protected_tokens": 200,
        "cache_protection_evaluated": True,
        "provider_cache_observed": True,
        "provider_cache_read_tokens": 200,
        "provider_cache_write_tokens": 0,
        "provider_cache_inferred": False,
        "semantic_cache_evaluated": False,
        "semantic_cache_hit": False,
        "semantic_cache_saved_tokens": 0,
        "prefix_cache_evaluated": False,
        "prefix_cache_saved_tokens": 0,
        "ccr_references": [],
        "ccr_retrieval_outcome": None,
        "total_saved_tokens": 500,
        "created_savings_tokens": 300,
        "observed_provider_savings_tokens": 200,
        "by_source_tokens": {
            "cutctx_compression": 300,
            "provider_prompt_cache": 200,
        },
        "by_source_usd": {},
        "savings_basis": "estimated",
        "pricing_basis": "model_input_list_price",
    }


def test_workload_not_downgradeable_explains_recent_tool_retention() -> None:
    explanation = explain_routing_reason(
        "workload_not_downgradeable",
        {"complexity": "high", "signals": ["recent_tool_context"]},
    )

    assert "recent tool context" in explanation.lower()
    assert "retained" in explanation.lower()


def test_complete_receipt_separates_created_and_observed_savings() -> None:
    receipt = build_decision_receipt(_complete_evidence())

    assert receipt["schema_version"] == DECISION_RECEIPT_SCHEMA_VERSION
    assert receipt["observation"]["completeness"] == "complete"
    assert receipt["routing"]["status"] == "retained"
    assert receipt["routing"]["reason"] == "workload_not_downgradeable"
    assert receipt["routing"]["rejected_candidates"][0]["candidate"] == "gpt-5.4-mini"
    assert receipt["cache"]["provider_prompt_cache"]["status"] == "hit"
    assert receipt["cache"]["semantic_response_cache"]["status"] == "unobserved"
    assert receipt["cache"]["cache_safe_prefix"]["status"] == "protected"
    assert receipt["attribution"]["created_savings_tokens"] == 300
    assert receipt["attribution"]["observed_provider_savings_tokens"] == 200


def test_explicit_cache_zeroes_are_misses_not_unobserved() -> None:
    observed = build_decision_receipt(
        {
            "request_id": "observed",
            "provider_cache_observed": True,
            "provider_cache_read_tokens": 0,
            "cache_protection_evaluated": True,
            "cache_protected_tokens": 0,
        }
    )
    missing = build_decision_receipt(
        {
            "request_id": "missing",
            "provider_cache_observed": False,
            "provider_cache_read_tokens": 0,
            "cache_protection_evaluated": False,
            "cache_protected_tokens": 0,
        }
    )

    assert observed["cache"]["provider_prompt_cache"]["status"] == "miss"
    assert observed["cache"]["cache_safe_prefix"]["status"] == "not_protected"
    assert missing["cache"]["provider_prompt_cache"]["status"] == "unobserved"
    assert missing["cache"]["cache_safe_prefix"]["status"] == "unobserved"


def test_config_fingerprint_is_stable_and_ignores_secrets() -> None:
    left = SimpleNamespace(
        min_tokens_to_crush=500,
        cache_enabled=True,
        model_routing_preset="codex-gpt54mini-high",
        admin_api_key="secret-a",
    )
    right = SimpleNamespace(
        model_routing_preset="codex-gpt54mini-high",
        cache_enabled=True,
        min_tokens_to_crush=500,
        admin_api_key="secret-b",
    )
    changed = SimpleNamespace(
        min_tokens_to_crush=750,
        cache_enabled=True,
        model_routing_preset="codex-gpt54mini-high",
        admin_api_key="secret-a",
    )

    assert fingerprint_decision_config(left) == fingerprint_decision_config(right)
    assert fingerprint_decision_config(left) != fingerprint_decision_config(changed)
    assert "secret" not in str(fingerprint_decision_config(left))


def test_malformed_evidence_is_partial_and_does_not_copy_payloads() -> None:
    receipt = build_decision_receipt(
        {
            "request_id": "bad",
            "routing_trace": "not-a-mapping",
            "request_messages": [{"role": "user", "content": "private"}],
        }
    )

    serialized = str(receipt)
    assert receipt["observation"]["completeness"] == "partial"
    assert "private" not in serialized
    assert "request_messages" not in serialized


def test_legacy_and_minimal_receipts_are_explicit_about_missing_evidence() -> None:
    legacy = build_legacy_decision_receipt(
        {
            "request_id": "legacy",
            "model": "gpt-5.4",
            "tokens_saved": 10,
            "transforms_applied": ["smart_crusher"],
        },
        payload_capture="disabled",
    )
    minimal = build_minimal_decision_receipt(
        "failed",
        payload_capture="disabled",
        failure="receipt_builder_failed",
    )

    assert legacy["observation"]["completeness"] == "legacy"
    assert "routing.rejected_candidates" in legacy["observation"]["missing"]
    assert minimal["observation"]["completeness"] == "partial"
    assert minimal["observation"]["missing"] == ["receipt_builder_failed"]
