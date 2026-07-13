# Production Readiness Assessment — 2026-07-12

**Repository:** `main @ v0.30.0-58-g7bd12a1a`
**Live proxy:** v0.31.0, all 6 dependency checks healthy, rust_core loaded
**Test suite:** 98/98 critical pass, 3/3 dashboard e2e pass, 620 test files
**Working tree:** Clean (1 binary file)

---

## Readiness Score: **78 / 100** (Pilot-Ready, Not Broad-Release-Ready)

| Bucket | Score | Key Strengths | Key Gaps |
|---|---|---|---|
| **Features** | 85/100 | Full pipeline, CCR, MCP, cross-agent memory | PitchToShip dependency, no self-serve billing |
| **Security** | 82/100 | HMAC audit, auth rate-limited, egress enforcer | No progressive backoff, no Sentry, K8s egress wide-open |
| **Performance** | 70/100 | Backpressure on executor, caches with RLocks | No memory accounting per-request, all caches in-memory |
| **Deployment** | 78/100 | Docker+Helm+K8s, 22 CI workflows, resource limits | Alerting (2 rules), no WebSocket session cap, memory limits tight |
| **Testing** | 75/100 | 620 files, 7,763+ tests, e2e suites | EE coverage gap (4 files for 7+ features), 9 modules untested |
| **Monitoring** | 65/100 | Excellent Prometheus metrics, health checks, structured logs | Alerting insufficient (2 rules), no Sentry, no memory/disk checks |
| **Overall** | **78/100** | Core engineering solid. Gaps are bounded and fixable. | 2-week sprint to 85+. |

---

## 1. Missing Features / Stubs (Score: 85/100)

### Real Stubs Found
| Finding | File | Severity |
|---|---|---|
| PitchToShip-dependent billing — entire `cutctx/billing.py`, `cutctx_ee/billing/__init__.py`, `cutctx/cli/billing.py` depend on `POST https://pitchtoship.com/api/billing/checkout` which returns HTTP 400 | 20+ files across `cutctx/billing.py`, `cutctx_ee/billing/`, `cutctx/cli/billing.py`, `cutctx/proxy/routes/license_validation.py` | **Critical** |
| No `customer.subscription.created` handler in Stripe webhook — only `.deleted` and `.updated` are handled | `cutctx_ee/billing/stripe_webhook.py:292-295` | **High** |
| Memory service admits no RBAC and no audit emission (explicit TODO) | `cutctx_ee/memory_service/api.py:110` | **Medium** |
| Kompress batch compression path marked as TODO (PR-B4) | `crates/cutctx-core/src/transforms/live_zone.rs:1618` | **Low** |
| No dashboard billing/pricing/subscription page | `dashboard/` (no Billing.jsx, Pricing.jsx, Subscription.jsx exists) | **High** |

### No Significant Stubs Found
A systematic grep for `TODO`, `FIXME`, `raise NotImplementedError`, `pass  # todo`, `stub` found zero production-code stubs outside the items above. The codebase is remarkably complete for its scope.

### Feature Flags / Gated Features
- `CUTCTX_OFFLINE_MODE` — air-gap mode
- `CUTCTX_SSO_ENABLED` — SSO toggle
- `CUTCTX_MFA_ENFORCE` — MFA enforcement (optional)
- `CUTCTX_ALLOW_DEBUG` — debug mode (startup warning when set)
- `CUTCTX_KOMPRESS_MAX_WORDS` — ML compression input cap (default 80K)
- `CUTCTX_EGRESS_POLICY` — egress allowlist (opt-in)

**Finding:** Sensible gating. No half-baked features exposed to users.

---

## 2. Security Gaps (Score: 82/100)

### Critical
| Finding | Detail | Evidence |
|---|---|---|
| None | All prior criticals fixed (auth bypass, LIKE injection, Kompress DoS) | Verified in current worktree |

### High
| Finding | Detail | Evidence |
|---|---|---|
| **No error tracking (Sentry)** | Unhandled exceptions in request handlers have no fallback reporting. Silent failures in production. | `grep -r "sentry" cutctx/` → no results |

