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
- [x] `WS11` Tool-result memoization
  - [x] `W11.1-2` `cutctx/proxy/memoizer.py` — canonicalize_args, derive_key, is_write_tool, MemoizeConfig, ToolMemoizer (LRU + invalidation)
  - [x] `W11.3` `cutctx/proxy/memoize_interceptor.py` — wire-format detection (OpenAI / Anthropic / Google), fabricated tool_result on hit, passthrough on miss, byte-identical payload
  - [x] `W11.4` Write-invalidation correctness: read → edit → read returns fresh content
  - [x] `W11.5` `SavingsSource.MEMOIZATION` registration + dashboard aggregation

Status:
- `2026-07-02`: `WS21.1` shared marker contract path implemented.
- Focused verification passed: `tests/test_ccr_markers.py`, `tests/test_ccr_tool_injection.py`, `tests/test_ccr_tool_always_on.py`, and `tests/test_ccr_response_handler_extra.py` (`56 passed`).
- `2026-07-02`: `WS11` complete on branch `feat/ws11-memoize`. New files: `cutctx/proxy/memoizer.py` (module), `cutctx/proxy/memoize_interceptor.py` (interceptor), `tests/test_proxy_memoizer.py` (34 tests), `tests/test_proxy_memoize_interceptor.py` (12 tests), `tests/test_savings_types_memoization.py` (8 tests). Modified: `cutctx/savings/types.py` (MEMOIZATION enum), `dashboard/src/pages/Overview.jsx` (per-source mapping). 2 pre-existing tests updated to be additive. Broader regression: 613/613 tests pass on the WS11 surface. The interception is exposed as `MemoizeInterceptor.intercept_tool_calls(response, session_id)` — the caller wires it into the existing CCR tool handling path. The full integration into `cutctx/ccr/response_handler.py` is documented as a deferred follow-up (W11.6).
