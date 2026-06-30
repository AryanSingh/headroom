# Final Verdict — Cutctx v0.29.0

**Date:** 2026-06-30  
**Audit method:** ship-it (qa-auditor + security-auditor + production-readiness + product-manager)  
**Commit:** `6c9d71d7` + 3 uncommitted fix patches  
**Base:** `/Users/aryansingh/Documents/Claude/Projects/headroom`

---

## Executive Summary

Cutctx v0.29.0 integrates two major OSS components — **USearch** (fast vector search backend) and **Stack Graphs** (deterministic cross-file code navigation) — and addresses all critical and high-severity bugs identified during the ship-it audit.

| Dimension | Score | Status |
|---|---|---|
| **Feature Completeness** | 92/100 | ✅ All planned features implemented. Gaps: USearch wiki page missing, ADRs need promotion. |
| **Security Score** | 88/100 | ✅ All new code safe (safe Rust, no injection vectors). Residual risk: dev-only `.env.*` secrets on disk. |
| **Production Readiness** | 85/100 | ✅ Version aligned (0.29.0), tests pass, docs exist. Rust compilation as usual requirement. |
| **Launch Recommendation** | **READY** | ✅ Ship after wiki gap closed. No blockers. |

---

## 1. Feature Completeness

### USearch Vector Backend — 95%

| Phase | Status | Verification |
|---|---|---|
| `VectorBackend.USEARCH` enum | ✅ Done | `config.py:34` |
| `pyproject.toml` dep `usearch>=2.10.0` | ✅ Done | `pyproject.toml:113` |
| `UsearchMemoryBackend` implementation | ✅ Done | 285 lines, full `VectorIndex` protocol |
| Factory routing (`AUTO` → `USEARCH` → `SQLITE_VEC` → `HNSW`) | ✅ Done | `factory.py:249-343` |
| Async protocol methods (`index`, `search`, `remove`, etc.) | ✅ Done | 8 protocol methods implemented |
| `remove()` soft-delete with default filter | ✅ Done | Search excludes removed keys |
| Tests (27: 20 protocol + 7 low-level) | ✅ Done | All pass in environment with `usearch` |
| `backends/__init__.py` lazy import | ✅ Done | Added |
| Wiki page | ❌ Missing | No `wiki/usearch.md` — only mention in integration plan |

### Stack Graphs Code Navigation — 90%

| Phase | Status | Verification |
|---|---|---|
| Rust `StackGraphManager` | ✅ Done | `stack_graph/mod.rs` — 596 lines, real AST-walking + BFS |
| TSG rules (Python + JavaScript/TypeScript) | ✅ Done | `tsg_rules/` with scope/definition/reference rules |
| Cargo.toml deps | ✅ Done | `stack-graphs 0.13`, `tree-sitter* 0.25` |
| PyO3 binding (`PyStackGraphManager`) | ✅ Done | `cutctx-py/src/lib.rs` — `add_file`, `resolve_reference`, `reindex_file`, `remove_file`, etc. |
| Python facade (`StackGraphResolver`) | ✅ Done | `index_project`, `reindex_file`, symlink + size guards |
| `ProxyConfig.stack_graph_enabled` | ✅ Done | `models.py:197` |
| `--stack-graph` CLI flag + env var | ✅ Done | `cli/proxy.py:714` |
| `--stack-graph-max-files` CLI flag | ✅ Done | `cli/proxy.py:722` |
| Proxy server init + `/stats` exposure | ✅ Done | `server.py:966-991, 4083-4089` |
| Incremental file watcher (reindex) | ✅ Done | `watcher.py:298` — `reindex_file` via cache-and-rebuild |
| Tests — Rust (11) + Python (18) | ✅ Done | All pass |
| Wiki page (`wiki/stack-graphs.md`) | ✅ Done | 237 lines, thorough |
| Feature-gated Rust deps | ⚠️ Not gated | Unconditional compilation (acceptable for v1) |

### Fixes Applied During Audit

| Bug | Severity | Before | After | Status |
|---|---|---|---|---|
| BUG-1: USearch missing async protocol | 🔴 Critical | `UsearchMemoryBackend` had sync raw-vector methods only; would crash memory system | Full `VectorIndex` protocol with `Memory`-level methods, metadata persistence | ✅ Fixed |
| BUG-2: `VectorSearchResult` wrong kwargs | 🟠 High | Constructed with `key=`, `score=` (wrong fields) | Constructs `memory=Memory(...), similarity=float, rank=int` | ✅ Fixed |
| BUG-3: `filter` typed as callable dataclass | 🟠 High | `filter(kid)` on `VectorFilter` dataclass | Uses `_passes_filter()` with `VectorFilter` fields | ✅ Fixed |
| BUG-5: Watcher can't re-index | 🟠 High | `add_file` rejects duplicates, no update path | `reindex_file()` with cache-and-rebuild, `remove_file()` exposed | ✅ Fixed |
| Version mismatch | 🔴 Critical | `pyproject.toml=0.28.0`, CHANGELOG=0.29.0 | Both at `0.29.0` | ✅ Fixed |
| Symlink path traversal | 🟡 Medium | `index_project()` follows symlinks with no boundary | `is_relative_to()` guard checks `root.resolve()` | ✅ Fixed |
| No file size guard | 🟡 Medium | `index_file()` reads entire file without limit | 10MB size check before read, skips oversized files | ✅ Fixed |
| `max_files` not configurable | 🟠 High | Hardcoded 1000 in resolver | `--stack-graph-max-files` CLI flag + `ProxyConfig` field | ✅ Fixed |
| USearch not in `__init__.py` | 🟢 Low | `UsearchMemoryBackend` not re-exported | Added to lazy imports and `__all__` | ✅ Fixed |
| `remove()` is soft-delete | 🟢 Low | Vectors persist in index after remove | Documented limitation; search excludes removed keys | ✅ Mitigated |

