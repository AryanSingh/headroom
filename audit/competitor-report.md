# Cutctx — Competitive Landscape Report

**Date:** July 4, 2026  
**Product:** Cutctx — The context compression layer for AI agents  
**Scope:** All segments (developer tooling, enterprise, hosted API, OSS)

---

## Executive Summary

Cutctx operates in a rapidly bifurcating market. The "context compression" space has exploded in 2026, with YC W26 alone producing 3+ startups (Compresr, Token Co., Codag). Competitors cluster into four tiers:

| Tier | Players | Threat to Cutctx |
|---|---|---|
| **Local-first OSS analogs** | LeanCTX, Clean-CTX, ContextCutter, AgentCTX, CTX | **High** — same thesis, same local-first architecture |
| **Hosted compression APIs** | Compresr, Token Co., Morph Compact, OpenCompress, Eyelid AI, Hypernym | **Medium** — different deployment model but same buyer |
| **Gateway feature absorption** | Helicone (Context Editing), Portkey/Palo Alto, LiteLLM | **High** — if they add native compression, Cutctx's distribution erodes |
| **Narrow CLI wrappers** | RTK (67.5k ★), lean-ctx (3.1k ★) | **Low** — narrower scope, but form the "compression" category in users' minds |

**Key insight:** Cutctx's defensible moat is the combination of (a) **reversible compression (CCR)** — no competitor has this, (b) **5-source savings attribution** — the CFO-grade answer, (c) **multi-format compressor pipeline** — JSON + AST code + logs + diffs + images + prose, (d) **cross-agent memory + cross-provider cache alignment** — unique combination.

---

## 1. Local-First OSS Competitors

### 1.1 RTK (Rust Token Killer) — `github.com/rtk-ai/rtk`

| Dimension | Detail |
|---|---|
| **What it is** | CLI binary + agent hook for deterministic shell output compression |
| **Stars** | ~67.5k (some inflation reported; audit ~63.6k) |
| **Language** | Rust, ~4.1 MB single binary, zero runtime deps |
| **License** | Apache 2.0 |
| **Agent support** | 14 agents (Claude Code, Cursor, Copilot, Gemini CLI, Codex, Windsurf, Cline, OpenCode, etc.) |
| **Compression** | 60-99% on shell commands (git, test runners, grep, find). Deterministic, rule-based (filter/group/truncate/dedup). |
| **Install** | `brew install rtk` / `curl | sh` |
| **Pricing** | Free OSS. RTK Cloud (waitlist) — $15/dev/mo, SSO/audit planned |
| **MCP** | None shipped (third-party bridge only) |
| **SDK** | None (CLI binary only) |
| **Memory** | None — local SQLite analytics only (90-day retention) |
| **Enterprise (SSO/RBAC)** | Not available (planned for cloud) |
| **Windows** | Degraded (CLAUDE.md fallback unless WSL) |

**Structural limitation:** Compresses shell output only. Native agent tools (Read, Grep, Glob) bypass RTK entirely. Does not touch RAG, conversation history, thinking tokens, or model output.

**Relationship to Cutctx:** Cutctx ships RTK's binary for shell-output rewriting and attributes it. Complementary, not competitive — RTK is an input-side member of the stack, Cutctx is the full pipeline.

### 1.2 LeanCTX (yvgude/lean-ctx) — `github.com/yvgude/lean-ctx`

| Dimension | Detail |
|---|---|
| **What it is** | Full "context engineering layer" — compression + routing + memory + verification + RBAC |
| **Stars** | ~3,100 |
| **Language** | Rust (single binary) + TypeScript/Python SDKs |
| **License** | Apache 2.0 (open core; enterprise tier in development) |
| **Agent support** | 30+ agents (Cursor, Claude Code, Codex, Gemini CLI, Windsurf, GitHub Copilot, OpenCode, etc.) |
| **Compression** | 10 read modes (full/map/signatures/diff/lines/density/entropy/task/reference/auto), tree-sitter AST for 27 languages, 95+ shell-output patterns, target-density budget. 60-99%. |
| **MCP** | 81 MCP tools (first-class citizen). Streamable HTTP MCP. |
| **SDK** | Python, TypeScript, Rust |
| **Memory** | CCP (Cross-Context Persistence): task/facts/decisions across chats. Knowledge graph with temporal facts + contradiction detection. Property graph (imports/calls/exports/type_ref). |
| **Enterprise** | RBAC (full role system), audit logs, workspace trust, secret redaction, PathJail, per-person RPM limits, CI drift gates. **PostgreSQL-backed team server.** |
| **Pricing** | OSS free. Enterprise tier in development (no public pricing). |
| **Windows** | Supported (PowerShell install script) |

