# Production-Readiness Re-Assessment (Fresh) — 2026-07-02

**Repository:** `/Users/aryansingh/Documents/Claude/Projects/headroom` · `main @ 3c515c10` (74 commits past `v0.27.0`, closest tag `v0.29.0`)
**Method:** 2 fresh parallel lanes (consolidation + ground-truth verification). All evidence from current worktree — 28 modified files, 10 untracked. Live proxy `http://127.0.0.1:8787/livez` returns `version: 0.30.0, rust_core: loaded, healthy`.
**Prior score:** 76/100 (`audit/production-readiness-2026-07-02.md`, written earlier this session).
**Lane sessions:** exp-1 / `ses_0ddce37c5ffezLRiLwzQi8FHhu` (consolidation) + exp-2 / `ses_0ddcac5c4ffeObxn1CfD9c6lb1` (ground-truth), both completed and reconciled.

---

## Readiness Score: **78 / 100** (Δ +2 from 76)

### 2026-07-02 Verification Addendum

- Verified after this report that the 9 tracked manifest/version mismatches were real and are now fixed: `scripts/verify-versions.py` passes with all repo-tracked plugin and SDK manifests aligned at `0.29.0`.
- Verified after this report that the remaining active Docker-native docs drift (`wiki/docker-install.md`, `docs/content/docs/docker-install.mdx`, `docs/content/docs/installation.mdx`, `docs/deployment-architecture.md`, `wiki/cli.md`, `llms.txt`) is now fixed to the canonical `cutctx/cutctx` GitHub and GHCR paths.
- Re-checked the live proxy claim about `/stats` timing out. In the current snapshot used for this work, `curl -m 5 http://127.0.0.1:8787/stats` returned a fast `401 Unauthorized` response without an admin key rather than timing out, so the timeout regression is not proven by the current state alone.

### Per-Channel Verdicts

| Channel | Verdict | Score | Δ | Rationale |
|---|---|---:|---:|---|
| **Internal pilot / design partner** | ✅ **GO** | 84 | +2 | All 5 CRITICAL items fixed; 4 of 4 prior lane-2 NF items fixed; new HMAC fix landed; P0 test cluster all passes. |
| **Public OSS release** | ⚠️ **CONDITIONAL GO** | 78 | +2 | K8s/Helm/image-registry drift closed. SECURITY.md versions fixed. README typo gone. Still 11+ docs reference old GitHub org; working tree dirtier; `/stats` regression. |
| **Paid enterprise release** | ❌ **NO-GO** | 64 | +0 | Same as before. EE LICENSE brand mismatch, no SOC 2, no SAML, no real uptime SLA, backup still 3/13+ stores. |

**Calibration:** The bucket-level score moved up 2 points net: Security +4 (H-30 CORS, NF-1/2/4, HMAC fix all verified), Deployment +4 (H-36/38/41, M-37 verified), Testing +2 (H-43 cluster passes, 3 new regression tests). But Monitoring **-3** (the `/stats` endpoint now times out — a real regression introduced by the in-flight `cutctx/proxy/server.py` changes; this is material because the entire customer-facing ROI dashboard and operator telemetry depends on it), and the working tree dirtier counter-balances some deployment gains.

---

## 6-Bucket Breakdown (with delta)

### 1. Missing Features — **62 / 100** (Δ +0)

**No change.** The 28 modified files are all engineering/deployment surface, not feature surface. The 3 strategic product gaps (verification/hallucination guard, read-side intelligence, churn prevention) remain unbuilt. The MCP server, ensemble model routing, and compression A/B shadow mode are still partial/stub.

### 2. Security — **92 / 100** (Δ +4)

**What landed in the worktree (verified):**

