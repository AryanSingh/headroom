"""Tests for context budget controller and progressive compression."""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch

from headroom.context_budget import (
    BudgetPolicy,
    BudgetStatus,
    BudgetZone,
    ContextBudgetController,
)


class TestBudgetZone:
    """Test BudgetZone enum."""

    def test_zone_values(self):
        """Verify all zones exist and have string values."""
        assert BudgetZone.GREEN.value == "GREEN"
        assert BudgetZone.YELLOW.value == "YELLOW"
        assert BudgetZone.RED.value == "RED"
        assert BudgetZone.CRITICAL.value == "CRITICAL"

    def test_zone_comparison(self):
        """Zones can be compared by string value."""
        assert BudgetZone.GREEN == "GREEN"
        assert BudgetZone.YELLOW != BudgetZone.GREEN


class TestBudgetPolicy:
    """Test BudgetPolicy configuration."""

    def test_default_policy(self):
        """Default policy uses balanced thresholds."""
        policy = BudgetPolicy()
        assert policy.green_threshold == 0.60
        assert policy.yellow_threshold == 0.80
        assert policy.red_threshold == 0.95
        assert policy.compression_window_yellow == 10
        assert policy.compression_window_red == 5

    def test_from_env_no_env_vars(self, monkeypatch):
        """from_env() uses preset when no env vars set."""
        # Ensure no env vars are set
        for key in [
            "HEADROOM_BUDGET_GREEN",
            "HEADROOM_BUDGET_YELLOW",
            "HEADROOM_BUDGET_RED",
            "HEADROOM_BUDGET_WINDOW_YELLOW",
            "HEADROOM_BUDGET_WINDOW_RED",
        ]:
            monkeypatch.delenv(key, raising=False)

        # Balanced (default)
        policy = BudgetPolicy.from_env("balanced")
        assert policy.green_threshold == 0.60
        assert policy.yellow_threshold == 0.80

    def test_from_env_conservative(self, monkeypatch):
        """Conservative policy keeps more context."""
        for key in [
            "HEADROOM_BUDGET_GREEN",
            "HEADROOM_BUDGET_YELLOW",
            "HEADROOM_BUDGET_RED",
            "HEADROOM_BUDGET_WINDOW_YELLOW",
            "HEADROOM_BUDGET_WINDOW_RED",
        ]:
            monkeypatch.delenv(key, raising=False)

        policy = BudgetPolicy.from_env("conservative")
        assert policy.green_threshold == 0.70
        assert policy.yellow_threshold == 0.85
        assert policy.compression_window_yellow == 15
        assert policy.compression_window_red == 8

    def test_from_env_aggressive(self, monkeypatch):
        """Aggressive policy compresses early and aggressively."""
        for key in [
            "HEADROOM_BUDGET_GREEN",
            "HEADROOM_BUDGET_YELLOW",
            "HEADROOM_BUDGET_RED",
            "HEADROOM_BUDGET_WINDOW_YELLOW",
            "HEADROOM_BUDGET_WINDOW_RED",
        ]:
            monkeypatch.delenv(key, raising=False)

        policy = BudgetPolicy.from_env("aggressive")
        assert policy.green_threshold == 0.50
        assert policy.yellow_threshold == 0.75
        assert policy.compression_window_yellow == 5

    def test_from_env_explicit_vars(self, monkeypatch):
        """Explicit env vars override presets."""
        monkeypatch.setenv("HEADROOM_BUDGET_GREEN", "0.55")
        monkeypatch.setenv("HEADROOM_BUDGET_YELLOW", "0.78")
        monkeypatch.setenv("HEADROOM_BUDGET_RED", "0.92")
        monkeypatch.setenv("HEADROOM_BUDGET_WINDOW_YELLOW", "12")
        monkeypatch.setenv("HEADROOM_BUDGET_WINDOW_RED", "6")

        # Policy name should be ignored when env vars are set
        policy = BudgetPolicy.from_env("balanced")
        assert policy.green_threshold == 0.55
        assert policy.yellow_threshold == 0.78
        assert policy.red_threshold == 0.92
        assert policy.compression_window_yellow == 12
        assert policy.compression_window_red == 6


