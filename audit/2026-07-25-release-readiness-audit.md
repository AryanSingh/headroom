# CutCtx — Independent Release-Readiness Audit

**Date:** 2026-07-25
**Branch / commit:** `main` @ `dcc5b9ee` ("docs: plan enterprise license portal validation")
**Working tree:** dirty — 5 modified, 8 untracked (audit docs + superpowers plans). Nothing was stashed, committed or discarded.
**Auditor:** Lead agent (Opus) + 7 delegated Haiku investigation agents
**Method:** Evidence-first. No prior status document, score, or completion claim was accepted without independent re-verification against the code and live runtime.

> **Standing note on prior documents.** This repo contains ~101 files in `audit/` plus 8 top-level status documents, with verdicts ranging from "Conditional Go, 92/100" to "62/100, early adopters only." Several are mutually contradictory. This audit treats all of them as *claims to be falsified*, not as inputs. Where I confirmed a prior finding, I say so. Where I refuted one, I say so explicitly (see §6, BLK-SEC-01).

---

## 1. Executive Summary

| | |
|---|---|
| **Release-readiness score** | **58 / 100** |
| **Confidence in this score** | **Medium-High** — quality gates and core runtime were executed directly; enterprise/EE, live-provider, IdP, and multi-platform paths remain unverified |
| **Recommended classification** | **HIGH RISK** |
| **Estimated remaining work** | **4–7 engineer-weeks** to reach *Ready with minor fixes*; **1–2 weeks** to reach a defensible *named-pilot* posture |

### Current status in one paragraph

CutCtx is a large, genuinely substantial system — not vapourware. The build is clean, 1,492 Rust tests and 9,036 Python tests pass, the proxy and CLI start and behave correctly, auth is properly enforced on protected routes, and the log-compression path really does achieve 96–97% token reduction. But the audit surfaced one reproducible correctness defect at the heart of the product, and a material gap between what the README advertises and what the system measurably delivers. Those two together — not the volume of open issues — are what drive the HIGH RISK classification.

### The three biggest risks

1. **The log compressor silently discards `FATAL`, `ERROR`, and `CRITICAL` lines** (BLK-01). This is directly reproducible and directly contradicts the README's headline demo caption: *"Live: 10,144 → 1,260 tokens — same FATAL found."* On my test the FATAL line was **not** found. The SRE-incident-debugging workload the README markets at 92% savings is precisely the workload this defect breaks.

2. **Published savings claims are not supported by the project's own telemetry** (BLK-02). README publishes 47–92%. The user's own `cutctx perf` output — 10,749 real requests, 925M → 918M tokens — shows **0.7%** actual realised savings. The gap is explainable (the README numbers describe eligible long-context workloads; most real traffic is short and bypassed), but that explanation appears in `artifacts/pitchdeck.md` and nowhere in the README. At $18k–$150k/yr price points this is commercial and legal exposure, not just a docs nit.

3. **`main` is red and CI would not catch most of it** (BLK-03, BLK-06). Three tests fail on `main` right now. Separately, CI does not run `cargo test`, dashboard tests, or the TypeScript SDK suite — roughly 1,800 passing tests provide *zero* regression protection because nothing executes them on merge.

### Shortest safe path to release

Fix BLK-01 (severity-aware line retention) → correct the README claims and add the scope caveat (BLK-02) → get `main` green and wire the orphaned suites into CI (BLK-03/06) → document the 109 undocumented env vars and write a restore runbook (BLK-04/05). Everything else can follow. Detail in §10.

---

## 2. Audit Scope and Evidence

### Applications and modules inspected

| Surface | Scale | Inspected |
|---|---|---|
| Python core (`cutctx/`) | 629 files | Yes |
| Enterprise (`cutctx_ee/`) | ~25 modules | Partial — code read, not runtime-verified (no EE licence) |
| Rust workspace (`crates/`) | 202 files, 4 crates | Yes — built + tested |
| Dashboard | React 19 + Vite SPA, 10 screens | Yes — built, linted, tested |
| Website (`website/`) | 9 pre-built static pages | Yes |
| SDKs | TypeScript, Python, Go, go-cutctx, java-cutctx | Yes (Java blocked) |
| Tests | 647 test files | Executed |
| Docs / marketing | README, PRODUCT_GUIDE, ENTERPRISE, wiki, artifacts | Yes |
| Infra | Dockerfile, compose, bake, k8s/, helm/, .github/workflows/ | Yes |

### Runtime environments used

- **User's macOS host** (via Desktop Commander) — the only environment with the real toolchain: cargo 1.96.0, node v22.22.3, and the project `.venv` (Python 3.12). All builds, test suites, and runtime verification ran here.
- **Linux sandbox** — used for static analysis only. `cargo`, `docker`, `go`, and `opencode` are all absent there, so no quality gate was run in the sandbox.

### Delegation

| Agent (Haiku) | Task | Lead verification |
|---|---|---|
| 1 | CLI command inventory (~130 commands/subcommands) | Spot-checked; accepted |
| 2 | Stub / TODO / dead-code sweep | Accepted; re-ranked severity |
| 3 | Static security audit | **Two findings overturned** — see below |
| 4 | Route / API / feature-flag inventory | Accepted; route auth re-verified independently |
| 5 | Prior-document claim extraction | Accepted as claims only |
| 6 | Dashboard + SDK + CI gates | Accepted; RSC applicability re-checked |
| 7 | Ops / deployment / docs review | Accepted; env-var counts spot-checked |
| 8 | Marketing-claim provenance | Accepted; corroborated against live `cutctx perf` |

