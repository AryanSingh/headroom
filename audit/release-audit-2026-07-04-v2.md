# Release Audit (Fresh) — 2026-07-04

**Repository:** `/Users/aryansingh/Documents/Claude/Projects/headroom` · `main` @ `8106b218`
**Method:** Independent fresh assessment — all evidence gathered in this session. No reliance on prior audit narratives.
**Live proxy:** Local process on port 8787, v0.29.0, rust_core loaded, all health checks green.

---

## Bottom Line: **SCORE: 82 / 100** — **CONDITIONAL SHIP for design-partner pilot**

### Quick Summary

| Dimension | Score | Verdict |
|---|---|---|
| Test Suite | 92/100 | 7,756 passed, 7 failed, 393 skipped. Core (P0 + security) all pass. 7 failures are dashboard asset-serving + flaky tests. |
| Security | 92/100 | HMAC chain fixed, CORS fixed, stats/reset audit fixed. 5/5 criticals resolved. 10 medium/low items open. |
| Live Proxy | PASS | v0.29.0, rust_core loaded, all checks healthy. `/stats` returns 401 in 81ms (correct). |
| Deployment | 68/100 | Versions aligned (0.29.0 across all manifests). Extensive CI/CD (22 workflows). 447 dirty files. No release tag for HEAD. |
| Monitoring | 72/100 | OTel metrics wired. Health endpoints work. Dashboard assets aren't served by proxy (404). No Prometheus for 3 new initiatives. |
| Docs & Brand | 80/100 | chopratejas references cleaned up. README HEADROOM removed. EE license entity correct. Both cutctx.dev and cutctx.com are NXDOMAIN. |

---

## 1. Git State

```
HEAD:      8106b218
Tags:      v0.29.0, v0.27.0, v0.26.2, v0.26.1, v0.26.0
Describe:  v0.27.0-121-g8106b218
Modified:  374 files
Deleted:   4 files
Untracked: 9 files
Total:     447 working-tree changes
```

**Critical finding:** No release tag for the current HEAD. `git describe` says `v0.27.0-121-g8106b218` — 121 commits past the last tag. Working tree is very dirty (447 changes, mostly release-prep edits).

---

## 2. Test Suite — **92/100**

### Full Suite

```
7,756 passed · 7 failed · 393 skipped · 358s
```

### Cluster Results

| Cluster | Result | Time | Notes |
|---|---|---|---|
| P0 (CCR + Content Router + Capability Extensions) | **91/91 passed** | 17s | Clean ✅ |
| Security (Egress Enforcer + Firewall + Residency) | **28/28 passed** | 2s | Clean ✅ |
| Dashboard e2e (Playwright) | **3/3 FAILED** | 43s | Dashboard assets not served by proxy |
| Overview headline tests | **2 FAILED** | — | Flaky — pass when run alone |
| Savings by model | **1 FAILED** | — | Flaky — pass when run alone |
| Docs page | **1 FAILED** | — | Flaky — passes when run alone |

### Root Cause of Dashboard Failures

The dashboard SPA is built correctly (387KB JS bundle, 40KB CSS bundle in `cutctx/dashboard/assets/`), but the proxy returns **HTTP 404 for `/assets/` paths**. The HTML loads but the JS/CSS 404, so the page renders empty. This is an asset-serve routing issue in the proxy, not a dashboard build issue.

The 4 non-dashboard failures are flaky — they pass when run individually.

---

## 3. Security — **92/100**

### 5 Critical Items — All VERIFIED FIXED

| ID | Finding | Verdict | File:Line |
|---|---|---|---|
| C-1 | Residency `verify()` broken | **FIXED** | Test suite passes |
| C-2 | DSR imports broken | **FIXED** | Honest gated fallbacks |
| C-3 | Residency route unauth | **FIXED** | Admin auth + RBAC wired |
| C-4 | Stripe tier from metadata | **FIXED** | Price IDs, not metadata |
| C-5 | EgressEnforcer not wired | **FIXED** | 15+ call sites |

### New Fixes Verified

