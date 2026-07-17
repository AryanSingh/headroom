# Cutctx competitive and best-in-class product audit

**Date:** 2026-07-17  
**Scope:** product strategy only; no production code was changed.  
**Evidence standard:** repository inspection and current primary sources. “Verified” means supported by source code, docs, or an official competitor source. “Inference” is labelled as such. Vendor claims are not treated as independent performance proof.

## 1. Executive summary

Cutctx has a credible opportunity to own a category that the market has not yet assembled cleanly: **the local-first, evidence-backed context control plane for coding agents**. The product already combines capabilities that are normally purchased separately: structured context reduction, cache alignment, reversible retrieval, cross-agent memory, safe model-routing, savings attribution, and gateway compatibility.

It is **not** yet best in class in the customer-visible sense. The strongest competitors win with a narrower, more legible story:

1. **LiteLLM, Portkey, and Cloudflare AI Gateway** make gateway adoption, routing, and provider reliability easy.
2. **Langfuse and Helicone** make traces, evaluation, prompt iteration, and debugging easy to trust.
3. **Mem0 and Zep/Graphiti** make memory quality, temporal facts, and retrieval semantics explicit.
4. **LLMLingua and provider-native caching/compaction** establish the baseline for compression and context reuse.

Cutctx’s strategic mistake would be trying to become a generic gateway, a generic LLMOps suite, and a generic memory vendor simultaneously. Its strategic advantage is making every context-reduction decision **reversible, attributable, policy-safe, and measurable on real agent work**—then exporting that evidence to the systems customers already operate.

### Recommendation

Position Cutctx as:

> **The context control plane for coding agents: reduce the context that does not matter, retain or retrieve what does, and prove every quality/cost decision.**

The first high-confidence milestone is a **Context Decision Explorer**: a single trace view that shows original context, selected compression/retrieval/routing decision, protected anchors, provider-cache effect, quality evidence, and a safe replay comparison. It turns existing technical breadth into a concrete customer outcome and directly answers the trust problem that blocks context optimization adoption.

## 2. Market definition

Cutctx overlaps six adjacent markets but should not position itself as a substitute for all of them.

| Market | Buyer job | Competitive baseline | Cutctx’s role |
|---|---|---|---|
| AI gateways | Reach models reliably, govern spend, survive provider failures | LiteLLM, Portkey, Cloudflare AI Gateway | Complementary context policy layer; retain compatible proxy path |
| LLM observability / evals | Explain, test, and improve model behaviour | Langfuse, Helicone | Emit context-decision evidence into the trace/eval stack |
| Agent memory | Retrieve durable, relevant state across sessions | Mem0, Zep/Graphiti | Agent/workspace memory plus context compression; improve temporal/provenance semantics |
| Prompt compression | Fit more useful information into a context window | LLMLingua, native compaction | Content-aware, reversible, production-oriented compression |
| Native provider optimization | Reuse stable prefixes and compact provider context | OpenAI/Anthropic/Gemini | Preserve native gains and attribute them separately |
| Coding-agent tooling | Make agents safer, faster, and easier to operate | Host-native memory/compaction, agent wrappers | Local agent integration, tool-output reduction, CCR, shared learning |

## 3. Competitor selection and rationale

The selection is based on functional overlap rather than brand recognition.

| Competitor / adjacent baseline | Why it matters |
|---|---|
| LiteLLM | The open-source reference gateway for multi-provider routing, budgeting, and enterprise proxy operations. |
| Portkey | The gateway competitor with an unusually productized routing, guardrail, MCP, and observability experience. |
| Cloudflare AI Gateway | The managed-edge benchmark for simple cache, rate-limit, fallback, and visual routing workflows. |
| Helicone | Directly competes for “one-line integration” observability, prompt workflow, sessions, and gateway convenience. |
| Langfuse | The strongest adjacent benchmark for trace UX, evaluation workflow, datasets, prompt management, and self-hosted LLMOps. |
| Mem0 | A leading memory-layer reference with managed, self-hosted, and agent-focused workflows and published benchmarks. |
| Zep / Graphiti | The temporal-context-graph reference for memory provenance, historical validity, hybrid retrieval, and graph semantics. |
| LLMLingua | The primary open prompt-compression research baseline, especially for LongLLMLingua/LLMLingua-2. |
| OpenAI native caching and compaction | A necessary provider-native baseline: customers should not pay Cutctx to duplicate what a provider delivers automatically. |

