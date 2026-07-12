# Cutctx — Consolidated Strategic Roadmap

**Generated:** 2026-07-10
**Sources:** 12 parallel domain audits (architecture, backend, security, database, performance, testing, frontend, UX, accessibility, competitive, commercial-readiness, production-readiness) + competitive gap analysis
**Supersedes:** `audit/consolidated-roadmap.md` (July 8, 50-item plan — several items remain unaddressed)

---

## Executive Summary

Cutctx has exceptional technical foundations — best-in-class compression pipeline (SmartCrusher at 0.22ms), reversible CCR, cross-agent memory, 4-language SDKs, and production-grade k8s deployment. The dual-runtime architecture (Python proxy + Rust binary) is intentional and well-executed. The engineering team has done outstanding work.

However, the product is blocked from commercialization by two fundamental gaps: (a) **cutctx.dev is NXDOMAIN** — every doc link, security contact, and email bounces; (b) **there is no working payment path** — Stripe webhook handlers exist but the checkout flow is dead. Additionally, 4 of 5 critical security findings from the July 8 audit remain unremediated, including an unrotated OpenAI API key and a fail-open MFA store. The `server.py` god object (7,903 lines) and absent schema migration system represent structural risks that compound with every sprint.

The path forward is clear: fix the security blockers and domain/payment gaps in the first 2 weeks to unlock a design-partner pilot, then execute a 3-phase roadmap that hardens the product (Phase 1), closes competitive gaps (Phase 2), and enables enterprise/self-serve scale (Phase 3). LeanCTX is the most urgent competitive threat — shipping daily with 81 MCP tools, 10 read modes, and knowledge graph — but Cutctx's CCR reversibility, 5-source attribution, and multi-format compression remain unmatched moats.

---

## Current State Scorecard

| Dimension | Score | Trend | Source Audit |
|-----------|-------|-------|--------------|
| Production Readiness | 58/100 | → | production-readiness.md |
| Paying-Customer Readiness (Pilot) | 82/100 | ↑ | paying-customer-readiness.md |
| Paying-Customer Readiness (Self-Serve) | 58/100 | → | paying-customer-readiness.md |
| Security | 45/100 | → | security-analysis.md |
| Architecture | 🟢 Good | → | architecture-analysis.md |
| Backend Code Quality | 🟡 Fair | → | backend-analysis.md |
| Database & Storage | 🟡 Fair | → | database-analysis.md |
| Performance | 🟡 Good w/ gaps | → | performance-analysis.md |
| Testing | 🟢 Strong | → | testing-analysis.md |
| Frontend | 🟡 Fair | → | frontend-analysis.md |
| UX | 🟡 Fair | → | ux-analysis.md |
| Accessibility | 62% WCAG AA | ↑ | accessibility-analysis.md |
| Competitive Position | 🟡 Strong niche | → | competitive-analysis.md |

---

## RICE Scoring Methodology

Each item scored on four dimensions:
- **Reach** (1-10): How many users/deals does this affect?
- **Impact** (1-3): 3 = massive, 2 = high, 1 = medium
- **Confidence** (1-3): 3 = certain, 2 = likely, 1 = uncertain
- **Effort** (1-10): Person-weeks. 1 = trivial, 10 = major initiative

**RICE = (Reach × Impact × Confidence) / Effort**

---

## Phase 1: Foundation & Pilot Launch (Weeks 1-4)

**Goal:** Fix all security blockers, unlock design-partner pilot, establish commercial foundation.
**Go/No-Go Gate:** Domain live, emails forwarding, license enforcement working, pilot contract signed, API key rotated, MFA fail-closed.

