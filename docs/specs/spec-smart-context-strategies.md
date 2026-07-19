# Spec: Smart Context Strategies (Adaptive Compaction)

**Status:** Draft for implementation
**Priority:** P0 (Phase 1) — smallest effort / highest leverage of the P0 set
**Date:** 2026-07-19
**Origin:** `docs/specs/features-from-youtube-research.md` §4
**Depends on:** nothing (pure extension of existing pipeline). Benefits from hooks (`spec-stream-processor-hooks.md`) for observability but does not require them.

---

## 1. Problem

The live-zone compressor applies one fixed behavior per auth mode. `CompressionPolicy` (`crates/cutctx-core/src/compression_policy.rs:148`) already carries the tuning knobs — `volatile_token_threshold`, `max_lossy_ratio`, `toin_read_only` — but per its own module docs they are **plumbed-but-unconsumed**: no detector or compressor reads them. Meanwhile agents accumulate context until they hit manual `/compact` or `/clear`, both of which are blunt. Cutctx sits in exactly the right place (the proxy sees every request's full message array) to pick the right compaction strategy automatically per request, based on observable session signals.

## 2. Goals

- A **strategy selector** that runs once per intercepted request and picks one of four strategies based on measured context signals: `RollingWindow` (existing behavior), `SmartCompact`, `SelectiveClear`, `SnapshotResume`.
- Consume the three dormant `CompressionPolicy` fields so per-auth-mode conservatism actually binds behavior.
- Fully deterministic given (body, policy, session history) — reproducible decisions, loggable rationale.
- Every strategy remains **reversible via CCR** where content is dropped (existing `CcrStore` contract, `crates/cutctx-core/src/ccr/mod.rs`).
- Preserve the frozen-floor cache-safety invariant everywhere (`cache_control.rs::compute_frozen_count`, live-zone byte-range surgery).

## 3. Non-goals (v1)

- Cross-request learning of strategy choice (that's `cutctx learn` / eval-framework territory).
- Client-side `/compact` command replacement — we operate transparently at the proxy; agent CLIs keep their commands.
- OpenAI Responses `previous_response_id` chain reconstruction (snapshot works on materialized message arrays only).
- Python proxy parity (follow-up; keep signal definitions identical).

## 4. Current state (ground truth)

- Dispatch: `forward_http` buffered arm calls `compression::compress_anthropic_request_with_ccr` / `compress_openai_chat_request` / `compress_openai_responses_request` (`crates/cutctx-proxy/src/proxy.rs` ~733–1093), each wrapping the core entry points `compress_*_live_zone[_with_ccr]` in `crates/cutctx-core/src/transforms/live_zone.rs` (`compress_anthropic_live_zone` :621, `_with_ccr` :646, openai chat :2086, responses :2705).
- Live-zone mechanics: byte-range surgery over `serde_json::value::RawValue`; `BlockAction {NoCompressionApplied | Compressed | Excluded}`; `ExclusionReason {BelowFrozenFloor | AboveLiveZone | CacheHotBlockType | ..}`; `CompressionManifest` reports counts.
- Frozen floor: `cutctx_core::cache_control::compute_frozen_count(parsed) -> usize` (:109); proxy wraps as `compression::resolve_frozen_count`. Gated by `Config::cache_control_auto_frozen`.
- Policy: `CompressionPolicy { live_zone_only, cache_aligner_enabled, volatile_token_threshold, max_lossy_ratio, toin_read_only }`, `for_mode(AuthMode)`; Payg/OAuth = {128, 0.45, false}, Subscription = {32, 0.25, true}. Cache-mutation economics already exist: `net_mutation_gain`, `should_mutate_deep`, `break_even_reads` (:262–:302).
- Session identity: no first-class agent id in the Rust proxy; per-session state precedent is `DriftState` (per-session structural-hash LRU, cap 1000, on `AppState`). The Python proxy has the richer `resolve_canary_identity` ladder (`cutctx/proxy/canary_identity.py`) — reimplement the *header subset* in Rust (see §5.2).
- Relevance scoring for "value of a turn": `crates/cutctx-core/src/relevance/` — `RelevanceScorer` trait (base.rs), `BM25Scorer`, `HybridScorer`, factory `create_scorer(tier)` (mod.rs). BM25 is dependency-free and fast — use it; do NOT pull fastembed into the proxy hot path.
- Existing deletion machinery for dropping turns: `transforms/deletion_compaction.rs` (`DeletionCompactor`, `Aggressiveness {Conservative, Moderate, Aggressive}`) and `transforms/adaptive_sizer.rs`.
- Tokenizers: `crates/cutctx-core/src/tokenizer/` (`Tokenizer` trait; `EstimatingCounter` fallback for Anthropic). Library-only today, not yet wired into the proxy — this spec wires it in for signal computation.

## 5. Design

### 5.1 New module `crates/cutctx-core/src/transforms/context_strategy.rs`

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContextStrategy {
    /// Existing live-zone behavior, unchanged. Always the fallback.
    RollingWindow,
    /// Run the full compression pipeline harder: lossy ratio up to
    /// policy.max_lossy_ratio, all applicable transforms enabled.
    SmartCompact,
    /// Drop whole low-value turns (offload to CCR), keep high-value ones.
    SelectiveClear,
    /// Persist a compressed session snapshot to CCR and replace the
    /// dropped prefix with a snapshot pointer + summary block.
    SnapshotResume,
}

/// Observable, deterministic inputs. Computed per request.
#[derive(Debug, Clone)]
pub struct ContextSignals {
    pub total_tokens_est: usize,        // EstimatingCounter over full messages array
    pub model_context_limit: usize,     // from compression/model_limits.rs (proxy crate exposes; see 5.4)
    pub utilization: f32,               // total / limit
    pub message_count: usize,
    pub frozen_message_count: usize,    // cache_control::compute_frozen_count
    pub live_zone_tokens_est: usize,    // tokens above frozen floor
    pub turns_since_frozen_advance: u32,// session state; proxy for "cache prefix is stale"
    pub low_value_turn_ratio: f32,      // fraction of live-zone turns scoring < LOW_VALUE_SCORE
    pub session_request_count: u64,     // session state
}

pub struct StrategyDecision {
    pub strategy: ContextStrategy,
    pub rationale: &'static str,        // bounded vocabulary; goes into manifest + metrics label
    pub signals: ContextSignals,
}

pub fn select_strategy(
    signals: &ContextSignals,
    policy: &CompressionPolicy,
    cfg: &StrategyConfig,
) -> StrategyDecision;
```

### 5.2 Session state (proxy side) — new `crates/cutctx-proxy/src/session_state.rs`

Follow the `DriftState` pattern exactly (per-session LRU on `AppState`, cap 1000):

- Session key: first present of `x-cutctx-session-id` → `x-session-id` → `session-id` → hash of (`authorization`|`x-api-key` + `x-cutctx-user-id` + `x-cutctx-project`) → request_id (non-sticky). This is the Rust subset of Python's `resolve_canary_identity` ladder; keep header names byte-identical to `cutctx/proxy/canary_identity.py` for parity.
- Stored per session: `request_count: u64`, `last_frozen_count: usize`, `turns_since_frozen_advance: u32`, `last_seen: Instant`, `last_snapshot_key: Option<String>`.

### 5.3 Selection rules (deterministic, ordered; first match wins)

Config defaults in `StrategyConfig`; every threshold is a config field, values below are defaults.

```
1. utilization < 0.50                                  → RollingWindow  ("low_utilization")
2. utilization >= 0.85
   && session_request_count >= 3                       → SnapshotResume ("near_limit")
3. low_value_turn_ratio >= 0.40
   && message_count >= 12                              → SelectiveClear ("session_drift")
4. utilization >= 0.50                                 → SmartCompact   ("high_utilization")
5. otherwise                                           → RollingWindow  ("default")
```

Policy binding (this consumes the dormant fields):

- `SmartCompact` passes `policy.max_lossy_ratio` as the hard cap on per-block lossy compression: any `BlockAction::Compressed` whose `compressed_tokens/original_tokens < (1 - max_lossy_ratio)`... — concretely: a block may not lose more than `max_lossy_ratio` of its tokens; blocks that would exceed it are re-emitted as `NoCompressionApplied` and counted in `proxy_compression_rejected_by_token_check_total` (existing counter, `observability/metric_names.rs`).
- `policy.volatile_token_threshold` gates `SelectiveClear`: turns whose token count is below the threshold are never dropped individually (too small to matter; churn risk exceeds win).
- `policy.toin_read_only == true` (Subscription mode) forbids `SelectiveClear` and `SnapshotResume` entirely (both mutate conversation structure); Subscription sessions can only ever get `RollingWindow`/`SmartCompact`. Encode as a hard override after rule evaluation, rationale `"policy_read_only"`.
- Strategies never touch messages below the frozen floor. `SnapshotResume`'s "dropped prefix" means the region **between** the frozen floor and the live-zone tail — cached prefix stays byte-identical.

### 5.4 Strategy implementations

**RollingWindow** — literally the current code path; `select_strategy` returning this must produce byte-identical output to today (regression guarantee).

**SmartCompact** — same live-zone walk, but: (a) enable the full transform set for each `ContentType` including offloads (`pipeline/offloads/`: JsonOffload, LogOffload, DiffOffload, DiffNoise) where today's path is more conservative; (b) lossy cap per policy as above; (c) require CCR store present (`ccr_store.is_some()`), else degrade to RollingWindow with rationale `"no_ccr"` (loud: WARN + metric, per no-silent-fallbacks rule).

**SelectiveClear** — new function in `context_strategy.rs`:

1. Score each live-zone turn with `BM25Scorer` (`relevance/bm25.rs`) against a context string = concatenation of (system prompt tail + last 2 user messages) — the "what does the agent currently care about" proxy.
2. A turn is low-value iff `score < cfg.low_value_score` (default 0.15) AND turn tokens ≥ `policy.volatile_token_threshold` AND turn contains no `ImportanceSignal` match with category `Error|Security` (reuse `signals/line_importance.rs::LineImportanceDetector` over the turn text — never drop error context).
3. Each dropped turn: full original JSON → `CcrStore::put(compute_key(payload), payload)`; replace the turn's content with a single text block: `"[cutctx: turn elided — retrieve with <<ccr:HASH>>]"` using the existing marker format (`ccr/mod.rs::marker_for`, regex `[a-f0-9]{16}`). Keep the message entry itself (role preserved) so provider-side role alternation constraints hold.
4. Cap: drop at most `cfg.max_clear_ratio` (default 0.5) of live-zone turns per request.

**SnapshotResume** — new:

1. Serialize live-zone messages `[frozen_floor .. len - cfg.keep_tail_turns]` (default keep_tail_turns = 4) into a snapshot document `{version: 1, session_key, created_unix, messages: [...]}`.
2. `CcrStore::put(snapshot_key, doc)`; record `last_snapshot_key` in session state.
3. Replace that message range with ONE user-role message: a structured summary block — per-turn one-line digests (first `cfg.digest_chars` = 160 chars of each turn's text content, tool calls rendered as `tool:{name}`) + trailing marker `<<ccr:SNAPKEY>>`.
4. Retrieval: existing `cutctx_retrieve` tool / `/v1/retrieve` machinery already resolves ccr markers — no new retrieval surface needed.
5. Snapshot is per-request idempotent: if `last_snapshot_key` exists and the frozen floor hasn't advanced, reuse it (don't re-put identical content; `compute_key` dedups anyway).

### 5.5 Wiring into the proxy

In the buffered arm of `forward_http`, after `resolve_frozen_count` and before the per-endpoint compression dispatch (~proxy.rs:850):

```rust
let signals = context_signals::compute(&parsed_body, frozen_count, &session_state, model);
let decision = context_strategy::select_strategy(&signals, &policy, &state.config.strategy_cfg);
// decision.strategy threaded into the compress_* call as a new parameter
```

Signature change: `compress_anthropic_live_zone_with_ccr(body, frozen_count, auth_mode, model, ccr_store)` gains `strategy: ContextStrategy` (and same for the two OpenAI variants). `RollingWindow` must be a pure pass-through to today's behavior.

`model_context_limit`: source from the existing `crates/cutctx-proxy/src/compression/model_limits.rs`. If that module lives proxy-side only, pass the limit into `compute()` from the proxy rather than moving the table (avoid core↔proxy dependency inversion).

Extend `compression::Outcome::Compressed` with `strategy: ContextStrategy` and `strategy_rationale: &'static str` (additive; existing constructors default to `RollingWindow`/`"default"`). Extend `CompressionManifest` similarly. These flow into the `forwarded` log line and SpendEvent context.

### 5.6 Configuration

`config.rs` additions (clap + env, defaults shown):

| Flag | Env | Default |
|---|---|---|
| `--context-strategies` | `CUTCTX_PROXY_CONTEXT_STRATEGIES` | `off` (opt-in for first release; flip to `on` after one minor version) |
| `--strategy-snapshot-threshold` | `CUTCTX_PROXY_STRATEGY_SNAPSHOT_THRESHOLD` | `0.85` |
| `--strategy-compact-threshold` | `CUTCTX_PROXY_STRATEGY_COMPACT_THRESHOLD` | `0.50` |
| `--strategy-low-value-ratio` | `CUTCTX_PROXY_STRATEGY_LOW_VALUE_RATIO` | `0.40` |
| `--strategy-low-value-score` | `CUTCTX_PROXY_STRATEGY_LOW_VALUE_SCORE` | `0.15` |
| `--strategy-keep-tail-turns` | `CUTCTX_PROXY_STRATEGY_KEEP_TAIL_TURNS` | `4` |
| `--strategy-max-clear-ratio` | `CUTCTX_PROXY_STRATEGY_MAX_CLEAR_RATIO` | `0.5` |

License: `SelectiveClear`/`SnapshotResume` require CCR ⇒ effectively Team+ via existing `allows_ccr()` gate; additionally gate the selector itself on `allows_live_zone()` (i.e. never runs at OpenSource tier, same as compression generally).

Per-request override header (also the escape hatch for agent CLIs): `x-cutctx-strategy: rolling_window|smart_compact|selective_clear|snapshot_resume|auto`. Invalid value → 400 is wrong (breaks never-break rule); instead ignore + WARN + metric.

## 6. Observability

- New counter `proxy_context_strategy_selected_total{strategy, rationale}` (metric_names.rs; bounded vocab for both labels).
- New histogram `proxy_context_strategy_signal_utilization` (buckets 0.1..1.0) — distribution of utilization at decision time.
- Reuse `proxy_compression_ratio_by_strategy{strategy, content_type}`: the strategy label vocabulary extends with the four strategy names.
- Manifest fields land in the `forwarded` structured log; `SpendEvent` unchanged (tokens_saved already captures the effect).
- If hooks land first: emit decision via annotation `strategy.decision` in `after_compress`.

## 7. Testing

- **Unit (core):** `select_strategy` truth table — every rule, boundary values, Subscription `toin_read_only` override, no-CCR degradation. Property test: decision is a pure function of (signals, policy, cfg).
- **Unit (SelectiveClear):** never drops a turn containing Error/Security importance signal; never drops below `volatile_token_threshold`; marker format matches `ccr::marker_for` regex; role alternation preserved (adjacent same-role messages never created).
- **Unit (SnapshotResume):** frozen floor untouched byte-for-byte (assert prefix byte equality); snapshot retrievable via `CcrStore::get`; idempotency on repeat request.
- **Golden/regression:** with `--context-strategies off` AND with strategy=RollingWindow selected, output is byte-identical to current main across the existing live-zone golden corpus (this is the hard gate).
- **Integration:** synthetic long session against mock upstream — drive utilization from 0.3 → 0.9 over 20 requests, assert strategy progression RollingWindow → SmartCompact → SnapshotResume and that `proxy_passthrough_bytes_modified_total` stays 0.
- **Eval hookup:** run `cutctx/evals/runners/compression_only.py` fidelity suite (threshold 0.90 verbatim_fidelity) over SelectiveClear/SmartCompact outputs; both must pass ≥0.90 before default-on.

## 8. Acceptance criteria

1. Off by default; on ⇒ all existing tests green, golden corpus byte-identical for RollingWindow.
2. Long-session integration test shows ≥30% additional token reduction vs RollingWindow-only at utilization ≥0.85, with fidelity ≥0.90 on the eval suite.
3. Frozen floor: zero cache-hot bytes modified in any test (`compute_frozen_count` prefix byte-equality assertions).
4. All drops recoverable: 100% of elided ccr markers in test outputs resolve via `CcrStore::get`.
5. Subscription auth mode never selects SelectiveClear/SnapshotResume.

## 9. Implementation plan

1. `context_strategy.rs`: enums, signals, `select_strategy` + unit truth table. (~1 day)
2. `session_state.rs` (proxy) + header-ladder session key + tests. (~0.5 day)
3. Thread `strategy` param through the three `compress_*_live_zone` entry points; `Outcome`/manifest extension; RollingWindow byte-identity golden gate. (~1 day)
4. SmartCompact (lossy cap consuming `max_lossy_ratio`; rejected-block accounting). (~1 day)
5. SelectiveClear (BM25 scoring + importance guard + CCR elision). (~1.5 days)
6. SnapshotResume (snapshot doc, summary block, idempotency). (~1.5 days)
7. Config flags, metrics, integration + eval runs. (~1 day)

## 10. Open questions

1. Should SnapshotResume's summary be LLM-generated (better quality, adds latency + cost + nondeterminism) vs the deterministic digest in §5.4? v1: deterministic; revisit when the eval framework can measure summary quality.
2. `x-cutctx-strategy` header vs the future feature-flags system — the flags spec (`spec-compression-feature-flags.md`) subsumes this header as one flag source; keep the header as the lowest-priority source there.
3. Anthropic `1h`/`5m` TTL interaction: advancing the frozen floor after a snapshot changes cache-write economics; `should_mutate_deep`/`break_even_reads` (`compression_policy.rs:284`) should eventually gate snapshot timing. v1 ignores; log `net_mutation_gain` inputs for offline analysis.
