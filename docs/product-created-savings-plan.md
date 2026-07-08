# Created Savings Product Plan

## Goal

Make Cutctx meaningfully useful even when provider prompt cache is already doing most of the visible savings work.

The product should clearly separate:

- `Observed savings`: discounts the upstream provider gave us.
- `Created savings`: savings Cutctx itself generated.

## Current Diagnosis

1. Provider prompt cache dominates the dashboard because it discounts large stable prefixes across turns.
2. The current `semantic cache` surface is actually an exact-match response cache, so it rarely hits on agentic traffic.
3. CCR is operational, but the product mostly treats it as invisible storage instead of a quality-preserving workflow.
4. Proxy compression is suffix-heavy by design because preserving provider cache alignment limits how aggressively we can rewrite stable prompt prefixes.

## Product Strategy

### 1. Tell the truth in the product surface

- Rename the current `Semantic cache` runtime card to `Response cache` until the implementation is genuinely semantic.
- Show `hits`, `misses`, and `tokens avoided` so operators can understand whether the cache is useful.
- Keep provider cache as a separate line item from Cutctx-created savings.

### 2. Win where providers cannot

Prioritize created-savings surfaces that are orthogonal to provider caching:

- Tool-output compression
- Tool schema compaction
- API surface slimming
- Context-tool savings (`rtk`, future LeanCtx)
- Deterministic tool-result memoization
- Model routing for low-complexity subrequests

### 3. Turn CCR into a product feature, not a hidden implementation detail

- Show `compressed safely without retrieval` versus `retrieval rescued fidelity`.
- Add retrieval-rate and retrieval-storm signals to explain when compression is too aggressive.
- Position CCR as reversible quality insurance, not only as storage.

### 4. Replace exact-match cache with reuse that fits agent workflows

- Near-term: normalize away harmless drift such as timestamps, reminders, and low-signal metadata.
- Mid-term: ship deterministic tool-result memoization for read-only tools.
- Later: add semantic equivalence classes for repeated tool and file-read patterns.

## Roadmap

## Phase 1: Honest telemetry and operator clarity

- Rename the runtime surface from `Semantic cache` to `Response cache`.
- Expose misses, stores, evictions, expirations, and tokens avoided in `/stats`.
- Attribute Anthropic response-cache hits using cached avoided-token values.
- Add explicit cache-hit response headers for debugging.

Success criteria:

- Dashboard no longer implies semantic reuse when only exact-match reuse exists.
- Operators can explain why cache value is low or high from one screen.

## Phase 2: Created-savings scorecard

- Add a `Created savings` section that aggregates only Cutctx-generated sources.
- Break out:
  - proxy compression
  - response cache
  - CCR-assisted compression
  - schema compaction
  - API surface slimming
  - context-tool savings
  - model routing
- Add `why not more` explanations for low-activity sources.

Success criteria:

- A buyer can distinguish provider cache benefits from Cutctx value in under 30 seconds.

## Phase 3: Agent-native reuse

- Ship deterministic memoization for read-only tool calls.
- Add normalization for exact-match response cache keys.
- Introduce retrieval-rate-driven compression-policy tuning.

Success criteria:

- On a normal coding-agent workday, Cutctx-created savings come from at least 3 active sources.

## Phase 4: CCR as quality moat

- Add UI for retrieval examples, retrieval spikes, and “saved by reversible expansion” stories.
- Expose when a compressed turn needed recovery versus when it stayed compressed safely.

Success criteria:

- CCR is legible as a quality guarantee, not just an internal cache.

## Implementation Notes For This Pass

This changeset covers the first Phase 1 slice:

- response-cache metrics now include misses, stores, evictions, expirations, and avoided tokens
- Anthropic cache-hit attribution now records cached avoided-token values
- cache-hit responses include explicit `x-cutctx-response-cache` and `x-cutctx-cache-kind` headers
- the Capabilities page now labels the surface as `Response cache`