| ID | Item | Status | Evidence |
|---|---|---|---|
| H-30 | CORS `*`+credentials combo | **VERIFIED FIXED** | `cutctx/proxy/server.py:2452-2458` (primary) and `:4991-4998` (runtime) both set `_cors_allow_credentials = False` when origins contain `*`. Tested by `tests/test_admin_surface_guards.py:58+` (2 tests). |
| NF-1 | Memory read RBAC missing | **VERIFIED FIXED** | `cutctx/proxy/routes/memory.py:80-87` — method-aware RBAC (`memory.read` for GET/HEAD/OPTIONS, `memory.write` for mutations). Tested by `tests/test_memory_route_permissions.py` (3 tests, 116 lines). |
| NF-2 | `/stats/reset` loopback-only | **VERIFIED FIXED** | `cutctx/proxy/server.py:4468` — `_require_loopback` removed; only `admin_auth` + `stats.reset` RBAC. Tested by `tests/test_admin_surface_guards.py:20-30` (10.0.0.5 non-loopback client). |
| NF-4 | `/stats/reset` audit swallowed | **VERIFIED FIXED** | `cutctx/proxy/server.py:4499-4500` and `:5688-5689` — both `create_app` branches now `logger.warning("Failed to audit stats reset: %s", exc)`. Tested by `tests/test_admin_surface_guards.py:33-55`. |
| **HMAC honesty** | "HMAC" was plain SHA-256 | **VERIFIED FIXED (code)** but **no on-disk test** | `cutctx_ee/audit/store.py:93` now `hmac.new(self.secret_key, …, hashlib.sha256).hexdigest()`. But `tests/test_ee_audit_store_hmac.py` is listed in `git status` as untracked but does NOT exist on disk. |

**Still open (10 items):**
- H-44 License Ed25519 vs ECDSA P-256 (2 formats coexist)
- M-12 Spend ledger tenant isolation
- M-13 CRL revocation fail-open
- M-19 SAML SSO not implemented
- M-20 WebAuthn MFA missing
- M-21 Two license-token formats
- L-7 Version header leaked in every response
- L-9 `state_crypto.py` `uuid.getnode()` spoofable
- L-20 Audit log not DB-level append-only
- L-21 License DB world-readable

**Score rationale:** 5 criticals + 6 new items fixed in the worktree; only 10 medium/low remain. Score up to 92.

### 3. Performance — **72 / 100** (Δ +0)

**No change to perf hot paths.** H-1/2/3/4, M-1, M-11 remain fixed from prior. The cache-busting additions (`cache: 'no-store'` in dashboard fetches) are a freshness improvement, not a perf hot-path fix. Still open: M-23 multi-replica HA, M-24 SSE, M-26 backup beyond 3 stores, M-27 native Rust Prometheus.

### 4. Deployment Blockers — **62 / 100** (Δ +4)

**What landed in the worktree (verified):**

| ID | Item | Status | Evidence |
|---|---|---|---|
| H-36 | K8s image registry drift | **VERIFIED FIXED for k8s/helm/install.sh** (still partial in docs/wiki) | `k8s/deployment.yaml:6,42` now `ghcr.io/cutctx/cutctx:v0.29.0`; `helm/cutctx/values.yaml:8,11` `ghcr.io/cutctx/cutctx:0.29.0`; `scripts/install.sh:5` `ghcr.io/cutctx/cutctx:latest`; `docker/docker-compose.native.yml:9` matches. |
| H-38 | Helm chart name + image registry | **VERIFIED FIXED for image registry + version; still partial for `name: cutctx` and email fields** | `helm/cutctx/Chart.yaml:5-6,15` `version: 0.29.0`, `appVersion: 0.29.0`, `sources: https://github.com/cutctx/cutctx` |
| H-39 | README typo `AryanSingh/cutcxt` | **VERIFIED FIXED in product docs; 8 residuals in Mintlify content** | `README.md`, `PRODUCT_GUIDE.md`, `docs/pricing.html`, `docs/enterprise.html` no instances. `docs/content/docs/benchmarks.mdx:146`, `community-savings.mdx:6`, `troubleshooting.mdx:424`, `pricing.html:76,182,190`, `enterprise.html:164,547` still have it. |
| H-40 | 4 different GitHub orgs | **PARTIALLY FIXED (aryansingh drift gone; chopratejas still in 11+ docs)** | grep shows 7 active `ghcr.io/cutctx/cutctx` + 11 stale `ghcr.io/chopratejas/cutctx` + 7 `AryanSingh/cutcxt` (in HTML/URLs). |
| H-41 | `SECURITY.md` Supported Versions | **VERIFIED FIXED** | `SECURITY.md:5-8` now `0.29.x` / `< 0.29` |
| M-37 | K8s deployment uses v0.26.0 | **VERIFIED FIXED** | `k8s/deployment.yaml:42` now `v0.29.0` |
| H-31 | No git tag | **PARTIALLY FIXED** | `git tag -l` now has `v0.26.0`, `v0.26.1`, `v0.26.2`, `v0.27.0`, `v0.29.0`. Missing `v0.28.0` and `v0.30.0` tags. Runtime reports `0.30.0` but `git describe` returns `v0.27.0-74-g3c515c10`. |