### Where delegated findings were overturned by the lead

- **Agent 3 reported "2 HIGH npm vulns — DO NOT SHIP."** Re-verified: the advisory (GHSA-qwww-vcr4-c8h2) applies only to React Router **RSC mode**. The dashboard is a client-only SPA using `BrowserRouter`, with no `createServerRoute`, no SSR, and no RSC imports. **Not exploitable here.** Downgraded Critical → Low.
- **Agent 3 hypothesised, and a prior audit doc asserted, that "provider passthrough routes have NO auth — anyone on the network can make LLM calls."** Re-verified against `cutctx/proxy/client_auth.py:17-30`: `_require_key()` raises `ProxyClientAuthError` when the proxy is bound to a non-loopback host without `CUTCTX_PROXY_API_KEY`. Confirmed at runtime: `POST /v1/messages` returned **401**. **This prior finding is refuted.** Residual issue is narrower and lower severity (RISK-07).
- **Agent 6 reported the compression library returns 0% reduction, "gated behind a paid licence."** Re-verified: false. The 0% was a payload-shape artefact — the agent placed the payload in a user message, which the router correctly protects. Correctly-shaped tool-result logs compress at **96–97%** with no licence. However, re-testing surfaced the far more serious BLK-01.
- **mypy caveat, self-reported:** I ran `mypy cutctx` (498 errors). CI runs `mypy cutctx --ignore-missing-imports` (`ci.yml:100`), which is more permissive. My number is a stricter measure than the CI gate and should not be read as "CI is failing."

### Blocked by credentials or environment

Live provider calls (Anthropic/OpenAI/Bedrock/Vertex), SSO/OIDC against a real IdP, EE-licensed feature paths, Java SDK (no Maven), Docker/k8s deployment (no Docker in sandbox; not run on host), multi-platform installers (Windows/Linux), and load/performance testing. **None of these were assumed to pass.**

---

## 3. Module Status Matrix

| Module | Status | Evidence | Tests | Main Risks | Release Impact |
|---|---|---|---|---|---|
| Rust core (`cutctx-core`) | **Verified** | `cargo build --release` exit 0 (2m36s); `cargo test --workspace` 1,492 passed / 0 failed / 3 ignored | 1,492 | Not run in CI | Low |
| Rust proxy (`cutctx-proxy`) | **Verified** | Binary starts; `/healthz` → `{"ok":true}`; `/metrics` serves Prometheus | included above | Bedrock/Conversations routes disabled by default | Low |
| Python proxy | **Verified** | Starts clean, zero WARN/ERROR; all health endpoints 200; auth enforced (401 on `/stats`, `/admin/*`, `/v1/messages`) | in 9,036 | `/readyz` doesn't probe DB/backends | Medium |
| Compression — logs | **Broken** | 96–97% reduction achieved, **but FATAL/ERROR/CRITICAL lines dropped** (reproduced 4×) | pass, but don't cover this | Correctness / trust | **Critical** |
| Compression — JSON (SmartCrusher) | **Partial** | Realistic 100-result code-search tool payload returned `router:excluded:tool`, 0% reduction | pass in isolation | Flagship path didn't engage end-to-end | High |
| CCR (reversible retrieval) | **Verified** | Retrieval hash emitted in compressed output; `/v1/retrieve` requires auth, responds | pass | — | Low |
| Memory | **Implemented, unverified** | `cutctx memory stats` → 504 memories, 1.3MB, works | pass | EE memory service returns 501 in OSS (by design) | Low |
| CLI (~130 commands) | **Verified** | 8 read-only commands executed, all exit 0 with sensible output | pass | Mutating commands not exercised (deliberate) | Low |
| MCP server / gateway | **Implemented, unverified** | 8 tools registered with real handlers | pass | Not exercised via a live MCP client | Medium |
| Dashboard | **Verified** | lint exit 0 (`--max-warnings=0`), build exit 0, 13/13 tests pass, serves at `/dashboard` | 13 | Zero a11y affordances; tests not in CI | Medium |
| Website | **Partial** | 3 tests fail on `main`; inline checkout form present but tests assert removed link-based flow | 3 failing | `main` is red | High |
| Licensing / entitlements | **Implemented, unverified** | Ed25519 signed tokens; `cutctx license status` works; `seat_state.json` warns "plain JSON, not encrypted" | pass | Local tamper surface unverified at runtime | Medium |
| SDKs (TS/Py/Go) | **Verified** | TS 307 pass/33 skip; Py 14; Go 20; go-cutctx 8 | 349 | **None run in CI** | High |
| SDK (Java) | **Blocked** | Maven unavailable | 0 | Unknown | Medium |
| k8s / Helm | **Unverified** | Manifests read; probes, HPA, PDB, backup CronJob present | n/a | Never deployed in this audit | High |
| Migrations | **Broken (by absence)** | 5 raw `.sql` files, no runner, no ordering, no rollback | none | Data integrity on upgrade | High |
| CI/CD | **Partial** | 14 jobs; runs ruff/mypy/pytest/e2e | n/a | No cargo test, no dashboard test, no TS SDK test | High |

---

## 4. Feature Verification Matrix

