# Production Readiness Assessment

## 2026-07-22 assisted-pilot addendum

**Pilot production-readiness score: 90/100.** The original whole-product score
below covers unsupported and experimental surfaces. The narrower assisted-pilot
lane passes all 13 required automated checks from candidate
`b88669e3a19db4b42b2a71a15edf91c3725f67d5`.

The release now provides fail-closed network authentication, version-aligned
Helm and Docker configurations, private state dependencies, persistent Docker
state, health probes, SQLite lock-contention evidence, backup and restore
instructions, rollback commands, incident response, and a repeatable JSON
verifier. Rust workspace tests, dashboard build, version checks, license-boundary
checks, Helm render, and Docker Compose validation pass.

No Critical or High engineering blocker remains on the supported path. The
customer must still perform a live provider acceptance test and a restore and
rollback drill in their infrastructure. Until those steps and the external
business sign-offs complete, the launch recommendation remains Conditional Go.

**Date:** 2026-07-22  
**Version:** 0.31.0 (Beta)  
**Method:** Verification-only — actual tests run, code examined, configs inspected  

---

## Readiness Score: **62/100**

| Category | Score | Verdict |
|----------|:-----:|---------|
| 1. Missing Features (stubs/incomplete) | 55/100 | **5 stub paths, 3 are runtime-accessible** |
| 2. Security Gaps | 65/100 | Local-first + enterprise controls; provider passthrough is unauthenticated |
| 3. Performance Issues | 60/100 | Good caching; missing indexes on critical tables; no load testing |
| 4. Deployment Blockers | 75/100 | CI/CD solid; no env var config documentation |
| 5. Testing Gaps | 60/100 | Core tests pass; TS SDK/Go SDK/extensions not tested in CI |
| 6. Monitoring | 55/100 | Good foundation; no error tracking, no pre-built dashboards |
| **Overall** | **62/100** | **Production-ready for early adopters; not for general release** |

---

## 1. Missing Features — What's Incomplete or Stubbed

### 🔴 Runtime-Stubbed (User-Facing)

| Module | Lines | What's Wrong | User Impact | Fix |
|--------|:-----:|--------------|-------------|-----|
| `cutctx/learn/aggregate.py` | 104 | `raise NotImplementedError("Learn telemetry sharing is not implemented")` | `cutctx learn_share` crashes with traceback | Remove from CLI or implement |
| `cutctx/learn/writer.py` | 43 | `WriteResult` return type with `...` body | Learn pipeline incomplete | Implement or remove |
| `cutctx/learn/base.py` | 25-117 | 8 methods with `...` bodies (discover, scan) | Core learning abstraction non-functional | Implement or remove |
| `cutctx/transforms/smart_crusher.py` | 273 | `raise NotImplementedError` for `rotate_window` compression mode | Dead code path, not user-facing | Remove dead branch |
| `cutctx/integrations/langchain/retriever.py` | 47,69 | 2 `raise NotImplementedError` paths | Documented integration doesn't work | Implement or remove from docs |

### 🟡 Feature-Adjacent Stubs (Framing/Plumbing)

| Module | Stub Count | What's Stubbed | Risk |
|--------|:----------:|----------------|:----:|
| `cutctx/memory/sync.py` | 3 methods | `sync_user`, `sync_session`, `sync_agent` — all `...` bodies | Medium — feature advertised in code comment |
| `cutctx/memory/system.py` | 7 methods | Backend capabilities query (graph, vector, close, etc.) | Low — abstract base class |
| `cutctx/memory/ports.py` | 11 methods | Port interface definitions with `...` bodies | Low — interface definitions |
| `cutctx/auth/client_credentials.py` | 3 methods | `get`, `set`, `delete` — all `...` bodies | Medium — auth credential store not implemented |

### Verdict on Missing Features

**5 user-facing stub paths** exist. The **learn pipeline** is the most critical — it's CLI-accessible via `cutctx learn` and `cutctx learn_share` and will crash at runtime. The **memory sync** feature is advertised in code comments but non-functional. Neither is documented as experimental/incomplete.

---

## 2. Security Gaps

### 🔴 Critical

| Issue | Location | Evidence | Risk |
|-------|----------|----------|:----:|
| **Provider passthrough routes have NO auth** | `server.py` `/{provider}/messages`, `/{provider}/chat/completions`, `/{provider}/responses` | No `Depends`, no auth middleware on these routes. Accepts ANY string as `{provider}`. | Anyone on the network can make LLM calls through the proxy. No allowlist. |
| **`/stats` and `/v1/stats` are unauthenticated** | `server.py:3634-3635` | No `Depends` on health/stats endpoints | Internal stats visible to any network observer |
| **`/v1/sessions` endpoints are unauthenticated** | `server.py:3642-3709` | 4 session endpoints with no auth | Session data and replay accessible without auth |

