# Context Strategy Request-Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make active context strategies tool-pair safe, byte-compatible when disabled, failure-atomic, observable, and deterministically deduplicated.

**Architecture:** A focused `tool_integrity` module classifies provider tool linkage independently from strategy selection and mutation. Structural application returns an explicit `Result<Option<_>>`, stages CCR writes until byte surgery succeeds, and reports bounded application outcomes. Provider call sites separate structural CCR from live-zone CCR so pre-feature behavior is preserved exactly when the flag is off.

**Tech Stack:** Rust 1.95+, serde/serde_json `RawValue`, Prometheus 0.13.4, Axum/Tokio, wiremock, Cargo workspace tests.

## Global Constraints

- Never forward a complete input tool pair as an orphaned call or result.
- Preserve pre-feature Anthropic CCR behavior.
- OpenAI Chat, OpenAI Responses, and Bedrock must not receive new live-zone CCR markers while context strategies are disabled.
- No failed structural application may write CCR data or update the session snapshot pointer.
- Metric labels use bounded vocabularies only.
- No new dependencies.
- Preserve exact bytes outside mutation ranges.
- Use TDD: every production behavior change follows a witnessed failing regression.

---

### Task 1: Provider-neutral tool linkage and SelectiveClear eligibility

**Files:**
- Create: `crates/cutctx-proxy/src/tool_integrity.rs`
- Modify: `crates/cutctx-proxy/src/lib.rs`
- Modify: `crates/cutctx-proxy/src/strategy_shadow.rs`
- Test: `crates/cutctx-proxy/src/tool_integrity.rs`
- Test: `crates/cutctx-proxy/src/strategy_apply.rs`

**Interfaces:**
- Produces: `pub(crate) fn contains_tool_protocol(item: &Value) -> bool`
- Produces: `pub(crate) fn snapshot_range_preserves_tool_pairs(items: &[Value], start: usize, end: usize) -> bool`
- Consumes: provider JSON values already parsed by strategy selection/application.

- [ ] **Step 1: Add failing classifier tests**

Add table-driven unit fixtures covering:

```rust
json!({"role":"assistant","content":[
    {"type":"text","text":"large explanation"},
    {"type":"tool_use","id":"toolu_1","name":"search","input":{}}
]})
json!({"role":"user","content":[
    {"type":"tool_result","tool_use_id":"toolu_1","content":"result"}
]})
json!({"role":"assistant","content":"calling","tool_calls":[
    {"id":"call_1","type":"function","function":{"name":"search","arguments":"{}"}}
]})
json!({"role":"tool","tool_call_id":"call_1","content":"result"})
json!({"type":"function_call","call_id":"call_2","name":"search","arguments":"{}"})
json!({"type":"function_call_output","call_id":"call_2","output":"result"})
```

Assert every fixture is tool-bearing and ordinary text messages are not.

- [ ] **Step 2: Run the classifier test and witness RED**

Run:

```bash
cargo test -p cutctx-proxy tool_integrity -- --nocapture
```

Expected: compilation failure because `tool_integrity` and its exported functions do not exist.

- [ ] **Step 3: Implement linkage extraction**

Create private `ToolLinks { calls: HashSet<String>, results: HashSet<String>, has_protocol: bool, has_unlinked: bool }`.

Recognize:

```rust
// Anthropic blocks
type == "tool_use"              => call id from "id"
type == "tool_result"           => result id from "tool_use_id"

// Chat
tool_calls[*].id                => call id
role == "tool"                  => result id from "tool_call_id"

// Responses
type.ends_with("_call")         => call id from "call_id"
type.ends_with("_call_output")  => result id from "call_id"
```

Any item/block whose type contains `tool`, or whose role is `tool`, sets `has_protocol`; missing identifiers set `has_unlinked`.

- [ ] **Step 4: Add a failing SelectiveClear regression**

Construct a long, low-relevance assistant message containing both a text block and `tool_use`, plus its adjacent `tool_result`, and one unrelated long plain-text candidate. Assert the tool-bearing pair is byte/value-identical while the unrelated turn is elided.

Run:

```bash
cargo test -p cutctx-proxy strategy_apply::tests::selective_clear_skips_tool_protocol_turns -- --exact
```

