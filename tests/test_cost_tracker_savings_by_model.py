from cutctx.proxy.cost import CostTracker


def test_cost_tracker_savings_by_model():
    """TDD test: verify that CostTracker accurately tracks savings by model."""
    tracker = CostTracker()

    # Simulate some traffic
    tracker.record_tokens(
        "claude-3-opus-20240229",
        tokens_saved=1000,
        tokens_sent=5000,
        cache_read_tokens=1000,
        cache_write_tokens=0,
        uncached_tokens=4000,
    )
    tracker.record_tokens(
        "claude-3-opus-20240229",
        tokens_saved=2000,
        tokens_sent=1000,
        cache_read_tokens=0,
        cache_write_tokens=0,
        uncached_tokens=1000,
    )
    tracker.record_tokens(
        "gpt-4o",
        tokens_saved=5000,
        tokens_sent=2000,
        cache_read_tokens=0,
        cache_write_tokens=0,
        uncached_tokens=2000,
    )

    stats = tracker.stats()
    per_model = stats.get("per_model", {})

    # Check that both models exist in per_model
    assert "claude-3-opus-20240229" in per_model
    assert "gpt-4o" in per_model

    # Check that tokens_saved are aggregated correctly
    assert per_model["claude-3-opus-20240229"]["tokens_saved"] == 3000
    assert per_model["gpt-4o"]["tokens_saved"] == 5000

    # Check that savings_usd is populated and non-zero
    assert "savings_usd" in per_model["claude-3-opus-20240229"]
    assert per_model["claude-3-opus-20240229"]["savings_usd"] > 0.0

    assert "savings_usd" in per_model["gpt-4o"]
    assert per_model["gpt-4o"]["savings_usd"] > 0.0