### Medium
| Finding | Detail | Evidence |
|---|---|---|
| **Auth brute-force lacks progressive backoff** | Rate limiter uses fixed token-bucket refill (10/min/IP). No exponential backoff across IPs. Attacker with 1001 IPs gets ~10 attempts/IP/min indefinitely. | `server.py:3148-3162`, `rate_limiter.py:19` |
| **K8s network policy allows all egress** | Network policy opens `0.0.0.0/0` on ports 443/80/53 — opposite of deny-all. Application-level enforcer exists but is opt-in. | `k8s/network-policy.yaml:21-31` |
| **No memory pressure health check** | Livez/readyz doesn't check RSS, available memory, or swap usage. OOM risk invisible to operators. | `server.py:3426-3440` |
| **Metrics endpoint behind admin auth** | Prometheus scrapers typically need unauthenticated access or separate auth config. | `qa-report.md` |
| **No CSRF protection on dashboard** | SPA with header-based auth, but no SameSite/CSRF token patterns visible | `server.py:2484-2504` |

### Low
| Finding | Detail | Evidence |
|---|---|---|
| **No PGP key for vuln disclosures** | No `/.well-known/security.txt` with PGP fingerprint | Directory check |
| **Compression cache has no memory budget** | `max_entries=10000` cap but no per-entry size limit — pathological case could fill RAM | `compression_cache.py:97` |
| **All caches in-memory, no persistence** | Cache reset on restart means warm-up period after every deployment | `compression_cache.py` |

---

## 3. Performance Issues (Score: 70/100)

### High
| Finding | Detail | Evidence |
|---|---|---|
| **No per-request memory accounting** | 50MB default `max_body_mb` × 32 workers = 1.6GB theoretical in-flight. No safeguard against concurrent large payloads exhausting RAM. | `models.py:465`, `compression_decision.py` |
| **No WebSocket session limit** | `WebSocketSessionRegistry` has no `max_sessions` cap. Unbounded sessions = resource exhaustion. | `server.py` (grep shows index cache eviction at max sessions, but no WS limit) |

### Medium
| Finding | Detail | Evidence |
|---|---|---|
| **Compression cache without memory budget** | 10K entries × variable size. Large compressed payloads (images, long code outputs) could grow unbounded until cap hit. | `compression_cache.py:97` |
| **K8s memory limits tight for 32 workers** | 512Mi limit with 32 compression workers — each worker needs stack + compression state. Could OOM under load. | `k8s/deployment.yaml:resources` |
| **No persistent cache across restarts** | Every deployment = cold cache. Warm-up period for compression patterns. | `compression_cache.py` |

### Low
| Finding | Detail | Evidence |
|---|---|---|
| **Policy learning schema may lack indexes** | `policy_learning.py:84` — `CREATE TABLE` without explicit index creation | `policy_learning.py` |
| **No dependency audit tooling** | No `pip-audit` or `cargo audit` in CI pipeline | `.github/workflows/` |

---

## 4. Deployment Blockers (Score: 78/100)

### High
| Finding | Detail | Evidence |
|---|---|---|
| **Alerting rules insufficient** | Only 2 rules (5xx error rate, p99 latency). Missing: memory pressure, executor queue timeouts, WS sessions, leaked threads, upstream connectivity, disk space, cert expiry, auth failure spikes. | `k8s/prometheus-rules.yaml` (19 lines) |
| **PitchToShip billing dependency** | 20+ files depend on `pitchtoship.com` (HTTP 400 upstream). No direct Stripe checkout. Deploying without fixing this means billing is broken. | `cutctx_ee/billing/`, `cutctx/billing.py` |