### Workstream 1A: Security & Secrets (Owner: Security Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 1A-1 | 🔴 Rotate OpenAI API key in `.env.local` + add CI pre-commit scanning for `sk-proj-` patterns | 30 | 2h | None | SEC-01, production-readiness PR-1 |
| 1A-2 | 🔴 Fix MFA fail-open: deny request when store unavailable if enrollment exists (`server.py:3236-3241`) | 30 | 1h | None | SEC-05, production-readiness PR-2 |
| 1A-3 | 🟠 Fix admin API key stderr leak: print to `/dev/tty` or one-time file with `0600` perms (`server.py:3177`) | 20 | 2h | None | SEC-04, production-readiness PR-3 |
| 1A-4 | 🟠 Add SSRF protection: validate upstream URLs against private IP blocklist (`127.0.0.0/8`, `10.0.0.0/8`, etc.) | 15 | 3h | None | SEC-06, production-readiness PR-5 |
| 1A-5 | 🟠 Add `.env.local` to `.gitignore` explicitly + verify not tracked | 20 | 30m | None | SEC-02 |
| 1A-6 | 🟡 Add CI security scanning: gitleaks, cargo audit, pip-audit | 12 | 4h | None | SEC-15 |
| 1A-7 | 🟡 Enable firewall by default in production configs + add startup warning | 8 | 30m | None | SEC-11 |
| 1A-8 | 🟡 Tighten `deny.toml`: remove MPL-2.0, set `multiple-versions = "warn"` | 8 | 2h | None | SEC-09, SEC-10 |

### Workstream 1B: Commercial Foundation (Owner: Founder)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 1B-1 | 🔴 Register cutctx.dev ($12/yr), redirect to GitHub README as landing page | 30 | 1h | None | paying-customer-readiness P0 |
| 1B-2 | 🔴 Set up email forwarding: `hello@`, `security@`, `conduct@` to founder's email | 30 | 30m | 1B-1 | paying-customer-readiness P0 |
| 1B-3 | 🔴 Fix license enforcement: `watermark.py:185-204` — raise `LicenseViolation` when DB returns no matching key | 20 | 2h | None | paying-customer-readiness P0 |
| 1B-4 | 🔴 Prepare pilot contract: fill MSA template with Payzli Inc., get counsel review | 20 | 1w (legal) | None | paying-customer-readiness P0 |

### Workstream 1C: Backend Hardening (Owner: Backend Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 1C-1 | 🟠 Ban bare `except Exception` in proxy code: audit top-10 highest-impact sites (auth middleware, SSE streaming, startup lifecycle) | 15 | 3d | None | backend-analysis P0 |
| 1C-2 | 🟠 Add `strict` mode to `compress()`: when `True`, re-raise instead of swallowing (`compress.py:352`) | 12 | 30m | None | backend-analysis quick-win |
| 1C-3 | 🟡 Version-pin Rust `.abi3.so` to Python package version | 8 | 2h | None | backend-analysis P1 |
| 1C-4 | 🟡 Add WAL mode to Python `SqliteBackend` (`cache/backends/sqlite.py:41`) | 10 | 1h | None | database-analysis P0 |
| 1C-5 | 🟡 Add schema version tracking (`PRAGMA user_version`) to all SQLite databases | 10 | 1w | None | database-analysis P0 |

### Workstream 1D: UX Quick Wins (Owner: Frontend/UX Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 1D-1 | 🟠 Add `CutctxClient.from_env()` factory method | 15 | 2h | None | ux-analysis #1 |
| 1D-2 | 🟠 Group CLI help by user phase (Getting Started / Daily Use / Advanced / Admin) | 12 | 1d | None | ux-analysis #3 |
| 1D-3 | 🟡 Add first-run welcome message when `cutctx` invoked with no args | 8 | 30m | None | ux-analysis #4 |
| 1D-4 | 🟡 Add "What to do" guidance to common error messages | 10 | 1d | None | ux-analysis #5 |
| 1D-5 | 🟡 Add skip-to-content link in `App.jsx` | 10 | 15m | None | accessibility-analysis C-1 |
| 1D-6 | 🟡 Fix shimmer animation under `prefers-reduced-motion` | 8 | 15m | None | accessibility-analysis H-1 |
| 1D-7 | 🟡 Fix trend-bar focus ring: remove `outline: none`, add `focus-visible` styles | 8 | 15m | None | accessibility-analysis H-2 |

