"""Tests for the savings orchestration package.

Covers:
- Phase 1.1: SavingsSource enum + SavingsBySource + RequestSavingsBreakdown
- Phase 1.2: Request-level breakdown round-trip
- Phase 1.3: Aggregate breakdown consistency
- Phase 2.1-2.4: Provider parsers (OpenAI, Anthropic, Gemini, Bedrock, Azure)
- Phase 3.1-3.2: Strategy resolver + workload classes
- Phase 4.1-4.4: External integrations (LiteLLM, vLLM, GPTCache, model routing)
- Cross-cutting: zero-state, no-double-count, backward compatibility
"""

from __future__ import annotations

import pytest

from cutctx.savings import (
    AggregateSavings,
    RequestSavingsBreakdown,
    SavingsBySource,
    SavingsOrchestrator,
    SavingsSource,
    StrategyResolver,
    WorkloadClass,
    parse_anthropic_savings,
    parse_azure_openai_savings,
    parse_bedrock_savings,
    parse_gemini_savings,
    parse_gptcache_hit,
    parse_litellm_cache,
    parse_model_routing_metadata,
    parse_openai_savings,
    parse_provider_savings,
    parse_vllm_apc,
)

# ---------------------------------------------------------------------------
# Phase 1.1: SavingsSource + SavingsBySource
# ---------------------------------------------------------------------------


class TestSavingsSource:
    def test_all_five_sources_present(self):
        assert len(SavingsSource) == 7
        assert SavingsSource.PROVIDER_PROMPT_CACHE.value == "provider_prompt_cache"
        assert SavingsSource.CUTCTX_COMPRESSION.value == "cutctx_compression"
        assert SavingsSource.SEMANTIC_CACHE.value == "semantic_cache"
        assert SavingsSource.PREFIX_CACHE_SELF_HOSTED.value == "prefix_cache_self_hosted"
        assert SavingsSource.MODEL_ROUTING.value == "model_routing"

    def test_from_str_known(self):
        assert SavingsSource.from_str("provider_prompt_cache") == SavingsSource.PROVIDER_PROMPT_CACHE

    def test_from_str_unknown_defaults_to_compression(self):
        assert SavingsSource.from_str("not-a-source") == SavingsSource.CUTCTX_COMPRESSION

    def test_label_and_description_non_empty(self):
        for src in SavingsSource:
            assert src.label
            assert src.description


class TestSavingsBySource:
    def test_add_and_totals(self):
        b = SavingsBySource()
        b.add(SavingsSource.PROVIDER_PROMPT_CACHE, tokens=100, usd=0.50)
        b.add(SavingsSource.CUTCTX_COMPRESSION, tokens=200, usd=1.00)
        assert b.total_tokens == 300
        assert b.total_usd == pytest.approx(1.50)

    def test_add_clamps_negative(self):
        b = SavingsBySource()
        b.add(SavingsSource.CUTCTX_COMPRESSION, tokens=-50, usd=-1.0)
        assert b.total_tokens == 0
        assert b.total_usd == 0.0

    def test_round_trip_dict(self):
        b = SavingsBySource()
        b.add(SavingsSource.CUTCTX_COMPRESSION, tokens=42, usd=0.21)
        d = b.to_dict()
        assert d["total_tokens"] == 42
        assert d["total_usd"] == pytest.approx(0.21)
        b2 = SavingsBySource.from_dict(d)
        assert b2.total_tokens == 42
        assert b2.total_usd == pytest.approx(0.21)

    def test_from_dict_handles_garbage(self):
        assert SavingsBySource.from_dict(None).total_tokens == 0
        assert SavingsBySource.from_dict({}).total_tokens == 0
        assert SavingsBySource.from_dict({"tokens": "not-a-dict"}).total_tokens == 0


# ---------------------------------------------------------------------------
# Phase 1.2: RequestSavingsBreakdown
# ---------------------------------------------------------------------------


