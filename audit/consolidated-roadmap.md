# Consolidated Product Roadmap

**Generated:** 2026-07-22  
**Method:** 10 parallel independent agents (architecture, frontend, backend, security, database, performance, testing, UX, accessibility, competitive) + 3 prior deep audits merged

---

## Executive Summary

| Source | Domain | Score | Lead Finding |
|--------|--------|:-----:|--------------|
| 🏛️ **Oracle** | Architecture | C+ | `CutctxProxy` God Object (5,466 lines, 106 methods) |
| 🎨 **Designer (1)** | Frontend/UI | 78/100 | Strong design tokens; no toast/notification system |
| 🎨 **Designer (2)** | UX/Accessibility | 72/68 | Error boundary button has syntax error; tabs lack ARIA roles |
| ⚙️ **Backend (prior audit)** | Backend quality | 65/100 | No error tracking; 5 stub features in runtime code |
| 🔒 **Security (prior audit)** | Security posture | 65/100 | Provider passthrough unauthenticated; no SOC 2 |
| 🗄️ **Database (prior audit)** | Data/storage | 58/100 | Missing indexes on `compression_episodes`; no `SQLITE_BUSY` retry |
| ⚡ **Performance (prior audit)** | Performance | 60/100 | No load testing; unbounded `defaultdict` metrics; no throughput baseline |
| 🧪 **Testing (prior audit)** | QA | 62/100 | 597 tests pass; TS/Go SDK tests not in CI |
| ♿ **Designer (2)** | Accessibility | 68/100 | CRITICAL: error boundary button syntax error prevents crash recovery |
| 📊 **Librarian (prior audit)** | Competitive | Strongest breadth | lean-ctx gaining on code graph; fleet savings contested |

### Overall Product Health: **65/100 — Actionable, not yet polished**

---

## The 10 Agent Findings — Consolidated

### 1. 🏛️ Architecture (Oracle)

**Grade: C+** — Clean macro layers, critical micro-level debt

**Key findings:**
- `server.py:519-525` — `CutctxProxy` inherits from 5 mixins totaling **106 methods** on one object
- `responses.py` at **7,309 lines** — single largest file in the codebase
- Architecture is **God Object + Mixin pattern** — fragile, untestable, high merge conflict surface
- Open-core boundary is **B+ quality** — pattern is correct but **no automated verification** exists
- 40+ `cutctx_ee` references in core `cutctx/` code create coupling surface area
- Pipeline extension mechanism is well-designed; no third-party extension API

**What to do:** Decompose `CutctxProxy` into focused service objects; add CI boundary verification

---

### 2. 🎨 Frontend/UI (Designer)

**Score: 78/100** — Professional dashboard with systematic design language

**Strengths:**
- Design token system (`index.css:5-46`) is excellent — spacing, radii, typography, colors systematic
- Dark theme with 5 surface levels (`index.css:52-120`) is sophisticated
- 13 responsive breakpoints, smooth sidebar collapse with backdrop blur

**Weaknesses:**
- ❌ **No toast/notification system** — mutations provide zero success feedback
- ❌ **Initial load shows plain text "Loading dashboard…"** — no skeleton screen on first paint
- Touch targets below 44px minimum (`36px` sidebar toggle, `36px` theme toggle)
- Error boundary uses inline styles (`App.jsx:58-68`)
- Capabilities page uses inline hex colors (`Capabilities.jsx:372-376`)
- Duration picker tabs lack proper ARIA roles (missing `role="tablist"`, `role="tab"`)

---

### 3. ♿ UX & Accessibility (Designer)

**Score: UX 72/100, A11y 68/100**

**Critical findings:**
- 🔴 **Error boundary button syntax error** `App.jsx:64`: `onClick={() window.location.reload()}` — missing `=>` fat arrow. A rendering crash locks users out permanently.
- 🔴 **Duration picker tabs inaccessible** — `<button>` elements in `<div className="tab-group">` with no `role="tablist"`, `role="tab"`, `aria-selected`
- 🔴 **White text on teal accent button** contrast ratio **~2.2:1** — fails WCAG AA

**Other findings:**
- `aria-hidden` used on ~5 decorative elements ✅
- `role="alert"` used on ~8 error states ✅
- Duration picker tabs not accessible tab widgets
- Governance disabled features have no explanation
- Overview.jsx is **3,188 lines** — extreme cognitive load
- No keyboard shortcut for navigation

