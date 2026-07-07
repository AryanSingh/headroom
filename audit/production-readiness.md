# Cutctx Production Readiness Assessment

**Date:** 2026-07-07
**Version:** 0.30.0 (Development Status: 4 - Beta)
**Repository:** github.com/cutctx/cutctx
**Stack:** Python (FastAPI) + Rust (PyO3 native extensions) + TypeScript (Dashboard/SDK) + K8s/Helm

---

## Readiness Score: **69 / 100**

| Dimension | Score | Status |
|-----------|-------|--------|
| Features & Completeness | 60 | ⚠️ Beta - core works, EE features gated |
| Security | 55 | ⚠️ No SAST/DAST in CI, placeholder TLS, permissive deny.toml |
| Performance & Scalability | 78 | ✅ HPA, async, rate limiting, circuit breakers |
| Deployment & Operability | 72 | ✅ Helm/K8s, zero-downtime, backups. Placeholder DNS/TLS |
| Testing & Quality | 82 | ✅ 7,375 tests, 4-way parallel CI. No coverage gates or security testing |
| Monitoring & Observability | 68 | ⚠️ Prometheus + OTEL present, but basic alerts, no log shipping pipeline |

---

## 1. Missing & Incomplete Features

### What's present
- **Core proxy**: Compression, caching, CCR (reversible compression), cross-agent memory — all functional
- **Compression engines**: SmartCrusher (JSON), CodeCompressor (AST), Kompress (text/HF model), image optimization
- **Auth modes**: PAYG, OAuth, subscription, admin API key
- **Memory**: Graph (Neo4j), Vector (Qdrant, USearch, SQLite-vec), episodic memory
- **MCP server**: `cutctx_compress`, `cutctx_retrieve`, `cutctx_status` tools
- **Dashboard**: Savings overview, governance, operator surfaces
- **SSO/OIDC**: Support in Helm values and config

### What's missing/gated
| Gap | Severity | Notes |
|-----|----------|-------|
| EE modules gated behind proprietary binaries | Medium | Open-core model; compiled `.so` shadow source paths. Documented but confusing |
| Episodic memory disabled by default | Low | `CUTCTX_EPISODIC_MEMORY_ENABLED=0` — intentional opt-in for resource savings |
| Traffic learning disabled by default | Low | `CUTCTX_TRAFFIC_LEARNING_ENABLED=0` |
| MCP read operations disabled by default | Medium | `CUTCTX_MCP_READ=off` — intentional, but discoverability concern |
| No file/artifact compression (v0.x scope gap) | Low | Only messages and tool outputs. Binary file handling not scoped |
| Beta maturity status on PyPI | Medium | `Development Status :: 4 - Beta` — production users may have concerns |

### Action Items
1. **P0**: Document the EE gap clearly in Helm values + operator manual — which features require EE license
2. **P2**: Consider feature flags dashboard for operators to see available vs licensed features
3. **P2**: Add MCP read mode toggle to ConfigMap so operators can enable it declaratively

---

## 2. Security Gaps

### Critical (fix before production)
| Issue | Finding | Location |
|-------|---------|----------|
| 🚫 **No SAST/DAST in CI** | Zero security scanning: no CodeQL, Trivy, Snyk, Semgrep, Gitleaks, or any vulnerability scanner in CI pipelines | `.github/workflows/ci.yml`, `.github/workflows/docker.yml` |
| 🚫 **Permissive deny.toml** | `multiple-versions = "allow"`, `wildcards = "allow"`. Self-documented as "intentionally permissive during Phase 0 — tighten before Phase 2" | `deny.toml:31-32` |
| 🚫 **Placeholder TLS in production Ingress** | `cutctx.example.com` domain, `secretName: cutctx-tls` with no cert-manager annotation. Shipping this without real DNS/TLS would serve HTTP | `k8s/ingress.yaml` |
| 🚫 **ServiceAccount has no RBAC** | Empty `ServiceAccount` — no ClusterRole/RoleBinding. Runs with default namespace permissions | `k8s/rbac.yaml` |

