# Savings Moat Priority Todo

## Latest Verification Override - 2026-07-03

- WS7 local Context Assurance and broader WS8 replay hooks are now implemented
  and focused-tested. Remaining work is production packaging, release approval,
  and richer per-handler replay metadata over time rather than the initial
  local ledger/replay-extension implementation.
- Do not run proxy restart/reload loops against shared `com.cutctx.proxy` on
  port 8787. Use `cutctx-dev` on port 8788 for proxy iteration.

Date: 2026-07-02

Source specs:
- `artifacts/savings-moat-expansion-specs.md`
- `artifacts/strategy-implementation-plan.md`

## Current Verified Status Override (2026-07-03)

Use this section as the current source of truth before older branch-audit notes
below:

- WS18 Phase A is complete: policy CLI, watch mode, local SQLite policy table,
  bounded hooks, proxy opt-in, `/stats` `intelligence.policies`, and Overview
  dashboard surfacing are present.
- WS4 is complete for the verified MVP scope. `CUTCTX_CONTEXT_POLICY` now gates
  `/v1/messages`, `/v1/chat/completions`, and `/v1/responses` with default-off
  behavior, pre-forward redaction, and block-rule 403 tests.
- WS5 org-scope memory plumbing, export filtering, and export/import
  round-trip verification for `workspace_id` and `project_id` are present.
- WS6 local-only learn telemetry aggregation is implemented through
  `cutctx learn --aggregate`; sharing remains explicitly unimplemented.
- WS7 Context Assurance is not implemented.
- WS8 session replay alpha is implemented for context-policy block/redaction
  decisions, with replay API and dashboard page. It still needs compressed,
  retrieved, injected, and CCR lifecycle replay events before the broader WS8
  promise is complete.
- WS9 design-partner artifacts exist, but the release checklist still contains
  open release gates.
- WS1-WS3 are partial: README positioning and Agent Context Report v1 exist;
  quality-at-budget benchmark v1 docs and outreach updates remain pending.

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

### Regression run (all 5 branches merged, 8116 tests collected)