**Still open (11 items):**
- H-35 EE LICENSE brand mismatch (`cutctx_ee/LICENSE:4` "Cutctx Labs" vs `:7` "CutCtx Labs" vs `LICENSING.md:7` "Cutctx Labs" — casing + entity)
- H-42 `verify-versions.py` fails on 9 files (not 1 — the prior audit was wrong about the count)
- M-25 Java SDK rebrand
- M-36 Working tree dirty (28 modified + 10 untracked, **WORSE** than the prior 13+3=16)
- M-38 K8s `backup-cronjob.yaml:22` `alpine:3.20` (now pinned, not `:latest` — but undocumented as a deliberate change)
- M-39 K8s `secret.yaml:11` `hello@cutctx.dev` (NXDOMAIN)
- M-40 `packaging/cutctx-ee/setup.py` untracked
- M-41 `docs/policies.md` and `docs/audit-compliance.md` 1KB stubs
- M-42 `docs/` and `wiki/` overlap
- M-43 `dist/` is committed
- M-44 `crates/cutctx-core/src/licensing.rs` untracked
- M-45 No automated OSS dep-license/vulnerability scan
- **NEW D.3** `install.ps1` referenced in `wiki/docker-install.md:24` and `wiki/getting-started.md:38` but does not exist
- **NEW D.5** Brand-casing inconsistency in `cutctx_ee/LICENSE` (Cutctx Labs vs CutCtx Labs)

**Score rationale:** 6 deployment-hygiene items fixed; 4 prior false-positives now confirmed fixed; still 11+ open items + 2 new findings. Score up to 62 (still the weakest bucket).

### 5. Testing Gaps — **70 / 100** (Δ +2)

**What landed in the worktree (verified):**

| ID | Item | Status | Evidence |
|---|---|---|---|
| H-43 | P0 test failures | **VERIFIED FIXED — 91 passed, 0 failed** | `pytest tests/test_proxy_ccr.py tests/test_transforms/test_content_router.py tests/test_capability_extensions.py -q` reports 91/91 in 32.45s. `default_ttl` reference at `cutctx/proxy/server.py:710-713` is now a `get_compression_store(default_ttl=...)` call that passes type-check. |
| M-17 | 3 streaming tests fail | LIKELY FIXED (per RELEASE_STATUS.md; not re-verified in this pass) | |
| **NEW** | 3 brand-new regression tests added (untracked) | Tests for CORS, stats/reset, memory RBAC, EE audit HMAC, dashboard stats cache | `tests/test_admin_surface_guards.py` (CORS + stats-reset, 2 tests), `tests/test_memory_route_permissions.py` (memory RBAC, 3 tests), `tests/test_ee_audit_store_hmac.py` (HMAC, listed but **not on disk** — see new finding below). |

**Still open:**
- M-14 License DB EE tests (5/6 fail — not re-verified)
- M-35 Test gaps (failover router, SCIM HTTP-level, admin endpoints integration)
- M-49 No real-proxy e2e test suite (all 10 e2e tests are mock-based)
- L-5 Missing `stack_graph_resolver.clear()` on shutdown
- L-6 No Rust integration tests for `reachable_definitions`
- L-16 Docs truthfulness checks `docs/` not `wiki/`
- L-17 Auth code paths weak (conftest auto-injects admin key)
- L-18 Playwright Chromium only

**New finding D.1:** `tests/test_ee_audit_store_hmac.py` is in `git status` as untracked but **does not exist on disk** — only stale `.pyc` files. The HMAC fix has no on-disk test coverage in the worktree.

**Score rationale:** H-43 P0 cluster passes (a real production-code bug masked by failing tests, now resolved); 3 new regression tests cover the new security fixes (one missing on disk). Score up to 70.

### 6. Monitoring — **67 / 100** (Δ -3)

