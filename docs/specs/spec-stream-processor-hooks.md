# Spec: Stream Processor Hooks (Proxy Lifecycle Events)

**Status:** Draft for implementation
**Priority:** P0 (Phase 1)
**Date:** 2026-07-19
**Origin:** `docs/specs/features-from-youtube-research.md` §1
**Depends on:** existing proxy pipeline (no blockers)
**Blocks:** Multi-Signal Evaluation Framework (`spec-multi-signal-eval.md`), Feature Flags (`spec-compression-feature-flags.md`)

---

## 1. Problem

The Rust proxy's request pipeline (`crates/cutctx-proxy/src/proxy.rs::forward_http`, ~line 419) is a single 900-line function with hard-coded stages. There is no way for users, enterprise integrators, or our own future features (eval scorecards, feature flags, receipts) to observe or influence compression decisions without patching `forward_http`. The only extensibility seam today is the `Observer` trait in `crates/cutctx-core/src/transforms/smart_crusher/traits.rs` (line ~119), which fires only inside SmartCrusher.

## 2. Goals

- Deterministic, typed hook points at the five lifecycle stages of every intercepted request: `before_compress`, `after_compress`, `before_llm_send`, `after_llm_recv`, `on_error`.
- Hooks are **in-process Rust trait objects** registered on `AppState` (not a scripting layer, not RPC). External/user hooks come later via a config-driven built-in hook set.
- Hooks can: observe (always), veto/redirect compression (`before_compress` only), and annotate telemetry. Hooks can **never** mutate request/response bodies in v1.
- Zero overhead when no hooks are registered; bounded overhead (<1ms p99 for observe-only hooks) when they are.
- Preserve the project's inviolable rule: **compression must never break a request** — a panicking or erroring hook is logged, skipped, and the request proceeds.

## 3. Non-goals (v1)

- Body-mutating hooks (needs the byte-identity safety story; see §11 Open Questions).
- Hooks on the streaming byte path itself (SSE bytes remain untouched; hooks observe via the existing mpsc tee).
- WASM / out-of-process plugin hooks.
- Hooks in the Python proxy (`cutctx/proxy/server.py`) — Rust proxy first; Python parity is a follow-up spec.

## 4. Current state (ground truth)

Request lifecycle in `forward_http` (`crates/cutctx-proxy/src/proxy.rs`), ordered stages:

1. Request-id + tenancy parse (`x-cutctx-org/-workspace/-project/-agent`) — ~line 425
2. Remote org policy enforcement (`policy::client::get_policy`) — ~line 453
3. Auth-mode classification (`cutctx_core::auth_mode::classify`) → request extensions — ~line 553
4. `CompressionPolicy::for_mode(auth_mode)` → request extensions — ~line 567
5. Header build (`headers::build_forward_request_headers`) — ~line 641
6. Compression gate (`should_intercept`) — ~line 702
7. Buffered arm: body read → `compression::classify_compressible_path` → cache-stabilization detectors → per-endpoint dispatch returning `compression::Outcome` — ~lines 733–1093
8. Upstream forward via `reqwest`
9. Response path: SSE detection, `SseStreamKind::for_request_path`, tee into `run_sse_state_machine` via bounded `mpsc::channel(100)` — ~lines 1095–1304

Key types:

- `compression::Outcome` (`crates/cutctx-proxy/src/compression/live_zone_anthropic.rs:79`): `NoCompression | Compressed { body, tokens_before, tokens_after, strategies_applied: Vec<&'static str>, markers_inserted, per_strategy_tokens } | Passthrough { reason }`
- `AppState` (`proxy.rs:54`): `config, client, bedrock_credentials, drift_state, vertex_token_source, ccr_store, spend_emitter`
- Existing callback seam: `smart_crusher::traits::Observer { fn name(&self) -> &str; fn on_event(&self, event: &CrushEvent); }`
- Existing middleware precedent: `bedrock/auth_mode_layer.rs::classify_and_attach_auth_mode` via `axum::middleware::from_fn`
- Error contract: `TransformError::{InvalidInput, Skipped, Internal}` all mean "skip, continue, never panic"

## 5. Design

### 5.1 Core types — new module `crates/cutctx-proxy/src/hooks/mod.rs`

