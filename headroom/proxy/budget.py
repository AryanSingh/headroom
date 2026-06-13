"""Streaming Budget Cut-offs — terminate streams when budget is exceeded.

Monitors token usage during streaming and truncates the stream with a
system message when the user's budget quota is exhausted.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("headroom.proxy.budget")


@dataclass
class BudgetConfig:
    """Configuration for streaming budget enforcement."""
    enabled: bool = False
    default_budget_tokens: int = 100_000  # per-request token budget
    default_budget_usd: float = 10.0  # per-request dollar budget
    warning_threshold_percent: float = 80.0  # warn at 80% usage
    hard_limit: bool = True  # True = truncate, False = just warn

    @classmethod
    def from_env(cls) -> BudgetConfig:
        import os
        return cls(
            enabled=os.environ.get("HEADROOM_BUDGET_ENABLED", "").strip() == "1",
            default_budget_tokens=int(os.environ.get("HEADROOM_BUDGET_TOKENS", "100000")),
            default_budget_usd=float(os.environ.get("HEADROOM_BUDGET_USD", "10.0")),
            hard_limit=os.environ.get("HEADROOM_BUDGET_HARD_LIMIT", "1").strip() != "0",
        )


class BudgetTracker:
    """Tracks per-request budget consumption during streaming.

    Usage:
        tracker = BudgetTracker(config, user_budget_tokens=50000)
        # During streaming:
        tracker.add_tokens(100)
        if tracker.is_exceeded():
            yield make_budget_exceeded_chunk()
            break
    """

    def __init__(
        self,
        config: BudgetConfig | None = None,
        *,
        user_budget_tokens: int | None = None,
        user_budget_usd: float | None = None,
        model: str = "",
    ) -> None:
        self.config = config or BudgetConfig.from_env()
        self.budget_tokens = user_budget_tokens or self.config.default_budget_tokens
        self.budget_usd = user_budget_usd or self.config.default_budget_usd
        self.model = model
        self._tokens_used = 0
        self._chunks_yielded = 0
        self._start_time = time.monotonic()
        self._warned = False

    @property
    def tokens_used(self) -> int:
        return self._tokens_used

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.budget_tokens - self._tokens_used)

    @property
    def percent_used(self) -> float:
        if self.budget_tokens <= 0:
            return 100.0
        return min(100.0, (self._tokens_used / self.budget_tokens) * 100)

    def add_tokens(self, count: int) -> None:
        """Record tokens consumed."""
        self._tokens_used += count
        self._chunks_yielded += 1

    def is_exceeded(self) -> bool:
        """Return True if budget is exceeded and hard_limit is enabled."""
        if not self.config.enabled or not self.config.hard_limit:
            return False
        return self._tokens_used >= self.budget_tokens

    def should_warn(self) -> bool:
        """Return True if we should emit a warning (once)."""
        if not self.config.enabled:
            return False
        if self._warned:
            return False
        if self.percent_used >= self.config.warning_threshold_percent:
            self._warned = True
            return True
        return False

    def elapsed_ms(self) -> float:
        return (time.monotonic() - self._start_time) * 1000

    def make_budget_exceeded_chunk(self) -> str:
        """Create an SSE chunk indicating budget exceeded."""
        import json
        # OpenAI format
        chunk_data = {
            "choices": [{
                "delta": {
                    "content": f"\n\n[System: Budget Exceeded — {self._tokens_used}/{self.budget_tokens} tokens used. Stream terminated.]",
                },
                "finish_reason": "budget_exceeded",
            }],
        }
        return f"data: {json.dumps(chunk_data)}\n\ndata: [DONE]\n\n"

    def make_budget_warning_chunk(self) -> str:
        """Create an SSE chunk with a budget warning (non-blocking)."""
        import json
        chunk_data = {
            "choices": [{
                "delta": {
                    "content": f"\n\n[System: Budget Warning — {self.percent_used:.0f}% of token budget used ({self._tokens_used}/{self.budget_tokens})]",
                },
                "finish_reason": None,
            }],
        }
        return f"data: {json.dumps(chunk_data)}\n\n"

    def stats(self) -> dict[str, Any]:
        """Return budget tracking stats."""
        return {
            "budget_tokens": self.budget_tokens,
            "tokens_used": self._tokens_used,
            "tokens_remaining": self.tokens_remaining,
            "percent_used": round(self.percent_used, 1),
            "elapsed_ms": round(self.elapsed_ms(), 1),
            "chunks_yielded": self._chunks_yielded,
            "exceeded": self.is_exceeded(),
            "model": self.model,
        }
