# Action Plan — Cutctx v0.30.0

**Source:** QA Audit (98/100, 2 minor failures) + Product Maturity Audit (58/100)
**Date:** 2026-07-10 (updated after re-audit)
**Owner:** Staff QA Engineer

---

## Status: All 27 Previously Blocking Bugs Are Fixed ✅

The Sprint 1 "Bugfix Blitz" from the previous plan is **complete**. All 27 test failures reported in the last audit are now passing:
- `_retry_request()` telemetry_tags parameter added
- Circuit breaker defaults fixed
- Header isolation leak fixed (8 tests)
- Savings tracker schema version + record_request fixed
- Memory bridge optional-dependency skipping fixed
- Smart orchestrator BDD assertions updated
- DSR cascade fixed
- Code compressor tree-sitter handling fixed
- All savings reconciliation + history tests fixed

**Remaining: 2 minor test issues (1 stale Playwright locator, 1 flaky toggle test)**

---

## How to Use This Plan

- Items are ordered by impact within each sprint
- Each item has a clear **done** condition
- Dependencies are explicit; parallelizable work is grouped
- Estiamtes in hours/days

---

## Sprint 1: Test Hygiene & CI Gates (Week 1 — 12h)

### 1.1 Fix 2 Remaining Test Failures (2h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| A1 | Update dashboard Playwright test locator — page was rewritten, `"Orchestrator Insights"` heading no longer exists | `tests/test_dashboard_orchestrator_policy_e2e.py:155` | `test_orchestrator_renders_provider_policy_status` passes | None |
| A2 | Stabilize flaky savings toggle test — add `wait_for_selector` before toggle interaction or increase timeout to 10s | `tests/test_dashboard_savings_period_and_metric_toggle.py` | Test passes consistently in batch runs | None |

### 1.2 CI Quality Gates (6h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| A3 | Add CI gate that enforces 0 failures on `-k "not slow and not real_llm and not live and not e2e"` subset | `.github/workflows/ci.yml` | PRs blocked on test failures in main test suite | None |
| A4 | Add `pip-audit` to CI — hard-fail on known vulnerabilities | `.github/workflows/ci.yml` | CI blocks merge on `pip-audit` findings | None |
| A5 | Add coverage upload from main CI workflow (currently only in `native-e2e`) | `.github/workflows/ci.yml` | Codecov receives data from every push | None |
| A6 | Set `fail_under = 70` in `pyproject.toml` coverage config | `pyproject.toml` | CI fails if coverage drops below 70% | A5 |
| A7 | Add Dependabot config for Python, Rust, Docker, GitHub Actions | `.github/dependabot.yml` | Dependabot opens PRs for all ecosystems | None |

### 1.3 Lock In the Gains (4h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| A8 | Snapshot current test durations — generate `.test_durations` for pytest-split shard balancing | `.test_durations` | CI shards are balanced within 10% | None |
| A9 | Run the full 15-batch test matrix and verify 0 failures before tagging release | — | Green check across all 15 batches | A1, A2 |

### Sprint 1 Exit Criteria

- [ ] `pytest tests/ -k "not slow and not real_llm and not live"` — 0 failures
- [ ] CI blocks merge on test failure + `pip-audit` finding
- [ ] Coverage visible in Codecov from main CI
- [ ] Dependabot opens PRs

---

## Sprint 2: Security & Rust Hardening (Week 2 — 40h)

### 2.1 Security Quick Wins (8h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| B1 | Change `cargo audit` from soft-fail to hard-fail in CI | `.github/workflows/rust.yml` | CI blocks merge on `cargo audit` finding | None |
| B2 | Add pre-commit hook scanning for `sk-proj-` API key patterns | `.pre-commit-config.yaml` + custom hook | Commit with real API key pattern is rejected | None |
| B3 | Remove hardcoded Ed25519 signing key from `.env.secret` | `.env.secret` | File contains no real private key material | None |
| B4 | Review and remove any remaining dev-mode debug flags in committed files | `.env.local` | `CUTCTX_ALLOW_DEBUG=1`, `CUTCTX_LOG_MESSAGES=1` not in committed config | B3 |