| Item | Status | Evidence |
|---|---|---|
| **HMAC audit chain** (was plain SHA-256) | **FIXED** | `cutctx_ee/audit/store.py:92` — `hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()` |
| **CORS wildcard + credentials** | **FIXED** | `server.py:2464-2492` — credentials=False when origins=[`\*`] |
| **Stats/reset loopback restriction** | **FIXED** | Loopback removed; only admin auth + RBAC |
| **Stats/reset audit swallowed** | **FIXED** | `server.py:4510,5759` — `logger.warning("Failed to audit stats reset: %s", exc)` |
| **HMAC regression test** | **EXISTS ON DISK** | `tests/test_ee_audit_store_hmac.py` — 21KB, guards the contract |

### Still Open (10 medium/low)

- Two license formats (Ed25519 + ECDSA P-256) coexist
- Spend ledger tenant isolation (no org filter → all orgs)
- CRL revocation fails open on network errors
- No SAML SSO (OIDC only)
- No WebAuthn (TOTP only)
- Version header leaked in every response
- `state_crypto.py` UUID-based fingerprint spoofable
- Audit log not DB-level append-only
- License DB world-readable
- NetworkPolicy allows egress to 0.0.0.0/0

---

## 4. Live Proxy — **PASS**

| Endpoint | Status | Response Time | Detail |
|---|---|---|---|
| `GET /livez` | **200** | <50ms | `healthy`, `ready:true`, `version:0.29.0`, `rust_core:loaded` |
| `GET /readyz` | **200** | <50ms | All checks healthy, upstream: anthropic |
| `GET /health` | **200** | <50ms | Full config dump, OTEL wired |
| `GET /stats` (unauthenticated) | **401** | 81ms | Correct behavior, NOT a timeout |

Compression executor: 0 queued, 0 running, 0 leaked threads (fresh proxy). Runtime: anthropic pre-upstream with 8 concurrent sessions.

---

## 5. Deployment — **68/100**

### What's Good

| Area | Status | Detail |
|---|---|---|
| **Version alignment** | ✅ **ALL 0.29.0** | All manifests aligned — `pyproject.toml`, SDKs, plugins, marketplace files |
| **Dockerfile** | ✅ | Two-stage build + distroless option, healthcheck, non-root user, module entrypoint |
| **docker-compose** | ✅ | proxy + qdrant + neo4j with healthchecks |
| **K8s manifests** | ✅ | Full set: deployment, service, ingress, HPA, PDB, network policy, configmap, secret, RBAC, backup CronJob, Prometheus rules |
| **K8s deployment image** | ✅ | `ghcr.io/cutctx/cutctx:v0.29.0` (consistent registry) |
| **Helm chart** | ✅ | `0.29.0`, same registry |
| **Release-please** | ✅ | Configured and working |
| **CI/CD** | ✅ | 22 workflows: CI (parallel shards), release (matrix wheels), Docker, docs, e2e, benchmarks, SBOM |
| **Release pipeline** | ✅ | Tag-driven, PyPI trusted publishing, npm, GitHub Packages. PR dry-runs to catch wheel issues before tag. |
| **EE license entity** | ✅ | `Payzli Inc. (operating as Cutctx Labs)` — consistent |

### What's Open

| Issue | Severity | Detail |
|---|---|---|
| **No release tag for HEAD** | **HIGH** | `git describe` returns `v0.27.0-121-g8106b218`. Release workflow is tag-driven. |
| **Working tree very dirty** | **HIGH** | 447 changes. 374 modified + 9 untracked + 4 deleted. |
| **Dashboard assets 404** | **HIGH** | `/assets/` paths not served by proxy. All 3 Playwright e2e tests fail. |
| **Ingress placeholder domain** | MEDIUM | `k8s/ingress.yaml` — `cutctx.example.com` |
| **`hello@cutctx.com` in secret.yaml** | MEDIUM | Domain is NXDOMAIN |
| **Both cutctx.dev and cutctx.com are NXDOMAIN** | **HIGH** | 28+ files reference these for docs, licenses, security contacts |
| **Backup covers 3 of 13+ SQLite stores** | MEDIUM | memory, spend_ledger, audit.db only |
| **No dependency vulnerability scanning** | LOW | Dependabot.yml exists for ecosystem updates but no CVE scanning |
| **chopratejas in docs/image-compression.mdx** | LOW | 2 references — HuggingFace model ID (not GitHub org), fine to keep |

