# MCP = Mega Context Problem: Adopting the Cloudflare Code Mode Pattern

**Date:** 2026-07-04
**Source:** Matt Carey (Cloudflare) — "MCP = Mega Context Problem" / "Every API Is a Tool for Agents" (AI Engineer EU 2026 / MCP Dev Summit NA 2026)
**Status:** Analysis & Design
**Author:** Aryan Singh

---

## 1. Executive Summary

Matt Carey (Cloudflare, MCP TypeScript SDK maintainer) delivered the most directly relevant talk of the conference from Cutctx's perspective. His central thesis:

> *"The context limit is not an MCP problem. It's an agent problem. Tools should be discovered on demand."*

Cloudflare's OpenAPI spec is 2.3 million tokens. Converting it to MCP tools naively produces 1.1 million tokens — more than any model's context window. Carey's solution: **skip the tool list entirely** and give the agent a single `code` tool with a typed SDK, executed in a V8 isolate sandbox.

This is Cutctx's exact problem space — context window overflow — from the API/tool perspective instead of the conversation perspective.

---

## 2. Core Thesis

### The 2.3 Million Token Problem

Cloudflare's REST API covers 2,600+ endpoints across 16 product areas. The OpenAPI spec is **2.3 million tokens**. Naive conversion to MCP tool definitions = **1.1 million tokens**. No current model fits this in context.

The obvious fix (split into 16 MCP servers) reduces per-server context but forces users to manually select the right server, and coverage is still incomplete — "six tools for a product suite that had 30 endpoints."

### Three Approaches to Progressive Tool Discovery

| Approach | How It Works | Context Cost | Trade-off |
|---|---|---|---|
| **CLI** | Agent calls `wrangler --help`, reads command tree, drills in | Low (on demand) | Requires shell access on user machine |
| **Tool Search** | Keyword match (Claude Code style), loads ~8 tools matching query | ~1,600 tokens per used tool | Still loads unused descriptions; coverage-dependent on search quality |
| **Code Mode** | Generate typed TypeScript SDK from spec. Give agent single `code` tool. Agent writes against types. | **~300 tokens for 2,600 endpoints** | Requires sandbox execution; agent must be able to write code |

### How Code Mode Works

```
Traditional:
  MCP Server ──► 2,600 tool definitions ──► context (1.1M tokens)

Code Mode:
  MCP Server ──► 1 "code" tool + typed SDK ──► context (~300 tokens)
                      │
                      ▼
              Agent writes TypeScript
                      │
                      ▼
              V8 isolate sandbox (dynamic Worker)
              - No process.env
              - No network by default
              - Programmable per-domain egress
              - Granular read/write controls per endpoint
```

### The Sandbox: Dynamic Workers

The critical enabler: **isolated execution**. Each agent-generated code snippet runs in a fresh V8 isolate:
- `process.env` is empty by default
- Network blocked unless explicitly enabled
- Per-endpoint read/write permissions
- No filesystem access
- Capped execution time

This makes running LLM-generated code against live infrastructure safe — the agent writes code, but the sandbox enforces what it can do.

### Future Vision

Carey predicts MCP will become **a one-flag toggle in every full-stack framework**:
```typescript
// next.config.ts
export default { mcp: true }
// → Every API endpoint automatically exposed as MCP tool
//   backed by programmatic code execution
```

The MCP SDK will thin to the point where it's bundleable in any runtime. Stateless, resumable connections become default.

---

## 3. Relevance to Cutctx

**This is the most directly relevant talk of the four.** It's about the same problem from the tool-description angle.

### Direct Mapping

| Cloudflare Insight | Cutctx Relevance |
|---|---|
| 2.3M token OpenAPI spec → 1.1M token tools | **This is why Cutctx exists.** Tool descriptions consume massive context before the agent even starts working. |
| Code mode: one tool replaces hundreds | **The ultimate compression.** Instead of optimizing how tool descriptions fit in context, eliminate them entirely. Give the agent a language. |
| Progressive discovery: load tools on demand | Cutctx could support this in the proxy: intercept tool lists, load only what's needed, compress the rest to stubs. |
| Tool descriptions still consume context when unused | Cutctx's Schema Compressor already strips ~40% from tool defs (32 redundant metadata keys). But Carey shows that even compressed, 2,600 tools overwhelm context. |
| V8 isolate sandbox for agent-written code | Relevant for sub-agent bridge (Arize pattern): how do you safely execute agent-written code in sub-agents? |

### What This Means for Cutctx

The talks so far have been about compressing *conversation* context (Arize), *instruction* context (Supabase), and *memory* context (Neo4j). Carey's talk is about compressing **tool description** context — which is often the dominant consumer:

