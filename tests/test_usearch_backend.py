"""Tests for UsearchMemoryBackend vector index.

Tests verify the low-level vector API (add/search/remove/count/contains)
against the UsearchMemoryBackend implementation. All tests are guarded by
a skipif that checks whether the ``usearch`` package is installed.
"""

from __future__ import annotations

import numpy as np
import pytest

from cutctx.memory.backends.usearch_store import usearch_available, UsearchMemoryBackend


_skip_if_no_usearch = pytest.mark.skipif(
    not usearch_available(), reason="usearch not installed"
)


@_skip_if_no_usearch
class TestUsearchMemoryBackend:
    """Tests for UsearchMemoryBackend using the raw vector API."""

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

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_initialize_creates_empty_index(self, backend):
        """After initialization, the index has zero vectors."""
        assert backend.count() == 0

    def test_add_and_search(self, backend):
        """Adding a single vector makes it the top search result."""
        vec = np.random.randn(8).astype(np.float32)
        backend.add(1, vec)
        results = backend.search(vec, k=5)
        assert len(results) == 1
        assert results[0].key == 1
        assert results[0].score > 0.99

    def test_add_batch_100_vectors(self, backend):
        """Batch-adding 100 vectors yields count == 100."""
        n = 100
        vectors = np.random.randn(n, 8).astype(np.float32)
        backend.add_batch(list(range(n)), vectors)
        assert backend.count() == n

    def test_search_returns_top_k(self, backend):
        """``search(..., k=5)`` returns at most 5 results."""
        vectors = np.random.randn(50, 8).astype(np.float32)
        backend.add_batch(list(range(50)), vectors)
        results = backend.search(vectors[0], k=5)
        assert len(results) <= 5
        assert len(results) > 0

    def test_cosine_similarity(self, backend, unit_vector):
        """An identical vector query returns a similarity ≈ 1.0."""
        backend.add(1, unit_vector)
        results = backend.search(unit_vector, k=1)
        assert len(results) == 1
        assert results[0].score == pytest.approx(1.0, abs=1e-5)

    def test_remove_marks_key(self, backend, unit_vector):
        """After removal, the removed key is excluded from search results."""
        # Two orthogonal unit vectors
        vec_a = unit_vector
        vec_b = np.zeros(8, dtype=np.float32)
        vec_b[1] = 1.0

        backend.add(1, vec_a)
        backend.add(2, vec_b)
        backend.remove(1)

        results = backend.search(vec_a, k=5)
        keys = {r.key for r in results}
        assert 1 not in keys

    def test_contains(self, backend):
        """``contains`` reflects the logical membership."""
        vec = np.random.randn(8).astype(np.float32)
        backend.add(42, vec)
        assert backend.contains(42) is True
        backend.remove(42)
        assert backend.contains(42) is False

    def test_count_matches_unique_keys(self, backend):
        """``count()`` reflects the number of unique keys."""
        n = 10
        vectors = np.random.randn(n, 8).astype(np.float32)
        backend.add_batch(list(range(n)), vectors)
        assert backend.count() == n

        backend.remove(0)
        backend.remove(1)
        assert backend.count() == n - 2

        # Re-add with a new key
        backend.add(99, vectors[0])
        assert backend.count() == n - 1  # n - 2 removed + 1 new = 9

    def test_save_and_restore(self, tmp_path, unit_vector):
        """Persisting to disk and reloading preserves vectors."""
        path = tmp_path / "persist.usearch"

        # --- first session ---
        backend1 = UsearchMemoryBackend(ndim=8, path=path)
        backend1.initialize()
        backend1.add(1, unit_vector)
        backend1.save()
        assert backend1.count() == 1
        backend1.close()

        # --- second session (reload) ---
        backend2 = UsearchMemoryBackend(ndim=8, path=path)
        backend2.initialize()
        assert backend2.count() == 1
        assert backend2.contains(1) is True

        results = backend2.search(unit_vector, k=1)
        assert len(results) == 1
        assert results[0].key == 1
        assert results[0].score == pytest.approx(1.0, abs=1e-5)
        backend2.close()

    def test_not_initialized_raises(self, tmp_path):
        """Calling ``search`` before ``initialize`` raises RuntimeError."""
        backend = UsearchMemoryBackend(ndim=8, path=tmp_path / "fail.usearch")
        with pytest.raises(RuntimeError, match="not initialized"):
            backend.search(np.random.randn(8).astype(np.float32), k=5)

    def test_dimension_mismatch(self, backend):
        """Adding a vector with the wrong ndim raises an error."""
        wrong_vec = np.random.randn(4).astype(np.float32)
        with pytest.raises((ValueError, Exception), match="(?i)dimension|reshape|size"):
            backend.add(1, wrong_vec)