Expected: FAIL because the mixed assistant content is collapsed and its tool block disappears.

- [ ] **Step 5: Exclude tool-bearing turns during scoring**

In `low_value_turn_indices`, add:

```rust
&& !crate::tool_integrity::contains_tool_protocol(message)
```

This keeps both selection signals and application candidates consistent.

- [ ] **Step 6: Run focused tests and commit**

Run:

```bash
cargo test -p cutctx-proxy tool_integrity -- --nocapture
cargo test -p cutctx-proxy strategy_apply::tests::selective_clear_skips_tool_protocol_turns -- --exact
```

Expected: PASS.

Commit:

```bash
git add crates/cutctx-proxy/src/lib.rs crates/cutctx-proxy/src/tool_integrity.rs crates/cutctx-proxy/src/strategy_shadow.rs crates/cutctx-proxy/src/strategy_apply.rs
git commit -m "fix(proxy): preserve tool turns during selective clear"
```

### Task 2: Snapshot boundary integrity and deterministic keys

**Files:**
- Modify: `crates/cutctx-proxy/src/tool_integrity.rs`
- Modify: `crates/cutctx-proxy/src/strategy_apply.rs`
- Test: `crates/cutctx-proxy/src/tool_integrity.rs`
- Test: `crates/cutctx-proxy/src/strategy_apply.rs`

**Interfaces:**
- Consumes: `snapshot_range_preserves_tool_pairs(items, frozen_count, snapshot_end)`.
- Produces: deterministic version-1 snapshot payload without wall-clock fields.

- [ ] **Step 1: Add failing boundary tests**

Cover three partitions: frozen prefix, proposed snapshot range, and retained tail.

Assert:

```rust
// complete pair in snapshot range
assert!(snapshot_range_preserves_tool_pairs(&items, 1, 4));

// call in snapshot, result in retained tail
assert!(!snapshot_range_preserves_tool_pairs(&items, 1, 3));

// call in frozen prefix, result in snapshot
assert!(!snapshot_range_preserves_tool_pairs(&items, 2, 4));
```

Repeat linkage shapes for Anthropic `tool_use_id`, Chat `tool_call_id`, and Responses `call_id`. Add malformed tool-bearing boundary fixtures without identifiers and assert fail-closed.

- [ ] **Step 2: Run boundary tests and witness RED**

Run:

```bash
cargo test -p cutctx-proxy tool_integrity::tests::snapshot -- --nocapture
```

Expected: FAIL because snapshot boundary validation is not implemented.

- [ ] **Step 3: Implement partition-safe pairing**

Extract `ToolLinks` for each of the three partitions. Return false when:

```rust
left.calls intersects middle.results
left.results intersects middle.calls
middle.calls intersects right.results
middle.results intersects right.calls
left.calls intersects right.results
left.results intersects right.calls
```

Also return false when either item adjacent to `start` or `end` is tool-bearing but has an unusable identifier.

- [ ] **Step 4: Add failing SnapshotResume application tests**

Assert `apply_snapshot_resume` returns no mutation for a pair crossing the retained-tail boundary, while a complete pair wholly inside the range is replaced together and leaves no call/result orphan.

Add a second invocation with a fresh `InMemoryCcrStore` session-state hint of `None`, the same body, and the same session key. Assert the generated snapshot key equals the first key.

Expected before implementation:

- crossing pair is split;
- deterministic-key test fails after a one-second separation because `created_unix` changes the payload.

- [ ] **Step 5: Gate the range and remove the timestamp**

Before snapshot serialization:

```rust
if !crate::tool_integrity::snapshot_range_preserves_tool_pairs(
    messages,
    frozen_count,
    snapshot_end,
) {
    return Ok(None);
}
```

Serialize only:

```rust
json!({
    "version": 1,
    "session_key": session_key,
    "messages": snapshotted_messages,
})
```

Keep `cached_snapshot_matches` tolerant of legacy extra fields.

- [ ] **Step 6: Run focused tests and commit**

Run:

```bash
cargo test -p cutctx-proxy tool_integrity::tests::snapshot -- --nocapture
cargo test -p cutctx-proxy strategy_apply::tests::snapshot -- --nocapture
```

Expected: PASS.

