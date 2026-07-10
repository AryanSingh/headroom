from __future__ import annotations

import time

import pytest

from cutctx.proxy.rate_limiter import TokenBucketRateLimiter


@pytest.mark.asyncio
async def test_token_bucket_cleanup_and_stats_include_token_only_keys() -> None:
    limiter = TokenBucketRateLimiter(requests_per_minute=60, tokens_per_minute=100)

    allowed, _ = await limiter.check_tokens("token-only", 10)
    assert allowed

    async with limiter._lock:
        limiter._token_buckets["token-only"].last_update = time.time() - 601

    await limiter.check_request("request-only")
    stats = await limiter.stats()

    assert "token-only" not in limiter._token_buckets
    assert stats["active_request_keys"] == 1
    assert stats["active_token_keys"] == 0
    assert stats["active_keys"] == 1


@pytest.mark.asyncio
async def test_rate_limiter_stats_include_denied_event_counters() -> None:
    limiter = TokenBucketRateLimiter(requests_per_minute=1, tokens_per_minute=5)

    allowed, _ = await limiter.check_request("req-key")
    assert allowed is True

    allowed, wait_seconds = await limiter.check_request("req-key")
    assert allowed is False
    assert wait_seconds > 0

    allowed, _ = await limiter.check_tokens("tok-key", 3)
    assert allowed is True

    allowed, wait_seconds = await limiter.check_tokens("tok-key", 3)
    assert allowed is False
    assert wait_seconds > 0

    stats = await limiter.stats()

    assert stats["request_checks_total"] == 2
    assert stats["token_checks_total"] == 2
    assert stats["request_denied_total"] == 1
    assert stats["token_denied_total"] == 1
    assert stats["bucket_limit_denied_total"] == 0

    last_rate_limited = stats["last_rate_limited"]
    assert isinstance(last_rate_limited, dict)
    assert last_rate_limited["key"] == "tok-key"
    assert last_rate_limited["scope"] == "token"
    assert last_rate_limited["reason"] == "token_budget"
    assert last_rate_limited["wait_seconds"] > 0
    assert isinstance(last_rate_limited["timestamp"], str)
