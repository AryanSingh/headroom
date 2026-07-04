# Production Readiness Assessment — 2026-07-04

**Project:** cutctx (headroom) · **HEAD:** `8106b218` · **Version:** 0.29.0 (pyproject: 0.30.0)
**Method:** 6 parallel specialist lanes (features, security, performance, deployment, testing, monitoring) + live proxy probes + full test suite.

---

## Overall Score: **63 / 100**

| Dimension | Score | Verdict |
|---|---|---|
| 1. Missing Features | 72/100 | 5 stub routes, 20+ features default-off, 8 stub-EE module shims |
| 2. Security | 78/100 | 2 HIGH (unauth compress, eval SQLi), no critical vulns |
| 3. Performance | 70/100 | N+1 graph queries, missing indexes, no pricing cache |
| 4. Deployment | 55/100 | **Version drift BLOCKER**, port mismatch, startup safety gaps |
| 5. Testing | 68/100 | 7,763 core pass; but 22/22 EE modules untested (3,939 LOC) |
| 6. Monitoring | 38/100 | **No error tracking**, dead alert rules, tautology health checks |

---

## 1. Missing Features — 72/100

### CRITICAL Stubs & Gaps

| Issue | File | Impact |
|---|---|---|
| **5 EE stub routes return 501** | `routes/memory.py:34-50`, `routes/rbac.py:47-76`, `routes/license.py:42-46`, `routes/sso.py:69-73` | OSS users hit 501 for memory, RBAC, license, SSO operations |
| **License validation hard-coded True** | `cutctx_ee/watermark.py:195` — `# TODO: query actual DB` | **License enforcement is a no-op** — any key is always valid |
| **8 stub-EE modules raise ImportError** | `cutctx/{audit,sso,rbac,billing,seats,entitlements,retention}.py:17-22` | OSS builds cannot import these modules at all |
| **3 EE route surfaces silently 404** | `routes/audit.py:48-49`, `routes/policy.py:47-48`, `routes/spend.py:76-77` | Routes don't mount when EE missing — no 501, no error message |

### HIGH: 20+ Features Disabled By Default

Features that require explicit `CUTCTX_*_ENABLED=1`:
- LLM Firewall (prompt injection, PII, jailbreak detection)
- Multi-Model Ensemble
- Task-Aware Compression
- Semantic Deduplication
- Context Budget
- Cross-Session Profiles
- Cost Forecasting
- Compression Autopilot
- Episodic Memory
- OpenTelemetry Metrics
- Cache Aligner
- Langfuse tracing

The proxy boots in near-pass-through state unless operators explicitly enable each feature.

### MEDIUM: Production TODOs

- `cutctx/transforms/content_router.py:567-580` — placeholder documentation gaps
- `cutctx_ee/memory_service/api.py:102` — "no RBAC and no audit emission" (acknowledged security gap)
- `cutctx/proxy/handlers/openai/chat.py:1026` — realignment TODO

---

## 2. Security — 78/100

### HIGH

| Issue | Detail |
|---|---|
| **Unauthenticated `/v1/compress`** (`admin.py:2392`) | Every other admin route uses `dependencies=[Dep(require_admin_auth)]`. This endpoint is reachable without any auth, RBAC, or entitlement check. DoS vector and billing exposure. |
| **SQL injection in eval harness** (`batch_compression_eval.py:689`) | `f"SELECT * FROM users WHERE id = {user_id}"` — textbook SQLi. Eval harness, not production proxy, but still concerning. |

### MEDIUM

| Issue | Detail |
|---|---|
| **Exception text leaked in 500s** (5 sites) | `chat.py:1185`, `anthropic.py:2162`, `mfa.py:88`, `residency.py:111`, `server.py:2507` — raw `str(e)` returned in HTTP response |
| **Stripe webhook fall-open** (`license_validation.py:192-244`) | Falls open if `STRIPE_WEBHOOK_SECRET` unset and `CUTCTX_BILLING_STRICT_MODE != "1"` |
| **Version header on every response** | `X-Cutctx-Version` enables targeted CVE reconnaissance |

