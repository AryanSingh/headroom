# CutCtx Testing Infrastructure & Coverage Analysis

**Date:** 2026-07-08  
**Scope:** Full-stack analysis across Python, Rust, E2E, CI/CD, and supporting infrastructure.

---

## 1. Test Structure

The project uses a **hybrid Python + Rust** architecture with two independent test ecosystems plus shared integration/E2E tests.

### Python Test Suite (`tests/`)
- **Framework:** pytest (v7+) with `pytest-cov`, `pytest-asyncio`, `pytest-split`
- **Config:** `pyproject.toml` → `[tool.pytest.ini_options]`
- **Test root:** `tests/` — 514 `test_*.py` files across 27 subdirectories
- **Test subdirectories:**
  - `tests/test_cache/`, `tests/test_compression/`, `tests/test_dashboard/`
  - `tests/test_evals/`, `tests/test_install/`, `tests/test_integrations/`
  - `tests/test_memory/`, `tests/test_proxy/`, `tests/test_providers/`
  - `tests/test_transforms/`, `tests/test_backends/`, `tests/test_cli/`
  - `tests/test_storage/`, `tests/test_mcp_registry/`, `tests/test_learn/`
  - `tests/test_scripts/`, `tests/parity/`, `tests/integrations/`, `tests/fixtures/`
- **Total Python test lines:** ~123,608 (across 403 `.py` files in root + subdirs)
- **Shared fixtures:** `tests/conftest.py` — sets `TOKENIZERS_PARALLELISM=false`, `CUTCTX_CCR_BACKEND=memory`, auto-injects admin API key via Starlette `TestClient` monkey-patch
- **Test markers:** `slow`, `real_llm`, `live`, `no_auto_admin`

### Rust Test Suite (`crates/`)
- **Framework:** Cargo built-in (`#[test]`)
- **Two crate roots:**
  - `crates/cutctx-core/` — 83 source files, 105 modules with `#[cfg(test)]`
  - `crates/cutctx-proxy/` — 59 source files
- **Integration tests:** `crates/cutctx-core/tests/` (10 files), `crates/cutctx-proxy/tests/` (30+ files)
- **Test topics:** auth modes, cache control, CCR backends/roundtrip, live zone thresholds/dispatch, recommendations, stack graphs, tokenizer proptest, SSE framing (Anthropic/OpenAI), various proxy integrations (bedrock, vertex, SSE, WebSocket, HTTP, headers, health, metrics, cache drift, schema sort, tool sort, volatile detector)

### E2E Test Infrastructure (`e2e/`, `tests/e2e_*.py`)
- **Docker-based declarative harness:** `e2e/_lib/harness.py` — runs `cutctx` subprocesses in isolated environments with shims
- **Control plane tests:** `e2e/test_control_plane_e2e.py` — license, spend, policies, audit endpoints
- **Docker runners:** `e2e/init/run.py`, `e2e/wrap/run.py`
- **Python-driven e2e:**
  - `tests/e2e_real_compression.py` — 390 lines, multi-turn compression verification
  - `tests/e2e_ws_codex_usage_headers.py` — WebSocket Codex header validation
  - `tests/e2e_ws_responses_compression.py` — Responses API streaming compression
- **CI E2E workflows:** init-e2e, init-native-e2e, install-native-e2e, wrap-e2e, wrap-native-e2e

### Fuzz Testing (`fuzz/`)
- **3 targets:** `fuzz_diff_compressor`, `fuzz_live_zone_anthropic`, `fuzz_smart_crusher`
- Cargo-based fuzzing setup with `Cargo.toml` and `fuzz_targets/`

---

## 2. Test Counts

| Layer | Count | Notes |
|-------|-------|-------|
| **Python test functions** | ~7,996 | `grep -r "def test_" tests/` |
| **Rust `#[test]` functions** | ~1,267 | Total across all crates |
| — cutctx-core (inline) | ~864 | In source files |
| — cutctx-core (integration) | ~91 | In `tests/` directory |
| — cutctx-proxy (inline) | ~256 | In source files |
| — cutctx-proxy (integration) | ~52 | In `tests/` directory |
| **E2E (Python)** | ~5 files | Dedicated e2e scripts |
| **Fuzz targets** | 3 | Rust-based |
| **Total (approximate)** | **~9,300+** | Combined Python + Rust |

---

## 3. Coverage Infrastructure

- **Tool:** Codecov (`codecov.yml`)
- **Config:** `project: target: auto` and `patch: target: auto` — no explicit threshold
- **Source tracking:** `coverage.run.source = ["cutctx"]`
- **Ignores:** `tests/**`, `scripts/tests/**`, `.github/**`, `.claude-plugin/**`
- **Status:** Codecov is configured in CI but no local `.coverage/` results directory exists — coverage is purely cloud-driven via CI runs
- **Notable gap:** Rust code coverage is **not** tracked in codecov.yml — only Python (`cutctx` package) is instrumented. Rust coverage would need `tarpaulin` or `grcov` + Codecov integration.

---

## 4. CI/CD Pipeline

**22 GitHub Actions workflows** covering the full testing spectrum:

