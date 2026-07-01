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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cutctx.memory.models import Memory
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


# =============================================================================
# Internal Metadata Store
# =============================================================================


@dataclass
class _IndexedMemoryMetadata:
    """Metadata stored alongside vectors for post-filtering and Memory reconstruction."""

    memory_id: str
    user_id: str
    session_id: str | None
    agent_id: str | None
    valid_until: datetime | None
    entity_refs: list[str]
    content: str
    created_at: datetime
    importance: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_memory(cls, memory: Memory) -> _IndexedMemoryMetadata:
        """Create metadata from a Memory object."""
        return cls(
            memory_id=memory.id,
            user_id=memory.user_id,
            session_id=memory.session_id,
            agent_id=memory.agent_id,
            valid_until=memory.valid_until,
            entity_refs=memory.entity_refs.copy(),
            content=memory.content,
            created_at=memory.created_at,
            importance=memory.importance,
            metadata=memory.metadata.copy() if memory.metadata else {},
        )

    def to_memory(self, embedding: np.ndarray | None = None) -> Memory:
        """Reconstruct a basic Memory object from metadata.

        Note: This creates a partial Memory with only indexed fields.
        For full Memory objects, retrieve from the MemoryStore.
        """
        return Memory(
            id=self.memory_id,
            content=self.content,
            user_id=self.user_id,
            session_id=self.session_id,
            agent_id=self.agent_id,
            valid_until=self.valid_until,
            entity_refs=self.entity_refs.copy(),
            created_at=self.created_at,
            importance=self.importance,
            embedding=embedding,
            metadata=self.metadata.copy() if self.metadata else {},
        )


