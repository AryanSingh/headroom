"""Optional external integrations for savings orchestration.

Each integration is behind a feature flag. None of them are required
for the core path; if disabled or missing, the orchestrator simply
returns an empty breakdown.

The adapters are intentionally tiny so we can add more later
(LiteLLM, vLLM APC, GPTCache, LLMLingua, etc.) without coupling to
core code.
"""

from __future__ import annotations

import logging
from typing import Any

from headroom.savings.types import (
    RequestSavingsBreakdown,
    SavingsSource,
)

logger = logging.getLogger(__name__)


def parse_litellm_cache(metadata: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Parse LiteLLM cache hit metadata.

    LiteLLM passes through the underlying provider's usage object, so
    the cached token count lives in the same fields OpenAI/Anthropic
    use. We treat any cached token as ``provider_prompt_cache``
    because LiteLLM inherits the provider cache.
    """
    if not isinstance(metadata, dict):
        return RequestSavingsBreakdown()
    breakdown = RequestSavingsBreakdown()
    cached = int(
        metadata.get("cache_hit_tokens")
        or metadata.get("cached_tokens")
        or 0
    )
    if cached > 0:
        breakdown.provider_cached_tokens = cached
        breakdown.total_tokens_saved = cached
        breakdown.by_source.add(SavingsSource.PROVIDER_PROMPT_CACHE, cached)
    return breakdown


def parse_vllm_apc(metadata: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Parse vLLM Automatic Prefix Caching telemetry.

    vLLM APC reports ``prefix_cache_hits`` (number of tokens served
    from the prefix cache). These are self-hosted savings, so they
    go to ``prefix_cache_self_hosted`` (NOT provider_prompt_cache).
    """
    if not isinstance(metadata, dict):
        return RequestSavingsBreakdown()
    breakdown = RequestSavingsBreakdown()
    try:
        hits = int(metadata.get("prefix_cache_hits") or 0)
    except (TypeError, ValueError):
        hits = 0
    if hits > 0:
        breakdown.provider_cached_tokens = hits
        breakdown.total_tokens_saved = hits
        breakdown.by_source.add(SavingsSource.PREFIX_CACHE_SELF_HOSTED, hits)
    return breakdown


def parse_gptcache_hit(metadata: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Parse GPTCache hit metadata.

    GPTCache returns the saved prompt tokens when there's a hit. These
    are semantic-cache savings.
    """
    if not isinstance(metadata, dict):
        return RequestSavingsBreakdown()
    breakdown = RequestSavingsBreakdown()
    try:
        saved = int(
            metadata.get("saved_prompt_tokens")
            or metadata.get("tokens_avoided")
            or 0
        )
    except (TypeError, ValueError):
        saved = 0
    if saved > 0:
        breakdown.semantic_cache_avoided_tokens = saved
        breakdown.total_tokens_saved = saved
        breakdown.by_source.add(SavingsSource.SEMANTIC_CACHE, saved)
    return breakdown


def parse_model_routing_metadata(metadata: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Parse model-routing savings.

    When CutCtx routes a request to a cheaper model, the breakdown
    shows the difference between requested-model and actual-model
    costs. The caller provides ``tokens_routed`` and ``usd_saved``.
    """
    if not isinstance(metadata, dict):
        return RequestSavingsBreakdown()
    breakdown = RequestSavingsBreakdown()
    try:
        tokens = int(metadata.get("tokens_routed") or 0)
        usd = float(metadata.get("usd_saved") or 0.0)
    except (TypeError, ValueError):
        tokens, usd = 0, 0.0
    if tokens > 0 or usd > 0:
        breakdown.total_tokens_saved = tokens
        breakdown.by_source.add(SavingsSource.MODEL_ROUTING, tokens, usd)
    return breakdown


__all__ = [
    "parse_gptcache_hit",
    "parse_litellm_cache",
    "parse_model_routing_metadata",
    "parse_vllm_apc",
]
