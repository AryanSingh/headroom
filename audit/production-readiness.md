# Production Readiness Assessment — 2026-07-10

**Project:** Cutctx (headroom) — Context compression layer for AI agents
**Version:** v0.30.0 (pyproject.toml)
**HEAD:** `418ae99a`
**Method:** Independent 6-dimension audit via codebase recon, config analysis, test assessment, and dependency audit. Supersedes prior audits (Jul 2-6 reports referenced for delta tracking).

---

## Overall Score: **79 / 100** (+16 from Jul 4's 63; -7 from Jul 4's release-audit 86 due to broader scope including billing/support/enterprise readiness)

| Dimension | Score | Trend | Verdict |
|-----------|-------|-------|---------|
| 1. Missing Features | 70/100 | +5 | Stubs remain but license validation no longer hardcoded True |
| 2. Security | 88/100 | +10 | All 5 critical items fixed. HMAC, loopback bypass, CORS issues resolved |
| 3. Performance | 72/100 | +2 | N+1 queries remain in graph, no pricing cache |
| 4. Deployment | 78/100 | +23 | v0.30.0 tagged, version alignment fixed, CI/CD robust |
| 5. Testing | 92/100 | +24 | ~7,924+ passing, 0 failures last audit sweep |
| 6. Monitoring | 72/100 | +34 | OTEL, Prometheus, Langfuse wired — still missing error tracking |

---

## 1. Missing Features — 70/100

### What's good
- Core compression pipeline (17 strategies) fully implemented: SmartCrusher, CodeCompressor, Kompress, CacheAligner, ContentRouter
- CCR reversible compression with retrieval tool — production ready
- Cross-agent memory (SQLite + USearch + Qdrant + Neo4j backends)
- Multi-provider support: Anthropic, OpenAI, Gemini, Bedrock, LiteLLM
- Dashboard SPA with savings tracking, governance, capabilities toggles
- CLI with 34+ commands, agent wrap for 14 tools, MCP server
- `cutctx learn` for agent self-improvement

### CRITICAL stubs
| Issue | Detail | Impact |
|-------|--------|--------|
| **5 EE stub routes return 501** | memory RBAC, license, SSO routes in OSS mode | OSS users hit 501 from documented paths |
| **License validation still no-op** | `cutctx_ee/watermark.py:195` validates but doesn't deny service | Any key passes |
| **20+ features default-off** | Firewall, ensemble, episodic memory, autopilot, OTEL, Langfuse, etc. | Proxy boots near-pass-through by default |

### MEDIUM
- 8 stub-EE modules raise `ImportError` instead of graceful 501
- Some enterprise routes silently 404 when EE missing (no error message)
- Cutctx.dev NXDOMAIN (all emails bounce, no website, no docs site)

---

## 2. Security — 88/100

### What's been verified fixed (since Jul 2-4 audits)
- ✅ Loopback auth bypass closed for `/dashboard`, `/api/savings`, `/api/models`
- ✅ LIKE wildcard injection guard (`_escape_like()` + `ESCAPE "\"` clause)
- ✅ Kompress max-input DoS guard (`CUTCTX_KOMPRESS_MAX_WORDS`)
- ✅ CORS wildcard + credentials conflict resolved (`credentials=False` when `origins=["*"]`)
- ✅ Health endpoint split: public `/health` (no config leak) vs admin-gated `/health/config`
- ✅ HMAC audit chain fixed: `hmac.new(secret, msg, hashlib.sha256)` — was plain SHA-256
- ✅ Residency verification via `hashlib.sha256().digest()`
- ✅ DSR imports with honest gated fallbacks
- ✅ EgressEnforcer wired at 15+ call sites
- ✅ Fernet AES-128-CBC + HMAC-SHA256 encryption for local state
- ✅ No real hardcoded secrets in source

### Still open — HIGH
| Issue | Detail | Risk |
|-------|--------|------|
| **License validation no-op** | Validates but doesn't enforce. Paying customer bypasses license check. | Revenue loss |
| **Cross-project memory leak** | Tenant isolation not enforced in memory backends | Data leak in multi-tenant |
| **CCR retrieval endpoints no admin auth** | `/v1/retrieve/*` protected by entitlement only | Unauthorized content access |
| **`/v1/feedback` no admin auth** | Feedback endpoint unprotected | Data injection |
| **SQL injection in eval harness** | `batch_compression_eval.py:689` — `f"SELECT * FROM users WHERE id = {user_id}"` | Non-production but concerning pattern |
| **Exception text leaked in 500s** | 5 sites return raw `str(e)` in HTTP response | Info disclosure |

