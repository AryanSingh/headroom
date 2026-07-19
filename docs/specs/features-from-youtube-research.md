# Features & Functionalities for Headroom from YouTube Research

**Date:** 2026-07-19
**Sources:** Claude channel (141 videos), AI Engineer channel (880 videos)
**Purpose:** Extract concrete, buildable features from the research

---

## How to Read This

Each feature includes:
- **Source channel(s)** where the idea came from
- **Priority** (P0 = core differentiator, P1 = strong value, P2 = nice-to-have)
- **Dependencies** on other features or existing infra
- **Why it fits CutCtx** — what makes it a natural extension

---

## P0 — Core Differentiators

### 1. Stream Processor Hooks (Lifecycle Events)

**Source:** Claude channel #100 (Hooks in Claude Code), AI Engineer #205 (Event-sourced harness)

**What:** Deterministic hooks at key lifecycle points in CutCtx's pipeline. Pre/post hooks before compression, before LLM send, after response received.

```rust
// Hook points in CutCtx proxy pipeline
before_compress  → decide strategy, skip, or abort
after_compress   → log savings, trigger cutctx learn
before_llm_send  → inject context, block dangerous requests
after_llm_recv   → log response, update metrics
on_error         → circuit breaker, fallback strategy
```

**Why for CutCtx:** This is the stream processor model from the event-sourced harness, realized as a concrete API. Users compose processors at each hook point — the same mental model as Claude Code hooks, but for compression decisions.

**Build on:** CutCtx proxy pipeline (`crates/cutctx-proxy/src/handlers/`, `crates/cutctx-proxy/src/compression/`)

---

### 2. Agent Decomposition Framework (Tool → Skill → Subagent)

**Source:** Claude channel #38 (Tool, skill, or subagent?)

**What:** Three-tier processor abstraction in CutCtx:

| Layer | CutCtx Equivalent | Stateless? | Example |
|-------|-------------------|-----------|---------|
| **Tool** | Single compression strategy | Yes | `json_sampler(strategy: "kneedle")` |
| **Skill** | Composed processor chain | Configurable | `git_context_skill: code_compressor + json_sampler + cache_warm` |
| **Subagent** | Self-contained event-driven processor | No (has state) | `code_review_subagent: parses diff, compresses, runs rules` |

**Why for CutCtx:** Turns one-off compression strategies into a composable, hierarchical system. Users build skills by composing tools, and deploy subagents as stream processor chains. Maps directly to the existing `transforms/` pipeline.

**Build on:** `crates/cutctx-core/src/transforms/` — restructure transforms as implementors of a `StreamProcessor` trait.

---

### 3. Multi-Signal Evaluation Framework

**Source:** Claude channel #95 (Replit eval system), AI Engineer #70 (SWE-Marathon), AI Engineer #110 (Production Evals)

**What:** When CutCtx compresses content, evaluate the result across multiple signals before deciding whether to keep it:

| Signal | Metric | Source |
|--------|--------|--------|
| Quality | Compression faithfulness (auto-eval) | Compare compressed vs original meaning |
| Cost | Tokens saved | Core CutCtx metric |
| Latency | Compression overhead | Must be < round-trip savings |
| Error rate | Did compression break tool calls? | Detect structural changes |
| Token waste | How much was actually used by LLM? | Post-hoc analysis |

The eval system produces a scorecard for every compression decision, and `cutctx learn` uses these scorecards to tune strategies over time.

**Why for CutCtx:** Turns compression from a blind operation into an intelligent, self-correcting system. "Measuring compression quality" is the critical missing piece for enterprise adoption.

**Build on:** `crates/cutctx-core/src/relevance/` — add eval signals to existing relevance scoring.

---

### 4. Smart Context Strategies (Adaptive /compact)

**Source:** Claude channel #79 (Context Management), AI Engineer #216 (How we solved Context Management)

**What:** Replace manual `/compact` vs `/clear` with tiered, adaptive strategies:

| Strategy | When | Behavior |
|----------|------|----------|
| **Rolling window** | Default | Oldest messages dropped (existing) |
| **Smart compact** | High token usage | Intelligent compression via CutCtx pipeline |
| **Selective clear** | Session drift | Drop low-value turns, keep high-value context |
| **Snapshot + resume** | Long sessions | Save compressed state, resume later |

The proxy auto-detects which strategy to apply based on context composition, token rates, and session length.

**Why for CutCtx:** This is CutCtx's current sweet spot. The feature is making it adaptive rather than always-on. Users don't think about compression — CutCtx picks the right strategy automatically.

**Build on:** `crates/cutctx-core/src/cache_control.rs`, existing compression pipeline.

---

## P1 — Strong Value Features

### 5. Memory Consolidation Engine (cutctx learn v2)

**Source:** Claude channel #60 & #41 (Memory and dreaming, Agents that remember), AI Engineer #73 (Continual Learning)