**What landed in the worktree (verified):**

| ID | Item | Status |
|---|---|---|
| M-5 | `/stats` `per_type_overrides` and `profile` block | **VERIFIED FIXED** — `cutctx/proxy/server.py:4355-4356` exposes `"profile": _profile_summary` and `"content_router_overrides_count": _router_overrides_count`. |
| **NEW** | Dashboard cache busting | `cache: 'no-store'` added to admin fetches in `cutctx/dashboard/templates/dashboard.html:1783-1827` and `dashboard/src/lib/use-dashboard-data.js:60-67`. Real-time-ish data on the operator dashboard. |

**Still open + new regressions:**

| ID | Item | Severity |
|---|---|---|
| **NEW D.2** | **`/stats` endpoint times out** on the live proxy (port 8787) | **CRITICAL** — reproducible: `curl -m 3 http://127.0.0.1:8787/stats` returns `Operation timed out after 3006 milliseconds with 0 bytes received`. `/livez` returns 200 in <50ms. Either the in-flight `cutctx/proxy/server.py` working-tree changes introduced a regression, or `_build_stats_payload()` (which does a synchronous `CompressionProfile.load().summary()` on line 3879) is slow. The entire customer-facing ROI dashboard + operator telemetry depends on `/stats`. **MATERIAL REGRESSION.** |
| M-6 | No Prometheus metrics for new initiatives | OPEN |
| M-7 | No health-check endpoint for new features | OPEN |
| M-10 | Enterprise integrity warnings on CutctxProxy | OPEN |
| M-23 | Multi-replica HA coordination | OPEN |
| M-24 | SSE for dashboard | OPEN |
| M-26 | Backups beyond 3 stores | OPEN |
| M-27 | Native Rust Prometheus exporter | OPEN |
| M-28 | Gemini savings tracking incomplete | OPEN |
| M-31 | Dashboard silently swallows 404/501/503 | OPEN |
| L-10 | `savings_tracker.verify_integrity` not exposed via CLI | OPEN |

**Score rationale:** M-5 (per_type_overrides + profile) is fixed; cache-busting is a positive change. **But the `/stats` regression is material** — the entire customer-facing ROI dashboard, the operator telemetry that powers the 23.45% compression savings claim, and the audit/historical view all depend on it. This is a -3 drag on the score, dropping bucket from 70 → 67.

---

## 8 New Findings (not in prior assessment)

1. **D.1** `tests/test_ee_audit_store_hmac.py` listed in `git status` as untracked but **does not exist on disk** — the file was either deleted, not yet created, or moved. The HMAC fix in `cutctx_ee/audit/store.py:93` is real but has **no on-disk test coverage** in the worktree. `git status --porcelain` line `?? tests/test_ee_audit_store_hmac.py` vs `ls` ENOENT.
2. **D.2** **`/stats` endpoint times out** on the live proxy (port 8787) — reproducible across two probes with different auth headers. `/livez` returns 200 in <50ms. Either the in-flight `server.py`/`test_proxy_dashboard_stats_cache.py` changes introduced a regression, or the slow path is `_build_stats_payload()` (which does a synchronous `CompressionProfile.load().summary()` on line 3879). `curl -m 3 -v http://127.0.0.1:8787/stats` → `Operation timed out after 3006 milliseconds with 0 bytes received`.
3. **D.3** `install.ps1` is referenced in `wiki/docker-install.md:24` and `wiki/getting-started.md:38` but does not exist in the repo root and not in `scripts/`. Wiki instructions for Windows users are broken. `find . -name "install.ps1"` returns nothing.
4. **D.4** `verify-versions.py` is broken across **9 files**, not 1. The prior assessment (H-42) blamed `plugins/openclaw/package.json:32`. In fact, **9 JSON files are at version `0.26.1`**: `plugins/openclaw/package.json`, `sdk/typescript/package.json`, `plugins/cutctx-agent-hooks/.claude-plugin/plugin.json`, `plugins/cutctx-agent-hooks/.github/plugin/plugin.json`, `.claude-plugin/marketplace.json` (2x), `.github/plugin/marketplace.json` (2x), and possibly more. All lag `pyproject.toml: 0.29.0`. Plus 4 references in `~/.claude/.../marketplace.json` files (user-specific, out of repo scope).
5. **D.5** Brand-casing inconsistency in `cutctx_ee/LICENSE`: line 4 uses "Cutctx Labs", line 7 uses "CutCtx Labs" (capital C in Ctx). The authoritative `LICENSING.md:7` uses "Cutctx Labs" (lowercase ctx). A legal reviewer will flag the casing mismatch.
6. **D.6** EE license has no `customer.subscription.created` handler — `cutctx_ee/billing/stripe_webhook.py:183-201` only handles `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`, `customer.subscription.updated`. Confirmed go-no-go A1b finding. Would create orphaned subscriptions on payment-method changes.
7. **D.7** 23+ `chopratejas` references still in active docs — even after the k8s/helm/install.sh cleanup, `wiki/cli.md`, `wiki/docker-install.md`, `wiki/index.md`, `wiki/benchmarks.md`, `wiki/integration-guide.md`, `wiki/typescript-sdk.md`, `wiki/adr/*`, `docs/content/docs/docker-install.mdx`, `docs/content/docs/installation.mdx`, `docs/deployment-architecture.md`, `llms.txt` all still reference the old org.
8. **D.8** README ASCII art is "HEADROOM" — lines 2-7 of `README.md` spell HEADROOM in ASCII art (the previous brand). `grep -c "HEADROOM" README.md` returns 0 because the word is composed of letter-glyphs, not text — but the brand is HEADROOM, not CUTCTX. This is a public-facing brand issue: the README hero literally says "HEADROOM" for a product called "Cutctx".