### Low (but worth tracking)

- Machine-bound encryption default (`state_crypto.py:117-128`) — anyone with same machine-id decrypts
- License HMAC skip when unset (`state_crypto.py:280-306`) — returns `True` without checking
- Traceback logging in `logger.error` (not returned, but high-noise if logs shipped)

### Verified Clean

- ✅ No real hardcoded secrets — only placeholder strings
- ✅ CORS — credentials=False when origins=[`*`]
- ✅ SQL injection well-defended (hardcoded column names + parameterized values)
- ✅ Crypto — Fernet AES-128-CBC + HMAC-SHA256, length-prefixed audit chain
- ✅ HMAC audit chain — `hmac.new()` with SHA-256 (fixed)
- ✅ Stats/reset audit — logged as warning, not swallowed (fixed)

---

## 3. Performance — 70/100

### CRITICAL

| Issue | File | Detail |
|---|---|---|
| **N+1 per-entity SELECT in graph BFS** | `memory/adapters/sqlite_graph.py:432-441` | One round-trip per starting entity instead of `WHERE id IN (...)` |
| **N+1 per-relationship Neo4j + 2 embedding calls** | `memory/backends/direct_mem0.py:475-535` | 2N embed API calls + N Cypher round-trips per batch |
| **N+1 BFS relationship lookup per visited node** | `sqlite_graph.py:444-489` | O(visited²) queries for max_hops=2 |

### HIGH

| Issue | File | Detail |
|---|---|---|
| **Missing index: `workspace_id`, `project_id` on memories** | `memory/adapters/sqlite.py:125-167` | Every per-tenant memory query = full table scan |
| **Missing index: `actor`, `action`, `timestamp` on audit** | `cutctx_ee/audit/models.py:16-34` | Audit queries by actor/time = full table scan |
| **No TTL eviction sweep on ccr_entries** | `cache/backends/sqlite.py:41-53` | Dead rows accumulate; no periodic prune |
| **No pricing cache** | `proxy/cost.py:930-966` | `_get_list_price()` called on every stats/overview hit |

### MEDIUM

| Issue | Detail |
|---|---|
| Sync file IO in async request path (debug dumps) | `chat.py:1339`, `anthropic.py:2349` |
| Sync `json.load` in async path during logger warmup | `request_logger.py:233,280` |
| 2-query per audit append (SELECT prior hash + INSERT) | `cutctx_ee/audit/store.py:121-157` |
| Unbounded dict growth in cost tracker | `proxy/cost.py:752-767, 869-888` |

### What's Well-Designed

- ✅ 11 indexes on `memories` table — good coverage for most columns
- ✅ 50 MB body cap with Content-Length precheck + post-decompression verification
- ✅ Bounded `_retrieval_events` (MAX_EVENTS=1000), bounded `search_queries` (cap=10)
- ✅ LRU eviction via min-heap in compression store
- ✅ Session replay bounded (256 sessions × 200 events)
- ✅ Request logger bounded (deque maxlen=10,000)
- ✅ Image base64 redaction before persistence

---

## 4. Deployment — 55/100

### BLOCKER (must fix before ANY deployment)

| Issue | Detail |
|---|---|
| **Version sync failure** | `pyproject.toml` = `0.30.0` but 8 other files (SDKs, plugins, marketplace) are at `0.29.0`. `verify-versions.py` exits 1. Release workflow runs this check and would fail. |
| **K8s/Helm image tags pinned to v0.29.0** | `k8s/deployment.yaml:9,42`, `helm/cutctx/values.yaml:11` all at `0.29.0` while `Chart.yaml:5-6` is `0.30.0`. A fresh `helm install` pulls the prior release. |

### HIGH

