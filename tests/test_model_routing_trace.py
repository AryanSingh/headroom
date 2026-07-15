from __future__ import annotations

from types import SimpleNamespace

import pytest

from cutctx.orchestration import RoutingUnavailableError
from cutctx.proxy.model_router import ModelRouter, ModelRouterConfig, prepare_model_routing
from cutctx.proxy.model_routing_trace import (
    MODEL_ROUTING_TRACE_SCHEMA_VERSION,
    ModelRoutingDecisionTrace,
)
from cutctx.proxy.savings_metadata import merge_savings_metadata


def test_trace_schema_serializes_all_core_fields() -> None:
    trace = ModelRoutingDecisionTrace(
        request_id="req-1",
        mechanism="optimization_preset",
        requested_model="strong",
        effective_model="mini",
        reason="downgrade_applied",
        applied=True,
        candidates=["strong", "mini"],
    ).to_dict()

    assert trace["schema_version"] == MODEL_ROUTING_TRACE_SCHEMA_VERSION
    assert trace["requested_model"] == "strong"
    assert trace["effective_model"] == "mini"
    assert trace["candidates"] == ["strong", "mini"]


def test_trace_survives_handler_metadata_merge_without_becoming_savings() -> None:
    trace = ModelRoutingDecisionTrace(
        request_id="req-merge",
        mechanism="optimization_preset",
        requested_model="strong",
        effective_model="strong",
        reason="confidence_below_threshold",
        applied=False,
    ).to_dict()

    merged = merge_savings_metadata(
        {"model_routing_trace": trace},
        {"semantic_cache": {"tokens": 10}},
    )

    assert merged["model_routing_trace"] == trace
    assert merged["semantic_cache"]["tokens"] == 10


def test_preset_applied_and_abstained_decisions_emit_same_trace_shape() -> None:
    router = ModelRouter(ModelRouterConfig.codex_gpt54mini_high_preset())
    handler = type("Handler", (), {"_model_router": router})()

    routed_model, routed_metadata = prepare_model_routing(
        handler,
        "gpt-5.4",
        messages=[{"role": "user", "content": "hello"}],
        num_messages=1,
        request_id="req-routed",
        request_savings_metadata={},
    )
    retained_model, retained_metadata = prepare_model_routing(
        handler,
        "gpt-5.4",
        messages=[{"role": "user", "content": "Implement production security migration."}],
        num_messages=1,
        request_id="req-retained",
        request_savings_metadata={},
    )

    assert routed_model == "gpt-5.4-mini"
    assert retained_model == "gpt-5.4"
    routed = routed_metadata["model_routing_trace"]
    retained = retained_metadata["model_routing_trace"]
    assert set(routed) == set(retained)
    assert routed["applied"] is True
    assert retained["applied"] is False
    assert retained["reason"] == "workload_not_downgradeable"
    assert retained["rejected_candidates"]


def test_abstained_routing_trace_has_dashboard_safe_summary() -> None:
    router = ModelRouter(ModelRouterConfig.economy_preset())
    handler = type("Handler", (), {"_model_router": router})()

    model, metadata = prepare_model_routing(
        handler,
        "gpt-5.6-terra",
        messages=[{"role": "tool", "content": "repository output"}, {"role": "user", "content": "summarize this"}],
        num_messages=2,
        request_id="req-tool-context",
        request_savings_metadata={},
    )

    assert model == "gpt-5.6-terra"
    assert metadata["model_routing"]["source_model"] == "gpt-5.6-terra"
    assert metadata["model_routing"]["target_model"] == "gpt-5.6-terra"
    assert metadata["model_routing"]["reason"] == "workload_not_downgradeable"


def _orchestration_decision(**overrides):  # type: ignore[no-untyped-def]
    values = {
        "actual_model": "gpt-5.4-mini",
        "assigned_model": "openai:main:gpt-5.4-mini",
        "provider": "openai",
        "account_id": "main",
        "role": "worker",
        "binding_id": "worker-mini",
        "reason": "deterministic_assignment",
        "fallback_used": False,
        "fallback_trigger": None,
        "fallback_from": None,
        "policy": "role_locked",
        "mode": "strict",
        "candidates": ["openai:main:gpt-5.4-mini"],
        "required_capabilities": {"tool_calling"},
        "attempted_deployments": ["openai:main:gpt-5.4-mini"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_orchestration_trace_contains_binding_capability_and_transport_proof() -> None:
    service = type("Service", (), {"route": lambda self, request: _orchestration_decision()})()
    handler = type(
        "Handler",
        (),
        {
            "_orchestration_service": service,
            "_orchestration_account_id": "main",
            "_model_router": None,
        },
    )()

    model, metadata = prepare_model_routing(
        handler,
        "role:worker",
        transport_provider="openai",
        request_id="req-orchestration",
    )

    assert model == "gpt-5.4-mini"
    trace = metadata["model_routing_trace"]
    assert trace["mechanism"] == "deterministic_orchestration"
    assert trace["binding_id"] == "worker-mini"
    assert trace["required_capabilities"] == ["tool_calling"]
    assert trace["transport"]["provider_proven"] is True
    assert trace["transport"]["account_proven"] is True


def test_transport_mismatch_error_carries_rejected_decision_trace() -> None:
    service = type(
        "Service",
        (),
        {"route": lambda self, request: _orchestration_decision(provider="anthropic")},
    )()
    handler = type("Handler", (), {"_orchestration_service": service, "_model_router": None})()

    with pytest.raises(RoutingUnavailableError) as captured:
        prepare_model_routing(handler, "role:worker", transport_provider="openai")

    trace = captured.value.decision_trace
    assert trace["reason"] == "transport_mismatch"
    assert trace["applied"] is False
    assert trace["transport"]["provider_proven"] is False
    assert trace["rejected_candidates"][0]["reason"] == "transport_mismatch"


def test_orchestration_trace_exposes_equivalent_reliability_selection() -> None:
    decision = _orchestration_decision(
        reason="equivalent_deployment_selected",
        account_id="secondary",
        selection_evidence={
            "strategy": "equivalent_reliability",
            "selected": "openai:secondary:gpt-5.4-mini",
            "scores": [
                {
                    "deployment": "openai:secondary:gpt-5.4-mini",
                    "score": 0.95,
                    "health": 1.0,
                }
            ],
        },
    )
    service = type("Service", (), {"route": lambda self, request: decision})()
    handler = type(
        "Handler",
        (),
        {
            "_orchestration_service": service,
            "_orchestration_account_id": "secondary",
            "_model_router": None,
        },
    )()

    _model, metadata = prepare_model_routing(handler, "role:worker", transport_provider="openai")

    evidence = metadata["model_routing_trace"]["selection_evidence"]
    assert evidence["strategy"] == "equivalent_reliability"
    assert evidence["selected"] == "openai:secondary:gpt-5.4-mini"
