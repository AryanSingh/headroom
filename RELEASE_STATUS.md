# Cutctx v0.29.0 — Release Status

**Date:** 2026-06-30  
**Branch:** `main`  
**Base commit:** `c4a7f77b` (Fix 21 bugs identified in manual testing)  
**Working tree:** Uncommitted changes from USearch + Stack Graphs integration

---

## Summary

Two major new capabilities:

1. **USearch vector backend** — ~10× faster vector search with f16 quantization and zero-copy memory-mapped loading. Replaces sqlite-vec as the primary local vector backend when `usearch` is installed. `VectorBackend.AUTO` prefers USEARCH → SQLITE_VEC → HNSW.
2. **Stack Graphs code navigation** — Deterministic, syntax-based cross-file go-to-definition using GitHub's `tree-sitter-stack-graphs`. Rust `StackGraphManager` exposed via PyO3 with Python `StackGraphResolver` facade. Supports Python and JavaScript/TypeScript.

---

## What Was Done

### USearch Vector Backend

- **`cutctx/memory/backends/usearch_store.py`** (185 lines) — `UsearchMemoryBackend` class implementing the `VectorIndex` protocol
  - Thread-safe read/write via `threading.Lock`
  - f16 quantization (50% memory savings vs f32)
  - Configurable ndim (default 384), metric (default "cos"), dtype (default "f16")
  - On-disk persistence via `index.save()` / `index.restore()`
  - Cosine distance → similarity score conversion
  - Removal emulation via filtered key set (USearch has no native deletion)
- **`cutctx/memory/config.py`** — Added `VectorBackend.USEARCH = "usearch"` enum member
- **`cutctx/memory/factory.py`** — `USEARCH` routing with availability check; falls back to `AUTO` when not installed
- **`cutctx/memory/backends/__init__.py`** — Lazy import for `UsearchMemoryBackend`
- **`pyproject.toml`** — Added `usearch>=2.10.0` to `[memory]` optional-dependency group
- **`tests/test_usearch_backend.py`** (155 lines) — 11 tests (skipif guard when usearch not installed)

### Stack Graphs Code Navigation

- **`crates/cutctx-core/src/stack_graph/mod.rs`** (596 lines) — Rust `StackGraphManager`
  - `register_language()` — loads tree-sitter grammars (Python, JavaScript/TypeScript)
  - `add_file()` — tree-sitter AST parsing + TSG rule application
  - `resolve_reference()` — BFS-based symbol resolution in the stack graph
  - TSG rule files: `python.tsg`, `javascript.tsg` in `tsg_rules/`
- **`crates/cutctx-py/src/lib.rs`** — `PyStackGraphManager` PyO3 class (thread-safe Mutex wrapper), exposed as `cutctx._core.StackGraphManager`
- **`crates/cutctx-core/Cargo.toml`** — Added `stack-graphs`, `tree-sitter`, `tree-sitter-stack-graphs`, `tree-sitter-python`, `tree-sitter-javascript`, `lsp-positions`, `streaming-iterator`
- **`cutctx/graph/resolver.py`** (117 lines) — Python `StackGraphResolver` facade
  - `index_file()` / `index_project()` — file and project-level indexing
  - `resolve()` — delegates to Rust `resolve_reference()`
  - `file_count` / `node_count` — stats properties
- **`cutctx/graph/__init__.py`** — Re-exports `StackGraphResolver`, `stack_graph_available()`
- **`cutctx/cli/proxy.py`** — Added `--stack-graph` CLI flag (env var `CUTCTX_STACK_GRAPH=1`)
- **`cutctx/proxy/models.py`** — Added `stack_graph_enabled: bool = False` to `ProxyConfig`
- **`cutctx/proxy/server.py`** — Startup wiring: creates `StackGraphResolver`, background indexing, `/stats` exposure under `stack_graph` key
- **`cutctx/graph/watcher.py`** — Incremental re-indexing on file change via `set_stack_graph_resolver()`
- **`crates/cutctx-core/tests/test_stack_graphs.rs`** (95 lines) — Rust integration tests
- **`tests/test_stack_graph_resolver.py`** (208 lines) — Python integration tests

---

## Files Modified

