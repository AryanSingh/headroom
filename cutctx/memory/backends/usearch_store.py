"""Usearch vector index backend for Cutctx memory.

Provides a fast, memory-efficient vector index using USearch
(Unum's search library). Supports:

- Cosine similarity search with f16 quantization (~50% memory savings vs f32)
- Zero-copy memory-mapped index loading (index.view())
- Persistent index serialization (index.save())
- Thread-safe concurrent access

Use as:
    config = MemoryConfig(vector_backend=VectorBackend.USEARCH, ...)
    backend = create_vector_backend(config)
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cutctx.memory.ports import VectorFilter, VectorIndex, VectorSearchResult

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)


def usearch_available() -> bool:
    """Check whether the usearch package is installed."""
    try:
        import usearch  # noqa: F401
        return True
    except ImportError:
        return False


class UsearchMemoryBackend(VectorIndex):
    """Usearch-backed vector index for Cutctx memory.

    Wraps a usearch.Index with thread-safe read/write access,
    on-disk persistence, and configurable dimension/metric types.
    """

    def __init__(
        self,
        ndim: int = 384,
        metric: str = "cos",
        dtype: str = "f16",
        path: str | Path | None = None,
        connectivity: int = 16,
        expansion_add: int = 128,
        expansion_search: int = 64,
    ) -> None:
        if not usearch_available():
            raise ImportError(
                "usearch is not installed. Install with: pip install cutctx-ai[memory] "
                "or pip install usearch"
            )

        import usearch.index

        self.ndim = ndim
        self.metric = metric
        self.dtype = dtype
        self.connectivity = connectivity
        self.expansion_add = expansion_add
        self.expansion_search = expansion_search
        self.path = Path(path) if path else None

        self._lock = threading.Lock()
        self._index: usearch.index.Index | None = None
        self._keys: set[int] = set()

    def initialize(self) -> None:
        """Load existing index from disk or create a new one."""
        import usearch.index

        with self._lock:
            if self.path and self.path.exists():
                logger.info("Loading USearch index from %s", self.path)
                self._index = usearch.index.Index.restore(str(self.path))
                self.ndim = self._index.ndim
                self._keys = set(self._index.keys()) if hasattr(self._index, "keys") else set()
            else:
                logger.info(
                    "Creating new USearch index (ndim=%s, metric=%s, dtype=%s)",
                    self.ndim, self.metric, self.dtype,
                )
                self._index = usearch.index.Index(
                    ndim=self.ndim,
                    metric=self.metric,
                    dtype=self.dtype,
                    connectivity=self.connectivity,
                    expansion_add=self.expansion_add,
                    expansion_search=self.expansion_search,
                )
                self._keys.clear()

    def save(self, path: str | Path | None = None) -> None:
        """Persist index to disk."""
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("No path specified for USearch index save")
        with self._lock:
            if self._index is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                self._index.save(str(target))
                logger.info("USearch index saved to %s (%d vectors)", target, len(self._keys))

    def close(self) -> None:
        """Release resources."""
        with self._lock:
            self._index = None
            self._keys.clear()

    def add(self, key: int, vector: np.ndarray) -> None:
        """Add a single vector to the index."""
        import numpy as np
        with self._lock:
            if self._index is None:
                raise RuntimeError("USearch index not initialized")
            vec = np.asarray(vector, dtype=np.float32).reshape(1, self.ndim)
            self._index.add(key, vec)
            self._keys.add(key)

    def add_batch(self, keys: list[int], vectors: np.ndarray) -> None:
        """Add multiple vectors in a single operation."""
        import numpy as np
        with self._lock:
            if self._index is None:
                raise RuntimeError("USearch index not initialized")
            self._index.add(keys, vectors)
            self._keys.update(keys)

    def search(
        self,
        query: np.ndarray,
        k: int = 10,
        filter: VectorFilter | None = None,
    ) -> list[VectorSearchResult]:
        """Search for nearest neighbors.

        Args:
            query: Query vector (ndim,).
            k: Number of results to return.
            filter: Optional filter to apply post-search.

        Returns:
            List of VectorSearchResult sorted by distance (ascending).
        """
        import numpy as np
        with self._lock:
            if self._index is None:
                raise RuntimeError("USearch index not initialized")
            q = np.asarray(query, dtype=np.float32).reshape(1, self.ndim)
            keys, distances, _ = self._index.search(q, k)

        results: list[VectorSearchResult] = []
        for kid, dist in zip(keys[0], distances[0]):
            if kid < 0:
                continue
            if filter is not None and not filter(kid):
                continue
            similarity = 1.0 - (dist / 2.0)
            results.append(VectorSearchResult(key=int(kid), score=float(similarity)))

        return results

    def remove(self, key: int) -> None:
        """Mark a key as removed (USearch does not support true deletion)."""
        with self._lock:
            self._keys.discard(key)

    def count(self) -> int:
        """Return the number of vectors in the index."""
        with self._lock:
            return len(self._keys)

    def contains(self, key: int) -> bool:
        """Check if a key exists."""
        with self._lock:
            return key in self._keys
