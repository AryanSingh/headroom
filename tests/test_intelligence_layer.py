"""Comprehensive tests for the 6 intelligence-layer features.

1. Task-Aware Compression (task_aware.py)
2. Semantic Deduplication (dedup.py)
3. Context Budgeting (context_budget.py)
4. Cross-Session Profiles (profiles.py)
5. Multi-Agent Shared State (shared_context.py)
6. Cost Forecasting + Policy Engine (cost_forecast.py)
"""

from __future__ import annotations

import time

import pytest

# =====================================================================
# 1. Task-Aware Compression
# =====================================================================


class TestTaskExtractor:
    """Tests for TaskExtractor."""

    def test_extract_from_imperative_verb(self):
        from cutctx.compression.task_aware import TaskExtractor

        msgs = [{"role": "user", "content": "Fix the HTTP 500 error in the login endpoint"}]
        task = TaskExtractor.extract_task(msgs)
        assert task is not None
        assert "fix" in task.lower() or "HTTP" in task

    def test_extract_from_question_word(self):
        from cutctx.compression.task_aware import TaskExtractor

        msgs = [{"role": "user", "content": "How do I implement a rate limiter for the API?"}]
        task = TaskExtractor.extract_task(msgs)
        assert task is not None

    def test_extract_from_special_keyword(self):
        from cutctx.compression.task_aware import TaskExtractor

        msgs = [
            {
                "role": "user",
                "content": "There's a debug issue with the database connection pool timing out under load",
            }
        ]
        task = TaskExtractor.extract_task(msgs)
        assert task is not None
        assert "debug" in task.lower()

    def test_extract_returns_none_for_short_content(self):
        from cutctx.compression.task_aware import TaskExtractor

        msgs = [{"role": "user", "content": "ok"}]
        task = TaskExtractor.extract_task(msgs)
        assert task is None

    def test_extract_returns_none_for_empty_messages(self):
        from cutctx.compression.task_aware import TaskExtractor

        assert TaskExtractor.extract_task([]) is None
        assert TaskExtractor.extract_task([{"role": "assistant", "content": "hello"}]) is None

    def test_extract_uses_most_recent_user_message(self):
        from cutctx.compression.task_aware import TaskExtractor

        msgs = [
            {"role": "user", "content": "What time is it? This is a simple question."},
            {"role": "assistant", "content": "It's 3pm"},
            {
                "role": "user",
                "content": "Fix the memory leak in the worker process that handles background tasks",
            },
        ]
        task = TaskExtractor.extract_task(msgs)
        assert task is not None
        assert "memory" in task.lower() or "fix" in task.lower()


class TestRelevanceModulator:
    """Tests for RelevanceModulator."""

    def test_high_relevance_match(self):
        from cutctx.compression.task_aware import RelevanceModulator

        mod = RelevanceModulator(use_bm25=False)
        score = mod.score(
            '{"error": "connection refused", "status": 500, "endpoint": "/api/users"}',
            "debug HTTP 500 connection error",
        )
        assert score >= 0.3  # Should match on "error", "500", "connection"

    def test_low_relevance(self):
        from cutctx.compression.task_aware import RelevanceModulator

        mod = RelevanceModulator(use_bm25=False)
        score = mod.score(
            "The weather today is sunny with a high of 75 degrees",
            "debug database connection error",
        )
        assert score < 0.2

    def test_empty_content_returns_zero(self):
        from cutctx.compression.task_aware import RelevanceModulator

        mod = RelevanceModulator(use_bm25=False)
        assert mod.score("", "some task") == 0.0
        assert mod.score("content", "") == 0.0

    def test_bm25_fallback_on_error(self):
        from cutctx.compression.task_aware import RelevanceModulator

        mod = RelevanceModulator(use_bm25=True)
        # BM25 should be available, but test fallback path
        if mod._bm25_scorer is None:
            score = mod.score("some test content here", "test content")
            assert score >= 0.0


