# Token Cost Integrations Strategy And Spec

**Date:** June 20, 2026  
**Status:** Proposed  
**Audience:** Product, engineering, GTM, founder-led sales

---

## Purpose

This memo answers three questions:

1. Which external token-cost tools and platform features should CutCtx integrate?
2. How should those integrations be positioned so they help sell CutCtx instead of commoditizing it?
3. What exact product and engineering plan should be implemented to ship that strategy?

---

## Executive Summary

CutCtx should **not** position itself as "another prompt caching product." That category is increasingly absorbed by providers like OpenAI, Anthropic, Google, Bedrock, and Azure.

CutCtx should position itself as:

> **The optimization, savings intelligence, and governance layer across every token-saving mechanism.**

That means:

- Use provider-native caching wherever it exists
- Add CutCtx compression where provider caching does not help
- Add semantic cache where repeated intent is common
- Add routing, analytics, and policy so teams can see and control all of it in one place

The product should become the **system of record for token savings**, not just a compressor.

---

## Product Positioning

### Core Positioning

> CutCtx is the control plane for LLM token efficiency. It combines provider-native caching, CutCtx compression, semantic cache, and routing policies into one local-first optimization layer with measurable ROI.

### One-Liner Options

1. **The token efficiency control layer for AI agents**
2. **Make every token-saving mechanism work together**
3. **One layer to optimize, measure, and govern LLM cost**

### Why This Positioning Wins

- Provider-native caching alone is siloed by provider.
- Semantic cache alone is narrow and workload-dependent.
- Prompt compression alone is easy to commoditize.
- Gateways alone become operational plumbing.

CutCtx is strongest when it owns:

- decisioning
- compatibility
- measurement
- governance
- rollout safety

---

## Must-Have vs Nice-To-Have

### Must-Have Integrations

These directly improve product sellability and should be prioritized.

1. **OpenAI prompt caching support**
   - Detect and report cached-token usage
   - Preserve cache-friendly prefixes
   - Surface savings separately in dashboard and reports

2. **Anthropic prompt caching support**
   - Automatic `cache_control` strategies
   - Provider-specific heuristics for cacheable blocks
   - Separate reporting for prompt-cache hits vs CutCtx compression

3. **Gemini context caching support**
   - Support implicit and explicit cache modes where available
   - Add metrics so buyers can compare provider cache vs CutCtx savings

4. **Bedrock prompt caching support**
   - Important for enterprise procurement
   - Adds AWS-native story for regulated and infra-heavy buyers

5. **Azure OpenAI prompt caching support**
   - Important for enterprise and Microsoft-centric buyers
   - Must be treated as a first-class deployment surface

6. **Unified savings ledger**
   - The most important product feature
   - Must separate:
     - provider cache savings
     - CutCtx compression savings
     - semantic cache savings
     - routing/model savings

7. **Provider-aware policy engine**
   - Decide when to:
     - preserve cache-friendly prefixes
     - compress tool outputs
     - compress history
     - bypass lossy transforms

### High-Value Nice-To-Have Integrations

1. **LiteLLM cache backend interop**
   - Redis / Qdrant / semantic cache compatibility
   - Good for platform teams already standardized on LiteLLM

2. **vLLM automatic prefix caching support**
   - Strong self-hosted story
   - Best for enterprise and inference-platform teams

3. **LLMLingua as optional compression mode**
   - Good as a feature flag for long prompts
   - Should be optional, benchmark-gated, and reversible where possible

4. **GPTCache-style semantic response cache**
   - Strong for support, search, FAQ, and repeated workflow queries
   - Less useful as a default for coding agents

### Optional Ecosystem Integrations

1. **Helicone**
   - Good for observability interop
   - Not core to CutCtx value

2. **Portkey**
   - Good as an optional gateway integration
   - Not something CutCtx should depend on for its core story

### Things To Avoid

1. Becoming dependent on a third-party gateway as the primary product surface
2. Shipping semantic caching as the default for all agent workloads
3. Mixing provider-cache savings and CutCtx savings into one opaque number
4. Marketing any external cache as if it were proprietary CutCtx savings

---

## Sales Narrative

### Primary Message