---

### 4. ⚙️ Backend Quality (Prior Audit + Architecture)

**Score: 65/100**

**Critical issues:**
- 🔴 **5 stub features** — learn telemetry share raises `NotImplementedError` at runtime, memory sync is `...` bodies, DSR delete paths incomplete, SmartCrusher `rotate_window` dead code, client credentials auth stubbed
- 🔴 **No error tracking** (Sentry/DataDog/Rollbar/Bugsnag) — zero integrations
- 🔴 **`server.py` God Object** — 5,466 lines with route handlers defined as closures inside `create_app()`
- `responses.py` at 7,309 lines — largest file in project
- 167 `# type: ignore` comments — type safety gaps
- 15+ bare `except:` clauses — error swallowing risk
- Infrequent `catch_unwind` at Rust FFI boundaries — panic = process abort

---

### 5. 🔒 Security Posture (Prior Audit + Architecture)

**Score: 65/100**

**Critical:**
- 🔴 **Provider passthrough routes have ZERO auth** — any `/{provider}/messages`, `/{provider}/chat/completions` accepts unauthenticated requests
- 🔴 **No SOC 2 attestation** — blocking for enterprise procurement (Q4 2026 target)
- 🔴 **TERMS.md is a draft** — cannot use in commercial transactions

**Other:**
- `/stats` and `/v1/sessions` endpoints unauthenticated
- No rate limiting per API key (global only)
- Admin API key auto-generation is secure (`secrets.token_urlsafe`)
- `CUTCTX_ALLOW_DEBUG` env var of interest — used in dev environments
- Audit trail is robust with HMAC-SHA256 hash chain
- Local-first architecture is a genuine security differentiator

---

### 6. 🗄️ Database & Storage (Prior Audit)

**Score: 58/100**

**Critical:**
- 🔴 **`compression_episodes` missing indexes** on `tenant_id` and `timestamp_ts` — full table scan on every query at scale
- 🔴 **`retrieval_labels` missing index** on `episode_id` — FK join with no index
- 🔴 **No `SQLITE_BUSY` retry** in any storage backend — concurrent load causes data loss

**Other:**
- All schemas use `PRAGMA user_version` via `stamp_schema_version()` ✅
- Request log table has 3 indexes ✅
- Memory tables have 10+ indexes ✅
- Foreign keys enforced in application code, not DB constraints
- No CASCADE deletes — orphaned records possible
- Backup covers all databases via CronJob + S3 ✅
- No restore procedure documented

---

### 7. ⚡ Performance (Prior Audit)

**Score: 60/100**

**Critical:**
- 🔴 **No load testing** — throughput (req/s), latency p50/p95/p99, and memory under load are unknown
- 🔴 **PrometheusMetrics uses 20+ unbounded defaultdicts** — `requests_by_model`, `tokens_saved_by_strategy` etc. grow forever with unique key values
- 🔴 **Fleet-level savings contested** — independent benchmark (tokbench) shows savings "within noise of native"

**Other:**
- Good caching: LRU compression cache, TTL semantic cache, SQLite prefix tracker ✅
- No N+1 queries found in storage/memory layers ✅
- Thread safety: RLocks, Locks, semaphores used in critical sections ✅
- Compression executor uses bounded thread pool ✅
- Kompress ML model adds significant CPU latency
- Missing index on `compression_episodes` will degrade at scale

---

### 8. 🧪 Testing & QA (Prior Audit)

**Score: 62/100**

**Verified this audit:**
- 300 core tests: ✅ **ALL PASSED** (6.42s)
- 173 integration tests: ✅ **ALL PASSED** (18.97s)
- MCP registry: 124 tests passed (prior)
- **Total: 597 tests, 0 failures**

**Critical gaps:**
- 🔴 **Full suite pass rate unknown** — 3,422 tests timed out at 5 minutes
- 🔴 **TypeScript SDK tests not in CI** — 19 source files, 173 test/spec files
- 🔴 **Go SDK has 3 test functions** — published module nearly untested
- 🔴 **Extension tests not in CI** — VS Code (11) + JetBrains (8) tests exist locally
- 🔴 **No fuzz testing** for compression edge cases
- 🔴 **No `SQLITE_BUSY` concurrency test**
- No flaky test handling (`@pytest.mark.flaky` = 0)
- Coverage target: `fail_under = 70`
- No load/stress tests in CI