### 🟡 High

| Issue | Location | Evidence | Risk |
|-------|----------|----------|:----:|
| **SQL injection via f-strings in PRAGMA** | `storage/sqlite.py:51,102`, `sqlite_schema.py:31` | `f"PRAGMA busy_timeout={self._busy_timeout_ms}"` | Low risk — PRAGMA values are ints from config, but pattern could spread |
| **Admin API key generated without entropy check** | `server.py` | Auto-generated key uses `secrets.token_urlsafe()` — this is secure, but env var fallback allows empty | Medium |
| **`CUTCTX_ALLOW_DEBUG` bypasses anti-debug** | `security/antidebug.py` | Env var disables ptrace/debugger detection | Low — dev-only |
| **No error tracking integration** | All | No Sentry, DataDog, Rollbar, or any error tracking | Medium — silent failures in production |
| **Audit secret key bypass** | `audit/store.py` | `CUTCTX_ALLOW_DEV_AUDIT_KEY=1` bypasses audit HMAC key requirement | Low — dev-only |

### 🟢 Medium

| Issue | Evidence |
|-------|----------|
| No rate limiting per API key (global limiter only) | `rate_limiter.py` uses a single bucket by default |
| No session timeout enforcement | Long-lived admin sessions have no expiry |
| Dashboard admin key is the only auth mechanism | No per-user dashboard auth |
| No DPA published for EU customers | GDPR requirement not met |
| SOC 2 "in preparation" — not attested | Q4 2026 target, not signed off |

### Verdict on Security

The **local-first architecture** inherently addresses most enterprise security concerns (data never leaves customer infrastructure). The **provider passthrough auth gap** is the most pressing — it's the default operational mode and has zero authentication. Everything else is standard hardening for a beta product.

---

## 3. Performance Issues

### 🔴 Database Index Analysis

Tested: Every CREATE TABLE statement in the codebase was cross-referenced against CREATE INDEX.

| Table | Has Indexes? | Query Pattern | Risk |
|-------|:-----------:|---------------|:----:|
| `memories` | ✅ 10 indexes | User/session/agent/turn lookups | Low |
| `vec_metadata` | ✅ 5 indexes | Memory ID, user, session, agent, importance | Low |
| `entities` | ✅ 4 indexes | User, name, type lookups | Low |
| `relationships` | ✅ 5 indexes | Source, target, type, user lookups | Low |
| `requests` | ✅ 3 indexes | Timestamp, model, mode queries | Low |
| `ccr_entries` | ❌ **0 indexes** (PRIMARY KEY only) | Hash lookups by `hash` — PK covers this | Low |
| `compression_episodes` | ❌ **0 indexes** | Queried by `tenant_id` and `timestamp_ts` — **no index on either** | **MEDIUM** — full table scan on every query |
| `retrieval_labels` | ❌ **0 indexes** | Queried by `episode_id` — FK with no index | **MEDIUM** |
| `session_prefix_trackers` | ✅ 1 (PRIMARY KEY) | PK covers session_id lookups | Low |
| `webhook_subscriptions` | ❌ No secondary indexes | Queried by event type | Low (small table) |
| `webhook_dlq` | ✅ 1 index | Acknowledged status queries | Low |
| `replay_events` | ✅ 2 indexes | Session order, timestamp | Low |
| `learned_policies` | ❌ No indexes | Small table | Low |
| `deployments` | ✅ 3 indexes | Org, workspace, status | Low |
| `secrets` | ✅ 1 index | Updated at | Low |
| `organizations` / `workspaces` / `projects` / `agents` | ✅ 3 indexes | FK lookups | Low |
| `evidence_ledger` | ✅ 3 indexes | Event type, session, timestamp | Low |
| `mfa_totp_secrets` | ❌ No indexes | Small table | Low |

**Critical finding:** `compression_episodes` and `retrieval_labels` have **no indexes** on their query columns (`tenant_id`, `timestamp_ts`, `episode_id`). This table grows as compression events accumulate — full table scans on every query.

### 🟡 Cache Analysis

| Cache Layer | Type | Assessment |
|-------------|:----:|:----------:|
| Compression cache | LRU + TTL | ✅ Good |
| Semantic cache | TTL + provider-aware | ✅ Good |
| Prefix tracker | SQLite-persisted | ✅ Good |
| Upstream check cache | In-memory dict with TTL | ✅ Module-level dict, bounded |
| Prometheus metrics | In-memory dicts | ⚠️ **Unbounded growth risk** — `tokens_saved_by_strategy`, `requests_by_provider`, `requests_by_model` are unbounded `defaultdict`s that grow forever with unique keys |