class TestRequestSavingsBreakdown:
    def test_defaults_zero(self):
        b = RequestSavingsBreakdown()
        assert b.raw_input_tokens == 0
        assert b.post_cutctx_tokens == 0
        assert b.provider_cached_tokens == 0
        assert b.semantic_cache_avoided_tokens == 0
        assert b.total_tokens_saved == 0
        assert b.has_any_savings is False

    def test_round_trip_dict(self):
        b = RequestSavingsBreakdown(
            raw_input_tokens=1000,
            post_cutctx_tokens=400,
            provider_cached_tokens=300,
            semantic_cache_avoided_tokens=200,
            total_tokens_saved=500,
        )
        b.by_source.add(SavingsSource.CUTCTX_COMPRESSION, 200)
        b.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 300)
        d = b.to_dict()
        assert d["raw_input_tokens"] == 1000
        b2 = RequestSavingsBreakdown.from_dict(d)
        assert b2.raw_input_tokens == 1000
        assert b2.post_cutctx_tokens == 400
        assert b2.provider_cached_tokens == 300
        assert b2.by_source.get_tokens(SavingsSource.CUTCTX_COMPRESSION) == 200

    def test_from_dict_handles_legacy_payload(self):
        """Older records (no breakdown fields) must not crash consumers."""
        b = RequestSavingsBreakdown.from_dict({})
        assert b.has_any_savings is False
        b2 = RequestSavingsBreakdown.from_dict(None)
        assert b2.has_any_savings is False
        b3 = RequestSavingsBreakdown.from_dict({"raw_input_tokens": 100})
        assert b3.raw_input_tokens == 100
        assert b3.by_source.total_tokens == 0

    def test_merge_two_breakdowns(self):
        a = RequestSavingsBreakdown(
            raw_input_tokens=1000, total_tokens_saved=200, provider_cached_tokens=200
        )
        a.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 200)
        b = RequestSavingsBreakdown(
            raw_input_tokens=2000, total_tokens_saved=300, provider_cached_tokens=300
        )
        b.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 300)
        a.merge(b)
        assert a.raw_input_tokens == 3000
        assert a.total_tokens_saved == 500
        assert a.provider_cached_tokens == 500
        assert a.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 500


# ---------------------------------------------------------------------------
# Phase 2.1: OpenAI parser
# ---------------------------------------------------------------------------


class TestOpenAIParser:
    def test_chat_completions_cached(self):
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 750},
        }
        b = parse_openai_savings(usage)
        assert b.provider_cached_tokens == 750
        assert b.total_tokens_saved == 750
        assert b.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 750

    def test_responses_api_input_details(self):
        usage = {
            "input_tokens": 500,
            "output_tokens": 50,
            "input_tokens_details": {"cached_tokens": 400},
        }
        b = parse_openai_savings(usage)
        assert b.provider_cached_tokens == 400

    def test_no_cache_present(self):
        usage = {"prompt_tokens": 1000, "completion_tokens": 100}
        b = parse_openai_savings(usage)
        assert b.provider_cached_tokens == 0
        assert b.has_any_savings is False

    def test_garbage_input(self):
        assert parse_openai_savings(None).has_any_savings is False
        assert parse_openai_savings("string").has_any_savings is False
        assert parse_openai_savings({"prompt_tokens_details": "not-a-dict"}).has_any_savings is False
        assert parse_openai_savings({"prompt_tokens_details": {"cached_tokens": "abc"}}).has_any_savings is False


# ---------------------------------------------------------------------------
# Phase 2.2: Anthropic parser
# ---------------------------------------------------------------------------