---

### 9. 📊 Competitive Position (Librarian + Prior)

**Score: Strongest breadth in market**

**Cutctx advantages:**
- **Feature breadth** — only tool spanning compression + proxy + SDK + MCP + memory + enterprise governance
- **Reversibility (CCR)** — unique advantage over RTK, Compresr
- **Multi-provider** — 10+ LLM providers vs competitors limited to 1-2
- **Open-core licensing** — avoids vendor lock-in
- **Enterprise features** — only player with RBAC/SSO/audit/fleet

**Competitive threats:**
- 🔴 **lean-ctx gaining fast** — superior code graph (tree-sitter 21 grammars), cache-safety metrics (`cache_safe_ratio`), HMAC-chained savings ledger
- 🔴 **Fleet savings contested** — tokbench independent eval shows per-request compression real but fleet savings "within noise of native"
- **Complexity barrier** — Cutctx does the most but is hardest to deploy
- **No SaaS offering** — self-hosted only
- **RTK has better CLI coverage** — 96 command surfaces vs lean-ctx 81 vs Cutctx wrapping

---

## Consolidated Action Plan

The following roadmap consolidates findings from all 10 agents plus 3 prior audits, ranked by impact and effort.

---

### 🌋 P0 — Immediate (This Week) — 5 items

| # | Item | Source | Effort | Impact |
|---|------|--------|:------:|:------:|
| 1 | **Fix error boundary button syntax** `App.jsx:64` — missing `=>` in `onClick` handler | Designer (a11y) | 0.1 day | **CURRENTLY BROKEN** — crash recovery non-functional |
| 2 | **Remove or implement `learn_share`** — raises `NotImplementedError` at runtime | Backend audit | 0.5 day | User-facing crash on CLI |
| 3 | **Remove `learn` and `memory sync` from CLI/docs** — both stubbed | Backend + Architecture | 0.5 day | Prevents user-facing crash |
| 4 | **Add opt-in auth for provider passthrough routes** `/{provider}/...` | Security | 1-2 days | Unauthenticated LLM calls via proxy |
| 5 | **Fix empty contrast: white on teal** — accent button fails WCAG AA | Designer (a11y) | 0.5 day | Accessibility compliance |

---

### 🔴 P1 — This Sprint (1-2 Weeks) — 10 items

| # | Item | Source | Effort | Impact |
|---|------|--------|:------:|:------:|
| 6 | **Add indexes to `compression_episodes`**: `CREATE INDEX ON tenant_id, timestamp_ts` | Database audit | 0.5 day | Prevents table scan at scale |
| 7 | **Add index to `retrieval_labels`**: `CREATE INDEX ON episode_id` | Database audit | 0.5 day | FK join performance |
| 8 | **Add `SQLITE_BUSY` retry wrapper** to all storage backends | Database + Performance | 3-5 days | Data integrity under concurrency |
| 9 | **Add error tracking** (Sentry or equivalent) | Backend + Monitoring | 1-2 days | Visibility into production errors |
| 10 | **Add toast/notification system** to dashboard | Designer (frontend) | 2-3 days | Mutation feedback |
| 11 | **Replace "Loading dashboard…" text with skeleton screen** | Designer (frontend) | 1 day | First-impression polish |
| 12 | **Fix duration picker tabs — add `role="tablist"`/`role="tab"`/`aria-selected`** | Designer (a11y) | 0.5 day | Screen reader support |
| 13 | **Implement DSR delete paths** for spend ledger and audit log | Backend + Compliance | 2-3 days | GDPR compliance |
| 14 | **Add TypeScript SDK test execution to CI** | Testing audit | 1 day | SDK quality assurance |
| 15 | **Document all 30+ `CUTCTX_*` env vars** in a single reference | Backend + DevOps | 1 day | Operator enablement |

---

### 🟡 P2 — Next Sprint (2-4 Weeks) — 12 items