| Feature | Expected Behaviour | Verification Performed | Result | Evidence | Risk |
|---|---|---|---|---|---|
| Log compression ratio | Large reduction on log tool output | `compress()` on 1,201-line log via tool_result | **Pass** — 97.1% | `compression_ratio=0.971`, 34,807 tokens saved | Low |
| Log compression **fidelity** | Preserve critical lines ("same FATAL found") | Injected FATAL at line 600, re-ran | **Fail** | `FATAL kept=False`; omission marker `[1168 lines omitted: 221 ERROR, 249 WARN, 731 INFO]` | **Critical** |
| Same, with ERROR marker | Preserve | Injected ERROR at line 600 | **Fail** | `kept=False`, ratio identical 0.971 | **Critical** |
| Same, with CRITICAL marker | Preserve | Injected CRITICAL at line 600 | **Fail** | `kept=False` | **Critical** |
| Same, with Python Traceback | Preserve | Injected `Traceback (most recent call last)` | **Pass** | `kept=True`, ratio 0.965 | — |
| `--accuracy-guard strict` | Verify critical identifiers preserved before forwarding | Re-ran with `CUTCTX_ACCURACY_GUARD=strict` | **No effect** | Byte-identical output, identical ratio 0.971 | **High** |
| JSON tool-output compression | SmartCrusher, "80–95%" | 100-object code-search result as tool_result | **Fail (0%)** | `transforms_applied=['router:excluded:tool']` | High |
| User-message protection | Do not compress user-authored text | Large JSON as plain user message | **Pass** | `router:protected:user_message`, 0% | — |
| CCR retrieval hash emitted | Originals retrievable | Inspected compressed output | **Pass** | `Retrieve more: hash=601157cc19c5980cbafcd2bd` | Low |
| Proxy startup | Clean start | `cutctx proxy --port 18787` | **Pass** | Zero WARN/ERROR in log | Low |
| Health `/healthz` `/livez` | 200 | curl | **Pass** | 200 | Low |
| Readiness `/readyz` | Reflect true readiness | curl + code read | **Partial** | Checks upstream only; not DB/Qdrant/Neo4j/Redis (`server.py:3799`) | High |
| Admin auth | Reject unauthenticated | `GET /admin/config/flags`, `GET /stats` | **Pass** | 401 "Invalid or missing admin credentials" | Low |
| Provider passthrough auth | Reject unauthenticated | `POST /v1/messages` | **Pass** | 401 — *prior "no auth" claim refuted* | Low |
| `/v1/compress` auth | — | POST unauthenticated on loopback | **Open on loopback** | 200 returned; by design for local-first | Medium |
| Rust proxy health/metrics | Serve | curl `/healthz`, `/metrics` | **Pass** | `{"ok":true,"service":"cutctx-proxy"}` + Prometheus output | Low |
| Dashboard serves | Load in browser | `GET /dashboard` | **Pass** | HTML served | Low |
| Website pricing checkout | Purchasable | Inspected `website/pricing/index.html` | **Partial** | Inline `<form id="cutctx-checkout-form">` present; 3 tests assert the *old* pitchtoship link flow | High |
| Realised fleet savings | 47–92% (README) | `cutctx perf` on real telemetry | **0.7%** | 10,749 requests, 925M → 918M tokens | **Critical (claims)** |

---

## 5. Quality-Gate Results

| Gate | Command | Exit | Result |
|---|---|---|---|
| Rust build (release) | `cargo build --workspace --release` | **0** | Success, 2m36s |
| Rust tests | `cargo test --workspace --no-fail-fast` | **0** | **1,492 passed, 0 failed, 3 ignored** |
| Python tests | `pytest tests/ -q --timeout=300` | **1** | **9,036 passed, 3 failed, 468 skipped** (489.63s) |
| Lint (Python) | `ruff check .` | **0** | All checks passed |
| Format | `ruff format --check .` | **1** | **5 files would reformat** (4 in `cutctx_ee/tests/`, 1 in `scripts/`) |
| Type check | `mypy cutctx` | **1** | **498 errors in 86 files** (579 checked). *CI uses `--ignore-missing-imports`; not directly comparable* |
| Dashboard lint | `npm run lint` | **0** | Clean (`--max-warnings=0`) |
| Dashboard build | `npm run build` | **0** | dist/ produced, largest chunk 82.44 kB gz |
| Dashboard tests | `npm test` | **0** | **13 passed** |
| TS SDK tests | `npm test` (sdk/typescript) | **0** | **307 passed, 33 skipped** |
| Python SDK tests | `pytest` (sdk/python) | **0** | 14 passed |
| Go SDK tests | `go test ./...` | **0** | 20 passed |
| go-cutctx tests | `go test ./...` | **0** | 8 passed |
| Java SDK | — | — | **BLOCKED** — Maven unavailable |
| npm audit (prod) | `npm audit --omit=dev` | 1 | 2 HIGH — react-router 7.18.0, GHSA-qwww-vcr4-c8h2. **Assessed not applicable** (SPA, no RSC) |
| npm audit (all) | `npm audit` | 1 | 8 HIGH total; adds `brace-expansion` (no fix available), `postcss` (fixable) — dev-only |
| pip-audit / cargo-audit | — | — | **BLOCKED** — not installed; CI does run `pip-audit --strict` (`ci.yml:365`) |
| Docker build | — | — | **NOT RUN** — Docker unavailable in sandbox, not attempted on host |
| k8s deploy validation | — | — | **NOT RUN** |

### The 3 Python failures — all in `tests/website/test_static_site.py`

```
test_pricing_routes_to_pitchtoship_without_payment_secrets      (line 69)
test_public_pages_keep_local_assets_and_semantic_entry_points   (line 256)
test_pricing_preserves_commerce_and_adds_recommendation_hierarchy (line 286)
```

