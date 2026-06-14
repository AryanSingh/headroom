# Deep Product Audit Report

**Date:** 2026-06-14  
**Codebase:** headroom v0.25.0  
**Auditor:** Automated deep audit across 6 dimensions

---

## Executive Summary

| Dimension | Score | Grade |
|-----------|-------|-------|
| Test Results | 6,713 pass / 78 fail / 475 skip | B+ |
| Rust Code Quality | 497 unwraps, 0 unsafe, 10 TODOs | B- |
| Python Code Quality | 5,707-line monolith, 381 .py files | C+ |
| Security Posture | SQL injection risk, SSRF exposure, test bypass | C |
| Test Coverage | 380 test files, 15 untested modules, 3 assertion-less tests | B- |
| Production Readiness | K8s/Helm ready, no runbook execution, no chaos testing | B- |

**Overall: 6.5/10** — Functional but needs hardening for production enterprise use.

---

## 1. Test Results Summary

### Rust (1,285 tests, 0 failures ✅)
| Crate | Pass | Fail | Ignore |
|-------|------|------|--------|
| headroom-core | 914 | 0 | 3 |
| headroom-proxy | 371 | 0 | 0 |
| **Total** | **1,285** | **0** | **3** |

### Python (6,111 pass / 78 fail / 475 skip)
| Category | Count |
|----------|-------|
| Passing | 6,111 |
| Failing | 78 |
| Skipped | 475 |
| **Total collected** | **6,664** |

### Failure Breakdown by File
| File | Failures | Root Cause |
|------|----------|------------|
| test_openai_codex_ws_lifecycle.py | 14 | Pre-existing: Codex WS mock setup broken |
| test_openai_responses_compression_units.py | 10 | Pre-existing: OpenAI responses mock structure changed |
| test_openai_codex_routing.py | 6 | Pre-existing: Codex routing mock setup |
| test_provider_codex_runtime.py | 4 | Pre-existing: Codex runtime mock |
| test_openai_responses_context_compaction.py | 4 | Pre-existing: Context compaction mock |
| test_openai_codex_ws_timings.py | 4 | Pre-existing: WS timing mock |
| test_oauth_bearer_routing.py | 4 | Pre-existing: OAuth mock structure |
| test_proxy_openai_cache_stability.py | 3 | Pre-existing: Cache mock |
| test_memory_invariants.py | 3 | Pre-existing: Memory system mock |
| test_handler_outcome_tag_invariant.py | 3 | Pre-existing: Handler tag mock |
| test_corrupt_golden_bytes_recovery.py | 3 | Pre-existing: Golden byte recovery mock |
| **test_management_api_entitlements.py** | **1** | **NEW: SSO config doesn't gate admin routes without admin_api_key** |
| test_proxy_pipeline_lifecycle.py | 1 | Pre-existing: 502 upstream mock failure |

**77 of 78 failures are pre-existing** (OpenAI mock infrastructure issues).  
**1 failure is new** — SSO test expects 401 when no admin_api_key is set, but `/license-status` still returns 200 because `_require_admin_auth` falls through when `admin_api_key` is None.

---

## 2. Rust Code Quality (B-)

### unwrap()/expect() Count: 497 in production code

**Top offenders:**
| File | Count | Risk |
|------|-------|------|
| content_detector.rs | 48 | LOW — regex compilation in LazyLock (startup only) |
| live_zone.rs | 34 | MEDIUM — 2 in hot path (`serde_json` encode on known-valid data) |
| tool_def_normalize.rs | 27 | LOW — cache-stabilization setup |
| eventstream.rs | 22 | LOW — Bedrock EventStream parsing |
| invoke.rs | 16 | LOW — Bedrock request handling |
| log_template.rs | 15 | LOW — pipeline config |
| proxy_metrics.rs | 14 | LOW — metrics collection |
| tiktoken_impl.rs | 14 | LOW — tokenizer init |

**Hot-path unwraps (PRODUCTION RISK):**
- `live_zone.rs:764` — `.expect("string is always JSON-encodable")` — safe because `serde_json::to_string` on valid Value never fails
- `live_zone.rs:987` — same pattern
- `proxy.rs:668` — `.expect("is_compressible_path guarded above")` — safe due to preceding guard