### Phase 1 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Security: Unrotated keys | 0 | CI scan passes |
| Security: MFA fail-open | 0 | MFA store failure denies request |
| Domain: cutctx.dev | Resolves | `dig cutctx.dev` returns A record |
| Email: hello@, security@ | Deliverable | Test email received |
| License enforcement | Working | Trial key triggers `LicenseViolation` |
| Pilot contract | Signed | Legal review complete |
| Bare except ratio (proxy) | <20 (from 69-127) | grep count in server.py |
| WCAG AA compliance | >70% (from 62%) | Accessibility audit re-check |

---

## Phase 2: Competitive Hardening & Pilot Scale (Weeks 5-12)

**Goal:** Close critical competitive gaps, onboard 3-5 design partners, build case studies, wire Stripe.
**Go/No-Go Gate:** 3+ design partners active, Stripe checkout working, Gemini compression live, TTFT measured, component duplication resolved, coverage thresholds enforced.

### Workstream 2A: Security & Compliance (Owner: Security Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 2A-1 | 🟠 Implement minimal OSS RBAC fallback (deny-all for unprivileged users) | 12 | 4h | None | SEC-03, production-readiness |
| 2A-2 | 🟠 Add auth failure rate limiting: IP-based throttling on admin auth endpoint | 10 | 3h | None | SEC-13 |
| 2A-3 | 🟡 Fund SOC 2 engagement ($45-70K) | 8 | 1w (legal) | Revenue from pilots | paying-customer-readiness |
| 2A-4 | 🟡 Fund pentest ($15-25K) | 8 | 1d (procurement) | Revenue from pilots | paying-customer-readiness |

### Workstream 2B: Architecture & Backend (Owner: Architecture Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 2B-1 | 🔴 Begin `server.py` decomposition: extract routes, middleware, stats, startup into focused modules (target: ~500 lines for app lifecycle) | 15 | 1w | None | architecture-analysis, consolidated-roadmap #5 |
| 2B-2 | 🟠 Wire Gemini compression in Rust proxy (`live_zone_gemini.rs`) | 12 | 2w | None | architecture-analysis, performance-analysis |
| 2B-3 | 🟠 Collate provider resolution chain: move `_warn_unknown_model` to base class (eliminate 5× duplication) | 8 | 1d | None | backend-analysis P1 |
| 2B-4 | 🟡 Single-source config schema: generate Python + Rust from one source | 8 | 1w | None | backend-analysis P2 |
| 2B-5 | 🟡 Add connection pooling or per-thread singleton for hot-path SQLite stores | 6 | 2d | None | database-analysis P1 |

### Workstream 2C: Performance & Measurement (Owner: Performance Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 2C-1 | 🟠 Measure actual TTFT overhead: instrument streaming path to record time from request receipt to first upstream byte | 12 | 2d | None | performance-analysis |
| 2C-2 | 🟠 Profile ContentRouter decision overhead (65ms): cache routing decision or use cheaper classifier for common types | 10 | 3d | None | performance-analysis |
| 2C-3 | 🟡 Add `max_size_bytes` to SemanticCache (cap total memory, not just entry count) | 8 | 1h | None | performance-analysis |
| 2C-4 | 🟡 Publish latency benchmark results: add CI step to run `bench_latency.py` and commit `LATENCY_BENCHMARKS.md` | 8 | 2d | None | performance-analysis |
| 2C-5 | 🟡 Add `asyncio.Lock` contention metrics on SemanticCache | 6 | 1h | None | performance-analysis |

