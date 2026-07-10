# Cutctx Consolidated QA Roadmap

**Generated:** 2026-07-10
**Method:** 10 parallel specialist agents (architecture, frontend, backend, security, database, performance, testing, UX, accessibility, competitive analysis)
**Previous audit:** July 8, 2026 (commit `2b6f5481`)
**Since then:** 7 commits landed — routing fixes, maturity score improvements, dashboard savings fix
**Scope:** Fresh full-stack audit with actionable findings merged into a prioritized execution plan

---

## Remediation Since July 8 Audit

| Finding | Status | Detail |
|---------|--------|--------|
| 🔴 Neo4j default password fallback | ✅ Mitigated | `docker-compose.yml` now uses `${NEO4J_AUTH:-neo4j/REPLACE_WITH_STRONG_PASSWORD}` — forces operator to set env var |
| 🟡 Dashboard current session $0 | ✅ Fixed | Commit `c6bdbf85` |
| 🟡 Model routing scope | ✅ Broadened | Low-complexity routing for Claude, OpenAI Responses path added |
| 🟡 Codex routing telemetry | ✅ Fixed | WS routing and telemetry corrected |
| 🔴 OpenAI API key in `.env.local` | ❌ **NOT ROTATED** | Same key `sk-proj-nmPPq82Vld...` still present at `.env.local:26` |
| 🔴 OIDC fail-open auth | ❌ **NOT FIXED** | RBAC is a shim to `cutctx_ee`; OSS has no auth enforcement |
| 🟠 Admin API key to stderr | ⚠️ Partial | Moved from logger to `sys.stderr.write()`, but still leaks to container orchestrators |
| 🟡 Rust coverage in Codecov | ❌ **NOT FIXED** | No coverage upload step in `rust.yml` |
| 🟡 Coverage thresholds | ❌ **NOT FIXED** | `target: auto` only, no `fail_under` |
| 🟡 `test_memory_system.py` split | ❌ **NOT FIXED** | Still 1,831 lines |
| 🟡 Python-level load tests | ❌ **NOT FIXED** | Only config-level assertions |
| 🟡 First-run experience | ❌ **NOT FIXED** | Still 38+ commands alphabetically |
| 🟡 Error message guidance | ❌ **NOT FIXED** | Structured details but no "what to do" |
| 🟡 Skip-to-content link | ❌ **NOT FIXED** | Missing from `App.jsx` |
| 🟡 Shimmer reduced-motion | ❌ **NOT FIXED** | Animation still not disabled |
| 🟡 Trend-bar focus ring | ❌ **NOT FIXED** | `outline: none` with decorative box-shadow |

---

## Priority Matrix

### 🔴 Phase 1 — Immediate (0-2 weeks)

Security, secrets, and the highest-leverage quick wins. Every item here either prevents a breach or removes a blocker for all subsequent work.

| # | Domain | Finding | Action | Effort | Impact |
|---|--------|---------|--------|--------|--------|
| 1 | **Security** | **CRITICAL:** OpenAI API key `sk-proj-nmPPq82Vld...` in `.env.local` — **NOT ROTATED since July 8 audit** | Rotate key immediately. Add CI pre-commit hook scanning for `sk-proj-` patterns. Add `.env.local` to `.gitignore` explicitly. Audit git history for leaked key. | 2h | Prevents account takeover. 4 weeks overdue. |
| 2 | **Security** | **CRITICAL:** MFA store failure silently allows request through (`server.py:3236-3241`) | Fail closed: deny request if MFA store unavailable when enrollment exists. Currently fail-open. | 1h | Prevents authentication bypass |
| 3 | **Security** | **HIGH:** Admin API key leaked to stderr (`server.py:3177`) | Print to `/dev/tty` only or use one-time file with `0600` permissions. Container orchestrators capture stderr. | 1h | Prevents credential leak in production |
| 4 | **Backend** | **CRITICAL:** 69 bare `except Exception:` in `server.py` | Audit each bare except. Convert to specific exception types. Add `strict=True` mode flag to re-raise unknown exceptions in production. | 3d | Prevents silent swallow of real errors |
| 5 | **Architecture** | **CRITICAL:** `server.py` is a 7,903-line god object | Split: extract routes, middleware, stats, startup, compression cache into focused modules. Leave ~500 lines for app lifecycle. | 1w | Removes single-file SPOF. Enables faster changes. |
| 6 | **Database** | **CRITICAL:** No schema migration system | Add Alembic or `PRAGMA user_version` based migration to all SQLite stores. Replace ad-hoc `_migrate_add_column` with silent except pass. | 1w | Prevents silent schema drift in production |
| 7 | **Database** | **HIGH:** Inconsistent WAL mode across Python SQLite backends (5 stores missing) | Add `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` to: `SqliteBackend`, `SQLiteStorage`, memory adapters, vector adapter, graph adapter | 1d | Prevents `SQLITE_BUSY` under concurrent load |
| 8 | **Performance** | **HIGH:** TTFT hardcoded to `ttfb_ms=0` — no actual measurement | Wire actual time-to-first-token measurement in both Python and Rust proxies. Currently hardcoded zero. | 1d | Enables latency regression detection |
| 9 | **Testing** | **🔴 Rust coverage not tracked in Codecov** | Add `cargo-tarpaulin` or `llvm-cov` to `rust.yml` workflow + Codecov upload | 2d | No visibility into untested Rust code |
| 10 | **Testing** | **🔴 No coverage thresholds** | Set `fail_under = 70` in `pyproject.toml` and `target: 80%` in `codecov.yml` | 1d | Prevents coverage regression |
| 11 | **Architecture** | **HIGH:** `deny.toml` still permissive (`multiple-versions = "allow"`, `wildcards = "allow"`) | Set to `"warn"` or `"deny"`. Run `cargo deny check bans`. Fix version duplication. | 1d | Prevents stale dependency vulnerabilities |
| 12 | **Security** | **MEDIUM:** No SSRF protection on upstream URL forwarding | Validate upstream URLs against private IP blocklist. Reject `127.0.0.0/8`, `10.0.0.0/8`, etc. | 3h | Prevents SSRF attacks through proxy |
| 13 | **Security** | **MEDIUM:** Dev-mode flags (`CUTCTX_ALLOW_DEBUG=1`, `CUTCTX_LOG_MESSAGES=1`) in `.env.local` | Add CI check: fail build if these flags appear in committed files. Add production warning in `.env.example`. | 1h | Prevents dangerous config leakage |