### 2.2 Rust Hardening (16h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| B5 | Replace 50% of `unwrap()` in proxy crate with `Result` + error context | `crates/cutctx-proxy/src/*.rs` | Half of proxy crate unwrap() calls replaced (target: <50 remaining) | None |
| B6 | Add panic hook that captures + logs context before process exit | `crates/cutctx-proxy/src/lib.rs` | `panic!()` produces structured log entry | None |
| B7 | Review and replace 50% of `panic!()` calls with `return Err(...)` | All `crates/*/src/**/*.rs` | 50% of non-fatal panic!() calls replaced | None |
| B8 | Add `cargo-tarpaulin` or `llvm-cov` to Rust CI workflow | `.github/workflows/rust.yml` | Rust coverage visible in Codecov | None |

### 2.3 Enterprise Safeguards (16h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| B9 | SQLite at-rest encryption for all DBs (memory, audit, spend, RBAC, org, SCIM) | `cutctx_ee/*/store.py`, `cutctx/*/store.py` | All SQLite files encrypted with `sqlcipher` or OS keychain | None |
| B10 | Add `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` to all SQLite backends | All SQLite store constructors | Concurrent reads don't produce `SQLITE_BUSY` | None |
| B11 | Add global exception handler + Sentry error tracking hook (env-gated, zero deps by default) | `proxy/server.py`, `pyproject.toml` | Unhandled exceptions produce structured log + Sentry event when `CUTCTX_SENTRY_DSN` set | None |
| B12 | Add structured JSON log format (`CUTCTX_LOG_FORMAT=json`) | `proxy/server.py`, logging config | JSON log lines ship with `@timestamp`, `level`, `logger`, `message`, `request_id` | B11 |

### Sprint 2 Exit Criteria

- [ ] `cargo audit` hard-fails in CI
- [ ] 50% of `unwrap()` calls replaced (proxy crate only)
- [ ] Panic hook captures context before exit
- [ ] SQLite databases encrypted at rest
- [ ] Structured JSON logging available via env var
- [ ] Error tracking hook installed and verified

---

## Sprint 3: Deployment & Enterprise Readiness (Week 3 — 40h)

### 3.1 k8s/Helm Fixes (12h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| C1 | Add PVC templates for all SQLite DBs (memory, audit, spend, RBAC, org, SCIM) | `k8s/deployment.yaml`, `helm/cutctx/templates/` | Pod restart preserves all data | None |
| C2 | Fix port mismatch — both deployment and Helm use 8787 | `k8s/deployment.yaml`, `helm/cutctx/values.yaml` | `kubectl apply -f k8s/` works | None |
| C3 | Fix UID mismatch — nonroot user (1000) consistent across Dockerfile + k8s | `Dockerfile`, `k8s/deployment.yaml` | EE modules can write to `~/.cutctx/` | None |
| C4 | Add Secret templates for all EE keys | `helm/cutctx/templates/secrets.yaml` | `helm install` completes without manual Secret creation | None |
| C5 | Update image tags to current release version | `k8s/deployment.yaml`, `helm/cutctx/values.yaml` | Deployed version matches release | None |
| C6 | Add ServiceMonitor for Prometheus operator | `helm/cutctx/templates/` | Prometheus auto-discovers proxy metrics | None |

### 3.2 Product Polish (16h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| C7 | Group CLI help output by user phase (Getting Started, Monitoring, Configuration, Admin) | `cli/main.py` | `cutctx --help` shows organized groups instead of 33+ flat commands | None |
| C8 | Add `cutctx config doctor` — validate env, detect conflicts, suggest optimal settings | `cli/config_check.py` (new subcommand) | Misconfigured `CUTCTX_*` env vars produce actionable warnings | None |
| C9 | Fix dashboard mobile overflow + add ARIA labels | Dashboard CSS + React | 375px viewport renders without horizontal scroll; sidebar has ARIA labels | None |
| C10 | Add dark mode for dashboard (CSS variables, no-JS flicker-free switch) | Dashboard CSS + React | `prefers-color-scheme: dark` applies dark theme | None |
| C11 | Add skip-to-content link + keyboard nav for dashboard | Dashboard React | WCAG 2.4.1 passes | None |

### 3.3 Developer Experience (12h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| C12 | Add `cutctx verify` command — compress content, compare model output between compressed and original | New CLI command | `cutctx verify "analyze" ./file.log` produces comparison report | None |
| C13 | Add module docstrings to ~50 Python files missing them | Various | `pydocstyle` passes with minimal config | None |
| C14 | Add READMEs to 5 major component directories (`proxy/`, `handlers/`, `transforms/`, `cache/`, `memory/`) | Each directory | Each directory has a `README.md` explaining purpose and structure | None |
| C15 | Move internal documents (QA, sales, competitive) from `audit/` to `docs/internal/` | `audit/*.md` → `docs/internal/` | User-facing docs clean of internal reports | None |

