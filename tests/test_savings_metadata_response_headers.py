# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""Tests for the savings_metadata response-header escape hatch.

Production audit (production-audit-2026-06-20.md) §1.3 flagged that
self_hosted_prefix_cache and model_routing typed fields are zero
on the RequestOutcome, but the funnel reads the savings_metadata
escape hatch. These tests prove that real per-source values are
attributed to the correct bucket when the upstream emits the
response headers.
"""

from __future__ import annotations

from cutctx.proxy.outcome import (
    RequestOutcome,
    _build_savings_breakdown,
)
from cutctx.proxy.savings_metadata import extract_savings_metadata, merge_savings_metadata


def test_extract_from_response_headers_vllm_apc() -> None:
    """vLLM APC upstream sets x-cutctx-prefix-cache-hits; the
    extractor must attribute to prefix_cache_self_hosted.
    """
    headers = {"x-cutctx-prefix-cache-hits": "1500"}
    result = extract_savings_metadata(response_headers=headers)
    assert result is not None
    assert "prefix_cache_self_hosted" in result
    assert result["prefix_cache_self_hosted"]["tokens"] == 1500


def test_extract_from_response_headers_model_routing() -> None:
    """Model routing upstream sets x-cutctx-model-routing-tokens and
    -usd; the extractor attributes to model_routing.
    """
    headers = {
        "x-cutctx-model-routing-tokens": "2000",
        "x-cutctx-model-routing-usd": "0.05",
    }
    result = extract_savings_metadata(response_headers=headers)
    assert result is not None
    assert "model_routing" in result
    assert result["model_routing"]["tokens"] == 2000
    assert abs(result["model_routing"]["usd"] - 0.05) < 1e-6


def test_extract_combined() -> None:
    """All four sources can be set in one request and the extractor
    reports each in the right bucket.
    """
    headers = {
        "x-cutctx-provider-cache-tokens": "100",
        "x-cutctx-prefix-cache-hits": "200",
        "x-cutctx-model-routing-tokens": "300",
        "x-cutctx-model-routing-usd": "0.01",
    }
    result = extract_savings_metadata(response_headers=headers)
    assert result is not None
    assert "provider_prompt_cache" in result
    assert result["provider_prompt_cache"]["tokens"] == 100
    assert "prefix_cache_self_hosted" in result
    assert result["prefix_cache_self_hosted"]["tokens"] == 200
    assert "model_routing" in result
    assert result["model_routing"]["tokens"] == 300
    assert abs(result["model_routing"]["usd"] - 0.01) < 1e-6


def test_extract_returns_none_when_no_relevant_headers() -> None:
    """No relevant headers → None (caller can short-circuit)."""
    headers = {"content-type": "application/json", "x-trace-id": "abc"}
    assert extract_savings_metadata(response_headers=headers) is None
    assert extract_savings_metadata(response_headers={}) is None


def test_extract_handles_uppercase_headers() -> None:
    """Header lookups are case-insensitive (HTTP/1.1 RFC 7230)."""
    headers = {"X-Cutctx-Prefix-Cache-Hits": "777"}
    result = extract_savings_metadata(response_headers=headers)
    assert result is not None
    assert result["prefix_cache_self_hosted"]["tokens"] == 777


def test_extract_handles_malformed_values() -> None:
    """Malformed header values must not raise; they are coerced to 0."""
    headers = {
        "x-cutctx-prefix-cache-hits": "not-a-number",
        "x-cutctx-model-routing-usd": "NaN",
    }
    # Should not raise; should return empty buckets.
    result = extract_savings_metadata(response_headers=headers)
    # Both parse to 0 and are dropped by the extractor.
    assert result is None or all(
        v.get("tokens", 0) == 0 and v.get("usd", 0.0) == 0.0 for v in result.values()
    )


def test_funnel_attributes_savings_metadata_to_correct_sources() -> None:
    """The funnel must attribute savings_metadata to the per-source
    by_source dict, not lump everything into cutctx_compression.
    """
    outcome = RequestOutcome(
        request_id="test-1",
        provider="anthropic",
        model="claude-3-5-sonnet",
        original_tokens=1000,
        optimized_tokens=500,
        output_tokens=100,
        tokens_saved=500,
        attempted_input_tokens=1000,
        savings_metadata={
            "prefix_cache_self_hosted": {"tokens": 200},
            "model_routing": {"tokens": 100, "usd": 0.05},
        },
    )
    by_source_tokens, by_source_usd, _ = _build_savings_breakdown(outcome)
    # prefix_cache_self_hosted + model_routing tokens are subtracted
    # from the cutctx_compression residual (which started as 500).
    # The residual becomes 500 - 200 - 100 = 200.
    assert by_source_tokens.get("prefix_cache_self_hosted") == 200
    assert by_source_tokens.get("model_routing") == 100
    assert by_source_tokens.get("cutctx_compression") == 200
    assert abs(by_source_usd.get("model_routing", 0.0) - 0.05) < 1e-6


def test_merge_dedupes_duplicate_sources() -> None:
    """When request + response + body all report the same source, the
    merged result sums the values.
    """
    a = extract_savings_metadata(request_headers={"x-cutctx-prefix-cache-hits": "100"})
    b = extract_savings_metadata(response_headers={"x-cutctx-prefix-cache-hits": "200"})
    merged = merge_savings_metadata(a, b)
    assert merged is not None
    assert merged["prefix_cache_self_hosted"]["tokens"] == 300


def test_extract_aliases_supported() -> None:
    """Legacy header aliases must still work."""
    # x-cutctx-vllm-apc-hits is an alias of x-cutctx-prefix-cache-hits.
    headers = {"x-cutctx-vllm-apc-hits": "500"}
    result = extract_savings_metadata(response_headers=headers)
    assert result is not None
    assert result["prefix_cache_self_hosted"]["tokens"] == 500
