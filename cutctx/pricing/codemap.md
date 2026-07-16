# cutctx/pricing/

## Responsibility
Resolves provider/model token prices for cost and savings calculations.

## Design
A registry combines current curated OpenAI/Anthropic/Google tables, model aliases, long-context tiers, and LiteLLM-backed pricing. Unknown, internal, or incomplete entries fail closed instead of silently applying a stale generic rate.

## Flow
Callers submit provider/model/token counts; exact or aliased rates are resolved, tier thresholds are applied, and input/output cost is computed only when trustworthy pricing is available.

## Integration
Used by proxy cost tracking, savings, billing, and evals; optionally consumes LiteLLM pricing.
