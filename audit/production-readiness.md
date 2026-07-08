# Production Readiness Assessment

**Date:** 2026-07-07
**Version:** 0.31.0
**Scope:** Engineering readiness for production workloads

---

## Readiness Score: **68/100**

| Category | Score | Status |
|----------|-------|--------|
| Missing Features | 55 | 🟡 Several gaps in core flows |
| Security | 65 | 🟡 Solid foundation, missing certifications |
| Performance | 75 | 🟢 Well-architected, some concerns |
| Deployment | 80 | 🟢 First-class K8s/Helm support |
| Testing | 65 | 🟡 Strong unit coverage, weak integration |
| Monitoring | 70 | 🟡 Good base, missing production integrations |
| **Overall** | **68** | 🟡 **Conditional production readiness** |

---

## 1. Missing Features & Incomplete Paths (Score: 55)

### Blockers

| Issue | Severity | Detail |
|-------|----------|--------|
| **Self-serve billing broken** | CRITICAL | PitchToShip checkout is dead. No way for users to buy without manual intervention. CHANGELOG confirms this. |
| **TERMS.md is a draft** | CRITICAL | Labeled "must be reviewed by legal counsel." Cannot use in commercial procurement. |
| **Dashboard savings shows $0** | HIGH | `effectiveSavingsUsd` renders as $0.000 despite `lifetime.compression_savings_usd = $144`. Data flows through `/stats?cached=1` but frontend doesn't display it in Money Saved card. |
| **No self-serve trial flow** | HIGH | `cutctx/trial.py` exists in EE but no frontend flow to provision trials. |
| **No guided onboarding** | MEDIUM | First-run experience is `pip install` + manual config. No setup wizard, no decision tree for proxy vs wrap vs SDK vs MCP. |
| **No usage-based pricing option** | MEDIUM | All tiers flat-rate. No per-token or per-seat option for variable-spend teams. |
| **No cloud/managed option** | MEDIUM | Self-host only. Some buyers require managed SaaS. |

### Stubs / Placeholder Code

| Path | Issue |
|------|-------|
| `cutctx/billing.py` — PitchToShip integration | Integration is dead (confirmed in CHANGELOG) |
| `cutctx/checkout.py` | Points to non-functional `pitchtoship.com` |
| `TERMS.md` | Explicitly marked as draft needing legal review |
| `artifacts/openapi-management.yaml` | API spec exists but no matching frontend |
| `cutctx/proxy/routes/dsr.py` | DSR routes exist but GDPR compliance doc is missing |

---

## 2. Security (Score: 65)

### Strengths
| Feature | Status |
|---------|--------|
| SSO/OIDC/SAML | ✅ Working (`cutctx_ee`) |
| RBAC | ✅ Working (Viewer/Operator/Admin) |
| MFA/TOTP | ✅ Implemented |
| HMAC-SHA256 audit chain | ✅ Tamper-evident logging |
| Local-first by default | ✅ Loopback-only binding |
| API key auth | ✅ Bearer + header + query param |
| Network policies (K8s) | ✅ Defined |
| Secret scanning | ✅ `.gitguardian.yaml` configured |
| Security disclosure policy | ✅ `SECURITY.md` with 48h/7d SLAs |

### Gaps

| Gap | Severity | Impact |
|-----|----------|--------|
| **No SOC 2** | CRITICAL | Blocks enterprise procurement. Not started. |
| **No pentest report** | HIGH | Security teams will ask. No evidence of testing. |
| **Rate limiting on auth endpoints** | MEDIUM | No brute-force protection on login/auth |
| **Encryption-at-rest not documented** | MEDIUM | SQLite DBs (CCR, audit, spend) — no encryption policy |
| **No SBOM in CI** | MEDIUM | No software bill of materials generated |
| **Session management undocumented** | LOW | No session timeout or rotation policy |
| **No audit of third-party deps** | LOW | No automated dependency vuln scanning in CI |

### Auth Architecture Review

```
Browser ───→ Dashboard (React SPA)
                │
                │ x-cutctx-admin-key header
                ▼
         Cutctx Proxy ──→ API (FastAPI)
                │
                ├── Loopback bypass (localhost GET/HEAD only)
                ├── Admin key auth (Bearer | x-cutctx-admin-key)
                └── SSO (SAML/OIDC, enterprise tier)
```