### Workstream 2D: Testing & Quality (Owner: QA Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 2D-1 | 🟠 Add Rust coverage tracking: `cargo-tarpaulin` or `cargo-llvm-cov` in `rust.yml`, upload to Codecov | 12 | 30m | None | testing-analysis |
| 2D-2 | 🟠 Add coverage thresholds: `fail_under = 70` in `pyproject.toml`, `target: 70` in `codecov.yml` | 10 | 5m | None | testing-analysis |
| 2D-3 | 🟠 Add Python coverage to main CI: `--cov=cutctx --cov-report=xml` in ci.yml | 10 | 15m | None | testing-analysis |
| 2D-4 | 🟡 Split `test_memory_system.py` (1,831 lines) into 3 focused files | 8 | 1h | None | testing-analysis |
| 2D-5 | 🟡 Add Python-level load/stress tests (actual throughput, not just config assertions) | 8 | 2d | None | testing-analysis |
| 2D-6 | 🟡 Add `conftest.py` to `cutctx/tests/` with shared fixtures | 6 | 20m | None | testing-analysis |

### Workstream 2E: Frontend & UX (Owner: Frontend Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 2E-1 | 🟠 Extract shared components: `MetricCard`, `StatusBullet`, `ToggleSwitch`, `SkeletonCard` to `src/components/` | 12 | 2d | None | frontend-analysis |
| 2E-2 | 🟠 Break up `Overview.jsx` (1,006 lines) into smaller files | 10 | 1d | None | frontend-analysis |
| 2E-3 | 🟡 Move inline styles to CSS classes (reduce 445 inline `style=` attributes) | 8 | 3d | None | frontend-analysis |
| 2E-4 | 🟡 Add keyboard navigation to trend charts (tab, arrow keys, Enter) | 8 | 2d | None | accessibility-analysis H-4 |
| 2E-5 | 🟡 Wire direct Stripe Checkout (replace dead PitchToShip path) | 12 | 2-3d | None | paying-customer-readiness |
| 2E-6 | 🟡 Fix tenant isolation in memory backends | 10 | 3-5d | None | paying-customer-readiness |

### Workstream 2F: Commercial & GTM (Owner: Founder)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 2F-1 | 🟠 Publish website with docs + pricing (fix NXDOMAIN) | 15 | 1w | 1B-1, 1B-2 | paying-customer-readiness |
| 2F-2 | 🟠 Build billing UI in dashboard (customer self-service) | 12 | 1w | 2E-5 | paying-customer-readiness |
| 2F-3 | 🟡 Onboard first design partner: founder-led install, config, weekly sync | 15 | Ongoing | 1B-4 | paying-customer-readiness |
| 2F-4 | 🟡 Collect case study data: before/after token counts, dollar savings, UX feedback | 10 | Ongoing | 2F-3 | paying-customer-readiness |

### Phase 2 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Design partners active | ≥3 | Signed contracts |
| Stripe checkout | Working | End-to-end test purchase |
| Gemini compression | Live in Rust proxy | `live_zone_gemini.rs` merged |
| TTFT measured | Real ms values in telemetry | `ttfb_ms` ≠ 0 in streaming path |
| Coverage: Rust | Tracked in Codecov | Upload step in `rust.yml` |
| Coverage threshold | ≥70% enforced | `fail_under` in pyproject.toml |
| Component duplication | 0 duplicate shared components | MetricCard defined once |
| server.py size | <3,000 lines (from 7,903) | Line count post-extraction |
| WCAG AA compliance | >80% (from 62%) | Accessibility re-audit |

---

## Phase 3: Enterprise Readiness & Scale (Weeks 13-26)

**Goal:** SOC 2 Type I, SAML SSO, public self-serve, competitive feature parity.
**Go/No-Go Gate:** SOC 2 report issued, SAML working, public signup live, ≥$90K ARR pipeline.

### Workstream 3A: Enterprise Security & Compliance (Owner: Security Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 3A-1 | 🔴 SOC 2 Type I audit completion | 10 | 3-6 months | 2A-3 | competitive-analysis |
| 3A-2 | 🟠 SAML SSO implementation | 10 | 4w | None | competitive-analysis, paying-customer-readiness |
| 3A-3 | 🟠 Virtual API keys with per-team budgets | 8 | 3w | None | competitive-gap FG-10 |
| 3A-4 | 🟡 Pentest completion + remediation | 8 | 2w + remediation | 2A-4 | paying-customer-readiness |
| 3A-5 | 🟡 WebAuthn MFA (hardware key support) | 6 | 2w | None | paying-customer-readiness |