```rust
/// Context available to every hook. All fields are read-only references
/// or cheaply cloneable metadata. NO body bytes are exposed mutably.
pub struct HookCtx<'a> {
    pub request_id: &'a str,
    pub path: &'a str,
    pub method: &'a http::Method,
    pub auth_mode: cutctx_core::auth_mode::AuthMode,
    pub policy: cutctx_core::compression_policy::CompressionPolicy,
    /// Tenancy parsed from x-cutctx-* headers (stage 1 of forward_http).
    pub tenancy: &'a Tenancy,          // { org, workspace, project, agent: Option<String> }
    /// Mutable annotation bag; merged into the final `forwarded` log line
    /// and available to later hooks. String keys, JSON values, bounded to
    /// 32 entries / 4 KiB serialized (enforced on insert, excess dropped with WARN).
    pub annotations: &'a mut HookAnnotations,
}

/// Stage-specific payloads.
pub struct BeforeCompress<'a> {
    pub body: &'a [u8],                     // read-only original body
    pub endpoint: CompressibleEndpoint,     // from classify_compressible_path
    pub frozen_message_count: Option<usize>,
}

pub enum CompressDecision {
    /// Default: run the pipeline as configured.
    Proceed,
    /// Skip compression for this request (forward original bytes).
    Skip { reason: &'static str },
    /// Proceed but force a strategy override (consumed by feature-flags spec;
    /// until then, treated as Proceed + annotation).
    Override(StrategyOverride),
}

pub struct AfterCompress<'a> {
    pub outcome: &'a compression::Outcome,  // NoCompression | Compressed{..} | Passthrough{..}
    pub elapsed: std::time::Duration,       // compression wall time
}

pub struct BeforeLlmSend<'a> {
    pub headers: &'a http::HeaderMap,       // final outbound headers (read-only)
    pub body_len: usize,
    pub compressed: bool,
}

pub struct AfterLlmRecv<'a> {
    pub status: http::StatusCode,
    pub is_sse: bool,
    /// Populated for non-SSE responses only in v1. For SSE, hooks receive
    /// a terminal AfterLlmRecv fired from the SSE state-machine task on
    /// stream close, carrying usage totals instead of the body.
    pub usage: Option<UsageTotals>,         // input/output/cache_read/cache_creation tokens
    pub ttfb: Option<std::time::Duration>,
}

pub struct OnError<'a> {
    pub stage: HookStage,                   // where the error occurred
    pub error: &'a dyn std::error::Error,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum HookStage { BeforeCompress, AfterCompress, BeforeLlmSend, AfterLlmRecv, OnError }
```

### 5.2 The hook trait

```rust
/// All methods have default no-op impls so a hook implements only what it needs.
/// Contract mirrors TransformError semantics: NEVER panic; errors are contained.
pub trait ProxyHook: Send + Sync {
    fn name(&self) -> &'static str;

    /// Only hook that can influence the pipeline. First non-Proceed decision
    /// wins (registration order); remaining before_compress hooks still run
    /// for observation but their decisions are ignored (logged at DEBUG).
    fn before_compress(&self, ctx: &mut HookCtx, ev: &BeforeCompress) -> CompressDecision {
        let _ = (ctx, ev); CompressDecision::Proceed
    }
    fn after_compress(&self, ctx: &mut HookCtx, ev: &AfterCompress) { let _ = (ctx, ev); }
    fn before_llm_send(&self, ctx: &mut HookCtx, ev: &BeforeLlmSend) { let _ = (ctx, ev); }
    fn after_llm_recv(&self, ctx: &mut HookCtx, ev: &AfterLlmRecv) { let _ = (ctx, ev); }
    fn on_error(&self, ctx: &mut HookCtx, ev: &OnError) { let _ = (ctx, ev); }
}
```

Notes:

- Methods are **sync**. Hooks needing async work (e.g. spend emission) must enqueue to their own channel/task, following the `SpendEmitter` pattern (`observability/spend_emitter.rs`: bounded mpsc, batch flush, drop-with-warn). This keeps the hot path allocation- and await-free.
- `before_compress` runs **inside** the compression gate, i.e. only for requests where `should_intercept == true`. Requests that bypass compression entirely fire only `before_llm_send`/`after_llm_recv`.

### 5.3 Registry and dispatch

```rust
pub struct HookRegistry {
    hooks: Vec<Arc<dyn ProxyHook>>,        // registration order = execution order
}

impl HookRegistry {
    pub fn is_empty(&self) -> bool;
    /// Dispatch helpers wrap each hook call in catch_unwind + timing.
    pub fn dispatch_before_compress(...) -> CompressDecision;
    pub fn dispatch_after_compress(...);
    // ... one per stage
}
```