class TestAnthropicParser:
    def test_cache_read(self):
        usage = {
            "input_tokens": 1000,
            "output_tokens": 100,
            "cache_creation_input_tokens": 100,
            "cache_read_input_tokens": 900,
        }
        b = parse_anthropic_savings(usage)
        assert b.provider_cached_tokens == 900
        assert b.total_tokens_saved == 900

    def test_no_cache(self):
        usage = {"input_tokens": 500, "output_tokens": 100}
        b = parse_anthropic_savings(usage)
        assert b.provider_cached_tokens == 0

    def test_only_creation_no_read(self):
        usage = {"cache_creation_input_tokens": 100, "cache_read_input_tokens": 0}
        b = parse_anthropic_savings(usage)
        assert b.provider_cached_tokens == 0
        # Write-only is observability, not savings

    def test_garbage(self):
        assert parse_anthropic_savings(None).has_any_savings is False
        assert parse_anthropic_savings({"cache_read_input_tokens": "x"}).has_any_savings is False


# ---------------------------------------------------------------------------
# Phase 2.3: Gemini parser
# ---------------------------------------------------------------------------


class TestGeminiParser:
    def test_cached_content(self):
        usage_metadata = {
            "promptTokenCount": 1000,
            "candidatesTokenCount": 50,
            "cachedContentTokenCount": 800,
        }
        b = parse_gemini_savings(usage_metadata)
        assert b.provider_cached_tokens == 800

    def test_no_cache(self):
        b = parse_gemini_savings({"promptTokenCount": 100})
        assert b.provider_cached_tokens == 0


# ---------------------------------------------------------------------------
# Phase 2.4: Bedrock + Azure
# ---------------------------------------------------------------------------


class TestBedrockParser:
    def test_cache_read(self):
        usage = {"inputTokens": 100, "cacheReadInputTokens": 80}
        b = parse_bedrock_savings(usage)
        assert b.provider_cached_tokens == 80

    def test_no_cache(self):
        b = parse_bedrock_savings({"inputTokens": 100})
        assert b.provider_cached_tokens == 0


class TestAzureOpenAIParser:
    def test_delegates_to_openai(self):
        usage = {"prompt_tokens_details": {"cached_tokens": 200}}
        b = parse_azure_openai_savings(usage)
        assert b.provider_cached_tokens == 200


class TestProviderDispatch:
    def test_dispatch_anthropic(self):
        b = parse_provider_savings("anthropic", {"cache_read_input_tokens": 100})
        assert b.provider_cached_tokens == 100

    def test_dispatch_unknown(self):
        assert parse_provider_savings("unknown", {"x": 1}).has_any_savings is False

    def test_dispatch_none_usage(self):
        assert parse_provider_savings("openai", None).has_any_savings is False


# ---------------------------------------------------------------------------
# Phase 3.1 + 3.2: Strategy resolver + workload classes
# ---------------------------------------------------------------------------


class TestStrategyResolver:
    def test_default_workload_is_unknown(self):
        r = StrategyResolver()
        d = r.resolve(provider="anthropic", model="claude-3-haiku-20240307")
        assert d.strategy_label == "default"
        assert d.preserve_prefix_for_provider_cache is True
        assert d.semantic_cache_enabled is False

    def test_coding_agent_workload(self):
        r = StrategyResolver()
        d = r.resolve(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            workload=WorkloadClass.CODING_AGENT,
        )
        assert d.strategy_label == "coding_agent"
        assert d.compress_tool_outputs_only is True
        assert d.preserve_prefix_for_provider_cache is True
        assert d.semantic_cache_enabled is True
        assert d.semantic_cache_threshold < 0.92

    def test_long_doc_qa_disables_prefix_preservation(self):
        r = StrategyResolver()
        d = r.resolve(
            provider="custom", workload=WorkloadClass.LONG_DOC_QA
        )
        assert d.preserve_prefix_for_provider_cache is False

    def test_workload_from_string(self):
        r = StrategyResolver()
        d = r.resolve(provider="openai", workload="support_search")
        assert d.strategy_label == "support_search"

    def test_deterministic(self):
        r = StrategyResolver()
        a = r.resolve(provider="openai", workload="coding_agent")
        b = r.resolve(provider="openai", workload="coding_agent")
        assert a.to_dict() == b.to_dict()

    def test_user_overrides_win(self):
        r = StrategyResolver(user_overrides={"semantic_cache_enabled": False})
        d = r.resolve(provider="openai", workload="coding_agent")
        assert d.semantic_cache_enabled is False

    def test_request_shape_tool_results_turns_on_compress(self):
        r = StrategyResolver()
        d = r.resolve(
            provider="openai",
            workload="unknown",
            request_shape={"tool_result_count": 3},
        )
        assert d.compress_tool_outputs_only is True

    def test_can_be_disabled_cleanly(self):
        # Resolver with overrides={strategy_label: "off"} simulates disable.
        r = StrategyResolver(user_overrides={"strategy_label": "off"})
        d = r.resolve(provider="openai", workload="coding_agent")
        assert d.strategy_label == "off"


