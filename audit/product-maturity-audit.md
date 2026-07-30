# Product Maturity Audit — Cutctx v0.31.0

**Date:** 2026-07-29
**Method:** Fresh exploration — live DNS probes, source code inspection, CLI execution, CI/CD analysis, benchmark review, dependency audit. No prior audit files consulted.
**Live proxy:** `GET /livez` → 200 · `GET /readyz` → 200
**Working tree:** Clean (1 modified file — this audit)

---

## Executive Summary

Cutctx is a context-compression proxy for AI agent traffic. It sits between agents (Claude Code, Codex, Cursor) and LLM providers, compressing tool outputs, logs, files, and conversation history before they reach the model.

**Maturity score: 70/100** — The engineering core is functional and well-tested. The product is viable for individual developers and small teams today. It is NOT ready for self-serve commercial launch or enterprise procurement without addressing critical gaps in billing, security, monitoring, and legal.

### Quick verdict by channel

| Channel | Verdict | Key blocker |
|---------|---------|-------------|
| Individual developer (OSS) | ✅ **GO** | `pip install` works, 38 commands, 46 doc pages |
| Design-partner pilot (1–5 accounts) | ✅ **CONDITIONAL GO** | Needs domain fix + invoice-based billing |
| Public self-serve (Stripe checkout) | ❌ **NO-GO** | No working checkout path; Terms say "draft template" |
| Enterprise ($60–150K/yr) | ❌ **NO-GO** | No SOC 2, no pentest, Terms draft, SLA basic |

---

## 1. Feature Completeness

### What ships

| Feature | Files | Status | Notes |
|---------|-------|--------|-------|
| Content-aware compression | `cutctx/transforms/content_router.py` (3,968 lines) | ✅ Shipped | SmartCrusher, CodeCompressor, LogCompressor, DiffCompressor, Kompress (ML), SearchCompressor |
| Reversible compression (CCR) | `cutctx/ccr/` | ✅ Shipped | TTL-controlled, retrieval via MCP tool |
| Cross-provider proxy | `cutctx/proxy/server.py` (5,731 lines) | ✅ Shipped | Anthropic, OpenAI, Google, Bedrock, Vertex |
| Cross-agent memory | `cutctx/memory/` | ✅ Shipped | SQLite, USearch, Qdrant, Neo4j backends |
| Orchestration engine | `cutctx/orchestration/` | ✅ Shipped | Deterministic routing, fallback chains, budget controls |
| Dashboard (11 pages) | `dashboard/src/` | ✅ Shipped | Lazy-loaded React 19 + Vite 8, production build present |
| MCP server | `cutctx/mcp_server.py` | ✅ Shipped | compress, retrieve, status tools |
| CLI (38 commands) | `cutctx/cli/` | ✅ Shipped | Grouped into Getting Started, Daily Use, Optimize, Administration |
| Agent integrations | `plugins/` | ✅ Shipped | Claude Code, Codex, Cursor, OpenClaw, Hermes |
| SDKs | `sdk/` | ✅ Shipped | TypeScript (npm), Python (PyPI), Go |
| Rate limiting | `cutctx/proxy/rate_limiter.py` | ✅ Shipped | Token bucket, configurable per-minute |
| LLM Firewall | `cutctx/proxy/firewall/` | ✅ Shipped | 24 regex patterns, off by default |
| CacheAligner | `cutctx/proxy/cache_aligner.py` | ✅ Shipped | KV cache optimization |
| Image/audio compression | `cutctx/transforms/` | ✅ Shipped | Inline multimodal |

### What's missing or stubbed

| Feature | Status | Evidence |
|---------|--------|----------|
| **Billing checkout** | ❌ Broken | `get_checkout_url()` returns a redirect to `cutctx.com/pricing/?product=cutctx...` — no actual Stripe Checkout session creation. Tests confirm it's a URL redirect, not a payment flow. |
| **Learn telemetry sharing** | ❌ Stubbed | `cutctx/learn/aggregate.py:104` — `raise NotImplementedError("Learn telemetry sharing is not implemented")` |
| **Terms of Service** | ⚠️ Draft | `TERMS.md` header: *"These terms are a draft template. They must be reviewed by qualified legal counsel before publication or use in any commercial transaction."* |
| **Error tracking** | ⚠️ Optional extra | `cutctx/observability/error_tracking.py` exists, requires `pip install cutctx-ai[sentry]` + `CUTCTX_SENTRY_DSN`. Not enabled by default. |
| **Alert delivery** | ❌ Missing | No built-in alerting. Abuse events logged but not delivered anywhere. |

