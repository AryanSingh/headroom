# Specs: Savings Expansion & Moat Workstreams (WS10–WS21)

*Detailed specifications and implementation steps for an agent. Extends `artifacts/strategy-implementation-plan.md` (workstreams there end at WS9; numbering continues here).*
*Date: 2026-07-02. All module paths verified against the current tree.*

**Binding rules:** §0 of `artifacts/strategy-implementation-plan.md` (zero-regression protocol, feature flags default-OFF, additive-only surfaces, EE boundary, per-task gate, one commit per task) applies verbatim to every task below. Do not restate — comply.

**Shared integration points (verified):**
- Compression orchestration: `cutctx/proxy/intelligence_pipeline.py` (pre-compression and post-compression stages)
- Canonical request result: `cutctx/proxy/outcome.py` (`RequestOutcome` → `emit_request_outcome`) — all new per-request metrics flow through this, never a new side channel
- Hook surface: `cutctx/hooks.py` (`pre_compress`, `compute_biases`, `post_compress`, `on_pipeline_event`)
- Session dedup: `cutctx/dedup.py` (`SessionDeduplicator`, `[cutctx:ref:HASH]` pointers)
- CCR: `cutctx/ccr/store.py`, `context_tracker.py`, `tool_injection.py`, `response_handler.py`
- Router: `cutctx/proxy/model_router.py` (config-map downgrade MVP)
- Response cache: `cutctx/proxy/semantic_cache.py` (content-hash LRU)
- Training data: `cutctx/proxy/probe_recorder.py` (JSONL original/compressed pairs, `CUTCTX_PROBE_RECORD_DIR`)
- Savings attribution: `cutctx/savings/` (5-source model), `cutctx/agent_savings.py`

---

## Priority & sequencing

| Order | WS | Name | Effort | Payoff | Depends on |
|---|---|---|---|---|---|
| 1 | WS16 | Tokenizer-aware normalization | S | 3–8% universal | — |
| 2 | WS13 | Batch-API arbitrage | S | 50% on eligible traffic | — |
| 3 | WS11 | Tool-result memoization | M | Whole-request elimination | — |
| 4 | WS10 | Output-side optimization | M | 20–50% of output spend | — |
| 5 | WS12 | Fleet dedup + shared org CCR | M | Scales with fleet size | WS5 (org memory) |
| 6 | WS19 | Compression autopilot | M | Auto-tuning, trust | — |
| 7 | WS20 | Compression insurance | S | Sellable guarantee | WS19 |
| 8 | WS17 | Compression-aware downshift | M | 2–10× on eligible reqs | WS19 signals |
| 9 | WS15 | Pre-emptive compaction | M | Kills the compaction cliff | — |
| 10 | WS18 | Learned per-customer policies | L | **Primary moat** | WS19 data |
| 11 | WS14 | Stateful delta proxy | L | Long-session savings | — |
| 12 | WS21 | CCR interchange spec | S | Category ownership | Stable CCR markers |

New savings sources introduced here (`output_optimization`, `memoization`, `batch_routing`, `normalization`) **must** be registered in the attribution model in `cutctx/savings/types.py` so the 5-source model grows to N-source without breaking existing consumers (additive enum members only; verify dashboard aggregation in `dashboard/src/lib/use-dashboard-data.js` tolerates unknown sources first — add a tolerance test if absent).

---

## WS10 — Output-side optimization

**Goal:** reduce *output* tokens (≈5× input price). Three independent levers, each its own flag.

**Existing scaffolding:** task-type detection (query-aware compression in the pipeline), `cutctx/proxy/structured_output.py`, accuracy guard, `RequestOutcome`.

### Spec

