"""Normalize optional savings telemetry into RequestOutcome metadata."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from cutctx.savings import SavingsSource
from cutctx.savings.integrations import (
    parse_gptcache_hit,
    parse_litellm_cache,
    parse_model_routing_metadata,
    parse_vllm_apc,
)

SAVINGS_METADATA_HEADER = "x-cutctx-savings-metadata"


def _coerce_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _coerce_float(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _header(headers: Mapping[str, Any] | None, name: str) -> Any:
    if not headers:
        return None
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return value
    return None


def _merge(
    result: dict[str, dict[str, Any]],
    source: SavingsSource | str,
    *,
    tokens: int = 0,
    usd: float = 0.0,
) -> None:
    token_count = _coerce_int(tokens)
    usd_value = _coerce_float(usd)
    if token_count <= 0 and usd_value <= 0:
        return
    source_name = source.value if isinstance(source, SavingsSource) else str(source)
    bucket = result.setdefault(source_name, {"tokens": 0, "usd": 0.0})
    bucket["tokens"] = _coerce_int(bucket.get("tokens")) + token_count
    bucket["usd"] = round(_coerce_float(bucket.get("usd")) + usd_value, 6)


def _merge_breakdown(result: dict[str, dict[str, Any]], breakdown: Any) -> None:
    by_source = getattr(breakdown, "by_source", None)
    if by_source is None:
        return
    for source in SavingsSource:
        _merge(
            result,
            source,
            tokens=by_source.get_tokens(source),
            usd=by_source.get_usd(source),
        )


def _merge_payload(result: dict[str, dict[str, Any]], payload: Any) -> None:
    if not isinstance(payload, dict):
        return

    for source in SavingsSource:
        source_payload = payload.get(source.value)
        if isinstance(source_payload, dict):
            _merge(
                result,
                source,
                tokens=source_payload.get("tokens", source_payload.get("token_count", 0)),
                usd=source_payload.get("usd", 0.0),
            )

    aliases = {
        "provider_prompt_cache": parse_litellm_cache,
        "litellm": parse_litellm_cache,
        "semantic_cache": parse_gptcache_hit,
        "gptcache": parse_gptcache_hit,
        "prefix_cache_self_hosted": parse_vllm_apc,
        "vllm_apc": parse_vllm_apc,
        "model_routing": parse_model_routing_metadata,
    }
    for alias, parser in aliases.items():
        alias_payload = payload.get(alias)
        if isinstance(alias_payload, dict):
            _merge_breakdown(result, parser(alias_payload))

    # Flat metadata shape, useful for simple proxies and harness adapters.
    _merge_breakdown(result, parse_gptcache_hit(payload))
    _merge_breakdown(result, parse_litellm_cache(payload))
    _merge_breakdown(result, parse_vllm_apc(payload))
    _merge_breakdown(result, parse_model_routing_metadata(payload))


def _merge_headers(
    result: dict[str, dict[str, Any]],
    headers: Mapping[str, Any] | None,
) -> None:
    if not headers:
        return

    raw = _header(headers, SAVINGS_METADATA_HEADER)
    if raw:
        try:
            payload = json.loads(str(raw))
        except json.JSONDecodeError:
            payload = None
        _merge_payload(result, payload)

    _merge(
        result,
        SavingsSource.PROVIDER_PROMPT_CACHE,
        tokens=_header(headers, "x-cutctx-provider-cache-tokens")
        or _header(headers, "x-cutctx-provider-cache-hit-tokens"),
    )
    _merge(
        result,
        SavingsSource.SEMANTIC_CACHE,
        tokens=_header(headers, "x-cutctx-semantic-cache-tokens")
        or _header(headers, "x-cutctx-semantic-cache-avoided-tokens"),
    )
    _merge(
        result,
        SavingsSource.PREFIX_CACHE_SELF_HOSTED,
        tokens=_header(headers, "x-cutctx-prefix-cache-hits")
        or _header(headers, "x-cutctx-self-hosted-prefix-cache-hits")
        or _header(headers, "x-cutctx-vllm-apc-hits")
        or _header(headers, "x-cutctx-vllm-apc-tokens")
        # Standard vLLM APC header aliases (Audit-Deep-2026-06-21
        # Blocker 1: enables live detection of self-hosted prefix
        # cache hits when a vLLM sidecar or proxy sets these on the
        # upstream response).
        or _header(headers, "x-vllm-prefix-cache-hits")
        or _header(headers, "vllm-prefix-cache-hits")
        or _header(headers, "x-vllm-apc-hits"),
    )
    _merge(
        result,
        SavingsSource.MODEL_ROUTING,
        tokens=_header(headers, "x-cutctx-model-routing-tokens")
        or _header(headers, "x-cutctx-model-routing-tokens-saved"),
        usd=_header(headers, "x-cutctx-model-routing-usd")
        or _header(headers, "x-cutctx-model-routing-usd-saved"),
    )


def extract_savings_metadata(
    *,
    request_headers: Mapping[str, Any] | None = None,
    response_headers: Mapping[str, Any] | None = None,
    body: Mapping[str, Any] | None = None,
) -> dict[str, dict[str, Any]] | None:
    """Return canonical per-source savings metadata from opt-in telemetry.

    The request-header path is internal and stripped before upstream calls,
    so local harnesses can report vLLM APC, semantic cache, and routing
    savings without leaking Cutctx control headers to providers.
    """
    result: dict[str, dict[str, Any]] = {}
    _merge_headers(result, request_headers)
    _merge_headers(result, response_headers)
    if isinstance(body, Mapping):
        _merge_payload(result, body.get("cutctx_savings_metadata"))
        _merge_payload(result, body.get("savings_metadata"))
    return result or None


def merge_savings_metadata(
    *metadata_items: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]] | None:
    """Add normalized savings metadata buckets without losing duplicate sources."""
    result: dict[str, dict[str, Any]] = {}
    for metadata in metadata_items:
        if not metadata:
            continue
        for source, values in metadata.items():
            if not isinstance(values, Mapping):
                continue
            _merge(
                result,
                source,
                tokens=values.get("tokens", 0),
                usd=values.get("usd", 0.0),
            )
    return result or None