### File size hotspots (maintainability concern)

| File | Lines | What it does |
|------|-------|-------------|
| `cutctx/proxy/handlers/openai/responses.py` | 7,347 | OpenAI Responses API handler |
| `cutctx/proxy/server.py` | 5,731 | Proxy runtime: routes, middleware, auth, stats, replay, lifecycle |
| `cutctx/cli/wrap.py` | 5,530 | CLI tool wrapping logic |
| `cutctx/proxy/handlers/anthropic.py` | 4,303 | Anthropic API handler |
| `cutctx/transforms/content_router.py` | 3,968 | Content type detection and routing |
| `cutctx/proxy/helpers.py` | 3,476 | Shared utilities |
| `cutctx/proxy/savings_tracker.py` | 3,409 | Savings tracking and reporting |

**Risk:** Several files exceed 3,000 lines. `server.py` at 5,731 lines handles route registration, middleware, stats, session replay, CCR retrieval, dashboard serving, compression orchestration, entitlement checks, license validation, and CLI parsing — this is a single-responsibility violation that makes testing and reasoning difficult.

---

## 2. Security

### Auth

| Component | Status | Detail |
|-----------|--------|--------|
| Admin key auth | ✅ Implemented | `_require_local_admin_auth` middleware checks `X-Cutctx-Admin-Key` header, Authorization Bearer token, or SSO token |
| Admin auth failure limiting | ✅ Implemented | `admin_auth_failure_limiter` at line 2387 — rate-limits failed admin auth attempts |
| Client auth | ✅ Implemented | `_require_agent_client_auth` and `_require_hosted_compression_auth` for API client access |
| RBAC | ✅ Implemented | `_runtime_require_rbac_permission` — 4 roles, 25+ permissions, ~40 admin routes enforce |
| Dashboard admin key storage | ⚠️ Cookie + localStorage | Key stored in cookie, localStorage, and sessionStorage with `SameSite=Lax`. URL param passthrough on login (`window.location.search`). |

### CORS

CORS is config-driven and safety-gated:
- `*` origin → `allow_credentials = False` (prevents credentialed wildcard CORS)
- Non-wildcard origins → credentials allowed
- Methods and headers restricted when origins are specific

This is a **correct implementation**.

### SQL injection risk

No f-string SQL injection found in `cutctx_ee/` audit/billing modules. Parameterized queries (`?` placeholders) used consistently. However, `cutctx_ee/audit/__init__.py` builds dynamic WHERE clauses via `" AND ".join(clauses)` — the clause values are pre-sanitized filter keys, not raw user input, but this pattern should be reviewed under the assumption that filter keys could be contaminated.

### Rate limiting

- Global token bucket rate limiter (requests/min + tokens/min)
- Admin auth failure limiter
- Rate limit metrics recorded
- Rate limiting is **not** applied to individual endpoints differently (no per-route throttling)

### Encryption

| Layer | Algorithm | Detail |
|-------|-----------|--------|
| Transport | TLS 1.3 | Configurable via ingress/proxy. Proxy can terminate TLS. |
| At rest (state crypto) | Fernet (AES-128-CBC + HMAC-SHA256) | `cutctx/security/state_crypto.py` |
| Audit log integrity | HMAC-SHA256 | `cutctx_ee/audit/store.py` — tamper-evident hash chain |

### Security observations

| Item | Severity | Detail |
|------|----------|--------|
| PGP key for disclosures | ❌ Missing | SECURITY.md asks for email reports — no key for encrypted communication |
| Bug bounty | ❌ Not offered | Private disclosure only |
| Dependency scanning in CI | ⚠️ Not explicit | No `trivy`/`grype`/`snyk` step visible in CI workflows |
| SECURITY.md | ✅ Published | Supported versions table, reporting instructions, expected response times |

---

## 3. Performance

### Benchmarks (from `benchmark_results.md`, seed 42, 2026-07-18)