**This is Cutctx's most direct OSS competitor.** Same thesis (local-first Rust binary, MCP, multi-format compression, cross-agent features), similar token reduction claims. LeanCTX leads on memory (knowledge graph, CCP, property graph), verification (ctx_proof, tamper-evident ledger, signed snapshots), and multi-agent (ctx_agent/ctx_handoff, shared bus). Cutctx leads on reversibility (CCR), CacheAligner multi-provider cache stabilization, 5-source savings attribution, and commercial go-to-market.

**Strategic note:** Cutctx is explicitly listed in LeanCTX's addon registry as a compatible compression engine — they position Cutctx as a backend they can wrap, not as a competitor they need to replace.

---

## 2. Hosted API Competitors

### 2.1 Compresr — `compresr.ai` (YC W26)

| Dimension | Detail |
|---|---|
| **What it is** | Hosted LLM context-compression API. Query-specific relevance compression via GemFilter architecture. |
| **Pricing** | $0.10/1M tokens (input + output metered). $10 free credits. |
| **Compression** | Query-specific. Light ~2× compression (FinanceBench 73→77%). Quality drops ~2pp per doubling past 2×. Latte_v2: 5× faster. |
| **Enterprise** | On-prem/VPC available. No SSO/RBAC documented. Stateless — no logging of content. |
| **Integrations** | LangChain, LangGraph, LlamaIndex, LiteLLM. Open-source "Context Gateway" proxy. |
| **Limitation** | Quality degrades past 2× compression. Not designed for code preservation. |

### 2.2 The Token Company — `thetokencompany.com` (YC W26)

| Dimension | Detail |
|---|---|
| **What it is** | Hosted token-optimization API. Fast ML model (100K tokens <100ms). |
| **Pricing** | Free: 50M tokens/mo. Production: $0.30/1M tokens saved. Deterministic — same input = same output. |
| **Compression** | Aggressiveness 0.0-1.0. Models: bear-2 (accurate), bear-1.2 (fast). 10-37% latency improvement. |
| **Enterprise** | Custom fine-tuning, zero data retention option. No SSO/RBAC documented. |
| **Limitations** | Invite-only. Focused on NL workloads, less specialized for code. |

### 2.3 Morph Compact — `morphllm.com/products/compact`

| Dimension | Detail |
|---|---|
| **What it is** | Line-level deletion compaction (not summarization). Byte-identical output. 33K tok/s. |
| **Pricing** | $0.20 input / $0.50 output per 1M tokens. Free: 200 req/mo. Pro: $68/mo. |
| **Enterprise** | SOC 2 Type II, GDPR, data residency, self-host option. |
| **Compression** | 50-70% typical. Line-level deletion (not paraphrasing). Preserves verbatim code. 1M token context window. |
| **Limitations** | Cannot trim within a single line (minified code, giant JSON). 1M token ceiling. |

**Note:** Morph Compact is the most differentiated hosted competitor — byte-identical output is closest to "reversible" without being reversible. SOC 2 and self-host option make it enterprise-viable.

### 2.4 New Hosted Entrants (2026)

| Competitor | Differentiator |
|---|---|
| **OpenCompress** (opencompress.ai) | All-in-one gateway + compression pipeline. 50-70% cost reduction, ≥0.80 cosine similarity. CompressBench leaderboard. |
| **Eyelid AI** (eyelid.ai) | Deterministic, CPU-only. 17.5× compression, 95.1% HumanEval pass@1. Pitches savings to LLM providers, not just app developers. |
| **Hypernym** (hypernym.ai) | Structural-level context parsing + compression. 2-8× faster coding agent sessions. Cross-session persistence. |
| **gotcontext.ai** | MCP-native compression gateway. Semantic chunking + PageRank importance. Pairs with RTK for 82% joint reduction. |

---

## 3. Enterprise Gateway Competitors

### 3.1 Helicone Context Editing — `helicone.ai`

| Dimension | Detail |
|---|---|
| **What it is** | Open-source AI gateway + LLM observability with 0% markup pass-through billing. Context Editing feature clears old tool uses and thinking blocks when input exceeds threshold. |
| **Compression overlap** | **Closest commercial analog to Cutctx.** Destructive eviction (not compression) — throws away old content entirely. No SmartCrusher/Kompress-base equivalent. |
| **Pricing** | $0 markup + $20/seat/mo. |
| **Enterprise** | SSO, RBAC, audit logs, SOC 2 (claimed). |
| **Cutctx advantage** | Cutctx = compress & keep (reversible CCR). Helicone = evict & forget. Quantifiable quality delta on long sessions. |

**Primary competitive threat in commercial SaaS.** If Helicone adds actual compression (not just eviction), the gap narrows.

### 3.2 Portkey (Palo Alto Networks) — `portkey.ai`

| Dimension | Detail |
|---|---|
| **What it is** | "Control panel for production AI" — routing, fallbacks, caching, observability, guardrails across 1,600+ LLMs. |
| **Compression overlap** | **Minimal** — caching (simple + semantic) and prompt-cache awareness. No inline compression. |
| **Pricing** | Free → $49/mo → Enterprise custom. |
| **Enterprise** | SOC 2 Type II, HIPAA, ISO 27001, SSO, RBAC, audit logs, BAA, VPC. **Most enterprise-mature.** |
| **Threat** | **Feature absorption risk.** Acquired by Palo Alto Networks (2026). If Portkey adds compression as a guardrail hook, Cutctx's distribution story weakens. |

