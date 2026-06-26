"""Shared savings-source types and request breakdown schema.

Single source of truth for the five savings sources tracked by Cutctx:

    - provider_prompt_cache: provider-native prompt caching (Anthropic, OpenAI, Gemini)
    - cutctx_compression: Cutctx-internal compression (SmartCrusher, LiveZone, etc.)
    - semantic_cache: repeated-query detection and short-circuit
    - prefix_cache_self_hosted: self-hosted prefix cache (vLLM APC, etc.)
    - model_routing: cost savings from routing to a cheaper model

The ``SavingsBreakdown`` dataclass is the wire format that flows from
provider adapters through the proxy and into the durable savings tracker
and the dashboard.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SavingsSource(str, Enum):
    """Canonical enumeration of savings sources."""

    PROVIDER_PROMPT_CACHE = "provider_prompt_cache"
    CUTCTX_COMPRESSION = "cutctx_compression"
    SEMANTIC_CACHE = "semantic_cache"
    PREFIX_CACHE_SELF_HOSTED = "prefix_cache_self_hosted"
    MODEL_ROUTING = "model_routing"

    @classmethod
    def from_str(cls, value: str) -> SavingsSource:
        try:
            return cls(value)
        except ValueError:
            return SavingsSource.CUTCTX_COMPRESSION

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def description(self) -> str:
        return _DESCRIPTIONS[self]


_LABELS = {
    SavingsSource.PROVIDER_PROMPT_CACHE: "Provider Prompt Cache",
    SavingsSource.CUTCTX_COMPRESSION: "Cutctx Compression",
    SavingsSource.SEMANTIC_CACHE: "Semantic Cache",
    SavingsSource.PREFIX_CACHE_SELF_HOSTED: "Self-Hosted Prefix Cache",
    SavingsSource.MODEL_ROUTING: "Model Routing",
}

_DESCRIPTIONS = {
    SavingsSource.PROVIDER_PROMPT_CACHE: (
        "Savings from the upstream LLM provider's native prompt cache "
        "(Anthropic cache_control, OpenAI prompt caching, Gemini cachedContent)."
    ),
    SavingsSource.CUTCTX_COMPRESSION: (
        "Savings from Cutctx-internal compression (SmartCrusher, LiveZone, "
        "CodeCompressor, LogCompressor, etc.) measured at model list price."
    ),
    SavingsSource.SEMANTIC_CACHE: (
        "Tokens avoided by short-circuiting repeated or near-duplicate "
        "requests via semantic-cache lookup."
    ),
    SavingsSource.PREFIX_CACHE_SELF_HOSTED: (
        "Savings from a self-hosted prefix cache (e.g. vLLM Automatic "
        "Prefix Caching) routed through Cutctx."
    ),
    SavingsSource.MODEL_ROUTING: (
        "Savings from routing the request to a cheaper model than the "
        "user originally requested."
    ),
}


@dataclass
class SavingsBySource:
    """Per-source token and dollar savings for a single request or aggregate."""

    tokens: dict[str, int] = field(default_factory=dict)
    usd: dict[str, float] = field(default_factory=dict)

    def add(self, source: SavingsSource, tokens: int, usd: float = 0.0) -> None:
        self.tokens[source.value] = self.tokens.get(source.value, 0) + max(0, int(tokens))
        self.usd[source.value] = self.usd.get(source.value, 0.0) + max(0.0, float(usd))

    def get_tokens(self, source: SavingsSource) -> int:
        return int(self.tokens.get(source.value, 0))

    def get_usd(self, source: SavingsSource) -> float:
        return float(self.usd.get(source.value, 0.0))

    @property
    def total_tokens(self) -> int:
        return sum(self.tokens.values())

    @property
    def total_usd(self) -> float:
        return sum(self.usd.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokens": dict(self.tokens),
            "usd": {k: round(v, 6) for k, v in self.usd.items()},
            "total_tokens": self.total_tokens,
            "total_usd": round(self.total_usd, 6),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> SavingsBySource:
        if not payload:
            return cls()
        tokens = payload.get("tokens") or {}
        usd = payload.get("usd") or {}
        if not isinstance(tokens, dict) or not isinstance(usd, dict):
            return cls()
        return cls(
            tokens={str(k): int(v) for k, v in tokens.items()},
            usd={str(k): float(v) for k, v in usd.items()},
        )


@dataclass
class RequestSavingsBreakdown:
    """Per-request savings breakdown, including raw vs. optimized token counts."""

    raw_input_tokens: int = 0
    post_cutctx_tokens: int = 0
    provider_cached_tokens: int = 0
    semantic_cache_avoided_tokens: int = 0
    total_tokens_saved: int = 0
    by_source: SavingsBySource = field(default_factory=SavingsBySource)

    @property
    def has_any_savings(self) -> bool:
        return self.total_tokens_saved > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_input_tokens": int(self.raw_input_tokens),
            "post_cutctx_tokens": int(self.post_cutctx_tokens),
            "provider_cached_tokens": int(self.provider_cached_tokens),
            "semantic_cache_avoided_tokens": int(self.semantic_cache_avoided_tokens),
            "total_tokens_saved": int(self.total_tokens_saved),
            "by_source": self.by_source.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> RequestSavingsBreakdown:
        if not isinstance(payload, dict):
            return cls()
        by_source = SavingsBySource.from_dict(payload.get("by_source"))
        return cls(
            raw_input_tokens=int(payload.get("raw_input_tokens") or 0),
            post_cutctx_tokens=int(payload.get("post_cutctx_tokens") or 0),
            provider_cached_tokens=int(payload.get("provider_cached_tokens") or 0),
            semantic_cache_avoided_tokens=int(
                payload.get("semantic_cache_avoided_tokens") or 0
            ),
            total_tokens_saved=int(payload.get("total_tokens_saved") or 0),
            by_source=by_source,
        )

    def merge(self, other: RequestSavingsBreakdown) -> None:
        """Add another breakdown's values into this one (used for aggregation)."""
        self.raw_input_tokens += other.raw_input_tokens
        self.post_cutctx_tokens += other.post_cutctx_tokens
        self.provider_cached_tokens += other.provider_cached_tokens
        self.semantic_cache_avoided_tokens += other.semantic_cache_avoided_tokens
        self.total_tokens_saved += other.total_tokens_saved
        for src in SavingsSource:
            self.by_source.add(
                src,
                other.by_source.get_tokens(src),
                other.by_source.get_usd(src),
            )


__all__ = [
    "SavingsSource",
    "SavingsBySource",
    "RequestSavingsBreakdown",
    "asdict",
]
