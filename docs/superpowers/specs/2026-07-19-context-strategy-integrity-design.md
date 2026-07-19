# Context Strategy Request-Integrity Remediation

**Date:** 2026-07-19  
**Status:** Approved  
**Scope:** Rust proxy adaptive context strategies

## Problem

The first active implementation of `SelectiveClear`, `SnapshotResume`, and
`SmartCompact` introduced three request-integrity risks:

1. Structural strategies can separate provider tool calls from their results.
2. OpenAI and Bedrock live-zone compression can receive a CCR store when
   `--context-strategies` is disabled, changing their pre-feature wire output.
3. Structural application conflates ineligibility with internal failure, writes
   CCR data before the final body is known to be valid, and exposes no
   application outcome metric.

The implementation also omitted two metrics required by
`spec-smart-context-strategies.md`, made snapshot content keys depend on wall
clock time, and lacks provider-level regression fixtures for these invariants.

## Safety Invariants

- A transformed request must never contain a tool call without its corresponding
  result, or a result without its corresponding call, when the input pair was
  complete.
- With context strategies disabled, OpenAI Chat, OpenAI Responses, and Bedrock
  must preserve their pre-feature CCR behavior and upstream bytes.
- Anthropic's pre-existing live-zone CCR behavior must remain unchanged.
- A failed structural application must forward the original bytes, emit a
  bounded warning/metric outcome, and leave no newly written CCR entries.
- Every marker in a successfully transformed body must resolve from the CCR
  store.
- Snapshot keys must be deterministic for identical session identity and
  snapshotted messages.

## Design

### Tool-aware eligibility

Introduce provider-neutral tool linkage extraction over a request item:

- Anthropic content blocks: `tool_use.id` and `tool_result.tool_use_id`.
- OpenAI Chat: `tool_calls[*].id`, `role=tool`, and `tool_call_id`.
- OpenAI Responses: call/output item `call_id` values, including function,
  local-shell, apply-patch, computer, and other `*_call`/`*_call_output`
  variants.

`SelectiveClear` excludes any item containing a tool call, tool result, tool
reference, or mixed text/tool content. It may continue clearing unrelated text
turns in the same session.

`SnapshotResume` may remove complete call/result pairs together. Before applying
the selected range, compare calls and results in the frozen prefix, snapshot
range, and retained tail. Reject the strategy as ineligible if an identifier
crosses either boundary. A tool-bearing boundary item with no usable identifier
also fails closed to no structural mutation.

### Feature-off CCR compatibility

Separate two concepts currently represented by `ccr_for_request`:

- `structural_ccr`: available only to an enabled, selected structural strategy.
- `live_zone_ccr`: provider-compatible CCR passed into block compression.

Anthropic retains its pre-feature Team+ CCR behavior. OpenAI Chat, OpenAI
Responses, and both Bedrock invoke paths pass no live-zone CCR when context
strategies are disabled. When strategies are enabled, CCR is available to
SmartCompact and structural strategies under the existing license gate.

### Explicit, atomic application outcomes

Change structural strategy APIs to:

```rust
Result<Option<StructuralMutation>, StrategyApplyError>
```

`Ok(Some(_))` means applied, `Ok(None)` means safely ineligible, and `Err(_)`
means an internal parse/range/serialization invariant failed.

Construct replacements and pending CCR writes in memory. Apply and validate all
byte-range replacements first; only then commit pending writes and update
session snapshot state. Call sites forward the original bytes on `Ok(None)` or
`Err`, while `Err` additionally emits a warning containing request ID,
provider, strategy, and bounded error kind.

Add
`proxy_context_strategy_application_total{strategy,outcome}` with outcomes
`applied`, `ineligible`, and `error`.

### Required observability

- Add `proxy_context_strategy_signal_utilization` with fixed buckets
  `0.1, 0.2, ..., 1.0`, observed once per successful strategy decision.
- Add `proxy_context_strategy_override_invalid_total`, incremented whenever a
  non-UTF-8 or unknown `x-cutctx-strategy` value is ignored.
- Preserve `proxy_context_strategy_selected_total` as a selection metric;
  application outcomes are reported separately.

All label vocabularies remain bounded.

### Deterministic snapshots

Remove `created_unix` from the content-addressed snapshot document. The stored
payload becomes the deterministic serialization of:

```json
{"version":1,"session_key":"...","messages":[...]}
```

An identical session snapshot therefore receives the same CCR key after state
eviction or process restart. Existing version-1 snapshots containing
`created_unix` remain readable because matching ignores unknown fields.

## Error Handling

- Tool-boundary risk is normal ineligibility, not an internal error.
- Malformed request JSON remains passthrough and does not create CCR state.
- Internal range/shape inconsistencies produce `StrategyApplyError`, a warning,
  and an `error` application metric.
- No error path changes the forwarded body or session snapshot pointer.

## Verification

TDD regressions will cover:

1. SelectiveClear skips Anthropic mixed text/tool blocks, OpenAI assistant
   `tool_calls`, Chat tool results, and Responses call/output items.
2. SnapshotResume accepts complete pairs inside its range and rejects pairs
   crossing the frozen or retained-tail boundary for all provider shapes.
3. Identical snapshots deduplicate without remembered session state.
4. Simulated application failure leaves the CCR store unchanged.
5. Context-strategies-off produces pre-feature-equivalent upstream bodies for
   OpenAI Chat, OpenAI Responses, Bedrock invoke, and Bedrock streaming.
6. Anthropic CCR behavior remains available independent of the strategy flag.
7. Utilization, invalid override, and application outcome metrics appear with
   bounded labels and expected values.

Focused unit and wire-level integration suites run first, followed by formatting,
Clippy with warnings denied, the Rust workspace test suite, and relevant Python
workflow guards.

## Explicit Non-change

The Rust coverage workflow remains artifact-based. GitHub reports no branch
protection, repository ruleset, or merge-commit check requiring Codecov, so this
remediation does not reintroduce an unconfigured third-party upload.
