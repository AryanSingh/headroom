# Cutctx Value Proposition & Messaging

**Date:** June 13, 2026  
**Positioning:** The context, cost, and governance layer for AI agents

---

## One-Liner

**Cutctx reduces agent context cost by 60–95% while giving teams governance and visibility across every provider and tool.**

---

## Headline Options

1. **The context and cost control layer for AI agents**
2. **Govern AI agent context. Cut costs. Keep quality.**
3. **Make every token count — across every provider and tool.**

## Subheadline Options

1. **Reduce agent spend, fit more usable context, and govern AI workflows across providers without sending prompts to another SaaS.**
2. **A local-first proxy that compresses the right payloads, keeps originals retrievable, and gives your team visibility — without changing any code.**
3. **Cross-provider context optimization with reversible compression, team analytics, and enterprise governance.**

---

## Core Positioning Statement

> Cutctx is a **local-first, cross-provider context optimization and governance layer** for AI agents. It sits between your agent workflows and model providers, compresses the right payloads safely, keeps originals retrievable when needed, and gives teams visibility and policy control — all without sending prompts to external SaaS by default.

---

## Five Messaging Pillars

### 1. Reduce Cost Without Changing Workflows
Cutctx compresses tool outputs, logs, RAG results, code search, and conversation history by 60–95% before they reach the LLM. Your agents produce the same answers at a fraction of the token cost. Zero code changes required — just point your proxy at Cutctx.

### 2. Fit More Usable Context
Context windows are finite. Cutctx makes more of your context *usable* by compressing verbose payloads while preserving the information your agent needs. This means fewer context-limit errors, fewer retries, and more reliable agent runs.

### 3. Preserve Privacy With Local-First Deployment
Your prompts never leave your infrastructure by default. Cutctx runs locally, in Docker, or in your Kubernetes cluster. No SaaS hop, no external API calls for compression, no data retention on our servers.

### 4. Reversible Retrieval, Not Blind Lossy Compression
Unlike native provider caching or lossy compressors, Cutctx stores originals locally and provides retrieval markers. When the LLM needs the full payload, it calls `cutctx_retrieve` — and gets the original back. Best of both worlds: cheap context on the wire, full fidelity on demand.

### 5. Team Visibility and Policy Control
See exactly how your team uses AI agents, where tokens go, and what's being compressed. Set policies per team, per project, or per agent class. Export reports for ROI reviews. Enterprise buyers get SSO, RBAC, and audit logs.

---

## Why NOT Just "Prompt Compression"

| Old framing | New framing |
|-------------|-------------|
| "Saves tokens" | "Reduces agent context cost" |
| "Prompt compression" | "Context optimization and governance" |
| "LLM cost reducer" | "Agent infrastructure layer" |
| "Token saver" | "Cross-provider context control" |
| "Generic proxy" | "Agent-aware compression with reversible retrieval" |

**Why:** Native provider caching from OpenAI, Anthropic, and Google has made "prompt compression" a commodity claim. Cutctx's defensible value is cross-provider optimization, agent-specific compatibility, reversible retrieval, and enterprise governance — not raw token savings.

---

## Positioning Against Native Provider Caching

> "Provider-native caching helps inside a single provider. Cutctx works across providers, agent tools, and payload types — and adds observability, retrieval, and team policy control that no provider offers. The two are tracked independently: provider cache and Cutctx compression are separate line items in the buyer report, not netted into a single number."

**Five savings sources, attributed independently:**
1. **Provider prompt cache** — Anthropic `cache_read_input_tokens`, OpenAI `cached_tokens`, Gemini `cachedContentTokenCount`. Observed on the upstream side.
2. **Cutctx compression** — tokens removed by SmartCrusher, LiveZone, CodeCompressor, LogCompressor, etc. Observed on the proxy side.
3. **Semantic cache** — tokens avoided by serving a prior near-duplicate request from the response cache. Cross-provider.
4. **Self-hosted prefix cache** — tokens served by vLLM Automatic Prefix Caching. Reported separately from provider cache.
5. **Model routing** — tokens served by a cheaper model than the user originally requested, plus the resulting dollar savings.

**Attribution invariant:** the total reported savings is the sum of per-source values, never the difference between raw and optimized input. The buyer's CFO sees the marginal value of Cutctx above and beyond their existing provider cache, in dollars, with a reproducible schema. A buyer who already has Anthropic prompt cache enabled sees that cache as the first line item, and Cutctx compression as the second — they are independent, not redundant.

