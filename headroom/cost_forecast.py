"""Cost Forecasting + Policy Engine for Headroom.

Pre-task cost estimation and policy-driven compression decisions.
Combines model pricing data with context size to predict costs before
sending requests, and applies policy rules to select optimal compression
strategies based on budget constraints.

Usage:
    estimator = CostEstimator(model="claude-sonnet-4-5-20250929")
    estimate = estimator.estimate(input_tokens=50000, output_tokens=2000)
    print(estimate)  # CostEstimate(input_usd=0.15, output_usd=0.03, ...)

    engine = PolicyEngine()
    decision = engine.evaluate(messages, budget_remaining_usd=5.0)
    # decision.strategy = "aggressive", decision.rationale = "budget < $5"
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model pricing (input/output per 1M tokens, USD)
# Updated 2025-06. Source: provider pricing pages.
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    # Anthropic Claude
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "claude-haiku-3-5-20241022": {"input": 0.80, "output": 4.0},
    "claude-haiku-3-5": {"input": 0.80, "output": 4.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    # OpenAI GPT
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4.1": {"input": 2.0, "output": 8.0},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "o3": {"input": 10.0, "output": 40.0},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "o4-mini": {"input": 1.10, "output": 4.40},
    # Google Gemini
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-1.5-pro": {"input": 2.50, "output": 10.0},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
}

# Fallback for unknown models (conservative: Sonnet-class pricing)
_DEFAULT_INPUT_PER_M = 3.0
_DEFAULT_OUTPUT_PER_M = 15.0


def _resolve_model_pricing(model: str) -> tuple[float, float]:
    """Resolve input/output pricing per 1M tokens for a model.

    Tries exact match, then prefix match (e.g., "claude-sonnet-4-5-20250929"
    falls back to "claude-sonnet-4-5"), then default.

    Returns:
        (input_per_m, output_per_m) in USD per 1M tokens.
    """
    # Exact match
    if model in MODEL_PRICING:
        p = MODEL_PRICING[model]
        return p["input"], p["output"]

    # Prefix match: try progressively shorter prefixes
    for length in range(len(model), 0, -1):
        prefix = model[:length]
        if prefix in MODEL_PRICING:
            p = MODEL_PRICING[prefix]
            return p["input"], p["output"]

    return _DEFAULT_INPUT_PER_M, _DEFAULT_OUTPUT_PER_M


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

@dataclass
class CostEstimate:
    """Pre-request cost estimate."""

    model: str
    input_tokens: int
    output_tokens: int
    input_usd: float
    output_usd: float
    total_usd: float
    compression_savings_usd: float = 0.0
    compressed_input_tokens: int = 0

    @property
    def savings_percent(self) -> float:
        if self.input_usd == 0:
            return 0.0
        return (self.compression_savings_usd / self.input_usd) * 100


class CostEstimator:
    """Estimate API call costs before sending requests.

    Uses model pricing data to predict cost, optionally factoring in
    expected compression savings.

    Usage:
        estimator = CostEstimator(model="claude-sonnet-4-5")
        estimate = estimator.estimate(input_tokens=50000, output_tokens=2000)
    """

    def __init__(self, model: str = "claude-sonnet-4-5-20250929") -> None:
        self.model = model
        self._input_per_m, self._output_per_m = _resolve_model_pricing(model)

    def estimate(
        self,
        input_tokens: int,
        output_tokens: int = 0,
        compression_ratio: float = 1.0,
    ) -> CostEstimate:
        """Estimate cost for a request.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            compression_ratio: Expected compression ratio (1.0 = no compression,
                             0.5 = 50% reduction). Applied to input tokens.

        Returns:
            CostEstimate with detailed breakdown.
        """
        input_usd = (input_tokens / 1_000_000) * self._input_per_m
        output_usd = (output_tokens / 1_000_000) * self._output_per_m
        total_usd = input_usd + output_usd

        # Compression savings
        compressed_input = int(input_tokens * compression_ratio)
        compressed_input_usd = (compressed_input / 1_000_000) * self._input_per_m
        savings = input_usd - compressed_input_usd

        return CostEstimate(
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_usd=round(input_usd, 6),
            output_usd=round(output_usd, 6),
            total_usd=round(total_usd, 6),
            compression_savings_usd=round(savings, 6),
            compressed_input_tokens=compressed_input,
        )

    def estimate_messages(
        self,
        messages: list[dict[str, Any]],
        output_tokens: int = 0,
        compression_ratio: float = 1.0,
    ) -> CostEstimate:
        """Estimate cost from a message list (rough token count).

        Args:
            messages: List of message dicts with 'content' keys.
            output_tokens: Expected output tokens.
            compression_ratio: Expected compression ratio.

        Returns:
            CostEstimate.
        """
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        total_chars += len(str(item.get("text", "")))
            else:
                total_chars += len(str(content))

        # Rough: 4 chars per token
        input_tokens = max(1, total_chars // 4)
        return self.estimate(input_tokens, output_tokens, compression_ratio)


# ---------------------------------------------------------------------------
# Compression strategy selection
# ---------------------------------------------------------------------------

class CompressionStrategy(str, Enum):
    """Compression strategy levels."""
    NONE = "none"           # No compression
    MINIMAL = "minimal"     # CacheAligner only (~5% reduction)
    LIGHT = "light"         # Type-based routing (~30% reduction)
    MODERATE = "moderate"   # SmartCrusher + CCR (~50% reduction)
    AGGRESSIVE = "aggressive"  # Full pipeline (~70% reduction)
    EMERGENCY = "emergency" # Extreme compression for budget crisis


@dataclass
class PolicyDecision:
    """Decision from the policy engine."""

    strategy: CompressionStrategy
    compression_ratio: float  # Expected ratio (0.0 = full compress, 1.0 = none)
    rationale: str
    budget_remaining_usd: float
    estimated_savings_usd: float
    priority: int = 0  # Higher = more urgent


# ---------------------------------------------------------------------------
# Policy engine
# ---------------------------------------------------------------------------

@dataclass
class PolicyRule:
    """A single policy rule for compression decisions."""

    name: str
    condition: str  # Human-readable condition
    strategy: CompressionStrategy
    compression_ratio: float
    priority: int = 0


# Default policy rules (evaluated in priority order)
_DEFAULT_RULES = [
    PolicyRule(
        name="budget_critical",
        condition="budget_remaining < $0.50",
        strategy=CompressionStrategy.EMERGENCY,
        compression_ratio=0.15,
        priority=100,
    ),
    PolicyRule(
        name="budget_low",
        condition="budget_remaining < $2.00",
        strategy=CompressionStrategy.AGGRESSIVE,
        compression_ratio=0.30,
        priority=80,
    ),
    PolicyRule(
        name="budget_moderate",
        condition="budget_remaining < $5.00",
        strategy=CompressionStrategy.MODERATE,
        compression_ratio=0.50,
        priority=60,
    ),
    PolicyRule(
        name="context_large",
        condition="input_tokens > 100K",
        strategy=CompressionStrategy.MODERATE,
        compression_ratio=0.50,
        priority=40,
    ),
    PolicyRule(
        name="context_medium",
        condition="input_tokens > 50K",
        strategy=CompressionStrategy.LIGHT,
        compression_ratio=0.70,
        priority=20,
    ),
    PolicyRule(
        name="default",
        condition="always",
        strategy=CompressionStrategy.LIGHT,
        compression_ratio=0.70,
        priority=0,
    ),
]


class PolicyEngine:
    """Policy-driven compression strategy selector.

    Evaluates rules against current context (budget, token count, model)
    to select optimal compression strategy.

    Usage:
        engine = PolicyEngine(model="claude-sonnet-4-5")
        decision = engine.evaluate(
            messages=messages,
            budget_remaining_usd=3.50,
        )
        # decision.strategy == CompressionStrategy.MODERATE
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250929",
        rules: list[PolicyRule] | None = None,
    ) -> None:
        self.model = model
        self._estimator = CostEstimator(model)
        self._rules = sorted(rules or _DEFAULT_RULES, key=lambda r: -r.priority)

    def evaluate(
        self,
        messages: list[dict[str, Any]] | None = None,
        input_tokens: int = 0,
        budget_remaining_usd: float = 100.0,
        output_tokens: int = 0,
    ) -> PolicyDecision:
        """Evaluate policies and select compression strategy.

        Args:
            messages: Message list (used for token estimation if input_tokens=0).
            input_tokens: Explicit token count (overrides message estimation).
            budget_remaining_usd: Remaining budget in USD.
            output_tokens: Expected output tokens.

        Returns:
            PolicyDecision with selected strategy and rationale.
        """
        # Estimate input tokens if not provided
        if input_tokens == 0 and messages:
            estimate = self._estimator.estimate_messages(messages, output_tokens)
            input_tokens = estimate.input_tokens
        elif input_tokens == 0:
            input_tokens = 1000  # Minimum fallback

        # Evaluate rules in priority order
        for rule in self._rules:
            if self._rule_matches(rule, budget_remaining_usd, input_tokens):
                # Estimate savings
                cost_estimate = self._estimator.estimate(
                    input_tokens, output_tokens, rule.compression_ratio
                )

                return PolicyDecision(
                    strategy=rule.strategy,
                    compression_ratio=rule.compression_ratio,
                    rationale=f"{rule.name}: {rule.condition}",
                    budget_remaining_usd=round(budget_remaining_usd, 4),
                    estimated_savings_usd=round(cost_estimate.compression_savings_usd, 6),
                    priority=rule.priority,
                )

        # Should never reach here (default rule always matches)
        return PolicyDecision(
            strategy=CompressionStrategy.LIGHT,
            compression_ratio=0.70,
            rationale="fallback",
            budget_remaining_usd=round(budget_remaining_usd, 4),
            estimated_savings_usd=0.0,
        )

    def _rule_matches(
        self,
        rule: PolicyRule,
        budget_remaining: float,
        input_tokens: int,
    ) -> bool:
        """Check if a rule's condition matches current state."""
        name = rule.name

        if name == "budget_critical":
            return budget_remaining < 0.50
        elif name == "budget_low":
            return budget_remaining < 2.00
        elif name == "budget_moderate":
            return budget_remaining < 5.00
        elif name == "context_large":
            return input_tokens > 100_000
        elif name == "context_medium":
            return input_tokens > 50_000
        elif name == "default":
            return True

        return False


