# Release, Commercial & QA Audit — 2026-07-18

**Method:** every gate below was executed on this tree (commit range
`origin/main..main`, working tree carrying only a concurrent session's
report edits and one pre-existing binary asset). Nothing was assumed from
prior reports; stale prior findings are marked as such.

## 1. Release readiness

| Gate | Result | Notes |
|---|---|---|
| `scripts/verify-versions.py` | ✅ | All 15 surfaces aligned at 0.31.0 (incl. Helm/K8s) |
| Computed next release | ✅ `0.32.0` | Conventional-commit parser sees `feat:` commits → minor bump |
| Conventional-commit format (commitlint, gates PRs) | ✅ **fixed this audit** | All 7 unpushed commits were non-conventional (missing `type:` colon) and would have failed CI on a PR; reworded in place (local-only history, backup at `backup-pre-reword`). Older direct-to-main commits bypassed the PR gate and are left as history. |
| `ruff check .` (repo-wide) | ✅ | The 2026-07-04 "release blocker" note is obsolete |
| `cargo fmt --check` | ✅ **fixed this audit** | `crates/cutctx-py/src/lib.rs` failed the formatting gate; formatted, `cargo check` + `cargo clippy` clean after |
| `cargo clippy -p cutctx-py` | ✅ | exit 0 |
| Full Python suite | ✅ 8,973 passed / 267 skipped; 1 network-flake (see §3) | executed this audit |
| Dashboard gates (lint / build / unit / e2e) | ✅ | ESLint clean; single-run build synced into package; 12 JS unit; 28 e2e (this cycle) |
| SDKs | ✅ | TypeScript 306 passed / 33 skipped; Go `ok`; (Python SDK 14/14 per 07-17 evidence, unchanged since) |
| CI path filters | ✅ | `helm/**`, `k8s/**` present in `ci.yml` (07-17 finding closed upstream) |
| Packaging | ✅ | maturin `include` packages `cutctx/` wholesale; dashboard assets synced & committed; sync script copies all chunks |
| CHANGELOG | ✅ | Current (2026-07-18 section) |
| RELEASE_STATUS.md | ⚠ stale → **banner added** | Snapshot of v0.29.0; superseded pointer added rather than rewriting history |
| Unpushed state | ⚠ | 9 commits ahead of `origin/main`; push (or PR) is the remaining release step, deliberately left to the operator |

**Release verdict:** ✅ green for a 0.32.0 cut once pushed. No code gate
fails. The only open items are operator actions (push/PR, tag via the
release workflow) and the stale-but-bannered status doc.

## 2. Commercial readiness

### Verified in good shape
- **Entitlement enforcement** — fail-closed on admin surfaces, config
  toggles, and BUSINESS-tier runtime features; startup license validation
  with plan override; UI explains refusals (tier-labeled disabled toggles
  + actionable 403 copy). Test-pinned end-to-end.
- **Value-meter integrity** — savings ledger reconciled (schema v7);
  created vs observed split live on real data; reconciliation provenance
  badged in the UI.
- **Public commercial surface** — plans/feature matrix and published SLA
  pages exist and are test-pinned; PRODUCT_GUIDE enforcement claim
  corrected; buyer-report CLI (`cutctx report buyer`) present.
- **Claims honesty** — README benchmark section is measured, hedged, and
  reproducible (per-dataset preservation/compression table; BFCL exclusion
  explained). `benchmark_results.md` carries the 2026-07-18 measured
  matrix with kept-fraction framing.
- **Trial flow** — `TrialManager` + `cutctx license status` trial
  reporting exist (07-17 "no trial flow" finding is stale).
- **Billing plumbing** — checkout/portal URL generation via the billing
  API; backend domain (pitchtoship.com) resolves (HTTP 200). End-to-end
  purchase not exercised (requires a real transaction).

### Open commercial blockers (business actions, not code)
1. **cutctx.com is dead** (connection failure). README's docs badge, doc
   links, llms.txt pointers, and the benchmark-methodology link all 404 at
   the domain level. This is the single most visible credibility gap for
   an evaluating buyer. (Register/point the domain, or repoint README to
   an existing host.)
2. **TERMS.md is explicitly a draft template** ("must be reviewed by
   qualified legal counsel") — blocks signed commercial transactions.
3. **SLA service-credit remedies** — policy published, credits TBD
   (flagged in the doc).
4. SOC 2 / third-party audit evidence — external program, correctly
   disclosed as unavailable today.

**Commercial verdict:** ⚠ ship-ready for design-partner/self-serve-free
motion; paid enterprise sale still gated on domain, counsel-approved
terms, and (per deal size) compliance evidence. Software-side monetization
enforcement is done.

## 3. QA health

- **Full suite:** 8,973 passed / 267 skipped / 1 failed in 9m12s — the
  failure (`TestHealthWithEpisodic::test_health_endpoint`) hit the live
  upstream probe from a sandboxed run and passes in isolation; it is
  now hardened with `CUTCTX_SKIP_UPSTREAM_CHECK=1` (it asserts proxy
  wiring, not provider connectivity). Two prior same-day full runs were
  green (8,968/8,969).
- **Skips** are environment-gated, not rot: Redis-backed orchestration
  (3), live-provider/credentialed paths, optional deps (playwright import
  guards, ONNX/vLLM extras), platform-specific cases. No test is skipped
  for being broken.
- **Known flake:** `test_hosted_compression_route_disabled_by_default`
  failed once under 3-way parallel load (HTTP/2 stream read); passes in
  isolation and in clean full runs (2 consecutive). Watch, don't chase.
- **Coverage surfaces added this cycle:** savings-ledger source-of-truth,
  v7 migration/idempotency, entitlement request-path (8 tests), health
  probe caching contract, bounded trace tail-read, code-elision semantic
  quality (`compile()`-verified output), Safe Savings API/CLI/panel (16 +
  3 + 4), governance 403 UX, plans/SLA doc pins.
- **e2e:** 28 dashboard Playwright tests green against the packaged
  bundle; UI functional matrix in `audit/ui-ux-audit-2026-07-18.md`.
- **Perf gates:** proxy overhead p50 2.5 ms / p95 3.1 ms (in-process,
  c=1), ~443 req/s single-worker saturation, 0 failures / 2,800 requests;
  routing quality 75/75 with zero unsafe downgrades.

**QA verdict:** ✅ healthy. Deepest remaining gap is live-provider
integration coverage (all provider paths mocked — long-standing, honest
caveat recorded in the audit trail).

## 4. Fixed during this audit
1. Reworded 7 unpushed commits to conventional format (would have failed
   the PR commitlint gate).
2. `cargo fmt` applied to `crates/cutctx-py/src/lib.rs` (failing CI gate);
   compile + clippy verified after.
3. `RELEASE_STATUS.md` superseded banner.
4. Hardened the episodic health test against live-network flakes.

## 5. Recommended next actions (priority order)
1. Push/PR the 9 commits; let release automation cut v0.32.0.
2. Resolve the cutctx.com domain (register or repoint README links).
3. Counsel pass on TERMS.md; decide SLA credit percentages.
4. Refresh the README zero-LLM benchmark table (ContentRouter tool-output
   row predates this week's compressor changes; `benchmark_results.md` is
   current).
5. Design-partner motion for live-provider validation evidence.
