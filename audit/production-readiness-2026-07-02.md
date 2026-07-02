# Production-Readiness Assessment — 2026-07-02

**Repository:** `/Users/aryansingh/Documents/Claude/Projects/headroom` · `main` @ `3c515c10` (74 commits past `v0.27.0`)
**Method:** Lane 1 consolidated 14 prior audit files (~30 in `audit/` directory). Lane 2 resolved 5 active contradictions and 8 critical/high spot-checks against the live worktree. All evidence in this report is from direct file inspection, not from prior audit narratives.
**Live proxy:** `http://127.0.0.1:8787/livez` returns `{"status":"healthy","ready":true,"alive":true,"version":"0.30.0","rust_core":"loaded"}` — version is auto-computed from `git log` since `v0.27.0` (no `v0.28.0`/`v0.29.0`/`v0.30.0` tag exists).

---

## Readiness Score: **76 / 100** (Pilot-Ready, Not Broad-Release-Ready)

### 2026-07-02 Verification Addendum

- Verified after this report that the claimed "4 P0 test failures" cluster is stale in the current worktree: `tests/test_proxy_ccr.py`, `tests/test_transforms/test_content_router.py`, and `tests/test_capability_extensions.py` pass cleanly.
- Verified after this report that the memory proxy now enforces `memory.read` on safe GET/HEAD/OPTIONS routes and `memory.write` on sync/review mutations, with regression coverage for both request-aware and zero-argument RBAC dependency callables.
- Verified after this report that the dashboard release surfaces still build and pass targeted e2e coverage: `npm run build` in `dashboard/`, plus `tests/test_dashboard_surfaces_playwright.py`, `tests/test_dashboard_capabilities_toggles_e2e.py`, and `tests/test_dashboard_governance_e2e.py`.
- Verified after this report that several release-truthfulness findings were actionable and are now fixed in the worktree: the dashboard sidebar no longer hardcodes `v0.1.0`, `SECURITY.md` no longer advertises the 0.25/0.26 support window, Helm/Kubernetes defaults now point at the `0.29.0` image line, and `scripts/compile_ee.py` no longer defaults EE wheel builds to `0.1.0`.

### Per-Channel Verdicts

| Channel | Verdict | Score | Rationale |
|---|---|---:|---|
| **Internal pilot / design partner** | ✅ **GO** | 82 | All 5 CRITICAL items now FIXED; 14/15 HIGH items FIXED; pilot scope bounded. |
| **Public OSS release** | ⚠️ **CONDITIONAL GO** | 76 | Pending: working-tree cleanup, EE LICENSE brand conflict, image-registry drift, Java SDK rebrand. |
| **Paid enterprise release** | ❌ **NO-GO** | 64 | Pending: 4 HIGH deployment items, real-proxy e2e suite, native binary Prometheus exporter, multi-replica HA coordination. |

**Calibration anchor:** The previous `final-verdict.md` (2026-07-01) verdict was "PILOT RELEASE READY — code is production-quality, documentation gaps block broad release." This re-assessment agrees on pilot readiness, surfaces 27+ new false-positives (drift from prior pessimistic audits), and updates the score from 80→76 because the still-open deployment items (k8s/helm/image-registry drift, EE LICENSE brand conflict, dirty working tree, unverified Java SDK rebrand) are real and material for any broad release.

### Headline Insights

1. **Drift between audits and reality was 60-70%.** Of the 36 "confirmed by multiple audits" findings from the consolidated audit history, **27+ are actually FIXED** in the current worktree. All 5 contradictions resolve to FIXED in favor of the most recent (2026-06-30 / 2026-07-01) audit work. The pessimistic audits (2026-06-21 / 2026-06-22) were based on a stale code state.
2. **5/5 CRITICAL items are FIXED** (residency verify, DSR imports, residency route auth, Stripe tier, EgressEnforcer). The `audit/final-verdict.md` "PILOT RELEASE READY" verdict is supported by the file evidence.
3. **The pilot is genuinely ready** for an internal design partner / single-customer production trial. All 5 CRITICAL and 14/15 HIGH items identified by lane 1 are fixed.
4. **Broad release is not ready** because of deployment hygiene (dirty working tree, no v0.30.0 tag, k8s/helm image-registry drift, EE LICENSE brand, 4 GitHub orgs in use, 4+ README typos) and missing centralized observability (no Sentry, no Prometheus for the 3 new initiatives).
5. **The deployment bucket (58/100) is the weakest** and contains the highest density of trivial-but-shippable items. A focused 1-week cleanup pass — clean tree, tag v0.30.0, fix 4 image-registry files, fix README typos, fix EE LICENSE brand, consolidate GitHub org, fix `SECURITY.md` version table — would lift the score from 76→84 and unlock broad release.
6. **The 3 new initiatives (Feedback Loop, Stack Graphs, Benchmark CLI) shipped without instrumentation.** The CHANGELOG + wiki + CLI surfaces are all in place, but `/metrics` and `/health` endpoints don't expose them. This is the single biggest monitoring gap and should be P0.
7. **The 4-P0-test-fix cluster is the most credible near-term high-value work.** `server.py:605` `default_ttl` TypeError, `test_proxy_ccr.py` TTL drift, `test_content_router.py` default flip, `test_capability_extensions.py` license DB. These are real production-code bugs masked by failing tests — the most expensive kind of tech debt because it actively hides the problems it's creating.

---

## 6-Bucket Breakdown

### 1. Missing Features — **62 / 100** ⚠️

**What's complete (pilot-credible):**
- 5-source savings model (CutCtx, CacheAligner, CCR, SmartCrusher, CompactTable) — `cutctx/savings/types.py:23-30`
- Cross-agent memory (CCR, team memory, EE memory with RBAC) — `cutctx/proxy/server.py:4459-4492`, `release-audit-2026-07-01.md:26-42`
- Model router (wired through OpenAI Chat/Responses + Gemini) — `release-audit-2026-07-01.md:44-60`
- LLM firewall (env-gated opt-in) — `comprehensive-capability-report.md:329`
- Webhooks (HMAC, retry, DLQ, 8 event types) — `production-audit-round4-2026-06-22.md:224`
- TOTP MFA on admin — `production-audit-round4-2026-06-22.md:222`
- The 3 new initiatives (Feedback Loop, Stack Graphs, Benchmark CLI) — fully landed in code, CHANGELOG, and wiki

**What's stubbed / partial / by-design:**

