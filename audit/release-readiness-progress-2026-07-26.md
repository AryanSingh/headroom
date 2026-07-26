# Release Readiness Progress — 2026-07-26

Tracks remediation of findings from `audit/2026-07-25-release-readiness-audit.md`.
Git is the source of truth; this file is the human-readable ledger.

## Branch

`release-readiness-2026-07-26`

## Commits

| Commit | Summary |
|---|---|
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
| Legacy `pitchtoship_client` non-`cutctx_` path | Only if `PITCHTOSHIP_URL` is set | Optional / unused for new keys |
| `cutctx/billing.py` deep links | Still name PitchToShip in comments; not used by website checkout | Dead for self-serve path |

Evidence: 86 billing/license/website tests passed (1 skipped) after merge.

## Open items (post-pilot)

- [ ] Dashboard accessibility (aria-labels, tab roles, contrast)
- [ ] Rename/retire leftover PitchToShip module names and `cutctx/billing.py` deep-link helper
- [ ] Playwright a11y scan in CI
- [ ] Customer-cluster restore drill (runbook exists, drill not executed)
- [ ] Live provider E2E with customer keys
- [ ] Legal review of TERMS.md
- [ ] Root-cause EE+OSS combined pytest session pollution (3–4 tests)

## Verdict

**Pilot-ready.** Named, supported customers can proceed. Self-serve commerce
runs on Supabase Edge Functions with no PitchToShip runtime dependency.
Enterprise procurement and a11y polish remain open.
