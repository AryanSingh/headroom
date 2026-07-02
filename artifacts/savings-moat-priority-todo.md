# Savings Moat Priority Todo

Date: 2026-07-02

Source specs:
- `artifacts/savings-moat-expansion-specs.md`
- `artifacts/strategy-implementation-plan.md`

Working prioritization for the current repo state:

1. `WS21.1` Extract CCR marker parsing/formatting into `cutctx/ccr/markers.py`
Reason:
- Pure refactor with explicit zero-behavior-change contract
- Low regression risk compared with new runtime savings paths
- Unblocks CCR spec/conformance work and reduces duplicated marker logic

2. `WS16` Tokenizer-aware normalization
Reason:
- Smallest direct savings feature in the spec
- No new provider workflows required
- Can stay fully flag-gated and additive

3. `WS11` Tool-result memoization
Reason:
- High payoff, but correctness-sensitive
- Needs careful invalidation and e2e coverage before shipping

4. `WS10` Output-side optimization
Reason:
- Strong savings upside, but touches prompt mutation and request caps
- Should follow after marker/spec cleanup and normalization

5. `WS13` Batch-API arbitrage
Reason:
- Explicitly opt-in and high upside
- More provider-specific branching than the items above

6. `WS19` Compression autopilot
Reason:
- Valuable control loop, but depends on already trustworthy signals
- Better after at least one or two new additive savings sources ship

7. `WS18` Learned per-customer policies
Reason:
- Primary moat per spec
- Should build on stable outcome streams and controller behavior

Current implementation target:
- [x] `W21.1` Add `cutctx/ccr/markers.py`
- [x] Move CCR marker constants/patterns/helpers behind that module
- [x] Update `cutctx/dedup.py`, `cutctx/ccr/tool_injection.py`, and `cutctx/ccr/response_handler.py` imports with no behavior change
- [x] Add focused tests for marker extraction/round-trip behavior
- [x] Re-run CCR/dedup-focused tests
- [x] `WS16` Tokenizer-aware normalization
  - [x] `W16.1` `cutctx/transforms/normalize.py` with 4 passes (NFC, whitespace, blob, decimal)
  - [x] `W16.2` ContentRouter pre-pass wiring, flag-gated by `CUTCTX_NORMALIZE=1`
  - [x] `W16.3` `SavingsSource.NORMALIZATION` registration + dashboard aggregation

Status:
- `2026-07-02`: `WS21.1` shared marker contract path implemented.
- Focused verification passed: `tests/test_ccr_markers.py`, `tests/test_ccr_tool_injection.py`, `tests/test_ccr_tool_always_on.py`, and `tests/test_ccr_response_handler_extra.py` (`56 passed`).
- `2026-07-02`: `WS16` complete on branch `feat/ws16-normalize`. New files: `cutctx/transforms/normalize.py`, `tests/test_transforms_normalize.py` (29 tests), `tests/test_transforms_normalize_wiring.py` (9 tests), `tests/test_savings_types_normalization.py` (9 tests). Modified: `cutctx/transforms/content_router.py` (pre-pass injection), `cutctx/savings/types.py` (NORMALIZATION enum), `dashboard/src/pages/Overview.jsx` (per-source mapping), `dashboard/src/lib/use-dashboard-data.js` (caching). 2 pre-existing tests updated to be additive (`test_savings_buyer_report.py`, `test_savings_orchestration.py`). Broader regression: 552/552 tests pass on `tests/test_transforms* tests/test_savings*`. Per the strategy-implementation-notes.md: blob-to-CCR-pointer swap is read-only (deferred); live /stats doesn't yet emit normalization line items (deferred).
