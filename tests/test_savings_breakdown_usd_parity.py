import pytest

from cutctx.proxy.outcome import RequestOutcome, _build_savings_breakdown
from cutctx.savings import SavingsSource


def test_build_savings_breakdown_usd_parity():
    # Construct a RequestOutcome that exercises compression, semantic cache,
    # self-hosted prefix cache, and model routing simultaneously.
    outcome = RequestOutcome(
        request_id="req-123",
        provider="anthropic",
        model="gpt-4o",  # we test with a model we know litellm costs
        original_tokens=10000,
        optimized_tokens=2000,
        output_tokens=50,
        tokens_saved=8000,
        attempted_input_tokens=10000,
        semantic_cache_avoided_tokens=1000,
        self_hosted_prefix_cache_hits=2000,
        model_routing_tokens_saved=500,
        model_routing_usd_saved=0.005,
    )

    tokens_by_source, usd_by_source, breakdown = _build_savings_breakdown(outcome)

    # We should have attribution for:
    # 1. Semantic cache
    # 2. Self-hosted prefix cache
    # 3. Model routing
    # 4. Cutctx compression (the residual: 8000 - (1000+2000+500) = 4500)

    assert tokens_by_source.get(SavingsSource.SEMANTIC_CACHE.value) == 1000
    assert tokens_by_source.get(SavingsSource.PREFIX_CACHE_SELF_HOSTED.value) == 2000
    assert tokens_by_source.get(SavingsSource.MODEL_ROUTING.value) == 500
    assert tokens_by_source.get(SavingsSource.CUTCTX_COMPRESSION.value) == 4500

    # Acceptance: every key present in the by-source *tokens* dict
    # has a corresponding key in the by-source *USD* dict after this function returns.
    for key, tokens in tokens_by_source.items():
        assert key in usd_by_source
        assert usd_by_source[key] > 0.0