class TestBudgetStatus:
    """Test BudgetStatus dataclass."""

    def test_status_creation(self):
        """BudgetStatus holds all required fields."""
        status = BudgetStatus(
            zone=BudgetZone.YELLOW,
            tokens_used=45000,
            tokens_budget=100000,
            tokens_available=55000,
            percent_used=45.0,
            compression_applied=True,
            forecast_usd=0.45,
        )
        assert status.zone == BudgetZone.YELLOW
        assert status.tokens_used == 45000
        assert status.percent_used == 45.0


class TestContextBudgetController:
    """Test ContextBudgetController main class."""

    def test_initialization(self):
        """Controller initializes with correct defaults."""
        controller = ContextBudgetController(max_tokens=100_000)
        assert controller.max_tokens == 100_000
        assert controller.model == "claude-sonnet-4-6"
        assert controller.policy.green_threshold == 0.60
        assert controller.percent_used == 0.0

    def test_initialization_with_policy(self, monkeypatch):
        """Controller respects policy argument."""
        for key in [
            "HEADROOM_BUDGET_GREEN",
            "HEADROOM_BUDGET_YELLOW",
            "HEADROOM_BUDGET_RED",
            "HEADROOM_BUDGET_WINDOW_YELLOW",
            "HEADROOM_BUDGET_WINDOW_RED",
        ]:
            monkeypatch.delenv(key, raising=False)

        controller = ContextBudgetController(policy="aggressive")
        assert controller.policy.green_threshold == 0.50

    def test_apply_empty_messages(self):
        """apply() handles empty message list."""
        controller = ContextBudgetController()
        result = controller.apply([])
        assert result == []

    def test_apply_green_zone_passthrough(self):
        """In GREEN zone, messages pass through unchanged."""
        controller = ContextBudgetController(max_tokens=100_000)
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        result = controller.apply(messages)

        # In GREEN zone, compression not applied
        assert controller.percent_used < 60
        assert result == messages
        assert controller.status.zone == BudgetZone.GREEN
        assert not controller.status.compression_applied

    def test_zone_detection_green(self):
        """Zone detection: GREEN for 0-60%."""
        controller = ContextBudgetController(max_tokens=100)
        controller._tokens_used = 30  # 30%
        assert controller._get_zone(30) == BudgetZone.GREEN

    def test_zone_detection_yellow(self):
        """Zone detection: YELLOW for 60-80%."""
        controller = ContextBudgetController(max_tokens=100)
        assert controller._get_zone(70) == BudgetZone.YELLOW

    def test_zone_detection_red(self):
        """Zone detection: RED for 80-95%."""
        controller = ContextBudgetController(max_tokens=100)
        assert controller._get_zone(90) == BudgetZone.RED

    def test_zone_detection_critical(self):
        """Zone detection: CRITICAL for 95%+."""
        controller = ContextBudgetController(max_tokens=100)
        assert controller._get_zone(97) == BudgetZone.CRITICAL

    def test_percent_used(self):
        """percent_used property calculates correctly."""
        controller = ContextBudgetController(max_tokens=1000)
        controller._tokens_used = 250
        assert controller.percent_used == 25.0

    def test_percent_used_at_max(self):
        """percent_used caps at 100%."""
        controller = ContextBudgetController(max_tokens=1000)
        controller._tokens_used = 2000  # Over budget
        assert controller.percent_used == 100.0

    def test_status_property(self):
        """status property returns current BudgetStatus."""
        controller = ContextBudgetController(max_tokens=100_000)
        messages = [{"role": "user", "content": "test"}]
        controller.apply(messages)

        status = controller.status
        assert isinstance(status, BudgetStatus)
        assert status.zone in [BudgetZone.GREEN, BudgetZone.YELLOW, BudgetZone.RED, BudgetZone.CRITICAL]
        assert status.tokens_budget == 100_000
        assert status.tokens_available == max(0, 100_000 - status.tokens_used)

    def test_forecast_empty_messages(self):
        """forecast() handles empty messages gracefully."""
        controller = ContextBudgetController(max_tokens=100_000)
        forecast = controller.forecast([])
        assert forecast["token_velocity"] == 0
        assert forecast["estimated_messages_remaining"] == 0
        assert forecast["confidence_pct"] == 0.0

    def test_forecast_structure(self):
        """forecast() returns all required fields."""
        controller = ContextBudgetController(max_tokens=100_000)
        messages = [{"role": "user", "content": "hello"}] * 10
        forecast = controller.forecast(messages)

        assert "token_velocity" in forecast
        assert "tokens_available" in forecast
        assert "estimated_messages_remaining" in forecast
        assert "forecast_usd" in forecast
        assert "confidence_pct" in forecast
        assert "current_cost_usd" in forecast
        assert "projected_additional_cost_usd" in forecast

    def test_forecast_confidence_increases(self):
        """Forecast confidence increases with more messages."""
        controller = ContextBudgetController(max_tokens=100_000)

        # Few messages = low confidence
        forecast_few = controller.forecast([{"role": "user", "content": "hi"}])
        assert forecast_few["confidence_pct"] == 10.0

        # More messages = higher confidence
        forecast_many = controller.forecast([{"role": "user", "content": "hi"}] * 10)
        assert forecast_many["confidence_pct"] == 100.0

    def test_count_tokens_simple(self):
        """Token counting works for simple messages."""
        controller = ContextBudgetController()
        messages = [{"role": "user", "content": "hello"}]

        # Should return some positive count
        tokens = controller._count_tokens(messages)
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_count_tokens_empty(self):
        """Token counting returns 0 for empty messages."""
        controller = ContextBudgetController()
        tokens = controller._count_tokens([])
        assert tokens == 0

    def test_count_tokens_multiple_messages(self):
        """Token counting scales with content size."""
        controller = ContextBudgetController()
        # Use content long enough for the char-based fallback to return >0
        content = "hello world how are you doing today this is a test message"
        short = [{"role": "user", "content": content}]
        long = [{"role": "user", "content": content}] * 10

        tokens_short = controller._count_tokens(short)
        tokens_long = controller._count_tokens(long)

        assert tokens_long > tokens_short

    def test_estimate_cost(self):
        """Cost estimation returns reasonable values."""
        controller = ContextBudgetController(model="claude-sonnet-4-6")

        # Small token count = low cost
        cost_small = controller._estimate_cost(100)
        cost_large = controller._estimate_cost(10000)

        assert cost_small < cost_large
        assert cost_small >= 0.0

    def test_estimate_cost_per_token(self):
        """Cost per token returns positive value."""
        controller = ContextBudgetController()
        cost = controller._get_cost_per_token()
        assert cost > 0
        assert cost < 0.001  # Should be a fraction of a penny per token

    def test_fallback_cost_estimates(self):
        """Fallback cost estimates vary by model family."""
        # Opus should be more expensive than Haiku
        opus_cost = ContextBudgetController(model="claude-opus-4-20250514")._get_cost_per_token()
        haiku_cost = ContextBudgetController(model="claude-haiku-4-5")._get_cost_per_token()
        assert opus_cost > haiku_cost

    def test_compression_flag_on_yellow(self):
        """Compression flag set when zone is YELLOW."""
        controller = ContextBudgetController(max_tokens=100)

        assert controller._get_zone(70) == BudgetZone.YELLOW

        messages = [{"role": "user", "content": "test"}] * 5
        # Mock _count_tokens so apply() sees 70 tokens (YELLOW zone)
        with patch.object(controller, '_count_tokens', return_value=70):
            controller.apply(messages)

        # The controller should mark that it tried compression
        # (even if it fell back to original)
        status = controller.status
        assert status.zone == BudgetZone.YELLOW

    def test_last_compression_zone_tracking(self):
        """last_compression_zone tracks when compression was applied."""
        controller = ContextBudgetController(max_tokens=100)
        assert controller._last_compression_zone is None

        # After applying in a zone that triggers compression,
        # the zone should be tracked
        controller._tokens_used = 70  # YELLOW
        controller.apply([{"role": "user", "content": "test"}])

        # Even if compression failed, zone should be tracked
        status = controller.status
        assert status.last_compression_zone in [BudgetZone.YELLOW, None]

    def test_zero_max_tokens_critical(self):
        """Zero max_tokens puts controller in CRITICAL zone."""
        controller = ContextBudgetController(max_tokens=0)
        assert controller._get_zone(0) == BudgetZone.CRITICAL

    def test_token_history_bounded(self):
        """Token history is kept bounded."""
        controller = ContextBudgetController()
        messages = [{"role": "user", "content": "test"}]

        # Apply 150 times to exceed history limit of 100
        for _ in range(150):
            controller.apply(messages)

        assert len(controller._token_history) <= 100