### 🟡 Phase 2 — Short-term (2-4 weeks)

UX improvements, frontend maintainability, backend quality. These items directly impact developer productivity and user onboarding.

| # | Domain | Finding | Action | Effort | Impact |
|---|--------|---------|--------|--------|--------|
| 14 | **Frontend** | **HIGH:** Component duplication (MetricCard x5, StatusBullet x3, ToggleSwitch x2, SkeletonCard x2) | Extract `src/components/` with normalized interfaces. Consolidate MetricCard, StatusBullet, ToggleSwitch, SkeletonCard. | 3d | Reduces maintenance risk for all 6 pages |
| 15 | **Frontend** | **HIGH:** Monolithic 3,040-line `index.css` | Split into scoped modules: tokens, typography, layout, components, pages. CSS modules or scoped styles per component. | 1w | Eliminates merge conflicts, improves discoverability |
| 16 | **Frontend** | **MEDIUM:** `Overview.jsx` is 2,760 lines | Extract TrendChart, SavingsPanel, data transformation helpers into separate files. | 1d | Improves navigability and testability |
| 17 | **UX** | **🔴:** CLI help shows 38+ commands alphabetically — no phase grouping | Organize help output by user phase: Getting Started, Monitoring, Configuration, Administration, Advanced. Hide esoteric commands behind `--advanced`. | 2d | First impression improvement — new users see path, not wall |
| 18 | **UX** | **🔴:** No `CutctxClient.from_env()` factory | Add factory that loads from env vars + standard config paths. Current best path is 4+ lines. | 1d | Drops first-compression boilerplate by 50% |
| 19 | **UX** | **🔴:** 707-line config model overwhelms new users | Add `cutctx config show --explain` with curated settings. Hide advanced behind `--advanced`. Add `config doctor` command. | 1w | Reduces cognitive load for configuration |
| 20 | **UX** | **HIGH:** Error messages lack "what to do next" | Add the 3-question pattern (What happened? Why? What to do?) to: port-in-use, missing API key, proxy connection failures, config validation errors. | 3d | Reduces support burden |
| 21 | **Backend** | **HIGH:** Provider pattern duplication across 5+ files | Reduce via registration-based provider factory. `install_registry.py` hints at this pattern. | 1w | Simplifies new provider onboarding |
| 22 | **Backend** | **HIGH:** ProxyConfig has 60+ fields across 37 config classes | Consolidate config model hierarchy. Group related settings. Add validation at construction time. | 2d | Reduces config surface complexity |
| 23 | **Database** | **MEDIUM:** Unbounded growth in `cutctx_audit.db` and `spend_ledger.db` | Add configurable retention + archival. Monthly rotation by default. `VACUUM` after cleanup. | 2d | Prevents unbounded disk growth |
| 24 | **Accessibility** | **CRITICAL:** No skip-to-content link (WCAG 2.4.1) | Add `<a href="#main-content" className="skip-link">` at top of `App.jsx`. Style as position-fixed offscreen until focused. | 5min | Keyboard users can bypass 9+ sidebar links |
| 25 | **Accessibility** | **HIGH:** `@keyframes shimmer` not disabled under `prefers-reduced-motion` | Add `animation: none !important` to the reduced-motion block at `index.css:2913`. Currently only disables transitions. | 2min | Protects users with vestibular disorders |
| 26 | **Accessibility** | **HIGH:** Trend bar focus ring removed (`outline: none` with decorative box-shadow) | Replace `box-shadow` with visible `outline: 2px solid var(--teal)` on `.trend-bar:focus-visible` | 2min | Keyboard users can navigate trend chart |
| 27 | **Testing** | **MEDIUM:** `test_memory_system.py` not split (1,831 lines) | Refactor into domain-specific modules: `test_memory_crud.py`, `test_memory_search.py`, `test_memory_retention.py` | 2d | Faster test runs, easier debugging |