| Issue | Detail |
|---|---|
| **Port mismatch: Dockerfile 8787 vs k8s 8080** | Dockerfile default `--port 8787`, but k8s probes hit `8080`. Startup probes never succeed. |
| **Network policy too permissive** | `network-policy.yaml:14-15` allows ingress from ALL namespaces. Should be restricted. |
| **fluent-bit:latest not pinned** | `fluentbit.yaml:19` — violates project's own "no floating tags" rule. |
| **.env.example misleads operators** | 30+ documented env vars are not read by `server.py`. `CUTCTX_UPSTREAM_OPENAI_API_KEY` etc. have zero `os.environ` reads. Users set them, proxy ignores them. |
| **No startup validation for REQUIRED env vars** | Audit key, upstream API keys, admin API key — all claimed "REQUIRED" in `.env.example` but proxy starts without checking any of them. First request fails. |

### MEDIUM

| Issue | Detail |
|---|---|
| `docker-compose.yml` `depends_on` lacks `condition: service_healthy` | Proxy may start before qdrant/neo4j ready |
| Backup CronJob references PVC not shipped | `backup-cronjob.yaml:72` — `claimName: cutctx-data` but no PVC manifest in repo |
| Helm default tag mismatch with chart version | `values.yaml:11` tag `0.29.0` vs `Chart.yaml:5` version `0.30.0` |
| RBAC: ServiceAccount exists but no Role/RoleBinding | Proxy has no in-cluster permissions |

### What's Good

- ✅ 22 CI/CD workflows with parallel shards, caching, matrix builds
- ✅ Release pipeline: tag-driven, 4-platform wheels, PyPI + npm + Docker, SBOM
- ✅ Docker: multi-stage, distroless option, non-root user, healthcheck
- ✅ K8s: full manifest set (HPA, PDB, network policy, Prometheus rules, configmap, secret)
- ✅ Helm chart with security context, probes, autoscaling
- ✅ Version sync script exists and detects drift
- ✅ Rust core fail-loud at startup (exit 78 on missing/stale)

---

## 5. Testing — 68/100

### CRITICAL

| Issue | Detail |
|---|---|
| **22/22 `cutctx_ee` production modules: 0 test references** | 3,939 LOC for billing, license, SSO, SCIM, seats, retention, org, entitlements, policy, ledger, audit — **zero direct unit tests** |

### HIGH

| Issue | Detail |
|---|---|
| **4 `cutctx/security/` modules untested** | `antidebug.py`, `integrity.py`, `firewall_ml.py` (partial), `mfa.py` (partial) |
| **4 `cutctx/transforms/` modules untested** | `anchor_selector.py`, `compact_table.py`, `query_adapter.py`, `selective_filter.py` |
| **7/16 proxy route modules untested** | `audit.py`, `failover.py`, `license.py`, `license_validation.py`, `mfa.py`, `policy.py`, `spend.py` — these are the entitlement/policy enforcement surface |
| **35+ live-API tests silently skipped in CI** | Gated by API key env vars not present in CI — real failure modes never caught |

### MEDIUM

| Issue | Detail |
|---|---|
| **59 `time.sleep()` calls in tests** | No `@pytest.mark.flaky` markers, no retry logic — latent CI flakiness |
| **128 skip markers across 41 test files** | 35+ are env-gated; 6 hard-skipped with no reason given |
| **Mocks dominate: 118/369 test files** | Only 8% of test files are real integration tests |
| **No `@pytest.mark.flaky` / `real_llm` / `live` markers** | No way to quarantine flakes or run live tests on demand |

### LOW

| Issue | Detail |
|---|---|
| `crates/cutctx-py/src/lib.rs` no Rust-side tests for Python bindings | FFI not exercised from Rust side |
| Thin coverage (1 test file each) for 4 security modules, 4 graph modules, 7 memory modules | Surface coverage only |

### What's Strong

- ✅ **7,763 passed, 0 failed, 393 skipped** in core test suite
- ✅ Rust workspace compiles and tests cleanly
- ✅ 3 Playwright e2e tests pass
- ✅ P0 cluster (CCR + content router + capability extensions): 91/91
- ✅ Security cluster (egress enforcer + firewall + residency): 28/28

---

## 6. Monitoring — 38/100

### CRITICAL

