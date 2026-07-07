"""Tests for WS10/WS11/WS13 attribution in _build_savings_breakdown.

Constructs synthetic RequestOutcomes with the three new fields set and
asserts the corresponding SavingsSource keys appear in both the tokens
and USD dicts with the expected values.
"""

from __future__ import annotations

import pytest

from cutctx.proxy.outcome import RequestOutcome, _build_savings_breakdown
from cutctx.savings import SavingsSource


def test_memoization_attribution() -> None:
    """Memoization tokens appear in the breakdown with the MEMOIZATION key."""
    outcome = RequestOutcome(
        request_id="req-memo-1",
        provider="anthropic",
        model="claude-sonnet-4-5",
        original_tokens=5000,
        optimized_tokens=3000,
        output_tokens=100,
        tokens_saved=2000,
        attempted_input_tokens=5000,
        memoization_hits=3,
        memoization_tokens_saved=600,
    )
    tokens, usd, breakdown = _build_savings_breakdown(outcome)
    assert SavingsSource.MEMOIZATION.value in tokens
    assert tokens[SavingsSource.MEMOIZATION.value] == 600
    # USD should be auto-computed via value_tokens_usd since a known
    # model was provided and tokens > 0.
    assert SavingsSource.MEMOIZATION.value in usd
    assert usd[SavingsSource.MEMOIZATION.value] > 0.0


def test_memoization_zero_hits_omitted() -> None:
    """Memoization with zero hits and zero tokens is absent from breakdown."""
    outcome = RequestOutcome(
        request_id="req-memo-0",
        provider="anthropic",
        model="claude-sonnet-4-5",
        original_tokens=5000,
        optimized_tokens=3000,
        output_tokens=100,
        tokens_saved=2000,
        attempted_input_tokens=5000,
        memoization_hits=0,
        memoization_tokens_saved=0,
    )
    tokens, usd, _ = _build_savings_breakdown(outcome)
    assert SavingsSource.MEMOIZATION.value not in tokens
    # It may still get USD auto-computed as 0.0 which won't be emitted
    assert SavingsSource.MEMOIZATION.value not in usd


def test_output_optimization_attribution() -> None:
    """Output-optimization tokens appear with the OUTPUT_OPTIMIZATION key."""
    outcome = RequestOutcome(
        request_id="req-oo-1",
        provider="anthropic",
        model="claude-sonnet-4-5",
        original_tokens=5000,
        optimized_tokens=3000,
        output_tokens=100,
        tokens_saved=2000,
        attempted_input_tokens=5000,
        output_optimization_tokens_saved=400,
    )
    tokens, usd, breakdown = _build_savings_breakdown(outcome)
    assert SavingsSource.OUTPUT_OPTIMIZATION.value in tokens
    assert tokens[SavingsSource.OUTPUT_OPTIMIZATION.value] == 400
    assert SavingsSource.OUTPUT_OPTIMIZATION.value in usd
    assert usd[SavingsSource.OUTPUT_OPTIMIZATION.value] > 0.0


def test_batch_routing_attribution() -> None:
    """Batch-routing tokens and USD appear with the BATCH_ROUTING key."""
    outcome = RequestOutcome(
        request_id="req-br-1",
        provider="anthropic",
        model="claude-sonnet-4-5",
        original_tokens=5000,
        optimized_tokens=3000,
        output_tokens=100,
        tokens_saved=2000,
        attempted_input_tokens=5000,
        batch_routing_tokens_saved=10000,
        batch_routing_usd_saved=0.015,  # pre-computed at handler site
    )
    tokens, usd, breakdown = _build_savings_breakdown(outcome)
    assert SavingsSource.BATCH_ROUTING.value in tokens
    assert tokens[SavingsSource.BATCH_ROUTING.value] == 10000
    assert SavingsSource.BATCH_ROUTING.value in usd
    assert usd[SavingsSource.BATCH_ROUTING.value] == 0.015


def test_batch_routing_zero_usd_auto_computed() -> None:
    """Batch routing with zero explicit USD gets auto-computed from tokens."""
    outcome = RequestOutcome(
        request_id="req-br-0usd",
        provider="anthropic",
        model="claude-sonnet-4-5",
        original_tokens=5000,
        optimized_tokens=3000,
        output_tokens=100,
        tokens_saved=2000,
        attempted_input_tokens=5000,
        batch_routing_tokens_saved=10000,
        batch_routing_usd_saved=0.0,
    )
    tokens, usd, _ = _build_savings_breakdown(outcome)
    assert SavingsSource.BATCH_ROUTING.value in tokens
    # USD is auto-computed via value_tokens_usd since tokens > 0
    assert SavingsSource.BATCH_ROUTING.value in usd
    assert usd[SavingsSource.BATCH_ROUTING.value] > 0.0


def test_all_three_sources_simultaneously() -> None:
    """All three new sources coexist in the breakdown when set together."""
    outcome = RequestOutcome(
        request_id="req-all-3",
        provider="anthropic",
        model="claude-sonnet-4-5",
        original_tokens=5000,
        optimized_tokens=3000,
        output_tokens=100,
        tokens_saved=2000,
        attempted_input_tokens=5000,
        memoization_hits=2,
        memoization_tokens_saved=300,
        output_optimization_tokens_saved=200,
        batch_routing_tokens_saved=5000,
        batch_routing_usd_saved=0.0075,
    )
    tokens, usd, _ = _build_savings_breakdown(outcome)
    for source in (
        SavingsSource.MEMOIZATION,
        SavingsSource.OUTPUT_OPTIMIZATION,
        SavingsSource.BATCH_ROUTING,
    ):
        assert source.value in tokens, f"{source.value} missing from tokens"
        assert source.value in usd, f"{source.value} missing from usd"
    assert tokens[SavingsSource.MEMOIZATION.value] == 300
    assert tokens[SavingsSource.OUTPUT_OPTIMIZATION.value] == 200
    assert tokens[SavingsSource.BATCH_ROUTING.value] == 5000