| Workflow | Trigger | Scope |
|----------|---------|-------|
| `ci.yml` | Push/PR to main | Smart path-filter → lint, build-wheel, prefetch-model, **test (4 shards)**, extras, agno, commitlint, workflow-validation |
| `rust.yml` | Push/PR touching `crates/` | cargo fmt + clippy + test, plus wheel builds (linux + macOS) |
| `pr-health.yml` | PR events | Labels PRs needing rebase, with conflicts, or with CI failures |
| `chaos-testing.yml` | Nightly | k8s Kind cluster + pod evictions + synthetic load |
| `benchmark.yml` | Weekly + dispatch | Runs compression comparison benchmarks |
| `eval.yml` | Weekly + dispatch + PR to transforms | Compression quality evaluation suite |
| `init-e2e.yml` | Push/PR | Docker-based init CLI e2e |
| `wrap-e2e.yml` | Push/PR | Docker-based wrap CLI e2e |
| `init-native-e2e.yml` | Push/PR | Native (non-Docker) init e2e |
| `wrap-native-e2e.yml` | Push/PR | Native wrap e2e |
| `install-native-e2e.yml` | — | Install e2e |
| Others | Various | docs, docker, publish, release, sign-artifacts, stale, dependabot, devcontainers |

**CI test execution:** Python tests are sharded 4-way using `pytest-split`. Rust tests run serially via `cargo test --workspace`. Total CI timeout: 30 min per shard.

---

## 5. Test Quality Assessment

### Strengths
1. **Comprehensive coverage area:** Tests exercise compression pipeline (decision, policy, store, summary, safety, observability, determinism), proxy (handlers, SSE, WebSocket, headers, routes, warmup), memory system (tracker, sync, storage, ranking, routing), intelligence layer, TOIN, billing, reporting, dashboard, security (HMAC, RBAC, secrets, residency), and more.
2. **Well-structured Python tests:** Class-based organization with descriptive test names, clear docstrings, and scenario-based testing (empty messages, small passthrough, large compression, edge cases).
3. **Security-hardened fixtures:** `conftest.py` disables tokenizer parallelism, sets secure defaults, and monkey-patches admin auth headers — demonstrating security-conscious test infrastructure.
4. **Dual-language testing:** Python tests for the SDK layer, Rust tests for the core engine — each at the appropriate abstraction level.
5. **Fuzz + chaos + benchmarks:** Three specialized testing dimensions beyond unit/integration.
6. **Parity testing:** `tests/parity/` directory verifies Python ↔ Rust implementation equivalence for cache aligner, CCR, content detector, diff/log/smart crusher, tokenizer, and Codex/OpenAI contracts.

### Weaknesses
1. **No Rust coverage tracking:** Codecov only tracks Python (`cutctx` package). The Rust crates (`cutctx-core`, `cutctx-proxy`) are uncovered in CI coverage reporting.
2. **No explicit coverage thresholds:** `codecov.yml` uses `target: auto` — no minimum floor, no regression gates. A PR could drop coverage without failing.
3. **Test brittleness risk:** Many Python tests use mocks/patches for the Rust extension (`_core.*.so`), which can drift from actual Rust behavior.
4. **Large test files:** Several test files are oversized (e.g., `test_memory_system.py` at 65KB), making them hard to maintain and slow to run.
5. **`manual-testing-guide.md` not found:** Referenced in documentation but missing or renamed.
6. **No load/stress tests in Python:** The chaos testing is k8s-specific; no Python-level stress test for the proxy under concurrent load.
7. **Coverage not run locally:** No `.coverage/` directory or Makefile target for local coverage generation.

---

## 6. Gaps (What's Not Tested or Under-Tested)

| Area | Gap | Severity |
|------|-----|----------|
| **Rust coverage** | Not tracked in CI | Medium — risk of untested Rust code merging |
| **Regression gates** | No minimum coverage threshold | Medium — gradual coverage erosion possible |
| **Concurrent/load testing (Python)** | Python-level stress tests absent | Low — k8s chaos covers k8s deployment |
| **Cross-version Python testing** | CI only tests 3.12 (multi-version noted as "planned follow-up") | Medium |
| **macOS x86_64** | Explicitly excluded from wheel matrix (ONNX dependency) | Low — documented limitation |
| **Manual testing guide** | File referenced but not found | Low — QA playbook covers manual testing |
| **Local coverage workflow** | No Makefile target for `cargo-tarpaulin` or `pytest --cov` | Low |

---

## 7. Recommendations

1. **Add Rust coverage to Codecov:** Integrate `cargo-tarpaulin` or `grcov` into `rust.yml` and submit results to Codecov alongside Python coverage.
2. **Set explicit coverage thresholds:** Change `target: auto` to `target: 80%` (project) and `target: 75%` (patch) in `codecov.yml` to prevent regressions.
3. **Add local coverage make target:** Create `make coverage` that runs `pytest --cov=cutctx --cov-report=html` and/or `cargo tarpaulin`.
4. **Break up oversized test files:** Split `test_memory_system.py` (65KB) and other large files into domain-specific modules.
5. **Add Python-level load tests:** Create a benchmark/memory test for the proxy under high-concurrency Python requests (using `locust` or `pytest-benchmark`).
6. **Enable multi-version CI:** Add Python 3.10 and 3.13 to the test matrix (noted as planned in `ci.yml`).
7. **Generate cross-language coverage report:** Track which Rust functions are exercised by the Python test suite via the PyO3 bridge to identify dead or under-tested Rust code.

---

## Summary

The CutCtx project has an **exceptional test foundation** — ~9,300+ tests across Python and Rust, a robust sharded CI pipeline, fuzz testing, chaos engineering, dedicated E2E infrastructure, and code coverage tracking. The primary gaps are Rust coverage visibility, explicit regression thresholds, and local coverage tooling. The recommendations above are incremental improvements to an already strong testing posture.