> Your team already has multiple ways to save tokens. The problem is they are fragmented, provider-specific, hard to measure, and hard to govern. CutCtx unifies them into one optimization layer and one savings ledger.

### Best Commercial Angle

Do **not** sell:

> "We compress prompts."

Sell:

> "We orchestrate and measure every token-saving path across providers, caches, and agent workflows."

### Why Buyers Care

1. They want lower cost.
2. They want lower latency.
3. They want proof.
4. They want safety.
5. They want one place to operate the policy.

### GTM Message By Segment

#### Startup / AI Product Team

> Keep your existing stack. CutCtx automatically combines provider prompt caching and context compression to reduce spend and extend usable context, then shows exactly where the savings came from.

#### Platform Team

> Standardize LLM cost controls across OpenAI, Anthropic, Gemini, Bedrock, Azure, LiteLLM, and self-hosted inference. CutCtx gives you one policy layer and one savings ledger.

#### Enterprise Buyer

> CutCtx is the governance and cost-optimization layer across every model provider. It runs in your environment, preserves provider-native discounts, and gives your team auditable savings reporting.

---

## Packaging Recommendation

### Free / OSS

- Basic compression
- Basic provider compatibility
- Local stats
- No advanced savings attribution

### Team

- Unified savings dashboard
- Provider cache savings attribution
- Exportable savings reports
- Policy presets
- LiteLLM / Redis cache interop

### Business / Enterprise

- Bedrock / Azure / Vertex support
- Semantic cache controls
- Savings by org / project / agent / model
- Policy governance
- Scheduled reports
- SSO / RBAC / audit

---

## Detailed Product Spec

## Goal

Add a new product capability called:

> **Savings Orchestration**

This capability makes CutCtx aware of external token-saving systems and attributes value correctly across them.

### User Outcomes

Users should be able to:

1. Turn on provider-native caching without losing CutCtx compression benefits
2. See exactly how much each mechanism saved
3. Configure per-provider policy defaults
4. Export buyer-grade ROI reports
5. Safely compare strategies by workload

---

## Functional Requirements

### FR-1: Savings Source Attribution

CutCtx must track savings separately for:

- `provider_prompt_cache`
- `cutctx_compression`
- `semantic_cache_response_hit`
- `prefix_cache_self_hosted`
- `model_routing`

### FR-2: Unified Savings Ledger

Each request record must support:

- provider
- model
- cache mode used
- compression mode used
- tokens before optimization
- tokens after CutCtx optimization
- provider cached tokens
- semantic cache hit tokens avoided
- estimated dollar savings by source

### FR-3: Policy Engine

Policy must support:

- `preserve_prefix_for_provider_cache`
- `compress_tool_outputs_only`
- `compress_history_after_turn_n`
- `disable_lossy_compression_when_provider_cache_expected`
- `semantic_cache_enabled`
- `semantic_cache_threshold`

### FR-4: Dashboard Views

Add dashboard support for:

- total savings by source
- savings by provider
- savings by model
- savings by workload type
- policy effectiveness
- provider-cache vs CutCtx overlap analysis

### FR-5: ROI Reporting

Reports must export:

- weekly and monthly savings
- savings by source
- savings by org/project/agent/model
- "what if CutCtx were disabled"
- "what if provider cache were disabled"

### FR-6: A/B Strategy Evaluation

Support side-by-side comparisons for:

- provider-cache only
- CutCtx compression only
- combined mode
- semantic cache mode

---

## Non-Functional Requirements

1. **No silent savings inflation**
   - Provider cache savings must not be counted again as CutCtx savings.

2. **Backward compatibility**
   - Existing proxy flows must continue to work if integrations are disabled.

3. **Local-first**
   - Savings measurement and policy control must work without requiring SaaS.

4. **Explainability**
   - Each savings number shown in the dashboard must be attributable to a source and formula.

---

## Architecture Plan

### New Concept: SavingsSource

Add a normalized savings-source model in the core telemetry path.

Suggested enum:

```python
class SavingsSource(str, Enum):
    PROVIDER_PROMPT_CACHE = "provider_prompt_cache"
    CUTCTX_COMPRESSION = "cutctx_compression"
    SEMANTIC_CACHE = "semantic_cache"
    PREFIX_CACHE_SELF_HOSTED = "prefix_cache_self_hosted"
    MODEL_ROUTING = "model_routing"
```