### Sprint 3 Exit Criteria

- [ ] `kubectl apply -f k8s/` produces a working stateful deployment
- [ ] `helm install cutctx ./helm/cutctx` completes without manual steps
- [ ] `cutctx --help` organized by user phase
- [ ] `cutctx config doctor` ships
- [ ] Dashboard responsive at 375px, passes skip-to-content check
- [ ] All Python files have module docstrings

---

## Sprint 4: Competitive & Maturity Lift (Week 4 — 40h)

### 4.1 Competitive Differentiation (16h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| D1 | Expand MCP tools from 3 → 15+ — add file read modes (map, summary, signatures), diff compression, agent context | `mcp_server.py` | `cutctx mcp tools` shows 15+ available tools | None |
| D2 | Publish public benchmark leaderboard (compression ratio, latency, accuracy vs RTK, LeanCTX, Compresr) | Docs site / GitHub Pages | Public page shows comparative benchmarks | None |
| D3 | Add deterministic compression mode (`--deterministic` — rule-based only, no ML models) | `transforms/pipeline.py` | `cutctx proxy --deterministic` compresses without loading ML models | None |
| D4 | Add CI/CD integration (`cutctx compress --check --baseline main`) | New CLI flag | `cutctx compress --check` returns drift diff vs baseline | None |

### 4.2 Enterprise Compliance (12h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| D5 | Kick off SOC 2 Type II audit — engage auditor, scope controls | External | Auditor engaged, scope document signed | C1-C6 (k8s), B9-B12 (security baseline) |
| D6 | SAML SSO end-to-end verification — test with a real IdP (Okta/AzureAD) | `cutctx_ee/sso.py` | Complete login flow works against external IdP | None |
| D7 | Create SBOM generation in CI — `cdxgen` or `syft` on every release | `.github/workflows/release.yml` | Release artifacts include SBOM | None |
| D8 | Add performance regression gates — `pytest-benchmark` with p50/p99 thresholds | CI config | CI fails if p50 compression latency regresses >10% | None |

### 4.3 Architecture Debt Reduction (12h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| D9 | Break up `proxy/server.py` (4,798 lines) — extract routes, middleware, stats, startup into separate modules | New modules in `proxy/` | `server.py` is <800 lines | None |
| D10 | Break up `proxy/handlers/openai/responses.py` (6,348 lines) — extract streaming, handlers, validation | New modules in `proxy/handlers/openai/` | `responses.py` is <1,000 lines | None |
| D11 | Break up `proxy/handlers/anthropic.py` (4,114 lines) — extract handler, streaming, tools logic | New modules in `proxy/handlers/` | `anthropic.py` is <1,000 lines | None |
| D12 | Schedule fuzz targets in CI (weekly or per-release) | `.github/workflows/fuzz.yml` | Fuzz harnesses run weekly with artifact output | None |
| D13 | Add load test with `locust` or `pytest-benchmark` for proxy under 50 concurrent connections | `tests/test_load/` | Throughput and p50/p99 latency baselines established | None |

### 4.4 Documentation & Community (4h)

| # | Action | File(s) | Done When | Deps |
|---|--------|---------|-----------|------|
| D14 | Publish `docs/superpowers/specs/` — architecture decision records for key decisions | New directory | Key architectural decisions documented with rationale | None |

### Sprint 4 Exit Criteria

- [ ] MCP tools expanded from 3 → 15+
- [ ] Public benchmark leaderboard published
- [ ] Deterministic compression mode ships
- [ ] SOC 2 auditor engaged
- [ ] SAML SSO end-to-end verified
- [ ] `server.py` < 800, `responses.py` < 1,000, `anthropic.py` < 1,000
- [ ] Performance regression gates block >10% regression
- [ ] Fuzz targets run weekly in CI

---

## Condensed 4-Week Timeline