class TestTaskAwareCompressor:
    """Tests for TaskAwareCompressor."""

    def test_compress_with_task(self):
        from cutctx.compression.task_aware import TaskAwareCompressor

        comp = TaskAwareCompressor(task="debug error")
        result = comp.compress('{"error": "timeout", "code": 504, "message": "gateway timeout"}')
        assert result.compressed is not None
        assert result.original_tokens > 0
        assert result.task_used == "debug error"

    def test_compress_without_task(self):
        from cutctx.compression.task_aware import TaskAwareCompressor

        comp = TaskAwareCompressor(task=None)
        result = comp.compress("Some content to compress " * 20)
        assert result.compressed is not None
        assert result.task_used is None
        assert result.relevance_score == 1.0  # No task = fully relevant

    def test_set_task(self):
        from cutctx.compression.task_aware import TaskAwareCompressor

        comp = TaskAwareCompressor()
        assert comp.task is None
        comp.set_task("implement feature")
        assert comp.task == "implement feature"

    def test_tokens_saved_property(self):
        from cutctx.compression.task_aware import TaskAwareCompressor

        comp = TaskAwareCompressor()
        result = comp.compress("Hello world")
        assert result.tokens_saved >= 0


# =====================================================================
# 2. Semantic Deduplication
# =====================================================================


class TestSessionDeduplicator:
    """Tests for SessionDeduplicator."""

    def test_first_occurrence_not_deduped(self):
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        msgs = [{"role": "user", "content": "x" * 1000}]
        result = dedup.process(msgs)
        assert result.dedup_count == 0
        assert result.refs_created == 1

    def test_duplicate_content_deduped(self):
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        content = "The quick brown fox jumps over the lazy dog. " * 30  # >200 tokens
        msgs = [
            {"role": "user", "content": content},
        ]
        result1 = dedup.process(msgs)
        assert result1.dedup_count == 0

        result2 = dedup.process(msgs)
        assert result2.dedup_count == 1
        assert result2.tokens_saved > 0
        assert "[cutctx:ref:" in result2.messages[0]["content"]

    def test_system_messages_skipped(self):
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        msgs = [
            {"role": "system", "content": "You are a helpful assistant. " * 50},
            {"role": "user", "content": "Hello"},
        ]
        result = dedup.process(msgs)
        assert result.chunk_count == 0  # System messages not counted

    def test_short_content_not_deduped(self):
        from cutctx.dedup import MIN_DEDUP_TOKENS, SessionDeduplicator

        dedup = SessionDeduplicator()
        short_content = "x" * (MIN_DEDUP_TOKENS * 2)  # 400 chars = ~100 tokens < 200
        msgs = [{"role": "user", "content": short_content}]
        result = dedup.process(msgs)
        assert result.chunk_count == 0

    def test_stats_tracking(self):
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        content = "A" * 1000
        dedup.process([{"role": "user", "content": content}])
        dedup.process([{"role": "user", "content": content}])

        stats = dedup.stats
        assert stats["total_dedup_count"] == 1
        assert stats["tracked_hashes"] == 1
        assert stats["current_turn"] == 2

    def test_reset_clears_state(self):
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        content = "B" * 1000
        dedup.process([{"role": "user", "content": content}])
        assert dedup.stats["tracked_hashes"] == 1

        dedup.reset()
        assert dedup.stats["tracked_hashes"] == 0

    def test_hash_stability(self):
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        h1 = dedup._hash_content("test content")
        h2 = dedup._hash_content("test content")
        assert h1 == h2
        assert len(h1) == 16

    def test_multimodal_content_passthrough(self):
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        msgs = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        result = dedup.process(msgs)
        assert result.dedup_count == 0

    def test_get_hash_metadata(self):
        from cutctx.dedup import SessionDeduplicator

        dedup = SessionDeduplicator()
        content = "C" * 1000
        dedup.process([{"role": "user", "content": content}])
        h = dedup._hash_content(content)
        meta = dedup.get_hash_metadata(h)
        assert meta is not None
        assert meta.hash == h


# =====================================================================
# 3. Context Budgeting
# =====================================================================