# ---------------------------------------------------------------------------
# Phase 4: External integrations
# ---------------------------------------------------------------------------


class TestLiteLLM:
    def test_cache_hit(self):
        b = parse_litellm_cache({"cache_hit_tokens": 500})
        assert b.provider_cached_tokens == 500

    def test_no_hit(self):
        assert parse_litellm_cache({}).has_any_savings is False

    def test_garbage(self):
        assert parse_litellm_cache(None).has_any_savings is False


class TestVLLMAPC:
    def test_prefix_cache_hits(self):
        b = parse_vllm_apc({"prefix_cache_hits": 300})
        # Self-hosted, NOT provider cache
        assert b.provider_cached_tokens == 300
        assert b.by_source.get_tokens(SavingsSource.PREFIX_CACHE_SELF_HOSTED) == 300
        assert b.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 0

    def test_no_hits(self):
        assert parse_vllm_apc({}).has_any_savings is False


class TestGPTCache:
    def test_hit(self):
        b = parse_gptcache_hit({"saved_prompt_tokens": 250})
        assert b.semantic_cache_avoided_tokens == 250
        assert b.by_source.get_tokens(SavingsSource.SEMANTIC_CACHE) == 250

    def test_no_hit(self):
        assert parse_gptcache_hit({}).has_any_savings is False


class TestModelRouting:
    def test_routing_savings(self):
        b = parse_model_routing_metadata({"tokens_routed": 500, "usd_saved": 0.05})
        assert b.by_source.get_tokens(SavingsSource.MODEL_ROUTING) == 500
        assert b.by_source.get_usd(SavingsSource.MODEL_ROUTING) == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# Phase 1.3: Aggregate (no double-count)
# ---------------------------------------------------------------------------