| Dataset | N | ContentRouter | SmartCrusher | Kompress |
|---------|---|--------------|--------------|----------|
| ToolOutputSamples | 8 | 71.5% kept | 79.1% kept | 78.8% kept |
| CodeSamples | 2 | 87.4% kept | 100% (pass) | 84.8% kept |
| RAGSamples | 6 | 54.7% kept (query-aware) | 100% (pass) | 94.9% kept |
| MixedAgentTraces | 2 | 82.6% kept | 82.6% kept | 85.6% kept |

- **No expansion** — every compressor guarantees output ≤ input (`expansion_guard`)
- **Duration**: 8.7 seconds for full benchmark suite
- **Seed 42**, results are reproducible

### Memory

- SQLite stores have comprehensive indexes (verified in `cutctx/memory/adapters/sqlite.py` — 10 indexes on `memories` table, 5 on `vec_metadata`, 6 on entities/relationships)
- USearch backend uses f16 quantization with zero-copy memory-mapped loading
- Vector metadata table uses `SELECT *` without pagination — OOM risk at scale

### Concurrency

- Async throughout proxy hot path
- Retry logic with jitter + exponential backoff across all provider handlers
- Circuit breakers (per-provider + pipeline)
- Connection pooling not used for SQLite (each call opens/closes)

### Caching

- `@lru_cache` on tokenizers, provider config lookups (4 sites)
- CacheAligner for KV cache optimization
- Stats endpoint has TTL-based caching with `_get_cached_payload`
- No caching on content type classification or schema validation (recomputed per-request)

---

## 4. Deployment & CI/CD

### CI/CD (27 workflows)

| Workflow | Purpose | Status |
|----------|---------|--------|
| `ci.yml` | Primary — parallel build, lint, test (4 shards), prefetch model | ✅ Has path filters for code/helm/k8s/e2e |
| `rust.yml` | Rust workspace | ✅ Present |
| `docker.yml` | Container build | ✅ Present |
| `release.yml` | Release pipeline | ✅ Present |
| `publish.yml` | PyPI/npm publish | ✅ Present |
| `sign-artifacts.yml` | Artifact signing | ✅ Present |
| `compile-ee.yml` | EE wheel build | ✅ Present |
| `pr-health.yml` | PR health checks | ✅ Present |
| `docs.yml` | Documentation build | ✅ Present |
| `benchmark.yml` | Benchmark runs | ✅ Present |

### Infrastructure-as-code

| Component | Status | Detail |
|-----------|--------|--------|
| Dockerfile | ✅ Multi-stage | Distroless target, HEALTHCHECK, non-root user |
| docker-compose.yml | ✅ Present | Proxy + Qdrant + Neo4j, named volumes |
| K8s deployment | ✅ Present | Rolling update, resource requests (250m CPU, 256Mi), service account, security context (non-root, seccomp) |
| K8s HPA | ❌ Missing | No HorizontalPodAutoscaler |
| K8s PDB | ❌ Missing | No PodDisruptionBudget |
| Helm chart | ✅ Present | Chart.yaml, templates, values.yaml |
| Backup CronJob | ✅ Present | Daily S3 backup of 9+ SQLite stores |

### Environment vars

- `.env.example` documents required variables (NEO4J_URI, CUTCTX_PROXY_HOST, API keys)
- `.env.local` loaded automatically for local dev
- `docker-compose.yml` validates required vars at startup: `CUTCTX_ADMIN_API_KEY:?set`, `CUTCTX_PROXY_API_KEY:?set`, `CUTCTX_CLIENT_API_KEY:?set`

---

## 5. Testing

### Test inventory

| Metric | Value |
|--------|-------|
| Python test files | 698 files |
| Rust tests | Full workspace (`cargo test`) |
| Dashboard | 11 unit tests + Playwright e2e |
| TypeScript SDK | 306 tests (33 skipped) |
| Go SDK | 19/19 tests |

### Coverage

- Target: `fail_under = 70` in `pyproject.toml`
- Source coverage: `cutctx/` package only (excludes EE, tests, cli.py)
- Coverage NOT enforced in CI — `fail_under` is configured but no CI step gates on it

### Test gaps

