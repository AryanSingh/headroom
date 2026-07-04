# Cutctx Production Readiness Assessment

**Project:** cutctx (headroom) v0.30.0
**Date:** 2026-07-04
**Scope:** 6-dimension audit across ~504K LOC (Python + Rust + TS)

---

## Readiness Score: **58/100**

| Dimension | Weight | Score | Weighted |
|---|---|---|---|
| Security | 25% | 65 | 16.3 |
| Monitoring & Observability | 20% | 45 | 9.0 |
| Deployment & Operations | 20% | 45 | 9.0 |
| Performance & Scalability | 15% | 70 | 10.5 |
| Testing | 10% | 80 | 8.0 |
| Missing Features & Completeness | 10% | 85 | 8.5 |
| **Total** | **100%** | — | **61.3 → 58** |

**Rating: CONDITIONAL — production-capable with mandatory remediation before broad deployment.**

The project has exceptional engineering depth (8K+ tests, 50+ Prometheus metrics, layered RBAC,
Fernet encryption, multi-stage Docker build, Helm chart, 20 CI workflows, release-please automation)
but is held back by **2 security vulnerabilities**, **4+ K8s deployment blockers**, **zero structured
logging**, **zero error tracking**, and **virtually no Prometheus alerts on its own metrics**.

---

## Dimension 1: Security (65/100)

### Critical — fix before any network-exposed deployment

| ID | Issue | Location | Fix |
|---|---|---|---|
| **S-1** | **Unauthenticated `/v1/compress` and `/v1/retrieve*`** — no API key, no admin auth, no RBAC. Any process that can reach the proxy can trigger LLM calls (denial of wallet) and read cached compression content. | `cutctx/proxy/routes/admin.py:1955, 2010, 2036, 2254, 2301, 2392` + `server.py:5801-5890` | Add `Depends(require_admin_auth)` or `Depends(require_loopback)` |
| **S-2** | **Path traversal in `/assets/{filename}`** — no `.resolve()` check. Attacker can read arbitrary files via `../` sequences. | `cutctx/proxy/server.py:2162-2167, 5927-5930` | Sanitize with `Path(filename).name` or `is_relative_to()` |

### High

| ID | Issue | Location | Fix |
|---|---|---|---|
| **S-3** | **TLS not enforced on non-loopback** — binding to `0.0.0.0` without TLS serves plaintext over network. | `cutctx/proxy/models.py:115`, `server.py:6203-6205` | Refuse start or warn prominently when host≠loopback and no TLS |
| **S-4** | **LLM Firewall disabled by default** — PII/prompt-injection/jailbreak scanners ship but are opt-in. | `cutctx/security/firewall.py:62` | Flip `enabled` default to `True` |
| **S-5** | **Permissive `deny.toml`** — `wildcards = "allow"`, `multiple-versions = "allow"`. Phase 0 tech debt. | `deny.toml:26-28` | Tighten before production |

### Medium

- **S-6**: Rate limits absent on admin endpoints — no defense against credential-stuffing on admin API key
- **S-7**: Webhook `secret` min_length=8 — below NIST recommendation of 32
- **S-8**: No CI lint rule against f-string SQL (all current uses are safe via allowlists, but no regression guard)

### Strengths
- `hmac.compare_digest` everywhere — no timing-attack vectors
- Auto-generated admin key correctly logged to stderr only (not Python logger)
- Layered auth: `admin_auth + rbac_permission + entitlement` on every sensitive route
- Fernet-encrypted secrets at rest, machine-bound state encryption
- Loopback guard with dual IP+Host check mitigates DNS rebinding
- No `eval()`, `exec()`, `pickle`, `yaml.load`, `shell=True`, `verify=False` in any code path

---

## Dimension 2: Monitoring & Observability (45/100)

### Critical — zero observability for ops