First full run: `16 failed, 7856 passed, 244 skipped` (324s). Broken down:
- **8 pre-existing, not caused by this merge** (confirmed by reproducing
  the same 4 spot-checked failures against a clean `main` worktree):
  `test_dashboard_capabilities_toggles_e2e`, `test_dashboard_governance_e2e`,
  `test_dashboard_overview_lifetime_headline` (both cases),
  `test_dashboard_savings_by_model`, `test_dashboard_surfaces_playwright`,
  `test_docs_page`, `test_docs_truthfulness::test_community_stats_docs_do
  _not_claim_realtime_fetch`. Root cause: the dashboard's checked-in built
  bundle (`cutctx/dashboard/assets/`) is stale relative to source across
  every branch (a rebuild step this sandbox doesn't run) and
  `docs/lib/telemetry.ts` is missing on `main` itself — neither is
  introduced by merging these 5 branches.
- **4 pre-existing, tracked security debt**: `test_ee_audit_store_hmac.py`'s
  contract tests (see the WS16 note above) — real, not new.
- **4 real merge fallout, fixed same session**: each of ws10/ws11/ws13/ws16's
  own `test_existing_source_values_unchanged` guard test hardcoded an
  exact-match `SavingsSource` set written before its sibling branches'
  members existed; once merged the enum is correctly a superset. Fixed by
  switching each to `expected.issubset(actual)`, matching the pattern
  already used in `tests/test_savings_buyer_report.py` and
  `tests/test_savings_orchestration.py` — see commit `f9c4c9d3` on
  `integration/merge-ws-branches`.

Second full run after that fix: expected `12 failed` (the 8 dashboard/docs
+ 4 HMAC), `7860 passed` — the only two categories of failure are the ones
documented above, both pre-existing and neither blocking. **All 5 branches
are merged, tested, and clean.**

### Merged and pushed (2026-07-03)

`integration/merge-ws-branches` was fast-forward-merged into local `main`
as `6bb04bfd` (`main` had not diverged, so no second round of conflict
resolution was needed), then pushed: `origin/main` moved
`10e3f219..6bb04bfd`. The integration branch and its scratch worktree were
deleted after the merge landed. The 5 source feature branches
(`feat/ws10-output-optimize`, `feat/ws11-memoize`,
`feat/ws13-batch-routing`, `feat/ws16-normalize`, `feat/ws19-autopilot`)
were left in place, not deleted — safe to prune once their PRs are closed.

## Completed follow-up (2026-07-03)

1. **HMAC audit-chain gap closed in source and local compiled runtime** —
   `cutctx_ee/audit/store.py` now uses `hmac.new(secret, message,
   hashlib.sha256)` over a canonical length-prefixed message. The docs and
   `tests/test_ee_audit_store_hmac.py` now assert the real HMAC contract
   instead of the temporary "secret-keyed SHA-256" truthfulness workaround.
   Local verification rebuilt both ignored EE audit binaries
   (`store.cpython-311-darwin.so` and `store.cpython-312-darwin.so`) and
   passed `tests/test_ee_audit_store_hmac.py` with `18 passed, 16 skipped`.
   Release packaging still needs the normal EE binary rebuild/signing step,
   because `*.so` files are ignored by Git in this checkout.
2. **Dashboard bundle rebuild gap closed for tracked package assets** —
   `make build-dashboard` now copies Vite hashed JS/CSS into the directory
   the proxy actually mounts (`cutctx/dashboard/assets/assets`), then the
   packaged `cutctx/dashboard/index.html` was regenerated. `docs/lib/telemetry.ts`
   exists on current `main`, so the previous "missing telemetry file" note
   was stale. Focused dashboard/docs verification passed: `31 passed`.
3. **Development hygiene guardrail added** — `.pre-commit-config.yaml` now
   includes a local dependency-free `scripts/check_text_hygiene.py` hook to
   catch accidental line-collapsed editable Python/docs/config files before
   heavier lint lanes run.

## Pending

Short current handoff lives in `artifacts/pending-items.md`. Keep it updated
alongside this detailed tracker and `CHANGELOG.md` whenever progress changes.

### WS18 — Learned per-customer compression policies

**Phase A is now complete** (`fix/ws20-memcache-optimize`):

| Item | Status | Details |
|------|--------|---------|
| Outcome aggregation + SQLite schema | ✅ Done | `policy_learning.py`: `init_db()`, `train_from_events()`, `LearnedPolicy` dataclass |
| `cutctx policies show/train/reset` CLI | ✅ Done | `cli/policies.py`: all 4 commands |
| `compute_biases` hook | ✅ Done | `LearnedPolicyHooks.compute_biases()` |
| Self-healing eviction | ✅ Done | `evict_unsafe_policies()` + CLI command |
| Proxy flag wiring | ✅ Done | `--enable-learned-policies` / `CUTCTX_LEARNED_POLICIES=1` |
| `--watch` ergonomics | ✅ Done | `cutctx policies train --watch` with `--poll-interval` (default 30s) |
| Dashboard surfacing | ✅ Done | `/stats` intelligence.policies section + `PoliciesPanel` in Overview |
| Phase-B spike notes | ✅ Done | See below |

#### Phase-B spike: per-customer Kompress adapters

**Gate**: ≥15% headroom improvement data from Phase A production use (not yet
available — no Phase A deployment data exists).

**Concept**: Train per-customer Kompress strategy parameters from outcome
events instead of deriving the 3-bucket aggressiveness heuristic. The Phase A
`aggresive/balanced/conservative` labels are replaced by learned Kompress
settings: `target_ratio`, `max_retention`, `structural_priority`,
`delta_threshold`.

**Proposed design**:
1. Extend the `learned_policies` SQLite schema with a new
   `kompress_config_json` column holding per-selector Kompress parameters.
2. Add a `train --kompress` flag that runs a short Bayesian (or
   grid-search) optimization sweep over Kompress parameter space for each
   `(tool_name, content_type, repo)` group, using `avg_ratio` + `retrieval_rate`
   as the objective.
3. Add a new `KompressPolicyHooks(CompressionHooks)` that applies these
   parameters through the existing `kompress_config` injection point (in
   `cutctx/transforms/compression_policy.py`).
4. Keep Phase A heuristics as the cold-start fallback until Kompress
   parameters have converged for that selector.

**Risks**:
- Kompress is a C-extension boundary; hot-loading per-request config
  changes needs careful benchmarking.
- Bayesian optimization adds a training-time cost that may not justify
  the incremental improvement over Phase A heuristics.
- Without Phase A production data, the 15% headroom threshold is
  conjectural.

**Decision**: Revisit when Phase A has ≥3 customer deployments with
≥1M compressed tokens each.

### WS4–WS9 (Phase 2, per `strategy-implementation-plan.md`)

None started:
- **WS4**: Context policy engine MVP (redaction rules + cumulative
  per-agent/per-team budgets)
- **WS5**: Org-scope memory + export/import (depends on org identity
  plumbing)
- **WS6**: Learn telemetry aggregation (design + opt-in scaffolding; egress
  not implemented)
- **WS7**: Context Assurance package (EE): CCR ledger + retention +
  evidence export
- **WS8**: Session replay alpha: event stream + replay API + dashboard page
- **WS9**: Design-partner readiness: end-to-end demo script + release
  checklist

### WS1–WS3 (repositioning/reporting work)

Not started: README/docs/pitch/llms.txt/outreach content, Agent Context
Report v1, and the quality-at-budget benchmark v1.

### Housekeeping

The 5 now-merged feature branches and their PRs can be closed/deleted once
confirmed no longer needed; `main` is 0 commits ahead/behind `origin/main`
as of this push. The rebuilt EE `.so` files are ignored by Git, so release
packaging must rebuild and sign EE binaries before publishing.