**Key differentiators:**
- Works across Anthropic, OpenAI, Google, Bedrock, Vertex — native caching is provider-locked
- Compresses tool outputs, logs, diffs, code search — not just conversation prefixes
- Reversible retrieval via CCR — native caching is lossy or limited
- Team analytics and policy control — native caching has zero governance
- Local-first deployment — native caching requires trusting the provider

---

## Objection Handling

### "We already use provider-native caching"
> "That's great — native caching works well for prefix caching within a single provider. Cutctx complements it by compressing tool outputs, logs, and cross-provider payloads that native caching doesn't touch. We also add retrieval, governance, and analytics that no provider offers."

### "We don't want to send prompts to another SaaS"
> "Cutctx runs locally by default. Your prompts never leave your infrastructure. We're a local-first proxy, not a cloud service."

### "Our LLM spend isn't that high"
> "Cutctx is most valuable when your agents read large tool outputs, code search results, or logs. Even moderate spend compounds when every agent loop reads thousands of tokens of tool output. We typically see 60–92% reduction on those payloads."

### "We're worried about compression hurting quality"
> "Cutctx uses reversible compression (CCR). The original payloads are stored locally and retrievable on demand. We also run safety guardrails and quality benchmarks. You can start with conservative compression and increase as you validate."

### "We only use one provider"
> "Cutctx still adds value on a single provider: tool output compression, reversible retrieval, team analytics, and governance. And when you inevitably add a second provider, you're already set up."

---

## Proof Points

### Benchmarks
| Workload | Before | After | Savings |
|----------|-------:|------:|--------:|
| Code search (100 results) | 17,765 tokens | 1,408 tokens | **92%** |
| SRE incident debugging | 65,694 tokens | 5,118 tokens | **92%** |
| GitHub issue triage | 54,174 tokens | 14,761 tokens | **73%** |
| Codebase exploration | 78,502 tokens | 41,254 tokens | **47%** |

### Accuracy (no quality loss)
| Benchmark | Baseline | Cutctx | Delta |
|-----------|---------:|---------:|------:|
| GSM8K (math) | 0.870 | 0.870 | **±0.000** |
| TruthfulQA (factual) | 0.530 | 0.560 | **+0.030** |
| SQuAD v2 (QA) | — | **97%** | 19% compression |
| BFCL (tools) | — | **97%** | 32% compression |

### Architecture
- Rust core: sub-millisecond compression, 1000+ tests
- 6 compression algorithms + multimodal support
- Works with Claude Code, Cursor, Codex, Aider, Copilot, and any OpenAI-compatible client
- Apache 2.0 license

---

## Pitch by Audience

### Startup Engineering Team
> "Your AI agents are burning tokens on verbose tool outputs and logs. Cutctx compresses those payloads by 60–95% with zero code changes — just point your proxy at it. Same answers, fraction of the cost. Install in 60 seconds."

### Platform Engineering Team
> "You're building infrastructure for AI agents across multiple providers and teams. Cutctx gives you a single context optimization layer that works across Anthropic, OpenAI, Bedrock, and Vertex — with team analytics, policy presets, and reversible retrieval. No vendor lock-in, runs in your cluster."

### Enterprise Security Buyer
> "Cutctx is a self-hosted proxy that runs in your infrastructure. Prompts never leave your network. We offer SSO/SAML, RBAC, audit logs, and air-gapped deployment. Our telemetry sends only aggregate counts — never message content. We can provide a security review packet for your team."

---

## Homepage Copy Structure

1. **Hero:** "The context and cost control layer for AI agents" + CTA
2. **Proof bar:** 60–95% savings, 6 algorithms, reversible, local-first
3. **Problem:** Agent prompts bloat, native caching isn't enough, tool outputs overwhelm, teams lack governance
4. **Solution:** Proxy, SDK, wrap, dashboard, CCR retrieval, policy control
5. **Why not native caching alone:** Cross-provider, agent-specific, reversible, governance
6. **Use cases:** Coding agents, support/incident agents, internal AI platforms
7. **Security:** Local-first, self-hosted, optional telemetry, no prompt retention
8. **Pricing preview:** Free / Team / Enterprise
9. **CTA:** Start free | Book enterprise demo
