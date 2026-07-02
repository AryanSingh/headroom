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

Status:
- `2026-07-02`: `WS21.1` shared marker contract path implemented.
- Focused verification passed: `tests/test_ccr_markers.py`, `tests/test_ccr_tool_injection.py`, `tests/test_ccr_tool_always_on.py`, and `tests/test_ccr_response_handler_extra.py` (`56 passed`).

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
- [x] `WS19` Compression autopilot (branch feat/ws19-autopilot, PR #7)
  - [x] `W19.1` Signal types (QualitySignal, LevelAdjustment, AutopilotStats)
  - [x] `W19.2` Pure deterministic controller (no ML); bad-signal drops level by 1, K-clean raises by 1
  - [x] `W19.3` Bounded step + clamping (min_level=1, max_level=5, hysteresis_window=10)
  - [x] `W19.4` Per-task-type isolation
  - [x] `W19.5` Audit/RequestOutcome-adjacent records

Status (2026-07-02, end of session):
- WS21.1: 56 tests pass
- WS16: 552/552 broader regression pass (branch feat/ws16-normalize, PR #3)
- WS11: 613/613 broader regression pass (branch feat/ws11-memoize, PR #4)
- WS10: 331/331 broader regression pass (branch feat/ws10-output-optimize, PR #5)
- WS13: 103/103 broader regression pass (branch feat/ws13-batch-routing, PR #6)
- WS19: 736/736 broader regression pass (branch feat/ws19-autopilot, PR #7)
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
5. WS19 (done)
6. WS18 (PRIMARY MOAT — start next session)
7. WS4-WS9 (Phase 2 from strategy-implementation-plan.md)