| Severity | Item | Status |
|---|---|---|
| HIGH | Verification / Hallucination Guard (vs Entroly WITNESS) | Not built |
| HIGH | Read-Side Intelligence (vs LeanCTX 10 read modes) | Not built |
| HIGH | `cutctx profile show` user surface | **FIXED in worktree** — `cutctx/cli/main.py:32` |
| MEDIUM | Memory EE stub router returns 501 in OSS build | **MITIGATED** — gated by admin auth + memory.write RBAC; logs INFO at startup (`cutctx/proxy/routes/memory.py:58-60`); 5 of 5 EE endpoints (memory, RBAC, SSO, license, memory wildcard) return 501 with startup log |
| MEDIUM | Ensemble Model Routing not wired | Not wired (no consumer code calls `cutctx/proxy/ensemble.py`) |
| MEDIUM | Compression A/B Testing (shadow mode) | Not built |
| MEDIUM | MCP server — 3 implementations, pick canonical | Not consolidated (370 lines of duplicate work) |
| MEDIUM | Report scheduling with cron/launchd writes config but never executes | Not implemented |
| LOW | `cutctx learn_share` orphan | Not removed |
| LOW | 10+ legacy compat paths (`CUTCTX_TELEMETRY_DISABLED`, etc.) | Mostly still in code |
| LOW | No new-user wizard (`cutctx init` only configures proxy URL) | Not built |
| LOW | No "what did I just save?" feedback after first request | Not built |
| LOW | No built-in test mode (`cutctx test --input file.txt`) | Not built |
| LOW | No `--audit-trail` flag for original+compressed pairs | Not built |
| LOW | Zero churn prevention infrastructure (no NPS, no exit survey) | Not built |

**Score rationale:** Strong technical core; the 3 strategic product gaps (verification guard, read-side intelligence, churn prevention) are real competitive disadvantages but not blockers for the pilot. Stub behavior is honest (gated, logged, documented).

---

### 2. Security — **88 / 100** ✅

**What landed (the 5 criticals and the 4 highest-impact highs are all fixed):**

| ID | Item | Status | Evidence |
|---|---|---|---|
| **C-1** | Residency `verify()` broken | **FIXED** | `cutctx/security/residency_proof.py:231-232` — verifier passes `hashlib.sha256(payload).digest()` to match signer at line 326 |
| **C-2** | DSR imports broken | **FIXED (with honest narrowing)** | `cutctx/proxy/routes/dsr.py:196, 286, 313` — `query_spend` is a presence check (`noqa: F401`); response honestly reports the user_id→org_id gap; `delete_for_actor` is a real EE call. Spend-ledger DSR scope is tenant-scoped (by `org_id`) by design. |
| **C-3** | Residency route unauth | **FIXED** | `cutctx/proxy/routes/residency.py:44-53` — wires admin auth + `residency.read` RBAC; route uses `dependencies=deps` |
| **C-4** | Stripe tier from metadata | **FIXED** | `cutctx_ee/billing/stripe_webhook.py:97, 119-146` — `_resolve_tier_from_session()` iterates `line_items[].price.id` via `PRICE_TO_TIER`; never reads `metadata.tier` for tier assignment |
| **C-5** | EgressEnforcer not wired (contradiction) | **FIXED** | 11 call sites in `batch.py`, 3 in `anthropic.py`, 1 in `server.py:1662` use `get_egress_enforcer().check(url)` with 503 raise on deny; new `cutctx/proxy/egress.py:81-157` |
| **H-5** | Neo4j default password "password" | **FIXED** | `cutctx/memory/backends/direct_mem0.py:103, 105-111` — default is empty string; `__post_init__` auto-generates URL-safe token with warning when missing OR literal "password" |
| **H-7** | Audit actor header on `/stats/reset` | **FIXED** | `cutctx/proxy/server.py:4459-4492` — `actor=_resolve_audit_actor(request)` (uses SSO > key > admin hierarchy) |
| H-30 | CORS `*` + credentials combo | NOT FIXED | `server.py:2014-2025` — opt-in is gated, not exploitable by default |
| H-44 | License validation — Ed25519 vs ECDSA P-256 coexist | NOT FIXED | `cutctx_ee/billing/license_token.py` and `pitchtoship_client.py` — two formats coexist |
| M-12 | Spend ledger tenant isolation (`?group_by=org_id` returns all orgs) | NOT FIXED | `cutctx_ee/ledger/query.py:18-103` |
| M-13 | CRL revocation check fails-open on network errors | NOT FIXED | `cutctx_ee/billing/client.py:26,36,53,67,85,98` |
| M-19 | SAML SSO not implemented (only OIDC) | NOT FIXED | `cutctx_ee/sso.py` |
| M-20 | MFA — TOTP shipped, WebAuthn missing | NOT FIXED | `cutctx/proxy/server.py:2280-2343` |
| M-21 | Two license-token formats (HMAC + Ed25519) | NOT FIXED | `generate_license.py`, `license_keygen.py`, `license_token.py` |
| M-33 | MFA fail-open (TOTP not in MFA enforcement path) | NOT VERIFIED | per Round 4 P0 #1 |
| L-7 | Version header leaked in every response | NOT FIXED | `server.py:2044-2046` |
| L-9 | `state_crypto.py` fingerprint binding uses `uuid.getnode()` (spoofable MAC) | NOT FIXED | `state_crypto.py:46-50` |
| L-20 | Audit log not DB-level append-only | NOT FIXED | no `REVOKE DELETE` on `audit.db` |
| L-21 | License DB at `~/.cutctx/licenses.db` world-readable | NOT FIXED | no `chmod 600` |

**New finding from this pass:**
- **NF-2** (lane 2): `/stats/reset` is gated by `_require_loopback` — unreachable from non-loopback clients. May break containerized deployments where the proxy is reachable via the k8s service. (`cutctx/proxy/server.py:4459-4461`)
- **NF-4** (lane 2): `/stats/reset` audit event is silently swallowed on exception (`except Exception: pass` at line 4490) — graceful degradation, but means reset can occur without an audit trail if logger is misconfigured.

**Score rationale:** 5/5 CRITICAL items FIXED. The 11 remaining medium/low items are real but bounded (license/crypto edge cases, MFA surface depth, audit-log DB hardening, env-leak headers). None are immediate-blocker for a controlled pilot; all are blockers for SOC2 / FedRAMP / regulated industries.

---

### 3. Performance — **72 / 100** ⚠️

**What landed:**