**Root cause (verified):** commits `fea89479` "feat: keep CutCtx checkout inline" and `62e6a8ff` "fix: refresh CutCtx checkout form styles" moved the pricing page from external pitchtoship.com links to an inline `<form id="cutctx-checkout-form">`. The tests still assert the removed link flow and the old CSS cache-buster (`?v=20260721-platform`; the page now serves `?v=20260723-inline-checkout`). **This is test/implementation drift, not a broken checkout** — but `main` is red either way, and the checkout's actual functional behaviour is now covered by nothing that runs.

### CI coverage gaps (quoted from `.github/workflows/ci.yml`)

| Suite | Tests | In CI? |
|---|---|---|
| Python | 9,036 | **Yes** — sharded ×4 (`ci.yml:251`) |
| mypy / ruff | — | **Yes** (`ci.yml:95-100`) |
| pip-audit | — | **Yes** (`ci.yml:365`) |
| Docker native e2e | — | **Yes** (`ci.yml:526-575`) |
| **Rust** | **1,492** | **No** — only `maturin build`, never `cargo test` |
| **Dashboard** | **13** | **No** — `npm run build` runs; `npm test` never invoked |
| **TypeScript SDK** | **307** | **No** |
| **Go SDKs** | **28** | **No** |

**~1,840 passing tests provide no regression protection.**

---

## 6. Release Blockers

### BLK-01 — Log compressor discards FATAL / ERROR / CRITICAL lines
- **Severity:** Critical · **Component:** `cutctx/transforms/log_compressor.py` · **Release-blocking:** Yes
- **Description:** When compressing a large log tool-result, the compressor retains a head and tail window and elides the middle. Severity-bearing lines in the elided region are dropped, including the highest-severity line in the payload.
- **Evidence (reproduced 4×, deterministic, seed=7):** 1,201-line log, marker injected at line 600.

  | Marker | Preserved? | Ratio |
  |---|---|---|
  | `FATAL ... CRITICAL_MARKER_XYZ` | **No** | 0.971 |
  | `ERROR ... CRITICAL_MARKER_XYZ` | **No** | 0.971 |
  | `CRITICAL ... CRITICAL_MARKER_XYZ` | **No** | 0.971 |
  | `Traceback (most recent call last)` | Yes | 0.965 |

  Output tail: `[1168 lines omitted: 221 ERROR, 249 WARN, 731 INFO]\n[1201 lines compressed to 33. Retrieve more: hash=601157cc19c5980cbafcd2bd]`
- **Impact:** An agent debugging an incident through CutCtx receives a log with the root-cause line removed and 731 routine INFO lines retained. It directly contradicts the README demo caption *"same FATAL found"* and undermines the SRE-incident-debugging workload advertised at 92% savings.
- **Likely root cause:** Retention is positional (head/tail window), not severity-ranked. The severity regex exists — `log_compressor.py:306` matches `ERROR|FATAL|CRITICAL` — and the omission summary counts ERROR/WARN/INFO, so severity is *detected* but not used to pin lines into the retained set. FATAL/CRITICAL are additionally absent from the omission taxonomy, suggesting they fall through to an uncategorised bucket.
- **Mitigating factors (stated for fairness):** the elision is *disclosed* in-band, counts are reported, and a CCR retrieval hash is emitted, so the data is recoverable if the agent chooses to retrieve. This is degradation, not silent unrecoverable loss.
- **Remediation:** Pin all lines matching the existing severity regex into the retained set before positional windowing, with a cap and an explicit overflow marker. Add FATAL/CRITICAL to the omission taxonomy.
- **Verification after fix:** Property test — for any log containing ≥1 line at ERROR or above, the compressed output must contain that line or an explicit `[N severity-≥ERROR lines omitted]` marker naming the severity. Run against the four markers above plus a log with >100 ERROR lines.
- **Effort:** 2–4 days including tests.

### BLK-02 — `--accuracy-guard strict` has no effect at library level
- **Severity:** Critical · **Component:** accuracy guard · **Release-blocking:** Yes
- **Description:** README: *"`--accuracy-guard strict` (default in agent profiles) verifies that compressed output preserves critical identifiers, function names, and references before forwarding."* Setting `CUTCTX_ACCURACY_GUARD=strict` produced **byte-identical output** and an identical compression ratio (0.971) to the unset case, while a FATAL line was being dropped.
- **Evidence:** Two runs, same script, only env differing — `[default] ratio=0.971 FATAL kept=False` / `[strict guard] ratio=0.971 FATAL kept=False`.
- **Impact:** The advertised safety net does not engage on the library path — which is exactly the path that needs it given BLK-01. It may be wired only into the proxy/agent-profile path; that was not verified and must be.
- **Remediation:** Determine which paths the guard is wired into; either wire it into `compress()` or correct the documentation to scope the claim precisely.
- **Verification:** Guard enabled + BLK-01 payload must fail loudly or preserve the marker.
- **Effort:** 1–3 days (scoping-dependent).

