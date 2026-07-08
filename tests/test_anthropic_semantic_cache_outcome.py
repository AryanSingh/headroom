"""Regression tests for proxy response-cache attribution."""

from __future__ import annotations

from datetime import datetime

import pytest

from cutctx.proxy.models import CacheEntry
from cutctx.proxy.outcome import RequestOutcome
from cutctx.proxy.semantic_cache import SemanticCache


class TestSemanticCacheOutcomeRecording:
    """Validate cache-hit accounting used by provider handlers."""

    def test_proxy_cache_entry_tracks_tokens_saved_per_hit(self):
        entry = CacheEntry(
            response_body=b'{"ok":true}',
            response_headers={"content-type": "application/json"},
            created_at=datetime.now(),
            ttl_seconds=60,
            tokens_saved_per_hit=321,
        )

        assert entry.tokens_saved_per_hit == 321
        assert entry.hit_count == 0

    def test_request_outcome_accepts_cached_avoided_tokens(self):
        outcome = RequestOutcome(
            request_id="test-cache-hit",
            provider="anthropic",
            model="claude-3-5-sonnet",
            original_tokens=0,
            optimized_tokens=0,
            output_tokens=0,
            tokens_saved=0,
            attempted_input_tokens=0,
            from_response_cache=True,
            semantic_cache_hit=True,
            semantic_cache_avoided_tokens=321,
        )

        assert outcome.from_response_cache is True
        assert outcome.semantic_cache_hit is True
        assert outcome.semantic_cache_avoided_tokens == 321


@pytest.mark.asyncio
async def test_semantic_cache_stats_track_hits_misses_and_tokens() -> None:
    cache = SemanticCache(max_entries=2, ttl_seconds=60)
    messages = [{"role": "user", "content": "repeat this"}]
    model = "claude-test"

    assert await cache.get(messages, model) is None

    await cache.set(
        messages,
        model,
        b'{"message":"cached"}',
        {"content-type": "application/json"},
        tokens_saved=123,
    )

    cached = await cache.get(messages, model)
    assert cached is not None
    assert cached.tokens_saved_per_hit == 123

    stats = await cache.stats()
    assert stats["entries"] == 1
    assert stats["total_hits"] == 1
    assert stats["total_misses"] == 1
    assert stats["total_stores"] == 1
    assert stats["tokens_avoided"] == 123