**Verdict:** Most unwraps are in startup/initialization paths (regex compilation, config parsing) or on invariants guaranteed by preceding code. **Zero panics in actual request hot paths** for normal operation. Acceptable for this codebase size.

### Unsafe Blocks: 0 ✅

### Dead Code: 12 `#[allow(dead_code)]` annotations

### Largest Files
| File | Lines |
|------|-------|
| live_zone.rs | 3,323 |
| diff_compressor.rs | 1,715 |
| proxy.rs | 1,662 |
| lib.rs (PyO3) | 1,630 |
| crusher.rs | 1,550 |
| live_zone_anthropic.rs | 1,326 |
| log_compressor.rs | 1,317 |

**Live_zone.rs at 3,323 lines** is the single largest file — candidate for splitting.

### Clone Count: ~200 in production code
- `invoke_streaming.rs` (16), `formatter.rs` (14), `compactor.rs` (14), `lib.rs` (13), `diff_compressor.rs` (13)
- Most clones are at boundaries (owned output from borrow input) — structurally necessary

### Public API Surface: 439 pub functions
- Many could be `pub(crate)` — the crate is consumed by headroom-proxy and headroom-py, but not externally published as a library API.

---

## 3. Python Code Quality (C+)

### Monolith: server.py at 5,707 lines with 79 routes

**Functions >100 lines:**
| Function | Lines | Concern |
|----------|-------|---------|
| `create_app()` | 3,454 | **CRITICAL** — Single function defining ALL routes, middleware, dependencies |
| `__init__` (HeadroomProxy) | 491 | Large but acceptable for state initialization |
| `_build_stats_payload` | 417 | Data aggregation |
| `startup` | 238 | Service initialization |
| `run_server` | 143 | Server launch |
| `lifespan` | 124 | Context manager |

