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
- [x] `WS10` Output-side optimization
  - [x] `W10.1-4` `cutctx/proxy/output_optimizer.py` — 3 levers (diff-edit steering, max_tokens auto-tuning, style shaping) with per-session safety rail
  - [x] `W10.5` `SavingsSource.OUTPUT_OPTIMIZATION` registration + dashboard aggregation
- [x] `WS11` Tool-result memoization
  - [x] `W11.1-2` `cutctx/proxy/memoizer.py` — canonicalize_args, derive_key, is_write_tool, MemoizeConfig, ToolMemoizer (LRU + invalidation)
  - [x] `W11.3` `cutctx/proxy/memoize_interceptor.py` — wire-format detection (OpenAI / Anthropic / Google), fabricated tool_result on hit, passthrough on miss, byte-identical payload
  - [x] `W11.4` Write-invalidation correctness: read → edit → read returns fresh content
  - [x] `W11.5` `SavingsSource.MEMOIZATION` registration + dashboard aggregation
- [x] `WS13` Batch-API arbitrage
  - [x] `W13.1` Eligibility gate (explicit, never inferred) — header `x-cutctx-batch: allow` OR allowlisted internal origin
  - [x] `W13.2` Internal queue state (pending/completed/failed/total)
  - [x] `W13.5` `SavingsSource.BATCH_ROUTING` registration
- [x] `WS16` Tokenizer-aware normalization
  - [x] `W16.1` `cutctx/transforms/normalize.py` with 4 passes (NFC, whitespace, blob, decimal)
  - [x] `W16.2` ContentRouter pre-pass wiring, flag-gated by `CUTCTX_NORMALIZE=1`
  - [x] `W16.3` `SavingsSource.NORMALIZATION` registration + dashboard aggregation

Status:
- `2026-07-02`: `WS21.1` shared marker contract path implemented.
- Focused verification passed: `tests/test_ccr_markers.py`, `tests/test_ccr_tool_injection.py`, `tests/test_ccr_tool_always_on.py`, and `tests/test_ccr_response_handler_extra.py` (`56 passed`).
- `2026-07-02`: `WS11` complete on branch `feat/ws11-memoize`. New files: `cutctx/proxy/memoizer.py` (module), `cutctx/proxy/memoize_interceptor.py` (interceptor), `tests/test_proxy_memoizer.py` (34 tests), `tests/test_proxy_memoize_interceptor.py` (12 tests), `tests/test_savings_types_memoization.py` (8 tests). Modified: `cutctx/savings/types.py` (MEMOIZATION enum), `dashboard/src/pages/Overview.jsx` (per-source mapping). 2 pre-existing tests updated to be additive. Broader regression: 613/613 tests pass on the WS11 surface. The interception is exposed as `MemoizeInterceptor.intercept_tool_calls(response, session_id)` — the caller wires it into the existing CCR tool handling path. The full integration into `cutctx/ccr/response_handler.py` is documented as a deferred follow-up (W11.6).
- `2026-07-02`: `WS16` complete on branch `feat/ws16-normalize`. New files: `cutctx/transforms/normalize.py`, `tests/test_transforms_normalize.py` (29 tests), `tests/test_transforms_normalize_wiring.py` (9 tests), `tests/test_savings_types_normalization.py` (9 tests). Modified: `cutctx/transforms/content_router.py` (pre-pass injection), `cutctx/savings/types.py` (NORMALIZATION enum), `dashboard/src/pages/Overview.jsx` (per-source mapping), `dashboard/src/lib/use-dashboard-data.js` (caching). 2 pre-existing tests updated to be additive (`test_savings_buyer_report.py`, `test_savings_orchestration.py`). Broader regression: 552/552 tests pass on `tests/test_transforms* tests/test_savings*`. Per the strategy-implementation-notes.md: blob-to-CCR-pointer swap is read-only (deferred); live /stats doesn't yet emit normalization line items (deferred).