### 🟢 Phase 3 — Medium-term (4-8 weeks)

Architecture improvements, competitive positioning, and strategic quality investments.

| # | Domain | Finding | Action | Effort | Impact |
|---|--------|---------|--------|--------|--------|
| 28 | **Architecture** | **HIGH:** Python/Rust compression pipeline duplication | Prioritize Python code removal for transforms that have verified Rust parity. Gate behind `_core.so` availability. Sunset Python fallback implementations. | 2w | Eliminates duplicate maintenance surface |
| 29 | **Architecture** | **MEDIUM:** Model router is Python-only (705 lines) | Port model routing logic to Rust. Add Rust-side `ModelRouter` stub that at minimum can classify and route. | 2w | Enables Rust-only proxy path |
| 30 | **Performance** | **HIGH:** Gemini compression not wired in Rust proxy | Implement `live_zone_gemini.rs` for `/v1beta/...` paths. Currently all Gemini requests bypass compression. | 1w | Captures Gemini user segment |
| 31 | **Performance** | **MEDIUM:** Semantic cache single `asyncio.Lock` bottleneck | Replace single lock with sharded locking or read-write lock. At minimum, exclude `stats()` from acquiring the lock. | 3d | Reduces lock contention under load |
| 32 | **Performance** | **MEDIUM:** No Python-level load tests in test suite | Create benchmark using `locust` or `pytest-benchmark` for proxy under high-concurrency. Test throughput, p50/p99 latency. | 1w | Prevents performance regression |
| 33 | **Competitive** | **🔴 HIGH threat:** LeanCTX shipping 81 MCP tools, knowledge graph, daily iteration | Accelerate MCP tool coverage. Target: 20+ tools. Add knowledge graph CCP integration. Improve cross-agent memory surface. | 3w | Closes fastest-growing competitor gap |
| 34 | **Competitive** | **🔴 Enterprise blocker:** No SOC 2 | Kick off SOC 2 Type II audit. Engage auditor. Implement required controls (access review, incident response, change management). | 4w+ | Unblocks enterprise procurement |
| 35 | **Competitive** | **🔴 Enterprise blocker:** No SAML SSO | Implement SAML SSO provider integration. Enterprise mandate for many buyers. | 2w | Unblocks enterprise deals |
| 36 | **Competitive** | **HIGH:** No verification/hallucination guard | Add compression-aware guardrail: lightweight PII/malcontent detection, faithfulness verification for compressed output. Neutralizes #1 CISO objection. | 3w | Differentiates from competitors, addresses enterprise risk |
| 37 | **UX** | **MEDIUM:** No `config doctor` validation command | Build `cutctx config doctor` that validates environment, detects conflicts, suggests optimal settings for detected agent + provider combination. | 1w | Prevents misconfiguration |
| 38 | **Accessibility** | **MEDIUM:** Light theme tertiary text contrast needs verification | Manual color contrast audit of all light theme text colors. Adjust to meet WCAG AA 4.5:1 ratio. | 1d | Ensures WCAG AA compliance |
| 39 | **Testing** | **MEDIUM:** No Python-level load tests | Add concurrent request load test with `pytest-benchmark` or `locust`. Verify throughput and latency under 50 concurrent connections. | 1w | Prevents regression under load |
| 40 | **Testing** | **MEDIUM:** pytest-split without `.test_durations` file | Generate `.test_durations` from CI run history. Rebalance shards. | 1d | Reduces CI wall-clock time |

### 🔵 Phase 4 — Long-term (8+ weeks)

Strategic investments in architecture, enterprise readiness, and market differentiation.