### Medium
| Finding | Detail | Evidence |
|---|---|---|
| **Helm values have limited env var coverage** | `values.yaml` only comments out a single `CUTCTX_LICENSE_KEY` example. All env vars must be set through external values file or secrets. | `helm/cutctx/values.yaml` |
| **Stripe env vars not documented in Helm** | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*` not in Helm values or K8s configmaps | `helm/cutctx/values.yaml` |

### Low
| Finding | Detail | Evidence |
|---|---|---|
| **No release branch strategy** | Only `main` branch with tags. No `release/*` branches for hotfixes. | `git branch -a` |
| **Dashboard asset serving 404 from proxy** | `/assets/` returns 404; test mocks work around it but production dashboard may serve unstyled | `release-audit-verify-2026-07-04.md` |

---

## 5. Testing Gaps (Score: 75/100)

### What's Tested ✅
| Area | Count | Status |
|---|---|---|
| Total Python test files | 620 | ✅ Good breadth |
| Total tests passing | 7,763 | ✅ Verified 0 failures |
| Critical cluster (CCR + Content Router + Capability Extensions) | 98/98 | ✅ Pass |
| Dashboard e2e (Playwright) | 3/3 | ✅ Pass |
| Core compression transforms | Extensive | ✅ |
| Proxy route tests | Good | ✅ |
| Rust crate tests | 10 integration files | ✅ |
| Commercial surface truthfulness | Has dedicated test | ✅ |

### What's NOT Tested ❌
| Area | Severity | Detail |
|---|---|---|
| **Enterprise Edition features** | **High** | Only 4 test files for SSO, RBAC, SCIM, audit, retention, fleet, DSR, residency, abuse, secrets — 7+ major EE features with near-zero test coverage |
| **`cutctx/compress.py`** | **Medium** | Core compression module has no dedicated test file |
| **`cutctx/proxy/` routes** | **Medium** | No `tests/test_proxy.py` — proxy tested indirectly through integration tests |
| **`cutctx/client.py`** | **Medium** | SDK client module untested |
| **`cutctx/dedup.py`** | **Low** | Dedup module untested |
| **`cutctx/security/`** | **High** | Security module (state crypto, keyring, egress) has minimal test coverage |
| **`cutctx/context_budget.py`** | **Medium** | Budget enforcement untested |
| **`cutctx/cost_forecast.py`** | **Low** | Cost forecasting untested |
| **`cutctx/profiles.py`** | **Low** | Compression profiles untested |

### Flaky Test Patterns
| Pattern | Occurrences | Risk |
|---|---|---|
| `@pytest.mark.flaky` | 0 | Low — no known flaky tests |
| `time.sleep(` in tests | Minimal | Low |
| `tests/test_memory_bridge.py:60` — `## TODO` | 1 | Contains actual TODO marker |

---

## 6. Monitoring (Score: 65/100)

### Health Checks ✅
| Endpoint | What It Checks | What's Missing |
|---|---|---|
| `GET /livez` | Startup, HTTP client, cache, rate limiter, memory, upstream | Memory pressure (RSS), compression executor health, disk space |
| `GET /readyz` | Same as livez + 503 when unhealthy | Same gaps |
| `GET /health` | Aggregate status | Same gaps |

### Prometheus Metrics ✅ (Excellent Coverage)
| Metric Group | Examples |
|---|---|
| Request counts | `cutctx_request_total` by provider/model/status |
| Token tracking | `cutctx_tokens_input`, `cutctx_tokens_output`, `cutctx_tokens_saved` |
| Compression | `cutctx_compression_ratio` |
| Latency | `cutctx_latency_seconds`, `cutctx_ttfb_seconds`, `cutctx_stage_timing_ms_*` |
| WebSocket | `cutctx_active_ws_sessions`, `cutctx_active_relay_tasks`, `cutctx_ws_session_duration_*` |
| Rate limiting | `cutctx_rate_limited_total` |
| Savings | `cutctx_savings_*` (cumulative) |
| Prefix cache | `cutctx_prefix_cache_*` |
| Executor | `cutctx_compression_executor_*` (queue depth, in-flight, leaked threads) |

### Alerting ❌ (Critical Gap)
| Current Rules | Missing Rules |
|---|---|
| HighErrorRate (>5% 5xx for 5m) | Memory pressure / OOM risk |
| HighLatency (p99 > 2s for 5m) | Compression executor queue timeout saturation |
| — | WebSocket session count spike |
| — | Rate limiter bucket saturation (legitimate users blocked) |
| — | Upstream connectivity loss |
| — | Leaked threads increasing (stuck workers) |
| — | SQLite disk space low |
| — | TLS certificate expiry |
| — | Admin auth failure spike (brute-force detection) |

**The 3am page scenario:** High error rate will fire. But memory exhaustion, executor saturation, upstream failures, and disk-full conditions degrade silently without any alert.

### Logging ✅ (Good)
| Requirement | Status |
|---|---|
| Structured JSON logs | ✅ `request_logger.py` |
| API key redaction | ✅ |
| PII handling | ✅ Firewall module blocks PII/injection/jailbreak |
| Request IDs | ✅ Tied to metrics for correlation |
| Base64 redaction threshold | ✅ 1024 bytes — correctly avoids false positives |

### Error Tracking ❌
- **No Sentry, no error tracking SDK configured**
- Unhandled exceptions in request handlers have no fallback reporting
- Silent failures in production go undetected until a user reports them

---

## Prioritized Action Plan

### Week 1 (Score impact: 78 → 85)

| Priority | Action | Area | Effort |
|---|---|---|---|
| **P0** | Expand Prometheus alerting rules — add memory pressure, executor queue timeouts, WS session count, leaked threads, upstream health, disk space, cert expiry, auth failures | Monitoring | 1 day |
| **P0** | Add `max_ws_sessions` configurable limit to `WebSocketSessionRegistry` | Performance | 0.5 day |
| **P0** | Add `customer.subscription.created` handler to `stripe_webhook.py` | Billing | 0.5 day |
| **P1** | Add per-request memory accounting — track in-flight compression payload sizes, reject when budget exceeded | Performance | 1 day |
| **P1** | Add Sentry/error tracking at proxy startup | Monitoring | 0.5 day |
| **P1** | Add memory pressure check to `/livez` and `/readyz` | Monitoring | 0.5 day |

### Week 2 (Score impact: 85 → 90)

| Priority | Action | Area | Effort |
|---|---|---|---|
| **P1** | Write test files for untested critical modules: `compress.py`, `client.py`, `security/`, `context_budget.py` | Testing | 2 days |
| **P1** | Write EE test coverage for SSO, RBAC, SCIM, audit, retention, fleet (currently 4 test files for 7+ features) | Testing | 3 days |
| **P1** | Reduce `max_body_mb` default from 50 to 10, or add configurable per-worker memory limit | Performance | 0.5 day |
| **P2** | Add progressive backoff to admin auth rate limiter (exponential delay, cross-IP coordination) | Security | 1 day |
| **P2** | Tighten K8s network policy — deny-all egress by default, allowlist specific endpoints | Security | 0.5 day |
| **P2** | Add compression cache memory budget (per-entry size cap, total memory limit) | Performance | 1 day |

### Month 2 (Score impact: 90 → 95)

| Priority | Action | Area | Effort |
|---|---|---|---|
| **P2** | Wire Stripe Checkout directly (bypass PitchToShip) — direct `stripe.checkout.Session.create()` call | Billing | 3 days |
| **P2** | Add persistent cache backend (Redis or SQLite) for compression patterns | Performance | 2 days |
| **P2** | Add `pip-audit` / `cargo audit` to CI pipeline | Security | 0.5 day |
| **P3** | Add progressive auth backoff with cross-node coordination (Redis-based) | Security | 2 days |
| **P3** | Add dashboard billing page (Pricing.jsx, Subscription.jsx) | Features | 2 days |
| **P3** | Add CSRF protection tokens to dashboard endpoints | Security | 0.5 day |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OOM under load (512Mi + 32 workers) | Medium | High | Add per-request memory budget, reduce max_body_mb default |
| Silent upstream failure (Anthropic/OpenAI down) | Low | Critical | Add upstream health metric to alerting rules (Week 1 P0) |
| Cache poisoning / unbounded memory via compression cache | Low | Medium | Add memory budget to cache (Week 2 P2) |
| Auth brute-force via IP rotation | Low | High | Add progressive backoff (Week 2 P2) |
| WebSocket resource exhaustion (no session cap) | Low | Medium | Add max_ws_sessions config (Week 1 P0) |
| Enterprise feature regression (no EE test coverage) | Medium | High | Write EE test suite (Week 2 P1) |

---

## Sources

This report consolidates findings from:
- Live probes on 2026-07-12 (live proxy, DNS, git state, test runs)
- `cutctx/proxy/server.py`, `cutctx/proxy/rate_limiter.py`, `cutctx/proxy/prometheus_metrics.py`, `cutctx/proxy/request_logger.py`
- `cutctx/compression_cache.py`, `cutctx/security/egress.py`, `cutctx_ee/audit/store.py`
- `cutctx_ee/billing/stripe_webhook.py`, `cutctx_ee/billing/__init__.py`, `cutctx/billing.py`
- `k8s/prometheus-rules.yaml`, `k8s/deployment.yaml`, `k8s/network-policy.yaml`
- `helm/cutctx/values.yaml`
- `.github/workflows/ci.yml`
- `audit/qa-report.md` (2026-07-08)
- `audit/release-audit-verify-2026-07-04.md`
- `audit/production-readiness-2026-07-02.md` (76/100 baseline)
- Systematic grep for TODOs, stubs, env vars, test coverage, PitchToShip footprint
