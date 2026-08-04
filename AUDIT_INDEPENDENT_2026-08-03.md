# cutctx — Independent Release Audit (Complete)

> Historical baseline: this document records the product state at commit
> `09a6e767` before the `audit-fixes-2026-08-03` remediation series. Its defect
> statuses and release decision are not the current branch status; retain it as
> the original evidence-backed audit input rather than a live release report.

**Auditor:** Opus 5, acting as Lead Auditor / Release Manager / Final Decision Maker
**Date:** 2026-08-03
**Commit:** `09a6e767` (branch `main`)
**Product version:** cutctx 0.32.0
**Scope:** Greenfield. All prior audits, completion percentages and "all tests passed" claims disregarded.

---

# 1. Release Decision

## ❌ NOT READY

**Seven Critical and nineteen High defects, spread across every pillar of the product's own tagline — *govern · attribute · remember · compress*. Each pillar fails under execution:**

| Pillar | Verdict | Evidence |
|---|---|---|
| **compress** | Silently destroys up to 99.92% of data on the default path | C1 |
| **remember** | Cross-tenant data leak; any caller reads any tenant's memories | C4 |
| **attribute** | 8 different "tokens saved" totals in circulation, 8,501× apart | C7 |
| **govern** | PII firewall detects violations and forwards them upstream anyway | C6 |

Plus: reversibility is architecturally dead (C2), enterprise entitlements are bypassable three separate ways (C3), and the flagship Claude Code integration hangs forever without an error (C5).

**This decision does not depend on the remaining unverified areas (§8).** Even if all of them were perfect, C1–C7 block release.

---

# 2. Critical Defects

### C1 — Default compression route silently discards up to 99.92% of records
**Module:** `cutctx/transforms/content_router.py` · **Surfaces:** Core, Proxy, CLI, all agent integrations

Call the documented entrypoint `cutctx.compress(messages, model=...)` with **no config arguments**, payload = 1,200 records as an Anthropic `tool_result` block.

- **Measured:** `313,853 B → 589 B`; unique tokens `1200 → 1`. Loss range across payloads **41% – 99.92%**.
- **No disclosure:** regex scan for `omitted|truncat|compressed to|Retrieve|hash=|elided` returned `[]`.
- **Default path:** trigger is `enable_kompress=False`, the **default** at `content_router.py:756`. No env var, flag, licence or proxy needed. `protect_recent=4` does not shield tool results.
- **Deterministic:** 3 runs byte-identical (`sha=bb2e1143571a91fb`).
- **Root cause:** the sibling `log` route implements disclosure correctly — `[1162 lines omitted: 405 ERROR, 379 WARN, 378 INFO]`. `apply_accuracy_guard` is wired only into the log branch (`content_router.py:2123`, comment: "log-shaped payloads only"). `prose_compressor.py` has **zero** omission logic.
- **Verified twice** by two agents using independent methods and payloads.

**Impact:** the agent receives a fluent remnant indistinguishable from complete data. The provider returns HTTP 200. Nothing downstream can detect it.

### C2 — Retrieval markers can never match; "reversible" is false end-to-end
**Module:** `cutctx/ccr/markers.py` + `cutctx/ccr/store.py`

**Verified personally.** `store.py:64` emits `hashlib.md5(original.encode("utf-8")).hexdigest()[:24]` — **24 hex chars**. All four regexes at `markers.py:19-27` require `[a-f0-9]{16}` followed by a `\]` / `>>` anchor. A 24-char hash cannot match. Control experiment: truncating to 16 chars → `injected=True, tools=[…,'cutctx_retrieve']`.

The store itself is **correct** (byte-exact 82,061 B restore). Only the marker contract is broken. One-line fix — but until then C1's data loss is permanent rather than recoverable. Secondary: MD5 content-addressing is collision-prone and FIPS-rejected.

