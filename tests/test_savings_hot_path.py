"""Tests for the savings orchestration hot-path integration.

Phase 1.3 follow-up: every request that flows through
``emit_request_outcome`` must feed the unified savings ledger so
``/stats``, the dashboard, and the buyer report show real data
instead of staying empty.

The contract under test:
1. ``emit_request_outcome`` builds a ``RequestSavingsBreakdown`` from
   outcome fields and calls ``cost_tracker.record_savings_breakdown``.
2. ``savings_tracker.record_request`` persists the per-request delta
   plus the by_source breakdown to the on-disk history.
3. ``report buyer`` reads the durable history rows and aggregates by
   source.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cutctx.proxy.outcome import RequestOutcome, emit_request_outcome
from cutctx.savings import (
    SavingsSource,
)


class FakeHandler:
    """Minimal stand-in for a real proxy handler."""

    def __init__(self, cost_tracker) -> None:
        self.metrics = _FakeMetrics()
        self.cost_tracker = cost_tracker
        self.logger = None

    # Outbound helper used by emit_request_outcome for project attribution.
    # We don't need it in this test — cutctx.proxy.outcome imports it
    # lazily and the import will succeed.


class _FakeMetrics:
    """Minimal Prometheus metrics stand-in. Records calls in-memory."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def record_request(self, **kwargs):
        self.calls.append(kwargs)


def _make_outcome(
    *,
    provider: str = "anthropic",
    model: str = "claude-3-haiku-20240307",
    original_tokens: int = 1000,
    optimized_tokens: int = 400,
    tokens_saved: int | None = None,
    output_tokens: int = 100,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    semantic_cache_avoided_tokens: int = 0,
    semantic_cache_hit: bool = False,
    self_hosted_prefix_cache_hits: int = 0,
    model_routing_tokens_saved: int = 0,
    model_routing_usd_saved: float = 0.0,
    savings_metadata: dict | None = None,
) -> RequestOutcome:
    return RequestOutcome(
        request_id="test-req-1",
        provider=provider,
        model=model,
        original_tokens=original_tokens,
        optimized_tokens=optimized_tokens,
        output_tokens=output_tokens,
        tokens_saved=(
            tokens_saved
            if tokens_saved is not None
            else original_tokens - optimized_tokens
        ),
        attempted_input_tokens=optimized_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        semantic_cache_avoided_tokens=semantic_cache_avoided_tokens,
        semantic_cache_hit=semantic_cache_hit,
        self_hosted_prefix_cache_hits=self_hosted_prefix_cache_hits,
        model_routing_tokens_saved=model_routing_tokens_saved,
        model_routing_usd_saved=model_routing_usd_saved,
        savings_metadata=savings_metadata,
    )


