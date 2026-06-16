from dataclasses import dataclass

from headroom.pricing.registry import PricingRegistry


@dataclass
class CostResult:
    est_cost_usd: float | None
    est_cost_saved_usd: float | None


def compute_costs(
    registry: PricingRegistry,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    tokens_saved: int,
) -> CostResult:
    """Compute the estimated cost and cost saved for a given usage.

    If the model is not found or not provided, returns None for the costs.
    """
    if not model:
        return CostResult(None, None)

    try:
        # Calculate actual cost incurred
        actual_cost_estimate = registry.estimate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        est_cost_usd = actual_cost_estimate.cost_usd

        # Calculate cost saved (saved tokens are input tokens)
        if tokens_saved > 0:
            saved_cost_estimate = registry.estimate_cost(
                model=model,
                input_tokens=tokens_saved,
                output_tokens=0,
            )
            est_cost_saved_usd = saved_cost_estimate.cost_usd
        else:
            est_cost_saved_usd = 0.0

        return CostResult(est_cost_usd, est_cost_saved_usd)
    except ValueError:
        # Model not found in registry
        return CostResult(None, None)