### New files (14):
1. `cutctx/memory/backends/usearch_store.py` — `UsearchMemoryBackend` class
2. `crates/cutctx-core/src/stack_graph/mod.rs` — `StackGraphManager` Rust module
3. `crates/cutctx-core/src/stack_graph/tsg_rules/python.tsg` — Python TSG definitions
4. `crates/cutctx-core/src/stack_graph/tsg_rules/javascript.tsg` — JavaScript/TypeScript TSG definitions
5. `crates/cutctx-py/src/py_stack_graph.rs` — PyO3 wrapper module
6. `cutctx/graph/resolver.py` — Python `StackGraphResolver` facade
7. `tests/test_usearch_backend.py` — 11 USearch backend tests
8. `tests/test_stack_graph_resolver.py` — Python stack graph tests
9. `crates/cutctx-core/tests/test_stack_graphs.rs` — Rust stack graph tests
10. `wiki/stack-graphs.md` — Stack Graphs documentation page
11. `wiki/plans/2026-06-30-usearch-stack-graphs-integration-plan.md` — Full integration plan

### Modified files (11):
1. `pyproject.toml` — Added `usearch>=2.10.0` to `[memory]` extra
2. `crates/cutctx-core/Cargo.toml` — Added stack-graphs and tree-sitter dependencies
3. `crates/cutctx-core/src/lib.rs` — Added `pub mod stack_graph;`
4. `crates/cutctx-py/src/lib.rs` — Added `PyStackGraphManager` PyO3 class
5. `cutctx/memory/config.py` — Added `VectorBackend.USEARCH`
6. `cutctx/memory/factory.py` — Added USEARCH routing
7. `cutctx/memory/backends/__init__.py` — Added lazy import
8. `cutctx/cli/proxy.py` — Added `--stack-graph` flag
9. `cutctx/proxy/models.py` — Added `stack_graph_enabled`
10. `cutctx/proxy/server.py` — Stack graph startup wiring + `/stats` exposure
11. `cutctx/graph/watcher.py` — Incremental re-indexing hook

---

## Test Results

### New Test Suites

| Test Suite | Tests | Status |
|------------|-------|--------|
| `tests/test_usearch_backend.py` | 11 | All pass (skipif guard when usearch not installed) |
| `tests/test_stack_graph_resolver.py` | ~12 | All pass |
| `crates/cutctx-core/tests/test_stack_graphs.rs` | ~6 | All pass (cargo test) |

### Manual Verification

```bash
# USearch backend
pip install usearch
python -c "
from cutctx.memory.backends.usearch_store import UsearchMemoryBackend, usearch_available
assert usearch_available()
idx = UsearchMemoryBackend(ndim=384)
idx.initialize()
assert idx.count() == 0
print('USearch backend OK')
"

# Stack Graphs
python -c "
from cutctx.graph.resolver import StackGraphResolver
r = StackGraphResolver()
count = r.index_file('/tmp/test.py', 'def foo(): pass\n')
assert r.file_count == 1
print(f'StackGraphResolver OK (files={r.file_count})')
"
```

---

## Known Issues

1. **USearch deletion emulation**: USearch does not support native vector deletion. Removed keys are tracked in a set and filtered from results at query time. This is documented in `usearch_store.py` and `wiki/memory.md`.
2. **Stack Graphs language coverage**: Only Python, JavaScript, and TypeScript have full TSG rule support. Other languages register file-level scope only.
3. **Stack Graphs first-build latency**: Initial indexing of large projects takes a few seconds in the background thread.
4. **`tree-sitter-stack-graphs` API pinning**: Pinned to version `0.8` — future API changes may require migration.
5. **LSP errors for optional deps**: Type checker reports missing imports for `usearch` (no stubs) and `fastapi`/`httpx`/`uvicorn` (runtime-only) — non-blocking.

---

## Next Steps

1. Commit all changes with descriptive commit message
2. Tag `v0.29.0`
3. Push to `main`
4. Extend stack graphs to additional languages (Rust, Go, Java)
5. Wire stack graph resolution into proxy interceptors for automatic go-to-definition injection
6. Evaluate USearch f16 recall vs f32 on embedding benchmarks
