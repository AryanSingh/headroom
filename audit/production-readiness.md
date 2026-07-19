# Production Readiness Assessment — 2026-07-18

**Repository:** `main @ 7b726934` (v0.31+)
**Codebase:** 573 Python + 196 Rust + 37 JS/TSX files
**Test suite:** 620+ root test files, 44 cargo tests, 3 dashboard unit tests
**CI/CD:** 24 GitHub workflows (CI, Docker, release, rust, e2e, benchmarks, fuzz, PR health)
**Working tree:** Clean
**Previous assessments:** 55/100 (Jul 4) → 78/100 (Jul 12) → **82/100 (Jul 18)**

---

## Readiness Score: **82 / 100** (Pilot-Ready, Approaching Broad Release)

| Dimension | Jul 12 | Jul 18 | Δ | Key Progress |
|---|---|---|---|---|
| **Features** | 85 | **88** | +3 | Billing dashboard merged, tier entitlements enforced on request path |
| **Security** | 82 | **85** | +3 | Audit CLI injection fixed, CCR entitlement leak closed, verified remediations |
| **Performance** | 70 | **75** | +5 | Safe savings observability added, no structural gaps yet |
| **Deployment** | 78 | **82** | +4 | Helm/k8s version drifts fixed, CI covers deployment paths |
| **Testing** | 75 | **78** | +3 | Verified remediation tests added, EE/core gaps persist |
| **Monitoring** | 65 | **72** | +7 | Safe savings panels, CLI status, provenance UI, attribution reconciliation |
| **Overall** | **78** | **82** | +4 | |

---

## 1. Features — Score: 88/100

### Recent Wins (Jul 12–18)
| Finding | Status |
|---|---|
| PitchToShip billing dashboard | ✅ Merged — `cutctx pitch-to-ship billing dashboard` (256c04f8) |
| Business tier entitlement enforcement | ✅ Merged — `enforce business tier entitlements on request path` (0085cde2) |
| Safe savings model, API, CLI, dashboard | ✅ Merged — 4 commits (61c4a451, 55dcce20, 5c38afef, ae5e768c) |
| Attribution reconciliation provenance in savings UI | ✅ Merged (70b1c9cf) |

### Remaining Gaps
| Finding | Severity | Detail |
|---|---|---|
| `stripe_webhook.py:292-295` missing `customer.subscription.created` handler | **Medium** | Only `.deleted` and `.updated` handled |
| Kompress batch compression path flagged TODO (PR-B4) | **Low** | `crates/cutctx-core/src/transforms/live_zone.rs:1618` |
| Memory service lacks RBAC / audit emission (explicit TODO) | **Medium** | `cutctx_ee/memory_service/api.py:110` |
| No dashboard billing/pricing/subscription page | **Medium** | Billing backend merged but dashboard UX still absent |
| `cutctx/integrations/langchain/providers.py:169` TODO | **Low** | `# Add dedicated providers when needed` |

### Feature Flags (Gated, Not Leaked)
`CUTCTX_OFFLINE_MODE`, `CUTCTX_SSO_ENABLED`, `CUTCTX_MFA_ENFORCE`, `CUTCTX_KOMPRESS_MAX_WORDS`, `CUTCTX_EGRESS_POLICY`, `CUTCTX_ALLOW_DEBUG`

---

## 2. Security — Score: 85/100

### Recent Remediations Verified (Jul 17)
| Finding | Status | Evidence |
|---|---|---|
| Audit CLI SQL injection via URL query concatenation | ✅ Fixed | Now uses `params=` dict (`d341233e`) |
| CCR paid-feature revenue leak (free-tier CCR) | ✅ Fixed | Entitlements enforced on request path (0085cde2) |
| Managed RTK binary stale (v0.28.2 → v0.43.0) | ✅ Fixed | Pin + checksums updated Jul 17 |
| Helm/k8s metadata stale (v0.30.0 refs) | ✅ Fixed | Updated to v0.31.0 Jul 17 |
| CI ignored deployment-only changes | ✅ Fixed | `helm/**` and `k8s/**` added to path filters Jul 17 |
| Package version drift blocks release | ✅ Narrowed | Version sync runs before verify-versions in release |
| ContentRouter payload expansion | ✅ Fixed | Byte invariant enforced for direct callers |