| Area | Coverage | Notes |
|------|----------|-------|
| Core compression | ✅ Good | Multiple transform-specific test files |
| Proxy routes | ✅ Good | Extensive route tests |
| Security (auth, RBAC) | ⚠️ Moderate | `test_entitlements.py`, `test_rbac.py`, `test_sso.py`, `test_scim.py` exist |
| Billing pipeline | ⚠️ Moderate | `test_stripe_direct_billing.py` tests URL generation, not end-to-end checkout |
| EE modules | ⚠️ Partial | Test files exist for audit, entitlements, orgs, license, RBAC, SSO, SCIM |
| Load/stress tests | ❌ Missing | No performance regression suite |
| Fuzz testing | ❌ Not in CI | `fuzz/` directory exists but not wired into pipeline |
| Flaky tests | ❌ Not tracked | No explicit flaky test management |

### CI test execution

- 4 parallel `pytest-split` shards
- Offline mode (`HF_HUB_OFFLINE`) — no external model downloads during tests
- CPU-only torch (no CUDA)
- Single Python version (3.12) in PR CI; multi-version planned for main

---

## 6. Monitoring & Observability

### Logging

| Aspect | Detail |
|--------|--------|
| Framework | Python stdlib `logging`, with custom JSON serializer |
| Default format | Plain text (JSON available via env var) |
| Log levels | Configurable via `CUTCTX_LOG_LEVEL` |
| Secret redaction | No dedicated PII/secret redaction in log formatter |

### Error tracking

| Aspect | Detail |
|--------|--------|
| Implementation | `cutctx/observability/error_tracking.py` — wraps `sentry-sdk` |
| Activation | Requires `CUTCTX_SENTRY_DSN` env var + `pip install cutctx-ai[sentry]` |
| Default | **Off** — no DSN configured, no-op by default |
| Privacy | Request bodies and local variables never transmitted by design |
| Tested | `tests/test_error_tracking.py` verifies no-op behavior when absent |
| **Impact** | Unhandled exceptions in default installations are silently lost — captured only in local logs |

### Health checks

| Endpoint | Checks | Status |
|----------|--------|--------|
| `/livez` | Proxy process alive | ✅ 200 |
| `/readyz` | Dependencies ready | ✅ 200 |
| `/health` | Detailed health (version, uptime, upstream, datastores, rate limiter) | ✅ 200 |
| `/_health` | Full payload with config | ✅ Present |

### Metrics

- Prometheus `/metrics` endpoint behind admin auth (config trap for scrapers — documented)
- OTel metrics and tracing available as extras (`opentelemetry-api`, `opentelemetry-sdk`)
- Langfuse tracing available
- Rate limiter metrics (requests rate-limited per provider/model)
- Request outcome metrics (tokens, cost, latency)

### Alerting

- **No alert delivery mechanism.** `cutctx_ee/abuse.py` generates alert events but has no delivery target (no Slack, PagerDuty, email integration)
- **No uptime monitoring** — no external health check
- **No status page** — customers have no way to check service health

---

## 7. Commercial Surface

### Pricing

Four tiers well-defined in `artifacts/pricing-sheet.md` and published on `cutctx.com/pricing/`:

| Tier | Annual | Annual Price |
|------|--------|-------------|
| Builder | $0 | Free |
| Team | $18,000 | $1,500/mo |
| Business | $42,000 | $3,500/mo |
| Enterprise | Custom | $60K–$150K+ |

Add-ons available: onboarding ($5K), deployment hardening ($3K), premium SLA ($10K/yr), security review support ($7.5K).

### Billing pipeline

| Component | Status | Detail |
|-----------|--------|--------|
| Stripe webhook handler | ✅ Present | `cutctx_ee/billing/stripe_webhook.py` — handles checkout.session.completed, subscription updates |
| Offline licensing | ✅ Present | Ed25519 signed licenses with CRL revocation |
| License DB | ✅ Present | SQLite-backed, seat tracking, heartbeat APIs |
| Checkout URL | ⚠️ Redirect only | `get_checkout_url()` returns `https://cutctx.com/pricing/?product=cutctx&plan=X&billing=Y&email=Z` — a website URL, not a Stripe Checkout session |
| Direct Stripe Checkout | ❌ Missing | No `stripe.checkout.Session.create()` call in the codebase |
| Dashboard billing UI | ❌ Missing | No billing management page |

