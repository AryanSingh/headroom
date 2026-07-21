"""End-to-end guarantees for the user-facing routing modes.

The dashboard exposes three modes (off / balanced / aggressive). These map to
presets that must:
  * OFF        — never downgrade.
  * BALANCED   — downgrade *simple* requests to a cheaper model, keep complex
                 work on the requested model.
  * AGGRESSIVE — downgrade simple requests, and still protect genuinely
                 high-complexity work (intelligent, not blind, cost cutting).

This exercises the real request-entry path used by the Anthropic handler
(``prepare_model_routing``) with a minimal fake handler.
"""

from __future__ import annotations

import pytest

from cutctx.orchestration.registry import DynamicModelRegistry
from cutctx.proxy.model_router import (
    ModelRouter,
    ModelRouterConfig,
    TaskComplexity,
    classify_task_complexity,
    model_routing_preset_for_mode,
    normalize_model_routing_mode,
    prepare_model_routing,
)

SIMPLE = [{"role": "user", "content": "hi, what's 2+2?"}]
COMPLEX = [
    {
        "role": "user",
        "content": "Implement model routing in the proxy and test it end to end.",
    }
]


class _FakeHandler:
    def __init__(self, router):
        self._model_router = router
        self._orchestration_service = None
        self._orchestration_account_id = None

    def _anthropic_messages_to_routing_messages(self, messages):
        return messages


def _router_for(mode: str):
    preset = model_routing_preset_for_mode(normalize_model_routing_mode(mode))
    if preset is None:
        return None
    # The runtime proxy binds the orchestration model registry immediately
    # after constructing its router. Keep this end-to-end harness faithful to
    # that path so catalog-certified current models are tested rather than the
    # stale explicit-route compatibility fallback.
    return ModelRouter(
        config=ModelRouterConfig.from_preset_name(preset),
        registry=DynamicModelRegistry(),
    )


def _route(mode: str, model: str, messages):
    router = _router_for(mode)
    handler = _FakeHandler(router)
    routed, meta = prepare_model_routing(
        handler,
        model,
        request_savings_metadata={},
        cache_read_tokens=0,
        attempted_input_tokens=0,
        tool_calls=0,
        num_messages=len(messages),
        messages=messages,
        transport_provider="anthropic",
    )
    reason = (meta or {}).get("model_routing", {}).get("reason")
    return routed, reason


def test_off_never_downgrades():
    assert _router_for("off") is None


@pytest.mark.parametrize("mode", ["balanced", "aggressive"])
def test_simple_request_downgrades_to_cheaper_model(mode):
    routed, reason = _route(mode, "claude-opus-4-5", SIMPLE)
    assert routed != "claude-opus-4-5", f"{mode}: simple opus request was not downgraded"
    assert routed == "claude-haiku-4-5"
    assert reason == "catalog_candidate_selected"


@pytest.mark.parametrize("mode", ["balanced", "aggressive"])
def test_sonnet_simple_request_downgrades_to_haiku(mode):
    routed, _ = _route(mode, "claude-sonnet-4-5", SIMPLE)
    assert routed == "claude-haiku-4-5"


@pytest.mark.parametrize("mode", ["balanced", "aggressive"])
def test_complex_request_stays_on_requested_model(mode):
    """Intelligent routing must NOT send hard tasks to a weaker model,
    even in aggressive mode."""
    assert classify_task_complexity(COMPLEX) == TaskComplexity.HIGH
    routed, reason = _route(mode, "claude-opus-4-5", COMPLEX)
    assert routed == "claude-opus-4-5", f"{mode}: complex request wrongly downgraded to {routed}"
    assert reason == "workload_not_downgradeable"


def test_default_config_is_disabled_and_inert():
    """A bare ModelRouterConfig() must not silently route (it is disabled),
    so no downgrade happens unless a preset/mode is explicitly selected."""
    cfg = ModelRouterConfig()
    assert cfg.enabled is False
    router = ModelRouter(config=cfg)
    handler = _FakeHandler(router)
    routed, _ = prepare_model_routing(
        handler,
        "claude-opus-4-5",
        request_savings_metadata={},
        messages=SIMPLE,
        num_messages=len(SIMPLE),
        transport_provider="anthropic",
    )
    assert routed == "claude-opus-4-5"
