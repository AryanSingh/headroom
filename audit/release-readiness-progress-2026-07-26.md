# Release Readiness Progress — 2026-07-26

Tracks remediation of findings from `audit/2026-07-25-release-readiness-audit.md`.
Git is the source of truth; this file is the human-readable ledger.

## Branch

`release-readiness-2026-07-26`

## Commits

| Commit | Summary |
|---|---|
| `1d7bae89` | Cursor-style Auto routing + billing/a11y/prometheus gap closure |
| `95d8647b` | SPDX header for hosted license tests; billing status docs |
| `7cd7ca45` | Merge `origin/main` hosted Supabase billing into this branch |
| `8a8853ab` | Seat checkout + telemetry validation → Supabase edge functions |
| `f05fa5fe` | QA certification docs (13/13 verifier, score 88/100) |
| `cbefb1e8` | Mypy ratchet line-number fix, test DB isolation, Rust fmt |
| `ed938126` | Close all P0 blockers: log fidelity, licensing, readiness, security, docs |

## Blocker closure

| ID | Finding | Status | Evidence |
|---|---|---|---|
| BLK-01 | Log compressor drops FATAL/ERROR/CRITICAL | ✅ Closed | `crates/cutctx-core/.../log_compressor.rs`, `cutctx/transforms/log_compressor.py` |
| BLK-02 | `--accuracy-guard strict` no-op | ✅ Closed | `cutctx/proxy/accuracy_guard.py`, `tests/test_accuracy_guard.py` |
| BLK-03 | Savings claims vs telemetry | ✅ Closed | README + `docs/why-output-is-not-compressing.md` |
| BLK-04 | 3 failing tests on main | ✅ Closed | `tests/website/test_static_site.py` |
| BLK-05 | ~1,840 tests outside CI | ✅ Closed | `.github/workflows/rust.yml`, `go-sdk.yml`, `java-sdk.yml` |
| BLK-06 | No migration framework | ✅ Closed | `scripts/migrate.py`, `tests/test_sql_migrations.py` |
| BLK-07 | `/readyz` shallow | ✅ Closed | `cutctx/proxy/server.py` CCR probe |
| BLK-08 | 109 undocumented env vars | ✅ Closed | `docs/configuration-reference.md` (190 vars) |
| BLK-09 | SmartCrusher excluded on JSON tool | ⚠️ Documented | `docs/why-output-is-not-compressing.md` — denylist by design |
| BLK-10 | Version drift | ✅ Closed | `.release-please-config.json` |
| BLK-11 | mypy 498 errors | ⚠️ Ratcheted | `scripts/mypy_ratchet.py` + baseline; CI uses `--ignore-missing-imports` |

## Licensing fixes (production break)

| Issue | Status | Evidence |
|---|---|---|
| `license activate` → HTTP 405 | ✅ Fixed | Repointed to Supabase verify-license edge function |
| `checkout_seat` → HTTP 405 | ✅ Fixed | Repointed to seat-heartbeat edge function |
| `UsageReporter.validate_license` → HTTP 405 | ✅ Fixed | Same verify-license endpoint |
| `is_revoked()` false positive | ✅ Fixed | CRL replaced with verify-license + cache |
| `license_db` frozen path | ✅ Fixed | Per-call resolution + `CUTCTX_LICENSE_DB_PATH` |

## Security

| Item | Status |
|---|---|
| pyo3 0.24 → 0.29 (RUSTSEC-2026-0176/0177) | ✅ |
| Python deps 37 → 3 advisories | ✅ |
| `cargo audit` clean, unwaived | ✅ |

## Performance (first measurement)

See `audit/2026-07-26-first-load-test.md`:

- 603 req/s peak at concurrency 16
- p50 13–24 ms on 86.7 kB log payload
- FATAL preserved 720/720 under load

## Pilot verifier

```
scripts/verify_pilot_release.py → 13/13 passed (2026-07-26)
```

## Billing / commerce (post-merge verification)

Verified after merging `origin/main` (2026-07-26):

| Surface | Backend | PitchToShip required? |
|---|---|---|
| `website/assets/pricing.js` | Supabase `list-plans`, `create-order`, `verify-payment` | No |
| `website/assets/licenses.js` | Supabase `my-licenses`, `request-license-link` | No |
| Hosted `cutctx_*` keys | Supabase `verify-license`, `seat-heartbeat` | No (`PITCHTOSHIP_URL` unset) |
| `cutctx license activate` | Supabase `verify-license` default | No |
| CLI / EE deep links | `cutctx.com/pricing/` + `/licenses/` | No |
| Legacy `pitchtoship_client` non-`cutctx_` path | Only if `PITCHTOSHIP_URL` is set | Optional / unused for new keys |

Evidence: 86 billing/license/website tests passed (1 skipped) after merge; deep-link tests updated to cutctx.com.

## Cursor-style Auto routing (2026-07-26)