# =============================================================================
# Main Backend
# =============================================================================


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
        self._keys: set[int] = set()  # Integer USearch keys currently active

        # Bidirectional ID mapping: string memory_id <-> int usearch key
        self._memory_to_key: dict[str, int] = {}
        self._key_to_memory: dict[int, str] = {}
        self._next_key: int = 0

        # Metadata store for Memory reconstruction and post-filtering
        self._metadata: dict[str, _IndexedMemoryMetadata] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _meta_path(self, index_path: Path) -> Path:
        """Return companion metadata file path for a given index path."""
        return index_path.with_suffix(index_path.suffix + ".meta.json")

    def initialize(self) -> None:
        """Load existing index from disk or create a new one."""
        import usearch.index

        with self._lock:
            if self._index is not None:
                return  # Already initialized

            if self.path and self.path.exists():
                logger.info("Loading USearch index from %s", self.path)
                self._index = usearch.index.Index.restore(str(self.path))
                idx: usearch.index.Index = self._index  # help type-narrowing
                self.ndim = idx.ndim
                try:
                    raw_keys = idx.keys  # IndexedKeys property (not callable)
                    self._keys = set(raw_keys) if raw_keys is not None else set()
                except Exception:
                    self._keys = set()
                # Restore companion metadata
                self._load_metadata()
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
                self._save_metadata(target)
                logger.info("USearch index saved to %s (%d vectors)", target, len(self._keys))

    def _save_metadata(self, index_path: Path) -> None:
        """Persist companion metadata (ID mappings, metadata dict) to disk."""
        import json

        meta: dict[str, Any] = {
            "memory_to_key": {k: v for k, v in self._memory_to_key.items()},
            "key_to_memory": {str(k): v for k, v in self._key_to_memory.items()},
            "next_key": self._next_key,
            "metadata": {
                mid: {
                    "memory_id": m.memory_id,
                    "user_id": m.user_id,
                    "session_id": m.session_id,
                    "agent_id": m.agent_id,
                    "valid_until": m.valid_until.isoformat() if m.valid_until else None,
                    "entity_refs": m.entity_refs,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                    "importance": m.importance,
                    "metadata": m.metadata,
                }
                for mid, m in self._metadata.items()
            },
        }
        meta_path = self._meta_path(index_path)
        with open(meta_path, "w") as f:
            json.dump(meta, f)

    def _load_metadata(self) -> None:
        """Restore companion metadata from disk."""
        import json
        from datetime import datetime

        if self.path is None:
            return
        meta_path = self._meta_path(self.path)
        if not meta_path.exists():
            logger.info("No companion metadata found at %s", meta_path)
            return

        with open(meta_path) as f:
            meta = json.load(f)

        self._memory_to_key = {k: int(v) for k, v in meta.get("memory_to_key", {}).items()}
        self._key_to_memory = {
            int(k): v for k, v in meta.get("key_to_memory", {}).items()
        }
        self._next_key = meta.get("next_key", 0)

        raw_metadata: dict[str, dict[str, Any]] = meta.get("metadata", {})
        self._metadata = {}
        for mid, data in raw_metadata.items():
            valid_until_raw = data.get("valid_until")
            created_at_raw = data.get("created_at")
            self._metadata[mid] = _IndexedMemoryMetadata(
                memory_id=data["memory_id"],
                user_id=data["user_id"],
                session_id=data.get("session_id"),
                agent_id=data.get("agent_id"),
                valid_until=(
                    datetime.fromisoformat(valid_until_raw) if valid_until_raw else None
                ),
                entity_refs=data.get("entity_refs", []),
                content=data.get("content", ""),
                created_at=(
                    datetime.fromisoformat(created_at_raw) if created_at_raw else datetime.now()
                ),
                importance=data.get("importance", 0.5),
                metadata=data.get("metadata", {}),
            )

    def close(self) -> None:
        """Release resources."""
        with self._lock:
            self._index = None
            self._keys.clear()
            self._memory_to_key.clear()
            self._key_to_memory.clear()
            self._metadata.clear()
            self._next_key = 0

    # ------------------------------------------------------------------
    # Internal raw-vector helpers (low-level API, kept for compatibility)
    # ------------------------------------------------------------------

    def add(self, key: int, vector: np.ndarray) -> None:
        """Add a single vector by integer key.

        Note: This is a low-level helper. Prefer the protocol-compliant
        ``index()`` method instead.

        If the key already exists in the index, this call is a no-op
        (USearch does not support duplicate keys).
        """
        import numpy as np

        with self._lock:
            if self._index is None:
                raise RuntimeError("USearch index not initialized")
            if key in self._keys:
                return  # USearch does not support duplicate keys
            vec = np.asarray(vector, dtype=np.float32).reshape(1, self.ndim)
            self._index.add(key, vec)
            self._keys.add(key)

    def add_batch(self, keys: list[int], vectors: np.ndarray) -> None:
        """Add multiple vectors by integer keys.

        Note: This is a low-level helper. Prefer the protocol-compliant
        ``index_batch()`` method instead.
        """

        with self._lock:
            if self._index is None:
                raise RuntimeError("USearch index not initialized")
            # Filter out keys that already exist in the index
            new_keys = [k for k in keys if k not in self._keys]
            if not new_keys:
                return
            # Select corresponding vectors
            indices = [i for i, k in enumerate(keys) if k not in self._keys]
            new_vectors = vectors[indices] if len(indices) > 0 else vectors
            self._index.add(new_keys, new_vectors)
            self._keys.update(new_keys)

    def search_raw(
        self,
        query: np.ndarray,
        k: int = 10,
    ) -> list[VectorSearchResult]:
        """Search for nearest neighbors using raw vector query (sync).

        Note: This is a low-level helper that accepts a raw numpy vector.
        Prefer the protocol-compliant async ``search(VectorFilter)`` method.

        Args:
            query: Query vector (ndim,).
            k: Number of results to return.

        Returns:
            List of VectorSearchResult (with partial Memory objects) sorted
            by similarity (descending).
        """
        import numpy as np

        with self._lock:
            if self._index is None:
                raise RuntimeError("USearch index not initialized")
            q = np.asarray(query, dtype=np.float32).reshape(1, self.ndim)
            matches = self._index.search(q, k)

        results: list[VectorSearchResult] = []
        for kid, dist in zip(matches.keys, matches.distances):
            kid_int = int(kid)
            if kid_int < 0:
                continue

            similarity = 1.0 - (dist / 2.0)

            # Try to reconstruct Memory from metadata
            memory_id = self._key_to_memory.get(kid_int)
            if memory_id is not None:
                meta = self._metadata.get(memory_id)
                if meta is not None:
                    memory = meta.to_memory()
                else:
                    memory = Memory(id=memory_id, content="", user_id="")
            else:
                memory = Memory(id=str(kid_int), content="", user_id="")

            results.append(
                VectorSearchResult(
                    memory=memory,
                    similarity=float(similarity),
                    rank=len(results) + 1,
                )
            )

        return results

    def remove_key(self, key: int) -> None:
        """Mark a raw integer key as removed.

        Note: This is a low-level helper. Prefer the protocol-compliant
        async ``remove(memory_id: str)`` method instead.
        """
        with self._lock:
            self._keys.discard(key)

    def count(self) -> int:
        """Return the number of vectors in the index.

        Deprecated: Use the ``size`` property instead.
        """
        with self._lock:
            return len(self._keys)

    def contains(self, key: int) -> bool:
        """Check if a raw integer key exists in the index."""
        with self._lock:
            return key in self._keys

    # ------------------------------------------------------------------
    # VectorIndex Protocol — Properties
    # ------------------------------------------------------------------

    @property
    def dimension(self) -> int:
        """Return the embedding dimension this index expects."""
        return self.ndim

    @property
    def size(self) -> int:
        """Return the number of vectors currently indexed."""
        with self._lock:
            return len(self._keys)

    # ------------------------------------------------------------------
    # VectorIndex Protocol — Indexing
    # ------------------------------------------------------------------

    async def index(self, memory: Memory) -> None:
        """Index a memory's embedding for similarity search.

        The memory must have an embedding set.

        Args:
            memory: The memory to index.

        Raises:
            ValueError: If the memory has no embedding or wrong dimension.
            RuntimeError: If the index has not been initialized.
        """
        import numpy as np

        if memory.embedding is None:
            raise ValueError(f"Memory {memory.id} has no embedding")

        embedding = np.asarray(memory.embedding, dtype=np.float32)
        if embedding.shape[0] != self.ndim:
            raise ValueError(
                f"Embedding dimension {embedding.shape[0]} does not match "
                f"index dimension {self.ndim}"
            )

        with self._lock:
            if self._index is None:
                raise RuntimeError("USearch index not initialized. Call initialize() first.")

            if memory.id in self._memory_to_key:
                # Re-indexing existing memory — discard old key, assign new
                old_key = self._memory_to_key[memory.id]
                self._key_to_memory.pop(old_key, None)
                self._keys.discard(old_key)

            # Assign next available key
            key = self._next_key
            self._next_key += 1
            vec = embedding.reshape(1, self.ndim)
            self._index.add(key, vec)
            self._keys.add(key)
            self._memory_to_key[memory.id] = key
            self._key_to_memory[key] = memory.id

            # Update metadata
            self._metadata[memory.id] = _IndexedMemoryMetadata.from_memory(memory)

    async def index_batch(self, memories: list[Memory]) -> int:
        """Index multiple memories' embeddings.

        Memories without embeddings are skipped.

        Args:
            memories: List of memories to index.

        Returns:
            Number of memories actually indexed.
        """
        import numpy as np

        indexed_count = 0
        new_keys: list[int] = []
        new_vectors: list[np.ndarray] = []

        for memory in memories:
            if memory.embedding is None:
                continue
            embedding = np.asarray(memory.embedding, dtype=np.float32)
            if embedding.shape[0] != self.ndim:
                logger.warning(
                    "Skipping memory %s: wrong embedding dimension %d (expected %d)",
                    memory.id, embedding.shape[0], self.ndim,
                )
                continue

            with self._lock:
                if self._index is None:
                    raise RuntimeError(
                        "USearch index not initialized. Call initialize() first."
                    )

                if memory.id in self._memory_to_key:
                    # Re-indexing existing memory — discard old key
                    old_key = self._memory_to_key[memory.id]
                    self._key_to_memory.pop(old_key, None)
                    self._keys.discard(old_key)

                key = self._next_key
                self._next_key += 1
                new_keys.append(key)
                new_vectors.append(embedding)
                self._memory_to_key[memory.id] = key
                self._key_to_memory[key] = memory.id

                self._metadata[memory.id] = _IndexedMemoryMetadata.from_memory(memory)
                indexed_count += 1

        if new_keys:
            vectors_arr = np.stack(new_vectors, axis=0).astype(np.float32)
            with self._lock:
                if self._index is None:
                    raise RuntimeError("USearch index not initialized")
                self._index.add(new_keys, vectors_arr)
                self._keys.update(new_keys)

        return indexed_count

    # ------------------------------------------------------------------
    # VectorIndex Protocol — Removal
    # ------------------------------------------------------------------

    async def remove(self, memory_id: str) -> bool:
        """Remove a memory from the vector index by its string ID.

        Args:
            memory_id: The unique identifier of the memory.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            key = self._memory_to_key.pop(memory_id, None)
            if key is None:
                return False
            self._key_to_memory.pop(key, None)
            self._keys.discard(key)
            self._metadata.pop(memory_id, None)
            return True

    async def remove_batch(self, memory_ids: list[str]) -> int:
        """Remove multiple memories from the vector index.

        Args:
            memory_ids: List of memory IDs to remove.

        Returns:
            Number of memories actually removed.
        """
        count = 0
        for memory_id in memory_ids:
            if await self.remove(memory_id):
                count += 1
        return count

    # ------------------------------------------------------------------
    # VectorIndex Protocol — Update
    # ------------------------------------------------------------------

    async def update_embedding(self, memory_id: str, embedding: np.ndarray) -> bool:
        """Update the embedding for an indexed memory.

        Since USearch does not support in-place updates, the old embedding
        is retained (but excluded from search results) and the new embedding
        is inserted with a fresh internal key.

        Args:
            memory_id: The unique identifier of the memory.
            embedding: The new embedding vector.

        Returns:
            True if updated, False if memory not found in index.
        """
        import numpy as np

        embedding = np.asarray(embedding, dtype=np.float32)
        if embedding.shape[0] != self.ndim:
            raise ValueError(
                f"Embedding dimension {embedding.shape[0]} does not match "
                f"index dimension {self.ndim}"
            )

        with self._lock:
            old_key = self._memory_to_key.get(memory_id)
            if old_key is None:
                return False
            if self._index is None:
                raise RuntimeError("USearch index not initialized")

            # Assign a new key and insert the new vector; the old key
            # remains in the USearch index but is removed from our
            # tracking sets so it won't appear in search results.
            new_key = self._next_key
            self._next_key += 1

            self._key_to_memory.pop(old_key, None)
            self._keys.discard(old_key)

            vec = embedding.reshape(1, self.ndim)
            self._index.add(new_key, vec)
            self._keys.add(new_key)
            self._memory_to_key[memory_id] = new_key
            self._key_to_memory[new_key] = memory_id
            return True

    # ------------------------------------------------------------------
    # VectorIndex Protocol — Search
    # ------------------------------------------------------------------

    async def search(self, filter: VectorFilter) -> list[VectorSearchResult]:
        """Search for similar memories using vector similarity.

        Args:
            filter: Vector search filter with query and constraints.

        Returns:
            List of search results sorted by similarity (descending).

        Raises:
            ValueError: If no query_vector is provided.
        """
        import numpy as np

        if filter.query_vector is None:
            if filter.query_text is not None:
                raise ValueError(
                    "query_text provided but UsearchMemoryBackend does not embed text. "
                    "Provide query_vector directly or use an Embedder first."
                )
            raise ValueError("Either query_vector or query_text must be provided")

        query_vector = np.asarray(filter.query_vector, dtype=np.float32)
        if query_vector.shape[0] != self.ndim:
            raise ValueError(
                f"Query vector dimension {query_vector.shape[0]} does not match "
                f"index dimension {self.ndim}"
            )

        with self._lock:
            if self._index is None:
                raise RuntimeError("USearch index not initialized")
            current_size = len(self._keys)
            if current_size == 0:
                return []

            # Search with buffer for post-filtering (10x to ensure enough candidates)
            k_with_buffer = min(filter.top_k * 10, current_size)
            q = query_vector.reshape(1, self.ndim)
            matches = self._index.search(q, k_with_buffer)

            results: list[VectorSearchResult] = []

            for kid, dist in zip(matches.keys, matches.distances):
                if kid < 0:
                    continue

                # Skip if not in our mappings (deleted or unmanaged key)
                memory_id = self._key_to_memory.get(int(kid))
                if memory_id is None:
                    continue

                # Skip if the key is no longer active
                if int(kid) not in self._keys:
                    continue

                similarity = 1.0 - (dist / 2.0)

                # Apply minimum similarity threshold
                if similarity < filter.min_similarity:
                    continue

                # Get metadata for post-filtering
                metadata = self._metadata.get(memory_id)
                if metadata is None:
                    continue

                # Apply scope/temporal filters
                if not self._passes_filter(metadata, filter):
                    continue

                # Reconstruct Memory from metadata
                memory = metadata.to_memory()

                results.append(
                    VectorSearchResult(
                        memory=memory,
                        similarity=float(similarity),
                        rank=0,  # Will be set after sorting
                    )
                )

                # Stop early if we have enough results
                if len(results) >= filter.top_k:
                    break

        # Sort by similarity (descending) and assign 1-indexed ranks
        results.sort(key=lambda r: r.similarity, reverse=True)
        for i, result in enumerate(results):
            result.rank = i + 1

        return results[: filter.top_k]

    # ------------------------------------------------------------------
    # Filter Helpers
    # ------------------------------------------------------------------

    def _passes_filter(
        self,
        metadata: _IndexedMemoryMetadata,
        filter: VectorFilter,
    ) -> bool:
        """Check if metadata passes all filter constraints.

        Args:
            metadata: The indexed entry metadata.
            filter: The vector filter with constraints.

        Returns:
            True if all filter constraints pass, False otherwise.
        """
        # User ID filter
        if filter.user_id is not None and metadata.user_id != filter.user_id:
            return False

        # Session ID filter
        if filter.session_id is not None and metadata.session_id != filter.session_id:
            return False

        # Agent ID filter
        if filter.agent_id is not None and metadata.agent_id != filter.agent_id:
            return False

        # Scope level filter
        if filter.scope_levels is not None:
            from cutctx.memory.models import ScopeLevel

            # Determine the memory's scope level
            if metadata.agent_id is not None:
                memory_scope = ScopeLevel.AGENT
            elif metadata.session_id is not None:
                memory_scope = ScopeLevel.SESSION
            else:
                memory_scope = ScopeLevel.USER

            if memory_scope not in filter.scope_levels:
                return False

        # Temporal filter — valid_at
        if filter.valid_at is not None:
            if metadata.valid_until is not None:
                if filter.valid_at > metadata.valid_until:
                    return False

        # Superseded filter — exclude superseded by default
        if not filter.include_superseded:
            if metadata.valid_until is not None:
                return False

        # Entity refs filter — any match suffices
        if filter.entity_refs is not None and len(filter.entity_refs) > 0:
            if not any(ref in metadata.entity_refs for ref in filter.entity_refs):
                return False

        return True