### Workstream 3B: Competitive Features (Owner: Product Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 3B-1 | 🟠 Verification / hallucination guard: `cutctx verify` command comparing compressed vs original output | 12 | 4w | None | competitive-gap FG-1, competitive-analysis |
| 3B-2 | 🟠 Read-side intelligence: 3-4 read modes (map, signatures, diff, auto) | 10 | 3w | None | competitive-gap FG-2 |
| 3B-3 | 🟠 Expand MCP tools to 20+ (file read modes, diff compression, agent handoff) | 10 | 3w | None | competitive-gap FG-4 |
| 3B-4 | 🟡 OpenTelemetry export: trace/span export for compression events | 8 | 2w | None | competitive-gap FG-15 |
| 3B-5 | 🟡 CI/CD integration: `cutctx compress --check` for drift gates | 8 | 2w | None | competitive-gap FG-7 |
| 3B-6 | 🟡 Windows install script (PowerShell) | 8 | 1w | None | competitive-gap FG-13 |
| 3B-7 | 🟡 Knowledge graph + contradiction detection (integrate Zep/Graphiti adapter) | 8 | 2w | None | agent-memory-analysis |
| 3B-8 | 🟢 Pinned core memory blocks + memory rewrite tool | 8 | 2w | None | agent-memory-analysis P1 |

### Workstream 3C: Scale & Self-Serve (Owner: Full Stack Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 3C-1 | 🟠 Public self-serve signup (Stripe checkout, automated onboarding) | 12 | 2w | 2E-5, 2F-1 | paying-customer-readiness |
| 3C-2 | 🟠 Dashboard SSE push (replace polling for real-time updates) | 8 | 2w | None | consolidated-roadmap #45 |
| 3C-3 | 🟡 Compression-aware guardrails (PII/malcontent detection in stream) | 8 | 4w | None | consolidated-roadmap #47 |
| 3C-4 | 🟡 Model routing × compression combined story (80-95% cost reduction) | 8 | 4w | None | consolidated-roadmap #48 |
| 3C-5 | 🟡 OTEL observability bridge for existing stacks | 6 | 2w | 3B-4 | consolidated-roadmap #49 |
| 3C-6 | 🟢 Pipeline extension system in Rust (WASM or trait-based dynamic dispatch) | 6 | 4w | None | consolidated-roadmap #41 |

### Workstream 3D: Database & Infrastructure (Owner: Infrastructure Lead)

| # | Item | RICE | Effort | Dependencies | Source |
|---|------|------|--------|--------------|--------|
| 3D-1 | 🟠 Add retention policy to audit and spend databases (configurable window + archival + VACUUM) | 8 | 2d | None | database-analysis P1 |
| 3D-2 | 🟡 Make Redis default for multi-worker CCR (vs opt-in) | 6 | 2w | None | database-analysis P3 |
| 3D-3 | 🟡 Add storage metrics (DB file sizes, query latency, connection count) to prometheus endpoint | 6 | 2d | None | database-analysis P2 |
| 3D-4 | 🟡 Add `VACUUM` scheduling for all mutable SQLite stores | 4 | 1d | None | database-analysis P2 |
| 3D-5 | 🟢 Replace JSON savings file with dedicated SQLite database | 4 | 2w | None | database-analysis P3 |

### Phase 3 Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| SOC 2 Type I | Report issued | Audit firm sign-off |
| SAML SSO | Working with 2+ IdPs | Okta/Azure AD integration test |
| MCP tools | ≥20 | Tool count in MCP server |
| Read modes | ≥4 | `cutctx read --mode=map\|signatures\|diff\|auto` |
| Verification guard | `cutctx verify` works | Compressed→original accuracy report |
| Public self-serve | Signup → payment → active | End-to-end funnel test |
| ARR pipeline | ≥$90K | 3-5 design partners at $18-42K/yr |
| Windows support | Install + basic proxy works | CI green on Windows runner |

---

## Workstream Ownership Matrix

