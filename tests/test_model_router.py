# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the config-driven cost-based model router (Blocker-5).

Production audit (production-audit-progress-2026-06-20.md)
found that the model_routing source was structurally zero
in live traffic. This file tests the new minimum-viable
router that closes that gap.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from cutctx.orchestration.models import Capability, ModelRecord
from cutctx.orchestration.registry import DynamicModelRegistry
from cutctx.proxy.model_router import (
    ModelRoute,
    ModelRouter,
    ModelRouterConfig,
    TaskComplexity,
    TaskComplexityAssessment,
    assess_task_complexity,
    classify_task_complexity,
    prepare_model_routing,
)
from cutctx.proxy.savings_canary import CanaryAssignment

# ─- Config loading ───────────────────────────────────────────────


def test_config_from_env_empty_when_unset() -> None:
    """Unset env var produces an empty config (no routing)."""
    with patch.dict(os.environ, {}, clear=True):
        cfg = ModelRouterConfig.from_env()
    assert cfg.enabled is False
    # Default config has 4 hardcoded routes; an empty env means defaults.
    assert len(cfg.routes) == 4


def test_config_from_env_disabled_by_default() -> None:
    """Setting the env var to an empty JSON object still leaves
    enabled=False. The router is OFF by default.
    """
    with patch.dict(os.environ, {"CUTCTX_MODEL_ROUTING": "{}"}):
        cfg = ModelRouterConfig.from_env()
    assert cfg.enabled is False


def test_model_routing_canary_uses_gpt54mini_for_low_complexity_without_global_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Canary:
        def assign(self, *args, **kwargs):
            return CanaryAssignment(
                arm="model_routing",
                eligible=True,
                enabled=True,
                reason="assigned",
                bucket=25,
                assignment_identity_source="codex_session",
                assignment_sticky=True,
            )

    class _Handler:
        _model_router = None

    monkeypatch.setattr(
        "cutctx.proxy.savings_canary.get_savings_canary_coordinator",
        lambda: _Canary(),
    )
    target, metadata = prepare_model_routing(
        _Handler(),
        "gpt-5.4",
        messages=[{"role": "user", "content": "Rename this variable."}],
        request_id="stable-session",
        client="codex",
    )
    assert target == "gpt-5.4-mini"
    assert metadata["model_routing"]["request_overrides"]["reasoning"] == {"effort": "high"}


def test_config_from_env_parses_routes() -> None:
    payload = json.dumps(
        {
            "enabled": True,
            "downgrade_when": "always",
            "routes": [
                {
                    "source": "claude-opus-4-5",
                    "target": "claude-sonnet-4-5",
                },
                {
                    "source": "gpt-4o",
                    "target": "gpt-4o-mini",
                },
            ],
        }
    )
    with patch.dict(os.environ, {"CUTCTX_MODEL_ROUTING": payload}):
        cfg = ModelRouterConfig.from_env()
    assert cfg.enabled is True
    assert cfg.downgrade_when == "always"
    assert len(cfg.routes) == 2
    assert cfg.routes[0].source == "claude-opus-4-5"
    assert cfg.routes[0].target == "claude-sonnet-4-5"
    assert cfg.routes[1].source == "gpt-4o"
    assert cfg.routes[1].target == "gpt-4o-mini"


def test_config_from_env_invalid_json_falls_back_to_disabled() -> None:
    with patch.dict(os.environ, {"CUTCTX_MODEL_ROUTING": "not json"}):
        cfg = ModelRouterConfig.from_env()
    assert cfg.enabled is False


@pytest.mark.parametrize(
    "content",
    [
        "Prepare, commit, push, and release all files.",
        "Run the full benchmark suite and optimize the weakest path.",
        "Fix the production billing failure.",
        "Update all modules and services for the new API.",
        "Apply this patch:\n*** Begin Patch\n*** End Patch",
    ],
)
def test_classifier_keeps_high_consequence_short_tasks_on_strong_model(content: str) -> None:
    assert classify_task_complexity([{"role": "user", "content": content}]) != TaskComplexity.LOW


@pytest.mark.parametrize(
    "content",
    [
        "Rotate the credentials and update IAM permissions.",
        "Revoke API keys and audit access policies.",
    ],
)
def test_classifier_keeps_inflected_security_work_on_strong_model(content: str) -> None:
    assert classify_task_complexity([{"role": "user", "content": content}]) == TaskComplexity.HIGH


