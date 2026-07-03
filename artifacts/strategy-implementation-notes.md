# Strategy Implementation Notes — 2026-07-02

Per `artifacts/strategy-implementation-plan.md` §0.3, this file tracks
deferred refactors, pre-existing baseline failures, and notes that
arose during WS16 implementation. Every implementing agent should
update this file when work reveals a needed refactor or a baseline
caveat that the per-task gate would otherwise miss.

## WS16 — Tokenizer-aware normalization

**Status (2026-07-02):** Steps W16.1, W16.2, W16.3 complete and merged
to branch `feat/ws16-normalize`. 552/552 regression tests pass on the
broader transforms + savings surface.

### What landed

- `cutctx/transforms/normalize.py` — 4 passes (NFC + homoglyph
  whitespace collapse, trailing-whitespace + blank-run collapse,
  base64/hex blob detection, decimal-precision cap in numeric tables).
  Pure functions, idempotent, semantics-preserving. Default-OFF via
  `NormalizeConfig` (all sub-flags False). `normalize_content()` is a
  no-op when all sub-flags are off, satisfying the flag-off golden
  contract.
- `cutctx/transforms/content_router.py` — `ContentRouterConfig.normalize_config`
  field added (default: `NormalizeConfig()` — all off). The pre-pass
  runs at the top of `ContentRouter.compress()` after the empty/whitespace
  check, before content-type detection. With the default config, the
  pre-pass short-circuits and compress() is byte-identical to pre-WS16.
- `cutctx/savings/types.py` — `SavingsSource.NORMALIZATION` enum member
  added. Labels + descriptions updated. The model grew from 7 to 8
  sources; consumers that key off the canonical string values are
  unaffected (additive contract).
- `dashboard/src/pages/Overview.jsx` — `LIFETIME_SAVINGS_SOURCES` table
  extended with `'normalization_savings_usd', 'normalization'`. The
  `getSessionSavingsUsd` function includes a `normalizationUsd`
  calculation. Total Math.max() includes `normalizationUsd` in the sum.
- 3 new test files:
  - `tests/test_transforms_normalize.py` — 29 tests: flag-off golden,
    per-pass correctness, idempotency, BDD scenarios.
  - `tests/test_transforms_normalize_wiring.py` — 9 tests: pre-pass
    fires when enabled, doesn't fire when disabled, output type unchanged.
  - `tests/test_savings_types_normalization.py` — 9 tests: enum registration,
    additive contract, aggregation, dashboard tolerance, round-trip.
- 2 existing test files updated to be additive:
  - `tests/test_savings_buyer_report.py` — empty-state JSON test now
    asserts baseline sources are a subset (not equality) and that
    `normalization` is present.
  - `tests/test_savings_orchestration.py` — `test_all_five_sources_present`
    renamed semantically to "baseline seven + WS16" and asserts
    `NORMALIZATION` is present without hard-coding the total count.

### Deferred items (recorded here per §0.3)

- **W16 step 1: blob-to-CCR-pointer swap is read-only.** Pass 3 detects
  base64/hex blobs but does NOT modify content or insert a CCR pointer.
  The actual CCR-insert integration lands in W16.2 (which is now done
  — the wiring exists; the blob pass-through is the only step deferred).
  The deferred swap is the marker-to-pointer replacement; the marker
  format `[cutctx:ref:HASH]` is a single source-of-truth in
  `cutctx/ccr/markers.py` (from the prior WS21.1 work). A follow-up
  should add a `ccr_insert_blob(content, blob)` call in
  `_pass_blob_to_pointer` to actually swap the marker for a real CCR
  pointer. The detection + classification logic is shipped; the
  write path is the only step remaining.

- **No "normalization" telemetry in the live /stats payload yet.** The
  WS16 step 3 work added the savings source to the enum and the
  dashboard, but the proxy's `cutctx/proxy/savings_tracker.py` (and
  related `emit_request_outcome` callers) does not yet emit a
  `normalization` line item per request. This means the live
  proxy will count normalization savings as 0 until a hook in the
  pipeline calls `savings_tracker.add(SavingsSource.NORMALIZATION, ...)`
  with the per-request savings. A follow-up should add this hook
  in `cutctx/proxy/intelligence_pipeline.py` (the same place that
  records other per-source savings). Detected this gap during
  W16.3 — flagged here per §0.3 rather than expanding scope.

- **The "5-source model" docstring in `cutctx/savings/types.py` is
  stale.** The model is now 8 sources. A docstring update
  ("5-source → N-source") is purely cosmetic and was not part of
  the additive contract, so it was left for a docs-only commit.

### Pre-existing baseline failures (untouched per §0.1)

- **Dashboard e2e tests** (Playwright in `dashboard/e2e/`) are NOT
  discoverable by `pytest` from the repo root. They require
  `cd dashboard && npx playwright test` (per the per-task gate in
  §0.1). The WS16 work did NOT run the Playwright suite. A
  follow-up to add a CI workflow that runs both pytest and playwright
  would close this loop.

- **Proxy e2e tests** (in `tests/e2e_*.py` glob) returned 0 items
  collected by pytest. The actual e2e coverage lives in JS/TS
  harnesses that pytest cannot discover. Same caveat as above.

- **2 SWIG DeprecationWarnings** in the broader regression suite
  (`builtin type SwigPyObject has no __module__ attribute`) are
  pre-existing, unrelated to WS16, and not addressed here.

### Per-task gate results

| Gate | Result |
|---|---|
| Targeted new tests pass (WS16.1) | 29/29 PASS |
| Targeted new tests pass (WS16.2) | 9/9 PASS |
| Targeted new tests pass (WS16.3) | 9/9 PASS |
| Full transforms + savings surface | 552/552 PASS |
| Flag-off parity (golden) | confirmed byte-identical for `NormalizeConfig()` default |
| Docs build | not run (no docs touched in WS16) |
| Coverage | new tests added alongside code, not after |
| One commit per task | one commit, three steps documented in commit message |