```
Typical agent context breakdown:
┌────────────────────────────────────┐
│  System prompt + skills     ~2K    │
│  Tool descriptions          ~50K   │ ← Carey's problem space
│  Conversation history       ~10K   │
│  Tool outputs               ~30K   │ ← Cutctx compresses this today
│  RAG / file contents        ~20K   │
└────────────────────────────────────┘
```

Cutctx's Schema Compressor is the relevant existing feature, but Carey shows that even after compression, the volume is prohibitive at scale. The real fix is **progressive disclosure of tool descriptions** — which Cutctx could enable in the proxy layer.

---

## 4. Adoption Opportunities

### A — Schema Compressor: Code Mode Detection (Quick Win, ~1 week)

The Schema Compressor currently strips redundant metadata from tool definitions (~40% savings). It could detect when an agent is operating in "code mode" (one `code`/`execute` tool + typed SDK) vs "tool enumeration mode" (many individual tool definitions).

In code mode:
- Tool descriptions are nearly irrelevant — the agent works against SDK types, not tool descriptions
- Schema Compressor can reduce tool definitions to bare stubs: tool name + "see SDK"
- Estimated savings: 40% → **95%+** in code mode

### B — Progressive Tool Loading via Proxy (Medium, ~2-3 weeks)

The Cutctx proxy currently compresses content that's *already in context*. It could also manage *what enters context* by intercepting tool list negotiations:

```
Agent → MCP Server: list_tools
                    │
                    ▼
              Cutctx Proxy
              1. Load first N tool descriptions (N=10)
              2. Detect which tools agent actually calls
              3. Load remaining on demand
              4. Compress idle tool descriptions to stubs
                    │
                    ▼
              Cutctx compression
              (already done for tool outputs)
```

**Implementation sketch:**
- Add `progressive_tool_loading` option to proxy config
- On `list_tools` response, truncate to first N tools, mark as "stub"
- On tool call to a stubbed tool, load its full description, cache it
- Compress idle stubs to minimal format: `{name, description: "See SDK"}`
- Estimated savings for large MCP servers: **60-90% context reduction in tool descriptions**

### C — Tool Description Benchmark (Sales/Marketing, ~1 day)

Matt Carey's 1.1M token number is a powerful benchmark. Cutctx should measure and publish:

> "Cloudflare's 2,600-endpoint OpenAPI spec → 1.1M tokens as MCP tools. Cutctx compresses this to X tokens."

Run the Cloudflare OpenAPI spec through:
1. Schema Compressor alone
2. Schema Compressor + IntelligentContext
3. Full pipeline (ContentRouter + all compressors)
4. Progressive tool loading (ideal case)

Numbers like "1.1M → 45K" would be the most compelling Cutctx sales data yet — it addresses every organization with a large API surface.

### D — Tool Description Stub Mode (Small, ~3 days)

A simpler version of progressive loading: don't intercept `list_tools`. Instead, provide a configurable `tool_description_stub` option that replaces verbose tool descriptions with minimal stubs:

```python
# Before (verbose):
tool = {
    "name": "list_workers",
    "description": "Lists all Workers in a Cloudflare account... (200 words)",
    "inputSchema": { ... }  # 500 tokens of JSON Schema
}

# After (stub):
tool = {
    "name": "list_workers",
    "description": "See SDK docs",
    "inputSchema": {}
}
```

The agent gets the tool name (so it knows what exists) but not the full description. If it actually needs a tool, it calls it and the real description/schema loads on demand. This is the simplest version of progressive discovery — Cutctx just compresses what the MCP server already sent.

### E — Code Generation as Compression Strategy (Architectural, Long-term)

Carey's deepest insight: **code is the most compact representation of an API**. TypeScript SDK types compress to far fewer tokens than tool descriptions.

Cutctx could adopt a similar pattern:
- Auto-generate typed stubs from OpenAPI/Protobuf specs
- Replace 2,600 tool definitions with a generated TypeScript SDK snippet (~300 tokens)
- The agent writes code against the types
- Execution goes through the existing proxy (compression still applies to results)

This is a larger architectural shift but represents the ultimate compression strategy for tool-heavy workloads.

---

## 5. Where This Fits: The Unified Stack (4 Talks)

```
┌──────────────────────────────────────────────────────┐
│                   AGENT LAYER                         │
├──────────────────────────────────────────────────────┤
│                                                       │
│  1. INSTRUCTION  ← Supabase (Skills + MCP)            │
│     What context to load                              │
│     → Skill-aware compression                         │
│                                                       │
│  2. TOOL          ← Cloudflare (Code Mode)            │
│     How tool descriptions fit                         │
│     → Progressive loading, stub mode, code gen        │
│                                                       │
│  3. SESSION       ← Arize (Sub-agents)                │
│     How session context fits in window                │
│     → IntelligentContext, CCR, sub-agent bridge        │
│                                                       │
│  4. MEMORY        ← Neo4j (Context Graphs)            │
│     What persists across sessions                     │
│     → Reasoning memory, graph retrieval               │
│                                                       │
├──────────────────────────────────────────────────────┤
│                CUTCTX CONTROL PLANE                    │
│   (compression · governance · memory · retrieval)      │
└──────────────────────────────────────────────────────┘
```

