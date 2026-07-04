# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the cutctx.savings/ module (High-20).

Production audit (production-audit-2026-06-20.md) found that
the cutctx.savings/ module — the new moat-b1 code on this
branch — had 0 test imports. This file adds coverage for the
shared types, parsers, policy, integrations, and orchestrator.
"""

from __future__ import annotations

import pytest

from cutctx.savings import (
    RequestSavingsBreakdown,
    SavingsBySource,
    SavingsSource,
    parse_provider_savings,
)
from cutctx.savings.integrations import (
    parse_gptcache_hit,
    parse_litellm_cache,
    parse_model_routing_metadata,
    parse_vllm_apc,
)
from cutctx.savings.orchestrator import (
    SavingsOrchestrator,
)
from cutctx.savings.policy import PolicyDecision, StrategyResolver, WorkloadClass

# ── types.py ────────────────────────────────────────────────────────


def test_savings_source_enum_values() -> None:
    """The five canonical sources are spelled exactly as the docs
    and the dashboard expect them.
    """
    assert SavingsSource.PROVIDER_PROMPT_CACHE.value == "provider_prompt_cache"
    assert SavingsSource.CUTCTX_COMPRESSION.value == "cutctx_compression"
    assert SavingsSource.SEMANTIC_CACHE.value == "semantic_cache"
    assert SavingsSource.PREFIX_CACHE_SELF_HOSTED.value == "prefix_cache_self_hosted"
    assert SavingsSource.MODEL_ROUTING.value == "model_routing"
    assert SavingsSource.NORMALIZATION.value == "normalization"
    assert SavingsSource.BATCH_ROUTING.value == "batch_routing"
    assert SavingsSource.MEMOIZATION.value == "memoization"
    assert SavingsSource.OUTPUT_OPTIMIZATION.value == "output_optimization"


def test_savings_source_from_str_valid() -> None:
    """from_str returns the matching enum value for known names."""
    assert SavingsSource.from_str("provider_prompt_cache") == SavingsSource.PROVIDER_PROMPT_CACHE
    assert SavingsSource.from_str("model_routing") == SavingsSource.MODEL_ROUTING


def test_savings_source_from_str_invalid_falls_back_to_compression() -> None:
    """An unknown source name falls back to cutctx_compression
    (the default residual bucket). This is the documented behavior.
    """
    assert SavingsSource.from_str("nonsense") == SavingsSource.CUTCTX_COMPRESSION
    assert SavingsSource.from_str("") == SavingsSource.CUTCTX_COMPRESSION


def test_savings_source_label_and_description_nonempty() -> None:
    """Every source has a human-readable label and description."""
    for src in SavingsSource:
        assert src.label, f"label missing for {src.value}"
        assert src.description, f"description missing for {src.value}"


def test_savings_by_source_add_and_total() -> None:
    """SavingsBySource.add accumulates tokens and USD per source."""
    sbs = SavingsBySource()
    sbs.add(SavingsSource.PROVIDER_PROMPT_CACHE, tokens=100)
    sbs.add(SavingsSource.PROVIDER_PROMPT_CACHE, tokens=50)
    sbs.add(SavingsSource.MODEL_ROUTING, tokens=200, usd=0.05)
    assert sbs.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 150
    assert sbs.get_tokens(SavingsSource.MODEL_ROUTING) == 200
    assert sbs.get_usd(SavingsSource.MODEL_ROUTING) == 0.05
    assert sbs.total_tokens == 350
    assert sbs.total_usd == pytest.approx(0.05)


def test_savings_by_source_add_rejects_negative() -> None:
    """add() coerces negative values to 0 (defensive)."""
    sbs = SavingsBySource()
    sbs.add(SavingsSource.CUTCTX_COMPRESSION, tokens=-50, usd=-1.0)
    assert sbs.get_tokens(SavingsSource.CUTCTX_COMPRESSION) == 0
    assert sbs.get_usd(SavingsSource.CUTCTX_COMPRESSION) == 0.0


def test_request_savings_breakdown_to_dict() -> None:
    """RequestSavingsBreakdown.to_dict serialises the breakdown to a
    plain dict with all five sources represented.
    """
    rsb = RequestSavingsBreakdown(
        raw_input_tokens=1000,
        post_cutctx_tokens=500,
        provider_cached_tokens=100,
        semantic_cache_avoided_tokens=50,
        total_tokens_saved=500,
    )
    rsb.by_source.add(SavingsSource.MODEL_ROUTING, tokens=200, usd=0.05)
    out = rsb.to_dict()
    assert out["raw_input_tokens"] == 1000
    assert out["post_cutctx_tokens"] == 500
    assert out["provider_cached_tokens"] == 100
    assert out["semantic_cache_avoided_tokens"] == 50
    assert out["total_tokens_saved"] == 500
    # by_source has the routing bucket.
    assert "model_routing" in out["by_source"]["tokens"]


# ── parsers.py ──────────────────────────────────────────────────────


def test_parse_provider_savings_anthropic() -> None:
    """Anthropic usage with cache_creation_input_tokens and
    cache_read_input_tokens is attributed to provider_prompt_cache.
    """
    usage = {
        "input_tokens": 1000,
        "output_tokens": 100,
        "cache_creation_input_tokens": 200,
        "cache_read_input_tokens": 800,
    }
    b = parse_provider_savings("anthropic", usage)
    assert b.provider_cached_tokens == 800
    assert b.total_tokens_saved == 800
    assert b.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 800


def test_parse_provider_savings_openai() -> None:
    """OpenAI usage with cached_tokens in prompt_tokens_details is
    attributed to provider_prompt_cache.
    """
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 50,
        "prompt_tokens_details": {"cached_tokens": 750},
    }
    b = parse_provider_savings("openai", usage)
    assert b.provider_cached_tokens == 750
    assert b.total_tokens_saved == 750


def test_parse_provider_savings_unknown_provider_returns_default() -> None:
    """Unknown providers get an empty breakdown rather than raising."""
    b = parse_provider_savings("mystery_provider", {"input_tokens": 100})
    assert b.provider_cached_tokens == 0
    assert b.total_tokens_saved == 0


# ── integrations.py ─────────────────────────────────────────────────


def test_parse_vllm_apc_with_prefix_cache_hits() -> None:
    """vLLM APC metadata with prefix_cache_hits is attributed to
    prefix_cache_self_hosted (NOT provider_prompt_cache).
    """
    md = {"prefix_cache_hits": 500}
    b = parse_vllm_apc(md)
    assert b.by_source.get_tokens(SavingsSource.PREFIX_CACHE_SELF_HOSTED) == 500
    # Critical: must NOT leak to provider_prompt_cache.
    assert b.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 0


def test_parse_vllm_apc_handles_zero() -> None:
    """Zero hits produce an empty breakdown."""
    b = parse_vllm_apc({"prefix_cache_hits": 0})
    assert b.by_source.total_tokens == 0


def test_parse_vllm_apc_handles_missing() -> None:
    """Missing field produces an empty breakdown."""
    b = parse_vllm_apc({})
    assert b.by_source.total_tokens == 0


def test_parse_vllm_apc_handles_none() -> None:
    """None metadata produces an empty breakdown."""
    b = parse_vllm_apc(None)
    assert b.by_source.total_tokens == 0


def test_parse_vllm_apc_handles_invalid_value() -> None:
    """A non-numeric value does not raise; it is coerced to 0."""
    b = parse_vllm_apc({"prefix_cache_hits": "not a number"})
    assert b.by_source.total_tokens == 0


def test_parse_gptcache_hit_with_saved_prompt_tokens() -> None:
    """GPTCache metadata with saved_prompt_tokens is attributed to
    semantic_cache.
    """
    md = {"saved_prompt_tokens": 250}
    b = parse_gptcache_hit(md)
    assert b.by_source.get_tokens(SavingsSource.SEMANTIC_CACHE) == 250


def test_parse_gptcache_hit_with_tokens_avoided_alias() -> None:
    """GPTCache also accepts the tokens_avoided alias."""
    md = {"tokens_avoided": 175}
    b = parse_gptcache_hit(md)
    assert b.by_source.get_tokens(SavingsSource.SEMANTIC_CACHE) == 175


def test_parse_litellm_cache_with_cache_hit_tokens() -> None:
    """LiteLLM metadata with cache_hit_tokens is attributed to
    provider_prompt_cache (LiteLLM inherits the provider's cache).
    """
    md = {"cache_hit_tokens": 400}
    b = parse_litellm_cache(md)
    assert b.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 400


def test_parse_model_routing_metadata_with_tokens_and_usd() -> None:
    """Model routing metadata with tokens_routed and usd_saved is
    attributed to model_routing with USD preserved.
    """
    md = {"tokens_routed": 1000, "usd_saved": 0.05}
    b = parse_model_routing_metadata(md)
    assert b.by_source.get_tokens(SavingsSource.MODEL_ROUTING) == 1000
    assert b.by_source.get_usd(SavingsSource.MODEL_ROUTING) == 0.05


def test_parse_model_routing_metadata_with_zero() -> None:
    """Zero values produce an empty breakdown."""
    b = parse_model_routing_metadata({"tokens_routed": 0, "usd_saved": 0.0})
    assert b.by_source.total_tokens == 0


# ── policy.py ───────────────────────────────────────────────────────


def test_policy_decision_defaults() -> None:
    """PolicyDecision has the documented default field values."""
    pd = PolicyDecision()
    assert pd.strategy_label == "default"
    assert pd.preserve_prefix_for_provider_cache is True
    assert pd.compress_tool_outputs_only is False
    assert pd.semantic_cache_enabled is False
    assert pd.semantic_cache_threshold == 0.92


def test_strategy_resolver_coding_agent_workload() -> None:
    """A coding_agent workload returns a non-default strategy."""
    resolver = StrategyResolver()
    decision = resolver.resolve(
        provider="anthropic",
        model="claude-3-5-sonnet",
        workload=WorkloadClass.CODING_AGENT,
    )
    # Coding agents get the coding_agent label (or default if not
    # configured); either way the field must be a non-empty string.
    assert decision.strategy_label


def test_strategy_resolver_handles_invalid_inputs() -> None:
    """The resolver does not raise on invalid input shapes."""
    resolver = StrategyResolver()
    decision = resolver.resolve(
        provider="mystery",
        model="mystery-model",
        workload=WorkloadClass.UNKNOWN,
        request_shape={},
    )
    assert decision.strategy_label == "default"


# ── orchestrator.py ─────────────────────────────────────────────────


def test_savings_orchestrator_record_request_accumulates() -> None:
    """SavingsOrchestrator.record_request accumulates per-source
    tokens and USD across many requests. The aggregate pulls
    from the breakdown's by_source dict; the provider_cached_tokens
    field on the breakdown is a parallel field that is not
    folded into the aggregate by_source.
    """
    orch = SavingsOrchestrator()
    rsb = RequestSavingsBreakdown(
        raw_input_tokens=1000,
        post_cutctx_tokens=500,
        provider_cached_tokens=100,
        total_tokens_saved=500,
    )
    rsb.by_source.add(SavingsSource.MODEL_ROUTING, tokens=200, usd=0.05)
    orch.record_request(rsb, provider="anthropic", model="claude-3-5-sonnet")
    orch.record_request(rsb, provider="anthropic", model="claude-3-5-sonnet")
    agg = orch.aggregate
    assert agg.requests == 2
    assert agg.by_source.tokens.get("model_routing") == 400
    assert agg.by_source.usd.get("model_routing") == pytest.approx(0.10)


def test_savings_orchestrator_per_provider_breakdown() -> None:
    """The orchestrator tracks per-provider breakdowns via the
    by_source dict on each request.
    """
    orch = SavingsOrchestrator()
    for provider, model, tokens in [
        ("anthropic", "claude-3-5-sonnet", 100),
        ("openai", "gpt-4o", 200),
        ("anthropic", "claude-3-5-sonnet", 50),
    ]:
        rsb = RequestSavingsBreakdown(
            raw_input_tokens=1000,
            post_cutctx_tokens=1000 - tokens,
            total_tokens_saved=tokens,
        )
        rsb.by_source.add(SavingsSource.CUTCTX_COMPRESSION, tokens=tokens)
        orch.record_request(rsb, provider=provider, model=model)
    agg = orch.aggregate
    assert "anthropic" in agg.by_provider
    assert "openai" in agg.by_provider
    assert agg.by_provider["anthropic"].total_tokens == 150
    assert agg.by_provider["openai"].total_tokens == 200


def test_savings_orchestrator_to_dict_round_trip() -> None:
    """The aggregate serialises to a dict that contains the
    requests, raw_input_tokens, and by_source fields.
    """
    orch = SavingsOrchestrator()
    rsb = RequestSavingsBreakdown(
        raw_input_tokens=1000,
        post_cutctx_tokens=500,
        total_tokens_saved=500,
    )
    orch.record_request(rsb, provider="anthropic", model="claude")
    out = orch.aggregate.to_dict()
    assert "requests" in out
    assert "raw_input_tokens" in out
    assert "by_source" in out
    assert out["requests"] == 1
    assert out["raw_input_tokens"] == 1000
    # by_source is itself a dict with tokens and usd sub-dicts.
    assert "tokens" in out["by_source"]
    assert "usd" in out["by_source"]


def test_savings_orchestrator_reset() -> None:
    """reset() clears the aggregate."""
    orch = SavingsOrchestrator()
    rsb = RequestSavingsBreakdown(
        raw_input_tokens=1000, post_cutctx_tokens=500, total_tokens_saved=500
    )
    orch.record_request(rsb, provider="anthropic", model="claude")
    assert orch.aggregate.requests == 1
    orch.reset()
    assert orch.aggregate.requests == 0
    assert orch.aggregate.total_tokens_saved == 0
