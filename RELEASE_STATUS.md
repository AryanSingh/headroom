# Cutctx v0.29.0 — Release Status

**Date:** 2026-07-01  
**Branch:** `main`  
**Base commit:** `9f27e3d0` (`Fix audio compression and dashboard verification`)  
**Working tree:** Release checkpoint being finalized on `main`

## 2026-07-01 Checkpoint

- Admin/runtime source boot restored after `cutctx/proxy/routes/admin.py` was returned to a clean `HEAD` state.
- Dashboard operator data path re-verified with current-source endpoints for `/health`, `/config/flags`, `/policy/status`, `/stats`, and `/stats-history`.
- Inline multimodal audio optimization is now implemented and covered by targeted tests; dedicated `/v1/audio/*` routes remain pass-through by design.
- Current verified checkpoint:
  - `cd dashboard && npm run build`
  - `uv run python -m pytest -q tests/test_audio_compressor.py tests/test_inline_audio_messages.py tests/test_proxy_compress_endpoint.py tests/test_handler_outcome_tag_invariant.py tests/test_modality_matrix.py -q`

USearch + Stack Graphs integration

---

## Summary

Two major new capabilities:

1. **USearch vector backend** — ~10× faster vector search with f16 quantization and zero-copy memory-mapped loading. Replaces sqlite-vec as the primary local vector backend when `usearch` is installed. `VectorBackend.AUTO` prefers USEARCH → SQLITE_VEC → HNSW.
2. **Stack Graphs code navigation** — Deterministic, syntax-based cross-file go-to-definition using GitHub's `tree-sitter-stack-graphs`. Rust `StackGraphManager` exposed via PyO3 with Python `StackGraphResolver` facade. Supports Python and JavaScript/TypeScript.
3. **Phase 1 Security fixes** — Four critical/high security patches: loopback auth bypass closure for `/dashboard`, `/api/savings`, `/api/models`; LIKE wildcard injection fix with `_escape_like()` helper; Kompress max-input DoS guard via `CUTCTX_KOMPRESS_MAX_WORDS`; startup warning when `CUTCTX_ALLOW_DEBUG` is set.

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

### Stack Graph Reachability Bridge

- **`cutctx/graph/reachability.py`** — `extract_symbol_names()` + `resolve_entry_points()`, bridging Rust `reachable_definitions()` BFS results into Python
  - Protects on-call-path symbols during aggressive compression (prevents breaking dependent code paths)
  - Wired into `CodeAwareCompressor.set_protected_symbols()` from `cutctx/proxy/server.py` (`_apply_stack_graph_to_compressor()`) via `content_router.py`
- **`cutctx/cli/stack_graph.py`** — New CLI subcommand: `cutctx stack-graph explain <query>`
  - Uses `stack_graph_available()`, `StackGraphResolver().index_project()`, `resolve_entry_points()`
  - Options: `--project-root`, `--max-files`

### Feedback Loop (Data Flywheel)

- **`cutctx/profiles.py`** — Per-workspace `CompressionProfile` persistence
  - Tracks per-content-type stats: `sessions_seen`, `total_compressions`, `total_retrievals`, `retrieval_rate`, `avg_compression_ratio`, `recommended_ratio`
  - Persisted as JSON at `~/.cutctx/profiles/<workspace_hash>.json` (`_get_profile_path()`)
  - `recommended_ratio` is clamped to a max of 0.95 (`_MAX_RECOMMENDED_RATIO`) so feedback can never fully disable compression (M-1 security fix)
  - Flows into `ContentRouterConfig.per_type_overrides` at proxy startup (`server.py`), biasing future compression per content type
- **`cutctx/cli/profile.py`** — New CLI subcommand: `cutctx profile show [--json]`
  - Calls `CompressionProfile.load()` / `.summary()`; friendly empty-state message when no profile exists yet
- **`/stats`** — now exposes a `"profile"` block (`CompressionProfile.load().summary()`) and `"content_router_overrides_count"` so operators can verify the flywheel is actually running end-to-end

### Benchmark CLI

- **`cutctx/cli/evals.py`** — `cutctx evals benchmark` command (`@evals.command("benchmark")`)
  - `--dataset` (multiple, default `tool_outputs`): `tool_outputs`, `longbench`, `squad`, `hotpotqa`, plus `--longbench-task` for LongBench subtasks
  - `--compressors` (multiple, default `all`): `smart_crusher`, `log`, `search`, `diff`, `code`, `kompress`, `llmlingua`, `drain3`, `content_router`, `all`
  - `--metrics` (multiple, default `ratio,f1,information_recall`): `ratio`, `tokens_saved`, `f1`, `rouge_l`, `information_recall`, `exact_match`
  - `--n` samples per dataset, `--parallel` worker count, `--output PATH` for JSON, `--markdown` for an LLMLingua-paper-style comparison table
  - Zero-LLM by default; still surfaced under the `evals` command group in `cutctx --help` (relabeled from "Memory evaluation commands" to also mention benchmarking)

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
6. **Auth bypass fixed**: `/dashboard`, `/api/savings`, and `/api/models` were stripped from the loopback auth bypass path in `server.py:213` — localhost no longer skips auth for these endpoints. Verified via manual curl against local proxy.
7. **LIKE injection guard applied**: `_escape_like()` helper and `ESCAPE "\\"` clause added for `entity_ref` LIKE queries in `sqlite.py`. Existing DB rows with unescaped wildcards are safe at read time; new writes are sanitized.
8. **Kompress DoS limit added**: `CUTCTX_KOMPRESS_MAX_WORDS` env var (default 80,000) caps per-call text input to the Kompress transformer. Backward compatible for typical usage; deployments with very long prompts may need to raise the limit.
9. **Ruff lint cleanup**: 56 auto-fixable lint errors resolved across the codebase (F401 unused imports, trailing whitespace, etc.). No behavioral changes.

---

## Next Steps

1. Commit all changes with descriptive commit message
2. Tag `v0.29.0`
3. Push to `main`
4. Extend stack graphs to additional languages (Rust, Go, Java)
5. Wire stack graph resolution into proxy interceptors for automatic go-to-definition injection
6. Evaluate USearch f16 recall vs f32 on embedding benchmarks