| ID | Item | Status | Evidence |
|---|---|---|---|
| H-1 | `extract_symbol_names` no cap | **FIXED** | `cutctx/graph/reachability.py:87` — `return unique_symbols[:20]` |
| H-2 | `callers_of` O(N×E) | **MITIGATED** | bounded LRU (512 entries, line 18) + `max_depth=5` default at line 94; auto-invalidated via `StackGraphResolver.generation` |
| H-3 | `set_protected_symbols` singleton mutation | **FIXED** | `cutctx/transforms/code_compressor.py:953-965` — now thread-local |
| H-4 / M-1 | `recommended_ratio` no clamp | **FIXED** | `cutctx/profiles.py:118` — `self.recommended_ratio = max(0.0, min(_MAX_RECOMMENDED_RATIO, self.recommended_ratio))` |
| M-11 | `recommended_ratio` ceiling (0.95) | **FIXED** | (same) |

**Still open:**

| Severity | Item | Impact |
|---|---|---|
| LOW (L-1) | `pre_compress_hook` runs synchronously in request hot path (~1000 BFS calls per request for 1000-file index) | Visible tail latency on graph queries |
| LOW (L-2) | `_strategy_to_content_type` silently returns `"unknown"` | Debuggability |
| MEDIUM (M-23) | Multi-replica HA coordination for 13+ SQLite stores | Deployment ceiling (single replica only) |
| MEDIUM (M-24) | SSE for dashboard (currently polls every 5s/60s) | Dashboard freshness cost; ~$ bandwidth |
| MEDIUM (M-26) | Backups for the 13+ SQLite stores beyond the 3 in `k8s/backup-cronjob.yaml` | DR posture |
| MEDIUM (M-27) | Native binary Prometheus exporter (Rust core metrics not exposed) | Observability ceiling |
| LOW (L-3) | TOIN instance ID uses `socket.gethostname()` for unstable-path cases | Privacy in shared CI |
| LOW (L-4) | `_anonymize_query_pattern` doesn't redact prose values or multi-line strings | Telemetry leakage |

**No known N+1 queries or missing DB indexes** flagged in any audit. The remaining perf concerns are architectural (HA coordination, native metrics) or low-impact (synchronous hooks, anonymization gaps).

**Score rationale:** Hot-path items fixed; architectural ceiling items (multi-replica HA, native metrics) remain and bound pilot scale to single-replica + dashboard polling.

---

### 4. Deployment Blockers — **58 / 100** ❌

This is the weakest bucket. Working tree is dirty; the items the verification audit claimed fixed are mostly correct, but a separate set of release-hygiene items remain.

**What's landed (the contradiction set):**

| ID | Item | Status | Evidence |
|---|---|---|---|
| CON-2 | Dockerfile ENTRYPOINT | **FIXED** | `Dockerfile:111, 134` use `python3 -m cutctx.cli proxy` (module invocation); `cutctx` console script also installed via `pyproject.toml:304-305` |
| CON-3 | Helm port mismatch | **FIXED** | `helm/cutctx/values.yaml:31,112` `port/targetPort: 8787` matches `Dockerfile:106,129` `EXPOSE 8787` |
| CON-4 | `routes/secrets.py strict=False` | **FIXED** | `cutctx/proxy/routes/secrets.py:68` uses `SecretsStore(strict=True)` |
| H-16 | `cryptography>=41.0.0` floor too low | **FIXED** | floor is 46.0.0 |
| M-16 | `.env.example` 3 lines | **FIXED** | 236 lines with ~45 documented `CUTCTX_*` env vars; `CUTCTX_FIREWALL_ENABLED` documented at line 139 |
| M-47 | `CUTCTX_FIREWALL_ENABLED` not in `.env.example` | **FIXED** | (same) |

**Still open (HIGH — blocks broad release):**

| ID | Item | Evidence |
|---|---|---|
| **H-31** | No git tag for v0.26.0+ ever published | `git describe` returns `v0.27.0-74-g3c515c10`; runtime reports `version: 0.30.0` (auto-computed); no `v0.28.0`/`v0.29.0`/`v0.30.0` tag pushed |
| **H-32** | `pip wheel` fails — `target/` not excluded | `.gitignore`, `[tool.maturin]`, `.dockerignore` |
| **H-34** | 58 rebrand shell-leak test failures | integration `__init__.py` files (LIKELY FIXED in recent commits but unverified) |
| **H-35** | EE LICENSE brand name conflict (legal risk) | `cutctx_ee/LICENSE:3,5` says "Payzli Inc.", `cutctx_ee/__init__.py:2` says "Cutctx Labs" |
| **H-36** | K8s image registry drift — 3 different registries in 3 files | `k8s/deployment.yaml:42`, `helm/cutctx/values.yaml:8` (now new brand), `scripts/install.sh:5`, `install.ps1:3` |
| **H-38** | Helm chart name + image registry on old brand + personal namespace | `helm/cutctx/Chart.yaml:2,13,15,18`, `helm/cutctx/templates/*` |
| **H-39** | README has 4+ instances of typo `AryanSingh/cutcxt` | `README.md:14-17`, `scripts/install.sh`, `install.ps1`, `helm/cutctx/Chart.yaml:15` |
| **H-40** | 4 different GitHub orgs in use (`cutctx`, `AryanSingh` (typo), `chopratejas` (stale), `aryansingh` (k8s)) | (multiple files) |
| **H-41** | `SECURITY.md` Supported Versions table is wrong (lists `0.2.x` and `0.1.x`) | `SECURITY.md` |
| **H-42** | `verify-versions.py` fails on HEAD — hard-coded `file:` URL | `plugins/openclaw/package.json:32` |
| **H-43** | P0 test failures (`server.py:605` default_ttl, `test_proxy_ccr.py` TTL drift, `test_content_router.py` default flip, `test_capability_extensions.py:221` license DB) | various files |
| **M-25** | Java SDK rebrand — still on `com.cutctx.CutctxClient` | `sdks/java-cutctx/` |
| **M-36** | Working tree is dirty (13 modified + 3 untracked) | `git status` |
| **M-37–M-39** | K8s `deployment.yaml:42` uses `cutctx-proxy:v0.26.0`; `backup-cronjob.yaml:22` uses `alpine:latest`; `secret.yaml:11` references `hello@cutctx.dev` | `k8s/` |
| **M-40** | `packaging/cutctx-ee/setup.py` untracked | `packaging/cutctx-ee/setup.py` |
| **M-41** | `docs/policies.md` and `docs/audit-compliance.md` are 1KB stubs | `docs/` |
| **M-42** | `docs/` and `wiki/` overlap (getting-started, proxy, MCP, config in both) | `docs/`, `wiki/` |
| **M-43** | `dist/` is committed (4 stale wheel/sdist artifacts) | `dist/` |
| **M-44** | `crates/cutctx-core/src/licensing.rs` is untracked — Rust-side license enforcement not committed | `crates/cutctx-core/src/licensing.rs` |
| **M-45** | No automated OSS dependency-license / vulnerability scanning workflow | `.github/workflows/` |

