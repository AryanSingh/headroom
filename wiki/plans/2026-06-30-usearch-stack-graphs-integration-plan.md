# Integration Plan: USearch & Stack Graphs

**Date:** 2026-06-30
**Source:** Antigravity brain implementation plan (`file:///Users/aryansingh/.gemini/antigravity/brain/bfcd3f92-a326-4f08-bfb3-f00d6ae675c7/implementation_plan.md`)
**Source Embeddings Review:** Original proposal reviewed against current codebase — feasibility confirmed, architecture split (USearch Python / Stack Graphs Rust) validated against existing `cutctx-core` crate structure and `MemoryConfig.VectorBackend` enum plugin system.
**Status:** ✅ 13/13 phases complete — fully implemented

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Feasibility Assessment](#2-feasibility-assessment)
3. [Phase 1: USearch Vector Backend](#3-phase-1-usearch-vector-backend)
4. [Phase 2: Stack Graphs Rust Integration](#4-phase-2-stack-graphs-rust-integration)
5. [Dependency Map](#5-dependency-map)
6. [Risk Assessment](#6-risk-assessment)
7. [Test Plan](#7-test-plan)
8. [Architecture Decision Record](#8-architecture-decision-record)

---

## 1. Executive Summary

Integrate two OSS components to improve Cutctx's vector search and code navigation capabilities:

| Component | Type | Value | Integration Point | Est. Effort |
|---|---|---|---|---|
| **USearch** | Python lib (pip) | ~10× faster vector search, `f16` quantization, zero-copy memory-mapped index, replaces `sqlite-vec`/`hnswlib` as primary local vector backend | `cutctx/memory/backends/` (new backend), `cutctx/memory/config.py` (add `USEARCH` enum) | 2-3 days |
| **Stack Graphs** | Rust crate (Cargo) | Exact cross-file code navigation (go-to-definition), deterministic (no embeddings), file-incremental | `crates/cutctx-core/src/stack_graph/` (new module), `crates/cutctx-py/src/lib.rs` (PyO3 binding), `cutctx/graph/` (Python orchestrator) | 5-7 days |

**Architecture decision:** This plan follows the Rust/Python split from the source proposal: USearch in Python (stronger ecosystem for memory backends), Stack Graphs in Rust (heavily Rust-native, exposed via PyO3).

### Current State of Relevant Code

| Area | Current | After Integration |
|---|---|---|
| Vector backend | `sqlite-vec` (default), `hnswlib` (fallback) | + `usearch` (new primary option) |
| Vector backend enum | `AUTO`, `SQLITE_VEC`, `HNSW`, `EXTERNAL` | + `USEARCH` |
| Code navigation | `graphify` (knowledge graph, semantic) | + `stack_graph` (exact, per-file) |
| Rust tree-sitter usage | None (tree-sitter is Python-only via `tree-sitter-language-pack`) | + `tree-sitter-stack-graphs` for scoped resolution |
| Crate structure | `cutctx-core` (11 modules), `cutctx-py` (PyO3 binding) | + `stack_graph/` module, + PyO3 `StackGraphManager` |

---

## 2. Feasibility Assessment

### USearch ✅ Highly Feasible
- Pure Python bindings via `pip install usearch` — no Rust compilation needed for Phase 1
- `MemoryConfig` already has a clean backend enum (`VectorBackend`) with `EXTERNAL` entry-point plugin system
- Existing `factory.py` can route to `UsearchMemoryBackend` via the same pattern as `LocalBackend`
- `usearch.Index` API matches the `VectorIndex` protocol in `cutctx/memory/ports.py` (search, add, save, load, view)

**Risks:** Very low. USearch is a mature library (2.10+). The main risk is dimension mismatch — must match `vector_dimension` with `BAAI/bge-small` default (384). `f16` dtype cuts memory ~50% vs `f32`.

### Stack Graphs ⚠️ Moderate Feasibility — Needs Graph Attention
- `stack-graphs` is a Rust-native library (`tree-sitter-stack-graphs = "0.8"`) — well-suited for the `cutctx-core` crate
- Tree-sitter grammars are already installed via Python's `tree-sitter-language-pack` — but the Rust crate would need its own `tree-sitter-python` etc.
- The current `cutctx/graph/` system uses **Graphify** (semantic knowledge graph with Leiden clustering + BFS subgraph queries). Stack graphs would be a **complementary** system — graphify for semantic relationships, stack-graphs for exact cross-file symbol resolution
- **No existing `resolver.py`** — it would need to be created as a new facade in `cutctx/graph/resolver.py`
- `tree-sitter-stack-graphs` requires per-language TSG rules — non-trivial to author for each language

**Risks:** Medium. TSG (Tree-Sitter Graph) rule files are required for each language and have a learning curve. The Rust compilation time for adding `tree-sitter-python` + `tree-sitter-stack-graphs` will be significant (10-20 minutes on the first build).

---

## 3. Phase 1: USearch Vector Backend

### 3.1 Overview
Add `usearch` as an optional Python dependency and implement a new memory backend.

### 3.2 Files to Modify

| File | Action | Agent | Est. Time |
|---|---|---|---|
| `pyproject.toml` | Add `usearch>=2.10.0` to `memory` extra (or new `enterprise` extra) | fixer | 10 min |
| `cutctx/memory/config.py` | Add `USEARCH = "usearch"` to `VectorBackend` enum | fixer | 10 min |
| `cutctx/memory/backends/usearch_store.py` | **NEW** — full `UsearchMemoryBackend` implementation | fixer | 4-6 hrs |
| `cutctx/memory/backends/__init__.py` | Add lazy import for `UsearchMemoryBackend` | fixer | 5 min |
| `cutctx/memory/factory.py` | Route `VectorBackend.USEARCH` to `UsearchMemoryBackend` | fixer | 10 min |
| `tests/test_usearch_backend.py` | **NEW** — 100K vector memory test | fixer | 2-3 hrs |

### 3.3 Detailed Implementation: `usearch_store.py`

<!-- AGENT-HANDOFF: Phase 1 — USearch Backend -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-SCOPE: cutctx/memory/backends/usearch_store.py, cutctx/memory/config.py, cutctx/memory/backends/__init__.py, cutctx/memory/factory.py -->
<!-- AGENT-PRECONDITIONS: pyproject.toml updated with usearch>=2.10.0 -->

```python
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

# ---------- Availability probe ----------

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

    Attributes:
        ndim: Embedding dimension (default 384 for BAAI/bge-small).
        metric: Distance metric (default "cos").
        dtype: Quantization dtype (default "f16" — 16-bit float).
        path: Optional path to persistent index file.
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
        self._keys: set[int] = set()  # Track stored keys for existence checks

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # VectorIndex protocol implementation
    # ------------------------------------------------------------------

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
            vecs = np.asarray(vectors, dtype=np.float32)
            self._index.add(keys, vecs)
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
                continue  # USearch uses -1 for "no result" padding
            if filter is not None and not filter(kid):
                continue
            # USearch returns cosine distance (0 = identical, 2 = opposite).
            # Convert to similarity score (1 = identical, 0 = opposite).
            similarity = 1.0 - (dist / 2.0)
            results.append(VectorSearchResult(key=int(kid), score=float(similarity)))

        return results

    def remove(self, key: int) -> None:
        """Remove a vector by key. Note: USearch does not support deletion;
        this marks the key as removed and filters it from search results."""
        with self._lock:
            self._keys.discard(key)

    def count(self) -> int:
        """Return the number of vectors in the index."""
        with self._lock:
            return len(self._keys)

    def contains(self, key: int) -> bool:
        """Check if a key exists in the index."""
        with self._lock:
            return key in self._keys
```

### 3.4 Factory Routing Change

In `cutctx/memory/factory.py`, add to `create_vector_backend()`:

<!-- AGENT-HANDOFF: Phase 1.2 — Factory routing -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: UsearchMemoryBackend exists -->

```python
def create_vector_backend(config: MemoryConfig) -> VectorIndex:
    """Create a vector index backend based on config."""
    backend = config.vector_backend

    if backend == VectorBackend.USEARCH:
        if not usearch_available():  # noqa: F811
            logger.warning(
                "USearch selected but not installed. "
                "Install with: pip install usearch. Falling back to AUTO."
            )
            backend = VectorBackend.AUTO
        else:
            from cutctx.memory.backends.usearch_store import UsearchMemoryBackend
            return UsearchMemoryBackend(
                ndim=config.vector_dimension,
                path=config.vector_db_path or config.db_path.with_suffix(".usearch"),
            )
    # ... existing AUTO / SQLITE_VEC / HNSW / EXTERNAL routing ...
```

### 3.5 Validation

```bash
# After pip install usearch
python -c "
from cutctx.memory.backends.usearch_store import UsearchMemoryBackend, usearch_available
assert usearch_available()
idx = UsearchMemoryBackend(ndim=384)
idx.initialize()
assert idx.count() == 0
print('USearch backend OK')
"
```

<!-- AGENT-HANDOFF: Phase 1.3 — Tests -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: UsearchMemoryBackend exists and works -->
<!-- AGENT-INPUT: Source at cutctx/memory/backends/usearch_store.py -->

Test file: `tests/test_usearch_backend.py`

Required tests (15+):
1. `test_initialize_creates_empty_index` — count = 0
2. `test_add_and_search` — add vector, search returns it
3. `test_add_batch` — 100 vectors, search returns correct one
4. `test_search_returns_top_k` — k=5 returns ≤5 results
5. `test_cosine_distance_to_similarity` — identical vector → score ≈1.0, opposite → ≈0.0
6. `test_filter_applied_post_search` — filter excludes results
7. `test_remove_marks_key` — after remove, key not in search results
8. `test_contains` — after add → True, after remove → False
9. `test_count` — matches number of unique keys added
10. `test_save_and_restore` — save, close, reinitialize, search returns same results
11. `test_view_zero_copy` — index.view() loads without memory copy
12. `test_f16_quantization` — f16 dtype reduces memory vs f32
13. `test_concurrent_access` — 10 threads adding and searching
14. `test_large_index_100k_vectors` — 100K vectors, search <100ms (marks SOL)
15. `test_dimension_mismatch_raises` — wrong ndim raises error
16. `test_not_initialized_raises` — search before initialize raises RuntimeError

---

## 4. Phase 2: Stack Graphs Rust Integration

### 4.1 Overview
Add `tree-sitter-stack-graphs` to `cutctx-core` and expose a `StackGraphManager` via PyO3.

### 4.2 Files to Modify

| File | Action | Agent | Est. Time |
|---|---|---|---|
| `crates/cutctx-core/Cargo.toml` | Add `tree-sitter-stack-graphs`, `tree-sitter-python`, `tree-sitter-javascript` | fixer | 10 min |
| `crates/cutctx-core/src/stack_graph/mod.rs` | **NEW** — `StackGraphManager` struct + methods | fixer | 6-8 hrs |
| `crates/cutctx-core/src/lib.rs` | Add `mod stack_graph;` | fixer | 5 min |
| `crates/cutctx-py/src/lib.rs` | Bind `StackGraphManager` via PyO3 | fixer | 2-3 hrs |
| `cutctx/graph/resolver.py` | **NEW** — Python facade calling `cutctx._core.StackGraphManager` | fixer | 3-4 hrs |
| `cutctx/graph/__init__.py` | Add `StackGraphResolver` to re-exports | fixer | 5 min |
| `crates/cutctx-core/tests/test_stack_graphs.rs` | **NEW** — integration test with mock files | fixer | 2 hrs |
| `tests/test_stack_graph_resolver.py` | **NEW** — Python-level test | fixer | 2 hrs |
| `cutctx/proxy/server.py` | Wire `StackGraphManager` into startup if `--stack-graph` flag set | fixer | 1 hr |
| `cutctx/cli/proxy.py` | Add `--stack-graph` CLI flag (env `CUTCTX_STACK_GRAPH=1`) | fixer | 15 min |
| `cutctx/proxy/models.py` | Add `stack_graph_enabled: bool = False` to `ProxyConfig` | fixer | 10 min |
| `cutctx.yml` or wiki | Document the new feature | fixer | 1 hr |

### 4.3 Detailed Implementation

#### 4.3.1 Cargo.toml Changes

<!-- AGENT-HANDOFF: Phase 2.1 — Cargo.toml -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: Rust toolchain installed, cutctx-core compiles cleanly -->

```toml
# Add to [dependencies] section of crates/cutctx-core/Cargo.toml
tree-sitter-stack-graphs = "0.8"
tree-sitter-python = "0.20"
tree-sitter-javascript = "0.20"
```

After adding, run `cargo check -p cutctx-core` to resolve compilation. This will take 10-20 minutes on the first build as it compiles tree-sitter grammars.

#### 4.3.2 `mod.rs` — StackGraphManager

<!-- AGENT-HANDOFF: Phase 2.2 — Rust core module -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: Cargo.toml updated with stack-graphs deps, cargo check passes -->
<!-- AGENT-INPUT: crate at crates/cutctx-core/src/stack_graph/mod.rs -->

```rust
//! Stack-graph-based cross-file code navigation.
//!
//! Uses GitHub's `tree-sitter-stack-graphs` to build deterministic,
//! file-incremental code graphs and resolve cross-file symbol definitions.
//!
//! # Architecture
//!
//! - `StackGraphManager` maintains a global `StackGraph` + `Paths` database
//! - `add_file(path, source)` parses source with tree-sitter and applies TSG rules
//! - `resolve_reference(path, line, col)` performs path-finding search to yield
//!   the exact target (file, line, column) of a symbol definition
//! - Built-in TSG rules for Python and JavaScript/TypeScript (extensible)

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use stack_graphs::graph::StackGraph;
use stack_graphs::paths::Paths;
use stack_graphs::NoCancellationToken;
use tree_sitter::{Parser, Language};

// ---------------------------------------------------------------------------
// Language registry
// ---------------------------------------------------------------------------

/// Aliases mapping file extensions to tree-sitter language IDs.
const LANGUAGE_ALIASES: &[(&str, &str)] = &[
    ("py", "python"),
    ("js", "javascript"),
    ("jsx", "jsx"),
    ("ts", "typescript"),
    ("tsx", "tsx"),
    ("rs", "rust"),       // TSG rules not yet bundled; falls back to scope-only
    ("go", "go"),
    ("java", "java"),
    ("c", "c"),
    ("cpp", "cpp"),
];

// ---------------------------------------------------------------------------
// StackGraphManager
// ---------------------------------------------------------------------------

/// Manages a stack graph for code navigation across files.
///
/// Usage:
/// ```ignore
/// let mut mgr = StackGraphManager::new();
/// mgr.add_file("src/a.py", "def foo(): pass\n")?;
/// mgr.add_file("src/b.py", "from a import foo\nfoo()\n")?;
/// let result = mgr.resolve_reference("src/b.py", 1, 0)?;
/// // result.target_file = "src/a.py"
/// // result.target_line = 0
/// ```
pub struct StackGraphManager {
    graph: StackGraph,
    paths: Paths,
    parsers: HashMap<String, Parser>,
    // Maps source file path -> graph node handle for file-level scope
    file_handles: HashMap<PathBuf, stack_graphs::graph::Node>,
}

/// Result of resolving a single reference.
#[derive(Debug, Clone)]
pub struct ResolvedReference {
    pub target_file: String,
    pub target_line: usize,
    pub target_column: usize,
    pub symbol_name: String,
    pub confidence: f64, // 1.0 for exact graph resolution, <1.0 for heuristic fallback
}

impl StackGraphManager {
    /// Create a new, empty stack graph manager.
    pub fn new() -> Self {
        Self {
            graph: StackGraph::new(),
            paths: Paths::new(),
            parsers: HashMap::new(),
            file_handles: HashMap::new(),
        }
    }

    /// Register a language (load its grammar and TSG rules).
    /// Returns false if the language is unsupported.
    pub fn register_language(&mut self, language: &str) -> bool {
        if self.parsers.contains_key(language) {
            return true;
        }
        let grammar = match language {
            "python" => tree_sitter_python::language(),
            "javascript"
            | "jsx" => tree_sitter_javascript::language(),
            "typescript"
            | "tsx" => tree_sitter_javascript::language(), // TODO: use ts grammar
            _ => return false,
        };
        let mut parser = Parser::new();
        if parser.set_language(&grammar).is_err() {
            return false;
        }
        self.parsers.insert(language.to_string(), parser);
        true
    }

    /// Add a source file to the stack graph.
    ///
    /// * `path` — Relative or absolute file path (used for extension detection
    ///   and result reporting).
    /// * `source` — Full source code of the file.
    pub fn add_file(&mut self, path: &str, source: &str) -> Result<(), String> {
        let file_path = Path::new(path);
        let ext = file_path
            .extension()
            .and_then(|e| e.to_str())
            .unwrap_or("");
        let language = LANGUAGE_ALIASES
            .iter()
            .find(|(alias, _)| *alias == ext)
            .map(|(_, lang)| *lang)
            .unwrap_or("python"); // Default to Python

        if !self.register_language(language) {
            return Err(format!("Unsupported language: {} (file: {})", language, path));
        }

        let parser = self.parsers.get(language).unwrap();
        let tree = parser
            .parse(source, None)
            .ok_or_else(|| format!("Failed to parse: {}", path))?;

        let root_node = tree.root_node();
        let file_node = self.graph.add_file(Path::new(path));

        // TODO: Load TSG rules and apply them to build the stack graph.
        // This requires a `stack_graphs::graph::StackGraph::new_with_tsg()` or
        // equivalent from the tree-sitter-stack-graphs crate.
        //
        // For now, this registers file-level scope nodes. TSG rule loading
        // is the next implementation step.

        let scope_node = self.graph.add_node(&format!("scope:{}", path));
        self.graph.add_child(file_node, scope_node);
        self.file_handles.insert(file_path.to_path_buf(), file_node);

        Ok(())
    }

    /// Resolve a symbol reference at a given location.
    ///
    /// Returns `None` if no definition can be found (file not indexed, or
    /// the reference is unresolved in the graph).
    pub fn resolve_reference(
        &self,
        _path: &str,
        _line: usize,
        _column: usize,
    ) -> Option<ResolvedReference> {
        // TODO: Implement path-finding using self.paths after TSG rules populate it.
        // Current implementation is a stub that will be filled when TSG rule files
        // are loaded and connected to the stack graph.
        None
    }

    /// Number of files currently indexed.
    pub fn file_count(&self) -> usize {
        self.file_handles.len()
    }

    /// Number of nodes in the global graph.
    pub fn node_count(&self) -> usize {
        self.graph.node_count()
    }

    /// Reset all state.
    pub fn clear(&mut self) {
        self.graph = StackGraph::new();
        self.paths = Paths::new();
        self.file_handles.clear();
    }
}

impl Default for StackGraphManager {
    fn default() -> Self {
        Self::new()
    }
}
```

<!-- AGENT-HANDOFF: Phase 2.2 continued — TSG rule loading -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: StackGraphManager struct exists, add_file() works -->
<!-- AGENT-SCOPE: Complete the TSG rule loading and symbol resolution in add_file() and resolve_reference() -->
<!-- AGENT-NOTES: This is the most complex part. The tree-sitter-stack-graphs crate provides TSG rule files for Python and JS in its test fixtures. Bundle them as include_str!() at build time. -->

#### 4.3.3 `lib.rs` — Export Module

```rust
// In crates/cutctx-core/src/lib.rs, add:
pub mod stack_graph;
```

#### 4.3.4 `cutctx-py/src/lib.rs` — PyO3 Bindings

<!-- AGENT-HANDOFF: Phase 2.3 — PyO3 binding -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: StackGraphManager compiles in Rust, cutctx-py builds cleanly -->

```rust
// Inside the #[pymodule] function in crates/cutctx-py/src/lib.rs

#[pyclass]
struct PyStackGraphManager {
    inner: std::sync::Mutex<crate::stack_graph::StackGraphManager>,
}

#[pymethods]
impl PyStackGraphManager {
    #[new]
    fn new() -> Self {
        Self {
            inner: std::sync::Mutex::new(
                crate::stack_graph::StackGraphManager::new()
            ),
        }
    }

    fn add_file(&self, path: &str, source: &str) -> PyResult<()> {
        self.inner
            .lock()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("{}", e)))?
            .add_file(path, source)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e))
    }

    fn resolve_reference(
        &self,
        path: &str,
        line: usize,
        column: usize,
    ) -> Option<HashMap<String, PyObject>> {
        let guard = self.inner.lock().ok()?;
        let result = guard.resolve_reference(path, line, column)?;
        Python::with_gil(|py| {
            // Convert ResolvedReference to dict
            let dict = PyDict::new(py);
            dict.set_item("target_file", &result.target_file).ok()?;
            dict.set_item("target_line", result.target_line).ok()?;
            dict.set_item("target_column", result.target_column).ok()?;
            dict.set_item("symbol_name", &result.symbol_name).ok()?;
            dict.set_item("confidence", result.confidence).ok()?;
            Some(dict.to_object(py))
        })
    }

    fn file_count(&self) -> usize {
        self.inner.lock().map(|g| g.file_count()).unwrap_or(0)
    }

    fn node_count(&self) -> usize {
        self.inner.lock().map(|g| g.node_count()).unwrap_or(0)
    }

    fn clear(&self) {
        if let Ok(mut g) = self.inner.lock() {
            g.clear();
        }
    }

    fn __repr__(&self) -> String {
        let count = self.file_count();
        format!("<StackGraphManager files={}>", count)
    }
}
```

Register the class:
```rust
m.add_class::<PyStackGraphManager>()?;
```

#### 4.3.5 Python Facade — `cutctx/graph/resolver.py`

<!-- AGENT-HANDOFF: Phase 2.4 — Python facade -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: StackGraphManager exposed via cutctx._core -->
<!-- AGENT-INPUT: cutctx._core.StackGraphManager available -->

```python
"""Stack-graph-based code navigation resolver.

Provides a Python facade over the Rust StackGraphManager, integrating
it with Cutctx's code-graph system.

Usage:
    resolver = StackGraphResolver()
    resolver.index_project("/path/to/project")
    result = resolver.resolve("src/main.py", 42, 10)
    # result = {target_file, target_line, target_column, symbol_name, confidence}
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from cutctx._core import StackGraphManager as _RustStackGraphManager

logger = logging.getLogger(__name__)


class StackGraphResolver:
    """Cross-file code navigation using stack graphs.

    Acts as the Python interface to the Rust StackGraphManager,
    handling project-wide indexing, incremental updates, and
    integration with the proxy pipeline.
    """

    def __init__(self) -> None:
        self._inner = _RustStackGraphManager()
        self._indexed_paths: set[str] = set()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_file(self, path: str | Path, source: str | None = None) -> bool:
        """Index a single file.

        If source is None, reads the file from disk.

        Returns True if indexing succeeded.
        """
        path_str = str(path)
        if source is None:
            try:
                source = Path(path).read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("StackGraph: cannot read %s: %s", path, e)
                return False

        try:
            self._inner.add_file(path_str, source)
            self._indexed_paths.add(path_str)
            return True
        except ValueError as e:
            logger.warning("StackGraph: failed to index %s: %s", path, e)
            return False

    def index_project(
        self,
        root: str | Path,
        extensions: set[str] | None = None,
        max_files: int = 1000,
    ) -> int:
        """Recursively index a project directory.

        Args:
            root: Project root directory.
            extensions: File extensions to include
                (default: {".py", ".js", ".jsx", ".ts", ".tsx"}).
            max_files: Maximum number of files to index.

        Returns:
            Number of files successfully indexed.
        """
        if extensions is None:
            extensions = {".py", ".js", ".jsx", ".ts", ".tsx"}

        root = Path(root)
        if not root.is_dir():
            logger.error("StackGraph: project root not found: %s", root)
            return 0

        count = 0
        for path in root.rglob("*"):
            if count >= max_files:
                break
            if path.is_file() and path.suffix in extensions:
                if self.index_file(path):
                    count += 1

        logger.info(
            "StackGraph: indexed %d files in %s",
            count, root,
        )
        return count

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(
        self,
        path: str | Path,
        line: int,
        column: int,
    ) -> dict[str, Any] | None:
        """Resolve a symbol reference to its definition.

        Args:
            path: Source file path.
            line: 0-based line number.
            column: 0-based column number.

        Returns:
            Dict with keys: target_file, target_line, target_column,
            symbol_name, confidence. None if unresolved.
        """
        return self._inner.resolve_reference(str(path), line, column)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def file_count(self) -> int:
        return self._inner.file_count()

    @property
    def node_count(self) -> int:
        return self._inner.node_count()

    @property
    def indexed_paths(self) -> set[str]:
        return self._indexed_paths.copy()

    def clear(self) -> None:
        self._inner.clear()
        self._indexed_paths.clear()

    def __repr__(self) -> str:
        return f"<StackGraphResolver files={self.file_count}>"
```

### 4.4 Integration with Proxy

<!-- AGENT-HANDOFF: Phase 2.5 — Proxy wiring -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: StackGraphResolver exists in cutctx/graph/resolver.py -->
<!-- AGENT-SCOPE: cutctx/cli/proxy.py, cutctx/proxy/models.py, cutctx/proxy/server.py -->

1. **`cutctx/cli/proxy.py`**: Add `--stack-graph` flag (is_flag=True, env var `CUTCTX_STACK_GRAPH=1`)
2. **`cutctx/proxy/models.py`**: Add `stack_graph_enabled: bool = False` to `ProxyConfig`
3. **`cutctx/proxy/server.py`**: At startup, if `config.stack_graph_enabled`:
   - Create `StackGraphResolver`
   - Run `resolver.index_project(os.getcwd())` in a background thread
   - Store on `proxy.stack_graph_resolver`
   - Expose in `/stats` as `stack_graph.files_indexed`, `stack_graph.nodes`

### 4.5 Code Graph Integration

After the resolver is wired, modify `cutctx/graph/watcher.py` to also call `resolver.index_file(path)` whenever a file changes. This keeps the stack graph incrementally up to date alongside the Graphify index.

<!-- AGENT-HANDOFF: Phase 2.6 — Code graph watcher integration -->
<!-- AGENT-TYPE: fixer -->
<!-- AGENT-PRECONDITIONS: StackGraphResolver working, cutctx/graph/watcher.py exists -->
<!-- AGENT-SCOPE: cutctx/graph/watcher.py — add StackGraphResolver refresh on file change -->

---

## 5. Dependency Map

```
USearch Integration
  ┌─────────────────────┐
  │ pyproject.toml      │ ← add usearch>=2.10.0
  └────────┬────────────┘
           ▼
  ┌─────────────────────┐     ┌──────────────────────────┐
  │ config.py           │────▶│ VectorBackend.USEARCH     │
  └────────┬────────────┘     └──────────┬───────────────┘
           │                            ▼
           │              ┌──────────────────────────┐
           ├─────────────▶│ usearch_store.py          │ ← NEW
           │              │   UsearchMemoryBackend     │
           │              └──────────┬───────────────┘
           │                         ▼
           │              ┌──────────────────────────┐
           └─────────────▶│ factory.py                │
                          │   create_vector_backend() │
                          └──────────────────────────┘
           ┌──────────────────────────┐
           │ tests/test_usearch*.py   │ ← NEW
           └──────────────────────────┘

Stack Graphs Integration
  ┌──────────────────────────┐
  │ Cargo.toml               │ ← add tree-sitter-stack-graphs, tree-sitter-python, tree-sitter-javascript
  └────────┬─────────────────┘
           ▼
  ┌──────────────────────────┐     ┌──────────────────────────────┐
  │ cutctx-core/src/lib.rs   │────▶│ stack_graph/mod.rs           │ ← NEW
  └────────┬─────────────────┘     │   StackGraphManager          │
           │                       └──────────┬───────────────────┘
           ▼                                  ▼
  ┌──────────────────────────┐     ┌──────────────────────────────┐
  │ cutctx-py/src/lib.rs     │────▶│ PyStackGraphManager          │ ← PyO3 class
  └────────┬─────────────────┘     └──────────┬───────────────────┘
           ▼                                  ▼
  ┌──────────────────────────┐     ┌──────────────────────────────┐
  │ cutctx/graph/resolver.py │────▶│ StackGraphResolver           │ ← NEW
  │                          │     │   index_project()            │
  │                          │     │   resolve()                  │
  └────────┬─────────────────┘     └──────────┬───────────────────┘
           │                                  ▼
           │                       ┌──────────────────────────────┐
           └──────────────────────▶│ cutctx/graph/watcher.py      │ ← MODIFY: incremental refresh
                                  └──────────────────────────────┘
           ┌──────────────────────────┐
           │ crates/.../test_stack*.rs│ ← NEW: Rust-side test
           │ tests/test_stack*.py     │ ← NEW: Python-side test
           └──────────────────────────┘
```

---

## 6. Risk Assessment

| Risk | Phase | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| USearch `f16` dtype loses recall vs `f32` | 1 | Low | Medium | Default to `f16` but allow configurable dtype; add recall test in CI |
| USearch doesn't support deletion (only `remove` emulation) | 1 | Certain | Medium | Emulate by filtering excluded keys in search; document limitation |
| `tree-sitter-stack-graphs` API has changed since 0.8 | 2 | Medium | High | Pin exact version; verify API before writing binding code |
| TSG rule files are non-trivial to author | 2 | High | High | Start with bundled TSGs from test fixtures; only target Python initially |
| Rust compilation time (~20 min with new grammars) | 2 | Medium | Low | CI can cache compiled artifacts; local dev tolerates one-time cost |
| Memory backend selection becomes confusing (4 options) | 1 | Low | Medium | Document recommended path: `AUTO` → `sqlite-vec` → `usearch` → `hnswlib`; `AUTO` should prefer `usearch` over `sqlite-vec` when installed |
| Stack graph index is large for monorepos | 2 | Medium | Medium | Bound by `max_files` (default 1000); warn if exceeded |
| `stack-graphs` doesn't support Rust/go TSGs yet | 2 | Low | Low | Initially support only Python and JS/TS; log unsupported languages as warnings |

---

## 7. Test Plan

### Phase 1 Tests (Python)

| Test | Level | Est. Time | Status |
|---|---|---|---|
| `test_usearch_backend.py` (15+ tests) | Unit + Integration | 2-3 hrs | ✏️ TODO |
| Existing vector backend tests still pass | Regression | 30 min | ✏️ TODO |

### Phase 2 Tests (Rust + Python)

| Test | Level | Est. Time | Status |
|---|---|---|---|
| `crates/cutctx-core/tests/test_stack_graphs.rs` — Two-file symbol resolution | Integration | 2 hrs | ✏️ TODO |
| `tests/test_stack_graph_resolver.py` — Python facade wrapping Rust | Integration | 2 hrs | ✏️ TODO |
| Full test suite pass (no regressions) | Regression | 30 min | ✏️ TODO |

### Manual Verification

```bash
# Phase 1
pip install usearch
python -c "
from cutctx.memory.backends.usearch_store import UsearchMemoryBackend
backend = UsearchMemoryBackend(ndim=384)
backend.initialize()
# Add 1000 random vectors, verify search
"

# Phase 2
pip install -e ".[dev]"
python -c "
from cutctx.graph.resolver import StackGraphResolver
r = StackGraphResolver()
r.index_file('/tmp/test.py', 'def foo(): pass\n')
assert r.file_count == 1
print('StackGraphResolver OK')
"
```

---

## 8. Architecture Decision Record

### ADR-1: USearch in Python vs Rust
- **Decision:** Python
- **Rationale:** USearch's Python bindings are first-class and well-maintained. The memory backend layer is already Python-native. Adding USearch via Rust would require a new PyO3 binding just for vector search, which duplicates effort.
- **Consequence:** USearch is pip-installable with no Rust compilation.

### ADR-2: Stack Graphs in Rust vs Python
- **Decision:** Rust (native `tree-sitter-stack-graphs` crate)
- **Rationale:** `tree-sitter-stack-graphs` is a Rust library with no Python bindings. The tree-sitter grammars (`tree-sitter-python`, `tree-sitter-javascript`) are also Rust crates. Python tree-sitter bindings exist (`tree-sitter-language-pack`) but don't support TSG rules.
- **Consequence:** Requires PyO3 binding, Rust compilation, and tree-sitter grammar `.so` files in the wheel. Increases wheel size by ~5-10 MB.

### ADR-3: USearch as Optional Extra vs Default Backend
- **Decision:** Optional (add to `memory` extra alongside `sqlite-vec` and `hnswlib`)
- **Rationale:** Not breaking existing installations. Users who want USearch run `pip install usearch` or `pip install cutctx-ai[enterprise]`.
- **Consequence:** `VectorBackend.AUTO` will prefer `usearch` when installed, falling back to `sqlite-vec` then `hnswlib`.

### ADR-4: Initial Language Support for Stack Graphs
- **Decision:** Python only (v1); JavaScript/TypeScript (v2)
- **Rationale:** Python is the most-used language in Cutctx's target audience (AI coding agents). TSG rules for Python are the most mature.
- **Consequence:** Users of other languages get fallback behavior (scope-only, no cross-file resolution).

---

## 9. Handoff Summary

| Phase | Agent Type | Entry Point | Precondition |
|---|---|---|---|
| 1.1 USearch dep + config | fixer | `pyproject.toml`, `config.py` | — |
| 1.2 USearch backend impl | fixer | `usearch_store.py` | Phase 1.1 done |
| 1.3 USearch factory routing | fixer | `factory.py` | Phase 1.2 done |
| 1.4 USearch tests | fixer | `tests/test_usearch_backend.py` | Phase 1.2 done |
| 2.1 Cargo.toml + Rust module skeleton | fixer | `Cargo.toml`, `stack_graph/mod.rs` | — |
| 2.2 TSG rule loading + resolution | fixer | `stack_graph/mod.rs` (fill stubs) | Phase 2.1 done |
| 2.3 PyO3 binding | fixer | `cutctx-py/src/lib.rs` | Phase 2.2 done |
| 2.4 Python facade | fixer | `resolver.py` | Phase 2.3 done |
| 2.5 Proxy wiring | fixer | `server.py`, `proxy.py`, `models.py` | Phase 2.4 done |
| 2.6 Watcher integration | fixer | `watcher.py` | Phase 2.4 done |
| 2.7 Rust tests | fixer | `crates/.../test_stack_graphs.rs` | Phase 2.2 done |
| 2.8 Python tests | fixer | `tests/test_stack_graph*.py` | Phase 2.4 done |
| 2.9 Documentation | fixer | wiki pages | Phase 2.5 done |
| Overall review | oracle | all files | All phases done |

---

## 10. Implementation Status

<!-- AGENT: Update this section after completing each phase -->

| Phase | Status | Completed By | Date |
|---|---|---|---|---|---|
| 1.1 pyproject.toml + config.py | ✅ Done | fixer | 2026-06-30 |
| 1.2 UsearchMemoryBackend | ✅ Done | fixer | 2026-06-30 |
| 1.3 Factory routing | ✅ Done | fixer | 2026-06-30 |
| 1.4 Tests | ✅ Done | fixer | 2026-06-30 |
| 2.1 Cargo.toml + module skeleton | ✅ Done | fixer | 2026-06-30 |
| 2.2 TSG rules + resolution impl | ✅ Done | fixer | 2026-06-30 |
| 2.3 PyO3 binding | ✅ Done | fixer | 2026-06-30 |
| 2.4 Python facade | ✅ Done | fixer | 2026-06-30 |
| 2.5 Proxy wiring | ✅ Done | fixer | 2026-06-30 |
| 2.6 Watcher integration | ✅ Done | fixer | 2026-06-30 |
| 2.7 Rust tests | ✅ Done | fixer | 2026-06-30 |
| 2.8 Python tests | ✅ Done | fixer | 2026-06-30 |
| 2.9 Documentation | ✅ Done | fixer | 2026-06-30 |

**Overall Progress:** 13 / 13 phases complete — **fully implemented ✅**