Commit:

```bash
git add crates/cutctx-proxy/src/tool_integrity.rs crates/cutctx-proxy/src/strategy_apply.rs
git commit -m "fix(proxy): keep snapshot tool pairs within boundaries"
```

### Task 3: Failure-atomic structural application

**Files:**
- Modify: `crates/cutctx-proxy/src/strategy_apply.rs`
- Modify: `crates/cutctx-proxy/src/proxy.rs`
- Modify: `crates/cutctx-proxy/src/bedrock/invoke.rs`
- Modify: `crates/cutctx-proxy/src/bedrock/invoke_streaming.rs`
- Test: `crates/cutctx-proxy/src/strategy_apply.rs`

**Interfaces:**
- Produces: `pub(crate) enum StrategyApplyError` with `as_str() -> &'static str`.
- Produces: `pub(crate) type StrategyApplyResult = Result<Option<StructuralMutation>, StrategyApplyError>`.
- Consumes: the tool-boundary predicate from Task 2.

- [ ] **Step 1: Add a failing atomicity test**

Introduce a test-only replacement helper input with an invalid or overlapping range and a pending CCR write. Assert:

```rust
assert!(result.is_err());
assert!(store.is_empty());
```

Also update existing application tests to unwrap the outer `Result` before expecting an optional mutation.

- [ ] **Step 2: Run the atomicity test and witness RED**

Run:

```bash
cargo test -p cutctx-proxy strategy_apply::tests::failed_application_does_not_commit_ccr_writes -- --exact
```

Expected: compilation failure because application has no explicit error result or staged-write boundary.

- [ ] **Step 3: Result-ify byte surgery and stage writes**

Define bounded error variants:

```rust
MalformedBody
RawViewMismatch
MissingRawItem
InvalidRange
Serialization
```

Make `apply_replacements` return `Result<Vec<u8>, StrategyApplyError>`.
Build `Vec<(String, String)>` pending CCR writes. Produce the full rewritten body first, then call `store.put` for every pending item. Return `Ok(None)` only for normal ineligibility such as an empty candidate set or unsafe tool boundary.

- [ ] **Step 4: Match outcomes at all provider call sites**

For generic proxy and both Bedrock paths:

```rust
match apply_selected_structural_strategy(...) {
    Ok(Some(mutation)) => { record applied; use mutation }
    Ok(None) => { record ineligible; use original bytes }
    Err(error) => {
        tracing::warn!(
            event = "context_strategy_application_failed",
            request_id,
            provider,
            strategy,
            error = error.as_str(),
            "context strategy application failed; forwarding original bytes"
        );
        record error;
        use original bytes
    }
}
```

Update session snapshot state only in the `Ok(Some(_))` path.

- [ ] **Step 5: Run focused tests and commit**

Run:

```bash
cargo test -p cutctx-proxy strategy_apply -- --nocapture
```

Expected: PASS with no CCR entries after the injected failure.

Commit:

```bash
git add crates/cutctx-proxy/src/strategy_apply.rs crates/cutctx-proxy/src/proxy.rs crates/cutctx-proxy/src/bedrock/invoke.rs crates/cutctx-proxy/src/bedrock/invoke_streaming.rs
git commit -m "fix(proxy): make structural strategy application atomic"
```

### Task 4: Feature-off CCR wire compatibility

**Files:**
- Modify: `crates/cutctx-proxy/src/proxy.rs`
- Modify: `crates/cutctx-proxy/src/bedrock/invoke.rs`
- Modify: `crates/cutctx-proxy/src/bedrock/invoke_streaming.rs`
- Test: `crates/cutctx-proxy/tests/integration_context_strategies.rs`
- Test: `crates/cutctx-proxy/tests/integration_bedrock_invoke.rs`
- Test: `crates/cutctx-proxy/tests/integration_bedrock_streaming.rs`

**Interfaces:**
- Produces: separate `licensed_ccr` and `strategy_ccr`/`live_zone_ccr` values at dispatch.
- Preserves: Anthropic receives `licensed_ccr`; OpenAI and Bedrock receive strategy-gated CCR.

- [ ] **Step 1: Add failing generic provider wire tests**