| ID | Issue | Location | Fix |
|---|---|---|---|
| **M-1** | **No structured (JSON) logging** — plain-text `%(asctime)s - %(name)s - %(levelname)s - %(message)s` format. ELK/Loki/Splunk ingestion requires fragile grok parsers. | `cutctx/proxy/helpers.py:961-999`, `server.py:6211` | Add `python-json-logger` or `structlog`; make default output JSON |
| **M-2** | **No error tracking** — no Sentry, GlitchTip, or equivalent. Unhandled exceptions use FastAPI's dev-style 500 with no stable error ID. | `cutctx/proxy/server.py:2503-2548` (HTTPException + JSONDecodeError handlers only) | Add Sentry SDK + global `@app.exception_handler(Exception)` |
| **M-3** | **Prometheus alerts query wrong metrics** — both existing alerts (HighErrorRate, HighLatency) use generic `http_requests_total` / `http_request_duration_seconds_bucket` (default uvicorn). **No alert fires on `cutctx_requests_failed_total`, `cutctx_compression_failures`, `cutctx_cache_bust_*`, or `cutctx_subscription_*`.** | `k8s/prometheus-rules.yaml` (19 lines, 2 alerts) | Rewrite to alert on cutctx-specific metrics; add alerts for compression failures, budget threshold, cache-bust rate, license expiry, audit chain break |
| **M-4** | **Log aggregation is placeholder** — FluentBit DaemonSet tails container logs but outputs to **stdout only** (no Loki/Elasticsearch/Splunk output plugin configured). | `k8s/fluentbit.yaml:42-50` | Add actual output plugin or remove as misleading |
| **M-5** | **`log_level` hardcoded to `"warning"` in uvicorn** — operators cannot enable debug logs without source change. `CUTCTX_LOG_LEVEL` is documented in `.env.example` but not read by `server.py`. | `cutctx/proxy/server.py:6211` | Wire `CUTCTX_LOG_LEVEL` → `uvicorn.run(log_level=...)` |

### High

| ID | Issue | Location |
|---|---|---|
| **M-6** | **Tracing covers compression pipeline only** — no FastAPI/Starlette auto-instrumentation, no httpx auto-inst, no SQLite auto-inst. Cache hit/miss, downstream provider latency, total request lifecycle are blind spots. | `cutctx/observability/tracing.py:133-192` — only 2 `start_as_current_span` call sites |
| **M-7** | **Audit chain `verify_chain()` never called** — HMAC-SHA256 tamper-evident chain exists in EE but no scheduled job calls `verify()` and no Prometheus gauge exposes chain validity. | `cutctx_ee/audit/store.py` (verify exists, not scheduled) |

### Strengths
- 50+ Prometheus metrics across request volume, token economics, latency, cache, per-transform timing, WS sessions, waste signals
- OpenTelemetry metrics with 16 instruments and configurable OTLP exporter
- Health endpoints correctly layered: `/livez` (process), `/readyz` (upstream connectivity + deps), `/health` (info)
- Cost tracking with budget enforcement and webhook event types
- React dashboard with 9 pages mounted at `/dashboard`
- EE audit log with HMAC-SHA256 hash chain, WAL mode, secret key enforcement

---

## Dimension 3: Deployment & Operations (45/100)

### Blocker — will crash or lose data

| ID | Issue | Location | Fix |
|---|---|---|---|
| **D-1** | **K8s uses non-existent CLI flags** — `--compression` / `--compression-mode` don't exist. `--mode live-zone` is invalid. **Pod crashes on startup.** | `k8s/deployment.yaml:57-64`, `configmap.yaml:11-12`, `helm/values.yaml:21-23` | Replace with `CUTCTX_MODE=token` / `CUTCTX_OPTIMIZE=1` |
| **D-2** | **PVC name mismatch** — PVC named `cutctx-pvc`, backup CronJob mounts `cutctx-data`. Backup never runs. | `k8s/pvc.yaml:4` vs `backup-cronjob.yaml:71` | Align names |
| **D-3** | **No volumeMount in deployment** — SQLite databases written to ephemeral pod FS. **All state lost on restart.** | `k8s/deployment.yaml:42-104` | Add `volumeMount` for `/home/nonroot/.cutctx` + set `CUTCTX_*_DB_PATH` env vars |
| **D-4** | **K8s NetworkPolicy port mismatch** — deployment on 8080, network-policy allows 8787. Traffic blocked. | `k8s/network-policy.yaml:20` vs `deployment.yaml:50` | Align port across all manifests |
| **D-5** | **Audit chain HMAC broken** — Python source fix exists but Cython-compiled `.so` shadows the source. Tests fail on HMAC contract. | `audit/audit-chain-hmac-cython-rebuild-required-2026-07-02.md` | Rebuild EE Cython module |

### High

| ID | Issue | Fix |
|---|---|---|
| **D-6** | Helm chart missing `persistence:` block — out-of-box `helm install` creates no PVC | Add defaults to `values.yaml` |
| **D-7** | Image tag stale at `0.29.0` vs project `0.30.0` in both K8s and Helm | Bump to `0.30.0` |
| **D-8** | Telemetry env var name mismatch: `.env.example` documents `CUTCTX_TELEMETRY_ENABLED`, code reads `CUTCTX_TELEMETRY` | Fix `.env.example` or add alias |
| **D-9** | `CUTCTX_UPSTREAM_API_KEY` in K8s secret doesn't exist — real vars are `CUTCTX_UPSTREAM_OPENAI_API_KEY` etc. | Fix secret template |
| **D-10** | Auto-generated admin key lost on process restart — no startup check in production mode | Add env-var-required check |
| **D-11** | Docker image not pinned by digest | Add `@sha256:` pinning |
| **D-12** | Chaos testing workflow uses wrong service name and label selector | Fix to `cutctx-proxy:80` + `app.kubernetes.io/name=cutctx-proxy` |