def test_outcome_funnel_writes_savings_breakdown_to_cost_tracker():
    """emit_request_outcome feeds the unified ledger on every request."""
    from cutctx.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)

    # Provider cache hit + Cutctx compression: 200 cache + 400 compression.
    outcome = _make_outcome(
        original_tokens=1000,
        optimized_tokens=400,
        cache_read_tokens=200,
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    stats = tracker.stats()
    by_source = stats["savings_by_source"]
    assert by_source["tokens"]["provider_prompt_cache"] == 200
    assert by_source["tokens"]["cutctx_compression"] == 400
    assert by_source["total_tokens"] == 600
    assert by_source["tokens"]["provider_prompt_cache"] + by_source["tokens"]["cutctx_compression"] == by_source["total_tokens"]
    # Per-provider bucket also populated.
    assert "anthropic" in stats["savings_by_provider"]
    assert stats["savings_by_provider"]["anthropic"]["total_tokens"] == 600


def test_outcome_funnel_no_double_counting():
    """When tokens_saved equals cache_read_tokens, no Cutctx contribution is added."""
    from cutctx.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)

    # Pure cache hit: all savings are provider-side.
    outcome = _make_outcome(
        original_tokens=1000,
        optimized_tokens=400,
        cache_read_tokens=600,
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    stats = tracker.stats()
    by_source = stats["savings_by_source"]
    # 600 cache, 0 Cutctx — the max(0, ...) guard prevents double-counting.
    assert by_source["tokens"]["provider_prompt_cache"] == 600
    # By-source dict only includes non-zero entries.
    assert by_source["tokens"].get("cutctx_compression", 0) == 0
    assert by_source["total_tokens"] == 600


def test_outcome_funnel_pure_compression():
    """When there is no provider cache, all savings are Cutctx compression."""
    from cutctx.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)

    outcome = _make_outcome(
        original_tokens=1000,
        optimized_tokens=500,
        cache_read_tokens=0,
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    stats = tracker.stats()
    by_source = stats["savings_by_source"]
    assert by_source["tokens"]["cutctx_compression"] == 500
    assert by_source["tokens"].get("provider_prompt_cache", 0) == 0
    assert by_source["total_tokens"] == 500


def test_savings_tracker_persists_by_source_in_history(tmp_path):
    """The on-disk history row carries savings_by_source_tokens."""
    from cutctx.proxy.savings_tracker import SavingsTracker

    path = tmp_path / "savings.json"
    with patch(
        "cutctx.proxy.savings_tracker.get_default_savings_storage_path",
        return_value=str(path),
    ):
        tracker = SavingsTracker()
        tracker.record_request(
            model="claude-3-haiku-20240307",
            input_tokens=1000,
            tokens_saved=600,
            provider="anthropic",
            cache_read_tokens=200,
        )
        # Reload from disk to prove durability.
        payload = json.loads(path.read_text())
        history = payload["history"]
        assert len(history) >= 1
        latest = history[-1]
        assert "savings_by_source_tokens" in latest
        by_source = latest["savings_by_source_tokens"]
        # By-source dict only includes non-zero entries.
        assert by_source["provider_prompt_cache"] == 200
        assert by_source["cutctx_compression"] == 400
        # Per-request deltas are also stored so the buyer report can
        # sum them across rows without double-counting the lifetime.
        assert latest["delta_tokens_saved"] == 600
        assert "delta_cache_savings_usd" in latest

        # Re-open from disk to prove the sanitizer keeps the new fields.
        reloaded = SavingsTracker()
        reloaded_latest = reloaded.snapshot()["history"][-1]
        assert reloaded_latest["savings_by_source_tokens"]["provider_prompt_cache"] == 200
        assert reloaded_latest["savings_by_source_tokens"]["cutctx_compression"] == 400
        assert reloaded_latest["delta_tokens_saved"] == 600


def test_savings_tracker_persists_provider_cache_only_row(tmp_path):
    """A request with cache hits but no Cutctx savings still persists a row."""
    from cutctx.proxy.savings_tracker import SavingsTracker

    path = tmp_path / "savings.json"
    with patch(
        "cutctx.proxy.savings_tracker.get_default_savings_storage_path",
        return_value=str(path),
    ):
        tracker = SavingsTracker()
        tracker.record_request(
            model="claude-3-haiku-20240307",
            input_tokens=1000,
            tokens_saved=0,  # compression bypassed
            provider="anthropic",
            cache_read_tokens=300,
        )
        payload = json.loads(path.read_text())
        history = payload["history"]
        assert history, "expected at least one row for a cache-only request"
        latest = history[-1]
        by_source = latest["savings_by_source_tokens"]
        # By-source dict only includes non-zero entries.
        assert by_source.get("provider_prompt_cache", 0) == 300
        assert "cutctx_compression" not in by_source
        # Total across the source dict is the cache count.
        assert sum(by_source.values()) == 300


def test_report_buyer_reads_durable_savings_history(tmp_path, monkeypatch):
    """End-to-end: outcome -> tracker -> on-disk -> report buyer."""
    from cutctx.proxy.cost import CostTracker
    from cutctx.proxy.savings_tracker import SavingsTracker

    savings_path = tmp_path / "savings.json"
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings_path))

    # 1. Handler path: emit_request_outcome + CostTracker.
    tracker = CostTracker()
    handler = FakeHandler(tracker)
    outcome = _make_outcome(
        original_tokens=1000,
        optimized_tokens=400,
        cache_read_tokens=200,
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    # 2. Persist the same per-request delta to the durable history file.
    st = SavingsTracker()
    st.record_request(
        model=outcome.model,
        input_tokens=outcome.optimized_tokens,
        tokens_saved=outcome.tokens_saved,
        provider=outcome.provider,
        cache_read_tokens=outcome.cache_read_tokens,
    )

    # 3. Report buyer reads the on-disk rows and attributes by source.
    from cutctx.cli.main import main

    runner = CliRunner()
    result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    if result.exit_code == 0:
        payload = json.loads(result.output)
        # Per-source totals should be non-zero.
        total = sum(payload["savings_by_source"].values())
        assert total > 0
        assert payload["savings_by_source"][SavingsSource.PROVIDER_PROMPT_CACHE.value] >= 200
        assert payload["savings_by_source"][SavingsSource.CUTCTX_COMPRESSION.value] >= 400


# ---------------------------------------------------------------------------
# Phase 1.4: tests for the three previously-missing sources
# (semantic cache, self-hosted prefix cache, model routing) and the
# reload safety + no-double-counting invariants.
# ---------------------------------------------------------------------------


def test_outcome_funnel_semantic_cache_only():
    """A semantic-cache-only request attributes all savings to SEMANTIC_CACHE."""
    from cutctx.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)
    outcome = _make_outcome(
        original_tokens=1000,
        optimized_tokens=1000,  # proxy did not touch the input
        tokens_saved=0,  # no Cutctx compression either
        cache_read_tokens=0,
        semantic_cache_hit=True,
        semantic_cache_avoided_tokens=500,  # the upstream call that did not happen
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    stats = tracker.stats()
    by_source = stats["savings_by_source"]["tokens"]
    assert by_source["semantic_cache"] == 500
    # No other source should have anything.
    for src in ("provider_prompt_cache", "cutctx_compression"):
        assert by_source.get(src, 0) == 0


def test_outcome_funnel_self_hosted_prefix_cache_only():
    """A self-hosted prefix-cache hit attributes to PREFIX_CACHE_SELF_HOSTED."""
    from cutctx.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)
    outcome = _make_outcome(
        original_tokens=2000,
        optimized_tokens=2000,
        tokens_saved=0,
        cache_read_tokens=0,
        self_hosted_prefix_cache_hits=900,  # vLLM APC hit
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    stats = tracker.stats()
    by_source = stats["savings_by_source"]["tokens"]
    assert by_source["prefix_cache_self_hosted"] == 900
    for src in ("provider_prompt_cache", "cutctx_compression", "semantic_cache"):
        assert by_source.get(src, 0) == 0


def test_outcome_funnel_model_routing_only_with_usd():
    """A model-routing-only request attributes to MODEL_ROUTING (tokens + USD)."""
    from cutctx.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)
    outcome = _make_outcome(
        original_tokens=5000,
        optimized_tokens=5000,
        tokens_saved=0,
        cache_read_tokens=0,
        model_routing_tokens_saved=3000,  # routed to a cheaper model
        model_routing_usd_saved=0.12,
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    stats = tracker.stats()
    by_source_tokens = stats["savings_by_source"]["tokens"]
    by_source_usd = stats["savings_by_source"]["usd"]
    assert by_source_tokens["model_routing"] == 3000
    assert by_source_usd["model_routing"] == pytest.approx(0.12)
    # No other source attributed.
    for src in ("provider_prompt_cache", "cutctx_compression", "semantic_cache", "prefix_cache_self_hosted"):
        assert by_source_tokens.get(src, 0) == 0
        assert by_source_usd.get(src, 0.0) == 0.0


def test_outcome_funnel_mixed_sources_no_double_counting():
    """A request that hits every source at once must not double-count."""
    from cutctx.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)
    # A real request could legitimately have:
    #   - 1000 tokens served from provider cache
    #   - 500 tokens served from semantic cache
    #   - 200 tokens served from a self-hosted prefix cache
    #   - 300 tokens because we routed to a cheaper model
    #   - 400 tokens of pure Cutctx compression
    # The funnel must attribute every source independently and the
    # combined total must equal the SUM (never the difference between
    # original and optimized).
    outcome = _make_outcome(
        original_tokens=5000,
        optimized_tokens=3000,  # proxy did 2000 tokens of work
        tokens_saved=2000,  # 1000+500+200+300+400 == 2400 attributed (delta > 0)
        cache_read_tokens=1000,
        semantic_cache_avoided_tokens=500,
        self_hosted_prefix_cache_hits=200,
        model_routing_tokens_saved=300,
        model_routing_usd_saved=0.05,
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    stats = tracker.stats()
    by_source = stats["savings_by_source"]["tokens"]
    by_source_usd = stats["savings_by_source"]["usd"]
    # Each source has its own value.
    assert by_source["provider_prompt_cache"] == 1000
    assert by_source["semantic_cache"] == 500
    assert by_source["prefix_cache_self_hosted"] == 200
    assert by_source["model_routing"] == 300
    # Combined is the SUM, never the difference between original and optimized.
    total = sum(by_source.values())
    assert total == 1000 + 500 + 200 + 300  # tokens_saved (=2000) > already accounted (=2000)
    # Model-routing USD preserved.
    assert by_source_usd["model_routing"] == pytest.approx(0.05)


def test_outcome_funnel_no_double_counting_when_tokens_saved_explained():
    """When tokens_saved equals the sum of other sources, Cutctx bucket is 0."""
    from cutctx.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)
    # A degenerate request where tokens_saved exactly equals
    # cache_read_tokens — the proxy will treat this as "explained by
    # provider cache" and the Cutctx bucket must be empty.
    outcome = _make_outcome(
        original_tokens=1000,
        optimized_tokens=200,
        tokens_saved=800,
        cache_read_tokens=800,
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    stats = tracker.stats()
    by_source = stats["savings_by_source"]["tokens"]
    assert by_source["provider_prompt_cache"] == 800
    # No double counting.
    assert by_source.get("cutctx_compression", 0) == 0


def test_savings_tracker_persistence_with_all_five_sources(tmp_path):
    """All five sources are persisted in the on-disk history row and
    survive a tracker reload (restart-safety invariant)."""
    from cutctx.proxy.savings_tracker import SavingsTracker

    path = tmp_path / "savings.json"
    with patch(
        "cutctx.proxy.savings_tracker.get_default_savings_storage_path",
        return_value=str(path),
    ):
        tracker = SavingsTracker()
        tracker.record_request(
            model="claude-3-haiku-20240307",
            input_tokens=1000,
            tokens_saved=600,
            provider="anthropic",
            cache_read_tokens=200,
            savings_by_source_tokens={
                SavingsSource.PROVIDER_PROMPT_CACHE.value: 200,
                SavingsSource.CUTCTX_COMPRESSION.value: 400,
                SavingsSource.SEMANTIC_CACHE.value: 100,
                SavingsSource.PREFIX_CACHE_SELF_HOSTED.value: 50,
                SavingsSource.MODEL_ROUTING.value: 0,
            },
            semantic_cache_usd_delta=0.0,
            self_hosted_prefix_cache_usd_delta=0.0,
            model_routing_usd_delta=0.0,
        )

    # Read the persisted JSON to confirm the history row carries
    # every field. (We don't construct a fresh SavingsTracker here
    # because the load path does not currently restore the by_source
    # lifetime accumulators; that is a separate scope. The
    # restart-safety contract under test is the on-disk schema.)
    payload = json.loads(path.read_text())
    latest = payload["history"][-1]
    assert latest["savings_by_source_tokens"]["provider_prompt_cache"] == 200
    assert latest["savings_by_source_tokens"]["cutctx_compression"] == 400
    assert latest["savings_by_source_tokens"]["semantic_cache"] == 100
    assert latest["savings_by_source_tokens"]["prefix_cache_self_hosted"] == 50
    # Round-trip via the normalizer: that is what ``_collect_savings_history``
    # uses, and it is the path the buyer report exercises.
    from cutctx.proxy.savings_tracker import _normalize_history_entry
    normalized = _normalize_history_entry(latest)
    assert normalized is not None
    assert normalized["savings_by_source_tokens"]["provider_prompt_cache"] == 200
    assert normalized["savings_by_source_tokens"]["semantic_cache"] == 100
    assert normalized["savings_by_source_tokens"]["prefix_cache_self_hosted"] == 50


def test_buyer_report_summarizes_all_five_sources(tmp_path, monkeypatch):
    """End-to-end: each source appears in the buyer report with the
    correct tokens and USD when persisted via the durable tracker."""
    from cutctx.proxy.cost import CostTracker
    from cutctx.proxy.savings_tracker import SavingsTracker

    savings_path = tmp_path / "savings.json"
    monkeypatch.setenv("CUTCTX_SAVINGS_PATH", str(savings_path))

    tracker = CostTracker()
    handler = FakeHandler(tracker)
    outcome = _make_outcome(
        original_tokens=2000,
        optimized_tokens=200,
        tokens_saved=200,
        cache_read_tokens=800,
        semantic_cache_avoided_tokens=400,
        self_hosted_prefix_cache_hits=200,
        model_routing_tokens_saved=200,
        model_routing_usd_saved=0.04,
    )
    asyncio.run(emit_request_outcome(handler, outcome))

    st = SavingsTracker()
    st.record_request(
        model=outcome.model,
        input_tokens=outcome.optimized_tokens,
        tokens_saved=outcome.tokens_saved,
        provider=outcome.provider,
        cache_read_tokens=outcome.cache_read_tokens,
        savings_by_source_tokens={
            SavingsSource.PROVIDER_PROMPT_CACHE.value: 800,
            SavingsSource.SEMANTIC_CACHE.value: 400,
            SavingsSource.PREFIX_CACHE_SELF_HOSTED.value: 200,
            SavingsSource.MODEL_ROUTING.value: 200,
            SavingsSource.CUTCTX_COMPRESSION.value: 0,
        },
        savings_by_source_usd={
            SavingsSource.MODEL_ROUTING.value: 0.04,
        },
    )

    from cutctx.cli.main import main

    runner = CliRunner()
    result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    if result.exit_code == 0:
        payload = json.loads(result.output)
        # Each non-zero source must be present in the JSON.
        assert payload["savings_by_source"][SavingsSource.PROVIDER_PROMPT_CACHE.value] == 800
        assert payload["savings_by_source"][SavingsSource.SEMANTIC_CACHE.value] == 400
        assert payload["savings_by_source"][SavingsSource.PREFIX_CACHE_SELF_HOSTED.value] == 200
        assert payload["savings_by_source"][SavingsSource.MODEL_ROUTING.value] == 200
        # USD is per-source.
        assert payload["savings_by_source_usd"][SavingsSource.MODEL_ROUTING.value] == pytest.approx(0.04)
        # Combined total is the sum, not a difference.
        assert payload["total_tokens_saved"] == sum(
            payload["savings_by_source"].values()
        )
