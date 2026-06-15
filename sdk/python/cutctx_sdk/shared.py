"""Thread-safe shared context for key-value storage."""

from __future__ import annotations

import threading
from typing import Any


class SharedContext:
    """Thread-safe key-value store for sharing context across operations.

    Example:
        ctx = SharedContext()
        ctx.put("project", "my-app")
        ctx.get("project")  # ("my-app", True)
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, str] = {}

    def put(self, key: str, value: str) -> None:
        """Store a key-value pair."""
        with self._lock:
            self._items[key] = value

    def get(self, key: str) -> tuple[str, bool]:
        """Retrieve a value by key. Returns (value, found)."""
        with self._lock:
            val = self._items.get(key)
            return (val, val is not None)

    def list(self) -> dict[str, str]:
        """Return a copy of all entries."""
        with self._lock:
            return dict(self._items)

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._items.clear()

    def stats(self) -> dict[str, Any]:
        """Return statistics about the shared context."""
        with self._lock:
            keys = sorted(self._items.keys())
            return {
                "entries": len(self._items),
                "keys": keys,
            }

    def __repr__(self) -> str:
        stats = self.stats()
        return f"SharedContext(entries={stats['entries']}, keys={stats['keys']!r})"
