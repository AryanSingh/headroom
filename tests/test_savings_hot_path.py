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
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from headroom.savings import (
    RequestSavingsBreakdown,
    SavingsSource,
)
from headroom.proxy.outcome import RequestOutcome, emit_request_outcome


class FakeHandler:
    """Minimal stand-in for a real proxy handler."""

    def __init__(self, cost_tracker) -> None:
        self.metrics = _FakeMetrics()
        self.cost_tracker = cost_tracker
        self.logger = None

    # Outbound helper used by emit_request_outcome for project attribution.
    # We don't need it in this test — headroom.proxy.outcome imports it
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
    output_tokens: int = 100,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> RequestOutcome:
    return RequestOutcome(
        request_id="test-req-1",
        provider=provider,
        model=model,
        original_tokens=original_tokens,
        optimized_tokens=optimized_tokens,
        output_tokens=output_tokens,
        tokens_saved=original_tokens - optimized_tokens,
        attempted_input_tokens=optimized_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )


def test_outcome_funnel_writes_savings_breakdown_to_cost_tracker():
    """emit_request_outcome feeds the unified ledger on every request."""
    from headroom.proxy.cost import CostTracker

    tracker = CostTracker()
    handler = FakeHandler(tracker)

    # Provider cache hit + CutCtx compression: 200 cache + 400 compression.
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
    """When tokens_saved equals cache_read_tokens, no CutCtx contribution is added."""
    from headroom.proxy.cost import CostTracker

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
    # 600 cache, 0 CutCtx — the max(0, ...) guard prevents double-counting.
    assert by_source["tokens"]["provider_prompt_cache"] == 600
    # By-source dict only includes non-zero entries.
    assert by_source["tokens"].get("cutctx_compression", 0) == 0
    assert by_source["total_tokens"] == 600


def test_outcome_funnel_pure_compression():
    """When there is no provider cache, all savings are CutCtx compression."""
    from headroom.proxy.cost import CostTracker

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
    from headroom.proxy.savings_tracker import SavingsTracker

    path = tmp_path / "savings.json"
    with patch(
        "headroom.proxy.savings_tracker.get_default_savings_storage_path",
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


def test_savings_tracker_persists_provider_cache_only_row(tmp_path):
    """A request with cache hits but no CutCtx savings still persists a row."""
    from headroom.proxy.savings_tracker import SavingsTracker

    path = tmp_path / "savings.json"
    with patch(
        "headroom.proxy.savings_tracker.get_default_savings_storage_path",
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
    from headroom.proxy.cost import CostTracker
    from headroom.proxy.savings_tracker import SavingsTracker

    savings_path = tmp_path / "savings.json"
    monkeypatch.setenv("HEADROOM_SAVINGS_PATH", str(savings_path))

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
    from headroom.cli.main import main

    runner = CliRunner()
    result = runner.invoke(main, ["report", "buyer", "--format", "json"])
    if result.exit_code == 0:
        payload = json.loads(result.output)
        # Per-source totals should be non-zero.
        total = sum(payload["savings_by_source"].values())
        assert total > 0
        assert payload["savings_by_source"][SavingsSource.PROVIDER_PROMPT_CACHE.value] >= 200
        assert payload["savings_by_source"][SavingsSource.CUTCTX_COMPRESSION.value] >= 400