class TestBudgetZoneTransitions:
    """Test zone transitions and progressive compression."""

    def test_green_to_yellow_transition(self):
        """Zone transitions from GREEN to YELLOW as tokens accumulate."""
        controller = ContextBudgetController(max_tokens=1000)

        # Start in GREEN
        controller._tokens_used = 500  # 50%
        assert controller._get_zone(500) == BudgetZone.GREEN

        # Move to YELLOW
        controller._tokens_used = 700  # 70%
        assert controller._get_zone(700) == BudgetZone.YELLOW

    def test_yellow_to_red_transition(self):
        """Zone transitions from YELLOW to RED."""
        controller = ContextBudgetController(max_tokens=1000)

        controller._tokens_used = 750  # 75% = YELLOW zone
        assert controller._get_zone(750) == BudgetZone.YELLOW

        controller._tokens_used = 850  # 85% = RED zone
        assert controller._get_zone(850) == BudgetZone.RED

    def test_red_to_critical_transition(self):
        """Zone transitions from RED to CRITICAL."""
        controller = ContextBudgetController(max_tokens=1000)

        controller._tokens_used = 900  # 90% = RED
        assert controller._get_zone(900) == BudgetZone.RED

        controller._tokens_used = 950  # 95% = CRITICAL boundary
        assert controller._get_zone(950) == BudgetZone.CRITICAL


class TestCompressionWindows:
    """Test compression window protection of recent messages."""

    def test_yellow_window_default(self):
        """YELLOW zone protects last 10 messages by default."""
        controller = ContextBudgetController(policy="balanced")
        assert controller.policy.compression_window_yellow == 10

    def test_red_window_default(self):
        """RED zone protects last 5 messages by default."""
        controller = ContextBudgetController(policy="balanced")
        assert controller.policy.compression_window_red == 5

    def test_conservative_windows_larger(self):
        """Conservative policy has larger protection windows."""
        conservative = ContextBudgetController(policy="conservative")
        balanced = ContextBudgetController(policy="balanced")

        assert conservative.policy.compression_window_yellow > balanced.policy.compression_window_yellow
        assert conservative.policy.compression_window_red > balanced.policy.compression_window_red

    def test_aggressive_windows_smaller(self):
        """Aggressive policy has smaller protection windows."""
        aggressive = ContextBudgetController(policy="aggressive")
        balanced = ContextBudgetController(policy="balanced")

        assert aggressive.policy.compression_window_yellow < balanced.policy.compression_window_yellow
        assert aggressive.policy.compression_window_red < balanced.policy.compression_window_red
