# USearch — Fast Vector Search Backend

[**USearch**](https://github.com/unum-cloud/usearch) is Unum's high-performance vector search library. Cutctx uses it as the primary local vector index backend, providing **~10× faster semantic search** than sqlite-vec with **~50% less memory** via f16 quantization.

---

## Overview

### Why USearch?

Vector similarity search is the core of memory retrieval. Every `memory_save` creates an embedding; every `memory_recall` searches the nearest neighbors. The speed and memory efficiency of this search directly impacts proxy latency and memory capacity.

Cutctx originally shipped with `sqlite-vec` (lightweight) and `hnswlib` (fast), but both use f32 floats throughout — doubling memory and slowing search at scale. USearch replaces both as the default when installed:

| Aspect | sqlite-vec | hnswlib | USearch |
|--------|------------|---------|---------|
| **Float precision** | f32 | f32 | f16 (configurable: f32, i8) |
| **Memory per 1M vectors (384d)** | ~1.5 GB | ~1.5 GB | **~750 MB** (f16) |
| **Search latency (100K, 384d)** | ~15–25 ms | ~3–5 ms | **~1–3 ms** |
| **Index build (100K, 384d)** | ~10–20 s | ~2–5 s | **~0.5–2 s** |
| **Zero-copy load** | ❌ | ❌ | ✅ `index.view()` |
| **Deletion support** | ✅ | ❌ (rebuild) | ⚠️ Soft-delete |
| **Thread-safe** | ❌ (per-conn) | ✅ | ✅ |
| **Install** | Bundled in proxy | `pip install hnswlib` | `pip install usearch` |

### How It Fits In

USearch lives at the **vector index** layer of Cutctx's memory architecture:

```
HierarchicalMemory
    │
    ├── MemoryStore (SQLite) — CRUD + supersession
    ├── VectorIndex — USearch (or sqlite-vec, hnswlib)
    ├── TextIndex (FTS5) — full-text search
    └── Embedder — text → vector
```

The `VectorBackend` enum (`cutctx/memory/config.py`) selects which implementation to use:

| Enum | Backend | Availability |
|------|---------|-------------|
| `VectorBackend.USEARCH` | `UsearchMemoryBackend` | `pip install usearch` |
| `VectorBackend.SQLITE_VEC` | `SQLiteVectorIndex` | Bundled (proxy) or `pip install sqlite-vec` |
| `VectorBackend.HNSW` | `HNSWVectorIndex` | `pip install hnswlib` |
| `VectorBackend.EXTERNAL` | Plugin-loaded | Entry points |

---

## Architecture

### Vector Backend Hierarchy

The `AUTO` resolution chain (defined in `cutctx/memory/factory.py`):

```
VectorBackend.AUTO
    │
    ├── usearch installed? ──▶ VectorBackend.USEARCH  ✓ (fastest)
    │
    ├── sqlite-vec installed? ──▶ VectorBackend.SQLITE_VEC
    │
    └── hnswlib installed? ──▶ VectorBackend.HNSW
```

When none are installed, `AUTO` raises a descriptive error with install instructions.

### Persistence

USearch persists vectors to disk as two companion files:

```
memory.usearch              # USearch HNSW index (binary, mmap-ready)
memory.usearch.meta.json    # Companion metadata (JSON)
```

The `.usearch` file is a native USearch serialized HNSW graph. The `.meta.json` companion file stores:
- `memory_to_key` / `key_to_memory` — bidirectional mapping of string memory IDs ↔ integer USearch keys
- `next_key` — auto-increment counter for key assignment
- `metadata` — per-memory metadata (user_id, session_id, agent_id, content, timestamp, entity_refs, importance) for post-filtering without SQLite round-trips

**Zero-copy loading:** On restart, `index.restore()` memory-maps the `.usearch` file. The index is available instantly — no deserialization pass.

### Thread Safety

`UsearchMemoryBackend` uses a Python `threading.Lock` (`_lock`) to serialize all read/write operations. USearch's native index operations (add, search) are themselves thread-safe, but the lock protects the Python-side tracking structures (`_keys`, `_memory_to_key`, `_key_to_memory`, `_metadata`).

---

## Installation

USearch is an **optional extra**. It is not included in the core `cutctx-ai` install or the `[all]` bundle, keeping the base dependency footprint small.

```bash
# Recommended: install the memory group
pip install cutctx-ai[memory]    # Includes usearch + hnswlib + sqlite-vec + sentence-transformers

# Or install only USearch
pip install usearch               # Pure Python bindings, no Rust compilation
```

> **Note:** USearch is included in the `[memory]` extra but intentionally **not** in `[all]`. This keeps `[all]` lighter and avoids pulling in numpy transitively for users who don't need memory.

### Availability Check

```python
from cutctx.memory.backends.usearch_store import usearch_available

if usearch_available():
    print("USearch is installed ✓")
else:
    print("Install with: pip install usearch")
```

---

## Usage

### Automatic Selection (Recommended)

```python
from cutctx.memory import HierarchicalMemory, MemoryConfig

config = MemoryConfig(
    vector_backend=VectorBackend.AUTO,  # Picks USEARCH if installed
)
memory = await HierarchicalMemory.create(config)
```

### Explicit Selection

```python
from cutctx.memory import HierarchicalMemory, MemoryConfig, VectorBackend

config = MemoryConfig(
    vector_backend=VectorBackend.USEARCH,
    vector_dimension=384,  # Must match embedder output dimension
)
memory = await HierarchicalMemory.create(config)
```

### With the Proxy

```bash
cutctx proxy --memory   # AUTO resolves to USearch when installed
```

The proxy's `--memory` flag initializes `HierarchicalMemory` with `VectorBackend.AUTO`, which follows the resolution chain above.

### Direct API

For advanced use, access the backend directly:

```python
from cutctx.memory.backends.usearch_store import UsearchMemoryBackend

backend = UsearchMemoryBackend(
    ndim=384,
    metric="cos",
    dtype="f16",
    path="./my_index.usearch",
    connectivity=16,
    expansion_add=128,
    expansion_search=64,
)
backend.initialize()

# Add vectors
import numpy as np
backend.add(1, np.random.randn(384).astype(np.float32))

# Search
results = backend.search_raw(
    np.random.randn(384).astype(np.float32),
    k=10,
)
for r in results:
    print(f"Key: {r.memory.id}, Similarity: {r.similarity:.4f}")

# Persist
backend.save()
backend.close()
```

---

## Configuration

### USearch-Specific Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ndim` | 384 | Embedding dimension (must match embedder output; 384 for `BAAI/bge-small-en-v1.5`) |
| `metric` | `"cos"` | Distance metric: `"cos"` (cosine), `"l2sq"` (squared L2), `"ip"` (inner product) |
| `dtype` | `"f16"` | Quantization: `"f16"` (16-bit float, recommended), `"f32"` (full precision), `"i8"` (8-bit integer) |
| `connectivity` | 16 | HNSW graph connectivity (M parameter); higher = more accurate, more memory |
| `expansion_add` | 128 | HNSW ef_construction; higher = better recall during index build |
| `expansion_search` | 64 | HNSW ef_search; higher = better recall during search |

These are configurable via `MemoryConfig`:

```python
from cutctx.memory import MemoryConfig, VectorBackend

config = MemoryConfig(
    vector_backend=VectorBackend.USEARCH,
    vector_dimension=384,   # → ndim
    # USearch-specific params are defaulted in UsearchMemoryBackend:
    # dtype="f16", connectivity=16, expansion_add=128, expansion_search=64
)
```

### Via MemoryConfig (inherited)

| MemoryConfig Field | Maps To | Default | Description |
|--------------------|---------|---------|-------------|
| `vector_dimension` | `ndim` | 384 | Embedding dimension |
| `vector_db_path` | `path` | `{db_path}.usearch` | Path to the USearch index file |
| `db_path` | path derivation | `cutctx_memory.db` | Base path; `.usearch` suffix appended for the index |

---

## Limitations

### No True Deletion

USearch's HNSW index does not support native vector deletion. `UsearchMemoryBackend` emulates deletion by:

1. Removing the key from the internal `_keys` tracking set
2. Removing the memory_id from `_memory_to_key` / `_key_to_memory` mappings
3. Filtering out tracked-but-removed keys at search time

The vector data remains in the USearch index file. It is invisible to search results but still occupies disk space. To physically reclaim space, you must **rebuild the index**:

```python
# Rebuild to reclaim space from deleted vectors
backend.save()                     # Save current state
backend.close()                    # Close old index
backend.initialize()               # Re-open — still has stale data
# To truly rebuild, create a fresh index and re-index remaining memories
```

This is the same limitation shared by hnswlib and most HNSW implementations.

### Dimension Mismatch

The `ndim` parameter **must match** the output dimension of your embedder. If using `BAAI/bge-small-en-v1.5` (the default), this is 384. If using OpenAI's `text-embedding-3-small` (1536 dimensions), set `vector_dimension=1536`:

```python
config = MemoryConfig(
    vector_backend=VectorBackend.USEARCH,
    vector_dimension=1536,  # Match OpenAI embedding dimension
)
```

A mismatch raises `ValueError` at index/query time.

### No Query-Time Embedding

`UsearchMemoryBackend` does **not** embed text. It requires a pre-computed `query_vector` in the `VectorFilter`. The `HierarchicalMemory` orchestrator handles embedding before calling the vector backend. If you use the backend directly, you must embed first.

---

## Implementation Details

### File: `cutctx/memory/backends/usearch_store.py`

The `UsearchMemoryBackend` class implements the `VectorIndex` protocol (`cutctx/memory/ports.py`):

| Method | Description |
|--------|-------------|
| `initialize()` | Load existing index from disk or create a new empty one |
| `index(memory)` | Index a single Memory by its embedding (protocol method) |
| `index_batch(memories)` | Index multiple memories in batch |
| `search(filter)` | Protocol-compliant async search with post-filtering |
| `search_raw(query, k)` | Low-level synchronous nearest-neighbor search |
| `remove(memory_id)` | Soft-delete a memory by string ID |
| `remove_batch(memory_ids)` | Soft-delete multiple memories |
| `update_embedding(memory_id, emb)` | Replace a memory's embedding (soft-delete old, add new) |
| `save(path)` | Persist index + companion metadata to disk |
| `close()` | Release resources |
| `dimension` | Embedding dimension (property) |
| `size` | Number of active vectors (property) |

### File: `cutctx/memory/factory.py`

Routing logic in `create_vector_backend()`:

1. If `VectorBackend.USEARCH` explicitly selected but `usearch` not installed → logs warning, falls back to `AUTO`
2. If `VectorBackend.AUTO` → checks `usearch_available()`, then `SQLITE_VEC_AVAILABLE`, then `HNSW_AVAILABLE`
3. Derives index path: `config.vector_db_path or config.db_path.with_suffix(".usearch")`

### Companion Metadata

The `.meta.json` file uses USearch integer keys internally and stores the mapping to string memory IDs. This avoids relying on USearch's own label handling, which can be lossy across save/restore cycles. Serialization uses Python's `json` module — not pickle — ensuring cross-version compatibility.

```json
{
  "memory_to_key": {"mem_abc": 0, "mem_def": 1},
  "key_to_memory": {"0": "mem_abc", "1": "mem_def"},
  "next_key": 2,
  "metadata": {
    "mem_abc": {
      "memory_id": "mem_abc",
      "user_id": "alice",
      "content": "User prefers Python",
      "importance": 0.8,
      ...
    }
  }
}
```

---

## Performance Benchmarks

Measured on Apple M3 Max (64 GB), 384d vectors, cosine metric:

| Dataset Size | sqlite-vec | hnswlib | USearch (f16) | USearch (f32) |
|-------------|-----------|---------|---------------|---------------|
| 1,000 | ~2 ms | ~1 ms | **<1 ms** | <1 ms |
| 10,000 | ~5 ms | ~2 ms | **~1 ms** | ~1 ms |
| 100,000 | ~20 ms | ~4 ms | **~2 ms** | ~3 ms |
| 1,000,000 | ~150 ms | ~12 ms | **~5 ms** | ~8 ms |

Memory usage (100K, 384d):

| Backend | Memory | Relative |
|---------|--------|----------|
| sqlite-vec | ~150 MB | 1× |
| hnswlib | ~150 MB | 1× |
| USearch f32 | ~150 MB | 1× |
| **USearch f16** | **~75 MB** | **0.5×** |

> **Note:** Benchmarks are indicative. Actual performance depends on dataset characteristics, query distribution, HNSW parameters, and hardware.

---

## Troubleshooting

### "usearch is not installed"

```
ImportError: usearch is not installed. Install with: pip install cutctx-ai[memory] or pip install usearch
```

**Fix:** `pip install usearch` or `pip install cutctx-ai[memory]`

### "USearch index not initialized"

```
RuntimeError: USearch index not initialized. Call initialize() first.
```

**Fix:** Call `backend.initialize()` before any `add`, `search`, or `save` operation. When using `HierarchicalMemory.create()`, initialization is handled automatically.

### Companion metadata missing on restart

```
INFO: No companion metadata found at /path/to/index.usearch.meta.json
```

This is expected on first run after an upgrade or when migrating from a USearch index that was created without the companion metadata system. Existing vectors remain searchable, but all returned Memory objects will have empty content fields until re-indexed. Run `memory._reindex_all()` or delete the `.usearch` file and let the index rebuild.

### "No vector index backend available"

```
ValueError: No vector index backend available for memory. Install one:
  pip install usearch       (fast, memory-efficient, recommended)
  pip install sqlite-vec    (lightweight, SQLite-based)
  pip install hnswlib       (alternative)
```

**Fix:** Install at least one vector backend. `pip install usearch` is recommended.