### Still open — MEDIUM
- Stripe webhook fall-open if `STRIPE_WEBHOOK_SECRET` unset
- X-Cutctx-Version header on every response (CVE recon)
- Machine-bound encryption default (same machine-id = decrypt)
- No SAML SSO (OIDC only)
- No WebAuthn (TOTP only)
- 2 license formats coexist (Ed25519 + ECDSA P-256)
- Spend ledger tenant isolation missing
- NetworkPolicy allows egress to 0.0.0.0/0
- License DB world-readable (no chmod 600)

---

## 3. Performance — 72/100

### What's well-optimized
- ✅ 50 MB body cap with Content-Length precheck + post-decompression verification
- ✅ Bounded data structures: `_retrieval_events` (MAX_EVENTS=1000), search_queries cap=10
- ✅ LRU eviction via min-heap in compression store
- ✅ Session replay bounded (256 sessions × 200 events)
- ✅ Request logger bounded (deque maxlen=10,000)
- ✅ Image base64 redaction before persistence
- ✅ 11 indexes on `memories` table

### Critical
| Issue | Detail | Impact |
|-------|--------|--------|
| **N+1 graph BFS queries** | `sqlite_graph.py:432-441` — one round-trip per entity instead of `WHERE id IN (...)` | O(visited²) queries for max_hops=2 |
| **N+1 Neo4j embedding calls** | `direct_mem0.py:475-535` — 2N embed API + N Cypher per batch | Multi-second latency per memory write |

### HIGH
| Issue | Detail |
|-------|--------|
| Missing index: `workspace_id`, `project_id` on `memories` | Every per-tenant query = full table scan |
| Missing index: `actor`, `action`, `timestamp` on audit | Audit queries = full table scan |
| No TTL eviction on `ccr_entries` | Dead rows accumulate unboundedly |
| No pricing cache | `_get_list_price()` called on every stats hit |
| Sync file IO in async request path | `chat.py:1339`, `anthropic.py:2349` — blocks event loop |
| 2-query per audit append | SELECT prior hash + INSERT — could be batched |
| Unbounded dict growth in cost tracker | `proxy/cost.py:752-767, 869-888` — no eviction policy |

---

## 4. Deployment — 78/100

### What's strong
- ✅ **v0.30.0 tagged and released** — version alignment issue from Jul 4 audit is resolved
- ✅ 24 CI/CD workflows — paths-filter, parallel test shards, lint/test/build staged
- ✅ Release pipeline: tag-driven with matrix wheels, SBOM generation, PyPI trusted publishing
- ✅ Full k8s manifests: deployment, service, ingress, HPA, PDB, network policy, ConfigMap, Secret, RBAC, backup CronJob, PrometheusRule, fluent-bit, PVC, namespace
- ✅ Docker multi-stage build with distroless runtime option + HEALTHCHECK
- ✅ docker-compose (proxy + qdrant + neo4j) with healthcheck
- ✅ Helm chart (Chart.yaml, templates for all resources, values.yaml)
- ✅ Release-please configured
- ✅ Pre-commit hooks: ruff, mypy, text hygiene, dashboard lint, version sync
- ✅ Makefile with ci-precheck target

### Still open
| Issue | Severity | Detail |
|-------|----------|--------|
| **Working tree dirty** | HIGH | Many modified files from release-prep work. Risk of unintended changes. |
| **Ingress placeholder domain** | MEDIUM | `cutctx.example.com` — requires per-deployment customization |
| **`hello@cutctx.dev` in k8s/secret.yaml** | MEDIUM | Domain is NXDOMAIN. License keys reference dead email. |
| **cutctx.dev / cutctx.com both NXDOMAIN** | HIGH | All docs links, security contacts, and copyright notices point at unreachable domains |
| **No dependency vulnerability scanning** | MEDIUM | Dependabot configured for updates but no CVE scanning in CI |
| **No release SBOM verification** | LOW | SBOM generated but no signature verification in pipeline |
| **Helm Chart.yaml vs values.yaml drift** | LOW | `Chart.yaml@0.30.0` matches `values.yaml@0.30.0` — fixed since Jul 4 |