### BLK-03 — Published savings claims contradicted by the project's own telemetry
- **Severity:** Critical (commercial/legal) · **Component:** README, PRODUCT_GUIDE, marketing · **Release-blocking:** Yes
- **Description:** README §Proof publishes 47%–92% under the heading *"Savings on real agent workloads."* The project's own `cutctx perf` output over **10,749 real requests** shows **925M → 918M tokens = 0.7% realised savings**. `audit/product-manager-report.md:159` independently records *"Fleet median: ~4.8%"*, and `:163-170` records tokbench finding fleet-level cost reduction *"within noise of native — not statistically significant"* with *"+0.9s per request (32% overhead)"*.
- **Reconciliation (important):** these measure different things. The README figures are per-request ratios on long-context eligible workloads; 0.7–4.8% is fleet-wide across traffic dominated by short turns where compression is deliberately bypassed. **Both can be true.** The problem is not that the numbers are fabricated — it is that the disclosure exists in `artifacts/pitchdeck.md:53` (*"Median production compression is 4.8% because most traffic is short"*) and in `wiki/benchmarks.md:158`, but **not in the README**, which is what buyers read.
- **Additional finding:** no reproducible artefact or script generates the four exact README numbers (17,765→1,408 etc.). They trace back to hand-written entries in `wiki/index.md:300-303`.
- **Impact:** At $18k–$150k/yr (`ENTERPRISE.md:114-117`) with ROI models built on the 60–95% figure, a customer measuring 0.7% has a misrepresentation argument.
- **Remediation:** (a) add a scope caveat directly beneath the README proof table; (b) commit a reproducible benchmark harness that regenerates the four numbers, or replace them with numbers that harness produces; (c) publish the fleet-median figure alongside.
- **Verification:** `make bench` (or equivalent) regenerates the published table within tolerance; legal/marketing sign-off on wording.
- **Effort:** 3–5 days.

### BLK-04 — `main` is red: 3 failing tests
- **Severity:** High · **Component:** `tests/website/test_static_site.py` · **Release-blocking:** Yes
- **Evidence / root cause:** see §5. Test/implementation drift from the inline-checkout migration.
- **Impact:** Cannot cut a release from a red `main`. More importantly, the checkout flow's real behaviour is now untested.
- **Remediation:** Update the three tests to assert the inline-form flow, and add a test that the inline checkout actually submits.
- **Effort:** 0.5–1 day.

### BLK-05 — ~1,840 tests exist but never run in CI
- **Severity:** High · **Component:** `.github/workflows/ci.yml` · **Release-blocking:** Yes
- **Evidence:** §5 table. No `cargo test`, no dashboard `npm test`, no TS SDK test job.
- **Impact:** A Rust core regression, a dashboard regression, or a TS SDK regression merges to `main` undetected. The Rust core is where compression correctness lives — the same area as BLK-01.
- **Remediation:** Add three CI jobs. All three suites already pass locally, so this is wiring, not fixing.
- **Effort:** 1–2 days.

### BLK-06 — No migration framework; no restore procedure
- **Severity:** High · **Component:** `sql/`, `k8s/backup-cronjob.yaml` · **Release-blocking:** Yes for any hosted/multi-tenant deployment
- **Evidence:** 5 raw `.sql` files with no runner, no ordering metadata, no version table, applied by hand via the Supabase SQL editor. SQLite uses `PRAGMA user_version` (`cutctx/storage/sqlite_schema.py:31`) but has no rollback path. A daily backup CronJob uploads 17 `.db` files to S3 — **with no documented or scripted restore.**
- **Impact:** Untested backups are not backups. Schema drift between an upgraded server and an older local DB has no guard.
- **Remediation:** Adopt a migration runner (or a documented, ordered, idempotent script with a version table); write and *rehearse* a restore runbook; add a startup schema-compatibility check that refuses to run against an incompatible DB.
- **Effort:** 1–2 weeks.

### BLK-07 — `/readyz` does not reflect real readiness
- **Severity:** High · **Component:** `cutctx/proxy/server.py:3799` · **Release-blocking:** Yes for k8s
- **Evidence:** `/readyz` calls `_check_upstream()` only. It does not probe SQLite, Redis (CCR backend), Qdrant, or Neo4j. `k8s/deployment.yaml` uses `/readyz` for the readiness probe.
- **Impact:** **This is the textbook silent-production-failure pattern.** Kubernetes routes traffic to a pod that reports ready while its datastore is unreachable; every request then fails at handler time.
- **Remediation:** Extend `/readyz` to probe each configured backend with a short timeout; keep `/livez` as process-liveness only.
- **Effort:** 2–3 days.

### BLK-08 — 109 undocumented environment variables
- **Severity:** High · **Component:** configuration · **Release-blocking:** Yes for self-hosting
- **Evidence:** 167 distinct `CUTCTX_*` variables read in code; 58 present in `.env.example`. Undocumented ones include security- and cost-relevant flags: `CUTCTX_ACCURACY_GUARD`, `CUTCTX_ALLOW_PRIVATE_UPSTREAM`, `CUTCTX_BUDGET_HARD_LIMIT`, `CUTCTX_COMPRESSION_MODE`, `CUTCTX_CODEX_WIRE_DEBUG`.
- **Impact:** Operators cannot know the security posture of their deployment. `CUTCTX_ALLOW_PRIVATE_UPSTREAM` in particular relaxes an SSRF boundary.
- **Remediation:** Generate a configuration reference from code; mark each var's default, scope, and security relevance.
- **Effort:** 3–5 days.

### BLK-09 — SmartCrusher did not engage on a realistic JSON tool payload
- **Severity:** High · **Component:** `cutctx/transforms/content_router.py:2752, 3165`
- **Evidence:** A 100-object, 44.5 kB code-search result delivered as a `tool_result` returned `transforms_applied=['router:excluded:tool']`, 0% reduction — while the README's flagship row is *"Code search (100 results) 17,765 → 1,408 = 92%."*
- **Impact:** The single most-advertised workload produced zero savings in an end-to-end test. Either the exclusion rule is too broad, or the README workload requires configuration the docs don't mention.
- **Remediation:** Determine the exclusion trigger (tool name allowlist? size/shape heuristic?), then either narrow it or document the prerequisite.
- **Effort:** 2–4 days investigation + fix.