- Add field `hooks: Arc<HookRegistry>` to `AppState` (`proxy.rs:54`) with builder `AppState::with_hooks(...)` following the existing `.with_ccr_store(...)` pattern (proxy.rs:163).
- **Fast path:** every dispatch site begins with `if state.hooks.is_empty() { ... }` so the no-hook configuration adds one branch per stage and nothing else.
- **Containment:** each hook invocation is wrapped in `std::panic::catch_unwind(AssertUnwindSafe(..))`. A panic or excessive latency increments `proxy_hook_failures_total{hook, stage, kind}` and the hook is skipped for the remainder of the request. A hook that panics ≥3 times within 60s is disabled process-wide (circuit breaker, `AtomicU32` per hook) and `proxy_hook_disabled_total{hook}` fires. This satisfies the "no silent fallbacks" rule: degradation is loud in metrics + WARN logs, but requests are never harmed.
- **Timing:** per-hook per-stage duration recorded into new histogram `proxy_hook_duration_seconds{hook, stage}` (add to `observability/metric_names.rs` with HELP text, following the PR-G3 conventions there).

### 5.4 Dispatch sites in `forward_http`

| Stage | Insertion point (proxy.rs, current lines) | Payload source |
|---|---|---|
| `before_compress` | Inside buffered arm, after `classify_compressible_path` + cache-stabilization detectors, immediately before the per-endpoint `compress_*` dispatch (~line 850) | buffered `Bytes`, endpoint class, `resolve_frozen_count` result |
| `after_compress` | Immediately after the `Outcome` is produced, before the passthrough-bytes-modified alarm (~line 1020) | `&Outcome`, timer started at `before_compress` |
| `before_llm_send` | After header build + optional `maybe_inject_openai_prompt_cache_key`, immediately before the `reqwest` send (both buffered ~line 1060 and streaming ~line 1085 arms) | final headers, body length |
| `after_llm_recv` (non-SSE) | Response path, after status/headers known and body fully relayed (~line 1300) | status, usage if parseable |
| `after_llm_recv` (SSE terminal) | Inside `run_sse_state_machine` completion (the same points that emit `SpendEvent` today: proxy.rs ~1575/1714/1876 for Anthropic / OpenAI Chat / Responses) | usage totals from stream state, TTFB from `first_byte_at` |
| `on_error` | (a) compression dispatch `Err(..)` branches; (b) `ProxyError` construction in the upstream-send arm; (c) SSE state-machine error paths | stage + error ref |

For the SSE terminal event: `HookCtx` cannot borrow the (already returned) request, so the SSE task receives a pre-built owned `HookCtxOwned` (request_id, path, auth_mode, policy, tenancy, annotations snapshot) alongside the existing channel payload. Annotations added at this stage are logged but cannot affect earlier stages (obviously).

### 5.5 `CompressDecision` handling

At the `before_compress` site:

