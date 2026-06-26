"""Tests for Agno hooks integration.

Tests cover:
1. CutctxPreHook - Pre-hook for tracking before LLM calls
2. CutctxPostHook - Post-hook for tracking after LLM calls
3. create_cutctx_hooks - Convenience function
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

# Check if Agno is available
try:
    import agno  # noqa: F401

    AGNO_AVAILABLE = True
except ImportError:
    AGNO_AVAILABLE = False

from cutctx import CutctxConfig, CutctxMode

# Skip all tests if Agno not installed
pytestmark = pytest.mark.skipif(not AGNO_AVAILABLE, reason="Agno not installed")


class TestCutctxPreHook:
    """Tests for CutctxPreHook."""

    def test_init_defaults(self):
        """Initialize with default settings."""
        from cutctx.integrations.agno import CutctxPreHook

        hook = CutctxPreHook()

        assert hook.mode == CutctxMode.OPTIMIZE
        assert hook.model == "gpt-4o"
        assert hook.total_tokens_saved == 0
        assert hook.metrics_history == []

    def test_init_with_custom_config(self):
        """Initialize with custom config."""
        from cutctx.integrations.agno import CutctxPreHook

        config = CutctxConfig(default_mode=CutctxMode.AUDIT)
        hook = CutctxPreHook(
            config=config,
            mode=CutctxMode.SIMULATE,
            model="claude-3-5-sonnet-20241022",
        )

        assert hook.config is config
        assert hook.mode == CutctxMode.SIMULATE
        assert hook.model == "claude-3-5-sonnet-20241022"

    def test_call_returns_input_unchanged(self):
        """Hook returns input unchanged (optimization at model level)."""
        from cutctx.integrations.agno import CutctxPreHook

        hook = CutctxPreHook()

        run_input = "Hello, how are you?"
        result = hook(run_input)

        assert result == run_input

    def test_call_tracks_metrics(self):
        """Hook tracks metrics on each call."""
        from cutctx.integrations.agno import CutctxPreHook

        hook = CutctxPreHook()

        hook("First input")
        hook("Second input")

        assert len(hook.metrics_history) == 2
        assert all(m.request_id for m in hook.metrics_history)
        assert all(isinstance(m.timestamp, datetime) for m in hook.metrics_history)

    def test_metrics_history_limited(self):
        """Metrics history is limited to 100 entries."""
        from cutctx.integrations.agno import CutctxPreHook

        hook = CutctxPreHook()

        # Call 150 times
        for i in range(150):
            hook(f"Input {i}")

        assert len(hook.metrics_history) == 100

    def test_get_savings_summary_empty(self):
        """get_savings_summary with no history."""
        from cutctx.integrations.agno import CutctxPreHook

        hook = CutctxPreHook()
        summary = hook.get_savings_summary()

        assert summary["total_requests"] == 0
        assert summary["total_tokens_saved"] == 0
        assert summary["average_savings_percent"] == 0

    def test_get_savings_summary_with_data(self):
        """get_savings_summary with metrics."""
        from cutctx.integrations.agno import CutctxPreHook

        hook = CutctxPreHook()

        # Make some calls
        hook("Input 1")
        hook("Input 2")

        summary = hook.get_savings_summary()

        assert summary["total_requests"] == 2
        # Pre-hook doesn't do actual optimization, so tokens_saved is 0
        assert summary["total_tokens_saved"] == 0


class TestCutctxPostHook:
    """Tests for CutctxPostHook."""

    def test_init_defaults(self):
        """Initialize with default settings."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook()

        assert hook.log_level == "INFO"
        assert hook.token_alert_threshold is None
        assert hook.total_requests == 0
        assert hook.alerts == []

    def test_init_with_threshold(self):
        """Initialize with alert threshold."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook(
            log_level="DEBUG",
            token_alert_threshold=10000,
        )

        assert hook.log_level == "DEBUG"
        assert hook.token_alert_threshold == 10000

    def test_call_returns_output_unchanged(self):
        """Hook returns output unchanged."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook()

        output = MagicMock()
        output.content = "Hello!"
        result = hook(output)

        assert result is output

    def test_call_tracks_requests(self):
        """Hook tracks requests on each call."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook()

        output1 = MagicMock()
        output1.content = "First response"
        output2 = MagicMock()
        output2.content = "Second response"

        hook(output1)
        hook(output2)

        assert hook.total_requests == 2

    def test_call_extracts_token_metrics(self):
        """Hook extracts token metrics from response."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook()

        output = MagicMock()
        output.content = "Response"
        output.metrics = MagicMock()
        output.metrics.input_tokens = 50
        output.metrics.output_tokens = 20
        output.metrics.total_tokens = 70

        hook(output)

        assert hook._requests[0]["input_tokens"] == 50
        assert hook._requests[0]["output_tokens"] == 20
        assert hook._requests[0]["total_tokens"] == 70

    def test_call_triggers_alert(self):
        """Hook triggers alert when threshold exceeded."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook(token_alert_threshold=50)

        output = MagicMock()
        output.content = "Response"
        output.metrics = MagicMock()
        output.metrics.total_tokens = 100  # Exceeds threshold

        hook(output)

        assert len(hook.alerts) == 1
        assert "Token alert" in hook.alerts[0]
        assert "100" in hook.alerts[0]

    def test_call_no_alert_below_threshold(self):
        """No alert when tokens below threshold."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook(token_alert_threshold=100)

        output = MagicMock()
        output.content = "Response"
        output.metrics = MagicMock()
        output.metrics.total_tokens = 50  # Below threshold

        hook(output)

        assert len(hook.alerts) == 0

    def test_requests_limited(self):
        """Request history is limited to 1000 entries."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook()

        # Call 1500 times
        for i in range(1500):
            output = MagicMock()
            output.content = f"Response {i}"
            hook(output)

        assert len(hook._requests) == 1000

    def test_get_summary_empty(self):
        """get_summary with no requests."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook()
        summary = hook.get_summary()

        assert summary["total_requests"] == 0
        assert summary["total_tokens"] == 0
        assert summary["alerts"] == 0

    def test_get_summary_with_data(self):
        """get_summary with requests."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook()

        # Add some requests directly
        hook._requests = [
            {"total_tokens": 100},
            {"total_tokens": 200},
            {"total_tokens": 50},
        ]

        summary = hook.get_summary()

        assert summary["total_requests"] == 3
        assert summary["total_tokens"] == 350
        assert summary["average_tokens"] == 350 / 3

    def test_reset(self):
        """reset() clears all state."""
        from cutctx.integrations.agno import CutctxPostHook

        hook = CutctxPostHook()

        # Add some state
        hook._requests = [{"test": 1}]
        hook._alerts = ["alert"]

        hook.reset()

        assert hook._requests == []
        assert hook._alerts == []


class TestCreateCutctxHooks:
    """Tests for create_cutctx_hooks convenience function."""

    def test_returns_tuple(self):
        """Returns tuple of (pre_hook, post_hook)."""
        from cutctx.integrations.agno import (
            CutctxPostHook,
            CutctxPreHook,
            create_cutctx_hooks,
        )

        pre_hook, post_hook = create_cutctx_hooks()

        assert isinstance(pre_hook, CutctxPreHook)
        assert isinstance(post_hook, CutctxPostHook)

    def test_passes_config_to_pre_hook(self):
        """Passes config to pre_hook."""
        from cutctx.integrations.agno import create_cutctx_hooks

        config = CutctxConfig(default_mode=CutctxMode.AUDIT)
        pre_hook, _ = create_cutctx_hooks(config=config)

        assert pre_hook.config is config

    def test_passes_mode_to_pre_hook(self):
        """Passes mode to pre_hook."""
        from cutctx.integrations.agno import create_cutctx_hooks

        pre_hook, _ = create_cutctx_hooks(mode=CutctxMode.SIMULATE)

        assert pre_hook.mode == CutctxMode.SIMULATE

    def test_passes_model_to_pre_hook(self):
        """Passes model to pre_hook."""
        from cutctx.integrations.agno import create_cutctx_hooks

        pre_hook, _ = create_cutctx_hooks(model="claude-3-5-sonnet-20241022")

        assert pre_hook.model == "claude-3-5-sonnet-20241022"

    def test_passes_log_level_to_post_hook(self):
        """Passes log_level to post_hook."""
        from cutctx.integrations.agno import create_cutctx_hooks

        _, post_hook = create_cutctx_hooks(log_level="DEBUG")

        assert post_hook.log_level == "DEBUG"

    def test_passes_threshold_to_post_hook(self):
        """Passes token_alert_threshold to post_hook."""
        from cutctx.integrations.agno import create_cutctx_hooks

        _, post_hook = create_cutctx_hooks(token_alert_threshold=5000)

        assert post_hook.token_alert_threshold == 5000

    def test_all_parameters(self):
        """Test with all parameters."""
        from cutctx.integrations.agno import create_cutctx_hooks

        config = CutctxConfig()
        pre_hook, post_hook = create_cutctx_hooks(
            config=config,
            mode=CutctxMode.AUDIT,
            model="gpt-4-turbo",
            log_level="WARNING",
            token_alert_threshold=8000,
        )

        assert pre_hook.config is config
        assert pre_hook.mode == CutctxMode.AUDIT
        assert pre_hook.model == "gpt-4-turbo"
        assert post_hook.log_level == "WARNING"
        assert post_hook.token_alert_threshold == 8000