---

## 6. Monitoring — **72/100**

### What's Good

- OTel metrics configured and wired (`server.py:1902`)
- `/livez`, `/readyz`, `/health` endpoints with per-component health checks
- Prometheus scrape annotations in k8s
- PrometheusRule alerts (HighErrorRate, HighLatency)
- Compression executor metrics exposed (queued, running, wait times)
- Dashboard cache-busting (`cache: 'no-store'`)

### What's Missing

- No Prometheus `/metrics` endpoint for Feedback Loop, Stack Graphs, Benchmark CLI
- No centralized error tracking (Sentry)
- PrometheusRule only has 2 alerts — no backup failure, no license expiry, no queue depth alerts
- No dashboard alerting or notification channels

---

## 7. Docs & Brand — **80/100**

### Cleaned Up Since Prior Audits

- **README HEADROOM ASCII art**: ✅ Removed
- **chopratejas GitHub org**: ✅ 0 references in wiki/ and docs/ (2 remain in `docs/image-compression.mdx` as HuggingFace model IDs — legitimate)
- **EE license entity**: ✅ Consistent ("Payzli Inc. operating as Cutctx Labs")
- **Install one-liner**: ✅ Points to `cutctx/cutctx`
- **CHANGELOG**: ✅ 671 lines, thorough

### Still Open

- **cutctx.dev: NXDOMAIN, cutctx.com: NXDOMAIN** — both dead
- `.env.local` exists (131 lines) — potential secret leakage risk
- Version alignment test passes but HEAD is 121 commits past last tag

---

## 8. Prior Audit Reconciliation

| Prior Finding | Status This Pass | Evidence |
|---|---|---|
| `/stats` timeout regression | **FALSE POSITIVE** | Returns 401 in 81ms (correct behavior with auth wall) |
| HMAC test file missing | **EXISTS NOW** | `tests/test_ee_audit_store_hmac.py` — 21KB |
| README HEADROOM ASCII art | **REMOVED** | grep returns 0 hits |
| chopratejas in wiki/ (8) | **CLEANED** | 0 references in wiki/ |
| EE license brand mismatch | **FIXED** | "Payzli Inc. (operating as Cutctx Labs)" |
| Version alignment drift | **FIXED** | All at 0.29.0 |
| P0 test failures (4) | **FIXED** | 91/91 pass |
| Dashboard e2e (Playwright) | **NOW FAILING (NEW)** | 3/3 fail — assets 404 |
| Test suite total | **7,924 → 7,756** | ~168 fewer tests collected (working tree changes) |

---

## P0 Blockers Before Shipping

| # | Item | Effort | Impact |
|---|---|---|---|
| 1 | **Fix dashboard asset serving** — proxy returns 404 on `/assets/` | 2-4h | Blocks all dashboard e2e tests, blocks operator dashboard in deployment |
| 2 | **Tag v0.30.0** from clean HEAD | 1h | Release workflow is tag-driven |
| 3 | **Clean working tree** — 447 changes | 2-4h | Risk of shipping unintended changes |

---

## Release Verdict by Channel

| Channel | Verdict | Score | Conditions |
|---|---|---|---|
| **Design-partner pilot** | ⚠️ **CONDITIONAL SHIP** | 82/100 | Fix dashboard asset serving + tag + clean tree (<2 days work) |
| **Public OSS release** | ❌ **NO-GO** | 72/100 | Dashboard broken, no release tag, working tree dirty, no monitoring for new features, both domains NXDOMAIN |
| **Paid enterprise** | ❌ **NO-GO** | 60/100 | No SAML, no SOC 2, no pentest, no multi-key admin, backup gap, domains dead |

Document classification: Release audit — scope: full repository as of `main @ 8106b218`. Score: **82/100**.
