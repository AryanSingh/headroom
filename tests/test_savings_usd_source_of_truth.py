"""Lifetime typed USD counters must equal the canonical by-source USD.

Guards the attribution divergence where ``lifetime.model_routing_savings_usd``
re-estimated routing savings at the routed-to model's flat input rate while
``lifetime["savings_by_source_usd.model_routing"]`` (and the headline
``created_savings_usd``) carried the router's true (source − target) price
delta — a 4.1x disagreement visible to any procurement reviewer.
"""

from __future__ import annotations

import pytest

from cutctx.proxy.savings_tracker import SavingsTracker


def _record_routed_request(tracker: SavingsTracker, *, routing_usd: float | None) -> None:
    kwargs: dict = {}
    by_source_usd = {"cutctx_compression": 1.25}
    if routing_usd is not None:
        by_source_usd["model_routing"] = routing_usd
        kwargs["model_routing_usd_delta"] = routing_usd
    tracker.record_request(
        model="gpt-5.4-mini",
        input_tokens=10_000,
        tokens_saved=300,
        cache_read_tokens=12_000,
        savings_by_source_tokens={
            "cutctx_compression": 300,
            "provider_prompt_cache": 12_000,
            "model_routing": 200_000,
        },
        savings_by_source_usd=by_source_usd,
        compression_savings_usd_delta=1.25,
        **kwargs,
    )


def test_lifetime_routing_usd_uses_router_delta_not_flat_reestimate(tmp_path) -> None:
    tracker = SavingsTracker(path=str(tmp_path / "savings.json"))

    # The router's true delta for these 200k tokens. A flat re-estimate at
    # the routed-to model's input rate would produce a different number.
    _record_routed_request(tracker, routing_usd=0.75)

    lifetime = tracker.stats_preview()["lifetime"]
    assert lifetime["model_routing_savings_usd"] == pytest.approx(0.75)
    assert lifetime["savings_by_source_usd.model_routing"] == pytest.approx(0.75)


def test_lifetime_typed_counters_converge_with_by_source_usd(tmp_path) -> None:
    tracker = SavingsTracker(path=str(tmp_path / "savings.json"))

    tracker.record_request(
        model="gpt-5.4-mini",
        input_tokens=10_000,
        tokens_saved=500,
        cache_read_tokens=40_000,
        savings_by_source_tokens={
            "provider_prompt_cache": 40_000,
            "semantic_cache": 9_000,
            "tool_schema_compaction": 4_000,
            "api_surface_slimming": 2_000,
        },
        savings_by_source_usd={
            "provider_prompt_cache": 0.11,
            "semantic_cache": 0.22,
            "tool_schema_compaction": 0.33,
            "api_surface_slimming": 0.44,
        },
        cache_savings_usd_delta=0.11,
        semantic_cache_usd_delta=0.22,
        tool_schema_compaction_usd_delta=0.33,
        api_surface_slimming_usd_delta=0.44,
    )

    lifetime = tracker.stats_preview()["lifetime"]
    for typed_key, source_key, expected in [
        ("cache_savings_usd", "provider_prompt_cache", 0.11),
        ("semantic_cache_savings_usd", "semantic_cache", 0.22),
        ("tool_schema_compaction_savings_usd", "tool_schema_compaction", 0.33),
        ("api_surface_slimming_savings_usd", "api_surface_slimming", 0.44),
    ]:
        assert lifetime[typed_key] == pytest.approx(expected), typed_key
        assert lifetime[f"savings_by_source_usd.{source_key}"] == pytest.approx(
            expected
        ), source_key


def test_lifetime_routing_usd_falls_back_to_estimate_without_by_source(tmp_path) -> None:
    tracker = SavingsTracker(path=str(tmp_path / "savings.json"))

    # Legacy caller shape: routed tokens known, no USD provided anywhere.
    _record_routed_request(tracker, routing_usd=None)

    lifetime = tracker.stats_preview()["lifetime"]
    # The flat estimate is a legacy fallback; it must still produce a
    # non-negative value and never crash.
    assert lifetime["model_routing_savings_usd"] >= 0.0