### BLK-10 — Four-way version drift
- **Severity:** Medium · **Release-blocking:** Yes (release hygiene)
- **Evidence:** `pyproject.toml` = 0.31.0 · installed CLI reports **0.32.0** · `crates/cutctx-core/Cargo.toml` = **0.1.0** · `k8s/deployment.yaml:9` label = **0.29.0** (image tag v0.31.0) · `k8s/README.md:113` example = v0.29.0.
- **Impact:** Support and incident triage cannot establish what is actually deployed.
- **Effort:** 1 day.

### BLK-11 — mypy: 498 errors across 86 files
- **Severity:** Medium
- **Evidence:** `mypy cutctx` → 498 errors / 579 files checked. I sampled the largest cluster (`orchestrator_enabled`, `_model_router` "has no attribute", ~18 hits in `server.py`) and **confirmed these are false positives** — dynamic attributes on a non-slots dataclass, and every read site uses `getattr(..., default)`. Not a runtime bug. The remaining ~480 are unclassified.
- **Impact:** Type signal is unusable as a defect detector at this volume, so real type bugs hide in the noise.
- **Effort:** 1–2 weeks to burn down, or 2 days to baseline and ratchet.

### Non-blockers, recorded for completeness
- `ruff format`: 5 files need reformatting — 15 minutes.
- npm HIGH advisories: assessed **not applicable** (no RSC); `postcss` dev-only, fixable; `brace-expansion` has no fix. Track, don't block.
- `NotImplementedError` in `smart_crusher.py:273` (custom relevance override) and `learn/aggregate.py:104` (telemetry sharing) — both deliberate, both fail loudly. Correct behaviour.
- `~/.cutctx/seat_state.json` warns "plain JSON, not encrypted" — worth reviewing for licence-tamper resistance, but the licence itself is Ed25519-signed.

---

## 7. Work Required Before Release

### Critical — must fix

| # | Item | Skill set | Depends on | Acceptance criteria | Verification | Effort |
|---|---|---|---|---|---|---|
| C1 | Severity-aware line retention in log compressor | Rust/Python core | — | Any log with a line ≥ERROR yields that line, or an explicit severity-named omission marker | Property test over FATAL/ERROR/CRITICAL/Traceback + >100-error log | 2–4d |
| C2 | Wire or re-scope `--accuracy-guard` | Core + docs | C1 | Guard demonstrably alters output on a payload that would otherwise lose a critical line | Differential test guard on/off | 1–3d |
| C3 | Correct README savings claims + commit reproducible harness | PM + eng + legal | — | Published numbers regenerate from a committed command; scope caveat sits adjacent to the table | Run the harness; marketing sign-off | 3–5d |
| C4 | Green `main` | Any eng | — | Full `pytest` exits 0 | CI run | 0.5–1d |

### High — must fix

| # | Item | Skill set | Depends on | Acceptance criteria | Verification | Effort |
|---|---|---|---|---|---|---|
| H1 | Add cargo/dashboard/TS-SDK jobs to CI | DevOps | C4 | All four suites gate merges to `main` | Open a PR that breaks each; confirm CI fails | 1–2d |
| H2 | Migration runner + versioning | Backend | — | Ordered, idempotent, version-tracked; startup refuses incompatible schema | Upgrade + downgrade rehearsal on a seeded DB | 1–2w |
| H3 | Restore runbook, rehearsed | SRE | H2 | Documented restore executed end-to-end from an S3 backup | Timed recovery drill | 3–5d |
| H4 | Dependency-aware `/readyz` | Backend | — | Returns 503 when any configured backend is unreachable | Kill each backend, assert 503 | 2–3d |
| H5 | Configuration reference for all 167 env vars | Backend + docs | — | Every var documented with default, scope, security note | Diff generated list against code | 3–5d |
| H6 | Investigate `router:excluded:tool` on JSON payloads | Core | — | Realistic code-search tool output either compresses or the exclusion is documented | Re-run the BLK-09 repro | 2–4d |
| H7 | Reconcile all version strings | Any eng | — | Single source of truth; all manifests agree | `grep` audit in CI | 1d |

### Medium — fix unless consciously accepted

