# CutCtx Consolidated QA Roadmap

**Generated:** 2026-07-08  
**Method:** 10 parallel specialist agents (architecture, frontend, backend, security, database, performance, testing, UX, accessibility, competitive analysis)  
**Scope:** Full-stack audit with actionable findings merged into a prioritized execution plan

---

## Priority Matrix

### 🔴 Phase 1 — Immediate (0-2 weeks)

| # | Domain | Finding | Action | Effort | Impact |
|---|--------|---------|--------|--------|--------|
| 1 | **Security** | **CRITICAL:** OpenAI API key (`sk-proj-nmPPq82Vld...`) in `.env.local` | Rotate key immediately. Audit git history. Add to `.gitignore` if not already. CI guard against committed secrets. | 1h | Prevents account takeover, financial loss |
| 2 | **Security** | **CRITICAL:** Neo4j default password fallback in `docker-compose.yml` | Remove `:-REPLACE_WITH_STRONG_PASSWORD` fallback. Fail startup if `NEO4J_AUTH` unset. Restrict port exposure. | 1h | Prevents database compromise |
| 3 | **Security** | **HIGH:** OIDC fail-open auth (`rbac.py:143`) | Change default to deny. `assert_valid` should fail-closed on any verification error. | 2h | Prevents auth bypass |
| 4 | **Security** | **HIGH:** Admin API key printed to stderr (`auth_mode.rs:89`) | Remove debug print. Redact in logs if logging is required. | 30m | Prevents credential leak |
| 5 | **Security** | Rotate exposed + add CI guard | Add CI lint rejecting `CUTCTX_ALLOW_DEBUG=1`, `LOG_MESSAGES=1`, and hardcoded secrets | 4h | Systemic prevention |
| 6 | **Architecture** | Rust proxy compression is passthrough (`CompressionMode::LiveZone` gated off) | Activate Phase B PR-B2: wire live-zone dispatchers, enable `LiveZone` mode by default | 2-3w | Unlocks Rust proxy value proposition |

### 🟡 Phase 2 — Short-term (2-4 weeks)

| # | Domain | Finding | Action | Effort | Impact |
|---|--------|---------|--------|--------|--------|
| 7 | **UX** | No first-run experience (`cutctx` shows nothing) | Add welcome screen showing proxy status, detected agents, suggested next steps. Group CLI help output by phase. | 1w | Retention — users see value immediately |
| 8 | **UX** | Error messages lack actionable guidance | Add the 3-question pattern to all errors: What happened? Why? What to do? | 1w | Reduces support burden, improves DX |
| 9 | **Frontend** | Component duplication (MetricCard x5, StatusBullet x4, etc.) | Extract shared `components/` directory. Consolidate MetricCard, StatusBullet, ToggleSwitch, SkeletonCard. | 3d | Reduces maintenance risk, enables consistent updates |
| 10 | **Frontend** | Per-page fetch boilerplate duplicated | Create shared `useApiFetch()` hook with loading/error/data states, deduplication, cleanup | 3d | ~40% reduction in per-page code |
| 11 | **Backend** | `proxy.rs` is 1909 lines | Split into route definitions, handler logic, forwarder module | 2d | Improves maintainability and reviewability |
| 12 | **Backend** | Broad `except Exception` in `compress.py` and `pipeline.py` | Add strict-mode flag, log full tracebacks, make failures debuggable | 2d | Prevents silent production failures |
| 13 | **Testing** | Rust coverage not tracked in Codecov | Integrate `cargo-tarpaulin` or `grcov` into `rust.yml` CI workflow | 2d | Visibility into untested Rust code |
| 14 | **Testing** | No coverage thresholds in `codecov.yml` | Set `target: 80%` project, `target: 75%` patch | 1d | Prevents coverage regression |
| 15 | **Database** | No data lifecycle policy for audit/spend DBs | Add configurable retention + archival for `cutctx_audit.db` and `spend_ledger.db` | 3d | Prevents unbounded storage growth |

### 🟢 Phase 3 — Medium-term (4-8 weeks)