**Impact:** A customer clicking "buy" is redirected to the marketing site's pricing page, not a payment flow. The Stripe webhook can process events but never fires because no checkout sessions are created. Manual invoicing is the only real payment path.

### Legal & Compliance

| Document | Status | Notes |
|----------|--------|-------|
| Terms of Service | ⚠️ Draft | Self-declared "draft template — must be reviewed by legal counsel" |
| Privacy Policy | ✅ Published | Clear local-first architecture explanation, data flow diagram |
| SLA | ✅ Published | Tiered support response times, severity definitions |
| Security Policy | ✅ Published | Supported versions, disclosure process |
| Licensing (open-core) | ✅ Published | Apache 2.0 + commercial boundary in `LICENSING.md` |
| SOC 2 | ❌ Not started | No auditor engaged |
| Penetration test | ❌ Not done | No report available |

### Domain & Website

| Domain | Status | Detail |
|--------|--------|--------|
| `cutctx.com` | ✅ **Live** | Cloudflare, serves marketing site, `/pricing` works |
| `cutctx.dev` | ❌ **NXDOMAIN** | Used in README badges, docs links, email addresses |
| `cutctx.io` | ❌ **NXDOMAIN** | Referenced in some code comments |
| `@cutctx.com` emails | ⚠️ Likely works | Domain resolves; email delivery not tested |

**Note:** `cutctx.com` resolves now — this is a change from earlier this month when it was NXDOMAIN. However, `cutctx.dev` (used in README badges and docs links) is still dead.

---

## 8. Enterprise Readiness

| Capability | Status | Detail |
|------------|--------|--------|
| OIDC SSO | ✅ Works | Implemented, tested |
| RBAC | ✅ Works | 4 roles, 25+ permissions, 40+ admin routes enforce |
| Audit logging | ✅ Works | HMAC-SHA256 hash chain, 8+ event types, exportable |
| Retention controls | ✅ Implemented | Configurable TTL per data type |
| Air-gap deployment | ✅ Supported | Offline licensing, pre-staged models |
| Multi-tenant (org/project) | ✅ Works | Hierarchical tenancy |
| SAML SSO | ⚠️ Partial | OIDC works; SAML-only IdPs unsupported |
| SCIM provisioning | ⚠️ Partial | APIs exist but not fully validated |
| Fleet management | ⚠️ Partial | APIs exist but multi-instance not validated |
| **SOC 2** | ❌ Not engaged | 7.5-month timeline if started now |
| **Penetration test** | ❌ Not available | 2-4 weeks if engaged |
| **Multi-key admin** | ❌ Single key | 1-2 weeks engineering |
| **MFA mandate** | ⚠️ Enrollment-gated | Not mandatory |
| **DR runbook** | ❌ Missing | Backup exists; restore untested |
| **Uptime SLA** | ❌ Support SLA only | No availability commitment |

---

## 9. Competitive Positioning

### Differentiation matrix

| Capability | Cutctx | RTK | LeanCTX | Helicone | Portkey |
|------------|--------|-----|---------|----------|---------|
| Reversible compression (CCR) | ✅ **Unique** | ❌ | ❌ | ❌ | ❌ |
| Multi-format pipeline (7+ compressors) | ✅ **Unique** | ❌ Shell | ⚠️ Some | ❌ | ❌ |
| Savings attribution (5 sources) | ✅ **Unique** | ❌ | ❌ | ❌ | ❌ |
| Cross-agent memory | ✅ | ❌ | ❌ | ❌ | ❌ |
| Cross-provider cache alignment | ✅ | ❌ | ❌ | ❌ | ❌ |
| Local-first deployment | ✅ | ✅ | ✅ | ❌ Hosted | ❌ Hosted |
| Open-core | ✅ Apache 2.0 | ✅ | ✅ | ⚠️ Limited | ⚠️ Limited |
| Dashboard | ✅ 11 pages | ❌ | ❌ | ✅ | ✅ |

### Moat assessment

Cutctx's defensible advantages:
1. **CCR reversibility** — no competitor allows the LLM to retrieve compressed originals on demand
2. **Multi-format pipeline** — 7+ content-type-specific compressors vs single-model or shell-only approaches
3. **Cross-agent memory** — memory persists across Claude Code, Codex, Cursor sessions
4. **Cross-provider cache alignment** — works across Anthropic, OpenAI, Google without reconfiguration

