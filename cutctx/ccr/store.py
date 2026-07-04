"""Backward-compatible CCRStore — lightweight wrapper around BatchContextStore.

Provides the legacy ``CCRStore`` class with a simple ``put(original, ttl_seconds=300)`` /
``get(key) -> str | None`` API, delegating internally to
``BatchContextStore.store()`` / ``BatchContextStore.get()``.

Usage::

    from cutctx.ccr.store import CCRStore

    store = CCRStore()
    store.put("some payload", ttl_seconds=300)
    value = store.get("<hash-key>")   # returns str or None
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

from .batch_store import (
    DEFAULT_BATCH_CONTEXT_TTL,
    BatchContext,
    BatchContextStore,
    BatchRequestContext,
)

logger = logging.getLogger(__name__)


class CCRStore:
    """Legacy string-based CCR store backed by ``BatchContextStore``.

    Provides a simple KV interface for storing and retrieving compressed
    payloads by content hash.  Each ``put()`` wraps the payload in a
    ``BatchContext`` with a single request and stores it under an
    MD5-based key (matching the pre-``BatchContextStore`` API).
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        ttl: int = DEFAULT_BATCH_CONTEXT_TTL,
    ):
        # db_path is accepted for backward compatibility with the legacy API,
        # but is ignored because BatchContextStore is in-memory.
        self._store = BatchContextStore(ttl=ttl)
        self._ttl = ttl

    def put(self, original: str, ttl_seconds: int = 300) -> str:
        """Store a string payload and return its content-hash key.

        Args:
            original: The payload to store.
            ttl_seconds: Time-to-live in seconds (default 300).

        Returns:
            The content-hash key that can be used to retrieve the payload
            via ``get()``.
        """
        # Compute a stable key from the content (MD5 for backward compat)
        key = hashlib.md5(original.encode("utf-8")).hexdigest()[:24]

        context = BatchContext(
            batch_id=key,
            provider="ccr_store",
        )
        context.expires_at = time.time() + ttl_seconds
        context.add_request(
            BatchRequestContext(
                custom_id=key,
                messages=[{"role": "user", "content": original}],
                tools=None,
                model="",
                system_instruction=None,
            )
        )

        # Run the async store in a synchronous context
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # We're inside an async context — schedule
            asyncio.ensure_future(self._store.store(context))
        else:
            asyncio.run(self._store.store(context))

        return key

    def get(self, key: str) -> str | None:
        """Retrieve a stored payload by its content-hash key.

        Args:
            key: The content-hash key returned by ``put()``.

        Returns:
            The original string payload, or ``None`` if not found / expired.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Schedule and get result via future
            asyncio.ensure_future(self._store.get(key))
            # In an already-running loop we can't block; return None
            # so callers don't deadlock.  Production callers should use
            # the async API directly.
            logger.debug(
                "CCRStore.get() called from running event loop; "
                "returning None. Use BatchContextStore directly for async access."
            )
            return None

        context = asyncio.run(self._store.get(key))
        if context is None:
            return None
        # Return the content from the first (only) request
        for req in context.requests.values():
            for msg in req.messages:
                content = msg.get("content")
                if content:
                    return content
        return None

    def stats(self) -> dict:
        """Get store statistics.

        Delegates to the underlying BatchContextStore.

        Returns:
            A dict with keys like ``total_entries``, ``max_entries``, ``ttl_seconds``.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            logger.debug("CCRStore.stats() called from running event loop; returning empty dict.")
            return {}

        raw = asyncio.run(self._store.stats())
        # Map to the legacy CCRStore stats key names
        return {
            "total_entries": raw["total_contexts"],
            "max_entries": raw["max_contexts"],
            "ttl_seconds": raw["ttl_seconds"],
        }

    def remove(self, key: str) -> bool:
        """Remove a stored payload by key.

        Args:
            key: The content-hash key.

        Returns:
            True if removed, False if not found.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            asyncio.ensure_future(self._store.remove(key))
            return True

        return asyncio.run(self._store.remove(key))