class TestContextBudgetController:
    """Tests for ContextBudgetController."""

    def test_green_zone_no_compression(self):
        from cutctx.context_budget import BudgetZone, ContextBudgetController

        ctrl = ContextBudgetController(max_tokens=100_000)
        msgs = [{"role": "user", "content": "Hello"}] * 10
        result = ctrl.apply(msgs)
        assert result == msgs  # No modification in GREEN
        assert ctrl.status.zone == BudgetZone.GREEN

    def test_status_tracks_usage(self):
        from cutctx.context_budget import ContextBudgetController

        ctrl = ContextBudgetController(max_tokens=1000)
        ctrl._tokens_used = 500
        status = ctrl.status
        assert status.percent_used == 50.0
        assert status.tokens_used == 500
        assert status.tokens_budget == 1000

    def test_percent_used(self):
        from cutctx.context_budget import ContextBudgetController

        ctrl = ContextBudgetController(max_tokens=200)
        msgs = [{"role": "user", "content": "x" * 400}]  # ~100 tokens
        ctrl.apply(msgs)
        # Should be ~50%
        assert 0 < ctrl.percent_used <= 100.0

    def test_budget_policy_presets(self):
        from cutctx.context_budget import BudgetPolicy

        conservative = BudgetPolicy.from_env("conservative")
        assert conservative.green_threshold == 0.70
        assert conservative.compression_window_yellow == 15

        aggressive = BudgetPolicy.from_env("aggressive")
        assert aggressive.green_threshold == 0.50
        assert aggressive.compression_window_red == 3

        balanced = BudgetPolicy.from_env("balanced")
        assert balanced.green_threshold == 0.60

    def test_forecast_returns_metrics(self):
        from cutctx.context_budget import ContextBudgetController

        ctrl = ContextBudgetController(max_tokens=100_000)
        msgs = [{"role": "user", "content": "test " * 100}] * 5
        forecast = ctrl.forecast(msgs)
        assert "forecast_usd" in forecast
        assert "token_velocity" in forecast
        assert "confidence_pct" in forecast

    def test_empty_messages(self):
        from cutctx.context_budget import ContextBudgetController

        ctrl = ContextBudgetController(max_tokens=100_000)
        result = ctrl.apply([])
        assert result == []


# =====================================================================
# 4. Cross-Session Profiles
# =====================================================================


class TestCompressionProfile:
    """Tests for CompressionProfile."""

    def test_content_type_stats_update(self):
        from cutctx.profiles import ContentTypeStats

        stats = ContentTypeStats(content_type="json")
        stats.update_from_session(100, 50, was_retrieved=False)
        assert stats.total_compressions == 1
        assert stats.avg_compression_ratio == 0.5

    def test_retrieval_rate(self):
        from cutctx.profiles import ContentTypeStats

        stats = ContentTypeStats(content_type="json")
        stats.update_from_session(100, 50, was_retrieved=True)
        stats.update_from_session(100, 50, was_retrieved=False)
        assert stats.retrieval_rate == 0.5

    def test_recommendation_increases_on_retrieval(self):
        from cutctx.profiles import ContentTypeStats

        stats = ContentTypeStats(content_type="json")
        # 3 compressions with high retrieval rate
        for _ in range(5):
            stats.update_from_session(100, 30, was_retrieved=True)
        # Should recommend less compression (higher ratio)
        assert stats.recommended_ratio > 0.3

    def test_recommendation_stable_low_retrieval(self):
        from cutctx.profiles import ContentTypeStats

        stats = ContentTypeStats(content_type="json")
        for _ in range(5):
            stats.update_from_session(100, 30, was_retrieved=False)
        # Should keep current ratio
        assert stats.recommended_ratio <= 0.5

    def test_profile_load_save_roundtrip(self):
        from cutctx.profiles import CompressionProfile, ContentTypeStats, _get_profile_path

        profile = CompressionProfile("test-hash-123")
        profile.record_session(
            "sess-1",
            [
                {"content_type": "json", "original_count": 100, "compressed_count": 50},
            ],
        )

        # Save to disk
        profile_path = _get_profile_path("test-hash-123")
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile.save()

        # Reload from disk via JSON
        import json

        with open(profile_path) as f:
            data = json.load(f)
        loaded_stats = {
            name: ContentTypeStats.from_dict(s) for name, s in data.get("stats", {}).items()
        }
        assert loaded_stats["json"].total_compressions == 1

    def test_profile_summary(self):
        from cutctx.profiles import CompressionProfile

        profile = CompressionProfile("test-hash")
        profile.record_session(
            "s1",
            [
                {"content_type": "json", "original_count": 100, "compressed_count": 50},
            ],
        )
        summary = profile.summary()
        assert summary["total_content_types"] == 1
        assert "json" in summary["stats_by_type"]