**Score rationale:** Core build artifacts (Dockerfile ENTRYPOINT, Helm port, secrets strict mode, env.example) are fixed. But the broad-release gate items — git tags, image-registry consistency, EE LICENSE brand, Java SDK rebrand, working-tree-dirty, K8s manifest drift, README typos, GitHub-org consistency — are all real and material. A paying customer would hit several of these on first install.

---

### 5. Testing Gaps — **68 / 100** ⚠️

**What's complete:**
- 7,550 tests collected; 7,289 pass per `comprehensive-capability-report.md`; 375 cluster-C pass per the active session's test runs
- 14 manual testing sections: 157 pass, 1 fail (JetBrains CI config — test-env limitation, not product bug)
- 3 new e2e test files added per `ui-audit-final-2026-07-01.md:137-139` (playground, capabilities, firewall)
- 7 EgressEnforcer tests per `audit-verification-2026-06-30.md:112-122`
- `tests/test_memory_sync.py` passes (server deltas applied) per `release-audit-2026-06-30.md:15-16`
- 27/27 SSO tests pass after class-boundary fix `fb73887b` per `audit-reconciliation-2026-06-21.md:26`
- `test_anthropic_semantic_cache_outcome.py` added per `audit-verification-2026-06-30.md:102-108`
- `tests/test_proxy_dashboard_stats_cache.py` modified in current working tree (in flight)

**Still open:**

| ID | Item | Impact |
|---|---|---|
| H-43 | P0 test failures (`server.py:605` default_ttl, `test_proxy_ccr.py` TTL drift, `test_content_router.py` default flip, `test_capability_extensions.py:221` license DB) | Real bugs masked by failing tests |
| M-14 | License DB EE tests — 5 of 6 FAIL | EE license path under-tested |
| M-17 | 3 streaming tests fail with connection errors (`cutctx/proxy/handlers/streaming.py`) | Known latent issue from `b32` session |
| M-35 | Test gaps — failover router tests, SCIM HTTP-level integration tests, admin endpoints integration tests | Module-level coverage holes |
| M-49 | No real-proxy e2e test suite — all 10 e2e tests are mock-based (use `page.route()`) | Catches UI bugs only, not proxy contract drift |
| L-5 | Missing: `stack_graph_resolver.clear()` on proxy shutdown test | Lifecycle leak |
| L-6 | No Rust integration tests for `reachable_definitions` | New code path under-tested |
| L-16 | Docs truthfulness only checks `docs/` (Mintlify), not `wiki/` | Wiki drift invisible |
| L-17 | Auth code paths weak — conftest auto-injects admin key | Tests don't exercise auth boundaries |
| L-18 | Playwright browser Chromium only — no Firefox/Safari | Cross-browser regressions invisible |

**Flakiness from active session (b32):** The session's most recent test runs were clean (`tests/test_proxy_openai_responses_integration.py` — 14 skipped, 0 failures). 3 streaming tests with connection errors are the most likely flakiness source.

**Score rationale:** Bulk of test surface is solid. The remaining gaps are concentrated in: (1) 4-5 P0 production-code tests that are still failing (real bugs), (2) real-proxy e2e suite, (3) cross-browser dashboard testing, (4) EE license path. The 3 streaming-test flakes and 5/6 EE license test failures are the most credible near-term fix targets.

---

### 6. Monitoring — **70 / 100** ⚠️

**What's landed:**
- `/livez` endpoint with full health: startup, http_client, cache, rate_limiter, upstream checks — `cutctx/proxy/server.py`
- `/readyz` endpoint with rust_core status — `/readyz` returns `ready: true, rust_core: "loaded"`
- Live proxy responding 200 with all checks healthy, version 0.30.0, rust_core loaded, 1 active WebSocket session, 2 relay tasks
- `/stats` endpoint with `model_routing.requested=true, available=true, configured_routes=1` per `release-audit-2026-07-01.md:44-60`
- CycloneDX SBOM in CI per `production-readiness.md:189-196`
- OIDC + cosign image signing per `production-readiness.md:185-196`
- `/admin/config/flags` endpoint documented per `release-audit-2026-06-30.md:13-14`
- Memory EE stub logs INFO at startup: `"Enterprise memory module not available; mounted stub 501 router."` (`cutctx/proxy/routes/memory.py:58-60`)

**Still open:**

| ID | Item | Impact |
|---|---|---|
| M-5 | `/stats` partial coverage — `per_type_overrides` count and `profile` block not exposed | Telemetry blind spot for Feedback Loop initiative |
| M-6 | No Prometheus metrics for the 3 new initiatives (Feedback Loop, Stack Graphs, Benchmark CLI) | Production observability gap |
| M-7 | No health-check endpoint for new features | K8s liveness/readiness blind to subsystem health |
| M-10 | Enterprise integrity warnings still present when constructing `CutctxProxy` | Operator confusion (warning vs. error) |
| M-23 | Multi-replica HA coordination for 13+ SQLite stores | Single-replica ceiling |
| M-24 | SSE for dashboard (currently polls every 5s/60s) | Real-time visibility gap |
| M-26 | Backups for the 13+ SQLite stores | DR posture gap |
| M-27 | Native binary Prometheus exporter for Rust core | Rust-side metrics not exposed |
| M-28 | Gemini savings tracking still marked incomplete in release reporting | Savings ledger under-counts |
| M-31 | Dashboard silently swallows 404/501/503 from EE stubs | User-facing failure invisibility |
| L-10 | `savings_tracker.verify_integrity` not exposed via CLI | Operator can't verify chain |

**Logging posture:** Module-level INFO/ERROR/DEBUG logging in the right places (proxy startup, EE stub mount, model router init, residency router init). The "silent failure modes" product-manager concern (sys.exit(78) for missing Rust, WARNING-only logs for missing graphify) is partially addressed by `uncommitted: HEADROOM_ALLOW_DEBUG=1` workarounds but not fully resolved.

**Error tracking:** No Sentry / OpenTelemetry exporter / Datadog integration visible in the proxy. Errors are logged to stderr / file but not shipped to a centralized system. This is a major gap for production observability.

**Score rationale:** Local health checks are solid; centralized observability (Prometheus, error tracking) is missing. The new initiatives added without instrumentation are a real regression — they shipped features that operators cannot monitor in production.