```
Week 1 (Test Hygiene)        Week 2 (Security & Rust)
┌─────────────────────┐      ┌─────────────────────────────┐
│ A1  Fix Playwright  │  2h  │ B1  cargo audit hard-fail   │  1h
│ A2  Flaky toggle    │  1h  │ B2  Pre-commit key scan     │  1h
│ A3  CI test gate    │  2h  │ B3  Remove .env.secret key  │  1h
│ A4  pip-audit CI    │  1h  │ B4  Debug flags cleanup     │  1h
│ A5  Coverage upload │  2h  │ B5  Rust unwrap() reduction  │  8h
│ A6  fail_under=70   │  1h  │ B6  Rust panic hook         │  2h
│ A7  Dependabot      │  1h  │ B7  Replace panic!() calls  │  4h
│ A8  .test_durations │  1h  │ B8  Rust coverage in CI     │  2h
│ A9  Verify all      │  1h  │ B9  SQLite encryption       │  6h
│                     │      │ B10 WAL mode all DBs         │  2h
│ Total: 12h          │      │ B11 Global exception handler │  4h
└─────────────────────┘      │ B12 Structured JSON logging │  4h
                             │                             │
                             │ Total: 40h                  │
                             └─────────────────────────────┘

Week 3 (Deploy & DX)         Week 4 (Competitive & Maturity)
┌─────────────────────┐      ┌─────────────────────────────┐
│ C1  k8s PVCs        │  4h  │ D1  MCP tools 3→15+        │  8h
│ C2  k8s port fix    │  1h  │ D2  Public benchmarks       │  4h
│ C3  k8s UID fix     │  1h  │ D3  Deterministic mode      │  4h
│ C4  k8s EE Secrets  │  2h  │ D4  CI/CD compress --check  │  4h
│ C5  Image tags      │  1h  │ D5  SOC 2 kickoff           │  4h
│ C6  ServiceMonitor  │  2h  │ D6  SAML SSO e2e            │  4h
│ C7  CLI help groups │  2h  │ D7  SBOM in CI              │  2h
│ C8  config doctor   │  4h  │ D8  Perf regression gates   │  2h
│ C9  Dashboard resp  │  2h  │ D9  Break up server.py      │  4h
│ C10 Dark mode       │  3h  │ D10 Break up responses.py   │  4h
│ C11 a11y skip+keyb  │  2h  │ D11 Break up anthropic.py   │  4h
│ C12 cutctx verify   │  6h  │ D12 Fuzz CI schedule        │  2h
│ C13 Docstrings (50) │  4h  │ D13 Load tests              │  4h
│ C14 READMEs (5 dirs)│  2h  │ D14 ADR docs                │  2h
│ C15 Move internals  │  1h  │                             │
│                     │      │ Total: 40h                  │
│ Total: 40h          │      └─────────────────────────────┘
└─────────────────────┘
```

---

## Dependencies Graph

```
A1 (Playwright fix) ───────► (unblocks dashboard CI)
A5 (coverage upload) ──────► A6 (fail_under=70)

B5 (unwrap reduction) ─────► B7 (panic! replacement) — same crate
B9 (SQLite enc) ───────────► D5 (SOC 2 kickoff)
B10 (WAL mode) ────────────► (concurrent performance)

C1-C6 (k8s fixes) ─────────► D5 (SOC 2) — deployment baseline required
C12 (cutctx verify) ───────► D3 (deterministic mode) — shares pipeline paths

D9 (break server.py) ──────► D10 (break responses.py) — same patterns
D1 (MCP tools) ────────────► (competitive differentiation)
```

---

## Quick Wins (Do Today, <2h each)

1. **A1** — Fix Playwright test locator (`"Orchestrator Insights"` → `"Routing mode control"`) — 5min
2. **A2** — Increase timeout on flaky savings toggle test — 15min
3. **A3** — Add CI test gate — 30min
4. **A4** — Add `pip-audit` to CI — 1h
5. **A7** — Create `dependabot.yml` — 30min
6. **A8** — Generate `.test_durations` — 30min
7. **B3** — Remove hardcoded Ed25519 key from `.env.secret` — 5min
8. **C2** — Fix k8s port mismatch (8080→8787) — 10min
9. **C3** — Fix k8s UID mismatch — 20min

---

## Verification

After each sprint:

```bash
# Python test suite — must be 0 failures
uv run python -m pytest tests/ -k "not slow and not real_llm and not live" --tb=short -q --no-header

# Rust test suite
cargo test --workspace

# Lint
uv run ruff check cutctx/
uv run mypy cutctx/ --ignore-missing-imports

# Security (post-B1/B4)
uv run pip-audit
cargo audit

# Coverage (post-A5/A6)
# Check Codecov for main branch
```

**Baseline:** 98/100 QA score, 0 test failures (excluding 2 known minor issues).
**Target:** 82/100 product maturity score by end of Sprint 4.
