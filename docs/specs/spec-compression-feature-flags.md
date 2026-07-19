# Spec: Feature Flags for Compression Behavior (Per-Agent Policy Routing)

**Status:** Draft for implementation
**Priority:** P1 (Phase 2)
**Date:** 2026-07-19
**Origin:** `docs/specs/features-from-youtube-research.md` §6
**Depends on:** Stream Processor Hooks (`spec-stream-processor-hooks.md`) — consumes `CompressDecision::Override`. Smart Context Strategies (`spec-smart-context-strategies.md`) — flag values include strategy overrides.

---

## 1. Problem

Compression behavior today varies only by **auth mode** (`CompressionPolicy::for_mode`, `crates/cutctx-core/src/compression_policy.rs:193`): three hard-coded profiles for Payg/OAuth/Subscription. Real deployments run many agents through one proxy — a code-review agent must never lose AST fidelity, a support agent can take aggressive compression, a research agent must preserve citations. There is no per-agent, per-team, or per-workload control, and no way to canary a compression change on 10% of traffic before rollout.

The building blocks exist but don't meet: tenancy headers are already parsed (`x-cutctx-org/-workspace/-project/-agent`, `proxy.rs:425–451`); the Python SDK has per-tool profiles (`cutctx_tool_profiles` in `cutctx/client.py`); the canary A/B machinery exists Python-side (`cutctx/proxy/savings_canary.py` — salted deterministic arms, restart-safe state); and there is a remote signed-policy channel (`policy/mod.rs::PolicyPayload`, Ed25519 `hrp1.` tokens) that already forces `req_comp` per org.

## 2. Goals

- A **flag resolution layer** in the Rust proxy that maps request identity → effective `CompressionProfile`, evaluated per request, deterministic, auditable.
- Four flag dimensions (matching the research doc): compression level, strategy override, model routing hint, cache policy.
- Flag sources, strictly ordered by precedence (highest first): remote signed org policy → local flag file → request headers → defaults.
- Percentage rollouts (canary) with sticky, salted bucketing — same session always gets the same arm.
- Hot reload of the local flag file without proxy restart.
- Every resolution decision is loggable and lands in metrics/spend events for the dashboard's per-agent breakdown.

## 3. Non-goals (v1)