### Strengths
- **Deployment security validator** — block launch without admin auth on non-loopback
- **Multi-layered auth** — admin API key, proxy client key, SSO/JWT, MFA
- **Security layer** — LLM firewall, PII detection, injection blocking, state encryption
- **HMAC audit chain** with integrity verification
- **Circuit breaker** per-provider failure isolation
- **Egress policy enforcer** (opt-in via `CUTCTX_EGRESS_POLICY`)
- **Secret detection** in pre-commit + `.gitguardian.yaml` allowlist
- **cargo-deny** for Rust dependency license enforcement
- **`.env.example`** — comprehensive 310-line config doc (no plaintext secrets)

### Remaining Gaps
| Finding | Severity | Detail |
|---|---|---|
| **No Sentry/error tracking** | **High** | Unhandled exceptions in request handlers have no fallback reporting. Silent failures in production. |
| **K8s NetworkPolicy allows all egress** | **Medium** | `0.0.0.0/0` on 443/80/53 — opposite of deny-all. App-level enforcer exists but is opt-in. |
| **Auth brute-force lacks progressive backoff** | **Medium** | Fixed token-bucket (10/min/IP). No exponential backoff. Multi-IP attacker persists. |
| **No memory pressure health check** | **Medium** | `/livez` and `/readyz` don't check RSS, available memory, or swap |
| **Metrics endpoint behind admin auth** | **Medium** | Prometheus scrapers need unauthenticated access or separate auth config |
| **No CSRF protection on dashboard** | **Medium** | SPA with header-based auth, no SameSite/CSRF token patterns |
| **Compression cache no memory budget** | **Low** | `max_entries=10000` but no per-entry size limit |
| **No `[advisories]` in deny.toml** | **Low** | cargo-deny configured for licenses only — no vulnerability database checks |
| **No `pip-audit` in CI** | **Low** | No Python dependency vulnerability scanning |
| **No security.txt / PGP key for disclosures** | **Low** | No `/.well-known/security.txt` |

---

## 3. Performance — Score: 75/100

### Strengths
- **Rust native core** for compression transforms (PyO3 bindings)
- **Token bucket rate limiter** (per-key, per-IP)
- **Semantic caching** — repeated queries saved cost
- **Circuit breaker** — fail fast on dead upstreams
- **Retry with exponential backoff** per-provider
- **Prometheus metrics** — request counts, token usage, latency, TTFB, per-transform timing
- **Safe savings monitoring** added (CLI, dashboard, status API)
- **Backpressure on compression executor**

### Remaining Gaps
| Finding | Severity | Detail |
|---|---|---|
| **No per-request memory accounting** | **High** | 50MB default `max_body_mb` × concurrent requests has no safeguard against RAM exhaustion |
| **Compression cache no per-entry size limit** | **Medium** | 10K entries × variable size. Pathological case fills RAM. |
| **All caches in-memory, no persistence** | **Medium** | Every deployment = cold cache. Warm-up period for compression patterns. |
| **No WebSocket session cap** | **Medium** | `WebSocketSessionRegistry` has no `max_sessions` config |
| **K8s memory limit tight** | **Medium** | 512Mi limit for proxy + compression workers under load |
| **Multi-version Python testing "planned"** | **Low** | Testing on single version (3.12) — no 3.10/3.11/3.13 in CI |
| **HPA maxReplicas=1** | **Low** | Blocked by ReadWriteOnce PVC — no horizontal scale |

---

## 4. Deployment — Score: 82/100

### Strengths
- **Multi-arch Docker build** (linux/amd64 + linux/arm64 on native runners) — 8 variant builds
- **Cosign keyless signing** via Sigstore OIDC
- **Full K8s stack**: Deployment, HPA, PDB, Service, Ingress, NetworkPolicy, ConfigMap, Secret, PVC, RBAC, PrometheusRule
- **Helm chart** with versioned releases
- **24 CI workflows** — build, test, lint, e2e, benchmarks, fuzz, chaos, release
- **Release-please** automated version management
- **Backup CronJob** — S3 with 30-day retention (17 SQLite databases)
- **Pre-commit hooks**: ruff, mypy, secret detection, text hygiene
- **Verification scripts**: version sync, leak guard (OSS wheel clean), secret checking
- **Makefile** — 25+ targets including `ci-precheck` full CI gate locally
- **.actrc** for local `act` simulation