class TestSavingsOrchestrator:
    def test_record_aggregates_by_provider(self):
        o = SavingsOrchestrator()
        b1 = RequestSavingsBreakdown(
            raw_input_tokens=1000, provider_cached_tokens=200, total_tokens_saved=200
        )
        b1.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 200)
        o.record_request(b1, provider="anthropic", model="claude-3-haiku")

        b2 = RequestSavingsBreakdown(
            raw_input_tokens=2000, provider_cached_tokens=500, total_tokens_saved=500
        )
        b2.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 500)
        o.record_request(b2, provider="anthropic", model="claude-3-haiku")

        a = o.aggregate
        assert a.requests == 2
        assert a.raw_input_tokens == 3000
        assert a.total_tokens_saved == 700
        assert a.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 700
        # Per-provider
        assert a.by_provider["anthropic"].get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 700
        # Per-model
        assert a.by_model["claude-3-haiku"].get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 700

    def test_combined_total_equals_sum_of_per_source(self):
        o = SavingsOrchestrator()
        b = RequestSavingsBreakdown(raw_input_tokens=1000, total_tokens_saved=0)
        b.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 100)
        b.by_source.add(SavingsSource.CUTCTX_COMPRESSION, 200)
        b.by_source.add(SavingsSource.SEMANTIC_CACHE, 50)
        b.total_tokens_saved = 350
        o.record_request(b)
        a = o.aggregate
        # Combined total == sum of per-source
        assert a.total_tokens_saved == sum(
            a.by_source.tokens.values()
        )
        assert a.total_tokens_saved == 350

    def test_no_double_counting_across_sources(self):
        o = SavingsOrchestrator()
        b = RequestSavingsBreakdown(raw_input_tokens=1000, total_tokens_saved=300)
        b.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 200)
        b.by_source.add(SavingsSource.CUTCTX_COMPRESSION, 100)
        o.record_request(b)
        # Provider cache and Cutctx compression are tracked independently
        # even when they apply to the same request.
        a = o.aggregate
        assert a.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 200
        assert a.by_source.get_tokens(SavingsSource.CUTCTX_COMPRESSION) == 100
        # Combined is their sum
        assert a.total_tokens_saved == 300

    def test_reset_clears(self):
        o = SavingsOrchestrator()
        b = RequestSavingsBreakdown()
        b.by_source.add(SavingsSource.CUTCTX_COMPRESSION, 100)
        o.record_request(b)
        o.reset()
        assert o.aggregate.requests == 0
        assert o.aggregate.total_tokens_saved == 0


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Older request records (no breakdown) must not crash."""

    def test_legacy_dict_missing_all_fields(self):
        b = RequestSavingsBreakdown.from_dict({})
        assert b.raw_input_tokens == 0
        assert b.post_cutctx_tokens == 0
        assert b.by_source.total_tokens == 0

    def test_legacy_dict_with_only_raw(self):
        b = RequestSavingsBreakdown.from_dict({"raw_input_tokens": 500})
        assert b.raw_input_tokens == 500
        assert b.post_cutctx_tokens == 0


class TestZeroState:
    """Zero-state parsing and aggregation must be safe."""

    def test_all_providers_garbage_input(self):
        for parser in (
            parse_openai_savings,
            parse_anthropic_savings,
            parse_gemini_savings,
            parse_bedrock_savings,
            parse_azure_openai_savings,
            parse_litellm_cache,
            parse_vllm_apc,
            parse_gptcache_hit,
            parse_model_routing_metadata,
        ):
            assert parser(None).has_any_savings is False
            assert parser({}).has_any_savings is False
            assert parser("string").has_any_savings is False
            assert parser(42).has_any_savings is False
            assert parser([]).has_any_savings is False

    def test_empty_aggregate_to_dict(self):
        a = AggregateSavings()
        d = a.to_dict()
        assert d["requests"] == 0
        assert d["total_tokens_saved"] == 0
        assert d["by_source"]["total_tokens"] == 0


class TestNoDoubleCounting:
    """Cross-source invariant: each source tracks its own tokens."""

    def test_provider_cache_does_not_appear_in_compression(self):
        b = RequestSavingsBreakdown()
        b.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 100)
        assert b.by_source.get_tokens(SavingsSource.CUTCTX_COMPRESSION) == 0

    def test_semantic_cache_does_not_appear_in_provider(self):
        b = RequestSavingsBreakdown()
        b.by_source.add(SavingsSource.SEMANTIC_CACHE, 50)
        assert b.by_source.get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 0

    def test_orchestrator_combined_is_sum(self):
        o = SavingsOrchestrator()
        b = RequestSavingsBreakdown(total_tokens_saved=0)
        b.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 10)
        b.by_source.add(SavingsSource.CUTCTX_COMPRESSION, 20)
        b.by_source.add(SavingsSource.SEMANTIC_CACHE, 30)
        b.by_source.add(SavingsSource.PREFIX_CACHE_SELF_HOSTED, 40)
        b.by_source.add(SavingsSource.MODEL_ROUTING, 50)
        o.record_request(b)
        a = o.aggregate
        assert a.total_tokens_saved == 150
        assert a.by_source.total_tokens == 150