## 4. Competitor comparison matrix

Legend: **Strong** = central documented capability; **Partial** = available but not central/needs integration; **—** = not the product’s documented focus. This is a capability map, not a scorecard or quality ranking.

| Product | Gateway / routing | Cache / response reuse | Context compression | Durable memory | Trace, eval, prompt UX | Governance / deployment | Primary strength | Material tradeoff |
|---|---|---|---|---|---|---|---|---|
| Cutctx | Strong | Strong | Strong | Strong | Partial | Strong | Local, reversible, agent-aware context control | Broad surface, proof and UX are fragmented |
| LiteLLM | Strong | Strong | Partial | — | Partial | Strong | Provider breadth, virtual keys, routing, spend controls | Does not own context quality/compression semantics |
| Portkey | Strong | Partial | — | — | Strong | Strong | Fast productized gateway, guardrails, MCP control | Context reduction is outside the core value proposition |
| Cloudflare AI Gateway | Strong | Strong | — | — | Partial | Strong | Managed edge operations and simple configurable routing | Cloud/platform dependency; cache is not semantic understanding |
| Helicone | Strong | Partial | — | — | Strong | Strong | Observability, sessions, prompt management, hosted UX | No deep reversible context-control layer |
| Langfuse | Partial | — | — | — | Strong | Strong | Evals, datasets, prompts, traces, self-hosting | Not a data-plane optimization layer |
| Mem0 | — | — | Temporal memory only | Strong | Partial | Strong | Memory algorithms, managed platform, agent skills | Requires application-side memory lifecycle / model calls |
| Zep / Graphiti | — | — | Graph context assembly | Strong | Strong (Zep Cloud) | Strong (Zep Cloud) | Temporal provenance and relationship-aware retrieval | Graph infrastructure/operational cost; community Zep deprecated |
| LLMLingua | — | — | Strong | — | — | OSS library | Research-backed prompt compression | Library-level, lossy by design; no proxy governance/CCR |
| Native OpenAI | Provider-scoped | Strong | Strong for transcript compaction | — | Provider console only | Provider-scoped | No-code native cache and context compaction | Provider lock-in; does not govern arbitrary agent/tool context across providers |

## 5. Detailed competitor findings

### LiteLLM — gateway reliability and operational breadth

