"""Model-price lookups shared by cost tracking and savings attribution."""
from __future__ import annotations

from cutctx.pricing.litellm_pricing import resolve_litellm_model


def _get_litellm_module():
    import litellm
    return litellm


def value_tokens_usd(model: str, tokens: int, *, rate_per_million: float | None = None) -> float:
    """USD value of `tokens` input tokens for `model`, at list price by default.

    Pass `rate_per_million` to price at a different rate (e.g. 0.5x for batch
    routing, or a cache-read rate). Returns 0.0 if tokens <= 0 or pricing is
    unavailable (never raises — attribution is best-effort).
    """
    if tokens <= 0:
        return 0.0
    if rate_per_million is not None:
        return (rate_per_million / 1_000_000) * tokens
    try:
        litellm = _get_litellm_module()
        resolved = resolve_litellm_model(model)
        info = litellm.model_cost.get(resolved, {})
        cost_per_token = info.get("input_cost_per_token")
        return cost_per_token * tokens if cost_per_token else 0.0
    except Exception:
        return 0.0