### Remaining Gaps
| Finding | Severity | Detail |
|---|---|---|
| **Ingress TLS host is placeholder** | **High** | `cutctx.example.com`, cert-manager annotation commented out. TLS won't work without edits. |
| **PitchToShip external billing dependency** | **Medium** | 20+ files depend on `pitchtoship.com`. HTTP 400 upstream blocks billing. |
| **HPA effectively disabled** (maxReplicas=1) | **Medium** | ReadWriteOnce PVC precludes horizontal scale. Requires RWX or external state. |
| **Backup uses alpine+aws-cli** (~200MB/run) | **Low** | Heavy per-backup pod. Could use aws-cli docker image or s3cmd. |
| **No explicit rollback procedure documented** | **Low** | No rollback.md, runbook, or playbook |
| **No Terraform/Pulumi for infra-as-code** | **Low** | Raw K8s manifests only |
| **No canary deployment strategy** | **Low** | RollingUpdate configured but no canary/flagger/argo-rollouts |

---

## 5. Testing — Score: 78/100

### Strengths
- **620+ root test files** (500 in `tests/` root)
- **4-way parallel pytest sharding** via `pytest-split`
- **Branch + line coverage** with 70% codecov target
- **Comprehensive benchmark suite** (35+ files)
- **Fuzz testing** (Rust cargo-fuzz targets)
- **E2E tests** (control plane, native install, wrap)
- **Parity tests** between Python ↔ Rust implementations
- **44 Rust cargo test files** + doc tests
- **Pre-commit quality gates**: lint, format, type-check, secret scan

### Remaining Gaps
| Finding | Severity | Detail |
|---|---|---|
| **Enterprise Edition severely undertested** | **High** | 6 test files for 45 source files (13% ratio). SSO, RBAC, SCIM, audit, retention, fleet, DSR, residency, secrets — 7+ major features with near-zero test coverage |
| **Dashboard only 3 unit tests** | **High** | bundle-budget, load-results, fetch-timeout — no component/render tests |
| **Core `cutctx/` modules untested** | **Medium** | `compress.py`, `client.py`, `dedup.py`, `security/`, `context_budget.py`, `profiles.py` — no dedicated test files |
| **Proxy routes directory untested** | **Medium** | `cutctx/proxy/routes/` has no dedicated test file |
| **Multi-Python-version testing "planned follow-up"** | **Medium** | CI only tests on 3.12 |
| **265 test files use skip markers** | **Low** | Most are environment-dependent (live API keys), but could be cleaner |
| **No property-based testing** | **Low** | No Hypothesis or similar |
| **No mutation testing** | **Low** | Not yet in pipeline |

---

## 6. Monitoring — Score: 72/100 (+7 since Jul 12)

### Recent Wins (Jul 12–18)
| Feature | Status |
|---|---|
| Safe savings dashboard panel | ✅ Merged |
| Safe savings CLI status command | ✅ Merged |
| Safe savings status API endpoint | ✅ Merged |
| Safe savings status model | ✅ Merged |
| Attribution reconciliation provenance in savings UI | ✅ Merged |

### Strengths
- **Prometheus metrics endpoint** — request counts, token usage, latency, TTFB, per-transform timing, waste signals, prefix cache stats, cumulative savings
- **Structured JSON logging** with request ID correlation, API key redaction
- **Health checks**: `/livez`, `/readyz`, `/health` with upstream, cache, rate limiter validation
- **K8s liveness/readiness/startup probes** with proper timeouts
- **FluentBit DaemonSet** for log collection
- **Request trace inspector** via `/transformations/traces/{request_id}`
- **OpenTelemetry integration** (optional)
- **K8s Prometheus scrape annotations**

