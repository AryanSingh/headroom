"""Fixtures for SQLite storage tests."""

from datetime import datetime

import pytest

from cutctx.config import RequestMetrics


@pytest.fixture
def temp_sqlite_db(tmp_path):
    """Return a path string for a temporary SQLite database file."""
    return str(tmp_path / "test.db")


@pytest.fixture
def sample_request_metrics():
    """Return a canonical RequestMetrics instance for testing."""
    return RequestMetrics(
        request_id="test-req-123",
        timestamp=datetime.now(),
        model="gpt-4o",
        stream=False,
        mode="audit",
        tokens_input_before=3000,
        tokens_input_after=2500,
        tokens_output=500,
        block_breakdown={"system": 400, "user": 2000, "assistant": 600},
        waste_signals={"json_bloat": 50, "redundant_system": 30},
        stable_prefix_hash="abc123",
        cache_alignment_score=85.0,
        cached_tokens=200,
        transforms_applied=["ContentRouter", "TokenBuddy"],
        tool_units_dropped=1,
        turns_dropped=0,
        messages_hash="def456",
    )