| Issue | Detail |
|---|---|
| **No centralized error tracking** | Zero SDKs for Sentry, Datadog, Rollbar, Bugsnag — anywhere in the runtime. Unhandled exceptions visible only in container logs. |
| **Audit-chain failures silently swallowed** | `cutctx_ee/memory_service/api.py:139-142` — bare `except Exception: pass`. No log, no metric, no alert. Compliance evidence silently lost. |
| **Prometheus alert rules reference non-existent metrics** | `prometheus-rules.yaml` uses `http_requests_total` and `http_request_duration_seconds_bucket` — **neither metric is exported by this proxy**. All alerts are dead config. |

### HIGH

| Issue | Detail |
|---|---|
| **`/health` always returns 200** | `server.py:3775,5744` — hard-coded 200 even when `ready: False`. k8s liveness probe never restarts degraded pod. |
| **Health checks are tautologies** | `_health_checks()` checks `object is not None` for cache, http_client, rate_limiter — once set, always True. Deadlocked or corrupted components report "healthy." |
| **No DB / persistence health checks** | No probe for audit.db, rbac.db, or any of the 13+ SQLite stores. Disk-full is invisible until 500s. |
| **Request ID not auto-injected into logs** | Middleware captures it but no `logging.Filter` or `contextvars` wiring. Only ~30 sites manually interpolate it. |

### MEDIUM

| Issue | Detail |
|---|---|
| `logger.error` vs `logger.exception` inconsistency | Only 1 `logger.exception` vs 4 `logger.error` in server.py (3 include `exc_info=True`) |
| OTel health invisible, default-off | No `otel_export_failures_total` metric. Default-off means most deployments silently drop metrics. |
| 18 audit action enums not enforced | 3 call sites use free-form strings not in the enum |
| No audit chain-length growth alarm | No Prometheus gauge for `audit_events_total` |

### LOW

| Issue | Detail |
|---|---|
| Webhook delivery errors not surfaced as metrics | Only logged, no `webhook_delivery_failures_total` counter |
| No operator health view in dashboard | Dashboard shows business metrics only (savings, tokens). No component health, no audit status. |
| `proxy.audit_logger` silently `None` in OSS build | No signal to operator that audit configuration is missing |
| `logger.debug` for required-stage failures | Pipeline failures at `DEBUG` — invisible at default log level |
| Rust core status logged but not alerted | Transitions to `disabled` only visible via manual `/health` curl |

### What's Good

- ✅ `/livez`, `/readyz`, `/health` endpoints exist with per-component checks
- ✅ 29 Prometheus metric families (`cutctx_*` prefixed) exported
- ✅ OTel metrics configured (opt-in, `otlp_http` or console)
- ✅ Request-ID middleware captures ID for every request
- ✅ HMAC-chained audit store with verifiable chain
- ✅ K8s fluentbit.yaml for log shipping (though on `:latest`)

---

## Prioritized Action Plan

### P0 — Blocking (must fix before any production deployment)

| # | Item | Dimension | Effort | Detail |
|---|---|---|---|---|
| 1 | **Fix version drift** — bump 8 files from 0.29.0 to 0.30.0, run `verify-versions.py` | Deployment | 30m | pyproject is 0.30.0; all SDKs, plugins, marketplace at 0.29.0. Release pipeline will reject. |
| 2 | **Fix port mismatch** — align Dockerfile/k8s/helm on one port | Deployment | 30m | Dockerfile 8787 vs k8s 8080. Startup probes fail, pod never ready. |
| 3 | **Wire Sentry or error-aggregator** into proxy lifespan | Monitoring | 1d | Zero error tracking today. Highest-ROI monitoring fix. |
| 4 | **Fix `/health` to return 503 when degraded** | Monitoring | 15m | `server.py:3775,5744` — change hard-coded 200 to 503 when `ready: False`. |
| 5 | **Fix Prometheus alert rules** against real `cutctx_*` metric names | Monitoring | 1d | Current rules reference non-existent metrics. All alerts are dead. |
| 6 | **Fix license validation** — replace `# TODO: query actual DB` | Features | 1d | `watermark.py:195` — license enforcement is a no-op. |