# =====================================================================
# 5. Multi-Agent Shared State
# =====================================================================


class TestSharedContext:
    """Tests for SharedContext."""

    def test_put_and_get(self):
        from cutctx.shared_context import SharedContext

        ctx = SharedContext(ttl=3600)
        ctx.put("test-key", "Hello world content " * 100)
        result = ctx.get("test-key")
        assert result is not None
        assert len(result) > 0

    def test_get_full_content(self):
        from cutctx.shared_context import SharedContext

        ctx = SharedContext(ttl=3600)
        original = "Original uncompressed content " * 50
        ctx.put("key1", original)
        full = ctx.get("key1", full=True)
        compressed = ctx.get("key1", full=False)
        # Full should be larger or equal
        assert len(full) >= len(compressed)

    def test_ttl_expiry(self):
        from cutctx.shared_context import SharedContext

        ctx = SharedContext(ttl=0)  # Immediate expiry
        ctx.put("expire-me", "content " * 100)
        time.sleep(0.01)
        assert ctx.get("expire-me") is None

    def test_stats(self):
        from cutctx.shared_context import SharedContext

        ctx = SharedContext(ttl=3600)
        ctx.put("a", "content a " * 100)
        ctx.put("b", "content b " * 100)
        stats = ctx.stats()
        assert stats.entries == 2
        assert stats.total_tokens_saved >= 0

    def test_max_entries_eviction(self):
        from cutctx.shared_context import SharedContext

        ctx = SharedContext(ttl=3600, max_entries=3)
        for i in range(5):
            ctx.put(f"key-{i}", f"content {i} " * 100)
        assert len(ctx.keys()) <= 3


class TestSharedCompressionCache:
    """Tests for SharedCompressionCache."""

    def test_cache_hit(self):
        from cutctx.shared_context import SharedCompressionCache

        cache = SharedCompressionCache(max_entries=100, ttl_seconds=3600)
        content = "Test content for caching " * 50

        def compress_fn(c):
            return c[:50]

        result1, hit1 = cache.get_or_compress(content, compress_fn, "agent-1")
        assert hit1 is False  # First time = miss

        result2, hit2 = cache.get_or_compress(content, compress_fn, "agent-1")
        assert hit2 is True  # Second time = hit
        assert result1 == result2

    def test_workspace_isolation(self):
        from cutctx.shared_context import SharedCompressionCache

        cache = SharedCompressionCache()
        content1 = "Content for workspace 1 " * 100
        content2 = "Content for workspace 2 " * 100

        cache.get_or_compress(content1, lambda c: "ws1-compressed", "agent-1", "ws1")
        cache.get_or_compress(content2, lambda c: "ws2-compressed", "agent-1", "ws2")

        # Each workspace has its own content
        r1 = cache.get_compressed(SharedCompressionCache._hash_content(content1), "ws1")
        r2 = cache.get_compressed(SharedCompressionCache._hash_content(content2), "ws2")
        assert r1 == "ws1-compressed"
        assert r2 == "ws2-compressed"

        # Cross-workspace access returns None
        r_cross = cache.get_compressed(SharedCompressionCache._hash_content(content1), "ws2")
        assert r_cross is None

    def test_stats(self):
        from cutctx.shared_context import SharedCompressionCache

        cache = SharedCompressionCache()
        cache.get_or_compress("content1", lambda c: "c1", "a1")
        cache.get_or_compress("content1", lambda c: "c1", "a1")  # hit
        cache.get_or_compress("content2", lambda c: "c2", "a1")

        stats = cache.stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 2


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_register_unregister(self):
        from cutctx.shared_context import AgentRegistry

        reg = AgentRegistry()
        reg.register("agent-1")
        assert "agent-1" in reg.active_agents()
        reg.unregister("agent-1")
        assert "agent-1" not in reg.active_agents()

    def test_set_get_task(self):
        from cutctx.shared_context import AgentRegistry

        reg = AgentRegistry()
        reg.register("agent-1")
        reg.set_current_task("agent-1", "debug DB")
        assert reg.get_current_task("agent-1") == "debug DB"