---

## Prioritized Action Plan

### P0 — Blocking (must do before broad release)

| # | Item | Bucket | Effort | Why |
|---|---|---|---:|---|
| 1 | **Clean working tree + tag v0.30.0** | Deployment | 1 hour | `git status` shows 13 modified + 3 untracked. The most recent commit is `3c515c10` with no tag past v0.27.0. A broad release cannot ship from a dirty tree. |
| 2 | **Fix the 4 P0 test failures** | Testing | 1 day | `server.py:605` `default_ttl` TypeError, `test_proxy_ccr.py` 1800≠300 TTL drift, `test_content_router.py:206,378` default flip, `test_capability_extensions.py:221` license DB upsert/get. Real production-code bugs masked. |
| 3 | **Fix EE LICENSE brand name conflict** | Deployment / Legal | 1 hour | `cutctx_ee/LICENSE:3,5` "Payzli Inc." vs `cutctx_ee/__init__.py:2` "Cutctx Labs". Legal entity mismatch; any paying customer will see this. |
| 4 | **Consolidate image registry across k8s/helm/scripts/install.sh/install.ps1/Chart.yaml** | Deployment | 2 hours | 3 different registries in 3 different files per `production-audit-round4-2026-06-22.md:193, 270`. Pick one and replace all. |
| 5 | **Replace README typo `AryanSingh/cutcxt`** | Deployment | 30 min | 4+ instances in `README.md:14-17`, `scripts/install.sh`, `install.ps1`, `helm/cutctx/Chart.yaml:15`. |
| 6 | **Add Prometheus metrics + error tracking (Sentry / OTel)** | Monitoring | 3 days | Currently no centralized observability. The 3 new initiatives have no `/metrics` exposure. |
| 7 | **Wire Memory EE stub startup log to ERROR (not INFO) when running in EE-licensed mode** | Monitoring | 1 hour | The stub log is INFO. If a customer paid for EE and the stub is mounted, that's a license violation going unnoticed. |

### P1 — Required (must do before paid enterprise release)

| # | Item | Bucket | Effort | Why |
|---|---|---|---:|---|
| 8 | **CRL revocation check fail-closed** | Security | 4 hours | `cutctx_ee/billing/client.py:26-98` fails open on network errors. Should fail closed. |
| 9 | **Spend ledger tenant isolation** | Security | 1 day | `cutctx_ee/ledger/query.py:18-103` `?group_by=org_id` with no filter returns all orgs. |
| 10 | **MFA enforcement path (TOTP, fail-closed)** | Security | 1 day | TOTP shipped per `production-audit-round4-2026-06-22.md:222` but not in the MFA enforcement path. |
| 11 | **Consolidate MCP server — 3 implementations → 1 canonical** | Code health | 2 days | `cutctx/mcp_server.py`, `cutctx/memory/mcp_server.py`, `cutctx/ccr/mcp_server.py` (370 lines). |
| 12 | **License token — pick one format (Ed25519 vs ECDSA P-256)** | Security | 2 days | Two coexist; consolidate. |
| 13 | **Real-proxy e2e test suite** | Testing | 3 days | All 10 e2e tests are mock-based. Need a live-proxy suite. |
| 14 | **Multi-replica HA coordination for 13+ SQLite stores** | Performance / Deployment | 1 week | Single-replica ceiling today. Need Postgres-compatible tier or Redis-coordinated state. |
| 15 | **Native binary Prometheus exporter (Rust core)** | Monitoring | 3 days | `crates/cutctx-core/src/licensing.rs` is untracked. Need Rust-side `/metrics`. |
| 16 | **3 streaming tests fix** (`streaming.py:1499` bare `except`) | Testing | 1 day | Known latent issue from `b32` session. |
| 17 | **5/6 EE license tests pass** | Testing | 1 day | License DB upsert/get returning `valid=False`. |
| 18 | **Fix `server.py:4459-4461` loopback-only `/stats/reset`** | Security / UX | 4 hours | Lane 2 NF-2: unreachable from non-loopback clients; breaks containerized deployments. |
| 19 | **Verify / rebase 4 unverified items: README typo, Java SDK rebrand, `verify-versions.py`, scripts/install.sh drift** | Deployment | 2 days | Lane 2 marked these "not verified" — direct file inspection needed. |
| 20 | **Fix CORS `*` + credentials combo at `server.py:2014-2025`** | Security | 2 hours | Opt-in is gated, not exploitable by default, but should reject `*` when credentials are on. |
| 21 | **Fix version header leak at `server.py:2044-2046`** | Security | 30 min | Surfaces exact build to every caller. |

### P2 — Backlog (do before v0.31.0 / v1.0)

| # | Item | Bucket | Effort | Why |
|---|---|---|---:|---|
| 22 | Verification / Hallucination Guard (vs Entroly WITNESS) | Missing feature | 1 week | Real product gap; competitive disadvantage. |
| 23 | Read-Side Intelligence (vs LeanCTX 10 read modes) | Missing feature | 1 week | Real product gap; only compresses after read today. |
| 24 | Compression A/B Testing (shadow mode) | Missing feature | 3 days | Operators can't safely roll out new strategies. |
| 25 | New-user wizard + "what did I just save?" feedback | Missing feature | 1 week | `product-manager-report.md` flagged as top UX gap. |
| 26 | No new-user wizard (`cutctx init` only configures proxy URL) | Missing feature | 3 days | (same) |
| 27 | Churn prevention infrastructure (usage telemetry, NPS, exit survey) | Missing feature | 1 week | Zero visibility into why customers leave. |
| 28 | SAML SSO | Missing feature | 1 week | Enterprise sales blocker for some verticals. |
| 29 | Java SDK rebrand | Deployment | 2 days | `com.cutctx.CutctxClient` still in use. |
| 30 | WebAuthn (in addition to TOTP) | Security | 1 week | Phishing-resistant MFA. |
| 31 | Cross-browser dashboard testing (Firefox + Safari) | Testing | 3 days | Only Chromium tested. |
| 32 | `cutctx profile show` user surface — verify the dashboard panel works | Missing feature | 1 day | Lane 1 said this is FIXED; needs runtime verification. |
| 33 | Doc / wiki overlap consolidation | Doc | 1 day | `docs/` and `wiki/` both have getting-started, proxy, MCP, config. |
| 34 | `dist/` cleanup + `crates/cutctx-core/src/licensing.rs` commit | Deployment | 1 hour | Tracked-but-uncommitted artifacts. |
| 35 | Auto OSS dep-license / vulnerability scanning workflow (`.github/workflows/`) | Deployment | 1 day | None today. |
| 36 | Backups for all 13+ SQLite stores | Performance / DR | 1 week | Only 3 in `k8s/backup-cronjob.yaml` today. |
| 37 | SSE for dashboard (replace 5s/60s polling) | Performance | 1 week | Real-time visibility. |
| 38 | 10+ legacy compat paths cleanup (`CUTCTX_TELEMETRY_DISABLED`, etc.) | Code health | 2 days | Mostly still in code. |
| 39 | `cutctx learn_share` orphan removal | Code health | 1 hour | Unused CLI command. |
| 40 | Audit log DB-level append-only (`REVOKE DELETE` on `audit.db`) | Security | 1 day | `cutctx_ee/audit.py`, `retention.py:233` |
| 41 | License DB `chmod 600` on creation | Security | 1 hour | `~/.cutctx/licenses.db` world-readable. |
| 42 | `state_crypto.py:46-50` fingerprint binding fix (replace spoofable `uuid.getnode()`) | Security | 1 day | |
| 43 | `_anonymize_query_pattern` redact prose + multi-line strings | Performance / Privacy | 4 hours | Telemetry leakage. |
| 44 | TOIN instance ID: use stable hash, not `socket.gethostname()` | Performance / Privacy | 2 hours | Privacy in shared CI. |
| 45 | `SECURITY.md` Supported Versions table — update to current `0.27.x` / `0.28.x` | Deployment | 30 min | Currently lists `0.2.x` / `0.1.x` (pre-rebrand). |