**Threat:** If Helicone or Portkey add native compression, Cutctx's price advantage narrows. What remains is compression depth + local-first governance.

---

## 10. Developer Experience

### What works ✅

- `pip install cutctx-ai` — single command
- `cutctx setup` — auto-detects agents (Claude, Codex, Cursor, Gemini, Aider, Copilot), auto-registers MCP
- `cutctx proxy` — starts the proxy with sensible defaults
- `cutctx config doctor` — validates configuration
- 38 commands organized into 4 journey groups (Getting Started, Daily Use, Optimize, Administration)
- 46 documentation pages in `docs/content/docs/`
- SDKs in Python, TypeScript, Go
- MCP server auto-install
- Docker, docker-compose, K8s, Helm deployment paths

### What hurts ❌

| Issue | Detail |
|-------|--------|
| `cutctx.dev` NXDOMAIN | README badges link to `docs.cutctx.dev` — every docs badge is broken for users who click through |
| No instant demo | `cutctx proxy` starts a server but gives no feedback that compression is working. No `cutctx compress "text"` command. |
| 38 commands, no umbrella | `rbac`, `orgs`, `audit`, `sso-test`, `policies` are separate top-level commands. No `cutctx admin` grouping. |
| Terms say "draft" | Any commercial buyer reading TERMS.md sees "must be reviewed by qualified legal counsel" — kills trust |
| Proxy starts with no output | `cutctx proxy` prints `info: cutctx proxy running on 127.0.0.1:8787` and goes silent. No dashboard URL, no "open http://localhost:8787" tip. |

---

## 11. Accessibility (Dashboard)

| Criterion | Status | Detail |
|-----------|--------|--------|
| Semantic HTML | ✅ Good | `main`, `nav`, `aside`, `section`, `article`, `button` used correctly |
| Skip-to-content link | ✅ Present | `#main-content` with `:focus-visible` styling |
| Heading hierarchy | ⚠️ Issue | Sidebar brand renders `<h1>` alongside page title `<h1>` |
| ARIA labels | ✅ 60+ instances | Navigation, form inputs, icons, tab interfaces |
| `prefers-reduced-motion` | ✅ Comprehensive | All transitions and skeleton animations disabled |
| Color contrast | ✅ Pass | Dark and light themes both meet AA standards |
| Keyboard navigation | ✅ `:focus-visible` rings | Consistent focus indicators |
| Form labeling | ✅ `<label>` / `htmlFor` pairs | Auth form, playground, governance inputs all properly labeled |
| `aria-expanded` on toggle | ❌ Missing | Sidebar toggle doesn't announce open/closed state |
| `scope="col"` on table headers | ❌ Missing | Data tables lack scope attributes |
| Accessibility testing | ❌ Not in CI | No axe-core or pa11y integration |

---

## Maturity Score: 70/100

### Score breakdown

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Feature Completeness | 75/100 | Core engine shipped; billing path broken, learn telemetry stubbed |
| Security | 76/100 | Auth solid, CORS correct, encryption implemented. No PGP key, no pentest, no bug bounty. |
| Performance | 82/100 | Well-benchmarked, no expansion, good index coverage. Vector pagination missing. |
| Deployment & CI/CD | 78/100 | 27 workflows, K8s + Helm + Docker, backup CronJob. No HPA/PDB, no container scanning in CI. |
| Testing | 72/100 | 698 test files, but coverage not enforced in CI, no load tests, no fuzz pipeline. |
| Monitoring | 55/100 | Health checks good. Error tracking is opt-in extra (off by default). No alerting, no log aggregation, no uptime monitoring. |
| Commercial Surface | 40/100 | Pricing defined, Terms are draft, billing path broken, no SOC 2/pentest, domain split (com live, dev dead). |
| Developer Experience | 75/100 | Good CLI setup flow and docs. Dead docs badge link, no instant demo, Terms say "draft". |
| Enterprise Readiness | 42/100 | RBAC/SSO/audit work. SAML partial, no SOC 2, no pentest, no DR, no uptime SLA. |
| Competitive Positioning | 82/100 | Unique combination of CCR + multi-format + cross-agent memory + local-first. Defensible moat. |
| **Overall** | **70/100** | |

---

