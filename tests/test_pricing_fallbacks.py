"""Regression tests for the curated pricing fallback path.

LiteLLM remains the primary runtime source. These tests cover only the
fail-closed behavior used when LiteLLM cannot price a request.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from cutctx.cost_forecast import CostEstimator, _resolve_model_pricing
from cutctx.pricing.anthropic_prices import ANTHROPIC_PRICES
from cutctx.pricing.anthropic_prices import LAST_UPDATED as ANTHROPIC_DATE
from cutctx.pricing.litellm_pricing import get_model_pricing
from cutctx.pricing.openai_prices import LAST_UPDATED as OPENAI_DATE
from cutctx.pricing.openai_prices import OPENAI_PRICES
from cutctx.providers.anthropic import AnthropicProvider
from cutctx.providers.google import GoogleProvider
from cutctx.providers.openai import OpenAIProvider, _check_pricing_staleness


def test_curated_prices_are_verified_on_the_current_audit_date() -> None:
    assert OPENAI_DATE == date(2026, 7, 16)
    assert ANTHROPIC_DATE == date(2026, 7, 16)
    assert _check_pricing_staleness() is None


def test_curated_tables_include_supported_current_models() -> None:
    assert OPENAI_PRICES["gpt-5.4"].input_per_1m == 2.50
    assert OPENAI_PRICES["gpt-5.4"].output_per_1m == 15.00
    assert OPENAI_PRICES["gpt-5.4-mini"].input_per_1m == 0.75
    assert OPENAI_PRICES["gpt-5.4-mini"].output_per_1m == 4.50
    assert OPENAI_PRICES["gpt-5.4-nano"].input_per_1m == 0.20
    assert OPENAI_PRICES["gpt-5.4-nano"].output_per_1m == 1.25
    assert OPENAI_PRICES["o1-mini"].input_per_1m == 1.10
    assert OPENAI_PRICES["o3"].input_per_1m == 2.00
    assert OPENAI_PRICES["o3"].output_per_1m == 8.00

    assert ANTHROPIC_PRICES["claude-opus-4-6"].input_per_1m == 5.00
    assert ANTHROPIC_PRICES["claude-opus-4-6"].output_per_1m == 25.00
    assert ANTHROPIC_PRICES["claude-sonnet-4-6"].input_per_1m == 3.00
    assert ANTHROPIC_PRICES["claude-sonnet-4-6"].output_per_1m == 15.00
    assert ANTHROPIC_PRICES["claude-haiku-4-5"].input_per_1m == 1.00
    assert ANTHROPIC_PRICES["claude-haiku-4-5"].output_per_1m == 5.00


def test_provider_fallbacks_price_known_models_and_reject_unknown_variants() -> None:
    openai = OpenAIProvider()
    anthropic = AnthropicProvider()
    google = GoogleProvider()

    assert openai._get_pricing("gpt-5.4-2026-03-05") == (2.50, 15.00)
    assert openai._get_pricing("gpt-5.4-internal") is None
    assert openai._get_pricing("gpt-99") is None

    assert anthropic._get_pricing("claude-opus-4-6") == {
        "input": 5.00,
        "output": 25.00,
        "cached_input": 0.50,
    }
    assert anthropic._get_pricing("claude-opus-9-internal") is None

    with patch("cutctx.providers.google.LITELLM_AVAILABLE", False):
        assert google.estimate_cost(1_000_000, 1_000_000, "gemini-2.5-flash") == 2.80
        assert google.estimate_cost(1_000, 1_000, "gemini-9-internal") is None


def test_provider_fallbacks_apply_documented_long_context_tiers() -> None:
    openai = OpenAIProvider()
    google = GoogleProvider()

    with patch("cutctx.providers.openai._get_litellm_module", return_value=None):
        # GPT-5.4 uses 2x input and 1.5x output rates above 272K input.
        assert openai.estimate_cost(300_000, 100_000, "gpt-5.4") == 3.75

    with patch("cutctx.providers.google.LITELLM_AVAILABLE", False):
        # Gemini 2.5 Pro uses $2.50/$15 above 200K input.
        assert google.estimate_cost(300_000, 100_000, "gemini-2.5-pro") == 2.25


def test_forecast_applies_documented_long_context_tiers() -> None:
    openai = CostEstimator("gpt-5.4").estimate(300_000, 100_000)
    assert openai.total_usd == 3.75

    google = CostEstimator("gemini-2.5-pro").estimate(300_000, 100_000)
    assert google.total_usd == 2.25


def test_forecast_does_not_invent_unknown_model_prices() -> None:
    assert _resolve_model_pricing("gpt-5.4-internal") is None
    assert _resolve_model_pricing("unknown-model-v99") is None

    estimate = CostEstimator("unknown-model-v99").estimate(1_000, 500)
    assert estimate.input_usd is None
    assert estimate.output_usd is None
    assert estimate.total_usd is None
    assert estimate.compression_savings_usd is None


def test_litellm_metadata_without_token_rates_is_not_zero_pricing() -> None:
    incomplete = {"openai/internal-model": {"max_input_tokens": 100_000}}
    with (
        patch("cutctx.pricing.litellm_pricing.LITELLM_AVAILABLE", True),
        patch("cutctx.pricing.litellm_pricing.litellm") as litellm,
    ):
        litellm.model_cost = incomplete
        assert get_model_pricing("internal-model") is None