### High (fix before GA launch)
| Issue | Finding | Location |
|-------|---------|----------|
| ⚠️ **Fluent-bit pinned to `:latest`** | No version pin on log shipper DaemonSet | `k8s/fluentbit.yaml:19` |
| ⚠️ **Dependabot limited to 5 security PRs** | Only opens 5 concurrent PRs for pip; other ecosystems are weekly | `.github/dependabot.yml:37` |
| ⚠️ **No dependency vulnerability audit in CI** | No `cargo audit`, `pip-audit`, or `osv-scanner` in CI pipeline | `.github/workflows/ci.yml` |
| ⚠️ **No Secret scanning in CI** | GitGuardian config exists but only allowlists known fixtures — not wired into CI | `.gitguardian.yaml` |
| ⚠️ **Neo4j default credentials** | `NEO4J_AUTH=neo4j/REPLACE_WITH_STRONG_PASSWORD` in docker-compose (dev only) | `docker-compose.yml:42` |

### Medium
| Issue | Finding | Location |
|-------|---------|----------|
| Telemetry beacon has hardcoded Supabase credentials | Public anon key (INSERT-only RLS), but still visible in source | `cutctx/telemetry/beacon.py:32-38` |
| No CSP headers configured | No Content-Security-Policy in proxy or dashboard responses | `cutctx/proxy/server.py` |
| No rate limiting by default | `--no-rate-limit` flag disables; but CLI defaults to enabled | `cutctx/cli/proxy.py:1085` |

### Action Items
1. **P0**: Add CodeQL + Trivy to CI workflows (`ci.yml`, `docker.yml`)
2. **P0**: Add `cargo audit` and `pip-audit` / `osv-scanner` steps to CI
3. **P0**: Tighten `deny.toml` — set `multiple-versions = "deny"`, `wildcards = "deny"`, add `[advisories]` with `severity-threshold = "high"`
4. **P1**: Replace placeholder Ingress domain with real DNS + add cert-manager annotation
5. **P1**: Add GitGuardian (or Gitleaks) scanning to CI
6. **P1**: Add proper RBAC ClusterRole + RoleBinding for the ServiceAccount
7. **P1**: Pin Fluent-bit to a specific version
8. **P2**: Add CSP and security headers to proxy middleware
9. **P2**: Consider moving Supabase telemetry URL/key to env vars

---

## 3. Performance & Scalability

### Strengths
| Feature | Details |
|---------|---------|
| ⚡ **Async architecture** | FastAPI + asyncio, non-blocking I/O throughout |
| ⚡ **Rust native extensions** | DiffCompressor, SmartCrusher compiled via PyO3 — ~10-100x faster than pure Python |
| ⚡ **HPA configured** | CPU @ 70% / Memory @ 80% utilization triggers; 2-10 replicas |
| ⚡ **Resource limits set** | Requests: 250m CPU / 256Mi RAM. Limits: 1000m / 512Mi |
| ⚡ **Rate limiting** | Present in proxy handlers with configurable backend |
| ⚡ **Circuit breakers** | Test coverage for circuit breaker behavior |
| ⚡ **Streaming support** | SSE, WebSocket streaming with backpressure handling |
| ⚡ **Semantic cache** | Redis/anthropic cache-backed with TTL and prefix tracking |
| ⚡ **Zero-copy JSON handling** | Rust `serde_json` with `raw_value` feature for byte-for-byte passthrough |

### Concerns
| Issue | Severity | Notes |
|-------|----------|-------|
| ❓ No published load test results | Medium | No K6/artillery/locust results in repo. Unknown p95 latency under 1000+ req/s |
| ❓ SQLite as primary local store | Medium | SQLite concurrent-write bottleneck under high proxy throughput. USearch may help vector queries |
| ❓ LTO build takes 30-50% longer | Low | Accepted tradeoff for wheel size (strip reduces 18→10 MB) |
| ❓ Telemetry in-memory cap at 10k events | Low | Configurable, but under heavy load could lose telemetry data |

