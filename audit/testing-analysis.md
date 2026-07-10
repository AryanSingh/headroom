# Testing Analysis — Cutctx Project

**Date:** 2026-07-10
**Rating:** 🟢 **Strong** (with notable gaps)

---

## Key Strengths

1. **Massive test corpus**: 426 Python test files (~8,191 test functions, ~129K lines) + 12K lines of Rust integration tests + 864 Rust unit tests in cutctx-core + 256 in cutctx-proxy
2. **Well-structured CI**: Python tests split into 4 parallel shards via `pytest-split`; Rust has its own dedicated workflow with fmt/clippy/test/audit/parity-nightly
3. **Rust integration test depth**: 44 test files covering compression, caching, streaming (SSE for Anthropic/OpenAI/Bedrock), metrics, schema sorting, tool sorting, health checks, and more
4. **Chaos testing**: Nightly k8s chaos workflow with pod evictions and synthetic load
5. **Benchmark suite**: 31 benchmark files (~19K lines) covering latency, compression, CCR regression, adversarial CCR, and cost
6. **Good fixture isolation**: `conftest.py` (108 lines) with autouse fixtures for `_restore_runtime_state` (resets cwd, rbac checker, webhooks singleton, subscription tracker) and `_cleanup_cutctx_logger` (restores logger propagation)
7. **Security-aware testing**: Admin API key injected into all TestClients by default; tests that verify 401 behavior monkeypatch their own key
8. **Multi-platform E2E**: Docker-based wrap/init e2e, Windows + macOS native wrapper tests in CI

## Critical Issues

### 🔴 Rust Coverage Not Tracked in Codecov

**Status: STILL NOT FIXED**

- `codecov.yml` (`.github/codecov.yml`) has `target: auto` for both `project` and `patch` — no hard thresholds
- No coverage upload step in `.github/workflows/rust.yml` — no `cargo-tarpaulin`, no `llvm-cov`, no `codecov-action` for Rust
- Python coverage is only partially tracked: `install-native-e2e.yml` and `wrap-native-e2e.yml` upload coverage, but the main `ci.yml` test job does NOT run `--cov` or upload coverage
- **Impact**: No coverage regression detection for either language; `target: auto` means Codecov flags any coverage drop but doesn't enforce a minimum

### 🔴 No Coverage Thresholds

- `codecov.yml` uses `target: auto` (tracks against baseline, no floor)
- No `fail_under` in `[tool.coverage.report]` in `pyproject.toml`
- No Makefile target for local coverage (`make coverage` absent)
- **Impact**: Coverage can silently regress without blocking merges

### 🟡 `test_memory_system.py` Not Split (1,831 lines, 104 tests)

- **File**: `tests/test_memory_system.py:1-1831`
- Still a monolithic file; the previous audit flagged it at ~65KB
- At 1,831 lines it's the largest test file in the suite
- **Impact**: Hard to navigate, slow to isolate failures, risk of cross-test contamination within the file

### 🟡 No Python-Level Load/Stress Tests

- `tests/test_proxy_scalability.py` (272 lines) tests connection pool config and worker settings — but only asserts on configuration objects, not actual throughput
- No concurrent request load tests, no throughput benchmarks under load in the test suite
- Chaos testing workflow exists (k8s pod evictions) but is infrastructure-level, not application-level load testing
- **Impact**: No regression detection for proxy performance under load

### 🟡 No `conftest.py` in `cutctx/tests/`

- `cutctx/tests/` has 7 test files but zero `conftest.py`
- Each test file must import and set up its own fixtures
- Contrast with `tests/conftest.py` which is well-structured (108 lines, autouse fixtures)
- **Impact**: Duplication of setup code; no shared fixtures for the OSS test subpackage

### 🟡 pytest-split Without `.test_durations` File

- CI uses `--splits 4 --group ${{ matrix.shard }}` (`.github/workflows/ci.yml:199`)
- No `.test_durations` file found in the repo root
- Without duration data, splits are alphabetical/uniform — some shards likely much slower than others
- **Impact**: Wasted CI time; one shard may be the bottleneck