# ─- maybe_route() ───────────────────────────────────────────────


def test_disabled_router_always_passes_through() -> None:
    """A router with enabled=False never routes, regardless
    of the model.
    """
    r = ModelRouter(ModelRouterConfig(enabled=False))
    decision = r.maybe_route("claude-opus-4-5")
    assert decision.routing_applied is False
    assert decision.target_model is None
    assert decision.reason == "router_disabled"


def test_no_route_for_model_passes_through() -> None:
    """A router with no matching route for the requested model
    returns a pass-through decision.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[ModelRoute(source="gpt-4o", target="gpt-4o-mini")],
    )
    r = ModelRouter(cfg)
    decision = r.maybe_route("claude-opus-4-5")
    assert decision.routing_applied is False
    assert decision.reason == "no_route_for_model"


def test_aggressive_routes_current_model_to_certified_capability_candidate() -> None:
    """Aggressive routing must not depend on a stale source->target table."""
    registry = DynamicModelRegistry()
    registry.register(
        ModelRecord(
            provider="openai",
            id="gpt-5.6-terra",
            account_id="openai-main",
            capabilities={
                Capability.REASONING.value,
                Capability.STREAMING.value,
                Capability.TOOL_CALLING.value,
            },
            input_cost_per_million=10.0,
            available=True,
            metadata={"routing_certified": True, "quality_tier": "strong"},
        )
    )
    registry.register(
        ModelRecord(
            provider="openai",
            id="gpt-5.4-mini",
            account_id="openai-main",
            capabilities={
                Capability.REASONING.value,
                Capability.STREAMING.value,
                Capability.TOOL_CALLING.value,
            },
            input_cost_per_million=1.0,
            available=True,
            metadata={"routing_certified": True, "quality_tier": "fast"},
        )
    )

    router = ModelRouter(ModelRouterConfig.economy_preset(), registry=registry)

    decision = router.maybe_route(
        "gpt-5.6-terra",
        required_capabilities={
            Capability.REASONING.value,
            Capability.STREAMING.value,
            Capability.TOOL_CALLING.value,
        },
        transport_provider="openai",
        transport_account_id="openai-main",
    )

    assert decision.routing_applied is True
    assert decision.target_model == "gpt-5.4-mini"
    assert decision.reason == "catalog_candidate_selected"
    finalized = router.finalize_savings(decision, input_tokens=1_000_000)
    assert finalized.usd_saved == pytest.approx(9.0)


def test_aggressive_allows_certified_mini_on_proven_subscription_transport() -> None:
    class Handler:
        _orchestration_account_id = None

        def __init__(self) -> None:
            self._model_router = ModelRouter(
                ModelRouterConfig.economy_preset(), registry=DynamicModelRegistry()
            )

    target, metadata = prepare_model_routing(
        Handler(),
        "gpt-5.6-terra",
        messages=[{"role": "user", "content": "Fix typo in README."}],
        transport_provider="openai",
        implicit_downgrade_allowed=False,
    )

    assert target == "gpt-5.4-mini"
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"


def test_catalog_capability_rejection_cannot_fall_through_to_legacy_route() -> None:
    registry = DynamicModelRegistry()
    target = registry.get("openai:gpt-5.4-mini")
    assert target is not None
    target.capabilities.discard(Capability.VISION.value)

    router = ModelRouter(ModelRouterConfig.economy_preset(), registry=registry)
    decision = router.maybe_route(
        "gpt-5.6-terra",
        required_capabilities={Capability.VISION.value},
        transport_provider="openai",
    )

    assert decision.routing_applied is False
    assert decision.target_model is None
    assert decision.reason == "no_certified_capability_match"


@pytest.mark.parametrize(
    ("provider", "source_model", "expected_target"),
    [
        ("openai", "gpt-5.6-terra", "gpt-5.4-mini"),
        ("anthropic", "claude-opus-4-5", "claude-haiku-4-5"),
        ("google", "gemini-2.5-pro", "gemini-2.5-flash"),
    ],
)
def test_aggressive_catalog_routes_each_supported_provider_to_certified_candidate(
    provider: str,
    source_model: str,
    expected_target: str,
) -> None:
    router = ModelRouter(ModelRouterConfig.economy_preset(), registry=DynamicModelRegistry())

    decision = router.maybe_route(source_model, transport_provider=provider)

    assert decision.routing_applied is True
    assert decision.target_model == expected_target
    assert decision.reason == "catalog_candidate_selected"


def test_balanced_catalog_routes_medium_work_to_mid_tier_not_fast_tier() -> None:
    router = ModelRouter(
        ModelRouterConfig.codex_gpt54mini_high_preset(),
        registry=DynamicModelRegistry(),
    )
    assessment = TaskComplexityAssessment(
        complexity=TaskComplexity.MEDIUM,
        confidence=0.85,
        signals=("context_dependent",),
    )

    decision = router.maybe_route(
        "gpt-5.6-terra",
        task_complexity=TaskComplexity.MEDIUM,
        task_assessment=assessment,
        transport_provider="openai",
    )

    assert decision.routing_applied is True
    assert decision.target_model == "gpt-5.6-luna"


def test_route_applied_with_known_costs() -> None:
    """A route with known per-mtok costs applies the downgrade
    and returns the target model.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="claude-opus-4-5",
                target="claude-sonnet-4-5",
                source_cost_per_mtok=15.0,  # $15 per million input tokens
                target_cost_per_mtok=3.0,  # $3 per million
            )
        ],
    )
    r = ModelRouter(cfg)
    decision = r.maybe_route("claude-opus-4-5")
    assert decision.routing_applied is True
    assert decision.target_model == "claude-sonnet-4-5"
    assert decision.source_model == "claude-opus-4-5"
    # Per-mtok delta is 12.0; tokens_saved is filled in finalize.
    assert decision.tokens_saved == 0
    assert decision.usd_saved == 0.0