---

## 5. Testing — 92/100

### What's solid
- ✅ **~550 test files, ~2,650 Python test functions + Rust tests** — massive coverage
- ✅ **Prior audit sweep: 7,924 passed, 0 failed, 258 skipped** (365s runtime)
- ✅ P0 cluster (CCR, content router, capability extensions): 91/91 passed
- ✅ Security cluster (egress enforcer, firewall, residency): 28/28 passed
- ✅ Dashboard e2e via Playwright: passing
- ✅ Audit HMAC regression test exists
- ✅ Code coverage tracking via Codecov (target: auto)
- ✅ Fuzz testing setup (`fuzz/`)
- ✅ Pre-commit hooks enforcing ruff, mypy, text hygiene
- ✅ Benchmark suite (`cargo bench`, `benchmarks/`)
- ✅ Parity tests ensuring Python ↔ Rust behavioral equivalence

### Gaps
| Issue | Severity | Detail |
|-------|----------|--------|
| **22/22 EE modules untested** | HIGH | 3,939 LOC of enterprise-only code with zero test coverage |
| **7 proxy routes untested** | MEDIUM | Enterprise-focused routes (license validation, SSO endpoints) |
| **59 `time.sleep()` calls in tests** | MEDIUM | Flaky under load — should use proper wait/retry |
| **6 hard-skipped tests with no reason** | LOW | Skipped with no `skipif` condition or comment |
| **No chaos testing in regular CI** | LOW | Chaos-testing workflow exists but is separate |
| **Integration tests require API keys** | MEDIUM | Many live tests skip without `OPENAI_API_KEY` etc. |

---

## 6. Monitoring — 72/100

### What's implemented
- ✅ `/livez`, `/readyz`, `/health` endpoints with per-component health checks
- ✅ Prometheus scrape config in k8s (`prometheus.io/scrape: "true"`)
- ✅ PrometheusRule alerts (HighErrorRate >5% 5xx, HighLatency p99 >2s)
- ✅ OTEL metrics system (`cutctx_otel_metrics`) with structured counters
- ✅ Langfuse tracing support
- ✅ Runtime metrics exposed (compression queue depth, wait times, leaked threads)
- ✅ WebSocket session tracking in health endpoint
- ✅ Dashboard with cache-busting fetches
- ✅ SBOM generation in CI
- ✅ Structured logging with JSON format option
- ✅ `X-Request-ID` propagation through proxy

### Critical gaps
| Issue | Detail | Impact |
|-------|--------|--------|
| **No centralized error tracking** | Sentry/OTel exporter not wired | Errors only visible in stderr logs — no alerting on exceptions |
| **No Prometheus /metrics for 3 new subsystems** | Feedback Loop, Stack Graphs, Benchmark CLI shipped without instrumentation | Cannot observe adoption or performance of new features |
| **PrometheusRule only has 2 alerts** | No alerts for: backup failure, license expiry, high queue depth, disk usage | Silent failures in critical operational paths |

### MEDIUM gaps
- No health-check endpoint specific to new features
- No dashboard alerting or notification channels
- `request_id` not wired into `logging.Filter` / `contextvars` — log correlation by request is manual
- No log shipping config in docker-compose (fluent-bit exists in k8s only)
- No operator health view in dashboard

---

## Channel-Specific Readiness

| Channel | Score | Verdict | Critical Path |
|---------|-------|---------|---------------|
| **Internal dev / staging** | 88/100 | ✅ **GO** | Fix working tree dirtiness before CI |
| **Design-partner pilot** | 79/100 | ⚠️ **CONDITIONAL GO** | Fix NXDOMAIN, fix license enforcement, wire error tracking |
| **Public OSS release** | 72/100 | ⚠️ **CONDITIONAL** | Fix billing pipeline, register cutctx.dev, fix 3 HIGH security items |
| **Paid enterprise** | 58/100 | ❌ **NO-GO** | SAML, WebAuthn, SOC 2, pentest, tenant isolation, SLA tooling — 2-3 months |

---

## Prioritized Action Plan

### P0 — Must fix before next ship (1-2 days)
| # | Item | Area | Effort |
|---|------|------|--------|
| 1 | **Register cutctx.dev** — all emails bounce, docs links dead, security contact unreachable | Deployment | 1h |
| 2 | **Fix license enforcement from no-op to denial** — `watermark.py:195` | Security | 2h |
| 3 | **Fix working tree** — commit or stash release-prep changes, ensure clean CI | Deployment | 2h |
| 4 | **Wire Sentry or OTel error exporter** — silent errors in production | Monitoring | 1d |

