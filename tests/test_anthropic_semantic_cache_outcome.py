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
    assert stats["total_hit_count"] == 1
    assert stats["tokens_saved_per_hit_capacity"] == 123


@pytest.mark.asyncio
async def test_semantic_cache_stats_keep_resident_aggregates_current() -> None:
    cache = SemanticCache(max_entries=1, ttl_seconds=60)
    first_messages = [{"role": "user", "content": "first"}]
    second_messages = [{"role": "user", "content": "second"}]

    await cache.set(first_messages, "claude-test", b"{}", {}, tokens_saved=50)
    assert await cache.get(first_messages, "claude-test") is not None

    await cache.set(second_messages, "claude-test", b"{}", {}, tokens_saved=80)
    stats = await cache.stats()

    # The first entry was evicted, so resident aggregates must not retain its
    # hit or savings-capacity contribution.
    assert stats["total_hits"] == 1
    assert stats["total_hit_count"] == 0
    assert stats["tokens_saved_per_hit_capacity"] == 80


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "stored_messages", "request_messages", "stored_model", "request_model", "hit"),
    [
        (
            "cache_control_only",
            [
                {
                    "role": "user",
                    "content": "repeat this",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            [{"role": "user", "content": "repeat this"}],
            "claude-test",
            "claude-test",
            True,
        ),
        (
            "timestamp_block_only",
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "repeat this"},
                        {"type": "timestamp", "timestamp": "2026-07-08T00:00:00Z"},
                    ],
                }
            ],
            [{"role": "user", "content": [{"type": "text", "text": "repeat this"}]}],
            "claude-test",
            "claude-test",
            True,
        ),
        (
            "system_reminder_only",
            [{"role": "user", "content": "repeat this"}],
            [
                {
                    "role": "user",
                    "content": "repeat this <system-reminder>ignore me</system-reminder>   ",
                }
            ],
            "claude-test",
            "claude-test",
            True,
        ),
        (
            "different_user_content",
            [{"role": "user", "content": "repeat this"}],
            [{"role": "user", "content": "something else"}],
            "claude-test",
            "claude-test",
            False,
        ),
        (
            "different_model",
            [{"role": "user", "content": "repeat this"}],
            [{"role": "user", "content": "repeat this"}],
            "claude-test",
            "claude-other",
            False,
        ),
    ],
)
async def test_semantic_cache_normalized_keys_table(
    name: str,
    stored_messages: list[dict],
    request_messages: list[dict],
    stored_model: str,
    request_model: str,
    hit: bool,
) -> None:
    cache = SemanticCache(max_entries=2, ttl_seconds=60)

    await cache.set(
        stored_messages,
        stored_model,
        b'{"message":"cached"}',
        {"content-type": "application/json"},
        tokens_saved=17,
    )

    cached = await cache.get(request_messages, request_model)

    assert (cached is not None) is hit, name
    if hit:
        assert cached is not None
        assert cached.tokens_saved_per_hit == 17