# ---------------------------------------------------------------------------
# Session cost tracker
# ---------------------------------------------------------------------------

@dataclass
class SessionCostSnapshot:
    """Snapshot of session costs at a point in time."""

    total_input_tokens: int
    total_output_tokens: int
    total_input_usd: float
    total_output_usd: float
    total_usd: float
    tokens_saved_by_compression: int
    usd_saved_by_compression: float
    request_count: int
    model: str
    budget_remaining_usd: float | None = None


class SessionCostTracker:
    """Track cumulative costs across a session.

    Accumulates per-request costs and compression savings to provide
    session-level cost visibility.

    Usage:
        tracker = SessionCostTracker(model="claude-sonnet-4-5")
        tracker.record_request(input_tokens=5000, output_tokens=200,
                               compressed_input_tokens=3000)
        snapshot = tracker.snapshot()
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250929",
        budget_usd: float | None = None,
    ) -> None:
        self.model = model
        self._estimator = CostEstimator(model)
        self._budget_usd = budget_usd

        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_input_usd = 0.0
        self._total_output_usd = 0.0
        self._tokens_saved = 0
        self._usd_saved = 0.0
        self._request_count = 0

    def record_request(
        self,
        input_tokens: int,
        output_tokens: int = 0,
        compressed_input_tokens: int | None = None,
    ) -> CostEstimate:
        """Record a request's token usage.

        Args:
            input_tokens: Input tokens (before compression).
            output_tokens: Output tokens.
            compressed_input_tokens: Input tokens after compression (None = no compression).

        Returns:
            CostEstimate for this request.
        """
        estimate = self._estimator.estimate(input_tokens, output_tokens)

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_input_usd += estimate.input_usd
        self._total_output_usd += estimate.output_usd
        self._request_count += 1

        if compressed_input_tokens is not None and compressed_input_tokens < input_tokens:
            saved_tokens = input_tokens - compressed_input_tokens
            saved_usd = (saved_tokens / 1_000_000) * self._estimator._input_per_m
            self._tokens_saved += saved_tokens
            self._usd_saved += saved_usd
            estimate.compressed_input_tokens = compressed_input_tokens
            estimate.compression_savings_usd = round(saved_usd, 6)

        return estimate

    def snapshot(self) -> SessionCostSnapshot:
        """Get current session cost snapshot."""
        budget_remaining = None
        if self._budget_usd is not None:
            budget_remaining = round(self._budget_usd - self._total_input_usd - self._total_output_usd, 6)

        return SessionCostSnapshot(
            total_input_tokens=self._total_input_tokens,
            total_output_tokens=self._total_output_tokens,
            total_input_usd=round(self._total_input_usd, 6),
            total_output_usd=round(self._total_output_usd, 6),
            total_usd=round(self._total_input_usd + self._total_output_usd, 6),
            tokens_saved_by_compression=self._tokens_saved,
            usd_saved_by_compression=round(self._usd_saved, 6),
            request_count=self._request_count,
            model=self.model,
            budget_remaining_usd=budget_remaining,
        )

    @property
    def is_budget_exceeded(self) -> bool:
        """Check if budget has been exceeded."""
        if self._budget_usd is None:
            return False
        return (self._total_input_usd + self._total_output_usd) >= self._budget_usd

    def reset(self) -> None:
        """Reset all counters."""
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_input_usd = 0.0
        self._total_output_usd = 0.0
        self._tokens_saved = 0
        self._usd_saved = 0.0
        self._request_count = 0