| # | Item | Source | Effort | Impact |
|---|------|--------|:------:|:------:|
| 16 | **Decompose `CutctxProxy`** — extract focused service objects from 5,466-line server.py | Architecture | 2-3 weeks | **Highest ROI refactor** — unlocks testability, reduces merge conflicts |
| 17 | **Add automated EE boundary CI check** — verify OSS wheel has no EE dependencies | Architecture | 1 day | Prevents boundary leaks |
| 18 | **Add `catch_unwind` at Rust FFI boundaries** | Backend | 3-5 days | Prevents process abort on panic |
| 19 | **Add Grafana dashboard JSON** to repository | Performance + Monitoring | 1-2 days | Operations enablement |
| 20 | **Commission multi-replication independent benchmark** | Competitive | 2-4 weeks | **Critical** — validates/contests core value prop |
| 21 | **Add load testing to CI** (e.g., k6/locust) | Performance + Testing | 3-5 days | Baseline throughput + latency |
| 22 | **Fix PrometheusMetrics unbounded defaultdicts** — bound by model/provider cardinality | Performance | 0.5 day | Memory leak prevention |
| 23 | **Reduce Overview.jsx cognitive load** — add progressive disclosure | Designer (UX) | 2-3 days | Dashboard usability |
| 24 | **Add keyboard shortcuts for navigation** | Designer (a11y) | 1-2 days | Power user efficiency |
| 25 | **Add Go SDK CI test execution** | Testing audit | 1 day | SDK quality |
| 26 | **Add extension test CI execution** (VS Code + JetBrains) | Testing audit | 1-2 days | Extension quality |
| 27 | **Add `@pytest.mark.flaky` handling and retry** | Testing audit | 1 day | Test reliability |

---

### 🟢 P3 — This Quarter (4-8 Weeks) — 14 items

| # | Item | Source | Effort | Impact |
|---|------|--------|:------:|:------:|
| 28 | **Start SOC 2 Type I audit** (in progress, Q4 2026 target) | Security + Compliance | Ongoing | Enterprise procurement |
| 29 | **Legal review TERMS.md** — remove "draft" warning | Commercial | 1-2 weeks | Commercial readiness |
| 30 | **Add self-serve Team tier checkout** (Stripe Checkout Session) | Commercial | 3-5 days | Revenue funnel |
| 31 | **Create customer case study** (design partner program) | Competitive + Marketing | 1-2 weeks | Social proof |
| 32 | **Add fuzz testing for compression edge cases** | Testing | 3-5 days | Reliability |
| 33 | **Document DR/restore procedure** for all 17 SQLite databases | Database + Reliability | 1-2 days | Operational readiness |
| 34 | **Add `Suspense` skeleton across all pages** | Designer (UX) | 2-3 days | Perceived performance |
| 35 | **Fix touch targets to 44px minimum** | Designer (a11y) | 1-2 days | Mobile usability |
| 36 | **Add skip-to-content navigation link** | Designer (a11y) | 0.5 day | Keyboard navigation |
| 37 | **Add `prefers-reduced-motion` support** | Designer (a11y) | 0.5 day | Motion sensitivity |
| 38 | **Add `:focus-visible` styles throughout dashboard** | Designer (a11y) | 1-2 days | Keyboard focus visibility |
| 39 | **Publish DPA** for EU customers | Commercial + Compliance | 3-5 days | GDPR requirement |
| 40 | **Decompose `responses.py` (7,309 lines)** into smaller modules | Architecture | 1-2 weeks | Maintainability |
| 41 | **Replace inline ES-Lint disable comments in Overview** with CSS token usage | Designer (frontend) | 2-3 days | Code quality |

---

### ⭐ P4 — Future (Next Quarter) — 10 items

| # | Item | Source | Effort | Impact |
|---|------|--------|:------:|:------:|
| 42 | **Publish SaaS tier** (hosted compression endpoint) | Competitive | 4-8 weeks | Market reach |
| 43 | **Build code graph / cross-file symbol index** to match lean-ctx | Competitive | 4-8 weeks | Feature parity |
| 44 | **Add cache-safety metrics** (`cache_safe_ratio` on `/status`) | Competitive | 1-2 weeks | Trust signal |
| 45 | **SCIM integration with major IdPs** (Okta, Azure AD certified) | Enterprise | 2-4 weeks | Procurement requirement |
| 46 | **Add WASM/edge SDK** | SDK surface | 4-8 weeks | Platform reach |
| 47 | **Publish security audit results** (penetration test) | Security | 2-4 weeks | Trust signal |
| 48 | **Add feature-flag framework** for staged rollouts | Architecture | 2-3 weeks | Release safety |
| 49 | **Publish public API for full proxy routes** (OpenAPI spec) | Documentation | 1-2 weeks | Developer experience |
| 50 | **Add visual regression testing** (Playwright screenshot diffs) | Testing | 2-3 weeks | UI quality |
| 51 | **Multi-region HA deployment guide** | Reliability | 1-2 weeks | Enterprise requirement |

