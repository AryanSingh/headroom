# Strategy Implementation Notes — WS11 (Tool-Result Memoization)

Per `artifacts/strategy-implementation-plan.md` §0.3, this file tracks
deferred refactors, pre-existing baseline failures, and notes that
arose during WS11 implementation. Every implementing agent should
update this file when work reveals a needed refactor or a baseline
caveat that the per-task gate would otherwise miss.

## WS11 — Tool-Result Memoization

**Status (2026-07-02):** Steps W11.1 through W11.5 complete and
merged to branch `feat/ws11-memoize`. 613/613 regression tests
pass on the WS11 surface (CCR + dedup + intelligence + savings).

### What landed

- `cutctx/proxy/memoizer.py` — pure module: `canonicalize_args` (sorted
  JSON, path normalization, pagination-irrelevant field stripping,
  idempotent), `derive_key` (SHA-256 truncated to 32 hex), `is_write_tool`,
  `MemoizeConfig` (default-off), `MemoizeDecision`, `MemoizeStats`,
  `MemoizeEntry`, `ToolMemoizer` (per-session LRU with 256-entry cap,
  whole-session write-invalidation).
- `cutctx/proxy/memoize_interceptor.py` — thin extension layer:
  `MemoizeInterceptor.intercept_tool_calls(response, session_id)` that
  detects tool calls in OpenAI / Anthropic / Google response formats,
  asks the memoizer, and fabricates a tool_result (byte-identical to
  the stored payload) on a hit. `InterceptedToolResult` / `InterceptResult`
  / `InterceptedToolCall` are the public types.
- `cutctx/savings/types.py` — `SavingsSource.MEMOIZATION` enum member
  added (additive per spec). Labels + descriptions updated. The savings
  model grew from 7 to 8 sources.
- `dashboard/src/pages/Overview.jsx` — `LIFETIME_SAVINGS_SOURCES`
  extended with `('memoization_savings_usd', 'memoization')`; the
  per-session aggregator sums the new source.
- 3 new test files:
  - `tests/test_proxy_memoizer.py` — 34 tests (canonicalizer, key
    derivation, allowlist, write-tool detection, LRU, invalidation,
    BDD scenarios including the spec's "read → edit → read returns
    fresh" correctness test).
  - `tests/test_proxy_memoize_interceptor.py` — 12 tests (flag-off
    no-op, cache hit fabrication, cache miss passthrough, mixed tool
    calls, session isolation, byte-identical content, OpenAI format).
  - `tests/test_savings_types_memoization.py` — 8 tests (enum
    registration, additive contract, aggregation, dashboard tolerance,
    round-trip).
- 2 existing test files updated to be additive:
  - `tests/test_savings_buyer_report.py` — empty-state JSON test now
    asserts baseline sources are a subset + the new MEMOIZATION source
    is present.
  - `tests/test_savings_orchestration.py` — `test_all_five_sources_present`
    now asserts baseline 7 + WS11 MEMOIZATION is present without
    hard-coding the total count.

### Deferred items (recorded here per §0.3)

- **W11.6: integrate `MemoizeInterceptor` into the existing
  `cutctx/ccr/response_handler.py` pipeline.** The interceptor is
  shipped as a standalone module; the call site in the live
  `CCRResponseHandler` flow has not been wired. A follow-up should
  add a call to `interceptor.intercept_tool_calls(response, session_id)`
  in the upstream pipeline after the LLM response is received,
  and call `interceptor.memoizer.record(...)` after the upstream
  tool calls return. The flag-off default ensures the integration
  is a no-op (zero behavior change) until CUTCTX_MEMOIZE=1 is set.

- **The interceptor does NOT mutate the response object.** The
  `InterceptResult.response` is the same object as the input. The
  fabricated tool_results are returned in `result.fabricated` and
  the caller (the upstream pipeline in the W11.6 integration) is
  responsible for appending them as `tool` role messages. This is
  by design — the interceptor is a pure inspection layer; mutation
  is the caller's responsibility. Flag-off: the same response
  reference is returned; no copies, no mutations, no state growth.

- **The memoizer is session-scoped only.** The spec mentions "fleet
  dedup + shared org CCR" as a separate workstream (WS12). The WS11
  implementation does not address the cross-agent sharing case. A
  follow-up WS12 work would extend the memoizer to optionally scope
  to org / workspace.

- **Pagination-irrelevant field stripping is hard-coded to a small
  set** (`page`, `page_size`, `cursor`, `offset`, `limit`). If
  additional pagination fields appear in a future tool version,
  they would be considered part of the args and would defeat
  memoization across different pagination values. A future
  enhancement could make the drop-list configurable per tool.

- **No automated time-based invalidation.** The spec's default TTL
  ("session lifetime, size-capped LRU 256 entries/session") is
  implemented as LRU eviction only. Time-based TTL is not
  implemented. Per the spec, "When in doubt, flush the whole
  session cache" is the conservative behavior on writes; the
  time-based case is a future enhancement.

- **No `CUTCTX_MEMOIZE` env-var read in the proxy startup path.**
  The config defaults to `enabled=False`; the only way to enable
  is to construct `MemoizeConfig(enabled=True)`. The full env-var
  integration in `cutctx/proxy/server.py` is a W11.6 follow-up.

### Pre-existing baseline failures (untouched per §0.1)

- **Dashboard e2e tests** (Playwright in `dashboard/e2e/`) are NOT
  discoverable by `pytest` from the repo root. They require
  `cd dashboard && npx playwright test`. The WS11 work did NOT run
  the Playwright suite. The WS11 dashboard aggregator changes
  were tested only at the unit level.

- **Proxy e2e tests** (in `tests/e2e_*.py` glob) returned 0 items
  collected by pytest. The actual e2e coverage lives in JS/TS
  harnesses that pytest cannot discover.

- **2 SWIG DeprecationWarnings** in the broader regression suite
  are pre-existing, unrelated to WS11, and not addressed here.

- **`test_dedup.py` does not exist** in this worktree. The dedup
  tests are scattered across `test_intelligence_pipeline.py`,
  `test_critical_gaps.py`, `test_drain3_compressor.py`, etc. The
  WS11 baseline ran these 310 tests; the WS11 work did not
  consolidate them into a single `test_dedup.py` file (would
  be a separate refactor).

### Per-task gate results

| Gate | Result |
|---|---|
| Targeted new tests pass (W11.1-2 memoizer) | 34/34 PASS |
| Targeted new tests pass (W11.3 interceptor) | 12/12 PASS |
| Targeted new tests pass (W11.5 savings source) | 8/8 PASS |
| Full WS11 surface (CCR + dedup + intelligence + savings) | 613/613 PASS |
| Flag-off parity (golden) | confirmed byte-identical for `MemoizeConfig()` default |
| Flag-off state growth (golden) | confirmed: 100 calls with flag off produce 0 entries, 0 hits, 0 misses |
| Write-invalidation correctness (W11.4) | confirmed via `test_bdd_read_edit_read_returns_fresh_content` and `test_write_tool_flushes_overlapping_session_cache` |
| Byte-identical fabricated content | confirmed via `test_interceptor_fabricated_content_is_byte_identical` |
| Docs build | not run (no docs touched in WS11) |
| Coverage | tests added alongside code (54 new tests across 3 new files) |
| One commit per task | one commit, four steps documented in commit message |
