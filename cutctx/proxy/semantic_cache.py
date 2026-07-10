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

_SYSTEM_REMINDER_BLOCK_RE = re.compile(
    r"<system-reminder\b[^>]*>.*?</system-reminder>",
    flags=re.IGNORECASE | re.DOTALL,
)
_VOLATILE_METADATA_KEYS = frozenset(
    {
        "client_request_id",
        "conversation_id",
        "created_at",
        "date",
        "message_id",
        "nonce",
        "request_id",
        "session_id",
        "timestamp",
        "time",
        "trace_id",
        "turn_id",
        "ts",
        "updated_at",
        "user_id",
    }
)
_VOLATILE_BLOCK_TYPES = frozenset(
    {
        "system-reminder",
        "system_reminder",
        "timestamp",
        "timestamp-block",
        "timestamp_block",
    }
)
_SKIP_VALUE = object()


def _normalize_semantic_cache_text(text: str) -> str:
    cleaned = _SYSTEM_REMINDER_BLOCK_RE.sub("", text)
    return cleaned.rstrip()


def _normalize_semantic_cache_value(value: object, *, in_metadata: bool = False) -> object:
    if isinstance(value, str):
        return _normalize_semantic_cache_text(value)

    if isinstance(value, list):
        normalized_list: list[object] = []
        for item in value:
            normalized_item = _normalize_semantic_cache_value(item, in_metadata=in_metadata)
            if normalized_item is not _SKIP_VALUE:
                normalized_list.append(normalized_item)
        return normalized_list

    if isinstance(value, dict):
        block_type = value.get("type")
        if isinstance(block_type, str):
            normalized_block_type = block_type.strip().lower().replace("_", "-")
            if normalized_block_type in _VOLATILE_BLOCK_TYPES:
                return _SKIP_VALUE

        normalized_dict: dict[object, object] = {}
        for key, item in value.items():
            key_str = str(key)
            key_lower = key_str.lower()

            if key_lower == "cache_control":
                continue
            if in_metadata and key_lower in _VOLATILE_METADATA_KEYS:
                continue

            normalized_item = _normalize_semantic_cache_value(
                item,
                in_metadata=in_metadata or key_lower == "metadata",
            )
            if normalized_item is _SKIP_VALUE:
                continue

            normalized_dict[key] = normalized_item

        return normalized_dict

    return value


def normalize_semantic_cache_messages(messages: list[dict]) -> list[dict]:
    """Return a deterministic cache-key view of request messages.

    The normalizer removes request-variant annotations that do not change the
    semantic prompt content: per-call cache breakpoints, volatile reminder and
    timestamp blocks, trailing whitespace, and obvious metadata churn.
    """

    normalized = _normalize_semantic_cache_value(messages)
    if isinstance(normalized, list):
        return normalized  # best-effort normalized copy for hashing
    return messages


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
        cleaned_messages = normalize_semantic_cache_messages(
            _strip_per_call_annotations(messages)
        )

        normalized = json.dumps(
            {"model": model, "messages": cleaned_messages},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
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