## Test Coverage Summary Table

| Area | Files | Test Functions | Lines | Coverage |
|------|-------|---------------|-------|----------|
| **Python (tests/)** | 426 | ~8,191 | ~129,071 | Partial (no CI upload from main job) |
| **Python (cutctx/tests/)** | 7 | ~208 | 3,175 | None tracked |
| **Python (scripts/tests/)** | 3 | ~small | ~small | None tracked |
| **Rust integration (cutctx-proxy)** | 44 | ~90+ `#[test]` | 10,015 | **Not tracked** |
| **Rust unit (cutctx-core)** | 11 files | ~120+ `#[test]` | 2,344 | **Not tracked** |
| **Rust inline (cutctx-core/src)** | 5 modules | 864 inline `#[test]` | — | **Not tracked** |
| **Rust inline (cutctx-proxy/src)** | 4 modules | 256 inline `#[test]` | — | **Not tracked** |
| **Rust async (#[tokio::test])** | — | 135 | — | **Not tracked** |
| **E2E (e2e/)** | 1 test file | 4 | 59 | None tracked |
| **E2E (Docker)** | 2 workflows | wrap + init | — | None tracked |
| **E2E (platform)** | 2 workflows | native installers | — | Partial |
| **Benchmarks** | 31 | N/A | ~18,857 | N/A |
| **Chaos** | 1 workflow | k8s pod eviction | — | N/A |

## Detailed Analysis

### 1. Python Test Suite

**Location**: `tests/` (main), `cutctx/tests/` (OSS subpackage)

**Structure**:
- 426 test files in `tests/`, all named `test_*.py`
- 7 test files in `cutctx/tests/` covering: billing, context budget, dedup, episodic CCR bridge, multi-agent, profiles, task-aware
- `tests/conftest.py`: 108 lines with 2 autouse fixtures + admin key injection
- `cutctx/tests/`: No `conftest.py`

**Test patterns**:
- Heavy use of `unittest.mock` (191 mock references in `cutctx/tests/`, many more in `tests/`)
- 1,186 asyncio references in `tests/` — significant async test coverage
- 386 TestClient/httpx.AsyncClient usages — proxy integration tests are thorough
- 4,902 references to `monkeypatch`/`tmp_path`/`tempfile` — good test isolation practices
- Class-based test organization in `cutctx/tests/` (e.g., `TestBasicDedup`, `TestAgentRegistry`, `TestTaskExtractorBasic`)

**Marker usage**:
- `@pytest.mark.real_llm`, `@pytest.mark.live`, `@pytest.mark.slow` — only 3 total in `tests/`
- `no_auto_admin` marker for testing 401 behavior
- `asyncio_mode = "auto"` in `pyproject.toml`

**Largest files (>1,000 lines)**:
| File | Lines | Tests |
|------|-------|-------|
| `tests/test_memory_system.py` | 1,831 | 104 |
| `tests/test_proxy_anthropic_cache_stability.py` | 1,591 | — |
| `tests/test_memory_handler_native_ops.py` | 1,505 | — |
| `tests/test_compression_store.py` | 1,455 | — |
| `tests/test_evals_benchmark.py` | 1,417 | — |
| `tests/test_critical_gaps.py` | 1,329 | — |
| `tests/test_proxy_savings_history.py` | 1,233 | — |
| `tests/test_ccr_batch_processor.py` | 1,196 | — |
| `tests/test_realignment_live_multi_turn.py` | 1,143 | — |
| `tests/test_release_workflows.py` | 1,123 | — |

15 files exceed 1,000 lines — several are candidates for splitting.

### 2. Rust Test Suite

**Location**: `crates/*/tests/` (integration), inline `#[cfg(test)]` modules

**cutctx-proxy integration tests** (44 files, 10,015 lines):
- Coverage of: responses API, metrics, compression, Bedrock (invoke/streaming/metrics/auth), Vertex, chat completions, cache control, schema sorting, tool sorting, SSE (Anthropic/OpenAI), health checks, HTTP, headers, licensing, volatile detection
- Largest: `integration_responses.rs` (908 lines), `integration_metrics.rs` (764 lines), `integration_compression.rs` (705 lines)

**cutctx-core integration tests** (11 files, 2,344 lines):
- Live zone dispatch, CCR roundtrip, cache control, token validation, auth mode, stack graphs, recommendations loader, tokenizer proptest

**Inline tests**:
- cutctx-core: 864 `#[test]` across 5 source modules
- cutctx-proxy: 256 `#[test]` across 4 source modules
- 135 `#[tokio::test]` async tests
- No `#[ignore]` or `#[should_panic]` annotations found — all tests are expected to pass

### 3. Coverage Configuration

**`codecov.yml`** (`.github/codecov.yml`):
```yaml
coverage:
  status:
    project:
      default:
        target: auto    # tracks against baseline, no floor
    patch:
      default:
        target: auto
```

**`pyproject.toml`** `[tool.coverage]`:
- `source = ["cutctx"]`, `branch = true`
- Omits `cutctx/cli.py` and `*/tests/*`
- No `fail_under` threshold

**Coverage upload points**:
- `install-native-e2e.yml`: `--cov=cutctx --cov-report=xml` → uploads to Codecov
- `wrap-native-e2e.yml`: `--cov=cutctx --cov-report=xml` → uploads to Codecov
- Main `ci.yml` test job: **NO** coverage collection or upload
- Rust `rust.yml`: **NO** coverage collection or upload

### 4. E2E Tests

**Location**: `e2e/`

- `test_control_plane_e2e.py`: 4 tests using FastAPI `TestClient` — tests license CRL, spend events, policies, audit events endpoints. All assert `status_code in [200, 501]` (accepts 501 for EE-only endpoints)
- `_lib/`: Test harness infrastructure (assertions, paths, shims, PowerShell shims)
- Docker-based: `e2e/wrap/Dockerfile` + `e2e/init/Dockerfile` run in CI

**What's covered**: Control plane endpoint wiring (license, spend, policies, audit)
**What's NOT covered**: Full request lifecycle through proxy, compression end-to-end, streaming e2e, WebSocket e2e (these are covered by Rust integration tests in `crates/cutctx-proxy/tests/e2e_real.rs` instead)

### 5. CI/CD

**`.github/workflows/ci.yml`** (441 lines):
- `changes` job: `dorny/paths-filter` — skips heavy work for docs-only changes
- `lint`: ruff + mypy, single run
- `build-wheel`: Maturin build once with fast `ci` cargo profile, shared via artifact
- `prefetch-model`: Downloads `all-MiniLM-L6-v2` once, warms HuggingFace cache
- `test`: 4 parallel shards via `pytest-split`, CPU-only torch, HF offline mode
- `test-extras`: Additional test job
- `test-agno`: Framework integration tests
- E2E: Docker-based wrap/init, Windows native, macOS native

**`.github/workflows/rust.yml`** (152 lines):
- `test`: fmt check + clippy + `cargo test --workspace`
- `wheels`: Multi-platform wheel builds (ubuntu, macOS ARM)
- `audit`: `cargo-audit` + `cargo-deny` (soft-fail)
- `parity-nightly`: Nightly Python↔Rust parity check (allowed to fail in Phase 0)

**Other workflows**: 25 total `.github/workflows/` files including chaos-testing (nightly k8s), benchmark, eval, Docker, docs, and release workflows.

### 6. Test Quality

**Isolation**:
- ✅ `conftest.py` autouse fixture resets cwd, rbac, webhooks, subscription tracker
- ✅ `conftest.py` restores logger propagation after each test
- ✅ `TOKENIZERS_PARALLELISM=false` set at module level to prevent deadlocks
- ✅ `CUTCTX_CCR_BACKEND=memory` forces in-memory backend for test isolation
- ✅ 4,902 uses of `monkeypatch`/`tmp_path`/`tempfile` across the suite
- ⚠️ `cutctx/tests/` has no `conftest.py` — no shared fixtures

**Flaky test detection**:
- No `@pytest.mark.flaky` or `flaky` plugin usage found
- No retry decorators found
- 3 `xfail`/`skip` references (all in `cutctx/tests/`) — minimal use of expected-failure markers
- Rust: No `#[ignore]` annotations found

**Fixture quality**:
- `tests/conftest.py`: Well-structured with admin key injection, state cleanup
- `cutctx/tests/`: 2 `@pytest.fixture` in `test_task_aware.py`, 0 conftest
- Heavy reliance on `unittest.mock.patch` rather than pytest fixtures for mocking

**Naming and organization**:
- Consistent `test_*.py` naming
- Class-based grouping in `cutctx/tests/` (e.g., `TestBasicDedup`, `TestAgentRegistry`)
- `tests/` has both flat files and subdirectories (`test_proxy/`, `test_compression/`, `test_memory/`, `test_cli/`, etc.)
- Some naming oddity: `test_handler_memoization_output_optimization_batch_routing_wiring.py` (58 words)

## Previous Issues — Verification

| Previous Issue | Status | Evidence |
|---|---|---|
| Rust coverage not tracked in Codecov | 🔴 **NOT FIXED** | No `cargo-tarpaulin` or `llvm-cov` in `rust.yml`; no codecov upload |
| No coverage thresholds | 🔴 **NOT FIXED** | `codecov.yml` uses `target: auto`; no `fail_under` in `pyproject.toml` |
| Large test_memory_system.py | 🟡 **NOT SPLIT** | Still 1,831 lines, 104 tests in one file |
| Python-level load tests | 🟡 **NOT ADDED** | `test_proxy_scalability.py` tests config objects, not throughput |

## Quick Wins

1. **Add Rust coverage tracking**: Add `cargo-tarpaulin` or `cargo-llvm-cov` step to `rust.yml`, upload to Codecov — **effort: ~30 min**
2. **Add Python coverage to main CI**: Add `--cov=cutctx --cov-report=xml` to the `pytest` command in ci.yml test shards, upload to Codecov — **effort: ~15 min**
3. **Set coverage thresholds**: Add `fail_under = 70` (or appropriate baseline) to `pyproject.toml` `[tool.coverage.report]`; set `target: 70` in `codecov.yml` — **effort: ~5 min**
4. **Generate `.test_durations`**: Run `pytest --store-durations` locally, commit the file — **effort: ~5 min**
5. **Add `conftest.py` to `cutctx/tests/`**: Extract shared fixtures — **effort: ~20 min**
6. **Split `test_memory_system.py`**: Break into `test_memory_system_queries.py`, `test_memory_system_storage.py`, `test_memory_system_lifecycle.py` — **effort: ~1 hr**
7. **Add `make coverage` target**: Add a Makefile target that runs pytest with `--cov` and opens the HTML report — **effort: ~5 min**

## File:line References

- `codecov.yml:8,11` — `target: auto` (no threshold)
- `.github/workflows/ci.yml:196-200` — pytest-split shards (no coverage)
- `.github/workflows/rust.yml:61-62` — `cargo test` without coverage
- `tests/conftest.py:54-108` — autouse isolation fixtures
- `tests/test_memory_system.py:1-1831` — monolithic file
- `tests/test_proxy_scalability.py:1-272` — config-only scalability tests
- `cutctx/tests/` — no conftest.py
- `pyproject.toml:543-558` — coverage config (no fail_under)
- `tests/` — 426 files, 8,191 test functions
- `crates/cutctx-proxy/tests/` — 44 files, 10,015 lines
- `crates/cutctx-core/tests/` — 11 files, 2,344 lines
