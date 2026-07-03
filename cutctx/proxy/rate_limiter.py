"""Token bucket rate limiter for the Cutctx proxy.

Rate limits request count and token usage per API key or IP address.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

from cutctx.proxy.models import RateLimitState

logger = logging.getLogger("cutctx.proxy")

# Prevent unbounded memory growth from spoofed API keys.
MAX_RATE_LIMITER_BUCKETS = 1000


class TokenBucketRateLimiter:
    """Token bucket rate limiter for requests and tokens."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        tokens_per_minute: int = 100000,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self._request_buckets: dict[str, RateLimitState] = defaultdict(
            lambda: RateLimitState(
                tokens=requests_per_minute,
                last_update=time.time(),
            )
        )
        self._token_buckets: dict[str, RateLimitState] = defaultdict(
            lambda: RateLimitState(
                tokens=tokens_per_minute,
                last_update=time.time(),
            )
        )
        self._lock = asyncio.Lock()

    async def _cleanup_stale_buckets(self) -> None:
        """Remove request and token buckets idle for more than 10 minutes."""
        now = time.time()
        stale_threshold = now - 600
        stale_request_keys = {
            key
            for key, state in self._request_buckets.items()
            if state.last_update < stale_threshold
        }
        stale_token_keys = {
            key
            for key, state in self._token_buckets.items()
            if state.last_update < stale_threshold
        }
        stale_keys = stale_request_keys | stale_token_keys

        for key in stale_keys:
            self._request_buckets.pop(key, None)
            self._token_buckets.pop(key, None)

        if stale_keys:
            logger.debug("Cleaned up %d stale rate limiter buckets", len(stale_keys))

    def _refill(self, state: RateLimitState, rate_per_minute: float) -> float:
        """Refill bucket based on elapsed time."""
        now = time.time()
        elapsed = now - state.last_update
        refill = elapsed * (rate_per_minute / 60.0)
        state.tokens = min(rate_per_minute, state.tokens + refill)
        state.last_update = now
        return state.tokens

    async def check_request(self, key: str = "default") -> tuple[bool, float]:
        """Check whether a request is allowed.

        Returns `(allowed, wait_seconds)`.
        """
        async with self._lock:
            await self._cleanup_stale_buckets()
            if len(self._request_buckets) >= MAX_RATE_LIMITER_BUCKETS:
                await self._cleanup_stale_buckets()
                if (
                    len(self._request_buckets) >= MAX_RATE_LIMITER_BUCKETS
                    and key not in self._request_buckets
                ):
                    logger.warning("Rate limiter bucket limit reached")
                    return False, 60.0

            state = self._request_buckets[key]
            available = self._refill(state, self.requests_per_minute)

            if available >= 1:
                state.tokens -= 1
                return True, 0.0

            wait_seconds = (1 - available) * (60.0 / self.requests_per_minute)
            return False, wait_seconds

    async def check_tokens(self, key: str, token_count: int) -> tuple[bool, float]:
        """Check whether a token budget draw is allowed."""
        async with self._lock:
            await self._cleanup_stale_buckets()
            if len(self._token_buckets) >= MAX_RATE_LIMITER_BUCKETS:
                await self._cleanup_stale_buckets()
                if (
                    len(self._token_buckets) >= MAX_RATE_LIMITER_BUCKETS
                    and key not in self._token_buckets
                ):
                    logger.warning("Rate limiter token bucket limit reached")
                    return False, 60.0

            state = self._token_buckets[key]
            available = self._refill(state, self.tokens_per_minute)

            if available >= token_count:
                state.tokens -= token_count
                return True, 0.0

            wait_seconds = (token_count - available) * (
                60.0 / self.tokens_per_minute
            )
            return False, wait_seconds

    async def stats(self) -> dict[str, float | int]:
        """Get rate limiter statistics."""
        async with self._lock:
            await self._cleanup_stale_buckets()
            active_keys = len(set(self._request_buckets) | set(self._token_buckets))
            return {
                "requests_per_minute": self.requests_per_minute,
                "tokens_per_minute": self.tokens_per_minute,
                "active_keys": active_keys,
                "active_request_keys": len(self._request_buckets),
                "active_token_keys": len(self._token_buckets),
            }