### Medium

- **D-13**: SQL migration files (`sql/`) unused — no migration runner, no schema version tracking
- **D-14**: No K8s manifest validation in CI (`helm template | kubectl apply --dry-run`)
- **D-15**: Multiple workers with in-memory CCR causes silent correctness bug (warned but not gated)

### Strengths
- Multi-stage Dockerfile with distroless Python 3.13 image (~100MB+)
- Non-root user in production stage
- Cosign keyless signing for Docker images
- Release-please automation for version bumps
- HPA, PDB, NetworkPolicy, RBAC, resource limits all present in K8s
- Liveness + readiness + startup probes configured
- uv.lock + Cargo.lock committed for reproducible builds
- CycloneDX SBOM generated on publish

---

## Dimension 4: Performance & Scalability (70/100)

### High

| ID | Issue | Location | Fix |
|---|---|---|---|
| **P-1** | **4 N+1 patterns in memory backends** — per-entity async DB lookups in `save_memory()` and `search_memories()`. | `cutctx/memory/backends/local.py:315-352, 422-446` | Batch into single `WHERE name IN (?,?,…)` + `executemany` |
| **P-2** | **Cache not applied to 3 handlers** — OpenAI Responses API, Gemini, and passthrough mode miss `self.cache.get/set`. | `handlers/openai/responses.py`, `handlers/gemini.py`, `handlers/openai/passthrough.py` | Wire same pattern as `chat.py:313, 1435` |
| **P-3** | **`_stable_hashes` and `_first_seen` unbounded** — set/dict grows forever across process lifetime. 500 sessions × 10k entries = 5M hashes leaked. | `cutctx/cache/compression_cache.py:110-111` | Cap at 2× `max_entries` |
| **P-4** | **No WAL mode on 3 memory backends** — single-writer serialization kills concurrent throughput. | `sqlite.py:116`, `sqlite_vector.py:237`, `sqlite_graph.py:80` | Add `PRAGMA journal_mode=WAL` |
| **P-5** | **O(n) full-cache scan on every retrieve** — `items()` materializes every BLOB to find a hash match. | `server.py:5832-5845` | Replace with hash-bucketed lookup |

### Medium

- **P-6**: Missing indexes on `retrieval_labels(episode_id, tenant_id)` and `webhook_subscriptions(created_at_ts, enabled)`
- **P-7**: `SemanticCache` dead code on proxy — defined, exported, but no handler imports it
- **P-8**: `ToolMemoizer._caches` / `_stats` unbounded by session count (session keys grow without cap)
- **P-9**: `asyncio.Lock` in `embedders.py` may be called from non-event-loop threads
- **P-10**: `HF_HUB_OFFLINE` not enforced by default — sentence-transformers makes network calls on first model load

### Strengths
- HTTP/2 + connection pooling (`httpx.Limits`) configured
- Dedicated `ThreadPoolExecutor` for compression, sized `min(32, cpu_count*4)`
- All CPU-bound work uses `asyncio.to_thread` or `run_in_executor`
- No `requests` library in proxy hot path (all `httpx.AsyncClient`)
- No Pydantic on hot paths — `@dataclass` + `dict[str, Any]`
- `OrderedDict` + `popitem(last=False)` for O(1) LRU eviction
- Body size cap (1MB) before JSON parse
- Eager warmup of compressors at startup avoids first-request latency spikes
- No eager `torch`/`onnxruntime`/`transformers` at module import

---

## Dimension 5: Testing (80/100)

### High