| Workstream | Owner | Phase 1 | Phase 2 | Phase 3 |
|------------|-------|---------|---------|---------|
| 1A/2A/3A: Security & Compliance | Security Lead | 8 items | 4 items | 5 items |
| 1B/2F: Commercial & GTM | Founder | 4 items | 4 items | — |
| 1C/2B: Architecture & Backend | Architecture Lead | 5 items | 5 items | — |
| 2C: Performance | Performance Lead | — | 5 items | — |
| 2D: Testing & QA | QA Lead | — | 6 items | — |
| 1D/2E: Frontend & UX | Frontend Lead | 7 items | 6 items | — |
| 3B: Competitive Features | Product Lead | — | — | 8 items |
| 3C: Scale & Self-Serve | Full Stack Lead | — | — | 6 items |
| 3D: Database & Infra | Infrastructure Lead | — | — | 5 items |

---

## Dependency Map

```
Phase 1:
  1B-1 (domain) → 1B-2 (email) → 1D-5/6/7 (a11y quick wins can run in parallel)
  1A-1 (rotate key) → 1A-6 (CI scanning) [can parallel]
  1A-2 (MFA fix) → independent
  1C-1 (bare except) → 1C-2 (strict mode) [independent but related]
  1B-4 (legal) → 2F-3 (first partner) [Phase 2]

Phase 2:
  2B-1 (server.py split) → 2B-2 (Gemini compression) [new modules need clean structure]
  2C-1 (TTFT measurement) → 2C-4 (publish benchmarks) [need data before publishing]
  2D-1 (Rust coverage) → 2D-2 (thresholds) [tracking before enforcing]
  2E-5 (Stripe checkout) → 2F-2 (billing UI) [payment before UI]
  1B-4 (pilot contract) → 2F-3 (first partner) → 2F-4 (case studies)

Phase 3:
  2A-3 (SOC 2 engagement) → 3A-1 (SOC 2 audit) [6-month engagement]
  3A-2 (SAML SSO) → 3C-1 (public self-serve) [enterprise before self-serve]
  3B-1 (verification guard) → 3B-2 (read-side intelligence) [trust before features]
  2F-4 (case studies) → 3C-1 (public launch) [social proof before marketing]
```

---

## Risk Register — Top 5 Risks That Could Derail the Plan

### Risk 1: LeanCTX Ships Faster Than We Can Close Gaps
| Field | Value |
|-------|-------|
| **Probability** | HIGH (70%) |
| **Impact** | HIGH — LeanCTX is shipping daily with 81 MCP tools, 10 read modes, knowledge graph. They're 3.2K stars and growing. |
| **Mitigation** | Accelerate MCP tool expansion (3B-3) and read-side intelligence (3B-2) in Phase 2. Differentiate on CCR reversibility + multi-format compression — LeanCTX has neither. |
| **Owner** | Product Lead |

### Risk 2: Design Partners Churn Before Case Studies
| Field | Value |
|-------|-------|
| **Probability** | MEDIUM (40%) |
| **Impact** | HIGH — No case studies = no social proof = no self-serve conversion. |
| **Mitigation** | 14-day bounded pilot with weekly syncs. Collect data from day 1. Have backup partners identified. Founder-led support ensures white-glove experience. |
| **Owner** | Founder |

### Risk 3: server.py Decomposition Breaks Existing Functionality
| Field | Value |
|-------|-------|
| **Probability** | MEDIUM (30%) |
| **Impact** | HIGH — `server.py` is the core proxy. Any breakage = production incident for pilot partners. |
| **Mitigation** | Extract routes/middleware/stats first (read-only refactors). Keep app lifecycle in one file. Run full test suite after each extraction. Do NOT refactor compression or auth paths in Phase 2 — those need the 69 bare-except audit first. |
| **Owner** | Architecture Lead |

