"""Response-cache implementation for the Cutctx proxy.

Despite the historical module name, this is currently an exact-match response
cache keyed by normalized ``{model, messages}`` content. The stats emitted here
feed the dashboard's runtime capability cards, so we track misses, evictions,
and avoided tokens explicitly.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import OrderedDict
from datetime import datetime

from cutctx.proxy.helpers import _strip_per_call_annotations
from cutctx.proxy.models import CacheEntry
from cutctx.memory.tracker import ComponentStats


class SemanticCache:
    """Exact-match response cache with LRU eviction."""

    def __init__(self, max_entries: int = 1000, ttl_seconds: int = 3600):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._stores = 0
        self._evictions = 0
        self._expired = 0
        self._tokens_avoided = 0

    def _compute_key(self, messages: list[dict], model: str) -> str:
        """Compute a normalized cache key for a request."""
        cleaned_messages = _strip_per_call_annotations(messages)

        for msg in cleaned_messages:
            if not isinstance(msg, dict):
                continue

            metadata = msg.get("metadata")
            if isinstance(metadata, dict):
                metadata.pop("user_id", None)

            content = msg.get("content")
            if isinstance(content, str):
                content = re.sub(
                    r"<system-reminder>.*?</system-reminder>",
                    "",
                    content,
                    flags=re.DOTALL,
                )
                msg["content"] = content.strip()

        normalized = json.dumps(
            {"model": model, "messages": cleaned_messages},
            sort_keys=True,
        )
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]

    async def get(self, messages: list[dict], model: str) -> CacheEntry | None:
        """Return a cached response when present and still valid."""
        key = self._compute_key(messages, model)
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            age = (datetime.now() - entry.created_at).total_seconds()
            if age > entry.ttl_seconds:
                del self._cache[key]
                self._expired += 1
                self._misses += 1
                return None

            entry.hit_count += 1
            self._hits += 1
            self._tokens_avoided += max(0, entry.tokens_saved_per_hit)
            self._cache.move_to_end(key)
            return entry

    async def set(
        self,
        messages: list[dict],
        model: str,
        response_body: bytes,
        response_headers: dict[str, str],
        tokens_saved: int = 0,
    ) -> None:
        """Store a response in the cache."""
        key = self._compute_key(messages, model)
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

            while len(self._cache) >= self.max_entries:
                self._cache.popitem(last=False)
                self._evictions += 1

            is_stream = response_headers.get("content-type", "").startswith("text/event-stream")
            self._cache[key] = CacheEntry(
                response_body=response_body,
                response_headers=response_headers,
                created_at=datetime.now(),
                ttl_seconds=self.ttl_seconds,
                tokens_saved_per_hit=max(0, tokens_saved),
                is_streaming=is_stream,
            )
            self._stores += 1

    async def stats(self) -> dict:
        """Return cache statistics for the admin surface."""
        async with self._lock:
            total_hit_count = sum(entry.hit_count for entry in self._cache.values())
            total_saved_per_hit = sum(entry.tokens_saved_per_hit for entry in self._cache.values())
            return {
                "entries": len(self._cache),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "total_hits": self._hits,
                "total_hit_count": total_hit_count,
                "total_misses": self._misses,
                "total_stores": self._stores,
                "total_evictions": self._evictions,
                "total_expired": self._expired,
                "tokens_avoided": self._tokens_avoided,
                "tokens_saved_per_hit_capacity": total_saved_per_hit,
            }

    async def clear(self) -> None:
        """Clear all cache entries and counters."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._stores = 0
            self._evictions = 0
            self._expired = 0
            self._tokens_avoided = 0

    def get_memory_stats(self) -> ComponentStats:
        """Return a best-effort memory snapshot for the memory tracker."""
        entries = list(self._cache.values())
        size_bytes = sum(len(entry.response_body) for entry in entries)
        size_bytes += sum(len(json.dumps(entry.response_headers)) for entry in entries)
        size_bytes += sum(len(str(entry.tokens_saved_per_hit)) for entry in entries)

        return ComponentStats(
            name="semantic_cache",
            entry_count=len(entries),
            size_bytes=size_bytes,
            budget_bytes=None,
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions + self._expired,
        )