- A management UI (dashboard read-only view comes with `spec-eval-dashboard.md`; editing is file/API based).
- User-defined arbitrary predicates (no expression language — that's the deferred Workflow DSL). Matching is by identity fields only.
- Model routing *implementation* — the flag emits a routing hint header; actual model rewriting is a separate feature. (Python side already has `model_routing_evals.py`; don't block on it.)
- Flags for the Python proxy (parity follow-up; keep the file format identical so one file serves both).

## 4. Current state (ground truth)

- Tenancy: `forward_http` parses `x-cutctx-org`, `x-cutctx-workspace`, `x-cutctx-project`, `x-cutctx-agent` (~proxy.rs:425–451). **`x-cutctx-agent` exists in the Rust proxy but there is no first-class agent identity in the Python proxy** (`canary_identity.py` builds session identity, not agent identity).
- Remote policy: `policy/client.rs::get_policy(api_url, org, workspace)` fetches `PolicyPayload { v, budget_usd, mtd_spend, budget_period, rpm, tpm, models, req_comp, ts }`, Ed25519-verified (`verify_policy_token`, keys from `CUTCTX_POLICY_PUBLIC_KEYS`). Enforced at stage 2 of `forward_http` (429/403 paths).
- Local policy: `CompressionPolicy` (5 fields, per auth mode). Config is CLI/env only (`config.rs`); **no config file exists for the Rust proxy** — the Python side owns `.cutctx/config.toml` (`cutctx/paths.py`).
- Canary precedent: `savings_canary.py` — arms with fixed percentages, salt-fingerprinted deterministic assignment, persisted state `{schema_version, salt_fingerprint, allocations, paused, metrics}`.
- Hooks: `CompressDecision::Override(StrategyOverride)` is defined-but-inert until this spec (hooks spec §5.5).
- License tiers: `LicenseTier {OpenSource, Team, Business, Enterprise}` + gates (`config.rs:592`).

## 5. Flag model

### 5.1 The resolved artifact: `CompressionProfile`

New in `crates/cutctx-core/src/compression_policy.rs` (same module — it is the policy system's v2 surface):

```rust
#[derive(Debug, Clone, PartialEq)]
pub struct CompressionProfile {
    /// Base numeric policy — starts from CompressionPolicy::for_mode(auth_mode),
    /// then level/overrides adjust fields.
    pub policy: CompressionPolicy,
    pub level: CompressionLevel,           // Off | Light | Balanced | Aggressive
    pub strategy_override: Option<ContextStrategy>, // from spec-smart-context-strategies
    pub transform_denylist: Vec<TransformId>,       // e.g. deny code lossy transforms
    pub preserve: PreserveSet,             // bitflags: ERRORS | WARNINGS | CITATIONS | TIMESTAMPS | CODE
    pub model_routing: Option<ModelRoutingHint>,    // Fast | Quality | Cheapest → emitted as x-cutctx-route header
    pub cache_policy: CachePolicy,         // Default | Fresh | NoCache
    /// Provenance for audit: which source set each dimension.
    pub provenance: ProfileProvenance,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompressionLevel { Off, Light, Balanced, Aggressive }
```

Level → policy field mapping (deterministic, documented in rustdoc):

| Level | max_lossy_ratio | volatile_token_threshold | offloads enabled | notes |
|---|---|---|---|---|
| Off | 0.0 | — | no | equivalent to `CompressDecision::Skip` |
| Light | 0.10 | 256 | no | reformat-only (`ReformatTransform`s) |
| Balanced | policy default (0.25/0.45 by mode) | policy default | yes | today's behavior |
| Aggressive | 0.60 | 64 | yes | never exceeds auth-mode ceiling: `min(0.60, mode_max * 1.35)`; Subscription mode caps at its own 0.25 — auth-mode policy is a **ceiling**, flags can only tighten or stay within it |

`PreserveSet` binds to the existing importance machinery: preserved categories are passed to compressors as `ImportanceCategory` guards (`crates/cutctx-core/src/signals/line_importance.rs` — `Error, Warning, Importance, Security, Markdown`; CITATIONS and TIMESTAMPS need two new categories added to that enum + detector patterns).

### 5.2 Flag file — `cutctx-flags.toml`

Loaded from `--flags-file` / `CUTCTX_PROXY_FLAGS_FILE` (no default path; feature inert unless set). Format shared with the future Python implementation.

```toml
schema_version = 1
salt = "prod-2026-07"            # bucketing salt; changing it reshuffles canaries

[defaults]
level = "balanced"

# Rules are evaluated top-to-bottom; ALL specified match fields must equal
# the request's identity fields (exact string match; "*" wildcard). First match wins.
[[rule]]
match = { agent = "code-review" }
level = "light"
transform_denylist = ["code_compactor", "deletion_compaction"]
preserve = ["errors", "warnings", "code"]

[[rule]]
match = { agent = "support-*", workspace = "cs" }   # trailing-* prefix glob allowed on values
level = "aggressive"
preserve = ["errors", "timestamps"]

[[rule]]
match = { org = "acme" }
level = "balanced"
cache_policy = "fresh"
model_routing = "cheapest"

# Canary: percentage split within a matched rule.
[[rule]]
match = { agent = "research" }
[[rule.arms]]
percent = 90
level = "light"
preserve = ["citations"]
[[rule.arms]]
percent = 10
name = "canary-balanced"
level = "balanced"
preserve = ["citations"]
```

Validation rules (fail LOUD at load, following `CompressionStartup` fatal-at-boot precedent, `error.rs`):
arm percents must sum to 100; unknown keys rejected; unknown transform ids rejected against a compiled registry of transform names; `schema_version` must be 1. A file that fails validation at **hot reload** (vs boot) keeps the previous good version and fires `proxy_flags_reload_failures_total` + ERROR log (never degrade silently to no-flags).

### 5.3 Identity for matching and bucketing

- Match fields: `org, workspace, project, agent` from the `x-cutctx-*` tenancy headers (already parsed), plus `auth_mode` and `model` (from `RequestedModel` extension, proxy.rs:52).
- Canary bucketing key: `blake3(salt + session_key)` → `u64 % 100`, where `session_key` is the same ladder as `session_state.rs` in the strategies spec (§5.2 there). Sticky per session, reshuffled only by salt change — mirrors `savings_canary.py` semantics.

### 5.4 Precedence (highest wins, per dimension)

1. **Remote org policy** — extend `PolicyPayload` with optional `comp_level`, `comp_flags` fields (additive; token format `hrp1.` unchanged; old payloads still verify). `req_comp` already forces compression on; `comp_level` can force a level. Signed ⇒ trusted ⇒ wins over everything.
2. **Local flag file** — first matching rule (+ canary arm).
3. **Request headers** — `x-cutctx-level`, `x-cutctx-strategy` (from strategies spec), `x-cutctx-cache-policy`. Headers may only **tighten** (move toward Off/Light/preserve-more) relative to the file result, never loosen — prevents an agent granting itself Aggressive against org policy. Invalid header values: ignore + WARN + `proxy_flags_invalid_header_total` (never 4xx; never-break rule).
4. **Defaults** — `[defaults]` from file, else `Balanced` ≙ current behavior.

`provenance` records source per dimension for audit (`ProfileProvenance { level: Source, strategy: Source, ... }`, `Source ∈ {RemotePolicy, FlagRule(rule_idx, arm), Header, Default}`).

## 6. Design — resolution engine

### 6.1 New module `crates/cutctx-proxy/src/flags/`

```
flags/
  mod.rs        // FlagEngine, resolve()
  file.rs       // TOML parse + validation + FlagSet model
  reload.rs     // hot reload
  bucketing.rs  // canary arm assignment
```

```rust
pub struct FlagEngine {
    current: arc_swap::ArcSwap<FlagSet>,   // lock-free read on hot path
    salt: String,
}

impl FlagEngine {
    pub fn resolve(&self, ident: &RequestIdentity, auth_mode: AuthMode,
                   headers: &HeaderMap, remote: Option<&PolicyPayload>)
        -> CompressionProfile;
}
```

- `AppState` gains `flags: Option<Arc<FlagEngine>>` (builder `.with_flags(...)`, same pattern as `.with_ccr_store`).
- Hot reload (`reload.rs`): tokio task, `notify` crate file watcher with 2s debounce + fallback 30s mtime poll; on change → parse/validate → `ArcSwap::store` on success. Metric `proxy_flags_reloads_total{result}`.
- Resolution cost budget: pure in-memory match over ≤ a few hundred rules; target <10µs p99. No I/O, no locks on the read path.

### 6.2 Wiring — via the hooks API

Implement as the built-in **`FlagResolutionHook`** (hooks spec §5.6 pattern):

- `before_compress`: call `FlagEngine::resolve`; store profile in annotations + request extensions; return
  `CompressDecision::Skip{reason:"flag_level_off"}` when `level == Off`, `CompressDecision::Override(StrategyOverride)` when `strategy_override` set, else `Proceed`.
- The compression dispatch reads `CompressionProfile` from request extensions (falling back to `CompressionPolicy::for_mode` exactly as today when absent — flags disabled ⇒ zero behavior change).
- `before_llm_send`: if `model_routing` set, add outbound header `x-cutctx-route: fast|quality|cheapest` (this is the one header-write hooks v1.1 allowlists; if hooks v1 lands without header writes, do this write inline at the header-build stage reading the extension instead — do not block on hooks v1.1).
- `cache_policy`: `Fresh` disables `maybe_inject_openai_prompt_cache_key` + cache-aligner for the request; `NoCache` additionally strips `cache_control` auto-placement (`cache_stabilization/anthropic_cache_control.rs`). Both only ever *reduce* caching.

### 6.3 Threading the profile into core

`compress_*_live_zone` entry points (already gaining `strategy` param per strategies spec) additionally accept `&CompressionProfile` — or, to keep signatures stable, fold level/denylist/preserve into the `CompressionPolicy` struct instance passed down (profile.policy is pre-adjusted). **Decision: pass pre-adjusted `CompressionPolicy` + `transform_denylist` + `preserve`; do not thread the whole profile into core.** Core stays ignorant of flags; it just honors policy numbers, a denylist, and preserve guards.

Transform denylist enforcement: in the pipeline orchestrator (`transforms/pipeline/orchestrator.rs`), filter `reformats_by_type`/`offloads_by_type` entries whose `name()` is denied; in the live-zone dispatch, gate per-block transform choice the same way. `TransformId` = the existing `&'static str` names (`fn name(&self)` on both pipeline traits) — compile a registry constant listing all valid names for file validation.

## 7. Observability

New metrics (metric_names.rs conventions):

- `proxy_flags_resolved_total{level, source}` — source = winning provenance for level
- `proxy_flags_canary_assignment_total{rule, arm}`
- `proxy_flags_reloads_total{result}` / `proxy_flags_reload_failures_total`
- `proxy_flags_invalid_header_total{header}`

`SpendEvent` (observability/spend_emitter.rs) gains optional fields `flag_level: Option<String>`, `flag_arm: Option<String>` (additive JSON; ledger receiver tolerates unknown fields). This is what powers per-arm savings comparison on the dashboard (eval-dashboard spec §6) — the same measurement the canary runbook (`LIVE_SAVINGS_CANARY_RUNBOOK.md`) does Python-side.

## 8. Testing

- **Unit (file.rs):** valid/invalid TOML corpus — percent sums, unknown transforms, unknown keys, wildcard/prefix-glob matching, schema_version.
- **Unit (resolve):** precedence truth table across all 4 sources × 4 dimensions; header-can-only-tighten property test; auth-mode-ceiling property (`resolved.policy.max_lossy_ratio <= for_mode(auth).max_lossy_ratio adjusted per §5.1 table`).
- **Unit (bucketing):** determinism (same salt+session ⇒ same arm, 10^5 trials); distribution (χ² over arms within 1%); salt change reshuffles.
- **Integration:** proxy + flag file: (a) `level=off` agent → passthrough (bytes identical); (b) denylist blocks a transform (assert absent from `strategies_applied` in Outcome); (c) hot reload mid-run flips an agent's level without restart or dropped requests; (d) corrupt reload keeps old flags + fires failure metric.
- **Golden:** flags disabled (`--flags-file` unset) ⇒ byte-identical to main across live-zone golden corpus.

## 9. Acceptance criteria

1. Feature inert without `--flags-file`; zero hot-path regression (criterion, ≤1%).
2. Precedence + tighten-only + auth-ceiling properties hold under proptest.
3. Hot reload: 0 dropped/erred requests during 1000-rps reload test.
4. Canary arms measurable end-to-end: per-arm `tokens_saved` visible via SpendEvents in the ledger.
5. Validation failures at boot are fatal; at reload are loud + non-fatal.

## 10. Implementation plan

1. `flags/file.rs` model + validation + corpus tests. (~1.5 days)
2. `resolve()` + precedence + bucketing + property tests. (~1.5 days)
3. Pre-adjusted `CompressionPolicy` folding + denylist/preserve threading into orchestrator & live-zone. (~2 days)
4. `FlagResolutionHook` wiring + cache_policy behaviors + routing hint header. (~1 day)
5. Hot reload + metrics + SpendEvent fields. (~1 day)
6. Integration/golden/perf suites. (~1 day)

## 11. Open questions

1. Remote `PolicyPayload.comp_flags` shape — inline mini-rules or a URL to a signed flag file? v1: single `comp_level` force only; full remote rules when the EE control plane needs them.
2. Should `model_routing` ever rewrite the `model` field directly in the proxy? Deferred — hint header only until routing evals (`cutctx/proxy/model_routing_evals.py`) define quality gates.
3. Per-tool flags (match on tool name inside the body, like Python `cutctx_tool_profiles`)? Requires body inspection during matching; defer to v2 with a `match.tool` field.