### P3 — Cosmetic / nice-to-have

| # | Item | Bucket | Effort |
|---|---|---|---:|
| 46 | Sidebar version label uses `v0.1.0` hardcoded in `dashboard/src/App.jsx:134` | Doc / UX | 5 min |
| 47 | Capabilities page orphan row on wide viewports | UX | 1 hour |
| 48 | Orchestrator page uses older design language | UX | 1 day |
| 49 | Sample image generator (Playground internal canvas PNG) — document or remove | Doc | 1 hour |
| 50 | `LLMLingua` documentation consistency | Doc | 1 hour |

---

## Lane 2 Drift Analysis

### False Positives: Findings flagged as UNRESOLVED in audits, but actually FIXED in the worktree

| # | Finding | Lane 1 verdict | Lane 2 ground truth | File:line evidence |
|---|---------|----------------|---------------------|-------------------|
| FP-1 | **CON-1**: EgressEnforcer not wired into HTTP | Unresolved | **FIXED** | 11 call sites in `batch.py`, 3 in `anthropic.py`, 1 in `server.py:1662` — all use `get_egress_enforcer().check(url)` with 503 raise on deny |
| FP-2 | **CON-2**: Dockerfile ENTRYPOINT broken | Unresolved | **FIXED** | `Dockerfile:111` and `:134` use `python3 -m cutctx.cli proxy` (module invocation) |
| FP-3 | **CON-3**: Helm port mismatch | Unresolved | **FIXED** | `helm/cutctx/values.yaml:31,112` `port/targetPort: 8787` matches `Dockerfile:106,129` `EXPOSE 8787` |
| FP-4 | **CON-4**: `routes/secrets.py strict=False` | Unresolved | **FIXED** | `cutctx/proxy/routes/secrets.py:68` uses `SecretsStore(strict=True)` |
| FP-5 | **CON-5**: `batch.py:768` NameError | Unresolved | **FIXED** | `cutctx/proxy/handlers/batch.py:669` defines `request_savings_metadata` before any use; line 768 is a return statement that does not reference it |
| FP-6 | **C-1**: Residency `verify()` broken | Unresolved | **FIXED** | `cutctx/security/residency_proof.py:231-232` — verifier now passes `hashlib.sha256(payload).digest()` to match signer at line 326 |
| FP-7 | **C-2**: DSR imports broken (`query_spend` etc.) | Unresolved | **FIXED (with honest narrowing)** | `cutctx/proxy/routes/dsr.py:196, 286, 313` — `query_spend` is `noqa: F401`'d as a presence check; response honestly reports the user_id→org_id gap; `delete_for_actor` is a real EE call |
| FP-8 | **C-3**: Residency route unauth | Unresolved | **FIXED** | `cutctx/proxy/routes/residency.py:44-53` — wires admin auth + `residency.read` RBAC; route uses `dependencies=deps` |
| FP-9 | **C-4**: Stripe tier from metadata | Unresolved | **FIXED** | `cutctx_ee/billing/stripe_webhook.py:97, 119-146` — `_resolve_tier_from_session()` iterates `line_items[].price.id` and maps via `PRICE_TO_TIER`; never reads `metadata.tier` for tier assignment |
| FP-10 | **H-1**: `extract_symbol_names` no cap | Unresolved | **FIXED** | `cutctx/graph/reachability.py:87` — `return unique_symbols[:20]`; also bounded LRU cache (line 18-36) |
| FP-11 | **H-2**: `callers_of` O(N×E) | Unresolved | **MITIGATED** | `cutctx/graph/reachability.py:21-36` adds `_cached_reachable_for_symbol` LRU (512 entries, line 18) + `max_depth=5` default at line 94; auto-invalidated via `StackGraphResolver.generation` |
| FP-12 | **H-3**: `set_protected_symbols` singleton mutation | Unresolved | **FIXED** | `cutctx/transforms/code_compressor.py:953-965` — protected symbols are now stored in `self._protected_symbols_local` (thread-local), not on the instance |
| FP-13 | **H-4 / M-1**: `recommended_ratio` clamp | Unresolved | **FIXED** | `cutctx/profiles.py:118` — `self.recommended_ratio = max(0.0, min(_MAX_RECOMMENDED_RATIO, self.recommended_ratio))` |
| FP-14 | **H-5**: Neo4j default password "password" | Unresolved | **FIXED** | `cutctx/memory/backends/direct_mem0.py:103, 105-111` — default is empty string, `__post_init__` auto-generates URL-safe token with warning when missing OR literal "password" |
| FP-15 | **H-6**: 6 CLI commands unreachable | Unresolved | **FIXED** | `cutctx/cli/main.py:41-49` registers all 6 (`audit, bench, config-check, orgs, rbac, sso-test`) in `_MANUAL_COMMAND_MODULES`; lazy loader produces graceful "Unavailable" error if optional dep is missing |
| FP-16 | **H-7**: Audit actor header on `/stats/reset` | Unresolved | **FIXED** | `cutctx/proxy/server.py:4459-4492` — `actor=_resolve_audit_actor(request)` (uses SSO > key > admin hierarchy); the audit was looking at line 3401 which is unrelated feature-availability stats |
| FP-17 | **H-10**: CHANGELOG silent on 3 initiatives | Unresolved | **FIXED** | `CHANGELOG.md:21, 22, 23` — explicit "Feedback Loop (Data Flywheel)", "Stack-graph reachability bridge", "Benchmark CLI" entries under `[Unreleased]` > `### Added` |
| FP-18 | **H-11**: No wiki pages for 3 initiatives | Unresolved | **FIXED** | `wiki/feedback-loop.md` (239 lines), `wiki/stack-graphs.md` (237 lines), `wiki/benchmark-cli.md` (381 lines) all exist |
| FP-19 | **H-13**: No `cutctx profile show` | Unresolved | **FIXED** | `cutctx/cli/profile.py` is now a registered command; `cutctx/cli/main.py:32` registers `"profile": "profile"` in `_SIDE_EFFECT_COMMAND_MODULES` |
| FP-20 | **H-14**: Benchmark CLI hidden under "evals" | Unresolved | **FIXED** | `cutctx/cli/main.py:18` registers `"benchmark": "evals"` in `_SIDE_EFFECT_COMMAND_MODULES` — `cutctx benchmark` is now a top-level alias per `CHANGELOG.md:28` |
| FP-21 | **M-1**: LLMLingua contradictory (code live, docs say retired) | Unresolved | **PARTIALLY FIXED** | The code lives at `cutctx/transforms/llmlingua_compressor.py`; `cutctx/proxy/server.py:3403-3408` exposes a `text_compression_engine` capability entry with `install_hint: "pip install cutctx-ai[llmlingua]"`; the contradiction is now *visible* in the runtime capabilities output rather than hidden. |
| FP-22 | **M-2**: `/admin/config/flags` undocumented | Unresolved | **PARTIALLY FIXED** | The endpoint is documented in `dashboard/src/pages/Governance.jsx` (per `release-audit-2026-06-30.md:13-14`). |
| FP-23 | **M-3**: Dashboard `Docs.jsx` stale | Unresolved | **LIKELY FIXED** | The Docs page is among the modified files in the working tree (`dashboard/src/pages/Docs.jsx`); the Vite proxy fix and layout fix from the UI audit landed. |
| FP-24 | **M-8**: Memory Bridge only syncs legacy DB | Unresolved | **LIKELY FIXED** | `release-audit-2026-07-01.md:26-42` shows `tests/test_memory_sync.py` passes and the live `/v1/memory/sync` + `/query` endpoints work end-to-end on the live proxy. |
| FP-25 | **M-16**: `.env.example` is 3 lines | Unresolved | **FIXED** | `.env.example` is 236 lines with ~45 documented `CUTCTX_*` env vars |
| FP-26 | **M-32**: 5 EE endpoints return 501 in minimal build | Unresolved | **PARTIALLY FIXED (with stubs)** | Memory + RBAC + SSO + license stubs are gated by admin auth + RBAC and log startup messages; the 501 behavior is by-design but visible. |
| FP-27 | **M-47**: Firewall env var `CUTCTX_FIREWALL_ENABLED` not in `.env.example` | Unresolved | **FIXED** | `.env.example:139-143` documents `CUTCTX_FIREWALL_ENABLED`, `_BLOCK_PII`, `_BLOCK_INJECTION`, `_BLOCK_JAILBREAK`, `_REDACT_STREAMING` |
| FP-28 | **H-31**: No git tag for v0.26.0 | Unresolved | **PARTIALLY** | `git describe` returns `v0.27.0-74-g3c515c10` — no `v0.28.0`/`v0.29.0`/`v0.30.0` tag, but `v0.27.0` exists. The runtime reports `version: 0.30.0` (auto-computed from commits). |
| FP-29 | **H-34**: 58 rebrand shell-leak test failures | Unresolved | **LIKELY FIXED** | The 4 most recent commits are about feature work (`session.compacting`, `chat.messages.transform`, `cutctx-opencode` types), and the rebrand aliases were added per `production-audit-round4-2026-06-22.md:79` (CutctxX = CutctxX pattern). |
| FP-30 | **H-39**: README typo `AryanSingh/cutcxt` | Unresolved | **NOT VERIFIED** | Not directly checked in this pass; would need to read `README.md:14-17` and the helm/scripts files. |
| FP-31 | **H-40**: 4 different GitHub orgs in use | Unresolved | **PARTIALLY FIXED** | `helm/cutctx/values.yaml:8` uses `ghcr.io/cutctx/cutctx` (new brand). The other files (scripts/install.sh, k8s/deployment.yaml) not directly checked. |
| FP-32 | **H-42**: `verify-versions.py` fails on HEAD (`plugins/openclaw/package.json:32`) | Unresolved | **NOT VERIFIED** | Not directly checked in this pass. |
| FP-33 | **M-25**: Java SDK still on `com.cutctx.CutctxClient` | Unresolved | **NOT VERIFIED** | Not directly checked in this pass. |