| Capability | Status | Evidence |
|---|---|---|
| Synthetic `model=auto` / `cutctx-auto` / `cursor-auto` | ✅ | Selects fast/medium/strong from complexity |
| Dashboard mode labeled **Auto** (was Balanced) | ✅ | `dashboard/src/pages/Orchestrator.jsx` |
| `CUTCTX_MODEL_ROUTING_PRESET=auto` alias | ✅ | Same as `codex-gpt54mini-high` |
| Auto works even when routing toggle is Off | ✅ | Request still resolves a concrete model |
| Catalog + static family fallbacks | ✅ | OpenAI / Anthropic / Google static tables |
| Docs | ✅ | `docs/content/docs/model-routing-presets.mdx` |
| Adversarial + HTTP e2e confirmation | ✅ | Plan + results: `audit/2026-07-26-model-routing-adversarial-test-plan.md` (18/18 e2e, live harness 9/9, quality unsafe Mini 0) |
| Uncertified inventory no longer blocks downgrades | ✅ | `_catalog_manages_source` requires certification |
| Anthropic Auto actually mutates upstream body | ✅ | `body["model"]` + `mark_mutated("model_routing")` |

Tests: `tests/test_model_router_auto.py` (9) + `tests/test_model_routing_adversarial_e2e.py` (18) + dashboard orchestrator suite green.

## Other gaps closed this pass

| Item | Status |
|---|---|
| Prometheus alerts pointed at real `cutctx_*` metrics | ✅ `k8s/prometheus-rules.yaml` |
| Dashboard ErrorBoundary resets on navigation | ✅ `dashboard/src/App.jsx` |
| Routing mode tabs: `role="tablist"` / `aria-selected` | ✅ |
| ASGI cloud default no longer pitchtoship.com | ✅ Supabase functions base |

## Exhaustive client adversarial campaign (2026-07-26)

Plan + results: `audit/2026-07-26-exhaustive-client-adversarial-plan.md`  
Bug ledger: `audit/2026-07-26-adversarial-bug-ledger.md`

| Gate | Status |
|---|---|
| New hermetic suite `tests/test_client_matrix_adversarial_e2e.py` | ✅ 18/18 |
| Process harness `scripts/verify_client_matrix_live.py` | ✅ 16/16 |
| Routing quality `unsafe_downgrade_rate` | ✅ 0.0 |
| Prior landmines (Auto mutate, catalog, WS keepalive, zstd, #746, sub WS, byte-faithful) | ✅ re-verified |
| Pilot verifier 13/13 | ❌ 12/13 — rust-tests disk full (env); `cutctx-core` lib tests 896 passed |
| LIVE-* Claude/Codex/Cursor | ✅ CC/CDX/MEM PASS; ⛔ CUR BLOCKED (`cursor agent login` / `CURSOR_API_KEY`) |
| Desktop operator checklists | ⚠️ Claude Desktop MCP installed; Cursor/ChatGPT GUI turns still unsigned |
| Playwright orchestrator | ✅ Chromium installed; suite green after one flake retry |
| Open S0/S1 | ✅ none |

**Campaign verdict: FAIL** (full exit gate / release claim) — residual: LIVE-CUR auth, Desktop GUI sign-off, pilot rust disk, CCR 21/36.

## Open items (post-pilot)

- [ ] Broader dashboard a11y (Overview/Savings duration tabs, contrast)
- [ ] Full rename of `pitchtoship_client.py` module (docstring updated; shim deferred)
- [ ] Playwright a11y scan in CI
- [ ] Customer-cluster restore drill (runbook exists, drill not executed)
- [ ] Live provider E2E with customer keys (**required to clear adversarial campaign**)
- [ ] Legal review of TERMS.md
- [ ] Root-cause EE+OSS combined pytest session pollution (3–4 tests)
- [ ] IDE/plugin UX: advertise Auto as a selectable model in VS Code / JetBrains
- [x] `npx playwright install` + re-run `dashboard/e2e/orchestrator.spec.js` (PASS after flake retry)
- [x] `cutctx mcp install --agent claude-desktop --gateway` (configured; Desktop restart + live tool turn still operator)
- [ ] Cursor agent login / `CURSOR_API_KEY` for LIVE-CUR-1/2
- [ ] Cursor Desktop + ChatGPT Desktop GUI operator checklist sign-off
- [ ] CCR adversarial suite debt (`benchmarks/adversarial_ccr_tests.py` 21/36) — ADV-20260726-012
- [ ] Free disk + re-run `scripts/verify_pilot_release.py` rust-tests

## Verdict

**Pilot-ready** for hermetic/named-client proxy behavior. Self-serve commerce
runs on Supabase Edge Functions with no PitchToShip runtime dependency.
Orchestrator Auto routing matches Cursor Auto semantics for `model=auto`.

**Not campaign-PASS** for exhaustive live Claude/Codex/Cursor adversarial
sign-off until LIVE-CUR + Desktop GUI checklists clear (Claude/Codex/MEM live
and Playwright cleared 2026-07-26 resume).