**Verified.** LiteLLM presents an OpenAI-compatible SDK/proxy spanning 100+ model providers with virtual keys, spend tracking, guardrails, load balancing, and an admin dashboard. Its public repository claims an 8 ms P95 at 1k RPS; treat that as vendor-reported benchmark evidence, not an apples-to-apples Cutctx comparison. It also exposes agent and MCP gateway surfaces. [LiteLLM repository](https://github.com/BerriAI/litellm)

**Why it is strong:** one integration path, mature provider coverage, and a clear control-plane story for platform teams. The community footprint is substantial (53.8k GitHub stars as observed on 2026-07-16).

**Tradeoff:** it optimizes *where* a call goes and how it is governed, not whether tool outputs, logs, retrieved chunks, or conversation state deserve to occupy the context window.

**Implication for Cutctx:** do not compete on “100+ providers” marketing. Be a first-class LiteLLM extension/exporter and show **context cost avoided before gateway routing** versus provider/cache/model-routing savings after it.

### Portkey — productized routing, guardrails, and MCP operations

**Verified.** Portkey’s gateway documents retries, fallbacks, load balancing, conditional routing, guardrails, a local console, hosted/enterprise deployment, and an MCP Gateway with centralized auth, access control, identity forwarding, and tool-call observability. It claims <1 ms gateway latency and 10B tokens/day; those are vendor claims. [Portkey Gateway repository](https://github.com/Portkey-AI/gateway)

**Why it is strong:** its configuration-led UX makes an abstract gateway policy tangible. Its MCP control plane is particularly relevant as agents become tool-first.

**Tradeoff:** its documented core is transport reliability and control, not selective/reversible agent-context reduction.

**Implication for Cutctx:** match the clarity, not the feature checklist. Every Cutctx decision should be represented as a versioned, previewable policy with a before/after receipt—especially compression, retrieval expansion, and downgrade abstention.

### Cloudflare AI Gateway — managed baseline for operational controls

**Verified.** Cloudflare documents AI Gateway analytics, caching, rate limiting, model fallback, DLP, guardrails, BYOK, and dynamic routing. Dynamic routes can be configured visually or in JSON, using conditionals, rate/budget limits, model nodes, and fallbacks. Its cache supports TTL and custom cache keys but is explicitly volatile, so concurrent identical requests can still miss. [AI Gateway overview](https://developers.cloudflare.com/ai-gateway/) and [dynamic routing](https://developers.cloudflare.com/ai-gateway/features/dynamic-routing/)

**Why it is strong:** it makes a broad set of operational primitives easy to adopt without deploying a bespoke control plane.

**Tradeoff:** cache equality/TTL and routing conditions do not establish semantic relevance, compression safety, or recoverability of discarded context.

**Implication for Cutctx:** integrate rather than duplicate. Export cache-safe prefix construction and context-decision metadata; make the value proposition independent of any cloud edge.

### Helicone — observability and prompt workflow standard

**Verified.** Helicone documents an AI Gateway for 100+ models, automatic fallbacks, traces and sessions, cost/latency/quality analytics, a playground, prompt versioning, self-hosting, and a 10k-request free tier. It states SOC 2 and GDPR compliance; this is a vendor compliance claim. [Helicone repository](https://github.com/Helicone/helicone)

**Why it is strong:** one-line adoption, understandable session views, direct path from a bad trace to a prompt experiment, and a mature hosted UX.

**Tradeoff:** it observes and routes requests but does not provide a documented, reversible data-plane system for reducing arbitrary agent context.

**Implication for Cutctx:** current Langfuse integration is useful, but customer-facing trace UX must show a complete decision story. Do not force buyers to infer why the context shrank, expanded, retrieved, or stayed on a strong model.

### Langfuse — the bar for evaluation and engineering workflow

**Verified.** Langfuse documents tracing for calls, retrieval, embedding and agent actions; prompt management; LLM-as-a-judge, code, manual and user-feedback evaluation; datasets/experiments; playground; API/SDKs; cloud and self-hosting. [Langfuse repository](https://github.com/langfuse/langfuse)

**Why it is strong:** it turns observability into an improvement loop rather than a passive dashboard.

**Tradeoff:** it is an observability/evaluation plane, not an in-line context optimization system.

**Implication for Cutctx:** ship a native **context-quality evaluation pack** that exports runs to Langfuse but also works locally. It must compare original vs. optimized agent outcome, tool-call validity, retrieval necessity, cost, latency, and user acceptance—not just compression ratio.

### Mem0 — memory productization and benchmark transparency

**Verified.** Mem0 offers a library, self-hosted server, cloud platform, CLI, and coding-agent skills. Its current documentation describes multi-level user/session/agent memory, hybrid semantic/BM25/entity retrieval, temporal reasoning, and an open evaluation framework. Its headline benchmark scores are explicitly for its managed platform and may not reproduce in OSS. [Mem0 repository](https://github.com/mem0ai/mem0)

**Why it is strong:** a crisp memory value proposition, distribution into agent workflows, and a public benchmark narrative.

**Tradeoff:** memory extraction/addition is itself an application/model workflow. It does not make arbitrary tool payloads reversible, nor does it provide a provider-neutral compression control plane.

**Implication for Cutctx:** stop claiming broad memory superiority without running the same public benchmarks. Differentiate on local provenance, agent/workspace scoping, no-extra-call extraction where safe, and memory-to-context cost accounting; validate those claims against LongMemEval/LoCoMo rather than comparison tables alone.

### Zep and Graphiti — temporal provenance and relationship-aware retrieval

**Verified.** Zep is now a managed memory platform; its former community edition is deprecated. Its open Graphiti project builds temporal context graphs with fact validity windows, episode provenance, incremental updates, hybrid semantic/keyword/graph retrieval, and MCP support. Graphiti’s own README distinguishes the managed Zep control plane from the self-managed open framework. [Zep repository](https://github.com/getzep/zep) and [Graphiti repository](https://github.com/getzep/graphiti)

**Why it is strong:** it models not merely “facts,” but *when* facts were true and *where* they came from. This is the right semantic bar for consequential agent memory.

**Tradeoff:** graph infrastructure and extraction increase implementation and operational complexity; Graphiti expects a graph backend and structured-output-capable models.

**Implication for Cutctx:** do not rush to build a general knowledge graph. First add a lightweight, queryable **provenance and supersession model** for Cutctx memories and CCR items: source turn/tool/file, validity period, policy version, and retrieval outcome. Escalate to graph relationships only after usage proves the need.

### LLMLingua — compression research baseline

**Verified.** Microsoft’s LLMLingua family uses a small model to identify removable prompt tokens. LongLLMLingua targets long-context/RAG ordering and compression; LLMLingua-2 is a distilled task-agnostic token classifier. The repository cites peer-reviewed papers and reports up to 20x compression with minimal performance loss; results must be read in the specific research-task context. [LLMLingua repository](https://github.com/microsoft/LLMLingua)

**Why it is strong:** a clear research baseline and a compression-specific evaluation tradition.

**Tradeoff:** it is a library rather than an agent control plane. It does not supply provider compatibility, policy, cache attribution, routing, multi-agent memory, or retrieval of the original content.

**Implication for Cutctx:** benchmark against it honestly on shared corpora and publish per-workload outcomes. Cutctx should win on *operational safety and agent outcomes*, not claim a universal compression ratio win.

### Provider-native OpenAI caching and compaction — non-negotiable baseline

**Verified.** OpenAI prompt caching is automatic for eligible recent models and begins at 1,024 prompt tokens; it reuses exact prefixes and exposes cached-input usage. OpenAI also offers server-side and standalone Responses compaction that carries forward encrypted compacted state for continued conversations. [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) and [compaction](https://developers.openai.com/api/docs/guides/compaction)

**Why it is strong:** no additional product to adopt, and an exact-prefix cache has no semantic-risk decision.

**Tradeoff:** provider-specific, transcript-focused, and unable to govern arbitrary tool output across agents/providers. It does not give Cutctx-style source-level attribution or local recovery of all original agent context.

**Implication for Cutctx:** cache alignment is important, but provider-cache savings must never be presented as Cutctx-created savings. The product should lead with incremental value above native caching, supported by explicit attribution.

## 6. Verified Cutctx strengths

1. **Unusually complete context pipeline.** The codebase joins content-aware transforms, a proxy, SDKs, memory, model routing, telemetry, dashboard, agent wrappers, and optional enterprise extensions. The architecture is not a thin wrapper around one provider.
2. **Reversibility is the defensible core.** CCR enables reduced context without treating deletion as permanent. That is a clearer answer to the compression-trust objection than “our model is probably accurate.”
3. **Cache-aware and attribution-aware.** The README and pipeline separately account for provider prompt-cache, direct compression, RTK, semantic cache, self-hosted prefix cache, and model-routing savings. This is strategically correct and should remain an invariant.
4. **Routing safety is stronger than simplistic cheapest-model routing.** The router records an explainable decision, requires capabilities, respects subscription transport constraints, and retains high-risk/recent-tool work on the requested model. [Model router](../cutctx/proxy/model_router.py#L1003)
5. **Agent-native distribution.** `cutctx setup` detects agents, registers MCP, starts the proxy, and verifies setup; the product also has host-specific wrappers and plugins. [Setup command](../cutctx/cli/setup.py#L112)
6. **Honest limitations and guardrails.** Documentation plainly states that source code and RAG often pass through, and that BFCL is not a release-quality signal until structurally validated. This is rare and valuable product discipline. [Limitations](../docs/content/docs/limitations.mdx#L8) and [benchmarks](../docs/content/docs/benchmarks.mdx#L26)
7. **A viable enterprise base.** RBAC, audit, retention, identity, entitlements, encryption for orchestration credentials, and air-gap paths exist. The direct orchestration executor correctly remains disabled by default where it would bypass the canonical pipeline. [Orchestration platform](../docs/content/docs/orchestration-platform.mdx#L131)

## 7. Product and technical gap analysis

### P0 findings — credibility blockers

| Finding | Severity / confidence | Evidence | Customer impact | Concrete remediation |
|---|---|---|---|---|
| No public, repeatable agent-outcome benchmark that compares Cutctx with the native/provider and LLMLingua baselines on a common corpus. | High / verified | Provider-backed evaluations currently cover 100 SQuAD, 50 HotpotQA, and 50 CodeSearchNet examples; docs explicitly say these are not cross-vendor proof. BFCL is excluded. | “Best in class” cannot be credibly claimed; compression ratio alone does not earn trust. | Publish a versioned agent-context benchmark with raw prompts redacted/consented, original-vs-optimized task result, executable tool validation, latency, cost, retrieval rate, and cache attribution. |
| The main product decision is not sufficiently visible in the dashboard. | High / verified | Dashboard routes cover overview, savings, orchestrator, capabilities, governance, firewall, memory, replay, playground, and docs—but no dedicated context-decision/evidence view. [Routes](../dashboard/src/App.jsx#L381) | Operators cannot immediately tell whether savings came from cache, compression, retrieval, routing, or accidental loss. | Build Context Decision Explorer with per-turn receipt, protected anchors, CCR link/retrieval, cache state, policy/model decision, and replay verdict. |
| The public story overstates universal breadth relative to documented behavior. | High / verified | Limitations say code and RAG contexts commonly pass through; AST compression is intentionally gated. [Limitations](../docs/content/docs/limitations.mdx#L35) | Sophisticated users discover exceptions after install and downgrade trust. | Replace “compresses everything” language with workload-specific promises: tool outputs, logs, JSON, diffs, search results, and managed long sessions. Publish the no-op and abstention rate. |
| Distributed-state posture is immature for enterprise-scale agent workflows. | High / verified | Durable workflows use `workflows.json` and the docs state that multi-host workers need a shared transactional backend. [Orchestration docs](../docs/content/docs/orchestration-platform.mdx#L137) | Teams can mistake a safe single-host implementation for a distributed scheduler. | Ship one supported HA state backend (Postgres first; Redis only for coordination/cache), clear topology guidance, backup/restore drills, and a non-HA refusal/warning. |

### P1 findings — high-value competitive improvements

| Finding | Severity / confidence | Evidence | Recommendation |
|---|---|---|---|
| Evaluation, prompt iteration, and trace UX lag Langfuse/Helicone. | High / high-confidence inference | Cutctx has Langfuse/OTel extras and replay screens, but no unified customer-facing quality loop comparable to datasets → experiment → trace → prompt/replay. | Add local-first evaluation datasets, golden tasks, annotation/acceptance events, and export/import adapters for Langfuse. |
| Memory semantics need stronger provenance/temporal explanation to match Mem0/Graphiti. | Medium / high-confidence inference | Cutctx has hierarchical scopes and supersession, while Graphiti documents episode provenance and explicit validity windows. | Add memory/CCR provenance receipts, query explanation, confidence/expiry/validity, and contradiction/supersession UI before attempting a full graph product. |
| Policy setup is too configuration-centric. | Medium / verified | Cutctx has 61 proxy flags plus multiple modes/presets; current setup is materially improved but decisions still require operator interpretation. | Provide workload contracts with intent, allowed transforms, quality budget, rollout percent, and simulated receipts—then compile to existing controls. |
| Enterprise control-plane UX is incomplete. | Medium / verified | API/EE surface is broad; the React dashboard route list has no dedicated audit, org, SCIM, retention, or fleet pages. | Make high-frequency buyer workflows first-class: tenant/workspace, identity status, audit search/export, retention, deployment health, and support bundle. |
| Ecosystem positioning is underspecified. | Medium / high-confidence inference | The code has LiteLLM and Langfuse integrations, but public positioning risks sounding like an alternative rather than a multiplier. | Publish integration packs: “Cutctx + LiteLLM”, “Cutctx + Langfuse”, “Cutctx behind Cloudflare AI Gateway”, each with architecture, attribution, and a 15-minute verified setup. |

### P2 findings — differentiators after the trust loop works

| Opportunity | Why it differentiates | Guardrail |
|---|---|---|
| Context quality autopilot | Adapt compression/retrieval/routing only from verified task outcomes and policy bounds. | Never learn from proxy savings alone; require outcome evidence and rollback. |
| Cross-agent context ledger | A shared, local evidence graph for facts, tool outputs, CCR blobs, decisions, source provenance, and expiry. | Start with a relational provenance model; do not build GraphRAG by default. |
| Safe model-routing evidence marketplace | Provider/customer-specific shadow evidence with capability proof and abstention reason. | Do not route solely on aggregate benchmark wins; maintain per-workload reliability budgets. |
| MCP context governance | Per-tool payload budgets, memoization/replay, least-privilege memory, tool-result citations, and team policy. | Preserve host-native semantics and require explicit tool-call validation. |

## 8. Ranked recommendations

### P0 — necessary to be credible

#### 1. Context Decision Explorer and stable decision receipt

- **Evidence:** Portkey/Cloudflare make policies inspectable; Langfuse/Helicone make traces understandable; Cutctx already emits routing and savings metadata.
- **Affected areas:** `cutctx/proxy/*decision*`, `cutctx/proxy/savings_metadata.py`, request outcome/trace API, `dashboard/src/pages/Overview.jsx`, a new `dashboard/src/pages/ContextDecisions.jsx`.
- **User outcome:** an operator can answer “what changed, why, what was protected, could it be retrieved, and did quality hold?” in one click.
- **Risk:** exposing sensitive payloads. Default to hashes/redacted anchors, RBAC, and explicit payload-access scope.
- **Verification:** a Playwright scenario creates a tool-heavy request, verifies the receipt fields, invokes a CCR retrieval path, and compares source-attribution totals without double counting.

#### 2. Publish an independent, reproducible Agent Context Quality Benchmark

- **Evidence:** Cutctx docs themselves correctly reject current sample sizes and BFCL text similarity as product proof; Mem0 and LLMLingua make benchmark frameworks central to trust.
- **Affected areas:** `benchmarks/`, `cutctx/evals/`, `tests/test_evals/`, `docs/content/docs/benchmarks.mdx`, CI release evidence.
- **User outcome:** buyers can evaluate expected savings and quality by workload rather than accept a headline ratio.
- **Risk:** unfavorable results. That is a product-discovery benefit; segment/no-op results instead of hiding them.
- **Verification:** fixed corpus/version/model matrix; original vs. Cutctx vs. native compaction/cache baseline vs. LLMLingua; executable tool assertions; report confidence intervals and provenance.

#### 3. Truthful positioning and first-run proof

- **Evidence:** direct docs state that code/RAG may be intentionally unchanged, while the headline presents broad compression claims.
- **Affected areas:** `README.md`, `PRODUCT_GUIDE.md`, docs quickstart, setup/perf output, dashboard onboarding.
- **User outcome:** a new user sees a workload fit verdict, an expected savings range, and an immediate “why nothing changed” explanation.
- **Risk:** narrower messaging may reduce top-of-funnel clicks but increases qualified conversion and retention.
- **Verification:** fresh-machine onboarding test reaches a value proof in <15 minutes with no manual proxy debugging; measure activation and 7-day repeat use.

### P1 — high-value differentiation and retention

#### 4. Local-first evaluation loop with Langfuse interoperability

- **Evidence:** Langfuse is the category UX leader for prompts, datasets, evaluation, and trace-driven iteration; Cutctx already supports Langfuse/OTel dependencies.
- **Affected areas:** evaluator/telemetry modules, `sdk/`, dashboard replay/playground, documentation.
- **User outcome:** teams can set a quality budget, run a shadow/replay comparison, approve a policy, and export evidence to their existing LLMOps system.
- **Risk:** accidentally becoming a second generic observability system.
- **Verification:** import a dataset, run baseline vs. policy, review failures with one-click provenance, export a compatible trace/eval outcome.

#### 5. Provenance-first memory and CCR ledger

- **Evidence:** Graphiti differentiates with time and source provenance; Mem0 differentiates with retrieval/eval story. Cutctx owns the unusual combination of local memory and reversible originals.
- **Affected areas:** `cutctx/memory/`, `cutctx/ccr/`, memory schema/migrations, dashboard Memory/Replay pages.
- **User outcome:** users can tell what an agent remembered, where it came from, whether it is current, and why it was injected or retrieved.
- **Risk:** privacy and retention complexity.
- **Verification:** memory supersession, source deletion/retention expiry, scoped access, and injection explanation all have automated integration tests.

#### 6. Context contracts and progressive rollout

- **Evidence:** Cloudflare/Portkey provide visual/versioned policy control; Cutctx has routing contracts/presets but needs a simpler operator abstraction.
- **Affected areas:** routing settings/compiler, config API, dashboard routing studio, audit log.
- **User outcome:** operators express intent such as “SRE logs may compress to 20% only if error anchors survive” rather than manipulate compression flags.
- **Risk:** a second config language.
- **Verification:** every saved contract compiles deterministically to existing settings, supports a simulation receipt, has an approval/audit record, and rolls back instantly.

### P2 — only after P0/P1 evidence is working

#### 7. Production HA state backend and fleet-ready topology

- **Evidence:** current docs limit workflows to one host/shared POSIX state; enterprise competitors sell managed control planes and topology confidence.
- **Affected areas:** workflow store abstraction, memory/CCR storage adapters, deployment docs/Helm, health/backup controls.
- **User outcome:** teams can use multiple replicas without ambiguous state or unsupported claims.
- **Risk:** major operational expansion.
- **Verification:** chaos-tested multi-replica workflow/memory state, backup restore test, and explicit consistency/idempotency documentation.

## 9. Proposed best-in-class position

### The product boundary

**Cutctx should own:** what enters an agent’s context, why it is retained/compressed/retrieved, how it affects cache/routing, and whether the decision still produces a verified outcome.

**Cutctx should integrate with:** inference gateways (LiteLLM, Portkey, Cloudflare), LLMOps/evals (Langfuse, Helicone), provider-native caching/compaction, and graph-memory systems where customers already standardize.

**Cutctx should avoid owning by default:** a marketplace of arbitrary model providers, a generic prompt CMS, a hosted analytics warehouse, or a general graph database.

### Differentiated customer promise

> Cutctx reduces the context your coding agents do not need, keeps what they may need recoverable, respects provider-native cache and compaction, and produces an auditable receipt for every quality/cost tradeoff.

This promise is defensible because it ties the product to a hard technical problem—safe context control across providers and agent tools—rather than a commoditized gateway feature list.

## 10. Phased roadmap and measurable acceptance criteria

| Phase | Outcome | Scope | Acceptance criteria |
|---|---|---|---|
| 0: Truth and baseline (2–3 weeks) | Align claims with proof | Workload taxonomy, common benchmark harness, onboarding audit, claim inventory | Every public metric has corpus, version, command, git SHA, comparator, and limitation; no provider cache counted as Cutctx savings |
| 1: Decision Explorer (3–5 weeks) | Make Cutctx explainable | Stable receipt schema, API, dashboard view, redaction/RBAC, CCR links | >95% of proxy decisions emit a parseable receipt; E2E covers compression/cache/routing/retrieval/no-op; a support engineer can explain any sampled decision in <2 minutes |
| 2: Quality loop (4–6 weeks) | Make policies safe to improve | Dataset/replay runner, tool-call validator, policy compare, Langfuse export | A policy cannot graduate without configured quality evidence; tool-use gates are executable; baseline/variant results have confidence/provenance |
| 3: Context contracts (4–6 weeks) | Make setup intuitive | Contract editor, simulation, approval/rollback, rollout controls | One SRE and one coding-agent contract are installable without raw env variables; rollback completes in one action and is audited |
| 4: Enterprise state (6–10 weeks) | Make the control plane operable at scale | Supported shared backend, backup/restore, fleet/governance UX | Multi-replica reference deployment passes fault/recovery tests; backup restore RTO/RPO are documented and tested |

### Smallest high-confidence first milestone

Build **Phase 1, first slice**: persist and render a read-only decision receipt for the existing proxy request trace. It should show:

- original vs. forwarded tokens and source-attributed savings;
- transform list, no-op/abstention reason, and protected anchors;
- cache read/write observation and cache-safe prefix status;
- routing source/target, eligibility, capabilities, confidence, rejected candidates, and transport proof;
- CCR reference, availability/expiry, and retrieval outcome;
- policy/config version and a payload-redaction state.

This uses existing routing, savings, cache, and trace signals; it does not require a new optimizer or a distributed backend. It is the fastest way to turn existing engineering into customer trust.

## 11. Claims and benchmarks to validate before public use

| Claim | Current status | Required validation before marketing |
|---|---|---|
| “Best in class” | Unsupported | Public, versioned head-to-head on representative agent traces with objective outcome metrics and disclosed limits |
| “Same answers” / “without losing accuracy” | Workload-limited | Per-workload quality thresholds, confidence intervals, retrieval-rate and failure analysis; never a universal guarantee |
| Compression percentage | Partially supported | Separate direct compression from provider cache, semantic cache, RTK, and routing; report medians and no-op rate |
| Low proxy overhead | Workload/environment-limited | Reproducible p50/p95/p99 by transform, payload size, platform, concurrency, and warm/cold state |
| Memory superiority | Unsupported as a general claim | Run LoCoMo/LongMemEval and a coding-agent memory benchmark against Mem0/Zep-like baselines; publish methodology |
| Routing savings without quality loss | Incomplete | Shadow/eval evidence per client, task, model pair, capability set, and transport; preserve abstention as success |
| Enterprise-ready / secure | Partially supported | Threat model, penetration test, backup/restore evidence, security controls mapping, and certification status (do not imply SOC 2 without audit) |

## 12. Sources

### Primary external sources (accessed 2026-07-16/17)

- [LiteLLM GitHub repository](https://github.com/BerriAI/litellm)
- [Portkey AI Gateway GitHub repository](https://github.com/Portkey-AI/gateway)
- [Helicone GitHub repository](https://github.com/Helicone/helicone)
- [Cloudflare AI Gateway overview](https://developers.cloudflare.com/ai-gateway/)
- [Cloudflare AI Gateway dynamic routing](https://developers.cloudflare.com/ai-gateway/features/dynamic-routing/)
- [Cloudflare AI Gateway caching](https://developers.cloudflare.com/ai-gateway/features/caching/)
- [Langfuse GitHub repository](https://github.com/langfuse/langfuse)
- [Mem0 GitHub repository](https://github.com/mem0ai/mem0)
- [Zep GitHub repository](https://github.com/getzep/zep)
- [Graphiti GitHub repository](https://github.com/getzep/graphiti)
- [Microsoft LLMLingua GitHub repository](https://github.com/microsoft/LLMLingua)
- [OpenAI prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching)
- [OpenAI compaction guide](https://developers.openai.com/api/docs/guides/compaction)

### Primary repository evidence

- [Repository map](../codemap.md)
- [Current limitations](../docs/content/docs/limitations.mdx)
- [Current benchmarks](../docs/content/docs/benchmarks.mdx)
- [Model-routing presets](../docs/content/docs/model-routing-presets.mdx)
- [Orchestration platform](../docs/content/docs/orchestration-platform.mdx)
- [Model router implementation](../cutctx/proxy/model_router.py)
- [Dashboard routes](../dashboard/src/App.jsx)
- [Unified setup command](../cutctx/cli/setup.py)
- [Product capability matrix (historical; checked against current code where cited)](../artifacts/PRODUCT_CAPABILITY_MATRIX.md)
- [Commercial readiness assessment (historical; checked against current code where cited)](../artifacts/commercial-readiness-audit.md)

## What was not checked

- Paid-plan prices were not normalized into a table because plans, seat definitions, and included usage vary frequently; public pricing/free-tier statements above are only used where the vendor exposed them directly.
- No customer interviews, retention data, sales-win/loss data, or live production workloads were available. Recommendations about buyer impact are reasoned inferences from the inspected product and market evidence.
- No penetration test, full E2E run, or live-provider benchmark was executed in this audit; this is a product/architecture/research review, not a release certification.