Each talk addresses a different *source* of context pressure. Cutctx already handles session (3) and has primitives for memory (4). Supabase (1) and Cloudflare (2) represent the clearest extension opportunities.

---

## 6. Validation Plan

### Phase 1: Quick Wins (1-2 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| V1 | Download Cloudflare OpenAPI spec; run through full Cutctx pipeline | Measure compression ratio: "1.1M tools → X tokens" |
| V2 | Implement `tool_description_stub` mode | Configurable; reduces tool descriptions by 90%+ |
| V3 | Add code mode detection to Schema Compressor | Detects single-tool-pattern vs multi-tool; adjusts compression |
| V4 | Publish benchmark: "Cutctx compresses Cloudflare's 2,600-endpoint API from 1.1M → X tokens" | Benchmark data available for sales/marketing |

### Phase 2: Progressive Tool Loading (2-3 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| P1 | Design proxy interception for `list_tools` negotiation | Handles streaming and non-streaming responses |
| P2 | Implement truncated tool list (first N tools) | Configurable N; remaining tools load on demand |
| P3 | Implement idle tool stub compression | Tools not called in last N turns compressed to minimal stubs |
| P4 | Test with Cloudflare MCP server (or equivalent large MCP) | End-to-end: agent discovers 2,600 tools, uses 5, context stays under budget |

### Phase 3: Code Mode Exploration (Future)

| Step | Action | Success Criteria |
|---|---|---|
| C1 | Research code generation from OpenAPI specs | Prototype: types → ~300 token SDK snippet |
| C2 | Evaluate sandbox execution options (V8 isolates, Deno, Pyodide) | Security analysis: is agent-generated code safe? |
| C3 | Design proxy integration for code mode | Agent writes code → proxy routes to sandbox → results compressed |

### Success Gates

| Gate | Entry Criteria | Go/No-Go |
|---|---|---|
| **V1-V4** | Benchmark published; stub mode working | ✅ Phase 2 |
| **P1-P4** | End-to-end test with large MCP server passes | ✅ Phase 3 exploration |
| **C1-C3** | Prototype working; security confidence | ✅ Production design |

---

## 7. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Tool stub mode breaks agents that rely on full descriptions | Medium | Medium | Stub mode is opt-in; default behavior unchanged |
| Progressive loading adds latency on first tool call | Medium | Low | Only affects first call to a new tool; subsequent calls cached |
| Cloudflare's code mode depends on sandbox infra we don't have | High | Medium | We adopt the *pattern* (code gen + progressive loading) not the sandbox. Cutctx doesn't need to be a code sandbox. |
| Tool description compression breaks Schema Compressor assumptions | Low | Low | Schema Compressor works on JSON structure; stubs are simpler, not more complex |

---

## 8. Success Metrics

| Metric | Current Baseline | Target |
|---|---|---|
| Tool description compression rate | ~40% (Schema Compressor alone) | 90%+ with stub mode; 95%+ with progressive loading |
| Benchmarked against 1.1M token spec | Not measured | Published number ≤100K tokens |
| Progressive loading latency overhead | N/A | <100ms on first tool call; 0 on subsequent |
| Code mode detection accuracy | N/A | >95% accuracy distinguishing code mode vs enumeration |

---

## 9. Recommendation

**Build in order: V1→V4, then P1→P4.**

The quick wins (benchmark, stub mode, code mode detection) are low-effort, high-visibility — they produce the most compelling sales data Cutctx would have.

The progressive tool loading (Phase 2) is the highest-impact feature for large MCP servers. It changes Cutctx from "compresses what's in context" to "manages what enters context" — a meaningful product expansion.

Code mode exploration (Phase 3) is directional but not urgent. The sandbox requirement is outside Cutctx's core competence. Adopt the *pattern* without building a sandbox.

---

## 10. References

- Talk: "MCP = Mega Context Problem / Every API Is a Tool for Agents" — Matt Carey, Cloudflare (AI Engineer EU 2026 / MCP Dev Summit NA 2026)
- Cloudflare MCP servers: https://github.com/cloudflare/mcp-server-cloudflare
- MCP TypeScript SDK: https://github.com/modelcontextprotocol/typescript-sdk
- Cutctx Schema Compressor: `cutctx/transforms/schema_compressor.py`
- Cutctx sub-agent adoption analysis: `docs/superpowers/specs/2026-07-04-subagent-context-management-adoption.md`
- Cutctx skills/MCP/context-graphs analysis: `docs/superpowers/specs/2026-07-04-skills-mcp-context-graphs-adoption.md`
