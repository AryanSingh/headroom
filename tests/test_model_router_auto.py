"""Cursor-style Auto model routing — synthetic ``model=auto`` selection."""

from __future__ import annotations

from cutctx.orchestration.models import ModelRecord
from cutctx.orchestration.registry import DynamicModelRegistry
from cutctx.proxy.model_router import (
    ModelRouter,
    ModelRouterConfig,
    TaskComplexity,
    is_auto_model,
    normalize_model_routing_mode,
    prepare_model_routing,
)


def _certified(provider: str, model_id: str, cost: float, tier: str) -> ModelRecord:
    return ModelRecord(
        provider=provider,
        id=model_id,
        display_name=model_id,
        capabilities={"tool_calling", "streaming", "reasoning"},
        input_cost_per_million=cost,
        available=True,
        metadata={
            "routing_certified": True,
            "routing_readiness": "ready",
            "quality_tier": tier,
            "catalog_source": "test",
        },
    )


def _openai_registry() -> DynamicModelRegistry:
    registry = DynamicModelRegistry()
    for record in (
        _certified("openai", "gpt-5.5", 10.0, "strong"),
        _certified("openai", "gpt-5.6-luna", 5.0, "medium"),
        _certified("openai", "gpt-5.4-mini", 1.0, "fast"),
    ):
        registry.register(record)
    return registry


def test_is_auto_model_aliases() -> None:
    assert is_auto_model("auto")
    assert is_auto_model("AUTO")
    assert is_auto_model("cutctx-auto")
    assert is_auto_model("cursor-auto")
    assert not is_auto_model("gpt-5.5")
    assert not is_auto_model(None)


def test_normalize_mode_maps_auto_and_balanced_to_auto() -> None:
    assert normalize_model_routing_mode("auto") == "auto"
    assert normalize_model_routing_mode("balanced") == "auto"
    assert normalize_model_routing_mode("codex-gpt54mini-high") == "auto"
    assert normalize_model_routing_mode("off") == "off"
    assert normalize_model_routing_mode("aggressive") == "aggressive"


def test_auto_preset_name_loads_balanced_config() -> None:
    config = ModelRouterConfig.from_preset_name("auto")
    assert config is not None
    assert config.enabled is True
    assert config.downgrade_when == "low_complexity"


def test_auto_routes_low_complexity_to_fast_catalog_model() -> None:
    router = ModelRouter(
        config=ModelRouterConfig.codex_gpt54mini_high_preset(),
        registry=_openai_registry(),
    )
    decision = router.maybe_route(
        "auto",
        task_complexity=TaskComplexity.LOW,
        transport_provider="openai",
    )

    assert decision.routing_applied is True
    assert decision.target_model == "gpt-5.4-mini"
    assert decision.reason == "auto_catalog_selected"
    assert decision.request_overrides == {"reasoning": {"effort": "high"}}


def test_auto_routes_medium_complexity_to_medium_catalog_model() -> None:
    router = ModelRouter(
        config=ModelRouterConfig.codex_gpt54mini_high_preset(),
        registry=_openai_registry(),
    )
    decision = router.maybe_route(
        "auto",
        task_complexity=TaskComplexity.MEDIUM,
        transport_provider="openai",
    )

    assert decision.target_model in {"gpt-5.6-luna", "gpt-5.4", "gpt-5"}
    assert decision.reason == "auto_catalog_selected"


def test_auto_routes_high_complexity_to_strong_catalog_model() -> None:
    router = ModelRouter(
        config=ModelRouterConfig.codex_gpt54mini_high_preset(),
        registry=_openai_registry(),
    )
    decision = router.maybe_route(
        "auto",
        task_complexity=TaskComplexity.HIGH,
        transport_provider="openai",
    )

    assert decision.target_model in {
        "gpt-5.5",
        "gpt-5.6-terra",
        "gpt-5.6-sol",
    }
    assert decision.reason == "auto_catalog_selected"


def test_auto_static_fallback_when_catalog_empty() -> None:
    router = ModelRouter(config=ModelRouterConfig.codex_gpt54mini_high_preset())
    decision = router.maybe_route(
        "cutctx-auto",
        task_complexity=TaskComplexity.LOW,
        transport_provider="anthropic",
    )

    assert decision.routing_applied is True
    assert decision.target_model == "claude-haiku-4-5"
    assert decision.reason == "auto_static_selected"


def test_auto_works_even_when_router_config_disabled() -> None:
    router = ModelRouter(config=ModelRouterConfig(enabled=False))
    decision = router.maybe_route(
        "auto",
        task_complexity=TaskComplexity.HIGH,
        transport_provider="openai",
    )

    assert decision.routing_applied is True
    assert decision.target_model == "gpt-5.5"
    assert decision.reason == "auto_static_selected"


def test_prepare_model_routing_resolves_auto_when_handler_router_off() -> None:
    class _Handler:
        _model_router = ModelRouter(config=ModelRouterConfig(enabled=False))
        _model_registry = None
        _orchestration_account_id = None

    effective, metadata = prepare_model_routing(
        _Handler(),
        "auto",
        messages=[{"role": "user", "content": "hi"}],
        transport_provider="openai",
    )

    assert effective == "gpt-5.4-mini"
    assert metadata is not None
    assert metadata["model_routing"]["target_model"] == "gpt-5.4-mini"
    assert metadata["model_routing"]["source_model"] == "auto"
