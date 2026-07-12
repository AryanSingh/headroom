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

from cutctx.proxy.model_router import (
    ModelRoute,
    ModelRouter,
    ModelRouterConfig,
    TaskComplexity,
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
    assert metadata["model_routing"]["request_overrides"]["reasoning"] == {
        "effort": "high"
    }


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
    assert metadata["model_routing"]["request_overrides"] == {
        "reasoning": {"effort": "high"}
    }
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
    assert metadata == {}


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
    assert metadata == {}


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
    assert metadata == {}


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