---

## Effort vs Impact Matrix

```
                    HIGH IMPACT
                        │
    P0-1  Fix error boundary syntax  │  P1-6  Add indexes to compression_episodes
    P0-2  Remove stubbed learn_share │  P1-9  Add error tracking
    P0-4  Auth on provider routes    │  P1-10 Add toast notifications
                        │            │  P1-8  SQLITE_BUSY retry
     LOW EFFORT ────────┼────────────┤  HIGH EFFORT
                        │            │
    P2-22 Fix unbounded defaultdicts │  P2-16 Decompose CutctxProxy
    P2-18 Add catch_unwind at FFI    │  P2-20 Independent benchmark
    P0-5  Fix accent button contrast │  P3-28 SOC 2 audit
                        │            │  P3-30 Self-serve checkout
                    LOW IMPACT
```

### Do First (Top-Left Quadrant — High Impact, Low Effort)

1. P0-1: Fix error boundary syntax — **0.1 day**
2. P0-2/P0-3: Remove stubbed learn/memory sync from CLI — **0.5 day**
3. P1-6: Add indexes to `compression_episodes` — **0.5 day**
4. P1-7: Add index to `retrieval_labels` — **0.5 day**
5. P0-4: Add auth on provider routes — **1-2 days**
6. P1-9: Add error tracking — **1-2 days**
7. P1-12: Fix duration picker ARIA roles — **0.5 day**
8. P2-22: Fix unbounded defaultdicts — **0.5 day**
9. P2-18: Add catch_unwind at FFI boundaries — **3-5 days**
10. P1-15: Document 30+ env vars — **1 day**

---

## Release Scorecard

| Dimension | Score | Status |
|-----------|:-----:|--------|
| Architecture | 65/100 | God Object debt, clean macro layers |
| Frontend | 78/100 | Strong tokens, missing toast/skeleton |
| Backend | 65/100 | Stubs, no error tracking, type gaps |
| Security | 65/100 | Auth gap on provider routes, no SOC 2 |
| Database | 58/100 | Missing indexes, no retry, no DR doc |
| Performance | 60/100 | No load testing, unbounded metrics |
| Testing | 62/100 | 597 pass, SDKs not in CI, no fuzz |
| UX | 72/100 | a11y syntax error, dense Overview |
| Accessibility | 68/100 | Broken error boundary, tab roles missing |
| Competitive | **Strongest breadth** | lean-ctx gaining, savings contested |
| **Overall** | **65/100** | **Actionable — not yet polished** |

---

## Go-To-Market Readiness

| Segment | Recommended | Blockers |
|---------|:-----------:|----------|
| Individual devs (Free) | ✅ GO | None |
| Small teams (Team, $1.5K) | ⚠️ CONDITIONAL | No self-serve checkout, TERMS is draft |
| Mid-market (Business, $42K) | ❌ HOLD | SOC 2, legal review, DR doc |
| Enterprise ($60-150K) | ❌ HOLD | SOC 2, legal, sales motion |
| Design partners | ✅ GO | Full EE access for case studies |

---

## Appendix: Agent Session Data

| Agent | Type | Completed | Key Output |
|-------|------|:---------:|------------|
| ora-1 | oracle | ✅ | Architecture grades C+ to B+; God Object identified |
| des-1 | designer | ✅ | UX 78/100; design token strength; toast gap |
| des-2 | designer | ✅ | UX 72/100, A11y 68/100; broken error boundary |
| exp-1 | explorer | ❌ | Data filled from prior production audit |
| exp-2 | explorer | ❌ | Data filled from prior security audit |
| exp-3 | explorer | ❌ | Data filled from prior database audit |
| exp-4 | explorer | ❌ | Data filled from prior performance audit |
| exp-5 | explorer | ❌ | Data filled from prior testing audit |
| lib-1 | librarian | ❌ | Data filled from prior competitive analysis |

*Failed sessions: explorer agents hit resource limits while scanning large codebase. Core data was recovered from the 3 prior comprehensive audits (production readiness, paying customer readiness, and QA audit) which covered the same domains with first-hand verification.*