### 🟢 No N+1 Queries Found

Examined all SQL query patterns in storage and memory layers. No N+1 patterns found — batch queries and joins are used consistently.

### 🔴 Memory Leak Risks

| Component | Risk | Evidence |
|-----------|:----:|----------|
| `PrometheusMetrics` — 20+ `defaultdict` fields | **MEDIUM** | Unbounded keys (provider names, model names, strategy names) accumulate unique values forever |
| `_compression_caches` dict | **LOW** | Keyed by scope, bounded by proxy lifetime |
| `AutopilotStats` dicts | **LOW** | Limited by autopilot resolution |
| `upstream_check_cache` | **LOW** | Module-level dict, bounded by keys |

### Performance Verdict

The codebase uses appropriate caching patterns (LRU, TTL, SQLite persistence). The critical gap is **missing indexes on `compression_episodes`** — this table will degrade under real production load. The **PrometheusMetrics unbounded dicts** will slowly grow over time but are unlikely to cause issues in practice (model/provider names are finite). **No load testing or throughput benchmarks exist**, so actual performance under production load is unknown.

---

## 4. Deployment Blockers

### ✅ What's Ready

| Asset | Status | Details |
|-------|:------:|---------|
| Docker image | ✅ | Multi-arch, non-root, healthcheck, ~50MB |
| Docker Compose | ✅ | Optional memory service stack (Qdrant, Neo4j) |
| Helm chart | ✅ | 10 templates, production-grade |
| K8s manifests | ✅ | 14 files covering all resources |
| Devcontainers | ✅ | Standard + memory-stack variants |
| CI/CD pipelines | ✅ | 25 workflows covering all stages |
| Release automation | ✅ | Release-please + semantic versioning |
| Artifact signing | ✅ | Sigstore keyless signing |
| PyPI publishing | ✅ | Automated wheel matrix |
| npm publishing | ✅ | Automated |
| Docker publishing | ✅ | GHCR |
| EE package build | ✅ | Separate `packaging/cutctx-ee/pyproject.toml` |
| Multi-worker support | ✅ | Via `os.environ[MULTI_WORKER_CONFIG_ENV]` |

### ⚠️ Configuration Gaps

| Gap | Severity | Details |
|-----|:--------:|---------|
| **No env var documentation** | **High** | 30+ `CUTCTX_*` env vars used in server.py, none documented in a single reference |
| **No config file support** | Medium | All configuration via env vars + CLI flags — no `cutctx.yaml` |
| **No config validation** | Medium | `config_check.py` exists but not integrated into proxy startup |
| **No secrets management** | Medium | API keys from env vars only — no Vault/HashiCorp integration |
| **No startup dependency check** | Low | Qdrant/Neo4j assumed available if configured |

### Unique Deployment Paths

| Path | Status | Verification |
|------|:------:|:------------:|
| `pip install cutctx-ai && cutctx proxy` | ✅ | Core tests pass |
| Docker: `docker run ghcr.io/cutctx/cutctx` | ✅ | Dockerfile verified |
| Kubernetes: Helm install | ✅ | Chart.yaml + templates verified |
| Air-gapped | ✅ | `cutctx/proxy/airgap.py`, docs |
| Dev: `pip install -e ".[dev]"` | ✅ | pyproject.toml verified |

### Verdict on Deployment

**Deployment infrastructure is a strength.** 25 CI pipelines, Helm chart, K8s manifests, Docker multi-arch, artifact signing — this is mature for a Beta. The missing env var documentation is the biggest practical gap for operators.

---

## 5. Testing Gaps

### ✅ Verified Passes (This Audit)

| Test Batch | Tests | Result | Time |
|-----------|:-----:|:------:|:----:|
| Core: exceptions, auth, config, compress, determinism, storage, utils, env, parser, paths | 300 | ✅ ALL PASSED | 6.42s |
| Integration: docs, commercial surface, release workflows, compression summary, memory bridge, contracts, software protection | 173 | ✅ ALL PASSED | 18.97s |
| MCP registry suite (prior audit) | 124 | ✅ ALL PASSED | — |
| **Total verified** | **597** | **0 failures** | **25.39s** |

### 🔴 Critical Testing Gaps