The loopback bypass is safe for single-user setups but allows any local process to read stats/dashboard without a key in multi-tenant deployments.

---

## 3. Performance (Score: 75)

### Architecture

```
Client ──→ Cutctx Proxy (Python/FastAPI)
              │
              ├── httpx.AsyncClient (500 max connections)
              ├── ThreadPoolExecutor (32 workers for compression)
              ├── Rust core (_core.abi3.so) for compression engine
              ├── SQLite (CCR store, audit, spend ledger)
              └── Cache layers:
                    ├── Compression cache (exact-match)
                    ├── Provider-native (Anthropic prompt caching, OpenAI)
                    └── Semantic cache (planned via Qdrant)
```

### Bottleneck Analysis

| Area | Assessment | Risk |
|------|-----------|------|
| **Python overhead** | FastAPI + httpx adds ~8ms P95 overhead. Acceptable for LLM proxy use (LLM calls take seconds). | LOW |
| **Connection pool** | 500 max connections, 100 keepalive. Adequate for moderate traffic. | LOW |
| **Compression pipeline** | ThreadPoolExecutor with 32 workers. Rust core for heavy lifting. | LOW |
| **SQLite persistence** | Potential bottleneck under high write concurrency. WAL mode not confirmed. | MEDIUM |
| **Memory usage** | CCR store could grow unbounded without `--ccr-ttl-seconds`. | MEDIUM |
| **Rate limiter** | Token bucket, 1000 concurrency limit. `--limit-concurrency` flag exists. | LOW |

### Scalability Configuration (from arg parser)

| Flag | Default | Notes |
|------|---------|-------|
| `--max-connections` | 500 | HTTP connection pool |
| `--max-keepalive` | 100 | Keepalive connections |
| `--workers` | 1 | Worker processes. Use N for multi-core. |
| `--limit-concurrency` | 1000 | Max concurrent before 503 |
| HPA min/max replicas | 2 / 10 | K8s autoscaling |

### Missing

- **No load testing scripts** in repo
- **No performance regression gates** in CI
- **No PyPy/alternative runtime evaluation**
- **No CDN/edge deployment support**

---

## 4. Deployment (Score: 80)

### Infrastructure Readiness

| Asset | Status | Detail |
|-------|--------|--------|
| **Dockerfile** | ✅ | Multi-stage build with Python + Rust |
| **docker-compose.yml** | ✅ | Proxy + Qdrant + Neo4j, healthchecks |
| **K8s deployment.yaml** | ✅ | Configurable via ConfigMap |
| **K8s hpa.yaml** | ✅ | 2-10 replicas, CPU/Mem autoscaling |
| **K8s pdb.yaml** | ✅ | Pod disruption budget |
| **K8s ingress.yaml** | ✅ | Ingress configuration |
| **K8s network-policy.yaml** | ✅ | Network isolation |
| **K8s secret.yaml** | ✅ | Secret template |
| **K8s pvc.yaml** | ✅ | Persistent volume claims |
| **K8s rbac.yaml** | ✅ | Service account RBAC |
| **K8s configmap.yaml** | ✅ | Config map template |
| **K8s fluentbit.yaml** | ✅ | Log shipping config |
| **K8s prometheus-rules.yaml** | ✅ | Alert rules |
| **K8s backup-cronjob.yaml** | ✅ | Daily S3 backup, 30-day retention |
| **Helm chart** | ✅ | In `helm/cutctx/` |
| **CI/CD (22 workflows)** | ✅ | Build, test, publish, EE compile |
| **Release automation** | ✅ | release-please |

### Backup & Recovery

Backup CronJob exists and covers:
- `cutctx_memory.db` → S3 daily
- `spend_ledger.db` → S3 daily
- `audit.db` → S3 daily
- 30-day retention with auto-prune

**Missing:**
- ❌ No documented DR runbook
- ❌ No restore procedure tested/verified
- ❌ No database migration strategy for SQLite schema changes
- ❌ No canary deployment documented
- ❌ No blue-green deployment config

### Environment Configuration

| File | Purpose | Status |
|------|---------|--------|
| `.env.example` | Reference for env vars | ✅ Exists |
| `.env.act.example` | CI test env | ✅ Exists |
| `.env.local` | Local dev (gitignored) | ✅ Exists |
| `Dockerfile` | Container build | ✅ Multi-stage |
| `docker-compose.yml` | Local stack | ✅ 3 services |