- Flags: `CUTCTX_OUTPUT_OPT=1` master; sub-flags `CUTCTX_OUTPUT_DIFF_EDITS`, `CUTCTX_OUTPUT_MAXTOK_AUTO`, `CUTCTX_OUTPUT_STYLE`. All default off.
- New module: `cutctx/proxy/output_optimizer.py`.
- **Lever 1 — diff-edit steering:** when the detected task type is CODE/EDIT and the request's tool surface includes a full-file write tool, inject a system-suffix instruction (via the existing prompt-injection path used by memory injection in `memory_injection.py` — reuse, don't fork) directing the model to emit minimal patches/edits rather than full-file rewrites. Never modify tool schemas.
- **Lever 2 — max_tokens auto-tuning:** maintain per-(task-type, agent) response-length quantiles from `RequestOutcome` history (p95 + 25% headroom). If the client sent no `max_tokens` or a value >4× p95, cap it. On a `max_tokens`-truncated finish reason, immediately record a *miss* and raise the cap class — a truncation caused by us must never survive more than one request. Store quantiles in the existing stats store (same DB as savings tracker; new table `output_quantiles`).
- **Lever 3 — style shaping:** for SEARCH/LIST/SUMMARIZE task types, inject a terse-output instruction. Skip entirely for CODE/DEBUG.
- **Attribution:** measured savings = (predicted baseline output tokens from quantile model) − actual; recorded as `output_optimization` source. Label as estimated in the report (WS2), since baseline is counterfactual.
- **Safety rail:** any guard failure or client retry within the same session with the same prompt disables levers 1/3 for that session (in-memory circuit breaker, log at WARNING, audit event).

### Steps

| ID | Task |
|---|---|
| W10.1 | `output_quantiles` table + quantile tracker fed from `emit_request_outcome`; unit tests with synthetic outcome streams |
| W10.2 | `output_optimizer.py` with the three levers as pure functions (request-in → request-out + `OutputOptActions` record); exhaustive unit tests incl. "client sent explicit max_tokens < cap → untouched" |
| W10.3 | Pipeline wiring in `intelligence_pipeline.py` pre-compression stage; flag-off golden test: request bytes identical to baseline |
| W10.4 | Truncation-miss feedback path + circuit breaker; test: forced truncation raises cap class on next request |
| W10.5 | Attribution source + report section + docs page |

**Verification:** e2e proxy test with a recorded fixture agent session; assert diff-edit instruction present only for CODE tasks, absent for DEBUG. **Regression guard:** the flag-off golden test (permanent); no lever may alter `messages` order or existing system prompt content — only append.

---

## WS11 — Tool-result memoization

**Goal:** identical tool call repeated in a session → answer locally from cache; the upstream model call for that turn's re-read never happens.

**Existing scaffolding:** `cutctx/dedup.py` already detects repeated content *after* the agent resends it. Memoization moves earlier: intercept the **tool call request** the model emits, and when we can prove the result is already in context or CCR, short-circuit.

### Spec

