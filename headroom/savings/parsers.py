"""Provider-native savings parsers.

Each provider returns slightly different usage metadata that tells us how
many of the input tokens were served from the provider's native prompt
cache. This module normalizes those fields into the shared
``RequestSavingsBreakdown`` so that downstream aggregation can never
double-count tokens.

The parsers are intentionally defensive: they must never raise on a
malformed or missing usage payload. The CutCtx proxy is on the hot
path, so all functions return safe defaults and log warnings rather
than throw.
"""

from __future__ import annotations

import logging
from typing import Any

from headroom.savings.types import (
    RequestSavingsBreakdown,
    SavingsBySource,
    SavingsSource,
)

logger = logging.getLogger(__name__)


def parse_openai_savings(usage: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Parse OpenAI Chat Completions/Responses usage into a savings breakdown.

    OpenAI exposes cache hit token counts as:
    - ``prompt_tokens_details.cached_tokens`` (chat completions + responses)
    - ``input_tokens_details.cached_tokens`` (responses, snake+snake-case fields)
    """
    breakdown = RequestSavingsBreakdown()
    if not isinstance(usage, dict):
        return breakdown
    try:
        cached_tokens = 0

        prompt_details = usage.get("prompt_tokens_details") or {}
        if isinstance(prompt_details, dict):
            cached_tokens += int(prompt_details.get("cached_tokens") or 0)

        input_details = usage.get("input_tokens_details") or {}
        if isinstance(input_details, dict):
            cached_tokens += int(input_details.get("cached_tokens") or 0)

        if cached_tokens > 0:
            breakdown.provider_cached_tokens = cached_tokens
            breakdown.total_tokens_saved = cached_tokens
            breakdown.by_source.add(
                SavingsSource.PROVIDER_PROMPT_CACHE, cached_tokens
            )
    except (TypeError, ValueError) as exc:
        logger.debug("OpenAI savings parse failed: %s", exc)
    return breakdown


def parse_anthropic_savings(usage: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Parse Anthropic Messages API usage.

    Anthropic reports cache read tokens as ``cache_read_input_tokens``
    and cache creation (write) tokens as ``cache_creation_input_tokens``.
    Cache reads are the savings source; writes are observability only.
    """
    breakdown = RequestSavingsBreakdown()
    if not isinstance(usage, dict):
        return breakdown
    try:
        cached_tokens = int(usage.get("cache_read_input_tokens") or 0)
        if cached_tokens > 0:
            breakdown.provider_cached_tokens = cached_tokens
            breakdown.total_tokens_saved = cached_tokens
            breakdown.by_source.add(
                SavingsSource.PROVIDER_PROMPT_CACHE, cached_tokens
            )
    except (TypeError, ValueError) as exc:
        logger.debug("Anthropic savings parse failed: %s", exc)
    return breakdown


def parse_gemini_savings(usage_metadata: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Parse Gemini usage metadata.

    Gemini reports cached tokens as ``cachedContentTokenCount`` in
    ``usageMetadata`` (camelCase in API responses).
    """
    breakdown = RequestSavingsBreakdown()
    if not isinstance(usage_metadata, dict):
        return breakdown
    try:
        cached_tokens = int(usage_metadata.get("cachedContentTokenCount") or 0)
        if cached_tokens > 0:
            breakdown.provider_cached_tokens = cached_tokens
            breakdown.total_tokens_saved = cached_tokens
            breakdown.by_source.add(
                SavingsSource.PROVIDER_PROMPT_CACHE, cached_tokens
            )
    except (TypeError, ValueError) as exc:
        logger.debug("Gemini savings parse failed: %s", exc)
    return breakdown


def parse_bedrock_savings(usage: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Parse Bedrock invoke/Converse usage.

    Bedrock mirrors Anthropic's shape (Anthropic Claude on Bedrock):
    ``cacheReadInputTokens`` and ``cacheWriteInputTokens`` (camelCase).
    """
    breakdown = RequestSavingsBreakdown()
    if not isinstance(usage, dict):
        return breakdown
    try:
        cached_tokens = int(usage.get("cacheReadInputTokens") or 0)
        if cached_tokens > 0:
            breakdown.provider_cached_tokens = cached_tokens
            breakdown.total_tokens_saved = cached_tokens
            breakdown.by_source.add(
                SavingsSource.PROVIDER_PROMPT_CACHE, cached_tokens
            )
    except (TypeError, ValueError) as exc:
        logger.debug("Bedrock savings parse failed: %s", exc)
    return breakdown


def parse_azure_openai_savings(usage: dict[str, Any] | None) -> RequestSavingsBreakdown:
    """Azure OpenAI uses the same shape as OpenAI, plus optional
    ``prompt_tokens_details.cached_tokens`` so reuse the OpenAI parser.
    """
    return parse_openai_savings(usage)


def parse_provider_savings(
    provider: str, usage: dict[str, Any] | None
) -> RequestSavingsBreakdown:
    """Dispatch to the right parser by provider name.

    Unknown providers return an empty breakdown. Never raises.
    """
    if not usage:
        return RequestSavingsBreakdown()
    p = (provider or "").lower().strip()
    if p.startswith("openai") or p == "openai":
        return parse_openai_savings(usage)
    if p == "anthropic":
        return parse_anthropic_savings(usage)
    if p == "gemini" or p == "google":
        return parse_gemini_savings(usage)
    if p == "bedrock" or p == "aws":
        return parse_bedrock_savings(usage)
    if p == "azure" or p == "azure_openai":
        return parse_azure_openai_savings(usage)
    return RequestSavingsBreakdown()


__all__ = [
    "parse_anthropic_savings",
    "parse_azure_openai_savings",
    "parse_bedrock_savings",
    "parse_gemini_savings",
    "parse_openai_savings",
    "parse_provider_savings",
]