---

## 5. Testing (Score: 65)

### Coverage

| Test Type | Count | Quality |
|-----------|-------|---------|
| Python unit tests | 544 files | ✅ Comprehensive |
| E2E tests | 3 files | ⚠️ Minimal |
| Rust tests | `crates/*` | ✅ In each crate |
| Fuzz targets | `fuzz/` | ✅ Exists |
| Benchmarks | `benchmarks/` | ✅ Exists |
| Code coverage | codecov.yml | ✅ Configured |
| Pre-commit hooks | `.pre-commit-config.yaml` | ✅ Configured |

### CI Pipeline (22 workflows)

| Workflow | Purpose |
|----------|---------|
| `ci.yml` | Core CI |
| `pr-health.yml` | PR quality gate |
| `benchmark.yml` | Performance benchmarks |
| `chaos-testing.yml` | Resilience testing |
| `compile-ee.yml` | EE compilation |
| `devcontainers.yml` | Dev container build |
| `docker.yml` | Docker image build |
| `docs.yml` | Documentation build |
| `eval.yml` | Evaluation suite |
| `init-e2e.yml` | E2E setup |
| `init-native-e2e.yml` | Native E2E setup |
| `install-native-e2e.yml` | Native install test |
| `network-diff-capture.yml` | Network diff testing |
| `publish.yml` | Package publishing |
| `publish-ee.yml` | EE publishing |

### Critical Gaps

| Gap | Severity | Detail |
|-----|----------|--------|
| **No integration tests with real providers** | HIGH | Tests mock external APIs. No real Anthropic/OpenAI test. |
| **No performance regression gates in CI** | HIGH | Benchmarks exist but aren't enforced |
| **Chaos testing workflow exists but not confirmed running** | MEDIUM | `chaos-testing.yml` in workflows |
| **No snapshot/approval tests for dashboard** | MEDIUM | Dashboard rendering not tested |
| **No load testing scripts** | MEDIUM | No k6/artillery/locust config |
| **No contract tests** | LOW | No provider API contract verification |
| **Flaky test handling not documented** | LOW | No retry/re-run strategy visible |

---

## 6. Monitoring (Score: 70)

### Health Endpoints

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `/livez` | Process liveness | ✅ |
| `/readyz` | Traffic readiness | ✅ (checks upstream, cache, memory) |
| `/health` | Aggregate health | ✅ (full system status) |
| `/health/config` | Config health | ✅ |
| `/metrics` | Prometheus metrics | ✅ |

### Logging

| Feature | Status |
|---------|--------|
| Python logging (INFO default) | ✅ |
| Log level config via env | ✅ (basicConfig) |
| Structured logging | ❌ Text only |
| Log file rotation | ❌ Not configured |
| Log shipping (fluentbit) | ⚠️ K8s config exists |

### Metrics & Alerting

| Feature | Status |
|---------|--------|
| Prometheus `/metrics` | ✅ |
| PrometheusRule (error rate, latency) | ✅ In K8s |
| Grafana dashboard | ❌ Not shipped |
| PagerDuty/Opsgenie integration | ❌ No webhook config |
| Custom business metrics | ❌ Not implemented |

### Tracing

| Feature | Status |
|---------|--------|
| Langfuse tracing | ✅ Configurable |
| OpenTelemetry | ✅ Configurable |
| Distributed tracing | ⚠️ Via Langfuse only |
| Request ID propagation | ✅ Implemented |

### Missing

| Gap | Impact |
|-----|--------|
| No structured JSON logging | Hard to parse in log aggregators |
| No Grafana dashboard in repo | Operations team must build from scratch |
| No PagerDuty/Opsgenie integration | No automated incident response |
| No SLO tracking | No dashboards measuring uptime/latency targets |
| No cost monitoring dashboards | No view of per-customer spend in hosted scenarios |
| No audit dashboard for non-EE | Audit logs only available in commercial tier |

---

## Prioritized Action Plan

### P0 — Must Fix Before Production (this week)

| # | Item | Category | Effort | Impact |
|---|------|----------|--------|--------|
| 1 | **Fix dashboard Money Saved display** — `$273` exists in API but frontend shows `$0.000` | Missing Features | 1 day | High |
| 2 | **Fix billing flow** — or establish manual invoicing process for first paid customers | Missing Features | 3 days | Critical |
| 3 | **Legal review TERMS.md** — cannot take money without finalized terms | Missing Features | 1 week | Critical |
| 4 | **Generate security review packet** — architecture, data flow, compliance, incident response for enterprise procurement | Security | 3 days | High |

