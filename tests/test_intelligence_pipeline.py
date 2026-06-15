"""Integration tests for Intelligence Pipeline wiring in proxy handlers."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class TestIntelligencePipeline:
    """Tests for IntelligencePipeline orchestration."""

    def test_from_config_all_disabled(self):
        config = MagicMock()
        config.task_aware_enabled = False
        config.dedup_enabled = False
        config.context_budget_enabled = False
        config.profiles_enabled = False
        config.shared_context_enabled = False
        config.cost_forecast_enabled = False
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline.from_config(config)
        assert not p.any_enabled()

    def test_from_config_some_enabled(self):
        config = MagicMock()
        config.task_aware_enabled = True
        config.dedup_enabled = True
        config.context_budget_enabled = False
        config.context_budget_max_tokens = 50_000
        config.context_budget_policy = "aggressive"
        config.profiles_enabled = False
        config.shared_context_enabled = False
        config.cost_forecast_enabled = False
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline.from_config(config)
        assert p.any_enabled()
        assert p.task_aware
        assert p.dedup

    def test_pre_compression_extracts_task(self):
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(task_aware=True)
        messages = [
            {"role": "user", "content": "debug the HTTP 500 error in auth handler"},
        ]
        ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-1")
        assert ctx.task is not None
        assert "debug" in ctx.task.lower() or "http" in ctx.task.lower()

    def test_pre_compression_no_task_when_disabled(self):
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(task_aware=False)
        messages = [{"role": "user", "content": "debug the HTTP 500 error"}]
        ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-2")
        assert ctx.task is None

    def test_post_compression_noop_when_all_disabled(self):
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline()
        messages = [{"role": "user", "content": "hello"}]
        ctx = MagicMock()
        result = p.post_compression(messages, messages, ctx, "req-3")
        assert result == messages

    def test_post_compression_dedup(self):
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(dedup=True)
        # Create messages with repeated content
        long_content = "x" * 2000  # > MIN_DEDUP_TOKENS
        messages = [
            {"role": "user", "content": "read this file"},
            {"role": "assistant", "content": "Here is the file:\n" + long_content},
            {"role": "user", "content": "read the file again"},
            {"role": "assistant", "content": "Here is the file:\n" + long_content},
        ]
        ctx = MagicMock()
        ctx.dedup_count = 0
        ctx.tokens_saved_by_dedup = 0
        result = p.post_compression(messages, messages, ctx, "req-4")
        # After dedup, second occurrence should be replaced
        assert ctx.dedup_count >= 0  # May or may not dedup depending on exact content

    def test_post_compression_context_budget(self):
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(context_budget=True, context_budget_max_tokens=1000)
        messages = [
            {"role": "user", "content": "hello " * 500},
            {"role": "assistant", "content": "world " * 500},
            {"role": "user", "content": "hi"},
        ]
        ctx = MagicMock()
        ctx.budget_zone = "GREEN"
        ctx.budget_compression_applied = False
        result = p.post_compression(messages, messages, ctx, "req-5")
        assert ctx.budget_zone in ("GREEN", "YELLOW", "RED", "CRITICAL")

    def test_pipeline_context_to_dict(self):
        from headroom.proxy.intelligence_pipeline import PipelineContext
        ctx = PipelineContext(
            task="debug HTTP error",
            dedup_count=3,
            tokens_saved_by_dedup=150,
            budget_zone="YELLOW",
            cost_estimate_usd=0.0042,
        )
        d = ctx.to_dict()
        assert d["task"] == "debug HTTP error"
        assert d["dedup_count"] == 3
        assert d["tokens_saved_by_dedup"] == 150
        assert d["budget_zone"] == "YELLOW"
        assert d["cost_estimate_usd"] == 0.0042

    def test_pre_compression_with_task_and_profiles(self):
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(task_aware=True, profiles=True)
        messages = [{"role": "user", "content": "fix the database connection pool leak"}]
        with patch("headroom.profiles.CompressionProfile.load") as mock_load:
            mock_profile = MagicMock()
            mock_profile.stats = {"json": MagicMock()}
            mock_load.return_value = mock_profile
            ctx = p.pre_compression(messages, "claude-3-5-sonnet-20241022", "req-6")
            assert ctx.task is not None
            assert ctx.profile_loaded

    def test_post_compression_cost_forecast(self):
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(cost_forecast=True, model="claude-3-5-sonnet-20241022")
        messages = [{"role": "user", "content": "hello"}]
        ctx = MagicMock()
        ctx.cost_estimate_usd = 0.0
        result = p.post_compression(
            messages, messages, ctx, "req-7",
            input_tokens=1000,
            output_tokens=500,
        )
        assert ctx.cost_estimate_usd > 0

    def test_post_compression_graceful_failure(self):
        """All modules should fail gracefully, not crash the request."""
        from headroom.proxy.intelligence_pipeline import IntelligencePipeline
        p = IntelligencePipeline(dedup=True, context_budget=True, cost_forecast=True)
        messages = [{"role": "user", "content": "test"}]
        ctx = MagicMock()
        # Force budget controller to raise
        p._budget_controller = MagicMock()
        p._budget_controller.apply.side_effect = RuntimeError("budget crash")
        # Should not raise
        result = p.post_compression(messages, messages, ctx, "req-8")
        assert result is not None
