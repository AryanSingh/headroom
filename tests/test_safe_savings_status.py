"""Unit tests for the pure Safe Savings status and explanation model."""

from __future__ import annotations

import pytest

from cutctx.proxy.model_router import ModelRouter, ModelRouterConfig
from cutctx.proxy.safe_savings_status import (
    build_safe_savings_status,
    explain_safe_savings_reason,
    safe_savings_experience_enabled,
)


def test_safe_savings_experience_flag_is_explicit_opt_in() -> None:
    assert safe_savings_experience_enabled({}) is False
    assert safe_savings_experience_enabled({"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "true"}) is True
    assert safe_savings_experience_enabled({"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "0"}) is False


def test_safe_savings_status_without_router_is_off_and_read_only() -> None:
    status = build_safe_savings_status(
        router=None,
        preset=None,
        recent_requests=[],
        experience_enabled=True,
    )
    assert status == {
        "schema_version": 1,
        "experience_enabled": True,
        "enabled": False,
        "mode": "off",
        "preset": None,
        "route_count": 0,
        "routes": [],
        "transport_safe_targets": [],
        "decision": None,
        "rollback_available": False,
    }


def test_safe_savings_status_lists_exact_routes_and_applied_decision() -> None:
    router = ModelRouter(ModelRouterConfig.codex_gpt54mini_high_preset())
    recent = [
        {
            "request_id": "req-1",
            "routing_metadata": {
                "requested_model": "gpt-5.6-sol",
                "actual_model": "gpt-5.4-mini",
                "reason": "downgrade_applied",
                "routed": True,
                "confidence": 0.9,
                "signals": ["explicit_low_complexity"],
            },
        }
    ]
    before_routes = list(router.config.routes)

    status = build_safe_savings_status(
        router=router,
        preset="codex-gpt54mini-high",
        recent_requests=recent,
        experience_enabled=True,
    )

    assert status["routes"][0].keys() >= {
        "source_model",
        "low_target_model",
        "medium_target_model",
        "low_target_capabilities",
        "medium_target_capabilities",
        "low_target_transport_safe",
        "medium_target_transport_safe",
    }
    assert status["decision"] == {
        "request_id": "req-1",
        "requested_model": "gpt-5.6-sol",
        "effective_model": "gpt-5.4-mini",
        "candidate_model": "gpt-5.4-mini",
        "applied": True,
        "reason": "downgrade_applied",
        "title": "Safe route applied",
        "explanation": (
            "The request passed the configured safety and compatibility gates "
            "for the selected lower-cost model."
        ),
        "scorer": None,
        "confidence": 0.9,
        "signals": ["explicit_low_complexity"],
        "required_capabilities": [],
        "missing_capabilities": [],
        "transport": {},
    }
    assert list(router.config.routes) == before_routes


@pytest.mark.parametrize(
    "reason",
    [
        "account_transport_mismatch",
        "calibrated_scorer_required",
        "confidence_below_threshold",
        "cost_lookup_failed",
        "downgrade_applied",
        "downgrade_blocked_unproven_transport",
        "no_route_for_model",
        "router_disabled",
        "router_error",
        "target_missing_capabilities",
        "transport_mismatch",
        "workload_not_downgradeable",
    ],
)
def test_every_terminal_reason_has_stable_operator_copy(reason: str) -> None:
    explanation = explain_safe_savings_reason(reason)
    assert explanation["title"]
    assert explanation["explanation"]
    assert reason not in explanation["explanation"]


def test_unknown_reason_and_partial_legacy_metadata_are_safe() -> None:
    status = build_safe_savings_status(
        router=None,
        preset=None,
        recent_requests=[
            {
                "request_id": "legacy",
                "model": "requested-model",
                "routing_metadata": {"reason": "future_reason"},
            }
        ],
        experience_enabled=True,
    )
    assert status["decision"]["reason"] == "future_reason"
    assert status["decision"]["title"] == "Routing decision recorded"
    assert status["decision"]["effective_model"] == "requested-model"
    assert status["decision"]["confidence"] is None
