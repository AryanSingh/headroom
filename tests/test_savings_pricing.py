import pytest

from cutctx.proxy.savings_pricing import value_tokens_usd
from cutctx.proxy.cost import CostTracker

def test_value_tokens_usd_known_model():
    model = "gpt-4o"  # or similar known model
    tokens = 1000
    
    tracker = CostTracker()
    expected = (tokens * tracker._get_list_price(model)) / 1_000_000
    
    # We should match exactly or within float tolerance
    actual = value_tokens_usd(model, tokens)
    assert actual > 0
    assert abs(actual - expected) < 1e-9


def test_value_tokens_usd_unknown_model():
    actual = value_tokens_usd("unknown-model-1234", 1000)
    assert actual == 0.0


def test_value_tokens_usd_rate_override():
    actual = value_tokens_usd("any-model", 1000, rate_per_million=3.0)
    # (3.0 / 1_000_000) * 1000 = 0.003
    assert abs(actual - 0.003) < 1e-9


def test_value_tokens_usd_zero_or_negative_tokens():
    assert value_tokens_usd("claude-3-5-sonnet-20241022", 0) == 0.0
    assert value_tokens_usd("claude-3-5-sonnet-20241022", -10) == 0.0