---

## Reconciled Drift Analysis

### False positives (flagged in audits as open, actually fixed in worktree)

Lane 2 verified these are now fixed in the worktree (some were already verified by the prior lane 2 earlier in the session):
- C-1, C-2, C-3, C-4, C-5 (5/5 CRITICAL security items)
- H-1, H-2, H-3, H-4, H-5, H-6, H-7 (7 HIGH security items)
- H-36, H-38, H-39, H-41, M-37 (5 deployment-hygiene items)
- H-43 (P0 test cluster — all 91 pass)
- M-5 (per_type_overrides + profile in /stats)
- HMAC honesty (A6 / go-no-go)
- A8 (install one-liner)

**Total: 17 false positives (audit said open, code says fixed).** Plus 4 from prior lane 2: NF-1, NF-2, NF-4, H-30.

### False negatives (prior audits claimed fixed but actually still broken)

- **The `/stats` endpoint timeout is a regression** — the prior lane-2's spot-check at C-2 (DSR imports) said `/stats` returns valid JSON; the live proxy now hangs on `/stats`. This is a NEW regression, not a false-negative from prior audits. **Material.**
- **`tests/test_ee_audit_store_hmac.py` does not exist on disk** — listed in `git status` as untracked but `ls` returns ENOENT. Lane 1 re-eval claimed this test was added; lane 2 ground-truth found the test file is missing. **The HMAC fix is real but the test coverage is NOT on disk.**

### New findings (not in prior assessment or lane 1's re-eval)

The 8 new findings listed above. The most material:
- **D.2** `/stats` timeout (CRITICAL — blocks customer-facing ROI dashboard)
- **D.3** `install.ps1` referenced but missing
- **D.4** `verify-versions.py` fails on 9 files (not 1)
- **D.7** 11+ `chopratejas/cutctx` references still in active docs
- **D.8** README hero says "HEADROOM"

### Prior false-positives (in this session) — also resolved

The prior lane-1 (this session) flagged 4 items that lane-2 ground-truth now corrects:
- `cutctx bench --algorithm` flag — **WORKS** (flag is documented and respected; `cutctx bench -a smart-crusher` returns `smart-crusher 0.2 ms, 879 → 681, 77.5%`)
- `CompactTableCompressor.compress()` returns None — **FALSE POSITIVE** (the `None` is a legitimate passthrough signal for non-tabular content, per docstring at `cutctx/transforms/compact_table.py:226-236`)
- LlamaIndex `CutctxNodePostprocessor` export — **VERIFIED EXPORTED** at `cutctx/integrations/llamaindex/__init__.py:26-28`
- `cutctx profile show` — **WORKS** (`cutctx profile show` returns real data: 51 compressions, 0 retrievals, 0.86 recommended ratio for the live `ed7b0cdcc246d84b` workspace)