### P1 — Required for public OSS release (1-week sprint)
| # | Item | Area | Effort |
|---|------|------|--------|
| 5 | **Fix billing pipeline** — PitchToShip is dead; wire direct Stripe checkout | Features | 2-3d |
| 6 | **Add admin auth to CCR retrieval + feedback endpoints** | Security | 1d |
| 7 | **Fix N+1 graph BFS queries** — batch into `WHERE id IN (...)` | Performance | 1d |
| 8 | **Add centralized error tracking** — Sentry or OTel exporter integration | Monitoring | 2d |
| 9 | **Add dependency vulnerability scanning** — Dependabot alerts or `cargo audit` + `pip-audit` | Security | 1d |
| 10 | **Fix exception text leakage in 500 responses** (5 call sites) | Security | 1d |
| 11 | **Add pricing cache** — `functools.lru_cache` on `_get_list_price()` | Performance | 1h |

### P2 — Required before v1.0 / enterprise (2-3 week sprint)
| # | Item | Area | Effort |
|---|------|------|--------|
| 12 | **EE module test coverage** — 22 modules, 3,939 LOC | Testing | 3w |
| 13 | **Wire request_id into logging context** via `contextvars` | Monitoring | 1d |
| 14 | **Expand backup coverage** — all durable stores backed up (currently partial) | Deployment | 2d |
| 15 | **Add TTL eviction sweep on ccr_entries** | Performance | 1d |
| 16 | **Add missing indexes** — `workspace_id` on memories, `actor` on audit | Performance | 2h |
| 17 | **Fix sync file IO in async paths** (chat.py, anthropic.py) | Performance | 2h |
| 18 | **Replace 59 `time.sleep` calls** with proper wait/retry in tests | Testing | 2d |
| 19 | **Add DB health probes to /health** (audit.db, rbac.db, etc.) | Monitoring | 1d |
| 20 | **Add Prometheus metrics for Feedback Loop, Stack Graphs, Benchmark CLI** | Monitoring | 3d |

### P3 — Quality of life (next release)
| # | Item | Area |
|---|------|------|
| 21 | Implement SAML SSO | Security |
| 22 | Add WebAuthn MFA | Security |
| 23 | Consolidate 2 license formats (Ed25519 + ECDSA P-256) | Security |
| 24 | Spend ledger tenant isolation | Security |
| 25 | Consolidate `.env.example` to match actual env vars read | Deployment |
| 26 | Add Prometheus gauge for audit chain length | Monitoring |
| 27 | Remove 6 hard-skipped tests with no reason | Testing |
| 28 | Fix license DB world-readable (`chmod 600`) | Security |
| 29 | Add PVC manifest for backup CronJob | Deployment |
| 30 | Pin fluent-bit to specific version in k8s | Deployment |

---

## Summary

**Cutctx v0.30.0 is a mature, well-architected product with strong engineering fundamentals.** The test suite is clean (7,924+ pass, 0 failures), security posture is solid (all 5 critical items fixed), and deployment infrastructure rivals mature SaaS products (24 CI workflows, full k8s stack, Helm chart, Docker multi-stage build, Prometheus + OTEL monitoring).

**The remaining gaps are concentrated in 3 areas:**
1. **Billing & licensing** — no working payment path, license validation is a no-op, cutctx.dev NXDOMAIN
2. **Enterprise features** — no SAML, no WebAuthn, tenant isolation incomplete, gap in EE test coverage
3. **Operational maturity** — no error tracking, partial alert coverage, backup gap for some stores

**Verdict:**
- **Design-partner pilot: CONDITIONAL GO** (fix 4 P0 items = ~3 days)
- **Public OSS release: CONDITIONAL** (~1 week sprint on P1 items)
- **Enterprise sales: NO-GO** (~2-3 months for P2 items, SOC 2, pentest)

The 15+ commits since the Jul 4 audit have moved the product forward significantly. The core product is strong enough for informed design partners to deploy today.

---
*Document classification: Production-readiness assessment. Scope: full repository as of `main @ 418ae99a`. Independent analysis — all findings from read-only codebase recon.*