| ID | Issue | Fix |
|---|---|---|
| **T-1** | **`.coverage` is stale/empty** — only 2 files in the SQLite `file` table, 69 KB (a proper run should be multi-MB). No actionable coverage data. | Re-run clean coverage profile; verify Codecov upload step |
| **T-2** | **Real LLM markers not applied** — `@pytest.mark.real_llm` and `@pytest.mark.live` are defined in `pyproject.toml` but **0 test files use them**. 5 files hit real Anthropic/OpenAI APIs silently. | Add markers + default `-m "not real_llm"` |
| **T-3** | **33 test files with `sleep()`** — real race-condition dependence. No `pytest-rerunfailures` installed. One `httpx.ReadTimeout → skip` hook masks the issue. | Add `pytest-rerunfailures` with `--reruns 2` |
| **T-4** | **No K8s manifest tests** — 15 yaml files, 1 Helm chart, 0 tests. `helm template | kubectl apply --dry-run` not in CI. | Add `tests/test_k8s_manifests.py` |
| **T-5** | **No SQL migration tests** — 5 migration files, 0 tests. Schema drift between code and Supabase is not detected. | Add migration test against fresh DB |
| **T-6** | **Fuzz targets exist but no CI workflow** — 3 targets (`fuzz_smart_crusher`, `fuzz_diff_compressor`, `fuzz_live_zone_anthropic`), 0 CI runs. No seed corpus. | Add `fuzz-smoke` workflow (60s per target) |

### Medium

- **T-7**: `test_gemini*.py` does not exist — only provider without dedicated top-level test
- **T-8**: `test_provider_claude.py` is 327 bytes, `test_provider_gemini_runtime.py` is 1,135 bytes — vestigial
- **T-9**: No Rust coverage measurement — `cargo-llvm-cov` not configured
- **T-10**: Dashboard Playwright runs **chromium only** — no Firefox/WebKit/mobile viewports
- **T-11**: Single Python version in CI (3.12) — 3.10/3.11/3.13 deferred
- **T-12**: No property-based or mutation testing

### Strengths
- **8,137 Python test functions** across 487 files — exceptional breadth
- **1,401 Rust `#[test]` annotations** — solid native coverage
- Mature test infrastructure: per-test isolated DB, auto-admin auth patching, log-propagation reset
- 47 top-level `test_proxy*` files + 7-file `test_proxy/` sub-directory
- Substantial security tests: firewall (17 KB), egress enforcer (13 KB), MFA TOTP (10 KB), secrets store (7.6 KB)
- 4-way `pytest-split` parallelism in CI with 30-min per-shard budget
- 7 Playwright E2E specs for the dashboard
- Parity tests between Python and Rust output

---

## Dimension 6: Missing Features & Completeness (85/100)

### Notable Gaps

| ID | Issue | Severity |
|---|---|---|
| **F-1** | **3,213+ lines of "intelligence layer" code dead by default** — 6 feature flags (`CUTCTX_TASK_AWARE_ENABLED`, `CUTCTX_DEDUP_ENABLED`, `CUTCTX_CONTEXT_BUDGET_ENABLED`, etc.) all default to `=0`. No CLI flags, no startup banner, no dashboard surface. | Medium |
| **F-2** | **EE-gated 501 endpoints** — `/v1/memory/*`, `/v1/rbac/*`, `/v1/sso/*`, `/v1/license/*`, `/v1/billing/*` return 501 when EE module is absent. Intentional OSS/EE split, but 6 endpoints with no fallback. | Low (intentional) |
| **F-3** | **Docs-vs-code drift** — IntelligentContextManager documented as active but code removed; LLMLingua extra described as removed in 0.9.x but still defined; AES-256 claim in SOC2 roadmap but code uses Fernet (AES-128-CBC); SAML SSO documented on roadmap but not implemented. | Medium |
| **F-4** | **Rust parity comparators 3/N are stubs** — `LogCompressorComparator`, `CacheAlignerComparator`, `CcrComparator` call `anyhow::bail!`. Phase 1 not landed. | Low |
| **F-5** | **`.env.example` has 22+ placeholder/empty required values** — including mandatory `CUTCTX_AUDIT_SECRET_KEY`. | Low (documentation) |

### Strengths
- Only **3 real TODO comments** survive in `cutctx/*.py` — codebase has been through TODO-removal passes
- All stubs are honest (`NotImplementedError` in abstract base classes is correct)
- Comprehensive audit infrastructure: 49 files in `audit/` documenting known gaps
- Legacy compat code is acknowledged and backward-compatible
- 17 LLM provider integrations, 30+ CLI commands, 200+ API endpoints

---

## Prioritized Action Plan

### Tier 0: Fix Immediately (Safety + Deployability)

| # | ID | Effort | Owner |
|---|---|---|---|
| 1 | **S-1** | Add auth to `/v1/compress` and `/v1/retrieve*` — ~10 lines | Security |
| 2 | **S-2** | Fix path traversal in `/assets/{filename}` — ~3 lines | Security |
| 3 | **D-1** | Fix K8s CLI flags — `--compression` → `CUTCTX_MODE`, remove `live-zone` | Ops |
| 4 | **D-2** | Align PVC name → `cutctx-data` | Ops |
| 5 | **D-3** | Add volumeMount for SQLite to deployment | Ops |
| 6 | **D-4** | Align NetworkPolicy port with deployment port | Ops |
| 7 | **D-5** | Rebuild EE Cython module to land audit HMAC fix | Eng |