def test_workload_not_downgradeable_blocks_route() -> None:
    """When downgrade_when='low_cache_read' and the request
    has a high cache_read share, the route is NOT applied.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="low_cache_read",
        cache_read_threshold=0.5,
        routes=[
            ModelRoute(
                source="claude-opus-4-5",
                target="claude-sonnet-4-5",
                source_cost_per_mtok=15.0,
                target_cost_per_mtok=3.0,
            )
        ],
    )
    r = ModelRouter(cfg)
    decision = r.maybe_route(
        "claude-opus-4-5",
        cache_read_tokens=800,  # 80% cache share
        attempted_input_tokens=1000,
    )
    assert decision.routing_applied is False
    assert decision.reason == "workload_not_downgradeable"


def test_workload_downgradeable_passes_threshold() -> None:
    """When cache_read share is below the threshold, the
    route is applied.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="low_cache_read",
        cache_read_threshold=0.5,
        routes=[
            ModelRoute(
                source="claude-opus-4-5",
                target="claude-sonnet-4-5",
                source_cost_per_mtok=15.0,
                target_cost_per_mtok=3.0,
            )
        ],
    )
    r = ModelRouter(cfg)
    decision = r.maybe_route(
        "claude-opus-4-5",
        cache_read_tokens=200,  # 20% cache share
        attempted_input_tokens=1000,
    )
    assert decision.routing_applied is True
    assert decision.target_model == "claude-sonnet-4-5"


def test_always_downgrade_bypasses_workload_classifier() -> None:
    """When downgrade_when='always', the workload classifier
    is bypassed and the route is always applied.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="gpt-4o",
                target="gpt-4o-mini",
                source_cost_per_mtok=2.5,
                target_cost_per_mtok=0.15,
            )
        ],
    )
    r = ModelRouter(cfg)
    decision = r.maybe_route(
        "gpt-4o",
        cache_read_tokens=999,
        attempted_input_tokens=1000,
    )
    assert decision.routing_applied is True


def test_cost_lookup_failure_skips_route() -> None:
    """If both costs are None (LiteLLM doesn't know the
    models) the route is skipped to avoid a negative-savings
    misclassification.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="mystery-model",
                target="another-mystery-model",
                # no cost overrides
            )
        ],
    )
    r = ModelRouter(cfg)
    with patch.object(r, "_lookup_costs", return_value=(None, None)):
        decision = r.maybe_route("mystery-model")
    assert decision.routing_applied is False
    assert decision.reason == "cost_lookup_failed"


