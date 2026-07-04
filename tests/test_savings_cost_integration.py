"""Integration tests for the savings orchestrator + CostTracker wiring."""

from __future__ import annotations

from cutctx.proxy.cost import CostTracker
from cutctx.savings import (
    RequestSavingsBreakdown,
    SavingsOrchestrator,
    SavingsSource,
)


class TestCostTrackerWiring:
    def test_record_breakdown_appears_in_stats(self):
        t = CostTracker()
        b = RequestSavingsBreakdown(raw_input_tokens=1000, total_tokens_saved=500)
        b.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 200)
        b.by_source.add(SavingsSource.CUTCTX_COMPRESSION, 300)
        t.record_savings_breakdown(b, provider="anthropic", model="claude-3-haiku")
        stats = t.stats()
        assert "savings_by_source" in stats
        assert "savings_by_provider" in stats
        sbs = stats["savings_by_source"]
        assert sbs["tokens"]["provider_prompt_cache"] == 200
        assert sbs["tokens"]["cutctx_compression"] == 300
        assert sbs["total_tokens"] == 500
        sbp = stats["savings_by_provider"]
        assert "anthropic" in sbp
        assert sbp["anthropic"]["total_tokens"] == 500

    def test_multiple_requests_aggregate(self):
        t = CostTracker()
        for i in range(3):
            b = RequestSavingsBreakdown(raw_input_tokens=1000, total_tokens_saved=100)
            b.by_source.add(SavingsSource.CUTCTX_COMPRESSION, 100)
            t.record_savings_breakdown(b, provider="openai", model="gpt-4o")
        stats = t.stats()
        assert stats["savings_by_source"]["tokens"]["cutctx_compression"] == 300
        assert stats["savings_by_provider"]["openai"]["total_tokens"] == 300

    def test_zero_state_safe(self):
        t = CostTracker()
        stats = t.stats()
        assert stats["savings_by_source"]["total_tokens"] == 0
        assert stats["savings_by_provider"] == {}


class TestOrchestratorDirect:
    def test_aggregate_combined_equals_sum(self):
        o = SavingsOrchestrator()
        b1 = RequestSavingsBreakdown()
        b1.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 100)
        o.record_request(b1, provider="anthropic")
        b2 = RequestSavingsBreakdown()
        b2.by_source.add(SavingsSource.CUTCTX_COMPRESSION, 200)
        o.record_request(b2, provider="anthropic")
        a = o.aggregate
        # Combined total = sum of per-source
        assert a.total_tokens_saved == 300

    def test_per_provider_breakdown(self):
        o = SavingsOrchestrator()
        b1 = RequestSavingsBreakdown()
        b1.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 50)
        o.record_request(b1, provider="anthropic")
        b2 = RequestSavingsBreakdown()
        b2.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, 75)
        o.record_request(b2, provider="openai")
        a = o.aggregate
        assert a.by_provider["anthropic"].get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 50
        assert a.by_provider["openai"].get_tokens(SavingsSource.PROVIDER_PROMPT_CACHE) == 75