### P1 — Required before public OSS or paid release

| # | Item | Dimension | Effort |
|---|---|---|---|
| 7 | Add auth dependency to `/v1/compress` endpoint | Security | 30m |
| 8 | Add `workspace_id` / `project_id` indexes to memories table | Performance | 30m |
| 9 | Add `actor` / `action` / `timestamp` indexes to audit table | Performance | 30m |
| 10 | Add startup validation for REQUIRED env vars (audit key, admin key, upstream keys) | Deployment | 1d |
| 11 | Fix `except: pass` in audit path → `logger.exception` + metric | Monitoring | 1h |
| 12 | Add TTL eviction sweep for ccr_entries | Performance | 1d |
| 13 | Add basic unit test coverage for top-5 EE modules (SSO, billing, license, retention, audit) | Testing | 1w |
| 14 | Restrict network policy ingress to specific namespace | Deployment | 30m |
| 15 | Pin fluent-bit to specific version in k8s | Deployment | 15m |
| 16 | Add `condition: service_healthy` to docker-compose depends_on | Deployment | 15m |

### P2 — Required before enterprise / SOC 2

| # | Item | Dimension | Effort |
|---|---|---|---|
| 17 | Test coverage for 22/22 EE modules (3,939 LOC) | Testing | 3w |
| 18 | Test coverage for 7 untested proxy routes | Testing | 1w |
| 19 | Add DB health probes to `/health` (audit.db, rbac.db, etc.) | Monitoring | 1d |
| 20 | Fix N+1 graph BFS + Neo4j embedding calls | Performance | 2d |
| 21 | Cache pricing lookups (`functools.lru_cache`) | Performance | 1h |
| 22 | Add operator health view to dashboard | Monitoring | 1w |
| 23 | Wire `request_id` into `logging.Filter` / `contextvars` | Monitoring | 1d |
| 24 | Implement SAML SSO | Security | 1w |
| 25 | Add WebAuthn MFA | Security | 1w |

### P3 — Quality of life (next release)

| # | Item | Dimension |
|---|---|---|
| 26 | Fix exception text leakage in 500 responses | Security |
| 27 | Replace 59 `time.sleep` calls in tests with proper wait/retry | Testing |
| 28 | Remove 6 hard-skipped tests with no reason | Testing |
| 29 | Consolidate `.env.example` to match actual env vars read | Deployment |
| 30 | Fix streaming debug sync file IO in async path | Performance |
| 31 | Add PVC manifest for backup CronJob | Deployment |
| 32 | Add Prometheus gauge for audit chain length | Monitoring |
| 33 | Consolidate 2 license formats (Ed25519 vs ECDSA P-256) | Security |
| 34 | Spend ledger tenant isolation | Security |

---

## Summary by Channel

| Channel | Score | Verdict | P0 items to clear |
|---|---|---|---|
| **Internal dev / staging** | 63/100 | ⚠️ **CONDITIONAL** | Fix port mismatch, version drift, and unauthenticated compress endpoint |
| **Design-partner pilot** | 63/100 | ⚠️ **CONDITIONAL** | Version sync + port mismatch + wire error tracking + fix /health status code |
| **Public OSS release** | 55/100 | ❌ **NO-GO** | All P0 + P1 items (~2 weeks sprint) |
| **Paid enterprise** | 40/100 | ❌ **NO-GO** | All P0/P1/P2 items + SOC 2 audit + pentest + SAML (~3 months) |

**The core product is strong (7,763 passing tests, solid security posture, extensive k8s/CI/CD infrastructure). The gaps are concentrated in monitoring infrastructure (score: 38) and deployment hygiene (score: 55). A focused 2-week sprint on P0+P1 items would lift the score from 63 to ~80.**

---

*Document classification: Production-readiness assessment. Scope: full repository as of `main @ 8106b218`. All findings from live specialist investigation — no code modified.*