def test_cost_lookup_negative_delta_skips_route() -> None:
    """If the target is more expensive than the source (e.g.
    operator misconfigured), the route is skipped to avoid
    the router making the request more expensive.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="cheap-model",
                target="expensive-model",
                source_cost_per_mtok=1.0,
                target_cost_per_mtok=10.0,
            )
        ],
    )
    r = ModelRouter(cfg)
    decision = r.maybe_route("cheap-model")
    assert decision.routing_applied is False
    assert decision.reason == "cost_lookup_failed"


def test_low_complexity_router_fails_closed_without_messages() -> None:
    """Missing evidence should not silently downgrade a request."""
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="low_complexity",
        routes=[
            ModelRoute(
                source="mystery-model",
                target="another-mystery-model",
                source_cost_per_mtok=8.0,
                target_cost_per_mtok=1.0,
            )
        ],
    )
    r = ModelRouter(cfg)
    decision = r.maybe_route(
        "mystery-model",
        cache_read_tokens=0,
        attempted_input_tokens=0,
        tool_calls=0,
        num_messages=0,
    )
    assert decision.routing_applied is False
    assert decision.reason in {"workload_not_downgradeable", "no_route_for_model"}


def test_assessment_is_explainable_and_preserves_legacy_tier() -> None:
    messages = [{"role": "user", "content": "Fix the typo in this heading."}]

    assessment = assess_task_complexity(messages)

    assert assessment.complexity == TaskComplexity.LOW
    assert assessment.complexity == classify_task_complexity(messages)
    assert assessment.source == "heuristic"
    assert assessment.confidence == pytest.approx(0.9)


def test_router_abstains_when_assessment_confidence_is_below_policy_threshold() -> None:
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        minimum_confidence=0.8,
        routes=[
            ModelRoute(
                source="gpt-strong",
                target="gpt-mini",
                source_cost_per_mtok=10.0,
                target_cost_per_mtok=1.0,
            )
        ],
    )

    decision = ModelRouter(cfg).maybe_route(
        "gpt-strong",
        task_assessment=TaskComplexityAssessment(
            TaskComplexity.LOW,
            confidence=0.79,
            source="test-scorer",
        ),
    )

    assert decision.routing_applied is False
    assert decision.reason == "confidence_below_threshold"
    assert decision.confidence == pytest.approx(0.79)
    assert decision.scorer == "test-scorer"


def test_router_records_confidence_and_scorer_on_applied_downgrade() -> None:
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="gpt-strong",
                target="gpt-mini",
                source_cost_per_mtok=10.0,
                target_cost_per_mtok=1.0,
            )
        ],
    )

    decision = ModelRouter(cfg).maybe_route(
        "gpt-strong",
        task_assessment=TaskComplexityAssessment(
            TaskComplexity.LOW,
            confidence=0.92,
            source="test-scorer",
        ),
    )

    assert decision.routing_applied is True
    assert decision.confidence == pytest.approx(0.92)
    assert decision.scorer == "test-scorer"


def test_claude_three_tier_preset_requires_promoted_calibrated_scorer() -> None:
    cfg = ModelRouterConfig.claude_three_tier_eval_preset()
    router = ModelRouter(cfg)

    decision = router.maybe_route(
        "claude-opus-4-5",
        task_assessment=TaskComplexityAssessment(TaskComplexity.LOW, 1.0),
    )

    assert decision.routing_applied is False
    assert decision.reason == "calibrated_scorer_required"


def test_claude_three_tier_preset_routes_low_to_haiku_and_medium_to_sonnet() -> None:
    class CalibratedScorer:
        artifact = type(
            "Artifact",
            (),
            {"minimum_confidence": 0.5, "segment_thresholds": {}},
        )()

        def assess(self, _messages):  # type: ignore[no-untyped-def]
            return TaskComplexityAssessment(TaskComplexity.LOW, 0.95, "calibrated-test")

    router = ModelRouter(
        ModelRouterConfig.claude_three_tier_eval_preset(), scorer=CalibratedScorer()
    )

    low = router.maybe_route(
        "claude-opus-4-5",
        task_assessment=TaskComplexityAssessment(TaskComplexity.LOW, 0.95, "calibrated-test"),
    )
    medium = router.maybe_route(
        "claude-opus-4-5",
        task_assessment=TaskComplexityAssessment(TaskComplexity.MEDIUM, 0.95, "calibrated-test"),
    )

    assert low.target_model == "claude-haiku-4-5"
    assert medium.target_model == "claude-sonnet-4-5"
    assert low.routing_applied is True
    assert medium.routing_applied is True


def test_prepare_model_routing_uses_injected_scorer_and_exposes_its_decision() -> None:
    class StaticScorer:
        def assess(self, _messages):  # type: ignore[no-untyped-def]
            return TaskComplexityAssessment(
                TaskComplexity.LOW,
                confidence=0.88,
                source="calibrated-test",
            )

    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="low_complexity",
        minimum_confidence=0.8,
        routes=[
            ModelRoute(
                source="gpt-strong",
                target="gpt-mini",
                source_cost_per_mtok=10.0,
                target_cost_per_mtok=1.0,
            )
        ],
    )
    handler = type("Handler", (), {"_model_router": ModelRouter(cfg, scorer=StaticScorer())})()

    model, metadata = prepare_model_routing(
        handler,
        "gpt-strong",
        messages=[{"role": "user", "content": "a borderline request"}],
        request_savings_metadata={},
    )

    assert model == "gpt-mini"
    assert metadata is not None
    assert metadata["model_routing"]["confidence"] == pytest.approx(0.88)
    assert metadata["model_routing"]["scorer"] == "calibrated-test"


def test_prepare_model_routing_attaches_placeholder_metadata() -> None:
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="claude-opus-4-5",
                target="claude-sonnet-4-5",
                source_cost_per_mtok=15.0,
                target_cost_per_mtok=3.0,
            )
        ],
    )

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "claude-opus-4-5",
        request_savings_metadata={"semantic_cache": {"tokens": 12, "usd": 0.03}},
        num_messages=3,
    )

    assert model == "claude-sonnet-4-5"
    assert metadata is not None
    assert metadata["semantic_cache"]["tokens"] == 12
    assert metadata["model_routing"]["source_model"] == "claude-opus-4-5"
    assert metadata["model_routing"]["target_model"] == "claude-sonnet-4-5"


def test_prepare_model_routing_preserves_upstream_routing_savings_when_retained() -> None:
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="low_complexity",
        routes=[ModelRoute(source="gpt-strong", target="gpt-mini")],
    )
    handler = type("Handler", (), {"_model_router": ModelRouter(cfg)})()

    model, metadata = prepare_model_routing(
        handler,
        "gpt-strong",
        messages=[{"role": "user", "content": "build an entire orchestrator with AST parsing"}],
        request_savings_metadata={"model_routing": {"tokens": 25, "usd": 0.03}},
    )

    assert model == "gpt-strong"
    assert metadata is not None
    assert metadata["model_routing"]["tokens"] == 25
    assert metadata["model_routing"]["usd"] == 0.03
    assert metadata["model_routing"]["reason"] == "workload_not_downgradeable"


def test_prepare_model_routing_attaches_request_overrides_for_codex_slim() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    handler = DummyHandler()
    handler._model_router._lookup_costs = lambda src, tgt: (10.0, 1.0)

    model, metadata = prepare_model_routing(
        handler,
        "gpt-5.5",
        messages=[{"role": "user", "content": "fix typo in README"}],
        request_savings_metadata={},
    )

    assert model == "gpt-5.4-mini"
    assert metadata is not None
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"
    assert metadata["model_routing"]["request_overrides"] == {"reasoning": {"effort": "high"}}
    assert metadata["model_routing"]["tokens_saved"] == 0
    assert metadata["model_routing"]["usd_saved"] == 0.0


def test_codex_preset_routes_tiny_greeting_to_mini() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.5",
        messages=[{"role": "user", "content": "hi"}],
        request_savings_metadata={},
    )

    assert model == "gpt-5.4-mini"
    assert metadata is not None
    assert metadata["model_routing"]["source_model"] == "gpt-5.5"
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"


def test_preset_allows_verified_mini_target_on_subscription_transport() -> None:
    """The Codex preset may use targets explicitly verified for the transport."""
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-terra",
        messages=[{"role": "user", "content": "hi"}],
        request_savings_metadata={},
        implicit_downgrade_allowed=False,
    )

    assert model == "gpt-5.4-mini"
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"


def test_subscription_websocket_preserves_requested_model() -> None:
    """Stateful ChatGPT WS turns must not rely on preset target allowlists."""
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-sol",
        messages=[{"role": "user", "content": "hi"}],
        request_savings_metadata={},
        implicit_downgrade_allowed=False,
        allow_transport_safe_targets=False,
    )

    assert model == "gpt-5.6-sol"
    assert metadata["model_routing_trace"]["applied"] is False
    assert metadata["model_routing_trace"]["reason"] == (
        "downgrade_blocked_unproven_transport"
    )


def test_unverified_target_remains_blocked_on_subscription_transport() -> None:
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="gpt-5.6-terra",
                target="unknown-cheap-model",
                source_cost_per_mtok=10.0,
                target_cost_per_mtok=1.0,
            )
        ],
    )

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-terra",
        messages=[{"role": "user", "content": "hi"}],
        request_savings_metadata={},
        implicit_downgrade_allowed=False,
    )

    assert model == "gpt-5.6-terra"
    assert metadata["model_routing_trace"]["applied"] is False
    assert metadata["model_routing_trace"]["reason"] == "downgrade_blocked_unproven_transport"
    assert metadata["model_routing_trace"]["transport"]["target_proven"] is False


def test_codex_preset_routes_contextual_medium_work_to_luna() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    messages = [
        {"role": "user", "content": "Inspect the service."},
        {"role": "assistant", "content": "I found two relevant modules."},
        {"role": "user", "content": "Explain the first module."},
    ]
    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-sol",
        messages=messages,
        request_savings_metadata={},
        implicit_downgrade_allowed=False,
    )

    assert classify_task_complexity(messages) == TaskComplexity.MEDIUM
    assert model == "gpt-5.6-luna"
    assert metadata["model_routing"]["target_model"] == "gpt-5.6-luna"


def test_codex_preset_can_still_route_easy_followups_to_mini() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    messages = [
        {"role": "user", "content": "Summarize the dashboard changes."},
        {"role": "assistant", "content": "Sure."},
        {"role": "user", "content": "thanks"},
    ]
    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-terra",
        messages=messages,
        request_savings_metadata={},
    )

    assert classify_task_complexity(messages) == TaskComplexity.LOW
    assert model == "gpt-5.4-mini"
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"


def test_codex_preset_routes_short_plain_followups_to_mini() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    messages = [
        {"role": "user", "content": "Please review the dashboard route."},
        {"role": "assistant", "content": "Done."},
        {"role": "user", "content": "Which script restarts the proxy after a crash?"},
    ]
    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-terra",
        messages=messages,
        request_savings_metadata={},
        implicit_downgrade_allowed=False,
    )

    assert classify_task_complexity(messages) == TaskComplexity.LOW
    assert model == "gpt-5.4-mini"
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"


def test_stale_tool_context_does_not_permanently_block_mini_routing() -> None:
    messages = [
        {"role": "tool", "content": "old build output"},
        {"role": "assistant", "content": "old result"},
        {"role": "user", "content": "old question"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "another question"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "more"},
        {"role": "assistant", "content": "answer"},
        {"role": "user", "content": "What is idempotency?"},
    ]

    assessment = assess_task_complexity(messages)

    assert assessment.complexity == TaskComplexity.LOW
    assert assessment.signals == ("explicit_low_complexity",)


@pytest.mark.parametrize(
    "tool_item",
    [
        {"type": "function_call", "name": "shell", "arguments": "{}"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {"name": "shell", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "assistant",
            "content": [{"type": "function_call", "name": "shell", "arguments": "{}"}],
        },
        {"type": "local_shell_call_output", "call_id": "call-1", "output": "done"},
    ],
    ids=[
        "responses-function-call",
        "chat-tool-calls",
        "nested-function-call",
        "responses-local-shell-output",
    ],
)
def test_provider_native_tool_context_stays_on_requested_model(tool_item: dict) -> None:
    messages = [
        {"role": "user", "content": "Inspect the repository."},
        tool_item,
        {"role": "user", "content": "Show status."},
    ]

    assessment = assess_task_complexity(messages)

    assert assessment.complexity == TaskComplexity.HIGH
    assert assessment.signals == ("recent_tool_context",)


@pytest.mark.parametrize(
    "content",
    [
        "Write SQL to delete duplicate production records.",
        "Fix the race in this worker.",
        "Inspect the config, fix it, test it, and deploy.",
        "Review permissions and rotate the production secret.",
    ],
)
def test_short_but_risky_work_stays_on_requested_model(content: str) -> None:
    assessment = assess_task_complexity([{"role": "user", "content": content}])

    assert assessment.complexity == TaskComplexity.HIGH
    assert assessment.signals == ("strong_model_gate",)


def test_codex_preset_routes_moderately_long_plain_requests_to_mini() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    messages = [
        {"role": "user", "content": "Please review the dashboard route."},
        {"role": "assistant", "content": "Done."},
        {
            "role": "user",
            "content": (
                "Give me the exact command to restart the proxy and the exact "
                "command to confirm it came back healthy."
            ),
        },
    ]
    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-terra",
        messages=messages,
        request_savings_metadata={},
        implicit_downgrade_allowed=False,
    )

    assert classify_task_complexity(messages) == TaskComplexity.LOW
    assert model == "gpt-5.4-mini"
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"


def test_codex_preset_routes_reference_dependent_current_turn_to_luna() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    messages = [{"role": "user", "content": "Explain the first module."}]
    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.6-sol",
        messages=messages,
        request_savings_metadata={},
        implicit_downgrade_allowed=False,
    )

    assert classify_task_complexity(messages) == TaskComplexity.MEDIUM
    assert model == "gpt-5.6-luna"
    assert metadata["model_routing"]["target_model"] == "gpt-5.6-luna"


@pytest.mark.parametrize(
    "content",
    [
        "summarize this briefly",
        "what is episodic memory?",
        "give me the restart command",
        "where is the governance tab wired?",
    ],
)
def test_codex_preset_routes_short_informational_requests_to_mini(content: str) -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.5",
        messages=[{"role": "user", "content": content}],
        request_savings_metadata={},
    )

    assert classify_task_complexity([{"role": "user", "content": content}]) == TaskComplexity.LOW
    assert model == "gpt-5.4-mini"
    assert metadata is not None
    assert metadata["model_routing"]["source_model"] == "gpt-5.5"
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"


@pytest.mark.parametrize(
    "content",
    [
        "implement model routing in the proxy and test it end to end",
        "debug why websocket responses are not preserving routing metadata",
        "refactor the orchestrator architecture",
        "wire Claude routing for low complexity tasks",
    ],
)
def test_codex_preset_keeps_complex_work_on_requested_model(content: str) -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.5",
        messages=[{"role": "user", "content": content}],
        request_savings_metadata={},
    )

    assert classify_task_complexity([{"role": "user", "content": content}]) == TaskComplexity.HIGH
    assert model == "gpt-5.5"
    assert metadata["model_routing_trace"]["applied"] is False
    assert metadata["model_routing_trace"]["reason"] == "workload_not_downgradeable"


@pytest.mark.parametrize(
    "messages",
    [
        [{"role": "user", "content": "explain the orchestration architecture and compare options"}],
        [{"role": "user", "content": "fix this"}],
        [
            {"role": "user", "content": "find the issue"},
            {"role": "assistant", "content": "I found two candidates"},
            {"role": "user", "content": "fix the first one"},
        ],
        [{"role": "user", "content": "rename this variable:\n```python\nlegacy_name = 1\n```"}],
        [{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
    ],
)
def test_codex_preset_keeps_ambiguous_or_contextual_requests_on_requested_model(messages) -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "gpt-5.5",
        messages=messages,
        request_savings_metadata={},
    )

    assert classify_task_complexity(messages) != TaskComplexity.LOW
    assert model == "gpt-5.5"
    assert metadata["model_routing_trace"]["applied"] is False
    assert metadata["model_routing_trace"]["reason"] == "workload_not_downgradeable"


def test_codex_preset_routes_simple_claude_sonnet_to_haiku() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        request_savings_metadata={},
    )

    assert model == "claude-haiku-4-5"
    assert metadata is not None
    assert metadata["model_routing"]["source_model"] == "claude-sonnet-4-5"
    assert metadata["model_routing"]["target_model"] == "claude-haiku-4-5"


def test_codex_preset_routes_simple_claude_opus_to_sonnet() -> None:
    cfg = ModelRouterConfig.codex_gpt54mini_high_preset()

    class DummyHandler:
        def __init__(self) -> None:
            self._model_router = ModelRouter(cfg)

    model, metadata = prepare_model_routing(
        DummyHandler(),
        "claude-opus-4-5",
        messages=[{"role": "user", "content": "fix typo in README"}],
        request_savings_metadata={},
    )

    assert model == "claude-sonnet-4-5"
    assert metadata is not None
    assert metadata["model_routing"]["source_model"] == "claude-opus-4-5"
    assert metadata["model_routing"]["target_model"] == "claude-sonnet-4-5"


# ─- finalize_savings() ──────────────────────────────────────────


def test_finalize_savings_computes_token_and_usd() -> None:
    """finalize_savings applies the per-mtok delta to the
    actual input token count.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="claude-opus-4-5",
                target="claude-sonnet-4-5",
                source_cost_per_mtok=15.0,
                target_cost_per_mtok=3.0,
            )
        ],
    )
    r = ModelRouter(cfg)
    decision = r.maybe_route("claude-opus-4-5")
    assert decision.routing_applied is True
    finalized = r.finalize_savings(decision, input_tokens=100_000)
    # Delta is 12.0 USD per million tokens. 100,000 tokens =
    # 0.1 million, so usd_saved = 12.0 * 0.1 = 1.20.
    assert finalized.tokens_saved == 100_000
    assert finalized.usd_saved == pytest.approx(1.20)


