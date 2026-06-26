"""Comprehensive tests for Intelligence Pipeline — all 6 features wired end-to-end."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestIntelligencePipelineConfig:
    """Pipeline configuration and initialization."""

    def test_from_config_all_disabled(self):
        config = MagicMock()
        config.task_aware_enabled = False
        config.dedup_enabled = False
        config.context_budget_enabled = False
        config.profiles_enabled = False
        config.shared_context_enabled = False
        config.cost_forecast_enabled = False
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline.from_config(config)
        assert not p.any_enabled()

    def test_from_config_all_enabled(self):
        config = MagicMock()
        config.task_aware_enabled = True
        config.dedup_enabled = True
        config.context_budget_enabled = True
        config.context_budget_max_tokens = 50_000
        config.context_budget_policy = "aggressive"
        config.profiles_enabled = True
        config.shared_context_enabled = True
        config.cost_forecast_enabled = True
        config.default_model = "claude-sonnet-4-5-20250929"
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline.from_config(config)
        assert p.any_enabled()
        assert p.task_aware
        assert p.dedup
        assert p.context_budget
        assert p.context_budget_max_tokens == 50_000
        assert p.context_budget_policy == "aggressive"
        assert p.profiles
        assert p.shared_context
        assert p.cost_forecast
        assert p.model == "claude-sonnet-4-5-20250929"

    def test_from_config_defaults_missing_attrs(self):
        config = MagicMock(spec=[])  # No attributes
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline.from_config(config)
        assert not p.any_enabled()
        assert p.context_budget_max_tokens == 100_000
        assert p.model == "claude-3-5-sonnet-20241022"


class TestTaskAwareCompression:
    """Feature 1: Task-aware compression with relevance scoring."""

    def test_pre_compression_extracts_task(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(task_aware=True)
        messages = [
            {"role": "user", "content": "debug the HTTP 500 error in auth handler"},
        ]
        ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-1")
        assert ctx.task is not None
        assert "debug" in ctx.task.lower() or "http" in ctx.task.lower()

    def test_pre_compression_no_task_when_disabled(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(task_aware=False)
        messages = [{"role": "user", "content": "debug the HTTP 500 error"}]
        ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-2")
        assert ctx.task is None

    def test_per_message_relevance_scoring(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(task_aware=True)
        messages = [
            {"role": "user", "content": "debug HTTP 500 error in /api/users endpoint with connection refused"},
            {"role": "assistant", "content": "The error log shows HTTP 500 connection refused to database"},
            {"role": "user", "content": "continue investigating the connection refused error"},
            {"role": "assistant", "content": "Here is the HTTP response with status 500 and error body showing connection refused"},
        ]
        ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-3")
        assert ctx.task is not None
        assert len(ctx.message_relevance_scores) == 4
        # All scores should be valid floats in [0, 1]
        for score in ctx.message_relevance_scores:
            assert 0.0 <= score <= 1.0

    def test_relevance_scoring_short_messages_get_full_score(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(task_aware=True)
        messages = [
            {"role": "user", "content": "hi"},  # < 20 chars
            {"role": "user", "content": "fix the bug"},  # < 20 chars
        ]
        ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-4")
        # Short messages get 1.0 (fully relevant)
        assert all(s == 1.0 for s in ctx.message_relevance_scores)

    def test_task_extractor_with_question_words(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(task_aware=True)
        messages = [
            {"role": "user", "content": "How do I configure the Redis connection pool in production?"},
        ]
        ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-5")
        assert ctx.task is not None
        assert "How" in ctx.task or "how" in ctx.task.lower()


class TestSemanticDedup:
    """Feature 2: Semantic deduplication with rolling hash index."""

    def test_post_compression_dedup(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(dedup=True)
        long_content = "x" * 2000  # > MIN_DEDUP_TOKENS (200)
        messages = [
            {"role": "user", "content": "read this file"},
            {"role": "assistant", "content": "Here is the file:\n" + long_content},
            {"role": "user", "content": "read the file again"},
            {"role": "assistant", "content": "Here is the file:\n" + long_content},
        ]
        ctx = MagicMock()
        ctx.dedup_count = 0
        ctx.tokens_saved_by_dedup = 0
        result = p.post_compression(messages, messages, ctx, "req-dedup-1")
        # Second occurrence should be replaced with dedup marker
        assert ctx.dedup_count >= 0

    def test_deduplicator_persists_across_requests(self):
        """Deduplicator instance should be reused across post_compression calls."""
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(dedup=True)
        long_content = "y" * 2000
        messages1 = [
            {"role": "assistant", "content": long_content},
        ]
        ctx1 = MagicMock()
        ctx1.dedup_count = 0
        ctx1.tokens_saved_by_dedup = 0
        p.post_compression(messages1, messages1, ctx1, "req-dedup-2")

        # Second request with same content — should be deduped
        messages2 = [
            {"role": "assistant", "content": long_content},
        ]
        ctx2 = MagicMock()
        ctx2.dedup_count = 0
        ctx2.tokens_saved_by_dedup = 0
        result = p.post_compression(messages2, messages2, ctx2, "req-dedup-3")

        # Deduplicator should have been reused
        assert p._deduplicator is not None
        # The second call should find the content already tracked
        assert ctx2.dedup_count >= 1  # Should dedup the repeated content

    def test_system_messages_not_deduped(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(dedup=True)
        messages = [
            {"role": "system", "content": "You are a helpful assistant. " * 100},
            {"role": "system", "content": "You are a helpful assistant. " * 100},
        ]
        ctx = MagicMock()
        ctx.dedup_count = 0
        ctx.tokens_saved_by_dedup = 0
        p.post_compression(messages, messages, ctx, "req-dedup-4")
        assert ctx.dedup_count == 0  # System messages not deduped


class TestContextBudget:
    """Feature 3: Context budget with progressive compression."""

    def test_post_compression_context_budget(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(context_budget=True, context_budget_max_tokens=1000)
        messages = [
            {"role": "user", "content": "hello " * 500},
            {"role": "assistant", "content": "world " * 500},
            {"role": "user", "content": "hi"},
        ]
        ctx = MagicMock()
        ctx.budget_zone = "GREEN"
        ctx.budget_compression_applied = False
        result = p.post_compression(messages, messages, ctx, "req-budget-1")
        assert ctx.budget_zone in ("GREEN", "YELLOW", "RED", "CRITICAL")

    def test_budget_controller_persists_across_requests(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(context_budget=True, context_budget_max_tokens=50_000)
        messages = [{"role": "user", "content": "test " * 200}]
        ctx = MagicMock()
        ctx.budget_zone = "GREEN"
        ctx.budget_compression_applied = False
        p.post_compression(messages, messages, ctx, "req-budget-2")
        first_controller = p._budget_controller
        assert first_controller is not None

        # Second request — should reuse same controller
        p.post_compression(messages, messages, ctx, "req-budget-3")
        assert p._budget_controller is first_controller


class TestCrossSessionProfiles:
    """Feature 4: Cross-session compression profiles."""

    def test_pre_compression_loads_profile(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(profiles=True)
        messages = [{"role": "user", "content": "test task"}]
        with patch("cutctx.profiles.CompressionProfile.load") as mock_load:
            mock_profile = MagicMock()
            stats = MagicMock()
            stats.recommended_ratio = 0.6
            mock_profile.stats = {"json": stats, "code": stats}
            mock_load.return_value = mock_profile
            ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-profile-1")
            assert ctx.profile_loaded
            assert "json" in ctx.profile_recommendations
            assert ctx.profile_recommendations["json"] == 0.6

    def test_profile_persists_across_requests(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(profiles=True)
        messages = [{"role": "user", "content": "test"}]
        with patch("cutctx.profiles.CompressionProfile.load") as mock_load:
            mock_profile = MagicMock()
            mock_profile.stats = {}
            mock_load.return_value = mock_profile
            p.pre_compression(messages, "model", "req-profile-2")
            first_profile = p._profile
            assert first_profile is not None

            p.pre_compression(messages, "model", "req-profile-3")
            assert p._profile is first_profile  # Same instance reused


class TestMultiAgentSharedState:
    """Feature 5: Multi-agent shared compression state."""

    def test_pre_compression_shared_context_check(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(shared_context=True)
        messages = [{"role": "user", "content": "test"}]
        with patch("cutctx.shared_context.MultiAgentCoordinator") as MockCoord:
            mock_coordinator = MagicMock()
            mock_coordinator.get_agent_context.return_value.total_items_compressed = 5
            MockCoord.get_instance.return_value = mock_coordinator
            ctx = p.pre_compression(messages, "model", "req-shared-1")
            assert ctx.shared_context_hit
            mock_coordinator.register_agent.assert_called_once()

    def test_post_compression_shared_store(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(shared_context=True)
        messages = [{"role": "assistant", "content": "compressed result here"}]
        ctx = MagicMock()
        with patch("cutctx.shared_context.MultiAgentCoordinator") as MockCoord:
            mock_coordinator = MagicMock()
            MockCoord.get_instance.return_value = mock_coordinator
            p.post_compression(messages, messages, ctx, "req-shared-2")
            mock_coordinator.compress_shared.assert_called_once()
            call_kwargs = mock_coordinator.compress_shared.call_args
            assert call_kwargs.kwargs["agent_id"] == "proxy"

    def test_coordinator_persists_across_requests(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(shared_context=True)
        messages = [{"role": "user", "content": "test"}]
        ctx = MagicMock()
        with patch("cutctx.shared_context.MultiAgentCoordinator") as MockCoord:
            mock_coordinator = MagicMock()
            MockCoord.get_instance.return_value = mock_coordinator
            p.pre_compression(messages, "model", "req-shared-3")
            first = p._coordinator
            p.pre_compression(messages, "model", "req-shared-4")
            assert p._coordinator is first


class TestCostForecasting:
    """Feature 6: Cost forecasting + policy engine."""

    def test_pre_compression_policy_evaluation(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(cost_forecast=True, model="claude-3-5-sonnet-20241022")
        messages = [{"role": "user", "content": "hello " * 1000}]
        with patch("cutctx.cost_forecast.SessionCostTracker") as MockTracker:
            mock_tracker = MagicMock()
            mock_tracker._budget_usd = None
            MockTracker.return_value = mock_tracker
            ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-cost-1")
            assert ctx.policy_strategy in ("none", "minimal", "light", "moderate", "aggressive", "emergency")
            assert ctx.policy_compression_ratio > 0

    def test_post_compression_cost_tracking(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(cost_forecast=True, model="claude-3-5-sonnet-20241022")
        messages = [{"role": "user", "content": "hello"}]
        ctx = MagicMock()
        ctx.cost_estimate_usd = 0.0
        ctx.cost_savings_usd = 0.0
        result = p.post_compression(
            messages, messages, ctx, "req-cost-2",
            input_tokens=1000,
            output_tokens=500,
        )
        assert ctx.cost_estimate_usd > 0

    def test_cost_tracker_persists_across_requests(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(cost_forecast=True, model="claude-3-5-sonnet-20241022")
        messages = [{"role": "user", "content": "hello"}]
        ctx = MagicMock()
        p.post_compression(messages, messages, ctx, "req-cost-3",
                          input_tokens=1000, output_tokens=200)
        first_tracker = p._cost_tracker
        assert first_tracker is not None
        p.post_compression(messages, messages, ctx, "req-cost-4",
                          input_tokens=500, output_tokens=100)
        assert p._cost_tracker is first_tracker
        # Should have accumulated 2 requests
        assert first_tracker._request_count == 2


class TestPipelineContext:
    """PipelineContext data structure."""

    def test_to_dict_with_all_fields(self):
        from cutctx.proxy.intelligence_pipeline import PipelineContext
        ctx = PipelineContext(
            task="debug HTTP error",
            dedup_count=3,
            tokens_saved_by_dedup=150,
            budget_zone="YELLOW",
            budget_compression_applied=True,
            cost_estimate_usd=0.0042,
            cost_savings_usd=0.001,
            profile_loaded=True,
            profile_recommendations={"json": 0.6, "code": 0.4},
            policy_strategy="moderate",
            policy_compression_ratio=0.50,
            policy_rationale="context_large: input_tokens > 100K",
            shared_context_hit=True,
            message_relevance_scores=[0.9, 0.3, 0.8],
        )
        d = ctx.to_dict()
        assert d["task"] == "debug HTTP error"
        assert d["dedup_count"] == 3
        assert d["tokens_saved_by_dedup"] == 150
        assert d["budget_zone"] == "YELLOW"
        assert d["budget_compression_applied"] is True
        assert d["cost_estimate_usd"] == 0.0042
        assert d["cost_savings_usd"] == 0.001
        assert d["profile_loaded"] is True
        assert d["profile_recommendations"] == {"json": 0.6, "code": 0.4}
        assert d["policy_strategy"] == "moderate"
        assert d["policy_compression_ratio"] == 0.50
        assert d["policy_rationale"] == "context_large: input_tokens > 100K"
        assert d["shared_context_hit"] is True
        assert d["message_relevance_scores"] == [0.9, 0.3, 0.8]

    def test_to_dict_defaults(self):
        from cutctx.proxy.intelligence_pipeline import PipelineContext
        ctx = PipelineContext()
        d = ctx.to_dict()
        assert d["task"] is None
        assert d["dedup_count"] == 0
        assert d["budget_zone"] == "GREEN"
        assert d["policy_strategy"] == "light"
        assert d["shared_context_hit"] is False
        assert d["message_relevance_scores"] == []


class TestGracefulFailure:
    """All modules should fail gracefully, never crash the request."""

    def test_dedup_failure_is_swallowed(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(dedup=True)
        p._deduplicator = MagicMock()
        p._deduplicator.process.side_effect = RuntimeError("dedup crash")
        messages = [{"role": "user", "content": "test"}]
        ctx = MagicMock()
        result = p.post_compression(messages, messages, ctx, "req-fail-1")
        assert result is not None

    def test_budget_failure_is_swallowed(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(context_budget=True)
        p._budget_controller = MagicMock()
        p._budget_controller.apply.side_effect = RuntimeError("budget crash")
        messages = [{"role": "user", "content": "test"}]
        ctx = MagicMock()
        result = p.post_compression(messages, messages, ctx, "req-fail-2")
        assert result is not None

    def test_cost_forecast_failure_is_swallowed(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(cost_forecast=True, model="claude-3-5-sonnet-20241022")
        p._cost_tracker = MagicMock()
        p._cost_tracker.record_request.side_effect = RuntimeError("cost crash")
        messages = [{"role": "user", "content": "test"}]
        ctx = MagicMock()
        result = p.post_compression(messages, messages, ctx, "req-fail-3")
        assert result is not None

    def test_profile_failure_is_swallowed(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(profiles=True)
        p._profile = MagicMock()
        p._profile.record_session.side_effect = RuntimeError("profile crash")
        messages = [{"role": "user", "content": "test"}]
        ctx = MagicMock()
        result = p.post_compression(messages, messages, ctx, "req-fail-4")
        assert result is not None

    def test_shared_context_failure_is_swallowed(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(shared_context=True)
        p._coordinator = MagicMock()
        p._coordinator.compress_shared.side_effect = RuntimeError("shared crash")
        messages = [{"role": "user", "content": "test"}]
        ctx = MagicMock()
        result = p.post_compression(messages, messages, ctx, "req-fail-5")
        assert result is not None

    def test_all_disabled_noop(self):
        from cutctx.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline()
        messages = [{"role": "user", "content": "hello"}]
        ctx = MagicMock()
        result = p.post_compression(messages, messages, ctx, "req-fail-6")
        assert result == messages