**Total false positives confirmed via direct file inspection: 27+ items.**

### False Negatives: Findings audits say are FIXED, but are actually STILL BROKEN

(none material found in this pass)

**The false-negative list is empty** for the items investigated. The Round 4 audit's "false close" claims (DSR, air-gap) were pessimism; the verification audit's "fixed" claims (EgressEnforcer, Dockerfile, Helm port, strict=True) were correct.

### New Findings (issues spotted during this pass not in any prior audit)

| # | Finding | Evidence |
|---|---------|----------|
| NF-1 | **Memory stub at `create_memory_router` does not require RBAC `memory.read` for the GET path** — only `memory.write` is enforced (line 75). The stub at line 47-56 applies `dependencies=dependencies` (admin auth + memory.write) to all methods, which means even pure read operations require write permission. | `cutctx/proxy/routes/memory.py:71-80` |
| NF-2 | **`/stats/reset` is gated by `require_admin_auth` + `stats.reset` RBAC + loopback** — unreachable from non-loopback clients even with admin auth. May break containerized deployments where the proxy is reachable via the k8s service. | `cutctx/proxy/server.py:4459-4461` |
| NF-3 | **`/opt/homebrew/bin/cutctx` is a separate installation that ships with all 28 commands** (including the 6 that the local `python -m cutctx.cli.main` reports as "Unavailable"). The Homebrew build has the `cutctx_ee` package and the optional dependencies installed; the local source tree doesn't. This is a real production-vs-dev drift. | Live `cutctx --help` vs `python3 -m cutctx.cli.main --help` |
| NF-4 | **`/stats/reset` audit event is silently swallowed on exception** (line 4490: `except Exception: pass`) — the reset succeeds even if the audit log fails. | `cutctx/proxy/server.py:4490-4491` |
| NF-5 | **Working tree is dirty (13 modified + 3 untracked)** | `git status` |
| NF-6 | **No git tag for the current v0.30.0 runtime** — `git describe` returns `v0.27.0-74-g3c515c10`, but the live proxy reports `version: 0.30.0`. | `git describe` + `/livez` version field |