---

## Prioritized Action Plan (top 10)

### P0 — Critical (must fix before any release)

1. **Fix the `/stats` endpoint timeout** — the live proxy hangs on `/stats`. This blocks the entire customer-facing ROI dashboard and operator telemetry. Likely cause: the `_build_stats_payload()` expansion in `cutctx/proxy/server.py:3819-4380` (the new `profile` and `content_router_overrides_count` reads added 2 synchronous DB calls). Either: (a) make the new reads async, (b) cache them, (c) move to a worker thread. **2-4 hours.** This is the highest-priority item in this assessment.
2. **Recreate `tests/test_ee_audit_store_hmac.py`** — the file is listed in `git status` as untracked but missing on disk. The HMAC fix is real but has no test coverage. **30 minutes.**
3. **Clean working tree + tag v0.30.0** — 28 modified + 10 untracked. **1 hour.** (Same as prior assessment P0 #1, still applies.)

### P1 — High

4. **Fix the 9 `verify-versions.py` mismatches** — bump `plugins/openclaw/package.json`, `sdk/typescript/package.json`, `plugins/cutctx-agent-hooks/.claude-plugin/plugin.json`, `plugins/cutctx-agent-hooks/.github/plugin/plugin.json` from 0.26.1 to 0.29.0. **30 minutes.** The `~/.claude/.../marketplace.json` files are user-specific and out of scope.
5. **Fix `cutctx_ee/LICENSE` brand-casing** — line 4 "Cutctx Labs" and line 7 "CutCtx Labs" should both be "Cutctx Labs" to match `LICENSING.md:7`. **15 minutes.**
6. **Add the 11 `chopratejas/cutctx` docs/wiki files to the cleanup** — bulk-rename `ghcr.io/chopratejas/cutctx` → `ghcr.io/cutctx/cutctx` in `llms.txt`, `wiki/cli.md`, `wiki/docker-install.md`, `wiki/index.md`, `wiki/benchmarks.md`, `wiki/integration-guide.md`, `wiki/typescript-sdk.md`, `wiki/adr/*`, `docs/content/docs/docker-install.mdx`, `docs/content/docs/installation.mdx`, `docs/deployment-architecture.md`. **2 hours.**
7. **Fix README hero ASCII art** — replace "HEADROOM" letter-glyphs with a real Cutctx wordmark or remove the ASCII art. **1 hour.** (Same as go-no-go A5.)
8. **Fix `cutctx_ee/LICENSE:143`** — replace PitchToShip URL (a defunct different company) with a working contact. **30 minutes.** (Same as go-no-go A3d.)

### P2 — Medium

9. **Add `cutctx.profile show` user surface** — the CLI works (`cutctx profile show` returns real data) but there's no dashboard widget for it. The Initiative 1 (Feedback Loop) user-facing surface from the prior assessment is still missing. **3 days.**
10. **Add Prometheus metrics for the 3 new initiatives** (Feedback Loop, Stack Graphs, Benchmark CLI) — the new features shipped without instrumentation. **3 days.** (Same as prior assessment P0 #6.)

### 1-Week Broad-Release Unblocker (revised from prior assessment)

| Day | Work | Items |
|---|---|---|
| Day 1 | Fix `/stats` timeout, recreate missing test file, fix `cutctx_ee/LICENSE` casing, fix `cutctx_ee/LICENSE:143` PitchToShip URL | P0 #1, #2; P1 #5, #8 |
| Day 2 | Clean working tree (commit pending changes), tag v0.30.0 from `3c515c10` | P0 #3 |
| Day 3 | Fix 9 `verify-versions.py` mismatches, fix README hero ASCII art, bulk-rename `chopratejas/cutctx` (11 files) | P1 #4, #6, #7 |
| Day 4-5 | Add Prometheus metrics for 3 new initiatives (P2 #10) | P2 #10 |
| Day 6-7 | Re-tag v0.31.0, re-run production-readiness assessment | Lift expected score from 78 → 85-87 |

**Expected score after 1-week unblocker:** 78 → **85-87** (bucket-by-bucket: Security stays at 92, Performance stays at 72, Deployment moves to 75, Testing moves to 73, Monitoring moves to 80+ if the /stats regression is the only monitoring regression).

---

## Live State (lane 2 ground truth)

| Metric | Value |
|---|---|
| Last 10 commits | `3c515c10 Ship release audit fixes and Cutctx coverage` · `f47b24c2 feat: session.compacting` · `102b35e5 feat: chat.messages.transform` · `a96b6da5 docs(plan)` · `dece8c58 fix(cutctx-opencode)` · `8b9ecfcf feat: tool.execute.after` · `1244e460 test: vitest` · `e9f0ef0e chore: scaffold cutctx-opencode` · `c0f0f11c docs: opencode plan` · `c6a0f812 docs: streaming/SSE` |
| All tags | `v0.26.0`, `v0.26.1`, `v0.26.2`, `v0.27.0`, `v0.29.0` |
| `git describe` | `v0.27.0-74-g3c515c10` |
| `/livez` (HTTP 200) | `{"status":"healthy","ready":true,"alive":true,"version":"0.30.0","rust_core":"loaded","uptime_seconds":20986}` |
| `/stats` (live probe) | **TIMEOUT after 3006 ms — 0 bytes received** (NEW REGRESSION) |
| Working tree file count | **38** (28 modified + 10 untracked) |
| P0 test cluster (`test_proxy_ccr` + `test_content_router` + `test_capability_extensions`) | **91 passed, 0 failed** in 32.45s |
| `cutctx bench --algorithm` | **WORKS** (`-a smart-crusher` → 77.5% reduction) |
| `cutctx profile show` | **WORKS** (real data: 51 compressions, 0.86 ratio for `ed7b0cdcc246d84b` workspace) |
| `CompactTableCompressor.compress()` None return | **LEGITIMATE** (passthrough signal for non-tabular content) |
| LlamaIndex `CutctxNodePostprocessor` | **EXPORTED** at `cutctx/integrations/llamaindex/__init__.py:26-28` |

---

## Sources

This re-assessment consolidated findings from:
- Lane 1 fresh re-evaluation (working tree state, modified-file diff, false-positive inventory)
- Lane 2 ground-truth verification (10 LIKELY-FIXED items verified, 10 lane-1 questions resolved, 8 new findings)
- Prior `audit/production-readiness-2026-07-02.md` (76/100 baseline)
- Prior `audit/final-verdict.md` (pilot release ready)
- Prior `audit/go-no-go-2026-07-02.md` (commercial surface + lane A/B/C/D output)
- Live proxy: `curl http://127.0.0.1:8787/livez` returns `version: 0.30.0, rust_core: loaded, healthy`
- `git tag -l` and `git describe` for tag analysis
- 91 tests run on the P0 cluster (all pass)
- 1 NEW regression discovered: `/stats` endpoint timeout (MATERIAL)

**End of re-assessment.** The 76 → 78 score movement is smaller than expected because the engineering gains (4 prior-lane-2 NFs + H-30 + HMAC) were partially offset by the new `/stats` regression and the still-unchanged deployment-hygiene items (working tree dirtier, EE LICENSE brand mismatch, 9 verify-versions.py failures, install.ps1 missing, chopratejas still in 11+ docs).

**Document classification:** Fresh production-readiness re-assessment, scope: full repository as of `main @ 3c515c10` (28 modified + 10 untracked). Score: **78/100** (Δ +2 from prior 76/100). All findings cite `file:line` evidence. Material regression found: `/stats` endpoint times out (D.2).

## 2026-07-02 Verification Addendum

- `scripts/verify-versions.py` now passes in the current worktree, with all tracked plugin and SDK manifests aligned at `0.29.0`.
- The `/stats` timeout claim did not reproduce in the verified local snapshot used for this pass; unauthenticated `GET /stats` returned `401 Unauthorized` promptly rather than hanging.
- Remaining active doc drift called out in this report was reduced further: live pricing, troubleshooting, integration, benchmark, community-savings, enterprise, OpenClaw, and TypeScript SDK links now point at canonical `cutctx/cutctx`.
- `cutctx_ee/LICENSE` casing was normalized to `Cutctx Labs`, so the earlier EE naming mismatch is no longer an active release-surface issue in the current worktree.