def test_finalize_savings_passthrough_is_noop() -> None:
    """If the decision was a pass-through (no routing),
    finalize_savings returns it unchanged.
    """
    r = ModelRouter(ModelRouterConfig(enabled=False))
    decision = r.maybe_route("claude-opus-4-5")
    finalized = r.finalize_savings(decision, input_tokens=100_000)
    assert finalized.routing_applied is False
    assert finalized.tokens_saved == 0
    assert finalized.usd_saved == 0.0


# ─- Integration: litellm cost lookup ─────────────────────────────


def test_lookup_costs_uses_litellm_when_available() -> None:
    """The cost lookup reads LiteLLM's published rates when
    the route has no explicit cost override.
    """
    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(
                source="gpt-4o",
                target="gpt-4o-mini",
                # no cost overrides — must look up LiteLLM
            )
        ],
    )
    r = ModelRouter(cfg)
    with patch.dict(
        "sys.modules",
        {
            "litellm": __import__("types", fromlist=["ModuleType"]).ModuleType("litellm"),
        },
    ):
        import litellm

        litellm.model_cost = {
            "gpt-4o": {"input_cost_per_token": 2.5e-6},  # $2.50 / 1M
            "gpt-4o-mini": {"input_cost_per_token": 0.15e-6},  # $0.15 / 1M
        }
        src, tgt = r._lookup_costs("gpt-4o", "gpt-4o-mini")
    assert src == pytest.approx(2.5)
    assert tgt == pytest.approx(0.15)