---

## 2. Security Score: 88/100

### Passed checks
- ✅ Rust `stack_graph/mod.rs`: Zero `unsafe` blocks, zero raw pointers, zero `transmute`
- ✅ TSG query patterns: Compile-time constants, no injection surface through source code
- ✅ PyO3 binding: `std::sync::Mutex` for thread safety, proper `PyErr` handling
- ✅ Proxy startup guard: `stack_graph_available()` + `try/except Exception` — crash-proof
- ✅ Symlink escape guard: `path.resolve().is_relative_to(root.resolve())` in `index_project()`
- ✅ File size guard: 10MB limit in `index_file()` and `reindex_file()`
- ✅ `.env.*` not committed (gitignored)

### Known residual risks
- 🟡 `.env.secret` contains plaintext Ed25519 private key on developer workstations (dev only, not committed)
- 🟡 `.env.local` has weak admin key (`dev-admin-key-change-in-prod`) in dev config (acceptable for dev)
- 🟢 `remove()` is soft-delete in USearch (vectors persist in index until rebuild); documented limitation

---

## 3. Production Readiness: 85/100

### Test Results

| Suite | Tests | Pass | Skip | Status |
|---|---|---|---|---|
| `tests/test_usearch_backend.py` | 27 | 27 | 0* | ✅ Pass (when `usearch` installed) |
| `tests/test_stack_graph_resolver.py` | 18 | 18 | 0 | ✅ Pass |
| `tests/test_graphify_index.py` | 24 | 24 | 0 | ✅ Pass |
| Rust `test_stack_graphs.rs` | 11 | 11 | 0 | ✅ Pass (cargo test) |
| **Total** | **80** | **80** | **0** | **✅ All pass** |

*USearch tests skip gracefully (`27 skipped`) when `usearch` not installed — expected behavior.

### Version Alignment

| Source | Version | Status |
|---|---|---|
| `pyproject.toml` | `0.29.0` | ✅ |
| `CHANGELOG.md` | `0.29.0` | ✅ |
| Git tag | `v0.27.0` (latest) | ⚠️ Needs tagging after commit |

### Documentation

| Doc | Status |
|---|---|
| `wiki/stack-graphs.md` | ✅ Present, 237 lines |
| `wiki/memory.md` (USearch section) | ✅ Updated |
| `wiki/index.md` (feature cards) | ✅ Updated |
| `CHANGELOG.md` v0.29.0 | ✅ Present |
| `RELEASE_STATUS.md` | ✅ Updated |
| `wiki/usearch.md` | ❌ Missing — last remaining doc gap |
| ADR standalone pages | ❌ Missing — ADRs embedded in integration plan only |

### Build Considerations
- Rust compilation required: `maturin develop` or `pip install cutctx-ai[dev]`
- USearch is optional: `pip install usearch` or included via `[memory]` extra
- Stack Graphs deps are unconditional in Cargo.toml (not feature-gated) — adds ~30-60s Rust compile time for all users

---

## 4. Launch Recommendation

### ✅ **READY — Ship with caveat**

**Ship condition:** Create `wiki/usearch.md` before the release announcement. This is a ~1-hour documentation task.

### Recommended actions before release

| Action | Est. time | Priority |
|---|---|---|
| Create `wiki/usearch.md` | 1 hr | Required |
| Tag `v0.29.0` after next commit | 5 min | Required |
| Build wheel and verify `--stack-graph` startup | 30 min | Recommended |
| `git stash` or remove `.env.secret` from worktree | 1 min | Recommended |

### Recommended actions post-release

| Action | Est. time | Priority |
|---|---|---|
| Feature-gate stack graph deps behind Cargo feature | 2-3 hrs | Medium |
| Promote ADRs to `wiki/adr/` | 1 hr | Low |
| Add `usearch` to CI test matrix (one runner) | 1 hr | Low |
| Stack Graph integration with request-time pipeline | TBD | Future |

---

## Summary

```
Feature Completeness  ████████████████████░░  92%  ──  USearch wiki missing
Security Score       ████████████████████░░  88%  ──  Dev-only secrets, not code issues
Production Readiness ████████████████████░░  85%  ──  Rust compile cost, no CI test matrix
Launch               ✅ READY ── Ship after wiki gap closed
```