### Tier 1: This Sprint (Observability + Testing Infrastructure)

| # | ID | Effort |
|---|---|---|
| 8 | **M-1** | Switch to structured JSON logging — 1-2 days |
| 9 | **M-2** | Add Sentry/GlitchTip + global exception handler — 1 day |
| 10 | **M-3** | Rewrite PrometheusRules with cutctx-specific alerts (10+ alert rules) — 1 day |
| 11 | **M-5** | Wire `CUTCTX_LOG_LEVEL` → uvicorn `log_level` — ~5 lines |
| 12 | **T-1** | Re-run clean coverage profile, verify Codecov upload — 1 hour |
| 13 | **T-2** | Apply `@pytest.mark.real_llm` to 5 files + gate default run — 1 hour |
| 14 | **T-3** | Add `pytest-rerunfailures` with `--reruns 2` to CI — 30 min |
| 15 | **T-4** | Add K8s manifest validation to CI — 1 day |
| 16 | **D-6** | Add `persistence:` block to Helm values — 30 min |
| 17 | **D-7** | Bump image tags to 0.30.0 — 10 min |

### Tier 2: Next Sprint (Performance + Test Depth)

| # | ID | Effort |
|---|---|---|
| 18 | **P-1** | Batch N+1 queries in `local.py` — 1-2 days |
| 19 | **P-2** | Wire response cache to Responses/Gemini/passthrough handlers — 1-2 days |
| 20 | **P-3** | Cap `_stable_hashes` / `_first_seen` — 30 min |
| 21 | **P-4** | Enable WAL on memory backends — ~5 lines |
| 22 | **P-5** | Replace linear `items()` scan with hash-keyed lookup — 1 day |
| 23 | **P-6** | Add missing indexes — 1 hour |
| 24 | **M-4** | Configure real log output in FluentBit — 1 day |
| 25 | **M-6** | Add FastAPI/httpx OTEL auto-instrumentation — 1 day |
| 26 | **T-6** | Add fuzz CI workflow — 1 day |
| 27 | **D-8** | Fix telemetry env var name — 30 min |
| 28 | **D-9** | Fix K8s secret template — 30 min |

### Tier 3: Backlog (Quality of Life + Completeness)

| # | ID | Effort |
|---|---|---|
| 29 | **S-4** | Flip firewall default to enabled — 1 line (needs testing) |
| 30 | **S-3** | Add TLS enforcement warning — 1 day |
| 31 | **S-5** | Tighten `deny.toml` — 1 hour |
| 32 | **F-1** | Surface feature-flag state at startup / dashboard — 1-2 days |
| 33 | **F-3** | Fix docs-vs-code drift — 2-3 days across docs |
| 34 | **T-7** | Create `test_gemini*.py` — 1-2 days |
| 35 | **T-9** | Add `cargo-llvm-cov` to CI — 1 day |
| 36 | **T-10** | Add Firefox/WebKit to Playwright projects — 1 day |
| 37 | **T-11** | Add 3.10/3.11/3.13 to CI matrix — 1 day |
| 38 | **T-5** | Add SQL migration tests — 2-3 days |
| 39 | **M-7** | Schedule `verify_chain()` + expose gauge — 1 day |
| 40 | **S-6** | Add per-route rate limits — 2-3 days |

---

## Key Metrics Summary

| Metric | Value |
|---|---|
| **Readiness Score** | **58/100** |
| **Security vulns (HIGH)** | 2 (both <30 lines of fix) |
| **Deployment blockers** | 5 (K8s config + audit HMAC) |
| **Python tests** | 8,137 functions |
| **Rust tests** | 1,401 annotations |
| **Prometheus metrics** | 50+ (but only 2 alerts, both wrong) |
| **Monitoring gaps (HIGH)** | 7 (no JSON logs, no Sentry, no real alerts, no tracing coverage, etc.) |
| **Codebase cleanliness** | Exceptional — 3 real TODOs in 400K+ lines |
| **Documented gaps** | 49 files in `audit/` — team is aware of most issues |

**Bottom line:** Fundamentally well-engineered. The blockers are concentrated in K8s config
and monitoring — not in the core architecture. Tier 0 fixes are ~50 lines of code. Tier 1
brings the score to ~75/100.