| # | Domain | Finding | Action | Effort | Impact |
|---|--------|---------|--------|--------|--------|
| 41 | **Architecture** | Pipeline extension system Python-only | Design Rust proxy plugin system (WASM? trait-based dynamic dispatch?). Enable third-party compression extensions. | 4w | Ecosystem moat |
| 42 | **Architecture** | Auth/RBAC boundary opaque (OSS can't see `cutctx_ee` RBAC) | Open-source the RBAC module or document the full auth flow for community contributors | 2w | Community trust and contribution enablement |
| 43 | **Performance** | Python proxy buffers entire response before compression | Implement streaming compression in Rust proxy (Phase B advancement). Reduce time-to-first-token. | 3w | Competitive latency advantage |
| 44 | **Database** | No shared CCR across instances without Redis | Make Redis the default for multi-instance deployments. Lazy-init for single-node. Connection pooling. | 2w | Enables horizontal scaling |
| 45 | **Frontend** | Dashboard polling instead of SSE push | Add SSE endpoint for real-time dashboard updates (compression events, savings). | 2w | Real-time UX, reduced bandwidth |
| 46 | **Security** | Dependencies audit: `deny.toml` too permissive | Tighten: `copyleft = "deny/allow"`, `yanked = "deny"`, add version advisory DB | 1w | Supply chain security hardening |
| 47 | **Competitive** | Compression-aware guardrails (PII/malcontent detection) | Add lightweight detection to the compression stream. Differentiates from all competitors. | 4w | Unique enterprise feature |
| 48 | **Competitive** | Model routing × compression combined story | Route to cheapest capable model AFTER compression. Combined 80-95% cost reduction narrative. | 4w | Compelling cost optimization story |
| 49 | **Competitive** | OTEL observability bridge | Export compression metrics in OpenTelemetry format for existing observability stacks. Removes monitoring adoption barrier. | 2w | Removes barrier to enterprise adoption |
| 50 | **UX** | Internal docs (QA, LEAD_GEN) mixed with user-facing docs | Move internal docs to `docs/internal/` directory. Create clear separation in README and docs navigation. | 1d | Reduces confusion for new users |

---

## QA Summary by Domain

| Domain | Rating | Critical Issues | Quick Wins | Since July 8 |
|--------|--------|----------------|------------|--------------|
| **Architecture** | 🟢 Good structure, Phase B key | server.py god object, Python/Rust duplication | Split server.py, tighten deny.toml | Model routing improved; deny.toml still permissive |
| **Frontend** | 🟡 Solid visually, maintenance debt | Component duplication ×5, 3K-line CSS | Extract shared components | Dashboard $0 savings fixed |
| **Backend** | 🟡 Solid core, patched surface | 69 bare except, provider duplication | Audit/replace bare except clauses | Routing fixes landed |
| **Security** | 🟡 MODERATE — 2 CRITICAL still open | API key NOT rotated, MFA fail-open | Rotate key, CI pre-commit hooks | 1 of 4 previous findings fully fixed |
| **Database** | 🟡 Functional, growth risks | No migration system, 5 stores missing WAL | Add WAL mode, VACUUM schedule | No improvement since July 8 |
| **Performance** | 🟡 Good baseline | TTFT hardcoded to 0ms, Gemini passthrough | Wire real TTFT measurement | No improvement since July 8 |
| **Testing** | 🟢 Excellent foundation, 2 gaps | Rust coverage invisible, no thresholds | Add cargo-tarpaulin to CI | All 4 previous issues still open |
| **UX** | 🟡 Functional, not delightful | No first-run flow, no from_env() | Group CLI help, add factory | No improvement since July 8 |
| **Accessibility** | 🟡 62% WCAG AA | Skip link missing, shimmer reduced-motion | 3 quick CSS fixes | Page titles fixed; skip link remains |
| **Competitive** | 🟡 Strong niche, critical gaps | LeanCTX closing fast, no SOC 2/SAML | SOC 2 audit kickoff, accelerate MCP | Landscape shifted — LeanCTX accelerating |

---

## Deliverables Created

All analysis documents written to `audit/`:
- `audit/architecture-analysis.md` — System architecture, component coupling, Phase B status (🟢)
- `audit/frontend-analysis.md` — Dashboard component structure, CSS monolith, data flow (🟡)
- `audit/backend-analysis.md` — Rust + Python code quality, error handling, PyO3 bridge (🟡)
- `audit/security-analysis.md` — 15 findings (2 CRITICAL), previous remediation status (🟡)
- `audit/database-analysis.md` — Storage layers, schema migration, WAL consistency (🟡)
- `audit/performance-analysis.md` — Compression throughput, TTFT gap, Rust proxy status (🟡)
- `audit/testing-analysis.md` — ~8,200 Python tests, coverage gaps, CI quality (🟢)
- `audit/ux-analysis.md` — CLI/SDK/config/dashboard/error UX, 5 critical issues (🟡)
- `audit/accessibility-analysis.md` — WCAG AA assessment, 7 findings, 62% compliance (🟡)
- `audit/competitive-analysis.md` — Landscape map, LeanCTX threat, enterprise gaps (🟡)
- **`audit/consolidated-roadmap.md`** — This file, 50-item 4-phase execution plan