| # | Item | Effort |
|---|---|---|
| M1 | mypy baseline + ratchet (don't fix all 498 now) | 2d |
| M2 | Dashboard accessibility — aria labels, landmarks, keyboard nav (currently absent) | 1–2w |
| M3 | Auto-generate OpenAPI from FastAPI; retire the hand-written `artifacts/openapi-management.yaml` | 3d |
| M4 | Error tracking (Sentry or equivalent) — none currently | 2–3d |
| M5 | Java SDK: get Maven into CI or drop the SDK from the supported list | 2d |
| M6 | Delete or clearly mark the ~101 stale `audit/` docs and superseded top-level status files | 1d |
| M7 | Load/performance testing — never performed | 1w |

### Low — after release

`ruff format` on 5 files · `postcss` dev advisory · k8s README version examples · consolidate duplicate status docs · document the 4 unregistered CLI helper modules.

---

## 8. Risk Register

| Risk | Probability | Impact | Evidence | Mitigation | Release Decision |
|---|---|---|---|---|---|
| Agent misdiagnoses an incident because the error line was compressed away | **High** | **Severe** — trust-destroying, hard to detect | BLK-01, reproduced 4× | C1 + C2 | **Blocks** |
| Customer measures ~0.7% and disputes the contract | **High** | Severe — refund/legal | `cutctx perf`: 925M→918M over 10,749 reqs vs README 47–92% | C3 | **Blocks** |
| Regression in Rust core or dashboard merges undetected | **High** | High | ~1,840 tests outside CI | H1 | **Blocks** |
| Data loss with no working restore | Medium | **Severe** | Backup CronJob exists, restore does not | H2 + H3 | **Blocks** |
| Pod serves traffic while its datastore is down | Medium | High | `/readyz` probes upstream only | H4 | **Blocks** |
| Self-hoster deploys with an unsafe flag default | Medium | High | 109 undocumented env vars incl. `CUTCTX_ALLOW_PRIVATE_UPSTREAM` | H5 | **Blocks** |
| Flagship JSON workload delivers no savings for a customer | Medium | High | `router:excluded:tool` on realistic payload | H6 | **Blocks** |
| Enterprise buyer fails an a11y procurement review | Medium | Medium | Dashboard has zero aria labels/landmarks | M2 | Accept for pilot |
| Licence bypass by local tampering | Low-Med | Medium | Ed25519-signed, but `seat_state.json` unencrypted; not runtime-tested | Runtime test | Accept, test soon |
| React Router advisory becomes exploitable | Low | Medium | GHSA-qwww-vcr4-c8h2 — RSC-only; dashboard is a client-only SPA | Monitor; upgrade when non-breaking | Accept |
| Undetected production errors | Medium | Medium | No Sentry/error tracking | M4 | Accept for pilot |
| Support cannot determine deployed version | Medium | Low-Med | 4-way version drift | H7 | Accept short-term |
| Schema drift corrupts data on upgrade | Low-Med | **Severe** | No migration ordering or rollback | H2 | **Blocks** |

---

## 9. Readiness Scorecard

| Area | Score | Justification (verified evidence only) |
|---|---:|---|
| Core functionality | **5**/10 | Log compression works at 97%, proxy and CLI verified — but the flagship JSON path returned 0% and the compressor drops the highest-severity line. The core does something impressive and something wrong. |
| Architecture | **8**/10 | Clean Rust/Python split, layered router, real CCR reversibility, sensible OSS/EE boundary (501 stubs, not fake data). Builds cleanly in 2m36s. |
| Reliability | **6**/10 | 10,528 tests pass across languages; proxy starts clean. Offset by `/readyz` not reflecting reality and no migration/rollback story. |
| Performance | **4**/10 | Never load-tested by anyone. Internal tokbench recorded +0.9s/request (32% overhead). Prior audit notes missing indexes on `compression_episodes`. |
| Security | **7**/10 | Genuinely good: no committed secrets (`.env.local` gitignored, verified), no `eval`/`exec`/`shell=True`/unsafe `pickle`, Ed25519 licensing, loopback guard with Host validation, auth enforced on every protected route I probed (401s confirmed). Prior "unauthenticated passthrough" claim refuted. Docked for 109 undocumented security-relevant flags and no runtime authz testing. |
| Testing | **5**/10 | Impressive volume (10,528 passing) undermined by structure: 3 failing on `main`, 468 skipped, ~1,840 outside CI, and no test caught BLK-01. |
| UI and UX | **5**/10 | Dashboard builds clean, 10 screens, 13 tests pass, bundles small. But prior audits and this one find operability is hard and configuration is complex. |
| Accessibility | **2**/10 | Zero aria labels, landmarks, or keyboard navigation. Playwright green ≠ accessible. |
| Deployment | **6**/10 | Genuinely strong Dockerfile (multi-stage, distroless, non-root, healthcheck) and CI release gating (glibc audit, smoke-import in two containers). Docked hard for no migration runner and no rehearsed restore. |
| Observability | **5**/10 | Prometheus `/metrics` verified live, OTel wired, structured logging. No error tracking, no committed alert rules or dashboards, health checks not dependency-aware. |
| Documentation | **5**/10 | Docs volume is high and often good. But 109 undocumented env vars, no auto-generated API spec, and a README whose headline claim isn't reproducible. |
| Maintainability | **5**/10 | 498 mypy errors, ~101 stale audit docs, contradictory status files. A new maintainer cannot tell what's true. |
| Developer experience | **6**/10 | `pip install -e`, devcontainer, Makefile targets, clean lint. CONTRIBUTING references `uv` without install instructions. |
| Commercial readiness | **3**/10 | Inline checkout exists but its 3 tests fail; savings claims not reproducible; pricing tied to ROI models the telemetry doesn't support. |
| Enterprise readiness | **5**/10 | Real breadth — SCIM, RBAC, SSO, audit log, fleet, residency, DSR, air-gap. But no IdP integration testing, thin EE dashboard UI, a11y failure, and no restore drill. |

**Weighted overall: 58/100.**

---

## 10. Recommended Release Plan

### Blocker-removal order

1. **C1 → C2** (sequential). C1 changes retention; C2 validates it. Nothing else should ship first — this is the correctness core.
2. **C4 → H1** (sequential). Green `main`, then lock it with the missing CI jobs. Do this early so every later fix is protected.
3. **C3** (parallel, starts now). Longest lead time because it needs marketing and legal sign-off, not just code.
4. **H2 → H3** (sequential). Migration runner, then rehearse restore against it.
5. **H4, H5, H6, H7** — fully parallel, mutually independent.
6. Medium tier after RC1.

### Parallelisable workstreams

| Stream | Owner profile | Items |
|---|---|---|
| A — Compression correctness | Senior core eng (Rust + Python) | C1, C2, H6 |
| B — CI & release hygiene | DevOps | C4, H1, H7 |
| C — Data durability | Backend + SRE | H2, H3, H4 |
| D — Claims & config docs | PM + tech writer + legal | C3, H5 |

Four streams, ~4 people, ≈2.5–3 weeks wall-clock to clear Critical + High.

### Required regression checks before RC

`cargo test --workspace` · full `pytest` · dashboard lint + build + test · TS SDK + Go SDK tests · `ruff check` + `ruff format --check` · `pip-audit` · Docker build + native e2e · **new:** compression-fidelity property suite from C1.

### Release-candidate criteria

All Critical and High closed · `main` green across all suites · all suites in CI · restore drill completed and timed · every README performance claim regenerable from a committed command · `/readyz` returns 503 when a backend is down · single consistent version string.

### Staging validation

Deploy the built image to k8s staging · verify liveness/readiness/HPA/PDB · kill each backend and confirm readiness flips · run a realistic agent workload through the proxy and confirm no ≥ERROR line is lost · restore staging from a production-shaped backup · confirm `/metrics` scrapes.

### Production deployment checks

Canary one replica · watch `cutctx_tokens_saved_total`, error rate, p95 latency (tokbench measured +0.9s — budget for it) · confirm audit log writes · confirm licence validation against the real endpoint.

### Rollback criteria

Roll back on any of: error rate >1% above baseline · p95 latency >1.5× baseline · any compression-fidelity alert · any DB write failure · licence validation failing closed for valid customers.

### Post-release monitoring

First 48h: compression-fidelity sampling (log a fingerprint of ≥ERROR lines in vs out), realised savings vs the published claim, retrieval-hash usage rate (tells you whether agents actually call `cutctx_retrieve` — this determines whether BLK-01's mitigation is real), and error rate by route.

### Who does what

| Work | Assign to |
|---|---|
| Inventory, doc-link checking, env-var extraction, TODO sweeps, version-string audits, running quality gates and reporting exact numbers | **Haiku / OpenCode Go agents** — this audit used them successfully for all of it |
| Compression retention logic, accuracy-guard wiring, migration runner design, readiness-probe semantics, authz review | **Lead model + human reviewer** |
| Savings-claim wording and pricing implications | **Human** — PM, marketing, and legal. Not delegable. |
| Restore drill | **Human SRE.** An agent can write the runbook; a human must execute the rehearsal. |

---

## 11. Final Verdict

# HIGH RISK

### Why

Not because the project is unfinished — by volume it is further along than most pre-1.0 systems, with 10,528 passing tests, a clean release build, working auth, and a real compression engine. It earns HIGH RISK on two specific grounds from the classification rules:

**Misleading feature completeness.** The README's headline demo says *"same FATAL found."* I injected a FATAL line into a realistic log, compressed it through the shipped library, and the FATAL line was gone — reproducibly, four times, with ERROR and CRITICAL behaving identically, and with `--accuracy-guard strict` making no difference. Separately, the README advertises 47–92% savings while the project's own telemetry over 10,749 real requests shows 0.7%. Both gaps have honest technical explanations. Neither explanation appears where a buyer would see it.

**Insufficient evidence to support a release.** `main` is red. ~1,840 tests never run in CI, including every Rust test guarding the compression core where the defect lives. There is a backup job and no restore procedure. There is no migration runner. `/readyz` reports ready while its datastore may be unreachable. 109 environment variables that change security and cost behaviour are undocumented.

I also want to be clear about what I am *not* saying. Several alarming claims in prior audit documents did not survive verification: provider passthrough **is** authenticated (401 confirmed at runtime); the npm HIGH advisories are **not** exploitable in a client-only SPA; the "compression is licence-gated and returns 0%" finding was a test artefact; and the largest mypy error cluster is false positives. The security posture is meaningfully better than the internal documents suggest.

### Evidence supporting the verdict

Direct execution, not inference: `cargo test` 1,492/0 · `pytest` 9,036 passed / 3 failed / 468 skipped · `mypy` 498 errors · four deterministic compression-fidelity reproductions · live proxy probing with observed 401/200 status codes · `cutctx perf` on 10,749 real requests · CI workflow YAML read line by line · 167-vs-58 env var count.

### What must change before the verdict improves

To **NOT READY**: fix BLK-01 and BLK-02, green `main`. To **READY WITH MINOR FIXES**: additionally close C3, H1–H7, and complete one rehearsed restore drill. To **READY**: additionally deploy to staging, run load testing (never performed by anyone), and verify the enterprise paths — SSO against a real IdP, EE licensing, multi-tenant isolation — that this audit could not reach.

### Conclusions that remain uncertain

- Whether `--accuracy-guard` works on the *proxy* path — I only disproved it on the library path.
- Whether the `router:excluded:tool` exclusion is a bug or a documented-elsewhere configuration requirement.
- Whether Kubernetes and Helm manifests actually deploy — never executed.
- The EE surface, live provider integrations, SSO/IdP, tenant isolation, and the Java SDK — all blocked by credentials or environment, all assumed unverified rather than assumed working.
- The remaining ~480 mypy errors I did not individually classify.
- Whether agents in practice call `cutctx_retrieve` when they see an omission hash. If they reliably do, BLK-01's severity drops materially. If they don't, the mitigation is theoretical. **This is the single highest-value thing to measure next**, and it is measurable from existing telemetry.

---

*Produced 2026-07-25 against `main`@`dcc5b9ee`. No production code was modified during this audit. All reproduction scripts were written to `/tmp`, outside the repository.*