- `Proceed` → existing behavior.
- `Skip { reason }` → forward the original buffered bytes exactly like `Outcome::Passthrough` today; record `reason` in annotations; increment `proxy_hook_compress_skipped_total{hook, reason}`. The passthrough-bytes-modified alarm (~line 1027) still applies — hooks must not have touched bytes (they can't; body is `&[u8]`).
- `Override(..)` → v1: log at INFO, record annotation `hook.override.requested`, then Proceed. The feature-flags spec (`spec-compression-feature-flags.md` §6.3) consumes this variant for real. Defining it now keeps the enum stable.

### 5.6 Built-in hooks shipped with v1

These prove the API and migrate existing scattered logic without behavior change:

1. **`TelemetryHook`** — replaces nothing, adds: emits stage timings and outcome summary into annotations, merged into the final `forwarded` log line. Default-on when `--hooks-telemetry` (default true).
2. **`SpendEventHook`** — moves the three inline `SpendEvent` emission sites (proxy.rs ~1575/1714/1876) into an `after_llm_recv` hook that calls the existing `SpendEmitter`. Pure refactor; `SpendEvent` struct unchanged. This is the proof that the SSE-terminal dispatch works.
3. **`GuardrailHook`** (opt-in, `--hooks-guardrail`) — `before_compress` returns `Skip` when the request body matches configured deny conditions (e.g. `content-type` mismatch already caught elsewhere; v1 condition set: body contains any of N configured literal markers, e.g. `"do-not-compress"`). Minimal, deterministic; exists mainly to exercise the veto path in production.

### 5.7 Configuration

Follow the existing clap + env pattern in `crates/cutctx-proxy/src/config.rs` (`CliArgs` derive at :186, `Config::from_cli` at :820):

| Flag | Env | Default | Meaning |
|---|---|---|---|
| `--hooks` | `CUTCTX_PROXY_HOOKS` | `enabled` | Master switch (`enabled`/`disabled`). Disabled ⇒ `HookRegistry` empty. |
| `--hooks-telemetry` | `CUTCTX_PROXY_HOOKS_TELEMETRY` | `true` | Register TelemetryHook |
| `--hooks-guardrail` | `CUTCTX_PROXY_HOOKS_GUARDRAIL` | `false` | Register GuardrailHook |
| `--hook-timeout-ms` | `CUTCTX_PROXY_HOOK_TIMEOUT_MS` | `5` | Per-hook per-stage soft budget; exceeding logs WARN + metric (does not abort the call — sync code can't be cancelled safely) |

No TOML file — the Rust proxy is CLI/env configured today; do not introduce a config file in this spec.

### 5.8 License gating

Hook registration API is available at all tiers (it's how we ship our own features). Registering **external** hooks (future) will gate on `LicenseTier::allows_live_zone()`-style checks (`config.rs:592`); out of scope for v1.

## 6. Observability

New metrics (add to `observability/metric_names.rs` with HELP/labels, and force-touch in `prometheus.rs::handle_metrics` init per existing convention):

- `proxy_hook_duration_seconds{hook, stage}` — histogram, buckets `[1e-5, 1e-4, 5e-4, 1e-3, 5e-3, 1e-2, 5e-2]`
- `proxy_hook_failures_total{hook, stage, kind}` — kind ∈ {panic, timeout}
- `proxy_hook_disabled_total{hook}`
- `proxy_hook_compress_skipped_total{hook, reason}`

OTel: add `cutctx.hooks.duration` + `cutctx.hooks.failures` to `otel.rs::metric_names` (dotted names, consistent with `cutctx.compression.ratio` etc.).

## 7. Testing

- **Unit** (`crates/cutctx-proxy/src/hooks/`): registry dispatch order; first-non-Proceed-wins; panic containment (hook that panics → request unaffected, metric fired); circuit breaker (3 panics/60s → disabled); annotation caps.
- **Integration** (`crates/cutctx-proxy/tests/`): spin proxy with a recording test hook against a mock upstream (follow existing integration-test patterns in `tests/`); assert all five stages fire in order for (a) compressible Anthropic request, (b) passthrough request (only send/recv fire), (c) SSE response (terminal after_llm_recv carries usage), (d) upstream 502 (on_error fires).
- **Refactor safety:** after moving spend emission into `SpendEventHook`, assert byte-identical `SpendEvent` JSON versus a golden fixture from the current inline path.
- **Perf:** criterion bench: `forward_http` hot path with 0 hooks vs 3 observe-only hooks; budget ≤1% regression at 0 hooks, ≤3% at 3 hooks.
- **E2E:** extend `e2e/` proxy suite with `--hooks-guardrail` + marker body → response identical to upstream (skip path verified end-to-end).

## 8. Acceptance criteria

1. All five stages dispatch at the documented points; ordering guaranteed within a request.
2. `cargo test -p cutctx-proxy` green; no change to any existing `Outcome` snapshot/golden test.
3. `proxy_passthrough_bytes_modified_total` remains 0 across the full e2e suite with hooks enabled.
4. Spend emission fully served by `SpendEventHook`; inline emission sites deleted.
5. No-hook overhead ≤1% on the criterion bench.
6. A panicking hook in e2e produces: successful client response + WARN log + `proxy_hook_failures_total` increment.

## 9. Implementation plan

1. `hooks/mod.rs`: types, trait, registry, containment, metrics (no dispatch sites yet). Unit tests. (~1 day)
2. Wire `AppState.hooks` + config flags. (~0.5 day)
3. Dispatch sites: before_compress / after_compress / before_llm_send / non-SSE after_llm_recv / on_error. Integration tests a, b, d. (~1.5 days)
4. SSE terminal after_llm_recv via `HookCtxOwned` through the mpsc channel; migrate spend emission → `SpendEventHook`; golden-fixture test. (~1.5 days)
5. TelemetryHook + GuardrailHook + e2e + bench. (~1 day)

## 10. Interactions with other specs

- **Multi-signal eval** (`spec-multi-signal-eval.md`): the `EvalHook` registers at `after_compress` + `after_llm_recv` and is the primary consumer of this API.
- **Feature flags** (`spec-compression-feature-flags.md`): implements a `FlagResolutionHook` at `before_compress` returning `CompressDecision::Override`.
- **Proactive compression** (future): scheduler tasks are NOT hooks; unrelated.

## 11. Open questions

1. Should `before_llm_send` be allowed to add outbound headers (e.g. receipts, trace baggage)? Deferred; if yes, expose an allowlisted `HeaderMap` writer (`x-cutctx-*` only) in v1.1.
2. Body-mutating hooks: would require rerunning `is_compressible`/frozen-floor logic post-mutation and extending the bytes-modified alarm semantics. Revisit only with a concrete enterprise use case.
3. Python proxy parity (`cutctx/proxy/server.py` middleware): file a follow-up spec once Rust API stabilizes; keep stage names identical.
