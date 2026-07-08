"""Shared savings-source types and request breakdown schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SavingsSource(str, Enum):
    """Canonical enumeration of savings sources."""

    PROVIDER_PROMPT_CACHE = "provider_prompt_cache"
    CUTCTX_COMPRESSION = "cutctx_compression"
    TOOL_SCHEMA_COMPACTION = "tool_schema_compaction"
    API_SURFACE_SLIMMING = "api_surface_slimming"
    SEMANTIC_CACHE = "semantic_cache"
    PREFIX_CACHE_SELF_HOSTED = "prefix_cache_self_hosted"
    MODEL_ROUTING = "model_routing"
    RTK_CLI_FILTERING = "rtk_cli_filtering"
    # WS16: tokenizer-aware normalization pre-pass. Additive enum member;
    # older consumers that don't know about it should treat it like any
    # other source and aggregate it into the total. See
    # artifacts/savings-moat-expansion-specs.md §WS16.
    NORMALIZATION = "normalization"
    # WS10: output optimization — predicted baseline output tokens vs
    # actual (see artifacts/savings-moat-expansion-specs.md §WS10).
    OUTPUT_OPTIMIZATION = "output_optimization"
    # WS11: memoization — avoided request's estimated input tokens
    # (see artifacts/savings-moat-expansion-specs.md §WS11).
    MEMOIZATION = "memoization"
    # WS13: batch routing — price delta from routing via batch queue
    # (see artifacts/savings-moat-expansion-specs.md §WS13).
    BATCH_ROUTING = "batch_routing"

    @classmethod
    def from_str(cls, value: str) -> SavingsSource:
        try:
            return cls(value)
        except ValueError:
            return cls.CUTCTX_COMPRESSION

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def description(self) -> str:
        return _DESCRIPTIONS[self]


_LABELS = {
    SavingsSource.PROVIDER_PROMPT_CACHE: "Provider Prompt Cache",
    SavingsSource.CUTCTX_COMPRESSION: "Cutctx Compression",
    SavingsSource.TOOL_SCHEMA_COMPACTION: "Tool Schema Compaction",
    SavingsSource.API_SURFACE_SLIMMING: "API Surface Slimming",
    SavingsSource.SEMANTIC_CACHE: "Semantic Cache",
    SavingsSource.PREFIX_CACHE_SELF_HOSTED: "Self-Hosted Prefix Cache",
    SavingsSource.MODEL_ROUTING: "Model Routing",
    SavingsSource.RTK_CLI_FILTERING: "RTK CLI Filtering",
    SavingsSource.NORMALIZATION: "Tokenizer Normalization",
    SavingsSource.MEMOIZATION: "Memoization",
    SavingsSource.OUTPUT_OPTIMIZATION: "Output Optimization",
    SavingsSource.BATCH_ROUTING: "Batch Routing",
}

_DESCRIPTIONS = {
    SavingsSource.PROVIDER_PROMPT_CACHE: "Tokens avoided by provider-native prompt caching.",
    SavingsSource.CUTCTX_COMPRESSION: "Tokens removed by Cutctx compression layers.",
    SavingsSource.TOOL_SCHEMA_COMPACTION: "Tokens removed by compacting repeated tool definitions.",
    SavingsSource.API_SURFACE_SLIMMING: "Tokens removed by trimming oversized tool API surfaces.",
    SavingsSource.SEMANTIC_CACHE: "Tokens avoided by semantic cache hits.",
    SavingsSource.PREFIX_CACHE_SELF_HOSTED: "Tokens avoided by self-hosted prefix caching.",
    SavingsSource.MODEL_ROUTING: "Tokens avoided or dollars saved by routing to a cheaper model.",
    SavingsSource.RTK_CLI_FILTERING: "Tokens avoided before model ingress by RTK command filtering.",
    SavingsSource.NORMALIZATION: (
        "Tokens removed by the WS16 normalization pre-pass "
        "(NFC, whitespace collapse, blob-to-CCR-pointer, decimal-precision cap). "
        "Universal 3-8% savings on tool-output content."
    ),
    SavingsSource.MEMOIZATION: (
        "Tokens avoided by serving a prior response from the tool-memoization cache. "
        "WS11: memoization attribution."
    ),
    SavingsSource.OUTPUT_OPTIMIZATION: (
        "Output tokens removed by the output optimizer (predicted baseline vs actual). "
        "WS10: output optimization attribution."
    ),
    SavingsSource.BATCH_ROUTING: (
        "Dollars saved by routing via a batch queue (e.g. 50% list-price discount). "
        "WS13: batch routing attribution."
    ),
}


@dataclass
class SavingsBySource:
    """Token and USD totals keyed by canonical source id."""

    tokens: dict[str, int] = field(default_factory=dict)
    usd: dict[str, float] = field(default_factory=dict)

    def add(
        self,
        source: SavingsSource | str,
        tokens: int = 0,
        usd: float = 0.0,
    ) -> None:
        source_name = source.value if isinstance(source, SavingsSource) else str(source)
        if tokens:
            self.tokens[source_name] = int(self.tokens.get(source_name, 0)) + int(tokens)
            if self.tokens[source_name] < 0:
                self.tokens[source_name] = 0
            if self.tokens[source_name] == 0:
                self.tokens.pop(source_name, None)
        if usd:
            self.usd[source_name] = float(self.usd.get(source_name, 0.0)) + float(usd)
            if self.usd[source_name] < 0.0:
                self.usd[source_name] = 0.0
            if abs(self.usd[source_name]) < 1e-12:
                self.usd.pop(source_name, None)

    def get_tokens(self, source: SavingsSource | str) -> int:
        source_name = source.value if isinstance(source, SavingsSource) else str(source)
        return int(self.tokens.get(source_name, 0))

    def get_usd(self, source: SavingsSource | str) -> float:
        source_name = source.value if isinstance(source, SavingsSource) else str(source)
        return float(self.usd.get(source_name, 0.0))

    @property
    def total_tokens(self) -> int:
        return sum(int(value) for value in self.tokens.values())

    @property
    def total_usd(self) -> float:
        return sum(float(value) for value in self.usd.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokens": dict(self.tokens),
            "usd": {key: round(value, 6) for key, value in self.usd.items()},
            "total_tokens": self.total_tokens,
            "total_usd": round(self.total_usd, 6),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> SavingsBySource:
        if not isinstance(payload, dict):
            return cls()

        tokens = payload.get("tokens") or {}
        usd = payload.get("usd") or {}
        if not isinstance(tokens, dict) or not isinstance(usd, dict):
            return cls()

        return cls(
            tokens={str(key): int(value) for key, value in tokens.items()},
            usd={str(key): float(value) for key, value in usd.items()},
        )


@dataclass
class RequestSavingsBreakdown:
    """Per-request savings breakdown, including raw vs optimized tokens."""

    raw_input_tokens: int = 0
    post_cutctx_tokens: int = 0
    provider_cached_tokens: int = 0
    semantic_cache_avoided_tokens: int = 0
    total_tokens_saved: int = 0
    by_source: SavingsBySource = field(default_factory=SavingsBySource)

    @property
    def has_any_savings(self) -> bool:
        return self.total_tokens_saved > 0 or self.by_source.total_tokens > 0

    def merge(self, other: RequestSavingsBreakdown) -> None:
        self.raw_input_tokens += other.raw_input_tokens
        self.post_cutctx_tokens += other.post_cutctx_tokens
        self.provider_cached_tokens += other.provider_cached_tokens
        self.semantic_cache_avoided_tokens += other.semantic_cache_avoided_tokens
        self.total_tokens_saved += other.total_tokens_saved
        for src, val in other.by_source.tokens.items():
            self.by_source.add(src, tokens=val)
        for src, val in other.by_source.usd.items():
            self.by_source.add(src, usd=val)

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

        return cls(
            raw_input_tokens=int(payload.get("raw_input_tokens") or 0),
            post_cutctx_tokens=int(payload.get("post_cutctx_tokens") or 0),
            provider_cached_tokens=int(payload.get("provider_cached_tokens") or 0),
            semantic_cache_avoided_tokens=int(payload.get("semantic_cache_avoided_tokens") or 0),
            total_tokens_saved=int(payload.get("total_tokens_saved") or 0),
            by_source=SavingsBySource.from_dict(payload.get("by_source")),
        )
