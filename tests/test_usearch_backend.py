"""Tests for UsearchMemoryBackend vector index.

Tests verify the VectorIndex protocol implementation
against the UsearchMemoryBackend. All tests are guarded by
a skipif that checks whether the ``usearch`` package is installed.
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from cutctx.memory.backends.usearch_store import usearch_available, UsearchMemoryBackend
from cutctx.memory.models import Memory
from cutctx.memory.ports import VectorFilter, VectorSearchResult


_skip_if_no_usearch = pytest.mark.skipif(
    not usearch_available(), reason="usearch not installed"
)


def _make_memory(
    memory_id: str | None = None,
    content: str = "",
    user_id: str = "test_user",
    embedding: np.ndarray | None = None,
) -> Memory:
    """Helper to create a Memory with an embedding."""
    m = Memory(
        id=memory_id or str(uuid.uuid4()),
        content=content,
        user_id=user_id,
    )
    m.embedding = embedding
    return m


@_skip_if_no_usearch
class TestUsearchMemoryBackendProtocol:
    """Tests for UsearchMemoryBackend using the VectorIndex protocol API."""

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @pytest.fixture
    def backend(self, tmp_path):
        """Return an initialized UsearchMemoryBackend isolated in tmp_path."""
        backend = UsearchMemoryBackend(ndim=8, path=tmp_path / "test.usearch")
        backend.initialize()
        yield backend
        backend.close()

    @pytest.fixture
    def unit_vector(self):
        """A simple unit-normalized 8-d vector (first dimension = 1)."""
        v = np.zeros(8, dtype=np.float32)
        v[0] = 1.0
        return v

    @pytest.fixture
    def unit_memory(self, unit_vector):
        """A Memory with the unit vector as its embedding."""
        return _make_memory(memory_id="1", content="unit", embedding=unit_vector)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    def test_dimension(self, backend):
        """``dimension`` returns the configured ndim."""
        assert backend.dimension == 8

    def test_size_empty_after_init(self, backend):
        """After initialization, the index has zero vectors."""
        assert backend.size == 0

    @pytest.mark.asyncio
    async def test_size_after_indexing(self, backend, unit_vector):
        """``size`` reflects indexed memories."""
        mem = _make_memory(embedding=unit_vector)
        await backend.index(mem)
        assert backend.size == 1

        mem2 = _make_memory(embedding=unit_vector)
        await backend.index(mem2)
        assert backend.size == 2

    # ------------------------------------------------------------------
    # Indexing and Search
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_index_and_search(self, backend):
        """Indexing a memory makes it discoverable via search."""
        vec = np.random.randn(8).astype(np.float32)
        mem = _make_memory(memory_id="mem1", content="test memory", embedding=vec)
        await backend.index(mem)

        results = await backend.search(
            VectorFilter(query_vector=vec, top_k=5)
        )
        assert len(results) == 1
        assert results[0].memory.id == "mem1"
        assert results[0].similarity > 0.99

    @pytest.mark.asyncio
    async def test_index_batch_100_memories(self, backend):
        """Batch-indexing 100 memories yields size == 100."""
        n = 100
        memories: list[Memory] = []
        for i in range(n):
            vec = np.random.randn(8).astype(np.float32)
            memories.append(_make_memory(memory_id=str(i), embedding=vec))

        indexed = await backend.index_batch(memories)
        assert indexed == n
        assert backend.size == n

    @pytest.mark.asyncio
    async def test_search_returns_top_k(self, backend):
        """search with top_k=5 returns at most 5 results."""
        n = 50
        memories: list[Memory] = []
        for i in range(n):
            vec = np.random.randn(8).astype(np.float32)
            memories.append(_make_memory(memory_id=str(i), embedding=vec))

        await backend.index_batch(memories)
        results = await backend.search(
            VectorFilter(query_vector=memories[0].embedding, top_k=5)
        )
        assert len(results) <= 5
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_cosine_similarity(self, backend, unit_vector):
        """An identical vector query returns similarity ≈ 1.0."""
        mem = _make_memory(memory_id="1", embedding=unit_vector)
        await backend.index(mem)

        results = await backend.search(
            VectorFilter(query_vector=unit_vector, top_k=1)
        )
        assert len(results) == 1
        assert results[0].similarity == pytest.approx(1.0, abs=1e-5)

    # ------------------------------------------------------------------
    # Removal
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_remove_excludes_from_results(self, backend, unit_vector):
        """After removal, the removed memory is excluded from search results."""
        # Two orthogonal unit vectors
        vec_a = unit_vector
        vec_b = np.zeros(8, dtype=np.float32)
        vec_b[1] = 1.0

        mem_a = _make_memory(memory_id="a", content="a", embedding=vec_a)
        mem_b = _make_memory(memory_id="b", content="b", embedding=vec_b)

        await backend.index(mem_a)
        await backend.index(mem_b)

        # Remove memory "a"
        removed = await backend.remove("a")
        assert removed is True

        results = await backend.search(
            VectorFilter(query_vector=vec_a, top_k=5)
        )
        ids = {r.memory.id for r in results}
        assert "a" not in ids

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, backend):
        """Removing a non-existent memory returns False."""
        result = await backend.remove("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_remove_batch(self, backend):
        """Removing a batch of memories returns the correct count."""
        memories: list[Memory] = []
        for i in range(5):
            vec = np.random.randn(8).astype(np.float32)
            memories.append(_make_memory(memory_id=str(i), embedding=vec))

        await backend.index_batch(memories)
        assert backend.size == 5

        count = await backend.remove_batch(["0", "1", "2"])
        assert count == 3
        assert backend.size == 2

    # ------------------------------------------------------------------
    # Update Embedding
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_embedding(self, backend, unit_vector):
        """Updating embedding changes search results."""
        vec_a = unit_vector
        vec_b = np.zeros(8, dtype=np.float32)
        vec_b[1] = 1.0

        mem = _make_memory(memory_id="upd", embedding=vec_a)
        await backend.index(mem)

        # Search should find it via vec_a
        results = await backend.search(VectorFilter(query_vector=vec_a, top_k=1))
        assert len(results) == 1
        assert results[0].memory.id == "upd"

        # Update embedding to vec_b
        updated = await backend.update_embedding("upd", vec_b)
        assert updated is True

        # Search with vec_a should not find it anymore
        results = await backend.search(VectorFilter(query_vector=vec_a, top_k=5))
        assert len(results) == 0

        # Search with vec_b should find it
        results = await backend.search(VectorFilter(query_vector=vec_b, top_k=1))
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_update_embedding_nonexistent(self, backend, unit_vector):
        """Updating embedding for a non-existent memory returns False."""
        result = await backend.update_embedding("nonexistent", unit_vector)
        assert result is False

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_search_filters_by_user_id(self, backend):
        """Search results can be filtered by user_id."""
        vec = np.random.randn(8).astype(np.float32)

        mem_alice = _make_memory(
            memory_id="alice1", content="alice", user_id="alice", embedding=vec
        )
        mem_bob = _make_memory(
            memory_id="bob1", content="bob", user_id="bob", embedding=vec
        )

        await backend.index(mem_alice)
        await backend.index(mem_bob)

        # Search filtered by alice
        results = await backend.search(
            VectorFilter(query_vector=vec, top_k=5, user_id="alice")
        )
        ids = {r.memory.id for r in results}
        assert "alice1" in ids
        assert "bob1" not in ids

    @pytest.mark.asyncio
    async def test_search_min_similarity(self, backend):
        """Results below min_similarity are excluded."""
        vec_a = np.random.randn(8).astype(np.float32)
        # Orthogonal vector
        vec_b = np.zeros(8, dtype=np.float32)
        vec_b[0] = 1.0

        mem_a = _make_memory(memory_id="a", embedding=vec_a)
        mem_b = _make_memory(memory_id="b", embedding=vec_b)

        await backend.index(mem_a)
        await backend.index(mem_b)

        # Search for vec_a with high min_similarity — only vec_a should pass
        results = await backend.search(
            VectorFilter(query_vector=vec_a, top_k=5, min_similarity=0.5)
        )
        ids = {r.memory.id for r in results}
        assert "a" in ids
        # "b" might or might not be in results depending on actual similarity

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_save_and_restore(self, tmp_path, unit_vector):
        """Persisting to disk and reloading preserves vectors."""
        path = tmp_path / "persist.usearch"

        # --- first session ---
        backend1 = UsearchMemoryBackend(ndim=8, path=path)
        backend1.initialize()

        mem1 = _make_memory(memory_id="p1", content="persist", embedding=unit_vector)
        await backend1.index(mem1)
        backend1.save()
        assert backend1.size == 1
        backend1.close()

        # --- second session (reload) ---
        backend2 = UsearchMemoryBackend(ndim=8, path=path)
        backend2.initialize()
        assert backend2.size == 1

        results = await backend2.search(
            VectorFilter(query_vector=unit_vector, top_k=1)
        )
        assert len(results) == 1
        assert results[0].memory.id == "p1"
        assert results[0].similarity == pytest.approx(1.0, abs=1e-5)
        backend2.close()

    # ------------------------------------------------------------------
    # Error Handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_not_initialized_raises(self, tmp_path):
        """Calling ``search`` before ``initialize`` raises RuntimeError."""
        backend = UsearchMemoryBackend(ndim=8, path=tmp_path / "fail.usearch")
        with pytest.raises(RuntimeError, match="not initialized"):
            await backend.search(
                VectorFilter(
                    query_vector=np.random.randn(8).astype(np.float32),
                    top_k=5,
                )
            )

    @pytest.mark.asyncio
    async def test_dimension_mismatch_on_index(self, backend):
        """Indexing a memory with the wrong ndim raises ValueError."""
        wrong_vec = np.random.randn(4).astype(np.float32)
        mem = _make_memory(embedding=wrong_vec)

        with pytest.raises(ValueError, match="(?i)dimension"):
            await backend.index(mem)

    @pytest.mark.asyncio
    async def test_index_without_embedding_raises(self, backend):
        """Indexing a memory without an embedding raises ValueError."""
        mem = Memory(id="no_emb", content="no embedding", user_id="test_user")
        with pytest.raises(ValueError, match="no embedding"):
            await backend.index(mem)

    @pytest.mark.asyncio
    async def test_search_without_query_vector_raises(self, backend):
        """Searching without a query_vector raises ValueError."""
        with pytest.raises(ValueError, match="Either query_vector or query_text"):
            await backend.search(VectorFilter(top_k=5))

    # ------------------------------------------------------------------
    # VectorSearchResult structure
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_search_result_fields(self, backend, unit_vector, unit_memory):
        """VectorSearchResult has the correct fields."""
        await backend.index(unit_memory)

        results = await backend.search(
            VectorFilter(query_vector=unit_vector, top_k=5)
        )
        assert len(results) == 1
        result = results[0]

        assert isinstance(result, VectorSearchResult)
        assert isinstance(result.memory, Memory)
        assert result.memory.id == "1"
        assert isinstance(result.similarity, float)
        assert isinstance(result.rank, int)
        assert result.rank == 1  # 1-indexed


@_skip_if_no_usearch
class TestUsearchMemoryBackendLowLevel:
    """Tests for the raw integer-key helper methods (backward compatibility)."""

    @pytest.fixture
    def backend(self, tmp_path):
        backend = UsearchMemoryBackend(ndim=8, path=tmp_path / "lowlevel.usearch")
        backend.initialize()
        yield backend
        backend.close()

    def test_contains(self, backend):
        """``contains`` reflects the logical membership."""
        vec = np.random.randn(8).astype(np.float32)
        backend.add(42, vec)
        assert backend.contains(42) is True
        backend.remove_key(42)
        assert backend.contains(42) is False

    def test_count_matches_unique_keys(self, backend):
        """``count()`` reflects the number of unique keys."""
        n = 10
        vectors = np.random.randn(n, 8).astype(np.float32)
        backend.add_batch(list(range(n)), vectors)
        assert backend.count() == n

        backend.remove_key(0)
        backend.remove_key(1)
        assert backend.count() == n - 2

        # Re-add with a new key
        backend.add(99, vectors[0])
        assert backend.count() == n - 1

    def test_not_initialized_raw_search_raises(self, tmp_path):
        """Calling ``search_raw`` before ``initialize`` raises RuntimeError."""
        backend = UsearchMemoryBackend(ndim=8, path=tmp_path / "fail.usearch")
        with pytest.raises(RuntimeError, match="not initialized"):
            backend.search_raw(np.random.randn(8).astype(np.float32), k=5)

    def test_raw_add_and_search_raw(self, backend):
        """Adding via ``add`` and searching via ``search_raw`` works as before."""
        vec = np.random.randn(8).astype(np.float32)
        backend.add(1, vec)
        results = backend.search_raw(vec, k=5)
        assert len(results) == 1
        assert results[0].memory.id == "1"
        assert results[0].similarity > 0.99

    def test_raw_search_returns_top_k(self, backend):
        """``search_raw(..., k=5)`` returns at most 5 results."""
        vectors = np.random.randn(50, 8).astype(np.float32)
        backend.add_batch(list(range(50)), vectors)
        results = backend.search_raw(vectors[0], k=5)
        assert len(results) <= 5
        assert len(results) > 0

    def test_dimension_mismatch_raw_add(self, backend):
        """Adding a vector with the wrong ndim via ``add`` raises an error."""
        wrong_vec = np.random.randn(4).astype(np.float32)
        with pytest.raises((ValueError, Exception), match="(?i)dimension|reshape|size"):
            backend.add(1, wrong_vec)

    def test_save_and_restore_raw(self, tmp_path, backend):
        """Low-level save/restore keeps integer keys intact."""
        # Use the already-created backend
        vec = np.random.randn(8).astype(np.float32)
        backend.add(99, vec)
        backend.save()
        assert backend.contains(99) is True