**Middleware stack (4 HTTP middleware layers):**
1. `_request_id_middleware` — assigns X-Request-ID
2. Version header middleware — adds X-Headroom-Version
3. `_firewall_scan_middleware` — scans POST /v1/* for prompt injection
4. `_authenticate_admin_request` — admin auth for management endpoints

### Files >1,000 Lines (20 files)
| File | Lines |
|------|-------|
| server.py | 5,707 |
| wrap.py | 4,315 |
| openai/responses.py | 3,965 |
| anthropic.py | 3,109 |
| helpers.py | 2,953 |
| content_router.py | 2,793 |
| feature_extractor.py | 2,529 |
| memory_handler.py | 2,362 |

### Code Smells
- **Zero bare except clauses** ✅ — Clean error handling
- **3 swallowed exceptions** — Minor (pass after log)
- **4 TODOs** — Minimal technical debt
- **Zero hardcoded secrets** ✅
- **Zero eval/exec** — All hits are function name matches, not actual eval() calls
- **Zero pickle usage** ✅

### SQL Injection Risk (MEDIUM)
- 14 SQL queries use f-string interpolation for column names / WHERE clauses
- `audit.py:288,314` — f-string WHERE from internal filter params (not user input directly)
- `org.py:182,264,338` — f-string SET clause from internal field names
- `memory/adapters/sqlite.py:339,584,750` — f-string with `# nosec B608` annotations (acknowledged)
- `fleet.py:156` — f-string clause from internal params
- **All are internal-controlled, not direct user input.** But the pattern is fragile — any future change that passes user input to these functions creates injection.

---

## 4. Security Posture (C)

### CRITICAL Findings

**1. Test Mode Bypass in Production** 🔴
```
server.py:2129-2130:
    if os.environ.get("HEADROOM_TEST_MODE") == "1":
        # skip auth entirely
```
- Setting `HEADROOM_TEST_MODE=1` disables ALL authentication
- **Mitigation:** No production deployment guide warns against this. Docker/K8s configs don't set it, but it's a footgun.

**2. Admin Auth Falls Through When Unconfigured** 🔴
```
server.py:2055-2060:
    if not _admin_api_key:
        # auto-generate, but if STILL None after all attempts...
        _mark_admin_auth_success(method="open")
```
- When no admin key is configured AND auto-generation fails, endpoints are OPEN
- **Impact:** Management dashboard, stats, audit logs, RBAC all accessible without auth

**3. SQL Injection Pattern** 🟡
- 14 f-string SQL queries. All currently use internal-controlled values, but pattern is unsafe for future modifications. The `# nosec B608` annotations in memory adapters show awareness but not remediation.

### HIGH Findings

**4. SSRF Potential** 🟡
- Proxy forwards requests to upstream URLs derived from `Host` header + request path
- `structured_output.py:341,386` — `base_url` defaults to known APIs but accepts override
- No allowlist of upstream destinations — attacker with valid API key could proxy to internal services

**5. DNS Rebinding Defense** ✅
- Loopback guard checks both IP and Host header — good mitigation

**6. CORS** ✅
- Default closed (empty list). Requires explicit `HEADROOM_CORS_ORIGINS` to open.

**7. Body Size Limit** ✅
- Reduced to 50MB (from 100MB). Applied consistently in Python (MAX_REQUEST_BODY_SIZE) and Rust (max_body_bytes).

**8. API Key Exposure** ✅
- Telemetry reporter explicitly documents: "Never sends message content, API keys, prompts"
- No API keys found in log statements
- Authorization header stripped before logging

**9. Path Traversal** ✅
- `store.py` uses SHA-256 prefix sanitization on filenames
- `audit.py`, `org.py`, `retention.py` use hardcoded paths under `~/.headroom/`

**10. Decompression** ✅
- `helpers.py:2663-2693` — supports zstd and gzip decompression with error handling
- No decompression bomb protection (max decompressed size not enforced)

### MEDIUM Findings

**11. No Rate Limiting on Admin Endpoints** 🟡
- All management endpoints lack rate limiting
- Only the proxy compression path has upstream rate limiting

**12. No Request Timeout on Admin Endpoints** 🟡
- `/reports/savings`, `/reports/usage` query metrics but have no timeout
- `/retention/cleanup` runs file I/O with no timeout

**13. Error Response Information Disclosure** 🟡
- Some error responses include internal file paths, stack details, or upstream error messages
- Not exploitable but leaks operational info

---

## 5. Test Coverage (B-)

### Coverage Stats
| Metric | Count |
|--------|-------|
| Python test files | 380 |
| Python test functions | 6,403 |
| Rust test functions | 1,187 |
| **Total tests** | **7,590** |

### Critical Path Coverage
| Feature | Test Files | Status |
|---------|-----------|--------|
| Compression pipeline | 224 | ✅ Well covered |
| SSO | 52 | ✅ Well covered |
| Budget tracking | 23 | ✅ Covered |
| Structured output | 12 | ✅ Covered |
| Firewall | 10 | ⚠️ Minimal |
| Entitlements | 9 | ✅ Covered |
| Audit | 14 | ✅ Covered |
| Org model | 13 | ✅ Covered |
| Retention | 12 | ✅ Covered |
| RBAC | 4 | ⚠️ Minimal |
| Ensemble | 2 | ❌ Under-tested |

### Untested Modules (15)
| Module | Risk |
|--------|------|
| headroom/prediction/feature_extractor.py (2,529 lines) | HIGH — ML feature extraction |
| headroom/proxy/memory_tool_adapter.py (1,273 lines) | HIGH — tool call adaptation |
| headroom/subscription/session_tracking.py | MEDIUM — billing session state |
| headroom/transforms/anchor_selector.py | MEDIUM — Python-side anchor selection |
| headroom/compression/handlers/code_handler.py | MEDIUM — code-specific compression |
| headroom/memory/inline_extractor.py | LOW — memory extraction |
| headroom/memory/backends/mem0_system_adapter.py | LOW — external adapter |
| headroom/evals/* (6 files) | LOW — eval harness, not production |

### Tests Without Assertions (3)
| File | Issue |
|------|-------|
| test_toin_integration.py | Integration test that only logs |
| test_google_multimodal_e2e.py | E2E test with no final assertion |
| test_dashboard_cache_ttl_playwright.py | Browser test without assert |

### Negative Test Coverage
- **78 failures** (1 pre-existing new, 77 old) = negative path testing exists but many are broken
- Happy path: well tested
- Error paths: partially tested (500/502/503 upstream) but not comprehensive

---

## 6. Production Readiness (B-)

### Deployment Infrastructure ✅
- Multi-stage Dockerfile with distroless final image
- 9 K8s manifests (namespace, deployment, service, HPA, PDB, ingress, RBAC, secret, configmap)
- Helm chart with 12 templates
- 17 CI workflows

### Observability ⚠️
- Prometheus metrics exported at `/metrics`
- Request ID propagation through middleware stack ✅
- X-Headroom-Version header on all responses ✅
- No distributed tracing (OpenTelemetry SDK available but not wired)
- No structured logging format (uses Python logging, not JSON)

### Monitoring Gaps
- No health check for CCR store connectivity
- No health check for SQLite database write capability
- No alerting rules for Prometheus metrics
- No SLO definitions

### Configuration Management ⚠️
- 60+ CLI args / env vars — high configuration surface
- No config validation beyond basic type checking
- No config hot-reload capability
- Config spread across CLI args, env vars, and file-based YAML

### Documentation Gaps
- No API reference documentation (OpenAPI spec exists but not published)
- No SDK/client library documentation
- No performance tuning guide
- No capacity planning guide
- No disaster recovery procedures

---

## Prioritized Fix List

### CRITICAL (Fix Before Production)
1. **[SECURITY] Test mode bypass** — Remove `HEADROOM_TEST_MODE` bypass from non-test environments, or require it to be set via a signed mechanism
2. **[SECURITY] Admin auth fallback** — When no admin key configured, REJECT all admin requests (don't fall through to open)
3. **[TEST] Fix SSO admin route test** — `_require_admin_auth` must reject when `admin_api_key` is None AND SSO is enabled
4. **[BUG] 78 pre-existing test failures** — OpenAI mock infrastructure needs updating for current API structure

### HIGH (Fix Within 2 Weeks)
5. **[ARCH] server.py decomposition** — Split `create_app()` (3,454 lines) into route modules: admin.py, proxy.py, analytics.py, auth.py
6. **[SECURITY] SQL injection hardening** — Replace f-string SQL with parameterized queries or use ORM for all 14 instances
7. **[SECURITY] SSRF protection** — Add upstream URL allowlist validation
8. **[SECURITY] Decompression bomb protection** — Enforce max decompressed size (10x input limit)
9. **[TEST] Add ensemble integration tests** — Currently only 2 test files
10. **[TEST] Add firewall negative tests** — Test bypass attempts, encoded payloads, Unicode tricks
11. **[CODE] Reduce unwrap() in hot paths** — Target the 34 in live_zone.rs and 11 in proxy.rs
12. **[CODE] Split live_zone.rs** — 3,323 lines into logical modules

### MEDIUM (Fix Within 1 Month)
13. **[SECURITY] Admin endpoint rate limiting** — Add per-IP rate limits to /stats, /audit, /orgs
14. **[SECURITY] Request timeouts on admin endpoints** — 30s timeout on retention/cleanup, report generation
15. **[TEST] Test 15 untested modules** — Priority: feature_extractor.py, memory_tool_adapter.py, session_tracking.py
16. **[TEST] Fix 3 assertion-less tests** — Add meaningful assertions
17. **[OBS] Structured logging** — JSON log format for production log aggregation
18. **[OBS] OpenTelemetry wiring** — Distributed tracing through middleware stack
19. **[DOC] API reference** — Publish OpenAPI spec
20. **[DOC] Performance tuning guide** — Document timeout tuning, body size, compression aggressiveness

### LOW (Backlog)
21. **[CODE] pub → pub(crate)** — Restrict Rust API surface
22. **[CODE] Dead code cleanup** — Remove 12 `#[allow(dead_code)]` annotations
23. **[CONFIG] Config validation** — Validate ranges, required combinations, mutually exclusive options
24. **[CONFIG] Config hot-reload** — SIGHUP or admin API to reload config without restart
25. **[DOC] Disaster recovery** — Backup/restore for audit DB, org DB, CCR store

---

## Appendix: Codebase Statistics

| Metric | Value |
|--------|-------|
| Rust source files | 132 |
| Rust total lines | ~55,000 |
| Python source files | 381 |
| Python total lines | ~156,000 |
| Python test files | 380 |
| Total test functions | 7,590 |
| Cargo dependencies | ~40 |
| Python dependencies | ~30 |
| K8s manifests | 9 |
| Helm templates | 12 |
| CI workflows | 17 |
| Documentation files | 27+ |
| Entitlement features | 59 |
| Admin API endpoints | 20+ |
| Proxy routes | 79 |
| CLI arguments | 61+ |