### Action Items
1. **P1**: Add load testing infrastructure (K6 scenario in `benchmarks/` or CI)
2. **P1**: Publish reference throughput numbers (req/s, p50/p95/p99 latency) for common compression profiles
3. **P2**: Benchmark SQLite vs PostgreSQL vs Redis for CCR/audit storage at scale
4. **P2**: Validate HPA scaling behavior under burst traffic pattern

---

## 4. Deployment & Operability

### Strengths
| Feature | Details |
|---------|---------|
| ✅ **Multi-stage Docker** | Builder (slim) → Runtime (slim + distroless) targets |
| ✅ **Multiple base image options** | python-slim AND distroless/python3-debian13 |
| ✅ **Zero-downtime deploys** | RollingUpdate with `maxUnavailable: 0`, `maxSurge: 1` |
| ✅ **Startup/liveness/readiness probes** | All three Kubernetes probes configured |
| ✅ **Pod Disruption Budget** | `minAvailable: 1` — survives node drains |
| ✅ **Backup CronJob** | Daily SQLite backups to S3 with 30-day retention |
| ✅ **Security contexts** | `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `capabilities.drop: ALL`, `seccomp: RuntimeDefault` |
| ✅ **Readiness gate** | `/readyz` checks component health before traffic |
| ✅ **Helm chart** | Complete Helm chart with values.yaml, templates |
| ✅ **Release automation** | release-please for automated changelog + version bumps |
| ✅ **Graceful shutdown** | preStop sleep 5s + 60s terminationGracePeriod |
| ✅ **Multi-arch images** | linux/amd64 + linux/arm64 via docker-bake.hcl |

### Gaps
| Issue | Severity | Notes |
|-------|----------|-------|
| ⚠️ **Ingress is a placeholder** | High | `cutctx.example.com` domain, `cutctx-tls` secret doesn't exist, no cert-manager annotation |
| ⚠️ **No migration/rollback procedure documented** | Medium | No documented process for rolling back a bad release |
| ⚠️ **PersistentVolume is 10Gi untyped** | Medium | No storage class specified; may not work on all clusters |
| ⚠️ **No canary deployment strategy** | Low | Only RollingUpdate; no canary/blue-green traffic splitting |
| ⚠️ **Neo4j + Qdrant are hard dependencies** | Medium | docker-compose requires both; downtime of either breaks core features |
| ⚠️ **No PodTopologySpread constraints** | Low | Pods may colocate on same node despite HPA |
| ⚠️ **NetworkPolicy is restrictive but broad** | Medium | Egress allows all `0.0.0.0/0` TCP 443/80 — no provider-specific allowlisting |

### Action Items
1. **P0**: Replace Ingress domain + TLS secret with real values + cert-manager annotation
2. **P0**: Document rollback procedure (helm rollback + DB restore) in operations manual
3. **P1**: Add `storageClassName` to PVC or document required storage class
4. **P1**: Add network policy egress rules specific to LLM providers (api.anthropic.com, api.openai.com, etc.)
5. **P1**: Add PodTopologySpreadConstraints for HA across zones
6. **P2**: Document Neo4j/Qdrant high-availability setup for production
7. **P2**: Consider removing `init-e2e.yml` dependency on external infra for local testing

---

## 5. Testing & Quality

### Strengths
| Metric | Value |
|--------|-------|
| Total test functions | **~7,375** across 422 test files |
| Test types | Unit + integration + e2e (Playwright) + parity + fuzz |
| CI parallelism | 4 shards via pytest-split |
| Pre-commit hooks | ruff (lint+format), mypy, text hygiene, dashboard eslint |
| Branch coverage | Enabled (codecov configured) |
| E2E coverage | Dashboard surfaces, governance, capability toggles, multi-turn real LLM (opt-in) |
| Parity tests | Rust ↔ Python output equivalence (smart_crusher, etc.) |
| Model tests | Memory, pricing, rate limiting, auth, security validation |

### Gaps
| Issue | Severity | Notes |
|-------|----------|-------|
| ⚠️ **No coverage threshold enforced** | High | `codecov.yml` target: `auto` — no minimum %. Coverage can drop without CI failure |
| ⚠️ **No mutation testing** | Medium | No `mutmut` or `cargo-mutants` to detect untested code paths |
| ⚠️ **No SAST/security tests in CI** | High | `test_security_hardening.py`, `test_security_validations.py` exist but aren't security scanning |
| ⚠️ **Some test files have stale/failing audit references** | Medium | `RELEASE_STATUS.md` mentions stale P0 test cluster assertions |

### Action Items
1. **P0**: Set minimum coverage threshold in codecov (`target: 80%` or similar)
2. **P1**: Add mutation testing for critical modules (compression, auth, cache)
3. **P1**: Run `cargo-deny check advisories` in CI with `deny.toml` tightened
4. **P2**: Create a CI gate that requires e2e test pass for dashboard-affecting PRs
5. **P2**: Add `--strict-markers` to pytest config to catch misspelled markers

---

## 6. Monitoring & Observability

### Strengths
| Feature | Details |
|---------|---------|
| ✅ **Prometheus `/metrics` endpoint** | 1,325-line metrics module tracking tokens, latency, savings, overhead, per-transform timing |
| ✅ **OTEL metrics** | Configurable OTLP HTTP export with resource attributes |
| ✅ **Langfuse tracing** | Built-in Langfuse OTLP trace export for LLM observability |
| ✅ **Three health endpoints** | `/livez` (liveness), `/readyz` (readiness), `/health` (aggregate with component status) |
| ✅ **PrometheusRules** | 2 alert rules (HighErrorRate, HighLatency) |
| ✅ **Fluent-bit DaemonSet** | Log collection from container stdout |
| ✅ **Audit logging** | HMAC-chained SQLite evidence ledger (tamper-evident) |
| ✅ **Telemetry** | Privacy-preserving anonymized telemetry with opt-out |
| ✅ **Dashboard** | React dashboard with savings, governance, operator surfaces |

### Gaps
| Issue | Severity | Notes |
|-------|----------|-------|
| ⚠️ **Only 2 Prometheus alert rules** | High | No alerts for: pod crash loop, high memory, certificate expiry, queue build-up, upstream latency degradation |
| ⚠️ **Fluent-bit outputs to stdout only** | High | No log shipping to Elasticsearch, Loki, S3, or any persistent backend |
| ⚠️ **No Grafana dashboards in repo** | Medium | No exported Grafana JSON dashboard for proxy metrics |
| ⚠️ **No structured logging schema** | Medium | Logs are free-text; no JSON schema enforcement for log parsing |
| ⚠️ **DORA tracking is manual** | Medium | DORA.md references exist but no automated deployment frequency/MTTR metrics |
| ⚠️ **No synthetic monitoring** | Medium | No external health check (Pingdom, Checkly, Grafana Cloud) configuration |
| ⚠️ **Telemetry disabled by default in K8s** | Low | `CUTCTX_TELEMETRY_ENABLED: "false"` in ConfigMap — intentional for privacy, but loses usage data |
| ⚠️ **No on-call/runbook documentation** | Medium | `SECURITY.md` has reporting process but no incident response runbook |

### Action Items
1. **P0**: Add Prometheus alert rules for: PodCrashLoop, HighMemoryUsage, CertificateExpiry, Upstream5xxRate
2. **P1**: Add Grafana dashboard JSON to `k8s/grafana-dashboard.json` for quick import
3. **P1**: Configure Fluent-bit to ship logs to Elasticsearch/Loki/S3 (not just stdout)
4. **P1**: Add structured JSON logging (structlog or python-json-logger)
5. **P1**: Add synthetic monitoring probe configuration (HTTP GET /health every 60s from external)
6. **P2**: Create incident response runbook in `docs/operations/incident-response.md`
7. **P2**: Automate DORA metric collection (deployment frequency, change lead time, MTTR, change failure rate)

---

## Prioritized Action Plan

### Must Fix Before Production (P0)
| # | Area | Action | Effort |
|---|------|--------|--------|
| 1 | Security | Add CodeQL + Trivy to CI workflows | 1 day |
| 2 | Security | Add `cargo audit` + `pip-audit` to CI | 0.5 day |
| 3 | Security | Tighten `deny.toml`: multiple-versions deny, wildcards deny, advisory severity threshold | 0.5 day |
| 4 | Security | Replace placeholder Ingress domain + TLS with real values + cert-manager | 0.5 day |
| 5 | Security | Add RBAC (ClusterRole + RoleBinding) for the ServiceAccount | 0.5 day |
| 6 | Testing | Set minimum coverage threshold in codecov (80%) | 0.25 day |
| 7 | Monitoring | Add Prometheus alert rules for crash loops, memory, cert expiry | 0.5 day |
| 8 | Deployment | Document rollback procedure in operations manual | 1 day |
| 9 | Deployment | Add storageClassName to PVC or document requirement | 0.25 day |

### Should Fix Before GA (P1)
| # | Area | Action | Effort |
|---|------|--------|--------|
| 10 | Security | Add GitGuardian/Gitleaks scanning to CI | 0.5 day |
| 11 | Security | Pin Fluent-bit to specific version | 0.25 day |
| 12 | Security | Add CSP + security headers to proxy middleware | 1 day |
| 13 | Performance | Add load testing (K6) and publish reference numbers | 2 days |
| 14 | Deployment | Add provider-specific egress rules to NetworkPolicy | 0.5 day |
| 15 | Deployment | Add PodTopologySpreadConstraints for zone HA | 0.5 day |
| 16 | Testing | Add mutation testing for critical modules | 2 days |
| 17 | Monitoring | Add Grafana dashboard JSON to repo | 1 day |
| 18 | Monitoring | Configure Fluent-bit to ship to persistent log backend | 1 day |
| 19 | Monitoring | Add structured JSON logging | 1 day |
| 20 | Monitoring | Add synthetic monitoring probe config | 0.5 day |

### Nice to Have (P2)
| # | Area | Action | Effort |
|---|------|--------|--------|
| 21 | Features | Add feature flag dashboard for operators | 3 days |
| 22 | Features | Add MCP read mode toggle to ConfigMap | 0.25 day |
| 23 | Security | Move Supabase telemetry URL/key to env vars | 0.25 day |
| 24 | Performance | Benchmark SQLite vs PostgreSQL at scale | 2 days |
| 25 | Deployment | Add canary deployment strategy | 2 days |
| 26 | Testing | Create CI gate for e2e test requirements | 1 day |
| 27 | Monitoring | Create incident response runbook | 1 day |
| 28 | Monitoring | Automate DORA metric collection | 2 days |

---

## Summary

Cutctx is a **well-architected, thoroughly tested, but pre-GA product** with strong engineering foundations. The Rust native extensions, comprehensive K8s manifests, and 7,375-test suite are standout qualities.

The **critical path to production** is primarily **security hardening**: CI has zero security scanning, the dependency configuration is intentionally permissive, and the Ingress/TLS configuration cannot ship as-is. The monitoring stack has good bones (Prometheus + OTEL + health checks) but needs more alert rules and a persistent log pipeline.

**Estimated effort to P0 readiness:** ~5 days of focused work on security + deployment hardening.
**Estimated effort to GA readiness:** ~15-20 additional days across all dimensions.

The codebase quality and engineering rigor are visible — this is a project that's been built with care. The gaps are typical for a pre-GA open-core project, and the fundamentals (test coverage, async architecture, K8s manifests, release automation) are already in better shape than many GA products.
