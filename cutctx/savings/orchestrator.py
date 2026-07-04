"""Top-level savings orchestrator.

The orchestrator owns the merge rules:

    1. The five savings sources are tracked independently.
    2. The combined total is the SUM of per-source tokens, never the
       difference between raw_input_tokens and post_cutctx_tokens.
       This prevents double-counting when Cutctx compression and
       provider cache both reduce the same input.
    3. Provider cache and Cutctx compression are reported separately
       so the buyer can see the marginal value of Cutctx above and
       beyond native prompt caching.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from cutctx.savings.types import (
    RequestSavingsBreakdown,
    SavingsBySource,
)

logger = logging.getLogger(__name__)


@dataclass
class AggregateSavings:
    """Aggregate across many requests."""

    requests: int = 0
    raw_input_tokens: int = 0
    post_cutctx_tokens: int = 0
    by_source: SavingsBySource = field(default_factory=SavingsBySource)
    by_provider: dict[str, SavingsBySource] = field(default_factory=dict)
    by_model: dict[str, SavingsBySource] = field(default_factory=dict)
    by_client: dict[str, SavingsBySource] = field(default_factory=dict)

    @property
    def total_tokens_saved(self) -> int:
        return self.by_source.total_tokens

    @property
    def total_usd_saved(self) -> float:
        return self.by_source.total_usd

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "raw_input_tokens": self.raw_input_tokens,
            "post_cutctx_tokens": self.post_cutctx_tokens,
            "total_tokens_saved": self.total_tokens_saved,
            "total_usd_saved": round(self.total_usd_saved, 6),
            "by_source": self.by_source.to_dict(),
            "by_provider": {k: v.to_dict() for k, v in self.by_provider.items()},
            "by_model": {k: v.to_dict() for k, v in self.by_model.items()},
            "by_client": {k: v.to_dict() for k, v in self.by_client.items()},
        }


class SavingsOrchestrator:
    """Merge per-request breakdowns into aggregates, never double-count."""

    def __init__(self) -> None:
        self._aggregate = AggregateSavings()

    @property
    def aggregate(self) -> AggregateSavings:
        return self._aggregate

    def record_request(
        self,
        breakdown: RequestSavingsBreakdown,
        *,
        provider: str | None = None,
        model: str | None = None,
        client: str | None = None,
    ) -> None:
        """Add one request to the aggregate."""
        self._aggregate.requests += 1
        self._aggregate.raw_input_tokens += breakdown.raw_input_tokens
        self._aggregate.post_cutctx_tokens += breakdown.post_cutctx_tokens
        self._aggregate.by_source.tokens.update(
            {
                k: self._aggregate.by_source.tokens.get(k, 0) + v
                for k, v in breakdown.by_source.tokens.items()
            }
        )
        self._aggregate.by_source.usd.update(
            {
                k: self._aggregate.by_source.usd.get(k, 0.0) + v
                for k, v in breakdown.by_source.usd.items()
            }
        )

        if provider:
            bucket = self._aggregate.by_provider.setdefault(provider, SavingsBySource())
            for src, n in breakdown.by_source.tokens.items():
                bucket.tokens[src] = bucket.tokens.get(src, 0) + n
            for src, u in breakdown.by_source.usd.items():
                bucket.usd[src] = bucket.usd.get(src, 0.0) + u

        if model:
            bucket = self._aggregate.by_model.setdefault(model, SavingsBySource())
            for src, n in breakdown.by_source.tokens.items():
                bucket.tokens[src] = bucket.tokens.get(src, 0) + n
            for src, u in breakdown.by_source.usd.items():
                bucket.usd[src] = bucket.usd.get(src, 0.0) + u

        if client:
            bucket = self._aggregate.by_client.setdefault(client, SavingsBySource())
            for src, n in breakdown.by_source.tokens.items():
                bucket.tokens[src] = bucket.tokens.get(src, 0) + n
            for src, u in breakdown.by_source.usd.items():
                bucket.usd[src] = bucket.usd.get(src, 0.0) + u

    def reset(self) -> None:
        self._aggregate = AggregateSavings()


__all__ = [
    "AggregateSavings",
    "SavingsOrchestrator",
]