class TestMultiAgentCoordinator:
    """Tests for MultiAgentCoordinator."""

    def test_compress_shared(self):
        from cutctx.shared_context import MultiAgentCoordinator

        MultiAgentCoordinator.reset_instance()
        coord = MultiAgentCoordinator.get_instance()

        result = coord.compress_shared(
            content="Large content to compress " * 100,
            agent_id="agent-1",
        )
        assert result.compressed_content is not None
        assert result.cache_hit is False

        # Second agent, same content
        result2 = coord.compress_shared(
            content="Large content to compress " * 100,
            agent_id="agent-2",
        )
        assert result2.cache_hit is True

        MultiAgentCoordinator.reset_instance()

    def test_get_agent_context(self):
        from cutctx.shared_context import MultiAgentCoordinator

        MultiAgentCoordinator.reset_instance()
        coord = MultiAgentCoordinator.get_instance()
        coord.register_agent("agent-1")
        coord.compress_shared("content " * 100, "agent-1")

        info = coord.get_agent_context("agent-1")
        assert info.active is True
        assert info.total_items_compressed >= 1

        MultiAgentCoordinator.reset_instance()


# =====================================================================
# 6. Cost Forecasting + Policy Engine
# =====================================================================


class TestCostEstimator:
    """Tests for CostEstimator."""

    def test_known_model_pricing(self):
        from cutctx.cost_forecast import CostEstimator

        est = CostEstimator(model="claude-sonnet-4-5-20250929")
        estimate = est.estimate(input_tokens=100_000, output_tokens=5_000)
        # Input: 100K * $3/1M = $0.30
        assert estimate.input_usd == pytest.approx(0.30, abs=0.001)
        # Output: 5K * $15/1M = $0.075
        assert estimate.output_usd == pytest.approx(0.075, abs=0.001)
        assert estimate.total_usd == pytest.approx(0.375, abs=0.001)

    def test_compression_savings(self):
        from cutctx.cost_forecast import CostEstimator

        est = CostEstimator(model="claude-sonnet-4-5")
        estimate = est.estimate(input_tokens=100_000, compression_ratio=0.5)
        assert estimate.compression_savings_usd > 0
        assert estimate.compressed_input_tokens == 50_000

    def test_unknown_model_uses_default(self):
        from cutctx.cost_forecast import _DEFAULT_INPUT_PER_M, CostEstimator

        est = CostEstimator(model="unknown-model-xyz")
        estimate = est.estimate(input_tokens=1_000_000)
        expected = _DEFAULT_INPUT_PER_M
        assert estimate.input_usd == pytest.approx(expected, abs=0.01)

    def test_estimate_messages(self):
        from cutctx.cost_forecast import CostEstimator

        est = CostEstimator(model="gpt-4o")
        msgs = [{"role": "user", "content": "hello world " * 100}]
        estimate = est.estimate_messages(msgs)
        assert estimate.input_tokens > 0
        assert estimate.input_usd > 0