Start a Team-tier proxy with a real in-memory CCR store, live-zone compression on, and `context_strategies = false`. Send compressible payloads to Chat and Responses. Compare captured upstream bodies with an otherwise identical proxy that has no CCR store. Assert byte equality and no `<<ccr:` marker.

Add Anthropic coverage asserting the Team-tier path still emits its pre-existing CCR marker for the same kind of compressible live-zone content.

- [ ] **Step 2: Run generic wire tests and witness RED**

Run:

```bash
cargo test -p cutctx-proxy --test integration_context_strategies feature_off -- --nocapture
```

Expected: Chat and Responses captured bodies differ because the CCR-backed path appends markers.

- [ ] **Step 3: Separate generic dispatch CCR handles**

Use:

```rust
let licensed_ccr = tier.allows_ccr().then(|| state.ccr_store.as_deref()).flatten();
let strategy_ccr = strategy_decision.as_ref().and(licensed_ccr);
```

Structural strategies and OpenAI live-zone compression consume `strategy_ccr`.
Anthropic live-zone compression consumes `licensed_ccr`.

- [ ] **Step 4: Add failing Bedrock invoke and streaming tests**

Configure Team tier, an in-memory CCR store, `context_strategies = false`, and compressible tool-result/text payloads. Assert the captured signed upstream JSON contains no new CCR marker and matches the no-store path semantically and byte-for-byte where the existing harness exposes raw bytes.

- [ ] **Step 5: Gate Bedrock CCR and run provider tests**

Set Bedrock `ccr_for_request` only when both a strategy decision exists and the license allows CCR.

Run:

```bash
cargo test -p cutctx-proxy --test integration_context_strategies -- --nocapture
cargo test -p cutctx-proxy --test integration_bedrock_invoke -- --nocapture
cargo test -p cutctx-proxy --test integration_bedrock_streaming -- --nocapture
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add crates/cutctx-proxy/src/proxy.rs crates/cutctx-proxy/src/bedrock/invoke.rs crates/cutctx-proxy/src/bedrock/invoke_streaming.rs crates/cutctx-proxy/tests/integration_context_strategies.rs crates/cutctx-proxy/tests/integration_bedrock_invoke.rs crates/cutctx-proxy/tests/integration_bedrock_streaming.rs
git commit -m "fix(proxy): preserve feature-off CCR wire behavior"
```

### Task 5: Complete context-strategy observability

**Files:**
- Modify: `crates/cutctx-proxy/src/observability/metric_names.rs`
- Modify: `crates/cutctx-proxy/src/observability/proxy_metrics.rs`
- Modify: `crates/cutctx-proxy/src/observability/prometheus.rs`
- Modify: `crates/cutctx-proxy/src/observability/mod.rs`
- Modify: `crates/cutctx-proxy/src/strategy_shadow.rs`
- Test: `crates/cutctx-proxy/src/observability/proxy_metrics.rs`
- Test: `crates/cutctx-proxy/src/strategy_shadow.rs`

**Interfaces:**
- Produces: `record_context_strategy_utilization(f64)`.
- Produces: `record_context_strategy_override_invalid()`.
- Produces: `record_context_strategy_application(strategy, outcome)`.

- [ ] **Step 1: Add failing metric catalogue tests**

Assert exact metric names and behavior:

```rust
record_context_strategy_utilization(0.73);
record_context_strategy_override_invalid();
record_context_strategy_application("selective_clear", "error");
```

The scrape must include:

```text
proxy_context_strategy_signal_utilization
proxy_context_strategy_override_invalid_total
proxy_context_strategy_application_total{outcome="error",strategy="selective_clear"}
```

Assert utilization bucket bounds equal `0.1..=1.0` in increments of `0.1`.

- [ ] **Step 2: Run metric tests and witness RED**

Run:

```bash
cargo test -p cutctx-proxy observability::proxy_metrics::tests::context_strategy -- --nocapture
```

Expected: compilation failure because the metric helpers/constants are absent.

- [ ] **Step 3: Implement and register bounded metrics**

Use `Histogram` with `HistogramOpts::buckets((1..=10).map(|n| n as f64 / 10.0).collect())`,
an unlabeled `IntCounter` for invalid overrides, and an `IntCounterVec` labelled only by `strategy,outcome` for application results.

