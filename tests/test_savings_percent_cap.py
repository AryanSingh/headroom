from datetime import datetime, timezone

import pytest

from cutctx.proxy.savings_tracker import SavingsTracker


def test_savings_percent_capped_at_100_when_output_saved(tmp_path):
    """
    Test that savings_percent calculation properly handles cases where
    tokens_saved > total_input_tokens (e.g. from semantic cache hits
    saving output tokens as well), capping the percentage at 100%.
    Regression test for the issue where Active Compression hit 292.8%.
    """
    db_path = tmp_path / "savings.json"
    tracker = SavingsTracker(db_path)

    # Simulate a request where the input is 5000 tokens,
    # but the cache hit saved 5000 input + 10000 output = 15000 tokens.
    tracker.record_request(
        model="claude-3-sonnet",
        input_tokens=5000,
        tokens_saved=15000,
        cache_read_tokens=5000,
        timestamp=datetime.now(timezone.utc),
    )

    # Fetch current session stats
    stats = tracker.stats_preview()
    display_session = stats.get("display_session", {})

    savings_percent = display_session.get("savings_percent")

    # Math: tokens_saved / max(total_input_tokens, tokens_saved) * 100
    # 15000 / max(5000, 15000) * 100 = 100.0%
    assert savings_percent == 100.0, f"Expected 100.0%, got {savings_percent}%"


def test_savings_percent_normal_compression(tmp_path):
    """
    Test that savings_percent is calculated correctly for normal
    compression where tokens_saved < total_input_tokens.
    """
    db_path = tmp_path / "savings.json"
    tracker = SavingsTracker(db_path)

    # Compress 1000 tokens to 500 tokens. Saved 500.
    tracker.record_request(
        model="claude-3-sonnet",
        input_tokens=1000,
        tokens_saved=500,
        timestamp=datetime.now(timezone.utc),
    )

    stats = tracker.stats_preview()
    display_session = stats.get("display_session", {})

    savings_percent = display_session.get("savings_percent")

    # Math: 500 / max(1000, 500) * 100 = 50.0%
    assert savings_percent == 50.0, f"Expected 50.0%, got {savings_percent}%"