- Flag: `CUTCTX_MEMOIZE=1`. New module: `cutctx/proxy/memoizer.py`.
- Applicability: read-only, deterministic-within-a-session tools only. Ship a conservative built-in allowlist (file read, code search, `cutctx_retrieve`) keyed by tool-name patterns; configurable via `cutctx.toml` `[memoize] tools = [...]`. Anything not allowlisted is never memoized.
- Key: `(session_id, tool_name, canonicalized_args_hash)`. Canonicalization: sort JSON keys, normalize paths, drop pagination-irrelevant fields — implement in `memoizer.py`, property-test it.
- Flow: proxy observes tool_use blocks in the model response stream (same interception point CCR uses in `ccr/response_handler.py` for `cutctx_retrieve` — extend, don't duplicate). On key hit within TTL (default: session lifetime, size-capped LRU 256 entries/session), the proxy fabricates the tool_result from cache and continues the loop exactly as CCR's transparent retrieval does today.
- **Invalidation:** any successful *write*-shaped tool call (name matches write/edit/delete patterns) flushes cache entries whose canonical path args overlap the written path. When in doubt, flush the whole session cache — correctness beats savings.
- **Attribution:** avoided request's estimated input tokens recorded as `memoization` source.
- **Escape hatch:** if the fabricated result would exceed staleness TTL or the tool is streaming, pass through untouched.

### Steps

| ID | Task |
|---|---|
| W11.1 | Canonicalizer + key derivation, property tests (arg order, path forms → same key; different content → different key) |
| W11.2 | Session cache (LRU, size-capped) + invalidation rules; tests incl. overlap-flush and doubt-flush |
| W11.3 | Interception wiring alongside CCR's tool handling in `response_handler.py`; transparent replay e2e test (agent reads same file twice → second read served locally, upstream sees one fewer round trip) |
| W11.4 | Write-invalidation e2e: read → edit → read returns fresh content (this is the correctness-critical test; do not ship without it) |
| W11.5 | Attribution + `cutctx perf` line + docs |

**Regression guard:** flag-off = zero interception (golden test). With flag on, a memoized reply must be byte-identical to what the original tool returned (assert stored-bytes equality, no re-serialization drift).

---

## WS12 — Fleet-level dedup + shared org CCR store

**Goal:** content one agent has read/compressed is referenced, not re-transmitted, by every other agent in the org. Extends `SessionDeduplicator` (session-scoped) to org scope; CCR store gains a shared tier.

**Depends on:** WS5 (org-scope memory) for the org identity plumbing; reuse its RBAC decisions.

### Spec

- Flag: `CUTCTX_FLEET_DEDUP=1`. Requires proxy mode (library mode: no-op).
- CCR store (`cutctx/ccr/store.py`) gains a `scope` column: `session` (default, current behavior) | `org`. Org-tier entries are content-addressed (hash = key already), so cross-agent sharing is natural: if agent B's content hash exists in the org tier, replace with the existing pointer.
- Dedup index: extend `cutctx/dedup.py` with an org-level rolling index persisted in the CCR store's DB (session index stays in-memory as today).
- **Privacy boundary (hard requirement):** org tier is only eligible for content originating from *tool outputs* (files, search, logs) — never user messages or model responses. Enforce by content-origin tag at insertion; test it.
- Retrieval path unchanged: `cutctx_retrieve(hash=…)` already resolves by hash; it consults session tier then org tier.
- Retention: org-tier entries obey the EE retention policy (WS7/P3.2); default TTL 7 days, configurable.
- **Attribution:** avoided tokens recorded under existing dedup accounting but tagged `fleet` so the report can show "cross-agent savings" as its own line — this number is the fleet-scaling proof point for sales.

### Steps

| ID | Task |
|---|---|
| W12.1 | CCR store `scope` column (additive migration, `user_version` bump, un-migrated-DB read guard) |
| W12.2 | Org rolling index + origin-tag enforcement; unit tests: user-message content never enters org tier |
| W12.3 | Cross-agent e2e: agent A (claude wrap) reads file → agent B (codex wrap) same org gets pointer; retrieval returns original |
| W12.4 | Retention wiring + TTL tests |
| W12.5 | `fleet` attribution tag + report line + docs |

**Regression guard:** with flag off, dedup behavior is bit-identical to current session-scoped behavior (reuse existing dedup tests as the contract). Org-tier lookup adds ≤5ms p95 to the dedup stage — add a perf assertion.

---

## WS13 — Batch-API arbitrage

**Goal:** route latency-insensitive traffic to provider batch endpoints (≈50% discount).

### Spec

- Flag: `CUTCTX_BATCH_ROUTING=1`. New module: `cutctx/proxy/batch_router.py`.
- **Eligibility is explicit, never inferred:** a request is batch-eligible only if it carries the header `x-cutctx-batch: allow` (SDK helper + `cutctx wrap` env passthrough) or originates from Cutctx's own background jobs (`cutctx learn`, `cutctx evals`, WS15 pre-compaction). No heuristic sniffing of "looks async" — mis-batching an interactive request is a catastrophic UX regression.
- Mechanics: eligible requests are enqueued to the provider's batch API (Anthropic Message Batches first; OpenAI second); the proxy returns a `202`-style poll handle or holds the connection per client preference header. Queue state in the existing stats DB.
- **Attribution:** price delta recorded as `batch_routing` source.

### Steps

W13.1 eligibility gate + header spec (+ SDK helper in `sdk/typescript` and Python client) → W13.2 Anthropic batch adapter in `cutctx/backends/` following existing backend conventions → W13.3 internal consumers (learn/evals) opt in → W13.4 attribution + docs. e2e with mocked batch endpoint; regression: no header → path untouched (golden test).

---

## WS14 — Stateful delta proxy

**Goal:** stop re-billing the full conversation each turn where the provider supports server-side state; emulate where it doesn't.

### Spec (build gated — see W14.0)

- Flag: `CUTCTX_STATEFUL=1`. Applies per (session, provider).
- Mode A (provider-native state, e.g. OpenAI Responses `previous_response_id`): proxy stores the mapping session→response-id, translates the client's stateless full-history request into a delta request; on any mismatch between client history hash and our tracked state, **fall back to full send** (never guess).
- Mode B (no provider state): no delta possible on the wire; the win is already covered by CacheAligner — Mode B is explicitly out of scope. Document this so nobody builds it.
- W14.0 (required first): a one-day spike measuring real savings on recorded traffic vs CacheAligner-only, written to `artifacts/strategy-implementation-notes.md`. **If <10% marginal savings, close the workstream** — this is the most complexity-dense item here and must earn its keep.

Steps: W14.0 spike/gate → W14.1 session-state tracker + hash-verified delta translation → W14.2 fallback correctness e2e (mid-session client edit of history → full resend) → W14.3 attribution (`delta_state`) + docs. Regression: any state-tracking error must degrade to today's behavior, never to a wrong-context request — the hash check is the permanent guard.

---

## WS15 — Pre-emptive background compaction

**Goal:** compact before the context cliff, in the background, optionally via batch (WS13), instead of one giant compaction call at the limit.

**Existing scaffolding:** `session.compacting` hook (recent commit `f47b24c2`), `cutctx/context_budget.py`, IntelligentContext scoring.

### Spec

- Flag: `CUTCTX_PRECOMPACT=1`. Threshold: when session context crosses 70% (configurable) of the model window post-compression, schedule a background summarization of the *oldest low-score span* (reuse IntelligentContext scores; never touch the protected recent turns from query-aware settings).
- The summary is staged, not applied: stored in CCR keyed to the span. It is swapped in only when the session actually crosses the compaction threshold — so if the session ends first, nothing changed and the cost was one cheap (batched) background call.
- Original span goes to CCR (retrievable) — pre-compaction is reversible like everything else.
- Attribution: tokens avoided at the cliff recorded under the existing compression source with tag `precompact`.

Steps: W15.1 threshold detector + span selector (unit tests on protected-turn invariants) → W15.2 background summarizer job (batch-eligible) → W15.3 staged-swap logic + e2e: session crossing the cliff uses the staged summary, retrieval of the original works → W15.4 docs. Regression: flag off = no background calls (assert zero outbound); staged summary must never be applied to a session whose history diverged from the staged span (hash check, same principle as WS14).

---

## WS16 — Tokenizer-aware normalization

**Goal:** rewrite content into token-cheaper equivalents per the target model's tokenizer. Small, universal, zero-risk-tier.

**Existing scaffolding:** `cutctx/tokenizer.py`, `cutctx/tokenizers/`, `cutctx/proxy/deblank.py` and `snip.py` (existing micro-normalizers — extend this family, match their conventions).

### Spec

- Flag: `CUTCTX_NORMALIZE=1`. New module `cutctx/transforms/normalize.py` (the `transforms/` package exists).
- Passes (each individually testable, applied only to tool-output content, never user/assistant text): unicode NFC + homoglyph whitespace collapse; trailing-whitespace/blank-run collapse beyond what deblank does; base64/hex blobs >256 chars → CCR pointer; decimal-precision capping in numeric tables (config, default off within the flag).
- Every pass must be **semantics-preserving under the accuracy guard**: run guard checks on normalized output like any compressor.
- Measure per-pass savings with the real tokenizer for the target model (`cutctx/tokenizer.py`), record as `normalization` source.

Steps: W16.1 passes + property tests (idempotent; guard-clean on fixture corpus) → W16.2 ContentRouter wiring as a pre-pass before compressors → W16.3 attribution + docs. Regression: flag-off golden test; corpus test asserting no identifier/number-bearing line is altered when precision capping is off.

---

## WS17 — Compression-aware model downshift

**Goal:** upgrade `model_router.py` from static config-map downgrades to a decision informed by compression outcome: small compressed context + simple task type → cheaper model, with verify-and-escalate.

### Spec

- Flag: `CUTCTX_ROUTER_ADAPTIVE=1` (existing static router behavior untouched without it).
- Decision inputs (all already computed): post-compression token count, task type, guard verdict, per-(task-type) historical success rate of the cheaper model from WS19's outcome data.
- Escalation: if the downshifted response trips quality signals (guard failure, client immediate-retry, WS19 retrieval spike), re-run on the original model transparently and mark the (task-type, downgrade) pair cold for N requests. Escalation cost is charged against the savings in attribution — report *net* savings only.
- Hard exclusions: any request with tool_use in flight, any CODE/DEBUG task type initially (allowlist grows only from measured success data, never by default).

Steps: W17.1 decision function (pure, unit-tested against synthetic histories) → W17.2 escalate-and-cooldown loop + e2e with mocked models → W17.3 net attribution under existing `model_routing` source → W17.4 docs. Regression: adaptive flag off = existing router tests pass unchanged; escalation loop must be bounded (max 1 escalation per request — test it).

---

## WS18 — Learned per-customer compression policies ⭐ primary moat

**Goal:** Cutctx measurably improves on *this customer's* repos, tools, and traffic over weeks. Local training, local artifacts, nothing leaves the machine.

**Existing scaffolding:** `probe_recorder.py` (exact training pairs: original vs compressed, per real session), CCR retrieval events (= over-compression labels), guard verdicts (= safety labels), `cutctx/hooks.py` `compute_biases` (= the injection point for learned behavior), `cutctx/training/` (exists), `cutctx/prediction/feature_extractor.py`.

### Spec

- **Phase A — learned policy table (ship this; no model training):** nightly local job (`cutctx policies train`, or `--watch`) aggregates per-(tool-name, content-type, repo) outcomes: achieved ratio, guard failures, retrieval rate. Emits a policy table: `{selector → aggressiveness, algorithm hint, protected-pattern list}`. Example learned row: "`grep` outputs in repo X: aggressive (93% ratio, 0 retrievals in 400 samples)"; "`deploy.log`: conservative (3 retrievals last week)".
  - Storage: `~/.cutctx/policies.db` (or project-local), human-inspectable via `cutctx policies show` — inspectability is a trust feature, build the show command first.
  - Application: policy table consulted in the pipeline pre-compression via `compute_biases` — it *biases* existing knobs (aggressiveness, protected turns, algorithm choice); it never introduces new transforms. This keeps the blast radius inside already-tested code paths.
  - Cold start: empty table = today's defaults exactly.
- **Phase B — per-customer Kompress adapters (design + spike only in this plan):** LoRA fine-tune of `kompress-v2-base` on the customer's probe recordings, trained locally (`[ml]` extra; MPS/CUDA). Gate: Phase A retrieval-rate data must first show ≥15% headroom between default and learned-optimal aggressiveness; write the spike result to the notes file before any productization.
- **Flag:** `CUTCTX_LEARNED_POLICIES=1`. Safety: any selector whose guard-failure rate exceeds default's is auto-evicted from the table (self-healing toward defaults).

### Steps

| ID | Task |
|---|---|
| W18.1 | Outcome aggregation job over probe recordings + RequestOutcome history; schema for `policies.db`; unit tests on aggregation math |
| W18.2 | `cutctx policies show/train/reset` CLI (show first) |
| W18.3 | `compute_biases` hook implementation applying the table; flag-off golden test; cold-start-equals-defaults test |
| W18.4 | Self-healing eviction + audit events on every policy change |
| W18.5 | Report section (WS2): "your Cutctx has learned N policies; X% better ratio at equal quality" — this line is the moat made visible; treat it as a product surface, not a log |
| W18.6 | Phase B spike + gate decision in notes file |

**Regression guard:** the policy table can only move knobs within their existing valid ranges (assert range clamping); `cutctx policies reset` must restore byte-identical default behavior (golden test).

---

## WS19 — Compression autopilot (closed feedback loop)

**Goal:** treat CCR retrievals, guard failures, and client immediate-retries as quality signals and auto-tune aggressiveness per (task-type, org) — continuously, without config.

**Relationship to WS18:** WS19 is the *fast* loop (per-session/day, coarse knobs, in-memory + stats DB); WS18 is the *slow* loop (nightly, fine-grained selectors). WS19 ships first and produces the labeled outcome stream WS18 trains on.

### Spec

- Flag: `CUTCTX_AUTOPILOT=1`.
- Signals (all exist): retrieval events from `ccr/response_handler.py`; guard verdicts; same-prompt client retry within 2 requests (detect via `semantic_cache.py` key collision on a non-cached miss).
- Controller: per (task-type) aggressiveness setpoint, adjusted by bounded steps (±1 level), with hysteresis (K clean requests required before re-raising). Pure function of the signal window; deterministic and unit-testable. No ML.
- Every adjustment emits an audit event and a `RequestOutcome`-adjacent record so WS2 reports and WS18 training see it.

Steps: W19.1 signal collectors unified into a `QualitySignal` stream (tests per signal source) → W19.2 controller (pure; property tests: bounded, converges, hysteresis honored) → W19.3 pipeline wiring + flag-off golden → W19.4 dashboard sparkline on Overview + docs. Regression: setpoints clamped to existing valid range; autopilot disabled = today's static behavior (contract test).

## WS20 — Compression insurance

**Goal:** when quality loss is detected, auto-retry uncompressed and *account for it publicly* — turning failures into a guarantee.

**Depends on WS19 signals.** Flag: `CUTCTX_INSURANCE=1`.

- On guard failure at compression time: already handled (forward uncompressed) — extend to record a `prevented_degradation` event with tokens forgone.
- On post-hoc signals (retrieval storm ≥N retrievals in one turn, immediate retry): re-issue upstream request with original uncompressed content, return the better response per existing ensemble conventions (`proxy/ensemble.py` — follow its response-selection pattern), record `insurance_retry` with net token cost (negative savings — honesty is the feature).
- Report/dashboard: "guarantee ledger" — degradations prevented, insurance retries, net cost of the guarantee. Sales artifact: "we detected and absorbed 100% of quality regressions, costing 0.4% of your savings."

Steps: W20.1 event types + ledger table → W20.2 retry path + response selection e2e → W20.3 ledger in report + Governance page → W20.4 docs. Regression: retry bounded to 1 per request; flag-off golden; ledger writes are append-only.

## WS21 — CCR interchange spec (category ownership)

**Goal:** publish the retrieval-marker + pointer convention as an open spec so ecosystem tools interoperate with Cutctx's format.

- Deliverable: `docs/content/docs/ccr-spec.mdx` + versioned spec file `spec/ccr-v1.md` (new top-level `spec/`): marker grammar (`[N items compressed to M. Retrieve more: hash=…]`, `[cutctx:ref:HASH]`), retrieval tool contract (`cutctx_retrieve` name, args, semantics), scope/TTL semantics, conformance checklist.
- Code task: single source of truth — extract marker formatting/parsing currently spread across `ccr/tool_injection.py`, `dedup.py`, `ccr/response_handler.py` into `cutctx/ccr/markers.py`; all three import from it. This is the one refactor in this document; it earns its place because the spec is only credible if the implementation provably matches it (conformance tests run against `markers.py`).
- Steps: W21.1 extract `markers.py` (pure refactor, existing tests as the contract, zero behavior change) → W21.2 spec docs + conformance test suite → W21.3 MCP extension note + announce draft in `blog/`.

**Regression guard:** W21.1 is behavior-frozen — every existing CCR/dedup test must pass unmodified; add byte-level marker round-trip tests before moving code.

---

## Global acceptance for this document

- Every WS lands flag-off-default with its golden parity test in the permanent suite.
- Every new savings source appears in attribution, `cutctx perf`, and the WS2 report — unattributed savings don't exist as far as the product is concerned.
- Phase-boundary verification matrix from `strategy-implementation-plan.md` runs after each WS merges.
- WS14 and WS18-Phase-B are gated on written spike results; skipping the gate is a plan violation.
- After WS10–W13 + WS16 ship, re-run the WS3 quality-at-budget benchmark and update `benchmarks/` — the new mechanisms must show up there or their claims come out of the marketing.