def test_lookup_costs_returns_none_when_litellm_missing() -> None:
    """When litellm is not installed or the model is unknown,
    the lookup returns (None, None) so the route is skipped.
    """
    import sys

    cfg = ModelRouterConfig(
        enabled=True,
        downgrade_when="always",
        routes=[
            ModelRoute(source="gpt-4o", target="gpt-4o-mini"),
        ],
    )
    r = ModelRouter(cfg)
    # Force the import inside _lookup_costs to fail.
    with patch.dict(sys.modules, {"litellm": None}):
        src, tgt = r._lookup_costs("gpt-4o", "gpt-4o-mini")
    assert src is None
    assert tgt is None


def test_router_rejects_downgrade_when_target_capability_is_unproven() -> None:
    router = ModelRouter(ModelRouterConfig(enabled=True, downgrade_when="always", routes=[
        ModelRoute(source="strong", target="cheap", source_cost_per_mtok=10, target_cost_per_mtok=1)
    ]))
    decision = router.maybe_route("strong", required_capabilities={"tool_calling"})
    assert not decision.routing_applied
    assert decision.reason == "target_missing_capabilities"
    assert decision.signals == ("tool_calling",)


def test_router_routes_when_target_explicitly_proves_request_capability() -> None:
    router = ModelRouter(ModelRouterConfig(enabled=True, downgrade_when="always", routes=[
        ModelRoute(source="strong", target="cheap", source_cost_per_mtok=10, target_cost_per_mtok=1,
                   target_capabilities={"tool_calling"})
    ]))
    assert router.maybe_route("strong", required_capabilities={"tool_calling"}).target_model == "cheap"


def test_finalize_savings_includes_output_delta_when_known() -> None:
    router = ModelRouter(ModelRouterConfig(enabled=True, downgrade_when="always", routes=[
        ModelRoute(source="strong", target="cheap", source_cost_per_mtok=10, target_cost_per_mtok=1,
                   source_output_cost_per_mtok=20, target_output_cost_per_mtok=2)
    ]))
    decision = router.maybe_route("strong")
    assert router.finalize_savings(decision, input_tokens=100_000, output_tokens=50_000).usd_saved == pytest.approx(1.8)