### Remaining Gaps
| Finding | Severity | Detail |
|---|---|---|
| **Only 2 alerting rules** | **High** | HighErrorRate (5xx >5%) + HighLatency (p99 >2s). Missing: memory pressure, executor queue, WS spikes, upstream connectivity loss, disk space, cert expiry, auth failure spikes |
| **No Sentry/error tracking** | **High** | Unhandled exceptions have zero fallback reporting |
| **No disk space monitoring** | **Medium** | SQLite + cache growth can fill disk silently |
| **No memory pressure alert** | **Medium** | No PrometheusRule for RSS >80% or OOM risk |
| **FluentBit only outputs to stdout** | **Medium** | No log alerting output, no structured destination (Elasticsearch/Loki) |
| **No SLO/SLI definitions** | **Low** | No documented service-level targets |
| **No synthetic monitoring** | **Low** | No external health check probes |
| **No PagerDuty/Opsgenie integration** | **Low** | Alert routing not configured |
| **Metrics endpoint may be auth-guarded** | **Low** | Prometheus scrapers need unauthenticated or separate auth |

---

## Prioritized Action Plan

### Legend
**P0** = Blocking production launch · **P1** = High risk if absent · **P2** = Important but not blocking · **P3** = Nice to have

### Week 1 (Score: 82 → 87)

| Pri | Action | Area | Effort | Target Gap |
|---|---|---|---|---|
| **P0** | Add Sentry/error tracking to proxy startup — instrument all request handlers | Monitoring | 0.5d | Silent failure in production |
| **P0** | Expand PrometheusRules — add: memory pressure (RSS >80%), executor queue depth, WS session spike, upstream connectivity, disk space, cert expiry, auth failure spike | Monitoring | 1d | Only 2 alerting rules |
| **P0** | Add `max_ws_sessions` configurable cap to `WebSocketSessionRegistry` | Performance | 0.5d | Unbounded WS sessions |
| **P1** | Add per-request memory accounting with configurable budget (default 20MB) | Performance | 1d | 50MB default × concurrency = OOM risk |
| **P1** | Add memory pressure check to `/livez` and `/readyz` — warn at 80% RSS | Monitoring | 0.5d | Health checks blind to memory |
| **P1** | Write core module test files: `compress.py`, `client.py`, `security/`, `context_budget.py` | Testing | 2d | 9 production modules untested |
| **P1** | Write EE test coverage for SSO, RBAC, SCIM, audit, retention | Testing | 3d | 6 tests for 45 source files |
| **P1** | Reduce default `max_body_mb` from 50 to 10, add per-worker memory limit | Performance | 0.5d | OOM vector |

### Week 2 (Score: 87 → 91)

| Pri | Action | Area | Effort | Target Gap |
|---|---|---|---|---|
| **P1** | Tighten K8s NetworkPolicy — deny-all egress default, allowlist specific provider endpoints | Security | 0.5d | All egress allowed |
| **P1** | Add compression cache memory budget — per-entry size cap + total memory limit | Performance | 1d | Unbounded cache memory |
| **P2** | Add progressive backoff to admin auth rate limiter (exponential delay) | Security | 1d | No backoff, multi-IP bypass |
| **P2** | Add `pip-audit` + `cargo audit` to CI pipeline | Security | 0.5d | No vulnerability scanning |
| **P2** | Write dashboard component tests (Playwright — Overview, Savings, Memory views) | Testing | 2d | 3 unit tests only |
| **P2** | Add `customer.subscription.created` handler to `stripe_webhook.py` | Features | 0.5d | Incomplete webhook coverage |
| **P2** | Add persistent cache backend (Redis or SQLite) for compression patterns | Performance | 2d | Cold cache every deploy |

### Month 2 (Score: 91 → 95+)