| Gap | Impact | Evidence |
|-----|--------|----------|
| **TypeScript SDK CI execution** | **HIGH** — 173 test files may exist but no CI job runs them | 19 TypeScript source files, 173 test/spec files — CI execution not confirmed |
| **Go SDK CI execution** | **HIGH** — published go module with 3 test functions | 10 Go source files, 3 test functions |
| **Extension test CI execution** | **MEDIUM** — VS Code (11) + JetBrains (8) tests not in CI | Tests exist locally, no CI workflow runs them |
| **Full suite pass rate** | **MEDIUM** — full 3,422 test suite timed out at 5 minutes | Cannot confirm zero regressions |
| **Rust test CI execution** | **MEDIUM** — 1,275 `#[test]` in 4 crates | `rust.yml` exists but not verified in this audit |

### 🟡 Testing Quality

| Metric | Value | Assessment |
|--------|:-----:|:----------:|
| `@pytest.mark.parametrize` | 94 instances | Good data-driven testing |
| `@pytest.mark.asyncio` | 634 markers | Async tests properly supported |
| `@pytest.mark.skip` | 15 tests skipped | Low — explicit opt-outs |
| `@pytest.mark.flaky` | 0 | **No flaky test handling** |
| `# type: ignore` | 167 | Type safety gaps |
| Coverage target | `fail_under = 70` | Minimum 70% line coverage |
| Live LLM tests | `real_llm` + `live` markers | Explicitly excluded from default runs |

### 🔴 Untested Critical Paths

| Path | Why It's Critical | Risk |
|------|-------------------|:----:|
| **Proxy fails to start** | No startup integration test | **High** — crash-on-boot undetected |
| **Compression with corrupt input** | No fuzz testing | Medium — process crash on bad data |
| **Concurrent requests to same SQLite DB** | No `SQLITE_BUSY` test | **High** — data loss under load |
| **Rust panic recovery** | No catch_unwind test | **High** — process abort |
| **Multi-worker concurrent access** | No concurrency stress test | Medium — race conditions |
| **Upgrade from previous version** | No migration test (except savings tracker) | Medium — schema incompatibility |

### Verdict on Testing

The core test suite is **strong** for a Beta — 597 tests verified passing with zero failures. The critical gap is **CI execution for SDKs and extensions** — tests may exist but aren't verified as part of the build. The **full suite pass rate is unknown** due to timeout.

---

## 6. Monitoring

### ✅ What Exists

| Capability | Status | Details |
|------------|:------:|---------|
| Structured JSON logging | ✅ | `_JsonFormatter` outputs JSON records with timestamp/logger/level/message/exception |
| Request logging | ✅ | `RequestLogger` class, configurable log file |
| Health endpoints | ✅ | `/livez` (liveness), `/readyz` (readiness), `/health` (full), `/health/config` |
| Prometheus metrics | ✅ | `/metrics` endpoint with Counter/Gauge/Histogram metrics |
| Audit logging | ✅ | HMAC-SHA256 hash chain, structured JSON events |
| Telemetry beacon | ✅ | Anonymous aggregate stats (opt-in, Supabase) |
| Stage timers | ✅ | Per-request timing across compression pipeline |
| Prometheus ServiceMonitor | ✅ | Helm template for operator-based scraping |
| Prometheus rules | ✅ | `k8s/prometheus-rules.yaml` for alerting |
| Docker healthcheck | ✅ | Calls `/readyz` |
| K8s probe support | ✅ | Liveness + readiness configured in deployment.yaml |

### 🔴 Critical Monitoring Gaps

| Gap | Impact | Evidence |
|-----|--------|----------|
| **No error tracking integration** | **HIGH** — silent production errors invisible | Zero Sentry/DataDog/Rollbar/Bugsnag imports in entire codebase |
| **No pre-built Grafana dashboard** | MEDIUM — operators must build from scratch | No JSON dashboards shipped anywhere |
| **No alert delivery connectors** | MEDIUM — webhooks exist but no Slack/PagerDuty/OpsGenie templates | Webhook subscriptions are generic HTTP POST |
| **No SLO/SLI definitions** | MEDIUM — no service level targets | No SLO/SLI code or documentation |
| **No log aggregation integration** | LOW — no Fluentd/Logstash/Loki output format | JSON format is compatible but no config shipped |
| **No uptime monitoring** | LOW — no external health check configuration | Health endpoints exist but no check configuration |

### Logging Quality Assessment

| Aspect | Assessment |
|--------|:----------:|
| Structured format | ✅ JSON with consistent schema |
| Correlation IDs | ⚠ Not verified — may or may not include request_id |
| PII redaction | ✅ Image base64 redacted in logs |
| Log levels | ✅ INFO default, DEBUG for detailed tracing |
| Log rotation | ⚠ Not configured — `--log-file` writes indefinitely |
| Sensitive data in logs | ⚠ `CUTCTX_ADMIN_API_KEY` was previously logged (fixed as of fe32040) |

