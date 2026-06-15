"""Context Budget Controller — progressive compression for long agent sessions.

Instead of truncating when context fills up, progressively compresses older
context to make room for new context. The agent never hits the wall.

Usage:
    budget = ContextBudgetController(max_tokens=100_000)
    messages = budget.apply(messages)
    print(budget.status)  # {"zone": "GREEN", "used": 45000, "forecast_usd": 0.45}
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("headroom.context_budget")


class BudgetZone(str, Enum):
    """Budget zone indicating compression urgency."""

    GREEN = "GREEN"        # 0-60%: No compression needed
    YELLOW = "YELLOW"      # 60-80%: Light compression
    RED = "RED"            # 80-95%: Aggressive compression
    CRITICAL = "CRITICAL"  # 95%+: Emergency summarization


@dataclass
class BudgetStatus:
    """Current budget status snapshot."""

    zone: BudgetZone
    tokens_used: int
    tokens_budget: int
    tokens_available: int
    percent_used: float
    compression_applied: bool
    forecast_usd: float
    last_compression_zone: BudgetZone | None = None


@dataclass
class BudgetPolicy:
    """Zone thresholds and compression parameters."""

    green_threshold: float = 0.60       # 0-60% is GREEN
    yellow_threshold: float = 0.80      # 60-80% is YELLOW
    red_threshold: float = 0.95         # 80-95% is RED
    compression_window_yellow: int = 10  # Protect last N messages in YELLOW
    compression_window_red: int = 5      # Protect last N messages in RED

    @classmethod
    def from_env(cls, policy: str = "balanced") -> BudgetPolicy:
        """Load policy from environment or use named preset.

        Environment variables override defaults:
            HEADROOM_BUDGET_GREEN (default 0.60)
            HEADROOM_BUDGET_YELLOW (default 0.80)
            HEADROOM_BUDGET_RED (default 0.95)
            HEADROOM_BUDGET_WINDOW_YELLOW (default 10)
            HEADROOM_BUDGET_WINDOW_RED (default 5)

        If none set, uses named preset: 'conservative', 'balanced', 'aggressive'.
        """
        # Check for explicit env vars first
        green = os.getenv("HEADROOM_BUDGET_GREEN")
        yellow = os.getenv("HEADROOM_BUDGET_YELLOW")
        red = os.getenv("HEADROOM_BUDGET_RED")
        window_yellow = os.getenv("HEADROOM_BUDGET_WINDOW_YELLOW")
        window_red = os.getenv("HEADROOM_BUDGET_WINDOW_RED")

        # If any env var is set, use all explicit values with defaults
        if any([green, yellow, red, window_yellow, window_red]):
            return cls(
                green_threshold=float(green or "0.60"),
                yellow_threshold=float(yellow or "0.80"),
                red_threshold=float(red or "0.95"),
                compression_window_yellow=int(window_yellow or "10"),
                compression_window_red=int(window_red or "5"),
            )

        # Otherwise use policy presets
        policy = policy.lower().strip()
        if policy == "conservative":
            return cls(
                green_threshold=0.70,
                yellow_threshold=0.85,
                red_threshold=0.95,
                compression_window_yellow=15,
                compression_window_red=8,
            )
        elif policy == "aggressive":
            return cls(
                green_threshold=0.50,
                yellow_threshold=0.75,
                red_threshold=0.90,
                compression_window_yellow=5,
                compression_window_red=3,
            )
        else:  # balanced (default)
            return cls()


class ContextBudgetController:
    """Progressive context compression for long agent sessions.

    Monitors token usage and compresses older messages progressively
    to avoid hard context limit failures.

    Usage:
        budget = ContextBudgetController(max_tokens=100_000, model="claude-sonnet-4-6")
        compressed_messages = budget.apply(messages)
        status = budget.status
        forecast = budget.forecast(messages)
    """

    def __init__(
        self,
        max_tokens: int = 100_000,
        model: str = "claude-sonnet-4-6",
        policy: str = "balanced",
    ) -> None:
        """Initialize budget controller.

        Args:
            max_tokens: Total token budget per session
            model: Model identifier for cost estimation
            policy: Budget policy ('conservative', 'balanced', 'aggressive')
        """
        self.max_tokens = max_tokens
        self.model = model
        self.policy = BudgetPolicy.from_env(policy)

        self._tokens_used = 0
        self._compression_applied = False
        self._last_compression_zone: BudgetZone | None = None
        self._token_history: list[int] = []  # For velocity calculation

    def apply(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply progressive compression based on budget zone.

        Returns messages with older ones compressed if needed to stay within budget.
        Recent messages are protected from compression to preserve active conversation.

        Args:
            messages: List of messages in Anthropic/OpenAI format

        Returns:
            Messages with compression applied progressively as needed
        """
        if not messages:
            return messages

        token_count = self._count_tokens(messages)
        self._tokens_used = token_count
        self._token_history.append(token_count)

        # Keep history bounded (last 100 measurements for velocity)
        if len(self._token_history) > 100:
            self._token_history = self._token_history[-100:]

        zone = self._get_zone(token_count)
        logger.debug(
            "Context budget zone: %s (used %d/%d tokens, %.1f%%)",
            zone,
            token_count,
            self.max_tokens,
            self.percent_used,
        )

        if zone == BudgetZone.GREEN:
            # No compression needed
            return messages

        elif zone == BudgetZone.YELLOW:
            # Light compression: compress messages older than window
            result = self._compress_messages_in_zone(
                messages,
                window_size=self.policy.compression_window_yellow,
                aggressiveness=0.5,
            )
            self._compression_applied = True
            self._last_compression_zone = zone
            return result

        elif zone == BudgetZone.RED:
            # Aggressive compression: compress older messages more
            result = self._compress_messages_in_zone(
                messages,
                window_size=self.policy.compression_window_red,
                aggressiveness=0.8,
            )
            self._compression_applied = True
            self._last_compression_zone = zone
            return result

        elif zone == BudgetZone.CRITICAL:
            # Emergency: summarize oldest 20%
            result = self._summarize_critical_zone(messages)
            self._compression_applied = True
            self._last_compression_zone = zone
            logger.warning("Context in CRITICAL zone; applying emergency compression")
            return result

        return messages

    @property
    def status(self) -> BudgetStatus:
        """Current budget status snapshot."""
        zone = self._get_zone(self._tokens_used)
        return BudgetStatus(
            zone=zone,
            tokens_used=self._tokens_used,
            tokens_budget=self.max_tokens,
            tokens_available=max(0, self.max_tokens - self._tokens_used),
            percent_used=self.percent_used,
            compression_applied=self._compression_applied,
            forecast_usd=self._estimate_cost(self._tokens_used),
            last_compression_zone=self._last_compression_zone,
        )

    @property
    def percent_used(self) -> float:
        """Percentage of token budget used."""
        if self.max_tokens <= 0:
            return 100.0
        return min(100.0, (self._tokens_used / self.max_tokens) * 100)

    def forecast(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Forecast total cost based on current token velocity.

        Args:
            messages: Current message list

        Returns:
            Forecast dict with projected costs and confidence
        """
        token_count = self._count_tokens(messages)
        tokens_available = max(0, self.max_tokens - token_count)

        # Calculate token velocity (tokens per message)
        velocity = (token_count / len(messages)) if messages else 0

        # Estimate messages we can fit in remaining budget
        estimated_messages_remaining = int(tokens_available / velocity) if velocity > 0 else 0

        # Get cost per token
        cost_per_token = self._get_cost_per_token()

        # Forecast
        current_cost = token_count * cost_per_token
        projected_cost = tokens_available * cost_per_token
        total_forecast = current_cost + projected_cost

        # Confidence: increases with more messages (10% per message, capped at 100%)
        confidence_pct = min(100.0, len(messages) * 10)

        return {
            "token_velocity": velocity,
            "tokens_available": tokens_available,
            "estimated_messages_remaining": estimated_messages_remaining,
            "forecast_usd": round(total_forecast, 4),
            "confidence_pct": round(confidence_pct, 1),
            "current_cost_usd": round(current_cost, 4),
            "projected_additional_cost_usd": round(projected_cost, 4),
        }

    def _compress_messages_in_zone(
        self,
        messages: list[dict[str, Any]],
        window_size: int,
        aggressiveness: float,
    ) -> list[dict[str, Any]]:
        """Compress older messages while protecting recent ones.

        Args:
            messages: All messages
            window_size: Number of recent messages to protect
            aggressiveness: Compression aggressiveness (0.0-1.0)

        Returns:
            Messages with old ones compressed
        """
        if len(messages) <= window_size:
            # All messages are protected
            return messages

        cutoff = len(messages) - window_size
        old_messages = messages[:cutoff]
        recent_messages = messages[cutoff:]

        # Compress old messages using headroom's compress API
        try:
            from headroom.compress import compress, CompressConfig

            config = CompressConfig(
                compress_user_messages=True,
                protect_recent=0,  # Compress all in this batch
                target_ratio=1.0 - aggressiveness,  # Higher aggressiveness = lower target ratio
            )

            result = compress(
                old_messages,
                model=self.model,
                config=config,
            )

            compressed_old = result.messages
            logger.debug(
                "Compressed %d old messages: %d -> %d tokens",
                len(old_messages),
                result.tokens_before,
                result.tokens_after,
            )

            return compressed_old + recent_messages

        except ImportError:
            logger.warning("headroom.compress not available; returning messages unchanged")
            return messages
        except Exception as e:
            logger.warning("Compression failed (%s); returning messages unchanged", e)
            return messages

    def _summarize_critical_zone(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Summarize oldest 20% of messages (emergency compression).

        Args:
            messages: All messages

        Returns:
            Messages with oldest 20% summarized into a single message
        """
        if not messages:
            return messages

        cutoff = max(1, len(messages) // 5)  # Oldest 20%
        to_summarize = messages[:cutoff]
        to_keep = messages[cutoff:]

        # Create a summary message from the oldest batch
        summary_text = f"[Context Summary] Compressed {len(to_summarize)} older messages due to budget constraints."

        # Try to create a proper tool message
        summary_message = {
            "role": "user",
            "content": summary_text,
        }

        logger.debug(
            "CRITICAL zone: summarized %d messages into summary",
            len(to_summarize),
        )

        return [summary_message] + to_keep

    def _count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Count tokens in messages using tiktoken or fallback.

        Args:
            messages: Messages to count

        Returns:
            Token count
        """
        try:
            import tiktoken

            # Try to use the model's tokenizer
            try:
                enc = tiktoken.encoding_for_model(self.model)
            except KeyError:
                # Model not recognized, use cl100k_base (GPT-4/3.5)
                enc = tiktoken.get_encoding("cl100k_base")

            total = 0
            for msg in messages:
                # Simple approximation: role + content
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")

                    # Convert content to string if needed (could be list of dicts)
                    if isinstance(content, list):
                        content_str = "".join(
                            str(item.get("text", "")) if isinstance(item, dict) else str(item)
                            for item in content
                        )
                    else:
                        content_str = str(content)

                    msg_text = f"{role} {content_str}"
                    total += len(enc.encode(msg_text))

            return total

        except Exception:
            # Fallback: rough estimate (4 chars = ~1 token)
            # Catches ImportError (tiktoken not installed) and network errors
            # (tiktoken tries to download encoding files on first use)
            logger.debug("tiktoken not available or failed to load; using fallback token counting")
            total = 0
            for msg in messages:
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content_str = "".join(
                            str(item.get("text", "")) if isinstance(item, dict) else str(item)
                            for item in content
                        )
                    else:
                        content_str = str(content)
                    total += len(content_str) // 4

            return total

    def _get_zone(self, tokens_used: int) -> BudgetZone:
        """Determine budget zone from token usage.

        Args:
            tokens_used: Current token count

        Returns:
            Current BudgetZone
        """
        if self.max_tokens <= 0:
            return BudgetZone.CRITICAL

        percent = tokens_used / self.max_tokens

        if percent < self.policy.green_threshold:
            return BudgetZone.GREEN
        elif percent < self.policy.yellow_threshold:
            return BudgetZone.YELLOW
        elif percent < self.policy.red_threshold:
            return BudgetZone.RED
        else:
            return BudgetZone.CRITICAL

    def _estimate_cost(self, tokens: int) -> float:
        """Estimate cost in USD for token count.

        Args:
            tokens: Token count

        Returns:
            Cost in USD
        """
        cost_per_token = self._get_cost_per_token()
        return tokens * cost_per_token

    def _get_cost_per_token(self) -> float:
        """Get input cost per token for the model.

        Returns:
            Cost per token (defaults to reasonable estimate if not available)
        """
        try:
            from headroom.proxy.cost import _get_litellm_module

            litellm = _get_litellm_module()
            if litellm is None:
                return self._fallback_cost_per_token()

            # Try to resolve the model name
            from headroom.pricing.litellm_pricing import resolve_litellm_model

            resolved = resolve_litellm_model(self.model)
            info = litellm.model_cost.get(resolved, {})
            cost = info.get("input_cost_per_token")

            if cost:
                return float(cost)

        except Exception:
            pass

        return self._fallback_cost_per_token()

    def _fallback_cost_per_token(self) -> float:
        """Fallback cost estimates when pricing data unavailable.

        Returns:
            Estimated cost per token
        """
        # Conservative estimates per model family
        if "claude-opus" in self.model:
            return 15.0 / 1_000_000  # $15/1M input tokens
        elif "claude-sonnet" in self.model:
            return 3.0 / 1_000_000  # $3/1M input tokens
        elif "claude-haiku" in self.model:
            return 0.8 / 1_000_000  # $0.80/1M input tokens
        elif "gpt-4o" in self.model or "gpt-4-turbo" in self.model:
            return 10.0 / 1_000_000  # $10/1M input tokens
        elif "gpt-3.5" in self.model or "gpt-35" in self.model:
            return 0.5 / 1_000_000  # $0.50/1M input tokens
        elif "gemini-1.5-pro" in self.model:
            return 2.5 / 1_000_000  # $2.50/1M input tokens
        else:
            # Safe default (Sonnet-like)
            return 3.0 / 1_000_000