### 3.3 LiteLLM (BerriAI) — `litellm.ai`

| Dimension | Detail |
|---|---|
| **What it is** | Open-source Python proxy + SDK wrapping 100+ LLM providers. Virtual keys, budgets, rate limits, caching, guardrails. |
| **Compression overlap** | **Indirect** — guardrails plugin system could wrap Cutctx. No native compression. |
| **Enterprise** | SSO/SAML, audit logs, spend tracking, multi-team management. |
| **Integration opportunity** | Cutctx is already listed as a LiteLLM-compatible compression callback. This is a distribution channel to prioritize. |

---

## 4. Security & Observability (Adjacent, Not Direct)

| Category | Players | Overlap with Cutctx |
|---|---|---|
| **Security** | Lakera (Check Point), Guardrails AI, NVIDIA NeMo | Screening/blocking, not compression. Complementary. Lakera could absorb compression via acquisition. |
| **Observability** | LangSmith, Langfuse, Weights & Biases, Datadog AI | Tracing/cost dashboards only. No compression. Complementary. |
| **Vector DB** | Chroma, Pinecone, Weaviate, Qdrant | Storage for RAG. No compression. Complementary. |
| **Memory** | Mem0, Zep | Long-term semantic memory. Complementary to Cutctx's cross-agent memory. |

---

## 5. Competitive Positioning Matrix

| Capability | Cutctx | RTK | LeanCTX | Compresr/Token Co. | Morph Compact | Helicone CE |
|---|---|---|---|---|---|---|
| **Local-first** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ (cloud) |
| **Reversible (CCR)** | ✅ | ❌ | ❌ (snapshots ≠ CCR) | ❌ | ❌ | ❌ |
| **Cross-provider caching** | ✅ | ❌ | Partial | ❌ | ❌ | ❌ (Anthropic only) |
| **5-source savings attribution** | ✅ | ❌ | ❌ (single ledger) | ❌ | ❌ | ❌ |
| **JSON compression** | ✅ (SmartCrusher) | ❌ | ✅ (10 modes) | ✅ | ❌ (line-level) | ❌ |
| **AST code compression** | ✅ (CodeCompressor) | ❌ | ✅ (tree-sitter, 27 langs) | ❌ | ❌ | ❌ |
| **Log compression** | ✅ (LogCompressor) | ❌ | ❌ (shell patterns only) | ❌ | ❌ | ❌ |
| **Image compression** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Memory/knowledge graph** | ✅ (cross-agent) | ❌ | ✅✅ (CCP + graph) | ❌ | ❌ | ❌ |
| **Agent wrap (60s setup)** | ✅ (7 agents) | ✅ (14 agents) | ✅ (30+ agents) | ❌ | ❌ | ❌ |
| **MCP server** | ✅ | ❌ | ✅ (81 tools) | ❌ | ❌ | ✅ |
| **Enterprise SSO/RBAC/audit** | ✅ | ❌ (planned) | ✅ (RBAC+audit) | ❌ | ✅ (SOC 2) | ✅ |
| **CI/CD tooling** | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Windows support** | ? | ❌ (degraded) | ✅ | N/A (API) | N/A (API) | N/A (API) |
| **OpenTelemetry export** | ❌ | ❌ (community) | ✅ | ❌ | ❌ | ✅ |

**Defensible advantages for Cutctx:**
1. Reversible compression (CCR) — unique in the market
2. 5-source savings attribution — CFO-grade answer to "did this save money?"
3. Multi-format compressor pipeline — no other vendor covers all content types
4. Cross-agent memory + cross-provider cache alignment — unique combination
5. Local-first + enterprise-grade — air-gap deployable with SSO/RBAC/audit

---

## 6. Market Observations

1. **YC W26 cluster:** 3+ context-compression startups in one batch confirms investor belief in the category. Expect continued competitive pressure.

2. **Feature absorption threat:** As Portkey (Palo Alto), Lakera (Check Point), and Helicone add compression features, Cutctx's standalone value proposition needs to stay ahead on depth.

3. **MCP is becoming table stakes.** Every competitor ships MCP. Cutctx already has MCP but LeanCTX's 81 tools set the bar.

4. **The market is bifurcating:** "Compression" (irreversible, hosted) vs. "Curation / context runtime" (reversible, local). Cutctx sits firmly in the latter, which is the smaller but more defensible niche — for now.

5. **Compliance certifications are the enterprise gate.** Morph Compact's SOC 2, Portkey's HIPAA/ISO, and Baseten's SOC 2 are table stakes Cutctx needs to match for enterprise procurement.