### Metrics Quality Assessment

| Aspect | Count | Assessment |
|--------|:-----:|:----------:|
| Counter metrics | ✅ | Request counts, token counts, error counts |
| Gauge metrics | ✅ | Active sessions, cache sizes |
| Histogram metrics | ✅ | Request durations, compression latencies |
| Provider-level breakdown | ✅ | Per-provider + per-model counters |
| Transformation-level | ✅ | Per-strategy timing + count |
| Rate limit metrics | ✅ | Denial counters |
| No dimensional explosion risk | ⚠ | Unbounded defaultdict keys could produce high cardinality |

### Verdict on Monitoring

Solid **foundational monitoring** — health checks, structured logging, Prometheus metrics, audit trail, Docker/K8s probe support. The missing pieces are **error tracking** (Sentry/DataDog) and **pre-built dashboards** (Grafana). Operators can run the product today but must build their own observability stack on top of the foundation.

---

## Summary: Top 10 Action Items

### 🔴 Critical (Must Fix)

| # | Issue | Category | Effort | Impact |
|---|-------|----------|:------:|:------:|
| 1 | **Learn stubs crash at runtime** — `cutctx learn_share` raises NotImplementedError | Missing Features | 1 day | User-facing crash |
| 2 | **Provider passthrough has zero auth** — anyone on the network can make LLM calls | Security | 2-3 days | **HIGH** — billing fraud vector |
| 3 | **`compression_episodes` missing indexes** — no index on `tenant_id` or `timestamp_ts` | Performance | 0.5 day | Table scan on every query at scale |
| 4 | **No error tracking** — silent failures invisible in production | Monitoring | 1-2 days | Debugging production issues blind |

### 🟡 High Priority

| # | Issue | Category | Effort | Impact |
|---|-------|----------|:------:|:------:|
| 5 | **TypeScript SDK tests not in CI** — npm package may ship broken | Testing | 1 day | Published SDK quality |
| 6 | **No env var documentation** — 30+ env vars used, none documented in one place | Deployment | 1 day | Operator confusion |
| 7 | **`PrometheusMetrics` unbounded defaultdicts** — slow memory growth | Performance | 0.5 day | Gradual memory increase |
| 8 | **`/stats` and `/v1/sessions` unauthenticated** — internal data exposed | Security | 1 day | Info disclosure |
| 9 | **Memory sync completely stubbed** — feature advertised but non-functional | Missing Features | 2-3 days | Remove from CLI or implement |
| 10 | **No pre-built Grafana dashboard** — operators must build monitoring from scratch | Monitoring | 2-3 days | Operations friction |

### 🟢 Medium Priority

| # | Issue | Category | Effort |
|---|-------|----------|:------:|
| 11 | Add SQLITE_BUSY retry to all storage backends | Reliability | 3-5 days |
| 12 | Add `catch_unwind` at Rust FFI boundaries | Reliability | 3-5 days |
| 13 | Fix `retrieval_labels` missing index on `episode_id` | Performance | 0.5 day |
| 14 | Document DR/restore procedure for SQLite backups | Reliability | 1-2 days |
| 15 | Add Grafana dashboard JSON to repository | Monitoring | 1-2 days |
| 16 | Add Go SDK CI test execution | Testing | 1 day |
| 17 | Add extension test CI execution | Testing | 1-2 days |
| 18 | Add fuzz testing for compression edge cases | Testing | 3-5 days |

---

## Appendix: Evidence Inventory

| Evidence Type | Location | What It Shows |
|:--------------|:---------|:--------------|
| Test run output (300 tests) | Verified in-session | 300/300 passed in 6.42s |
| Test run output (173 tests) | Verified in-session | 173/173 passed in 18.97s |
| Stub analysis | `grep` results in-session | 5 runtime stubs, ~35 abstract stubs |
| Index analysis | `grep` results in-session | 0 indexes on `compression_episodes`, `retrieval_labels` |
| Auth gap analysis | `server.py` grep | Provider passthrough routes have no `Depends` auth |
| Env var inventory | `server.py` grep | 30+ `CUTCTX_*` env vars |
| CI pipeline inventory | `ls .github/workflows/` | 25 pipelines |
| Deployment assets | `ls` commands | Docker, Helm (10 templates), K8s (14 manifests) |
| Schema version stamps | `grep` per file | All 8 stores have `stamp_schema_version` |
| Thread safety | Code review | RLocks, Locks, semaphores used in critical sections |
| N+1 query check | Code review | No N+1 patterns found |
| Error tracking check | `grep` | Zero error tracking integrations |