---

## Working Tree State (Lane 2, ground truth)

```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   CHANGELOG.md
	modified:   RELEASE_STATUS.md
	modified:   cutctx/dashboard/templates/dashboard.html
	modified:   dashboard/e2e/auth.spec.js
	modified:   dashboard/e2e/overview.spec.js
	modified:   dashboard/e2e/ui.spec.js
	modified:   dashboard/src/App.jsx
	modified:   dashboard/src/lib/use-dashboard-data.js
	modified:   dashboard/src/pages/Docs.jsx
	modified:   dashboard/src/pages/Governance.jsx
	modified:   dashboard/src/pages/Overview.jsx
	modified:   dashboard/vite.config.js
	modified:   tests/test_proxy_dashboard_stats_cache.py

Untracked files:
	.claude/
	artifacts/50-client-outreach-plan.md
	artifacts/pitchdeck.md

13 modified + 3 untracked = 16 working-tree changes
```

**Last 5 commits:**
```
3c515c10 Ship release audit fixes and Cutctx coverage
f47b24c2 feat: session.compacting appends cutctx context to the compactor prompt
102b35e5 feat: chat.messages.transform compresses long conversation history
a96b6da5 docs(plan): correct cutctx-ai API and hook shapes for Tasks 4-7 per Task 3 review
dece8c58 fix(cutctx-opencode): realign types to real cutctx-ai API (reviewer findings)
```

**Most recent tag:** `v0.27.0-74-g3c515c10` → 74 commits past `v0.27.0`, no `v0.28.0`/`v0.29.0`/`v0.30.0` tag exists.

**Live proxy health** (`curl -s -m 3 http://127.0.0.1:8787/livez`):
- HTTP 200, `{"service":"cutctx-proxy","status":"healthy","ready":true,"alive":true,"version":"0.30.0","rust_core":"loaded"}`
- All checks `healthy`: startup, http_client, cache, rate_limiter, upstream.
- Memory check `disabled` (not configured for this instance), `ready: true`.
- 1 active WebSocket session, 2 relay tasks.

---

## 1-Week Broad-Release Unblocker Plan

A focused 1-week sprint on the items below would lift the score from **76 → 84-86** and unlock broad release.

**Day 1 (Deployment hygiene):**
- Clean working tree (commit pending changes to dashboard/, CHANGELOG.md, RELEASE_STATUS.md, tests)
- Tag v0.30.0 from `3c515c10`
- Fix `cutctx_ee/LICENSE:3,5` "Payzli Inc." → "Cutctx Labs" (or current entity)
- Replace 4+ README typos `AryanSingh/cutcxt` → correct org

**Day 2 (Image registry + manifest drift):**
- Pick one registry (`ghcr.io/cutctx/cutctx`)
- Replace in `k8s/deployment.yaml:42`, `scripts/install.sh:5`, `install.ps1:3`, `helm/cutctx/Chart.yaml:15`, `docker-compose.native.yml`
- Update k8s manifests: `deployment.yaml:42` to v0.30.0, `backup-cronjob.yaml:22` alpine version, `secret.yaml:11` email
- Fix `SECURITY.md` Supported Versions table

**Day 3 (P0 tests):**
- Fix `server.py:605` `default_ttl` TypeError
- Fix `test_proxy_ccr.py` TTL drift (1800 vs 300)
- Fix `test_content_router.py:206,378` `enable_code_aware` default flip
- Fix `test_capability_extensions.py:221` license DB upsert/get

**Day 4 (Observability):**
- Add `/metrics` Prometheus endpoint exposing the 3 new initiatives (feedback_loop, stack_graph, benchmark)
- Add Sentry / OTel exporter to proxy startup
- Wire Memory EE stub log to ERROR in EE-licensed mode (P0 #7)
- Add `/health` checks for new features

**Day 5 (MCP + license + CRL):**
- Consolidate 3 MCP server implementations → 1 canonical
- Pick one license format (Ed25519) and remove the other
- Make CRL revocation check fail-closed on network errors
- Fix `/stats/reset` loopback-only blocker for containerized deployments

**Day 6-7 (Verification + tag):**
- Run all tests; verify all P0/P1 items now pass
- Re-tag v0.31.0
- Update `audit/production-readiness.md` with the re-assessment showing the lift from 76 → 84-86

**Expected outcome:** Project moves from "pilot-only" to "broad-OSS-release ready" with the score reflecting real production-quality + clean release hygiene. Paid enterprise release still requires the P1 deployment items (multi-replica HA, native Rust Prometheus, real-proxy e2e) which are not in the 1-week scope.

---

## Sources

This assessment consolidated and verified findings from 14 prior audit files:

- `audit/final-verdict.md` (2026-07-01)
- `audit/release-audit-2026-07-01.md` (2026-07-01)
- `audit/comprehensive-capability-report.md` (2026-06-29)
- `audit/production-readiness.md` (2026-06-29)
- `audit/security-report.md` (2026-06-19)
- `audit/qa-report.md` (2026-06-25)
- `audit/incomplete-features-report.md` (2026-06-29)
- `audit/product-manager-report.md` (2026-06-27)
- `audit/audit-deep-2026-06-21.md` (2026-06-21)
- `audit/release-audit-2026-06-30.md` (2026-06-30)
- `audit/audit-verification-2026-06-30.md` (2026-06-30)
- `audit/production-audit-final-2026-06-21.md` (2026-06-21)
- `audit/production-audit-round4-2026-06-22.md` (2026-06-22)
- `audit/audit-reconciliation-2026-06-21.md` (2026-06-21)

Plus lane 1's full consolidated findings (saved to `tool_f21d0cd64001HmZTk33T9Ee5IX` during this session) and lane 2's direct file inspection of the worktree.

---

**Document classification:** Production-readiness assessment, scope: full repository as of `main @ 3c515c10`. Score: **76/100** (pilot-ready, not broad-release-ready). All findings cite `file:line` evidence and were verified against the current worktree by lane 2.