### C3 — Enterprise entitlements bypassable three independent ways
1. **`CUTCTX_LICENSE_API_URL`** → attacker-controlled server returning `{"valid":true,"tier":"enterprise"}` with key `"I-NEVER-PAID-FOR-THIS"` → all 15 ENTERPRISE keys True. Env override confirmed at `proxy/models.py:19`, `integrations/asgi.py:41`, `telemetry/reporter.py:52`. Endpoint unpinned, response unsigned.
2. **Forged cache** — plain unsigned `license_cache.json` → enterprise. `verify_payload()` returns True when `CUTCTX_LICENSE_HMAC_SECRET` is unset (it is unset on the live proxy).
3. **No gate at all** — **verified personally:** 17 of 18 modules in `cutctx/proxy/routes/` contain zero entitlement checks. Only `admin.py` gates. At builder tier `/v1/airgap/status`, `/v1/residency/proof`, `/v1/rbac/assignments`, `/v1/spend/dashboard` return **200** while their `admin.py` twins return **403**.

`cutctx license generate` mints HMAC `ent-*` keys no code path can verify; the Ed25519 `hrk1` format has no verifier; `require_entitled()` has **zero production call sites**.

### C4 — Cross-tenant memory data leak (IDOR)
**Module:** `cutctx_ee/memory_service/api.py`

**Verified personally.** Lines 40-59:
```python
@router.get("/query")
@router.get("/search")
async def query_memory(..., org_id: str | None = None, ...):   # line 44 — caller-supplied
    ...
    if org_id:                                                  # line 58 — only filters IF given
        query = query.filter(MemoryRecord.org_id == org_id)
```
Tenant scope is an **optional query parameter**, never derived from the authenticated principal.

- Omit it → every tenant's memories in one body.
- Name another tenant → their data. Live repro returned `ORGB-SECRET beta stripe key sk_live_bbb`.
- `/sync` and `/review` scope correctly; `/query` and its `/search` alias are the leaking paths.
- Aggravating: `create_memory_router` logs "will be reachable without auth" and proceeds if no auth dependency is passed — a misconfiguration silently yields an unauthenticated memory API.

**Impact:** worst-class defect for a multi-tenant enterprise product. Customer data crosses tenant boundaries.

### C5 — `wrap claude` is non-functional and fails as a silent infinite hang
The flagship integration. Proxy passes the caller's OAuth credential through; Anthropic rejects with `"x-api-key header is required"` (req_011CdfKYee…); Claude Code retries on exponential backoff 2.7s → 21.3s **forever**. 4 runs, 0 bytes stdout, exit 124. No error surfaces to the user. Not escapable — cutctx persistently sets `env.ANTHROPIC_BASE_URL` in `~/.claude/settings.json`.

### C6 — PII firewall detects violations then forwards them upstream
**Verified personally.** `/firewall/status` → `enabled:true, block_pii:true, patterns_loaded:24`. `/firewall/scan` correctly returns `{"violations":[{"kind":"pii","description":"PII detected: SSN"},{"kind":"pii","description":"PII detected: AWS key"}],"block":true}`.

A real proxied request containing the same SSN and AWS key was **transmitted to Anthropic** — proven by the Anthropic-issued `request_id: req_011Cdg525pHj8FNw3gZuwGCD` in the response. cutctx returned the provider's error rather than blocking locally.