### Data Model Changes

Extend request metrics / persisted request records with fields like:

```json
{
  "provider": "openai",
  "model": "gpt-5.5",
  "tokens_input_raw": 12000,
  "tokens_after_cutctx": 8400,
  "provider_cached_tokens": 3000,
  "semantic_cache_tokens_avoided": 0,
  "self_hosted_prefix_cache_tokens_avoided": 0,
  "tokens_saved_total": 3600,
  "savings_breakdown": {
    "cutctx_compression": 600,
    "provider_prompt_cache": 3000,
    "semantic_cache": 0,
    "prefix_cache_self_hosted": 0,
    "model_routing": 0
  },
  "dollar_savings_breakdown": {
    "cutctx_compression": 0.003,
    "provider_prompt_cache": 0.018
  }
}
```

### Policy Layer

Add a provider-aware optimization strategy resolver:

- `headroom/policy/savings_orchestrator.py`

Responsibilities:

- inspect provider/model/workload
- decide whether to preserve prefixes
- decide whether to compress history
- decide whether to enable semantic cache lookup
- annotate request with active optimization strategy

### Provider Adapters

Add provider-specific savings parsers:

- `headroom/providers/openai/savings.py`
- `headroom/providers/anthropic/savings.py`
- `headroom/providers/gemini/savings.py`
- `headroom/providers/bedrock/savings.py`
- `headroom/providers/azure_openai/savings.py`

Responsibilities:

- parse provider response usage fields
- extract cached token counts where available
- normalize into shared savings schema

### Semantic Cache Adapter Layer

Add optional semantic cache abstraction:

- `headroom/cache/semantic/base.py`
- `headroom/cache/semantic/gptcache_adapter.py`
- `headroom/cache/semantic/litellm_adapter.py`

Do not hardcode any one vendor into the core path.

### Dashboard Additions

Extend dashboard payload with:

- `savings.sources`
- `savings.by_provider`
- `savings.by_model`
- `savings.policy_effectiveness`
- `savings.overlap`

### CLI Additions

Add or extend:

- `cutctx savings report --by-source`
- `cutctx savings report --by-provider`
- `cutctx savings compare --strategy provider-cache-only`
- `cutctx savings compare --strategy combined`
- `cutctx integrations status`
- `cutctx integrations test openai`

---

## Exact Implementation Plan

## Phase 1: Measurement First

### Objective

Make savings attribution trustworthy before adding more integrations.

### Work

1. Add normalized savings breakdown model to request metrics
2. Extend stats payload and history payload
3. Persist savings breakdown to storage
4. Update dashboard cards to split:
   - provider cache savings
   - CutCtx savings
   - total savings
5. Add tests for no double counting

### Files To Touch

- `headroom/proxy/server.py`
- `headroom/proxy/cost.py`
- `headroom/proxy/savings_tracker.py`
- `headroom/ccr/mcp_server.py`
- dashboard templates or React dashboard payload consumers

### Acceptance Criteria

- Dashboard shows separate lines for provider cache and CutCtx savings
- Exports preserve the same breakdown
- Total savings equals sum of individual sources

## Phase 2: Provider-Native Caching Support

### Objective

Make CutCtx aware of provider cache behavior.

### Work

1. Add OpenAI cached-token parser
2. Add Anthropic cached-token parser
3. Add Gemini cache parser
4. Add Bedrock and Azure parsers
5. Add policy hints:
   - preserve long stable prefix
   - minimize unnecessary rewrite of cacheable blocks

### Files To Add

- `headroom/providers/openai/savings.py`
- `headroom/providers/anthropic/savings.py`
- `headroom/providers/gemini/savings.py`
- `headroom/providers/bedrock/savings.py`
- `headroom/providers/azure_openai/savings.py`

### Acceptance Criteria

- Each provider parser maps response usage into common breakdown fields
- Dashboard shows cache savings by provider
- Unit tests cover missing/partial usage fields

## Phase 3: Savings Orchestrator

### Objective

Choose the best mechanism per workload.

### Work

1. Add orchestration policy config
2. Detect workload classes:
   - coding agent
   - support/search
   - long-doc Q&A
   - repetitive workflow agent