| # | Domain | Finding | Action | Effort | Impact |
|---|--------|---------|--------|--------|--------|
| 16 | **Architecture** | Dual implementation drift risk (auth_mode) | Unify Rust and Python auth-mode logic behind a single source of truth (TOML config? shared crate?) | 2w | Eliminates divergence risk |
| 17 | **Performance** | Python proxy buffers entire response before compression | Implement streaming compression in Rust proxy (Phase B) | 2-3w | Reduces time-to-first-token |
| 18 | **Backend** | 23 provider modules with duplication | Reduce via registration-based provider factory pattern. `install_registry.py` hints at this. | 1w | Simplifies maintenance, new provider onboarding |
| 19 | **UX** | No `CutctxClient.from_env()` factory | Add factory that loads from env vars + standard config paths. Add `CutctxConfig.simple()` builder. | 3d | Dramatically improves SDK onboarding |
| 20 | **UX** | Configuration surface is overwhelming (700+ lines config model) | Add `cutctx config show --explain` with curated settings. Hide advanced behind `--advanced`. Add `config doctor`. | 1w | Reduces user cognitive load |
| 21 | **Frontend** | CSS monolith (2835 line `index.css`) | Split into scoped modules (tokens, typography, layout, components, pages) | 1w | Improves CSS maintainability |
| 22 | **Accessibility** | Missing skip-to-content link, trend-bar focus ring removed, generic page title | Add skip link, restore focus ring on `.trend-bar`, update `<title>` | 2d | WCAG AA compliance for keyboard users |
| 23 | **Accessibility** | `@keyframes shimmer` not disabled under `prefers-reduced-motion` | Add `@media (prefers-reduced-motion)` rule for skeleton animations | 1d | Protects motion-sensitive users |
| 24 | **Testing** | Large test files (65KB `test_memory_system.py`) | Split into domain-specific modules | 2d | Faster test runs, easier maintenance |
| 25 | **Testing** | Add Python-level load tests | Create benchmark for proxy under high-concurrency Python requests | 1w | Prevents regression under load |
| 26 | **Competitive** | Build observability bridge (OpenTelemetry export) | Export compression metrics in OTEL format for existing observability stacks | 2w | Removes barrier to adoption |

### 🔵 Phase 4 — Long-term (8+ weeks)

| # | Domain | Finding | Action | Effort | Impact |
|---|--------|---------|--------|--------|--------|
| 27 | **Architecture** | Pipeline extension system Python-only | Design Rust proxy plugin system (WASM? dynamic loading? trait-based?) | 4w | Enables third-party compression extensions |
| 28 | **Database** | No shared CCR across instances without Redis | Make Redis the default for multi-instance deployments, lazy-init for single-node | 2w | Enables horizontal scaling |
| 29 | **Performance** | No distributed cache without Redis | Add connection pooling, WAL-mode SQLite, periodic checkpoint to object store | 3w | Production-grade reliability |
| 30 | **Frontend** | Dashboard polling instead of SSE push | Add SSE endpoint for real-time dashboard updates (compression events, savings) | 2w | Real-time UX, reduced bandwidth |
| 31 | **Security** | Dependencies audit (`deny.toml` too permissive) | Tighten `deny.toml`: `copyleft = "deny/allow"`, add `yanked = "deny"`, add version advisory DB | 1w | Supply chain security |
| 32 | **UX** | Internal docs (QA, LEAD_GEN) mixed with user docs | Move to `internal/` directory. Create clear separation in README. | 2d | Reduces confusion for new users |
| 33 | **Competitive** | Compression-aware guardrails | Add lightweight PII/malcontent detection to the compression stream | 4w | Differentiates from competitors |
| 34 | **Competitive** | Model routing x compression | Route to cheapest capable model after compression. Combined 80-95% cost reduction. | 4w | Compelling cost optimization story |

---

## QA Summary by Domain

| Domain | Rating | Critical Issues | Quick Wins |
|--------|--------|----------------|------------|
| **Architecture** | 🟡 Good structure, Phase B key | Dual-runtime drift, passthrough proxy | Activate compression in Rust proxy |
| **Frontend** | 🟢 Strong visually | Component duplication, CSS monolith | Extract shared components |
| **Backend** | 🟡 Solid core | proxy.rs size, broad exception handlers | Split proxy.rs, add strict mode |
| **Security** | 🔴 2 critical issues | API key leak, default passwords | Rotate keys, remove defaults |
| **Database** | 🟡 Functional | No lifecycle, no shared CCR | Add retention policies |
| **Performance** | 🟡 Good baseline | Passthrough mode, buffered Python | Activate Rust proxy compression |
| **Testing** | 🟢 Excellent foundation | Rust coverage invisible | Add Codecov for Rust |
| **UX** | 🟡 Competent, friction points | No first-run, blind errors | Add welcome screen, better errors |
| **Accessibility** | 🟡 Solid bones, 3 HIGH | Skip link, focus ring, title | 3 quick CSS/JS fixes |
| **Competitive** | 🟡 Unique niche | Missing guardrails, observability | OTEL export bridge |

---

## Deliverables Created

All analysis documents written to `audit/`:
- `audit/architecture-analysis.md` — System architecture, component relationships, gaps
- `audit/frontend-analysis.md` — Dashboard component structure, CSS, data flow
- `audit/backend-analysis.md` — Rust + Python code quality, error handling, cross-layer integration
- `audit/security-analysis.md` — 12 findings with severity ratings, remediation steps
- `audit/database-analysis.md` — Storage architecture, caching, data lifecycle
- `audit/performance-analysis.md` — Compression throughput, bottlenecks, optimization
- `audit/testing-analysis.md` — ~9,300 tests, coverage gaps, 7 recommendations
- `audit/ux-analysis.md` — 7 UX dimensions, P0-P3 priority fixes
- `audit/accessibility-analysis.md` — WCAG AA assessment, 15 findings
- `audit/competitive-analysis.md` — Landscape map, positioning, threats
- **`audit/consolidated-roadmap.md`** — This file, merging all findings into prioritized 4-phase execution plan