Register all three lazily. In `/metrics`, force-register the histogram without a synthetic observation, force the invalid counter to zero, and force the application vector with `__init__` labels at zero.

- [ ] **Step 4: Add invalid-header and utilization RED tests**

Call `shadow_select_with_config` with:

- `x-cutctx-strategy: definitely-invalid`;
- a non-UTF-8 `HeaderValue`;
- an ordinary valid request selecting a strategy.

Assert invalid counter increments for both invalid headers and utilization histogram sample count increments once for the valid decision.

- [ ] **Step 5: Emit metrics in selection and application paths**

Record utilization immediately after the final decision is resolved. Rewrite header parsing so an existing non-UTF-8 value is warned and counted rather than silently ignored. Wire the application metric into Task 3's call-site outcome matches.

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cargo test -p cutctx-proxy observability::proxy_metrics::tests::context_strategy -- --nocapture
cargo test -p cutctx-proxy strategy_shadow::tests -- --nocapture
```

Expected: PASS.

Commit:

```bash
git add crates/cutctx-proxy/src/observability/metric_names.rs crates/cutctx-proxy/src/observability/proxy_metrics.rs crates/cutctx-proxy/src/observability/prometheus.rs crates/cutctx-proxy/src/observability/mod.rs crates/cutctx-proxy/src/strategy_shadow.rs crates/cutctx-proxy/src/proxy.rs crates/cutctx-proxy/src/bedrock/invoke.rs crates/cutctx-proxy/src/bedrock/invoke_streaming.rs
git commit -m "feat(proxy): complete context strategy observability"
```

### Task 6: Full regression verification and delivery

**Files:**
- Modify only if verification exposes a defect in files already owned by Tasks 1–5.
- Verify: `docs/superpowers/specs/2026-07-19-context-strategy-integrity-design.md`

**Interfaces:**
- Consumes all behavior and tests from Tasks 1–5.
- Produces a reviewable branch with fresh verification evidence.

- [ ] **Step 1: Run formatting and focused strategy suites**

Run:

```bash
cargo fmt --all -- --check
cargo test -p cutctx-proxy strategy_apply -- --nocapture
cargo test -p cutctx-proxy tool_integrity -- --nocapture
cargo test -p cutctx-proxy --test integration_context_strategies -- --nocapture
cargo test -p cutctx-proxy --test integration_bedrock_invoke -- --nocapture
cargo test -p cutctx-proxy --test integration_bedrock_streaming -- --nocapture
```

Expected: all pass.

- [ ] **Step 2: Run static analysis**

Run:

```bash
cargo clippy --workspace --all-targets --all-features -- -D warnings
```

Expected: no warnings or errors.

- [ ] **Step 3: Run the full Rust workspace**

Run:

```bash
cargo test --workspace --all-features
```

Expected: all non-ignored tests pass.

- [ ] **Step 4: Run workflow guards**

Run:

```bash
pytest tests/test_release_workflows.py -q
ruff check tests/test_release_workflows.py
git diff --check
```

Expected: all pass and no whitespace errors.

- [ ] **Step 5: Audit every design requirement**

Confirm from source and test evidence:

- every supported tool protocol has fixtures;
- both snapshot boundaries are guarded;
- staged CCR writes occur after byte surgery;
- all provider call sites match explicit apply results;
- flag-off compatibility tests cover Chat, Responses, Bedrock invoke, and Bedrock streaming;
- Anthropic baseline CCR remains covered;
- three new metric families have production emit sites;
- snapshot payload contains no timestamp;
- no Codecov status dependency was introduced.

- [ ] **Step 6: Commit any final verification-only adjustments**

If no adjustment is needed, do not create an empty commit. Otherwise:

```bash
git add <only-files-corrected-by-verification>
git commit -m "test(proxy): close context strategy integrity gaps"
```

- [ ] **Step 7: Push and open a PR**

```bash
git push -u origin fix/context-strategy-integrity
gh pr create --base main --head fix/context-strategy-integrity --title "fix(proxy): preserve context strategy request integrity" --body-file <prepared-pr-body>
```

Monitor every PR workflow. Diagnose failures from logs, fix root causes with regression tests, and merge only after all executable checks are green.