3. Apply strategy defaults:
   - coding agent: provider cache + tool-output compression
   - support/search: semantic cache + provider cache + conservative compression
   - long-doc Q&A: provider cache + optional LLMLingua mode

### Files To Add

- `headroom/policy/savings_orchestrator.py`
- `docs/spec/005-integrations.md`
- `docs/spec/016-observability.md`

### Acceptance Criteria

- Strategy selection is logged and visible in stats
- Policies can be overridden by config and CLI
- Existing behavior remains default-safe when orchestrator is disabled

## Phase 4: Optional Integrations

### Objective

Add external cache/compression engines behind adapters.

### Recommended Order

1. LiteLLM cache interop
2. vLLM prefix-cache telemetry support
3. GPTCache semantic adapter
4. LLMLingua optional compressor

### Guardrails

- every optional integration must be feature-flagged
- every integration must have benchmark coverage
- every integration must report attribution separately

## Phase 5: GTM and Buyer Proof

### Objective

Turn technical capability into a sellable feature set.

### Work

1. Add ROI report template with savings-by-source breakdown
2. Add pricing-page language for unified savings orchestration
3. Add pilot success metric:
   - "verified provider + CutCtx combined savings"
4. Add sales deck proof screenshots from dashboard

### Files To Update

- `artifacts/value-proposition.md`
- `artifacts/pricing-sheet.md`
- `artifacts/pilot-success-metrics.md`
- `docs/pricing.html`

---

## Recommended Defaults

### Default Strategy by Workload

| Workload | Provider Cache | CutCtx Compression | Semantic Cache | Notes |
|----------|----------------|--------------------|----------------|-------|
| Coding agents | On | Tool outputs only, conservative history compression | Off by default | Preserve provider-cache prefixes |
| Support / FAQ | On | Light | On | Best semantic-cache fit |
| Long document Q&A | On | Optional heavy compression | Optional | Good for LLMLingua experiments |
| Repetitive internal workflows | On | Moderate | On | Strong combined ROI |
| Self-hosted inference | vLLM APC | On | Optional | Best enterprise/on-prem story |

---

## Metrics To Add

Add to `/stats`, `/stats-history`, and ROI exports:

- `provider_cached_tokens`
- `provider_cache_savings_usd`
- `cutctx_compression_savings_usd`
- `semantic_cache_savings_usd`
- `combined_savings_usd`
- `cache_preservation_rate`
- `compression_vs_cache_overlap_pct`
- `strategy_selected`
- `strategy_effectiveness_score`

---

## Testing Plan

### Unit Tests

- provider usage parsing
- breakdown aggregation
- no double-counting of savings
- policy selection logic

### Integration Tests

- OpenAI response with cached token fields
- Anthropic request with `cache_control`
- Gemini explicit cache flow
- fallback when provider returns no cache metadata

### Benchmark Tests

For each workload, compare:

1. baseline
2. provider cache only
3. CutCtx only
4. combined
5. semantic cache enabled

### Manual QA

- dashboard correctness
- export correctness
- CLI compare flows
- policy override behavior

---

## What Success Looks Like

This initiative is successful when all of the following are true:

1. A buyer can see a dashboard that separates provider savings from CutCtx savings.
2. A founder can say "CutCtx makes every token-saving layer work together" and the product proves it.
3. Engineering teams can enable new savings mechanisms without changing app code.
4. CutCtx becomes harder to replace because it owns optimization policy and ROI reporting.

---

## Recommended Immediate Next Steps

1. Ship **Phase 1** first: savings attribution and dashboard breakdown.
2. Ship **OpenAI + Anthropic** provider-aware support next.
3. Add **LiteLLM interop** before GPTCache or LLMLingua.
4. Treat **LLMLingua** as experimental until benchmarked in your target workloads.
5. Update GTM copy only after the dashboard can prove the breakdown.

---

## Founder Script

Use this in demos and outreach:

> Most teams now have multiple token-saving mechanisms available, but they are fragmented and hard to operate. CutCtx is the layer that makes them work together. We preserve provider-native cache wins, compress the payloads those caches do not touch, add optional semantic caching where it makes sense, and show you exactly where every dollar of savings came from.