**Impact:** the detection engine works; enforcement does not. A data-egress control that only observes is not a control. *(Caveat: the upstream call failed auth (C5), so this proves egress occurred, not the provider's handling of it. A valid-credential retest would strengthen it — but egress past the firewall is already the defect.)*

### C7 — Savings and ROI figures are unreliable and overstate cutctx's contribution
**Eight distinct "total tokens saved" values in circulation simultaneously:** `0`, `1,018,517`, `21,789`, `519,523,267`, `596,267,331`, `1,335,126,787`, `2,515,818,386`, `8,658,718,931` — largest vs API headline **8,501× apart**. Two figures in the *same* JSON object differ by 14.8%.

Five root causes, all confirmed in source:
- **RC-1 `--days` is structurally inert.** History is a 5000-row ring buffer holding ~21h (`savings_tracker.py:35`). No retained row predates any requested window, so `baseline` stays 0 and every "windowed" answer collapses to lifetime. 134,372 of 139,372 lifetime requests already trimmed.
- **RC-2 `requests_total: 5000` is the buffer size, not a request count.** ROI vs $49/mo divides an all-time numerator by a period denominator: `--days 1 → 4620.89×`. The all-time case reuses the 1-day divisor, inflating ROI ~30×.
- **RC-3 Three accumulators measure different physical quantities with no reconciling invariant.** `observed_provider_savings_tokens` (7.324B = **85% of the 8.659B headline**) is the provider's own `cache_read_tokens` — savings that occur **with or without cutctx in the path**.
- **RC-4 `/stats` interleaves in-memory (resets on restart) and on-disk (never resets) scopes in one unlabelled payload.**
- **RC-5 `report agent-context` contradicts itself** inside one object (`report.py:857` vs `:861`).

**Commercial conclusion (mine, not delegated):** the defensible cutctx-attributable all-time figure is `created_savings_tokens = 1,335,126,787`. The headline a buyer sees from `cutctx savings` is **2,515,818,386 — 1.88× larger** and labelled a 30-day number when it is all-time. Corroborated independently: real Codex traffic shows **0.00% cutctx compression** (143,124→143,124, `transforms_applied:[]`) while the product reports **95.88% savings**, all of it `provider_prompt_cache`.

*(Note: the raw compression **ratio** claims in the README are honest — measured 90.4%/94.8%/74.5%/42.5% vs advertised 92%/92%/73%/47%, confirmed against the real OpenAI token counter at 81.1%. The defect is in the savings **accounting and attribution**, not the compressor's ratio.)*

---

# 3. High-Severity Defects

| ID | Title | Evidence |
|---|---|---|
| **H1** | **Shipped EE binaries are stale and missing security fixes.** `trial.py` (Jul 30 17:24) is newer than `trial.cpython-312-darwin.so` (Jul 29 12:39); same for `user_tokens`. Commits `2668582c fix: honor hosted trial start failure` and `11520832 fix(auth): renew trusted local seat tokens` exist in source but **not in the binaries that load**. Manifests as 8 failing tests in `test_ee_billing_entitlements.py` whose subject is a `<cyfunction>`. **This resolves the fail-open/fail-closed conflict: source fails closed, the shipped binary fails OPEN.** What ships ≠ what is reviewed and tested. |
| **H2** | **EE integrity guard is non-enforcing.** Verified personally: appended one byte to `watermark…so`, hash moved `a735f319…`→`e32df595…`, guard printed "Refusing to load EE modules", module **imported successfully**. `verify_ee_manifest(strict=False)` → `logger.error(); return`, never raises (`integrity.py:190`). Docstring claims "loading is aborted". |
| **H3** | **50 tests failing on `main`**, including the 8 entitlement fail-closed tests above. |
| **H4** | **Tests that lock in bugs.** `test_evals_benchmark.py:1390` asserts `exit_code == 0` for a `"status":"FAIL"` report — fixing the CLI turns it red. `test_ccr_markers.py:14-63` fixtures are fabricated 16-hex hashes, pinning the contract that kills CCR retrieval. |
| **H5** | **Coverage is an illusion.** `cutctx.ccr` reports **82%** while `ccr/store.py` — the module holding C2 — is at **0%, 65/65 statements missed**. Safety slice overall 23%. `cutctx_ee/` excluded from coverage entirely. None of C1–C7 could have been caught by any existing test. |
| **H6** | **Admin API key in cleartext log.** 5 hits in `~/.cutctx/logs/request_history.jsonl` — **445 MB, mode 0644**. |
| **H7** | **Audit retention deletes nothing, reports success.** Float epoch cutoff vs ISO-8601 TEXT column. Live: `cleanup_count: 71`, all four deletion counters **0**, `errors: 0`. Compliance failure. |
| **H8** | **`/audit/verify` returns HTTP 500 always** — `admin.py:570` calls `AuditLogger.verify_chain()`, which does not exist. Audit-chain tamper-evidence unverifiable. |
| **H9** | **`POST /admin/config/flags` silently discards writes and reports success.** Canonical keys ignored, `applied_live:{}`, no `unknown` field, `"status":"success"`. It is the dashboard's declared fallback endpoint (`use-dashboard-data.js:119-140`), so a fallback hit is an undetectable no-op reported to the operator as success. |
| **H10** | **Context budget destroys single-shot requests.** An oversize user message has its entire content replaced by `"[Context Summary] Compressed 1 older messages…"` — the question is gone, client gets HTTP 200, no warning. Multi-turn unaffected. |
| **H11** | **21 broken CLI commands** of 105 executed. Worst: `install apply` → raw `CalledProcessError` traceback (npm package `cutctx-openclaw` 404s — also breaks `wrap openclaw`, `init -g openclaw`); whole `orgs` group non-functional (`list` says "No organizations found" while `GET /orgs` returns 2; `delete` 404s, no endpoint exists). |
| **H12** | **10 CLI commands print an error and exit 0** — including auth 401s and `cutctx verify` returning `Status: FAIL` with exit code 0. The "CI-friendly" gate cannot fail a build. |
| **H13** | **0% cutctx compression on real Codex traffic** (143,124→143,124). Claude: 0.00% (21,273→21,273, `declined_tokens:35,062`). Only OpenCode compresses (37.42%). |
| **H14** | **Four unauthenticated-input 500s with traceback leaks**: `"model":123` → `AttributeError` (`tokenizers/registry.py:141`); `"messages":null` → `TypeError` at the array-size guard itself (`handlers/anthropic.py:1148`); `"messages":{…}` → `AttributeError` (`tokenizers/base.py:93`); 10k-deep JSON → `RecursionError` escaping the `json.loads` guard (`helpers.py:3281`). |
| **H15** | **Two hang conditions, no total deadline.** Upstream that accepts and never replies: 150s zero bytes, `request_timeout_seconds=300` × 3 retries ≈ **15 minutes**. Slow-loris: the 300s timeout is *inter-byte*, so 1 byte/sec resets it forever. |
| **H16** | **O(n²) CPU on repetitive bodies** — 100 KB = 14.5s at 200% CPU, capped only by `COMPRESSION_TIMEOUT_SECONDS=30`. Plus 40× memory amplification (10 MB body → 399 MB RSS), nothing bounds aggregate in-flight memory. |
| **H17** | **Cost routing is inert.** `policy:"cheapest"` accepted, echoed in the decision, and ignored — a $30/Mtok model served a request while a $0.15/Mtok eligible model sat idle. `cost_usd` is **never computed** (always null). Model `context_length` unenforced — a 30k payload was billed to an 8192-ctx model. |
| **H18** | **Memory `review` accepts anything and un-deprecates records.** `action:"banana"` → `{"status":"success","state":"BANANA"}`; the documented `DEPRECATE` doesn't match the `!= "DEPRECATED"` filter, so the record keeps being served. `review_state` absent from API output, so operators can't see it. |
| **H19** | **717 leaked `~/.cutctx/opencode/config-override-*.json`**, each containing a plaintext provider API key. |

---

# 4. Medium / Low

Rust↔Python parity divergence in omission counts · malformed upstream JSON relayed as HTTP 200 · config starts broken silently (`_get_env_bool` coerces unrecognised values to false, fails **open**; `CUTCTX_STATELESS="True "` → False) · `wrap codex` deletes its own `CUTCTX_PROXY_URL`, breaking `cutctx_retrieve` · Playground "Run live compression" 401s in every dev env (`vite.config.js` injects the wrong Authorization header) · 4 dead dashboard controls (Replay search wired to nothing; Capabilities search unreachable; 21 Overview trend bars have no `onClick` — accessibility defect; "New contract" no-op) · `.env.local` admin key stale, breaking dev onboarding · `MANIFEST.sha256.json` tracked in git while `*.so` gitignored, guaranteeing a false "28 files tampered" alarm on every build · 9 of 12 live flags invisible on `/stats.config` and `/admin/config/flags` · batch endpoints skip client-key auth · `server.py:3799` disables admin auth when no key configured · desktop stores keys as plaintext 0600 files, not keychain · 3 dead desktop IPC commands · seat-gate returns 503 for a missing client credential (should be 401/403) · duplicate pipeline event recording (one request → two of every event) filed under a phantom `_pipeline` session · `~/.cutctx` hygiene (30 MB stale tmp, 101 MB journal) · `~/.cutctx/orchestration.json` is a dead file, not in the layered config path.

---

# 5. What Held Up

Evidence-first cuts both ways. Tested hard, passed:

- **Routing enforcement is genuine** — proven by upstream request capture, not logs. Client asked `gpt-5`, upstream received `gpt-5.4-mini`. Roles hit different targets; re-binding sent 0 requests to the old one. **Fallback actually fires** (`fallback_used=true`, +10 ms) and timeout-triggered fallback fires at the exact deadline.
- **Data durability** — no DB corruption, **no lost writes** (a journal at `savings_tracker.py:1171` replayed exactly the 39 missing requests), WAL cleanly drained, **no "database is locked"** across 400+ concurrent requests, no response cross-talk, 60/100 MB bodies cleanly 413'd.
- **Compression ratio claims are substantiated** (see C7 note) and message-structure integrity survived 7 adversarial shapes. Numeric invariant I1 holds; unicode/emoji/code-block round-trips byte-identical.
- **Dashboard is better than its static review suggested** — 124 of 131 controls pass; the two prime suspects (Governance flags, Orchestrator toggle) persist correctly and **revert properly on an injected 500**.
- **Desktop app is real** — all 25 IPC commands implemented, zero stubs, tray fully wired, 46/46 crate tests pass. Tauri v2 in-process only: no listening socket, another local process cannot reach it (tested).
- **Semantic memory retrieval is genuine** (`all-MiniLM-L6-v2`, 0.4383 vs 0.0472), deletes are hard not soft, no orphaned vectors. **Replay is byte-reproducible** across 3 runs.
- **`cargo test --workspace`: 1,495 passed, 0 failed.**
- **Admin auth is enforced** — several alarming static claims were **refuted** by execution: `POST /admin/config/flags` returns 401 (not unauthenticated); nothing binds `0.0.0.0`; the "84 unauthenticated routes" figure was an artifact of a 429 brute-force lockout masking 401s. Secrets files are correctly 0600. No path-traversal or shell-injection sinks. Intercept CA not installed as a trusted root.
- The **41 failing dashboard tests are a broken test harness, not a product defect** — I confirmed `RefreshReg` is absent from the production `dist/` bundle.

---

# 6. Root-Cause Themes

Four themes explain most of the defect list better than the individual tickets do:

1. **Detect-but-don't-enforce.** The firewall scans and forwards (C6). The integrity guard reports tampering and loads anyway (H2). Retention reports cleanup and deletes nothing (H7). Cost policy is accepted and ignored (H17). The pattern is a control plane that observes correctly and acts on nothing.
2. **Build artifacts drift from source.** Stale `.so` files ship without security fixes (H1); the manifest mismatch that should have caught it (M5) fires so often it is ignored. There is no build step guaranteeing compiled EE artifacts match source — and `cutctx_ee/` is excluded from coverage, so nothing measures it.
3. **Success is reported unconditionally.** 10 CLI commands exit 0 on error (H12); `/admin/config/flags` returns success for discarded writes (H9); memory `review` accepts `"banana"` (H18); retention self-reports healthy (H7).
4. **Accounting has no invariants.** Three savings accumulators measure different quantities with nothing reconciling them (C7). No test asserts survivor-count ≥ disclosed-count (C1). No test crosses the store/parse boundary (C2).

**Process observation:** four release documents (`RELEASE_AUDIT_2026_08_03.md`, `RELEASE_READINESS.md`, `RELEASE_REPORT.md`, `RELEASE_STATUS.md`) — one dated today — surfaced none of these. Combined with H3–H5, the release gate is not functioning.

---

# 7. Required Before Release

**Blocking, in dependency order:**

1. **C2** — `{16}` → `{24}` in `markers.py:19-27`. One line, largest correctness gain, partially de-fangs C1. Delete the bug-locking fixtures in `test_ccr_markers.py` first.
2. **C4** — derive `org_id` from the authenticated principal; never accept it as a caller parameter. Add a two-tenant isolation test (none exists today).
3. **C1** — port the `log` route's disclosure convention to `text`; add a cross-route invariant test asserting every lossy route emits retained/dropped counts and a handle.
4. **C6** — make the firewall enforce inline on the proxy path, not just on `/firewall/scan`.
5. **C3 + entitlement gating** — one workstream, not three tickets: locally verifiable signed licences (the `hrk1` Ed25519 format exists but has no verifier), pinned validation endpoint, signed cache, and gating moved to **middleware** so it cannot be omitted per-router.
6. **H1** — add a CI gate that fails if any `cutctx_ee/*.py` is newer than its `.so`, and regenerate the manifest at packaging time from shipped artifacts. Fix this before flipping H2's `strict=True`, or you will harden a guard that fires on every legitimate build.
7. **C7** — label every savings figure with its scope; separate cutctx-attributable from provider-native cache in all buyer-facing output; fix the ROI divisor. **Do not ship the current ROI evidence pack.**
8. **C5** — fix OAuth passthrough for Claude Code, and make credential failures surface as errors rather than infinite retry.
9. **H6** — stop logging the admin key, rotate it, truncate and `chmod 600` the 445 MB log.
10. **H14/H15** — type-guard the request parsers; add a total-request deadline distinct from the inter-byte timeout.
11. **H12** — non-zero exit on error across the CLI (this will turn `test_evals_benchmark.py:1390` red — that test is wrong).

**Before the decision can be revisited:** complete §8, and rebuild the test suite's credibility. 27 of 32 sampled safety tests were weak, tautological or mock-only; `test_entitlement_boundaries.py` is parametrised from `FEATURE_TIERS` itself, so expectation and source of truth are the same object.

---

# 8. Still Unverified — Explicit Disclosure

Four subagents were terminated mid-run by API rate limits and connection errors; I stopped re-launching after the fourth per the no-loop rule. The following have **no execution evidence** and must not be read as passing:

| Area | Note |
|---|---|
| Cross-surface consistency A.2–A.6 | Only feature flags (A.1) completed. Policies, RBAC enforcement parity, memory, orchestration and entitlement-denial parity across CLI/API/Dashboard untested |
| Spend ledger accuracy & spend caps | Do caps actually cap? Untested (`cost_usd` null per H17) |
| Audit-log tamper-evidence | Direct-DB-row-modification detection untested |
| `/metrics` ground-truth validation | Untested |
| Governance policy blocking beyond the PII firewall | Denied-model and spend-cap policies untested |
| 15 CLI commands | Of 120 leaf commands: 105 executed, 14 destructive-skipped, 5 unverified |
| Desktop interactive GUI journeys | Tauri GUI not headless-drivable; source and IPC verified, user journeys not |
| Claude streaming / tool calls / resume | Blocked by C5 — no request ever completed |
| Mid-session proxy death for all three agents | Blocked by port-scoped credentials |
| Non-Anthropic handlers (OpenAI/Gemini/Vertex) | H14's missing type guards may repeat there |
| Full Python suite | 3,672 passed / 50 failed / 195 skipped on a 198-file subset; ~511 files (~6,600 tests) unrun, ~2.5h projected |
| Docker / Helm / k8s deployment | Untested |
| SDKs (Python/TS/Go/Java), VS Code & JetBrains extensions | Untested |
| Competitive review | Not produced |

Given the tested areas yielded 7 Criticals and 19 Highs, **assume the untested areas contain further blockers.**

---

# 9. UX & Commercial Observations

Only items with material impact:

- **The first-run path is broken.** `.env.local` ships a stale admin key that 401s, and `cutctx install apply` dies on an npm 404. A developer following the repo's own instructions concludes the product is broken before reaching any feature.
- **Error messages are the weakest surface.** 6 raw tracebacks on ordinary bad input; `memory import` reports "Skipped 2 malformed entries" with no field, reason or schema hint; the seat gate returns 503 `server_error` for a missing credential, which will mislead load balancers and on-call engineers alike.
- **Alarm fatigue is engineered in.** Every EE import prints a 28-line "tampered" block that is always false-positive locally. This directly caused H2 to go unnoticed. Noisy controls get ignored; that is a design defect, not a user failing.
- **The savings surface is the commercial liability.** Eight totals, none labelled with scope, `--days` inert, ROI inflated ~30×, and 85% of the headline attributable to a provider feature the customer already has. This is the number the product is sold on. Fix the accounting before the marketing.
- **Strong foundations worth protecting:** routing enforcement, data durability under concurrency and SIGKILL, semantic memory quality, replay reproducibility, and a genuinely complete desktop implementation. The engineering is good; the *verification and enforcement layers* are what's missing.

---

# 10. Evidence Index

Preserved to `audit/independent-2026-08-03/` in the repo (21 MB, copied from `/tmp/cutctx-audit/`):

`evidence/core-compression.md` · `evidence/c1-replication.md` (independent 2nd replication) · `evidence/enterprise.md` · `evidence/dashboard.md` + `evidence/screens/` (50 Playwright captures) · `evidence/security.md` · `evidence/cli-execution.md` + `raw.log` · `evidence/memory-replay.md` · `evidence/routing.md` · `evidence/agent-integrations.md` · `evidence/test-quality.md` · `evidence/desktop-resilience.md` · `evidence/cross-surface-governance.md` (savings forensics) · `evidence/governance-crosssurface.md` (partial) · four inventory files (120 CLI commands, 181 routes, dashboard controls, 62 entitlement keys / 58 flags).

**State changes made during the audit, disclosed:**
- `POST /stats/reset` zeroed in-memory counters — **not restorable**.
- One byte appended to `watermark…so` during the tamper test, restored from backup.
- SCIM user, RBAC role and org records created and deleted (the org required a direct DB row delete — no DELETE endpoint exists).
- Two labelled memory rows created to prove C4, deleted and verified `count=0`.
- Licence files, agent configs (`settings.json`, `codex/auth.json`, `opencode.json`, `config.toml`), feature flags and routing configs all verified byte-identical to baseline.
- `prefix_tracker.db` changed — written continuously by the production proxy, not by the audit. Disclosed rather than claimed untouched.
- The live proxy was never restarted (uptime proves it) and no tracked repo file was modified.

---

# 11. Bottom Line

The engineering underneath this product is better than a 7-Critical defect list implies. Routing enforcement is real and provable. Data survives SIGKILL, 400-way concurrency and WAL replay without a single lost write. The compressor's ratios are honest. The desktop app has no stubs. Several of the scariest static findings evaporated under execution.

What fails is the layer that was supposed to make all of that trustworthy. Every one of the four product pillars has a control that detects correctly and then does nothing: the firewall forwards the PII it flagged, the integrity guard loads the binary it called tampered, retention reports deleting rows it never deleted, and the savings ledger reports eight different answers to one question. Meanwhile the test suite reports 82% coverage on a package whose broken module has never once been executed, and two of its tests would fail if the bugs were fixed.

**Decision: NOT READY.** Revisit after items 1–11 in §7, and after §8 is closed.

---

*Prepared by Opus 5 as Lead Auditor. Every Critical was verified independently of the agent that first reported it; C2, C3(3), C4, C6 and H1 were confirmed by me directly. Conflicting subagent findings were resolved rather than averaged. Untested areas are disclosed in §8 and are not represented as passing.*