## Prioritized Action Plan

### P0 — Must fix (this week)

| # | Item | Area | Reason |
|---|------|------|--------|
| 1 | Fix `cutctx.dev` DNS — register or redirect to `cutctx.com` | DX/Marketing | Every README badge and docs link pointing at cutctx.dev is broken |
| 2 | Replace Terms draft with legally-reviewed ToS | Legal | Current header explicitly says "draft template — must be reviewed by counsel" |
| 3 | Wire a real Stripe Checkout session — `stripe.checkout.Session.create()` | Billing | Customers cannot currently pay. Webhook handler exists but never fires. |
| 4 | Enable error tracking by default or document required setup prominently | Monitoring | Silent failures in production — no exception visibility without sentry extra + DSN |

### P1 — Should fix (next sprint)

| # | Item | Area | Reason |
|---|------|------|--------|
| 5 | Add `cutctx compress "text"` one-shot demo command | DX | Users get zero feedback that compression works after `pip install` |
| 6 | Add HPA + PDB to K8s manifests | Deployment | Single replica with no disruption budget. RollingUpdate allows zero-downtime deploys but lacks scale. |
| 7 | Add container vulnerability scanning to CI | Security | No `trivy`/`grype` in pipeline |
| 8 | Enforce coverage threshold in CI | Testing | `fail_under = 70` configured but never checked |
| 9 | Add pagination to vector metadata queries | Performance | `SELECT *` without LIMIT — OOM risk on large datasets |
| 10 | Add uptime monitoring + status page | Monitoring | Customers have no way to check service health |
| 11 | Reorder quickstart to lead with proxy (zero-code) path | DX | SDK-first ordering buries the fastest path to value |

### P2 — Should fix (next month)

| # | Item | Area | Reason |
|---|------|------|--------|
| 12 | Extract `server.py` — move route handlers to `proxy/routes/` | Architecture | 5,731-line god object violates SRP, hard to test |
| 13 | Add SAML SSO support | Enterprise | OIDC works but SAML-only IdPs are unsupported |
| 14 | Add load/stress test suite | Testing | No performance regression detection in CI |
| 15 | Add fuzz testing to CI | Testing | `fuzz/` directory exists but unused |
| 16 | Fix dashboard heading hierarchy (sidebar `<h1>` → `<div>`) | Accessibility | WCAG 1.3.1 — two `<h1>` per page |
| 17 | Add `aria-expanded` to sidebar toggle | Accessibility | WCAG 4.1.2 — screen reader can't detect collapse state |
| 18 | Add `scope="col"` to table headers | Accessibility | WCAG 1.3.1 — poor column association |
| 19 | Add accessibility test pipeline | Accessibility | No automated a11y regression detection |
| 20 | Build dashboard billing UI | Commercial | No billing management page for paid users |
| 21 | Add `cutctx admin` umbrella command | DX | RBAC, orgs, audit, sso-test, policies are scattered |

### P3 — Future (quarterly)

| # | Item | Area | Reason |
|---|------|------|--------|
| 22 | SOC 2 Type II audit | Enterprise | Required for enterprise sales (~7.5 months) |
| 23 | Third-party penetration test | Security | Required for enterprise procurement |
| 24 | Multi-key admin support | Enterprise | Single global admin key limits enterprise adoption |
| 25 | MFA mandate | Enterprise | MFA exists but is enrollment-gated, not enforced |
| 26 | DR runbook + restore testing | Reliability | Backup exists; restore is untested |
| 27 | Connection pooling for SQLite | Performance | Opens/closes connections per call — contention under load |

---

## Conclusion

**Maturity score: 70/100.** The product is functional for individual developers and small teams. The compression engine works, the proxy routes traffic, the dashboard displays metrics, and the deployment options are mature.

**Can you sell it today?** To a developer who finds it on GitHub and runs `pip install` — yes. To a team lead who needs to evaluate it — yes, with a manual invoice. To a company that needs a signed contract, payment via credit card, and a SOC 2 report — not yet.

**The critical path:**
1. Fix `cutctx.dev` DNS and the Terms of Service (trust signals)
2. Wire Stripe Checkout directly (make payment actually work)
3. Enable error tracking by default (prevent silent failures)

These three items remove the blockers between "functional prototype" and "sellable product."