- [x] `WS11` Tool-result memoization (branch feat/ws11-memoize, PR #4)
  - [x] `W11.1-2` `cutctx/proxy/memoizer.py` — canonicalize_args, derive_key, is_write_tool, MemoizeConfig, ToolMemoizer (LRU + invalidation)
  - [x] `W11.3` `cutctx/proxy/memoize_interceptor.py` — wire-format detection (OpenAI / Anthropic / Google), fabricated tool_result on hit, passthrough on miss, byte-identical payload
  - [x] `W11.4` Write-invalidation correctness: read → edit → read returns fresh content
  - [x] `W11.5` `SavingsSource.MEMOIZATION` registration + dashboard aggregation
- [x] `WS10` Output-side optimization (branch feat/ws10-output-optimize, PR #5)
  - [x] `W10.1-4` `cutctx/proxy/output_optimizer.py` — 3 levers (diff-edit steering, max_tokens auto-tuning, style shaping) with per-session safety rail
  - [x] `W10.5` `SavingsSource.OUTPUT_OPTIMIZATION` registration + dashboard aggregation
- [x] `WS13` Batch-API arbitrage (branch feat/ws13-batch-routing, PR #6)
  - [x] `W13.1` Eligibility gate (explicit, never inferred) — header `x-cutctx-batch: allow` OR allowlisted internal origin
  - [x] `W13.2` Internal queue state (pending/completed/failed/total)
  - [x] `W13.5` `SavingsSource.BATCH_ROUTING` registration
- [~] `WS19` Compression autopilot (branch feat/ws19-autopilot, PR #7)
  - [x] `W19.1` Signal types (QualitySignal, LevelAdjustment, AutopilotStats)
  - [x] `W19.2` Pure deterministic controller (no ML); bad-signal drops level by 1, K-clean raises by 1
  - [x] `W19.3` Bounded step + clamping (min_level=1, max_level=5, hysteresis_window=10)
- [x] `W19.4` Per-task-type isolation within the pure controller
- [x] `W19.5` Pipeline wiring + flag-off/persistence coverage
- [x] `W19.6` Overview sparkline + docs

Status (2026-07-02, end of session):
- WS21.1: 56 tests pass
- WS16: 552/552 broader regression pass (branch feat/ws16-normalize, PR #3)
- WS11: 613/613 broader regression pass (branch feat/ws11-memoize, PR #4)
- WS10: 331/331 broader regression pass (branch feat/ws10-output-optimize, PR #5)
- WS13: 103/103 broader regression pass (branch feat/ws13-batch-routing, PR #6)
- WS19: controller-only branch gap is now closed in the current worktree with stateful proxy-level pipeline wiring, `/stats` autopilot exposure, Overview surfacing, Governance/docs updates, and focused regression coverage (`56 passed` in the intelligence/autopilot/dashboard slice plus `dashboard/e2e/overview.spec.js` green)
- 5 PRs open, 0 merged into main; no work merged this session
- Per session policy: 5 PRs sit ready for review, each behind a clear "what / why / deferred items" section

Remaining undone (per the original priority list):
- WS18: Learned per-customer compression policies (PRIMARY MOAT per spec). Requires a written
  spike before productization per the spec: 'Phase A — learned policy table (ship this; no
  model training).' Spiked the design in the test file; needs the actual `cutctx policies`
  CLI + the policy.db + the `compute_biases` hook wiring + the self-healing eviction.
- WS4: Context policy engine MVP (Phase 2 from strategy-implementation-plan.md) — redaction
  rules + cumulative per-agent/per-team budgets
- WS5: Org-scope memory + export/import (depends on org identity plumbing)
- WS6: Learn telemetry aggregation (design + opt-in scaffolding; egress not implemented)
- WS7: Context Assurance package (EE): CCR ledger + retention + evidence export
- WS8: Session replay alpha: event stream + replay API + dashboard page
- WS9: Design-partner readiness: end-to-end demo script + release checklist
- WS1 (P1.1-P1.4): Repositioning content (README, docs, pitch, llms.txt, outreach)
- WS2: Agent Context Report v1 (5-source attribution rolled into the WS2 reports)
- WS3: Quality-at-budget benchmark v1 (provider-native-compaction comparison)

Order of remaining work (per savings-moat-priority-todo.md):
1. WS16 (done)
2. WS11 (done)
3. WS10 (done)
4. WS13 (done)
5. WS19 (current worktree wired; branch diff still unmerged into `main`)
6. WS18 (PRIMARY MOAT — start next session)
7. WS4-WS9 (Phase 2 from strategy-implementation-plan.md)

Reconciliation (2026-07-03): the 552/613/331/103 counts above are historical
snapshots from each branch's own (smaller, now-stale) test suite and are not
literally reproducible against today's ~7907-test suite — that's expected,
not a red flag. Independently re-verified all four branches today against
active source in isolated git worktrees (`git worktree add ... <branch>`,
run the shared `.venv`'s pytest with cwd = worktree so `import cutctx`
resolves to the branch's own source, not the main repo's editable-install
path — and remember to copy the gitignored `cutctx/_core.abi3.so` Rust
extension into the worktree first, since a bare worktree checkout never has
build artifacts):
- WS10 (`feat/ws10-output-optimize`): 1 ahead/0 behind main, clean merge,
  zero regressions from its own diff. The 2 extra failures beyond the usual
  7 pre-existing dashboard/docs Playwright flakiness (`test_docs_truthfulness
  ::test_community_stats_docs_do_not_claim_realtime_fetch`,
  `test_proxy_savings_history.py::test_dashboard_includes_history_toggle_and_endpoint`)
  already fail on `main` itself (missing `docs/lib/telemetry.ts`, pre-rebuild
  dashboard bundle) — not caused by this branch. **GO.**
- WS11 (`feat/ws11-memoize`): 1 ahead/1 behind main, clean merge, zero
  regressions — same 7 pre-existing + the same 2 main-baseline failures
  above, nothing new. **GO.**
- WS13 (`feat/ws13-batch-routing`): 1 ahead/0 behind main, clean merge, zero
  regressions — batch_router/batch_routing tests pass cleanly. **GO.**
- WS16 (`feat/ws16-normalize`): 1 ahead/1 behind main, clean merge, zero
  regressions from its own diff. 4 extra failures (`test_ee_audit_store_hmac
  .py`) are a **real, pre-existing gap, not a false positive** — this
  correction supersedes the "only exists on feat/ws19-autopilot" note
  written earlier the same day. `git branch --all --contains f38ca115`
  confirms `feat/ws16-normalize` already carries this commit and its own
  copy of the test file; the branch predates `feat/ws19-autopilot`, it did
  not inherit the file from it. The 4 failing tests are an intentionally-red
  contract suite documenting that `cutctx_ee/audit/store.py`'s
  `_compute_hash()` still concatenates the secret with `hashlib.sha256()`
  instead of using `hmac.new()` — a genuine length-extension vulnerability
  in the audit chain that WS16 documented but did not fix. Tracked as open
  work below, not blocking this merge. **GO** (HMAC gap carried forward as
  known, tracked debt).

All four are safe to merge into `main` as-is; none merge-conflict against
current `main`. Still 5 PRs open, 0 merged this session — merging is a
deliberate follow-up action, not done automatically as part of this pass.

## Merge execution (2026-07-03)

All five branches (`feat/ws10-output-optimize`, `feat/ws11-memoize`,
`feat/ws13-batch-routing`, `feat/ws16-normalize`, `feat/ws19-autopilot`)
merged sequentially, in that order, into an isolated integration branch
(`integration/merge-ws-branches`, created from `main` in a scratch git
worktree) before touching the real `main`. Merge order matched the
project's own stated priority order above.

Conflict pattern: every branch after the first additively extends
`SavingsSource` (`cutctx/savings/types.py`) with its own enum member, which
predictably re-conflicts `cutctx/savings/types.py`,
`dashboard/src/pages/Overview.jsx`, `tests/test_savings_buyer_report.py`,
and `tests/test_savings_orchestration.py` on every subsequent merge.
Resolution rule applied throughout: keep both sides' additions, never drop
one branch's member/assertion in favor of another's — verified after each
merge by counting unique `SavingsSource` values and grepping for leftover
`<<<<<<<`/`>>>>>>>` markers.

Two conflicts required judgment rather than mechanical combination:
- `tests/test_ee_audit_store_hmac.py` (add/add — both WS16 and WS19
  independently created a file at this path): kept WS16's fuller 14-test
  HMAC contract suite in full and appended WS19's 2 documentation-honesty
  guardrail tests, since the two check different things (one holds the
  implementation to a target it hasn't reached; the other checks that
  docs/comments honestly describe the current, non-HMAC state) and neither
  contradicts the other.
- `docs/enterprise.html`, `docs/pricing.html` (conflicting checkout CTA
  hrefs): kept the newer `?plan=starter` link (from WS16's `f38ca115`,
  2026-07-02) over the older `?product=cutctx-team` quickstart-redirect
  link carried on `feat/ws19-autopilot` (from `06ca87ac`, 2026-06-19),
  cross-verified against `cutctx/billing.py`'s `"team": "starter"`
  plan-key mapping.

One silent (non-conflict-marker) regression was caught by hand: git's
line-based auto-merge of `dashboard/src/pages/Overview.jsx` during the
WS19 merge produced duplicate `const` declarations for
`outputOptimizationUsd`/`memoizationUsd`/`normalizationUsd` (a JS
SyntaxError) because HEAD and WS19 each declared them a few lines apart
without a textual conflict. Fixed by replacing the whole
`LIFETIME_SAVINGS_SOURCES`/`getSessionSavingsUsd` region with WS19's own
clean version, which also correctly adds the `batchRoutingUsd` wiring that
no prior branch had wired into the dashboard. Verified via an
acorn+acorn-jsx parse check (no local `esbuild`/`node --check` support for
`.jsx` in this environment).