### Risk 4: SOC 2 Engagement Takes Longer Than Expected
| Field | Value |
|-------|-------|
| **Probability** | MEDIUM (50%) |
| **Impact** | MEDIUM — Delays enterprise sales but doesn't block design-partner pilot or self-serve. |
| **Mitigation** | Start engagement in Phase 2 (Week 5). Prepare pre-filled security questionnaire now. Build control evidence from existing security infrastructure (RBAC, MFA, Fernet secrets, anti-debug, integrity verification). |
| **Owner** | Security Lead |

### Risk 5: Domain/Email Setup Stalls on DNS Propagation
| Field | Value |
|-------|-------|
| **Probability** | LOW (15%) |
| **Impact** | HIGH — All 161+ doc links remain broken, security disclosures go nowhere. |
| **Mitigation** | Register domain immediately (1B-1). Use Cloudflare for fast propagation. Set up email forwarding before DNS fully propagates (MX records can be separate). Fallback: use `cutctx.io` if `.dev` is taken. |
| **Owner** | Founder |

---

## Competitive Positioning Summary

### Our Moats (Defend These)
1. **CCR Reversibility** — "Compress everything, lose nothing." No competitor matches this.
2. **5-Source Savings Attribution** — Know exactly where every dollar went.
3. **12 Specialized Compressors** — JSON + code + logs + diffs + images + prose.
4. **4-Language SDKs** — Python, TypeScript, Go, Java.
5. **Cross-Agent Memory** — Claude saves, Codex reads, Cursor searches.

### Close These Gaps (Phase 2-3)
1. SOC 2 Type II — Enterprise buyers require it
2. SAML SSO — Standard enterprise requirement
3. MCP tools (20+) — LeanCTX sets the bar at 81
4. Verification guard — #1 CISO objection
5. Windows support — Enterprise shops need it

### Deport/Deflect These Objections
- "Why no SOC 2?" → "Audit engagement started Q3 2026. Here's our pre-filled questionnaire."
- "Why no SAML?" → "OIDC works with all major IdPs. SAML on roadmap for Q3."
- "Why slower than RTK?" → "RTK compresses shell output only. We compress everything, reversibly."
- "Why no Windows?" → "Prioritizing Linux/macOS for pilot. Windows install script on Q3 roadmap."

---

## Appendix: Unresolved Items from Previous Audits

The following items from the July 8 audit and consolidated roadmap remain **NOT FIXED** as of July 10:

| # | Item | Severity | Status |
|---|------|----------|--------|
| 1 | OpenAI API key not rotated | 🔴 CRITICAL | ❌ 4 weeks overdue |
| 2 | OIDC fail-open auth | 🔴 CRITICAL | ❌ RBAC still a shim |
| 3 | Admin API key to stderr | 🟠 HIGH | ⚠️ Partial (moved from logger) |
| 4 | Rust coverage in Codecov | 🟡 MEDIUM | ❌ Not added |
| 5 | Coverage thresholds | 🟡 MEDIUM | ❌ No `fail_under` |
| 6 | `test_memory_system.py` split | 🟡 MEDIUM | ❌ Still 1,831 lines |
| 7 | Python-level load tests | 🟡 MEDIUM | ❌ Config-only assertions |
| 8 | First-run experience | 🟡 MEDIUM | ❌ Still 38+ commands |
| 9 | Error message guidance | 🟡 MEDIUM | ❌ No "what to do" |
| 10 | Skip-to-content link | 🟡 MEDIUM | ❌ Missing from App.jsx |
| 11 | Shimmer reduced-motion | 🟡 MEDIUM | ❌ Animation not disabled |
| 12 | Trend-bar focus ring | 🟡 MEDIUM | ❌ `outline: none` still present |
| 13 | Dashboard assets 404 | 🟡 MEDIUM | ❌ Production 404 on /assets/ |
| 14 | OG image hardcoded | 🟢 LOW | ❌ Still says "My App" |

**All 14 items are assigned to specific phases and workstreams above.**

---

*Document classification: Strategic roadmap. Scope: Full repository as of `main @ 418ae99a`. Generated by synthesizing 12 domain audit reports. Supersedes `audit/consolidated-roadmap.md`.*