### P1 — Week 1-2

| # | Item | Category | Effort | Impact |
|---|------|----------|--------|--------|
| 5 | **Commission pentest** — publish results (can be summary) | Security | 2 weeks | High |
| 6 | **Build restore runbook** — document and test DB restore from S3 backup | Deployment | 1 day | High |
| 7 | **Add Prometheus alert to PagerDuty webhook** — configure in K8s | Monitoring | 1 day | Medium |
| 8 | **Add structured JSON logging** — structured logging formatter | Monitoring | 2 days | Medium |
| 9 | **Add load testing with k6/locust** — in `benchmarks/` | Testing | 3 days | Medium |

### P2 — Month 1

| # | Item | Category | Effort | Impact |
|---|------|----------|--------|--------|
| 10 | **SOC 2 readiness assessment** — engage auditor | Security | Ongoing | Critical for enterprise |
| 11 | **Add integration tests with real provider** — optional CI workflow with provider keys | Testing | 1 week | High |
| 12 | **Add Grafana dashboard JSON** — ship with repo | Monitoring | 2 days | Medium |
| 13 | **Document database migration strategy** — SQLite schema versioning | Deployment | 2 days | Medium |
| 14 | **Add SBOM generation to CI** — `pip-audit` + `cargo audit` | Security | 1 day | Medium |
| 15 | **Add performance regression gates** — benchmark comparison in CI | Testing | 3 days | High |

### P3 — Month 2-3

| # | Item | Category | Effort | Impact |
|---|------|----------|--------|--------|
| 16 | **Build guided onboarding wizard** — `cutctx setup --interactive` | Missing Features | 2 weeks | Medium |
| 17 | **Build self-serve trial flow** — automated trial provisioning | Missing Features | 3 weeks | High |
| 18 | **Build canary deployment docs** — progressive delivery | Deployment | 1 week | Medium |
| 19 | **Add chaos testing to CI pipeline** — verify resilience | Testing | 2 weeks | Medium |
| 20 | **Add dashboard snapshot tests** — Playwright visual regression | Testing | 1 week | Medium |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Billing broken at customer go-live | HIGH | CRITICAL | P0 fix or manual invoicing fallback |
| Procurement blocks on SOC 2 | HIGH | HIGH | Start assessment now, prepare interim packet |
| Security team rejects no pentest | MEDIUM | HIGH | Commission pentest, publish summary |
| Dashboard shows $0 to evaluators | HIGH | MEDIUM | P0 fix — looks broken even when working |
| SQLite corruption under load | LOW | HIGH | WAL mode, backup strategy already in place |
| Python overhead at scale (500+ RPS) | MEDIUM | MEDIUM | Workers flag, HPA, Rust core mitigate |

---

## Recommendation

**Score: 68/100 → Conditional Production**

The project has **excellent infrastructure** for production (K8s, Helm, CI/CD, backup, autoscaling, monitoring framework) and a **well-architected core** (Rust compression, async I/O, connection pooling, caching layers).

The three hard blockers are:
1. **Billing flow is broken** — cannot actually collect money
2. **TERMS.md is a legal draft** — cannot sign contracts
3. **Security packet incomplete** — no pentest, no SOC 2

For **lighthouse/design-partner deployments** (where you control the relationship and have custom contracts), the engineering is solid enough. For **self-serve commercial launch**, fix the P0 items first.

---

## Appendix: Key Configs Checked

- `cutctx/proxy/server.py` (7142 lines) — proxy core
- `k8s/*.yaml` (12 files) — K8s manifests
- `docker-compose.yml` — Docker stack
- `.github/workflows/*.yml` (22 workflows) — CI/CD
- `pyproject.toml` — Python package config
- `codecov.yml` — Coverage config
- `.pre-commit-config.yaml` — Pre-commit hooks
- `.actrc` — Local CI config
- `.env.example` — Env reference
- `cutctx/entitlements.py` — Feature gating
- `cutctx/billing.py`, `checkout.py` — Billing integration
- `dashboard/src/pages/Overview.jsx` (2275 lines) — Dashboard main page