class TestPolicyEngine:
    """Tests for PolicyEngine."""

    def test_default_light_strategy(self):
        from cutctx.cost_forecast import CompressionStrategy, PolicyEngine

        engine = PolicyEngine(model="claude-sonnet-4-5")
        decision = engine.evaluate(budget_remaining_usd=50.0, input_tokens=10_000)
        assert decision.strategy == CompressionStrategy.LIGHT

    def test_budget_critical_emergency(self):
        from cutctx.cost_forecast import CompressionStrategy, PolicyEngine

        engine = PolicyEngine()
        decision = engine.evaluate(budget_remaining_usd=0.30, input_tokens=10_000)
        assert decision.strategy == CompressionStrategy.EMERGENCY
        assert decision.compression_ratio <= 0.20

    def test_budget_low_aggressive(self):
        from cutctx.cost_forecast import CompressionStrategy, PolicyEngine

        engine = PolicyEngine()
        decision = engine.evaluate(budget_remaining_usd=1.50, input_tokens=10_000)
        assert decision.strategy == CompressionStrategy.AGGRESSIVE

    def test_large_context_moderate(self):
        from cutctx.cost_forecast import CompressionStrategy, PolicyEngine

        engine = PolicyEngine()
        decision = engine.evaluate(budget_remaining_usd=50.0, input_tokens=150_000)
        assert decision.strategy == CompressionStrategy.MODERATE

    def test_medium_context_light(self):
        from cutctx.cost_forecast import CompressionStrategy, PolicyEngine

        engine = PolicyEngine()
        decision = engine.evaluate(budget_remaining_usd=50.0, input_tokens=75_000)
        assert decision.strategy == CompressionStrategy.LIGHT

    def test_budget_priority_over_context(self):
        from cutctx.cost_forecast import CompressionStrategy, PolicyEngine

        engine = PolicyEngine()
        # Large context but low budget — budget rule wins (higher priority)
        decision = engine.evaluate(budget_remaining_usd=1.0, input_tokens=150_000)
        assert decision.strategy == CompressionStrategy.AGGRESSIVE

    def test_evaluate_with_messages(self):
        from cutctx.cost_forecast import PolicyEngine

        engine = PolicyEngine()
        msgs = [{"role": "user", "content": "hello " * 5000}]
        decision = engine.evaluate(messages=msgs, budget_remaining_usd=50.0)
        assert decision.strategy is not None

    def test_estimated_savings(self):
        from cutctx.cost_forecast import PolicyEngine

        engine = PolicyEngine()
        decision = engine.evaluate(budget_remaining_usd=1.0, input_tokens=50_000)
        assert decision.estimated_savings_usd >= 0


class TestSessionCostTracker:
    """Tests for SessionCostTracker."""

    def test_record_and_snapshot(self):
        from cutctx.cost_forecast import SessionCostTracker

        tracker = SessionCostTracker(model="claude-sonnet-4-5")
        tracker.record_request(input_tokens=10_000, output_tokens=1_000)

        snap = tracker.snapshot()
        assert snap.request_count == 1
        assert snap.total_input_usd > 0
        assert snap.total_output_usd > 0

    def test_compression_savings(self):
        from cutctx.cost_forecast import SessionCostTracker

        tracker = SessionCostTracker(model="claude-sonnet-4-5")
        tracker.record_request(
            input_tokens=10_000,
            output_tokens=1_000,
            compressed_input_tokens=5_000,
        )

        snap = tracker.snapshot()
        assert snap.tokens_saved_by_compression == 5_000
        assert snap.usd_saved_by_compression > 0

    def test_budget_tracking(self):
        from cutctx.cost_forecast import SessionCostTracker

        tracker = SessionCostTracker(model="claude-sonnet-4-5", budget_usd=1.0)
        assert not tracker.is_budget_exceeded

        # Record many requests to exceed budget
        for _ in range(100):
            tracker.record_request(input_tokens=100_000, output_tokens=10_000)

        assert tracker.is_budget_exceeded
        snap = tracker.snapshot()
        assert snap.budget_remaining_usd is not None
        assert snap.budget_remaining_usd < 0

    def test_reset(self):
        from cutctx.cost_forecast import SessionCostTracker

        tracker = SessionCostTracker()
        tracker.record_request(input_tokens=10_000)
        assert tracker.snapshot().request_count == 1

        tracker.reset()
        assert tracker.snapshot().request_count == 0


class TestModelPricing:
    """Tests for pricing resolution."""

    def test_all_known_models_resolve(self):
        from cutctx.cost_forecast import MODEL_PRICING, _resolve_model_pricing

        for model in MODEL_PRICING:
            inp, out = _resolve_model_pricing(model)
            assert inp > 0
            assert out > 0

    def test_fuzzy_match(self):
        from cutctx.cost_forecast import _resolve_model_pricing

        # "claude-sonnet-4-5-20250929-extra" should match "claude-sonnet-4-5"
        inp, out = _resolve_model_pricing("claude-sonnet-4-5-20250929-extra")
        assert inp == 3.0  # claude-sonnet-4-5 pricing

    def test_cost_estimate_savings_percent(self):
        from cutctx.cost_forecast import CostEstimator

        est = CostEstimator(model="claude-sonnet-4-5")
        estimate = est.estimate(input_tokens=100_000, compression_ratio=0.5)
        assert estimate.savings_percent == pytest.approx(50.0, abs=1.0)