**What:** Cross-session memory that not just stores but consolidates. Between agent sessions, CutCtx runs a "dreaming" cycle:

1. Mine past sessions for failure patterns (current `cutctx learn`)
2. Consolidate repeated patterns into structured memory
3. Verify memory accuracy against real outcomes
4. Surface corrections as configuration updates

Unlike current `cutctx learn` which passively writes `CLAUDE.md` corrections, this actively consolidates across sessions.

**Why for CutCtx:** Natural evolution of `cutctx learn`. The consolidation/dreaming pattern from Claude Managed Agents shows the direction.

**Build on:** `plugins/cutctx-plugin/` + `cutctx learn` infrastructure.

---

### 6. Feature Flags for Compression Behavior

**Source:** AI Engineer #4 (Agents Need Feature Flags), Claude channel #49 (Teaching agents to learn)

**What:** Route different agents through different compression strategies via feature flags:

```
Agent A (customer support)  →  aggressive compression, keep all timestamps
Agent B (code review)       →  AST-preserving compression, no code loss
Agent C (research)          →  light compression, preserve citations
```

| Flag Type | Values |
|-----------|--------|
| Compression level | `off` / `light` / `balanced` / `aggressive` |
| Strategy override | `json_sampler` / `code_ast` / `log_pattern` / `none` |
| Model routing | `fast` / `quality` / `cheapest` |
| Cache policy | `fresh` / `cached` / `no-cache` |

**Why for CutCtx:** Enterprise feature. Different teams/agents need different compression behavior. Flags let teams canary-test compression before rolling out.

**Build on:** Existing compression policy (`crates/cutctx-core/src/compression_policy.rs`).

---

### 7. Agent-to-Agent Receipt Protocol

**Source:** AI Engineer #3 (Agents Need Receipts — Froglet protocol)

**What:** When CutCtx compresses content for an agent, it issues a verifiable receipt: hash of original content, compression strategy used, tokens saved, timestamp. Other agents can verify that content was compressed by CutCtx without decompressing.

```
Agent A compresses a file via CutCtx
  → CutCtx returns CCR pointer + signed receipt
Agent B encounters the same content
  → CutCtx verifies receipt, returns cached result
Agent C needs the original
  → CutCtx uses receipt to retrieve from CCR
```

**Why for CutCtx:** Composability across agents without redundant work. The Froglet protocol at AI Engineer shows this is an emerging standard.

**Build on:** Existing CCR infrastructure (`crates/cutctx-core/src/ccr/`).

---

### 8. Compression Evaluation Dashboard

**Source:** AI Engineer #89 (Your Agent Is Wasting Tokens), Claude channel #95 (Replit evals), AI Engineer #131 (LLM Observability)

**What:** Per-session and per-agent dashboard showing:

| Metric | Description |
|--------|-------------|
| Tokens saved | Total and per-strategy breakdown |
| Compression ratio | Before/after per message |
| Strategy distribution | Which strategies applied, how often |
| Quality signals | Eval scores per compression decision |
| Cost saved | Dollar equivalent at current provider rates |
| Retrieval rate | How often CCR retrieval was called |

Output as CLI/API for integration with external dashboards.

**Why for CutCtx:** Makes the invisible visible. Users don't know how much they're saving without this. Critical for enterprise adoption and ROI justification.

**Build on:** Existing metrics in proxy (`crates/cutctx-proxy/src/observability/`).

---

### 9. Proactive/Routine Compression

**Source:** Claude channel #68 (Proactive agent workflow with Claude Code)

**What:** Scheduled compression tasks that run without user intervention:

- **Session-end compact** — Automatically compress/clean up session context when agent finishes
- **Idle compression** — If agent hasn't sent messages in N minutes, compress pending context
- **Pre-emptive cache warm** — Pre-compress common resources (docs, codebases, API specs) before the agent needs them
- **Scheduled learning** — Nightly `cutctx learn` runs to consolidate cross-session patterns

Scheduled via cron-like configuration in `.cutctx/config.toml`.

**Why for CutCtx:** Moves from reactive compression to proactive infrastructure. "Set it and forget it."

---

### 10. Verifiable Workflow DSL (Trust Layer)

**Source:** Claude channel #43 (Making agentic workflows trustworthy with a custom DSL), AI Engineer #278 (Harness Engineering)

**What:** A bounded, deterministic configuration language for defining how CutCtx processes agent interactions:

```
// .cutctx/workflow.dsl — example
workflow "code-review" {
  on "prompt" {
    detect_tool: "git diff"
    strategy: "code_ast_compress"
    verify: "structural_integrity"   // verify JSON structure preserved
  }

  on "tool_result" {
    if content_size > 10_000 {
      strategy: "smart_crusher"
      sample_rate: 0.15
      preserve: ["errors", "warnings"]
    }
  }

  on "error" {
    action: "log_full"               // never compress errors
    notify: true
  }
}
```