| Pri | Action | Area | Effort | Target Gap |
|---|---|---|---|---|
| **P2** | Wire direct Stripe Checkout (decouple from PitchToShip) | Billing | 3d | External billing dependency |
| **P2** | Configure HPA with shared RWX volume or external state backend | Deployment | 2d | HPA maxReplicas=1 |
| **P3** | Add CSRF protection to dashboard endpoints | Security | 0.5d | No CSRF tokens |
| **P3** | Configure cert-manager + update Ingress with real TLS hostname | Deployment | 0.5d | Placeholder host/TLS |
| **P3** | Define SLOs/SLIs + add synthetic monitoring probes | Monitoring | 1d | No service-level targets |
| **P3** | Add multi-Python-version CI matrix (3.10, 3.11, 3.13) | Testing | 1d | 3.12 only |
| **P3** | Add dashboard billing/pricing pages | Features | 2d | Missing UX for billing |
| **P3** | Configure PagerDuty/Opsgenie alert routing | Monitoring | 0.5d | No alert notification |

---

## Day-One Launch Checklist

Before the first paying production tenant goes live:

- [ ] **Sentry** (or equivalent) configured and verified — test exception produces alert
- [ ] **Alert rules deployed** — memory pressure, executor queue depth, WS session count, upstream connectivity, disk space, cert expiry, auth failure spike
- [ ] **`max_ws_sessions`** set to sensible production limit (e.g. 500)
- [ ] **Per-request memory accounting** enabled with non-default budget
- [ ] **Direct Stripe checkout** verified with end-to-end test payment
- [ ] **`customer.subscription.created`** webhook handler deployed
- [ ] **K8s NetworkPolicy** tightened to deny-all egress with provider allowlist
- [ ] **TLS certificate** configured in Ingress (annotations uncommented, real hostname)
- [ ] **`pip-audit`** / **`cargo audit`** passing in CI
- [ ] **HPA** configured with external state backend (RWX or Redis/PostgreSQL)
- [ ] **EE test suite** at minimum covering: SSO login flow, RBAC enforcement, SCIM provisioning, audit trail verification

---

## Risk Register (Updated Jul 18)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Silent production failures (no Sentry) | Medium | High | P0 — Week 1 |
| OOM under load (512Mi limit + 50MB requests) | Medium | High | P1 — Week 1 |
| Alert-blind degradation (only 2 rules) | High | Medium | P0 — Week 1 |
| Enterprise regression (EE undertested) | Medium | High | P1 — Week 1 |
| Auth brute-force via IP rotation | Low | High | P2 — Week 2 |
| PitchToShip billing outage | Low | Critical | P2 — Month 2 |
| Cache memory exhaustion | Low | Medium | P2 — Week 2 |
| WebSocket resource exhaustion | Low | Medium | P0 — Week 1 |

---

## Evidence & Methodology

This assessment is based on direct codebase exploration of 573+ Python files, 196+ Rust files, 37 JS/TSX files, 24 CI workflows, K8s manifests, Docker build, Helm chart, security configs, pre-commit hooks, and git log analysis from June–July 2026.

**Previous baselines:**
- Jul 4: `audit/production-readiness-2026-07-04.md` — 55/100
- Jul 12: `audit/production-readiness.md` — 78/100
- Jul 17: `audit/verified-remediation-2026-07-17.md` — independent claim verification

**Key source files examined:**
- `cutctx/proxy/server.py` — proxy entry, health checks, auth, auth_mode.py, CORS
- `cutctx/proxy/rate_limiter.py`, `circuit_breaker.py`, `prometheus_metrics.py`
- `cutctx/proxy/deployment_security.py` — launch-blocking validation
- `cutctx/security/` — state_crypto, integrity, egress, mfa
- `cutctx/billing.py`, `cutctx_ee/billing/stripe_webhook.py` — billing surface
- `cutctx/telemetry/`, `cutctx/observability.py` — monitoring surface
- `k8s/` — deployment, hpa, pdb, network-policy, ingress, secret, prometheus-rules
- `helm/cutctx/` — Chart.yaml, values.yaml
- `.github/workflows/` — ci.yml, docker.yml, release.yml, rust.yml
- `Dockerfile`, `Makefile`, `pyproject.toml`, `Cargo.toml`, `deny.toml`
- `.pre-commit-config.yaml`, `.gitguardian.yaml`
# 2026-07-19 merged-main production-readiness addendum

Score: **78/100 — pilot-ready, not GA-ready.** Main passed the local core gate,
lint, and diff integrity checks. Fresh Docker-native and browser release
evidence are still required because their recorded failures were against an
older feature SHA.
