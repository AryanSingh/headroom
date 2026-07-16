"""Anthropic model pricing information."""

from datetime import date

from .registry import ModelPricing, PricingRegistry

# Last verified date for pricing information
LAST_UPDATED = date(2026, 7, 16)

# Official pricing page
SOURCE_URL = "https://platform.claude.com/docs/en/about-claude/pricing"

# All prices are in USD per 1 million tokens
ANTHROPIC_PRICES: dict[str, ModelPricing] = {
    "claude-opus-4-8": ModelPricing(
        model="claude-opus-4-8",
        provider="anthropic",
        input_per_1m=5.00,
        output_per_1m=25.00,
        cached_input_per_1m=0.50,
        batch_input_per_1m=2.50,
        batch_output_per_1m=12.50,
        context_window=1_000_000,
        notes="Claude Opus 4.8 standard global inference pricing",
    ),
    "claude-opus-4-7": ModelPricing(
        model="claude-opus-4-7",
        provider="anthropic",
        input_per_1m=5.00,
        output_per_1m=25.00,
        cached_input_per_1m=0.50,
        batch_input_per_1m=2.50,
        batch_output_per_1m=12.50,
        context_window=1_000_000,
        notes="Claude Opus 4.7 standard global inference pricing",
    ),
    "claude-opus-4-6": ModelPricing(
        model="claude-opus-4-6",
        provider="anthropic",
        input_per_1m=5.00,
        output_per_1m=25.00,
        cached_input_per_1m=0.50,
        batch_input_per_1m=2.50,
        batch_output_per_1m=12.50,
        context_window=1_000_000,
        notes="Claude Opus 4.6 standard global inference pricing",
    ),
    "claude-opus-4-5": ModelPricing(
        model="claude-opus-4-5",
        provider="anthropic",
        input_per_1m=5.00,
        output_per_1m=25.00,
        cached_input_per_1m=0.50,
        batch_input_per_1m=2.50,
        batch_output_per_1m=12.50,
        context_window=200_000,
        notes="Claude Opus 4.5 standard global inference pricing",
    ),
    "claude-opus-4-5-20251101": ModelPricing(
        model="claude-opus-4-5-20251101",
        provider="anthropic",
        input_per_1m=5.00,
        output_per_1m=25.00,
        cached_input_per_1m=0.50,
        batch_input_per_1m=2.50,
        batch_output_per_1m=12.50,
        context_window=200_000,
        notes="Pinned Claude Opus 4.5 snapshot",
    ),
    "claude-sonnet-4-6": ModelPricing(
        model="claude-sonnet-4-6",
        provider="anthropic",
        input_per_1m=3.00,
        output_per_1m=15.00,
        cached_input_per_1m=0.30,
        batch_input_per_1m=1.50,
        batch_output_per_1m=7.50,
        context_window=1_000_000,
        notes="Claude Sonnet 4.6 standard global inference pricing",
    ),
    "claude-sonnet-4-5": ModelPricing(
        model="claude-sonnet-4-5",
        provider="anthropic",
        input_per_1m=3.00,
        output_per_1m=15.00,
        cached_input_per_1m=0.30,
        batch_input_per_1m=1.50,
        batch_output_per_1m=7.50,
        context_window=200_000,
        notes="Claude Sonnet 4.5 standard global inference pricing",
    ),
    "claude-sonnet-4-5-20250929": ModelPricing(
        model="claude-sonnet-4-5-20250929",
        provider="anthropic",
        input_per_1m=3.00,
        output_per_1m=15.00,
        cached_input_per_1m=0.30,
        batch_input_per_1m=1.50,
        batch_output_per_1m=7.50,
        context_window=200_000,
        notes="Pinned Claude Sonnet 4.5 snapshot",
    ),
    "claude-haiku-4-5": ModelPricing(
        model="claude-haiku-4-5",
        provider="anthropic",
        input_per_1m=1.00,
        output_per_1m=5.00,
        cached_input_per_1m=0.10,
        batch_input_per_1m=0.50,
        batch_output_per_1m=2.50,
        context_window=200_000,
        notes="Claude Haiku 4.5 standard global inference pricing",
    ),
    "claude-haiku-4-5-20251001": ModelPricing(
        model="claude-haiku-4-5-20251001",
        provider="anthropic",
        input_per_1m=1.00,
        output_per_1m=5.00,
        cached_input_per_1m=0.10,
        batch_input_per_1m=0.50,
        batch_output_per_1m=2.50,
        context_window=200_000,
        notes="Pinned Claude Haiku 4.5 snapshot",
    ),
    "claude-3-5-sonnet-20241022": ModelPricing(
        model="claude-3-5-sonnet-20241022",
        provider="anthropic",
        input_per_1m=3.00,
        output_per_1m=15.00,
        cached_input_per_1m=0.30,
        batch_input_per_1m=1.50,
        batch_output_per_1m=7.50,
        context_window=200_000,
        notes="Most intelligent Claude model, best for complex tasks",
    ),
    "claude-3-5-sonnet-latest": ModelPricing(
        model="claude-3-5-sonnet-latest",
        provider="anthropic",
        input_per_1m=3.00,
        output_per_1m=15.00,
        cached_input_per_1m=0.30,
        batch_input_per_1m=1.50,
        batch_output_per_1m=7.50,
        context_window=200_000,
        notes="Alias for claude-3-5-sonnet-20241022",
    ),
    "claude-3-5-haiku-20241022": ModelPricing(
        model="claude-3-5-haiku-20241022",
        provider="anthropic",
        input_per_1m=0.80,
        output_per_1m=4.00,
        cached_input_per_1m=0.08,
        batch_input_per_1m=0.40,
        batch_output_per_1m=2.00,
        context_window=200_000,
        notes="Fast and cost-effective for simple tasks",
    ),
    "claude-3-opus-20240229": ModelPricing(
        model="claude-3-opus-20240229",
        provider="anthropic",
        input_per_1m=15.00,
        output_per_1m=75.00,
        cached_input_per_1m=1.50,
        batch_input_per_1m=7.50,
        batch_output_per_1m=37.50,
        context_window=200_000,
        notes="Previous generation powerful model for complex tasks",
    ),
    "claude-3-haiku-20240307": ModelPricing(
        model="claude-3-haiku-20240307",
        provider="anthropic",
        input_per_1m=0.25,
        output_per_1m=1.25,
        cached_input_per_1m=0.03,
        context_window=200_000,
        notes="Previous generation fastest and most compact model",
    ),
}


def get_anthropic_registry() -> PricingRegistry:
    """Create and return an Anthropic pricing registry.

    Returns:
        PricingRegistry configured with Anthropic model prices.
    """
    return PricingRegistry(
        last_updated=LAST_UPDATED,
        source_url=SOURCE_URL,
        prices=ANTHROPIC_PRICES.copy(),
    )