Turing-incomplete by design — no loops, no external calls. Safe to execute. Deterministic output.

**Why for CutCtx:** Enterprise governance. Compliance teams need to know *exactly* what compression is doing. A verifiable DSL makes CutCtx auditable.

**Build on:** Compression policy system, extend to DSL.

---

## P2 — Nice-to-Have (Future)

### 11. Isolated Agent Context VMs

**Source:** Claude channel #96 (Giving coding agents their own computers — Cursor)

**What:** Each agent's context runs in an isolated environment (WASM sandbox or cgroup) to prevent context leakage between agents. CutCtx proxy orchestrates context isolation.

**Why for CutCtx:** Enterprise security requirement. Only relevant for multi-tenant deployments.

---

### 12. Agent Capability Curve Detection

**Source:** Claude channel #54 (The capability curve)

**What:** Auto-detect the LLM provider/model capability curve and adjust compression strategy accordingly. Stronger models handle more aggressive compression; weaker models need lighter compression.

**Why for CutCtx:** Adaptive compression tuned to model capability. Prevents over-compression with weaker models.

---

### 13. Cross-Agent Memory Sharding

**Source:** AI Engineer #288 (Multi-Agent Orchestration Patterns), Claude channel #49 (Teaching agents to learn)

**What:** Shared memory across agents with role-based sharding. Agent A's context influences Agent B only through explicit sharing rules. Useful for agent teams/cohorts.

**Why for CutCtx:** Enterprise teams running swarms need controlled memory sharing. Builds on existing cross-agent memory.

---

### 14. Cost Attribution & Chargeback

**Source:** AI Engineer #1 (Stop Renting Your Cognitive Infrastructure), AI Engineer #136 (Payment Infrastructure)

**What:** Track compression savings per team/project/user and attribute cost. Show "before CutCtx" vs "after CutCtx" cost at the department level.

**Why for CutCtx:** Enterprise sales requirement. Finance teams need to see ROI.

---

### 15. Compliance Export Pipeline

**Source:** AI Engineer #114 (Production AI Playbook at Enterprise Scale), Claude channel #131 (Cowork and Plugins)

**What:** Export compressed session logs in compliance-friendly formats (immutable, signed, timestamped). Support for SOC2, HIPAA, GDPR retention policies.

**Why for CutCtx:** Enterprise procurement requirement. Many buyers can't adopt without audit trails.

---

## Feature Roadmap Overview

| Priority | Feature | Phase | Effort | Dependencies |
|----------|---------|-------|--------|-------------|
| **P0** | Stream Processor Hooks | 1 | Medium | Proxy pipeline |
| **P0** | Agent Decomposition Framework (Tool/Skill/Subagent) | 1 | Medium | Stream Processor Hooks |
| **P0** | Multi-Signal Evaluation Framework | 2 | Large | Stream Processor Hooks, cutctx learn |
| **P0** | Smart Context Strategies | 1 | Small | Existing compression pipeline |
| **P1** | Memory Consolidation Engine (cutctx learn v2) | 2 | Large | Evaluation Framework |
| **P1** | Feature Flags for Compression | 2 | Medium | Compression Policy |
| **P1** | Agent-to-Agent Receipt Protocol | 2 | Medium | CCR |
| **P1** | Compression Evaluation Dashboard | 1 | Medium | Metrics infra |
| **P1** | Proactive/Routine Compression | 2 | Medium | Scheduler infra |
| **P1** | Verifiable Workflow DSL | 3 | Large | Feature Flags, Policies |
| **P2** | Isolated Agent Context VMs | 3 | Large | Sandbox infra |
| **P2** | Agent Capability Curve Detection | 2 | Small | Model routing |
| **P2** | Cross-Agent Memory Sharding | 3 | Medium | Memory Engine |
| **P2** | Cost Attribution & Chargeback | 3 | Medium | Dashboard |
| **P2** | Compliance Export Pipeline | 3 | Medium | Workflow DSL |

---

## Implementation Phases

```
Phase 1 (Now)                          Phase 2 (Next)                     Phase 3 (Future)
──────────────────────────────         ───────────────────────────        ───────────────────────────
 Stream Processor Hooks                 Memory Consolidation Engine        Verifiable Workflow DSL
 Agent Decomposition                    Feature Flags                      Compliance Export Pipeline
 Smart Context Strategies               Agent Receipt Protocol             Isolated Agent VMs
 Eval Dashboard                         Proactive Compression              Memory Sharding
 Multi-Signal Eval Framework            Capability Curve Detection         Cost Attribution/Chargeback
```

## References

- `docs/specs/claude-channel-relevance.md` — Claude channel analysis
- `docs/specs/ai-engineer-channel-relevance.md` — AI Engineer channel analysis
- `docs/specs/event-sourced-agent-harness.md` — Event-sourced harness design
- `docs/content/docs/architecture.mdx` — Current CutCtx architecture
