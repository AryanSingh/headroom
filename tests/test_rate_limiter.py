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
