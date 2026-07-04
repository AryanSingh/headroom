# Skills, MCP, and Context Graphs: Adopting Supabase & Neo4j Patterns

**Date:** 2026-07-04
**Sources:**
- Pedro Rodrigues (Supabase) — "Combine Skills and MCP to Close the Context Gap" (AI Engineer EU 2026)
- Andreas Kollegger & Zaid Zaim (Neo4j) — "Context Graphs for Explainable, Decision-Aware AI Agents" (AI Engineer EU 2026)
**Status:** Analysis & Design
**Author:** Aryan Singh

---

## 1. Executive Summary

Two talks from AI Engineer Europe 2026 address complementary sides of the same problem: **agents have capability but lack structured context to use it reliably.**

- **Supabase** argues the bottleneck isn't capability — it's *context*. MCP tools give agents a steering wheel; Skills give them driving lessons. Together they bridge the "context gap" that causes agents to guess at tool combinations and bypass security rules.
- **Neo4j** argues agents need three layers of memory — knowledge (facts), conversation (state), and reasoning (policies, decisions, precedents) — unified in a graph structure so agents can answer not just "can I?" but *"should I?"*

Together with the Arize analysis (smart truncation + sub-agents), these three talks define the emerging **context engineering stack**:

| Layer | Problem | Source | Cutctx Status |
|---|---|---|---|
| **Session** | Keep what matters in context window | Arize | ✅ IntelligentContext + CCR |
| **Instruction** | Inject right procedural context | Supabase | ⚠️ Partial — no skill awareness |
| **Memory** | Structure persistent knowledge + decisions | Neo4j | ⚠️ Partial — flat memory, no graph |

Cutctx already owns the session layer (compression, CCR, memory). The opportunity is extending into the instruction and memory layers.

---

## 2. Video 1: Supabase — Skills + MCP

### 2.1 Core Thesis

> *"MCP and Skills aren't competitors. They're the two halves of a working agent."*

MCP provides the **interface to systems** (tools, typed schemas, isolated execution). Skills provide the **expert judgment** to use those tools safely (workflows, security rules, procedural knowledge).

### 2.2 Key Findings

**The "context gap":** Agents have capability via MCP tools but lack the procedural knowledge to use them correctly. In Supabase's eval, agents with MCP alone "guessed" at tool combinations and bypassed security. MCP + Skills achieved **100% success** on security-critical Postgres tasks.

**Progressive disclosure:** Skills load lazily — the agent reads only the name and one-line description first. The full body (instructions, references, scripts) loads only when the agent decides it's relevant. Keeps context minimal until needed.

**Three skill design principles:**
1. **Describe intent, not means** — Tell the agent *what* to achieve and *where* to find info, not the exact tool sequence
2. **Embed critical rules in skill.md** — Don't relegate security rules to external references the agent might skip
3. **Eval-driven testing** — Run headless Claude Code with/without skills, measure success rate

**MCP + Skills architecture:**
- A single MCP server can power many skills (different workflows, same tools)
- A single skill might call several MCP servers
- Skills make MCP servers safer (teach agent how to use the tool)
- MCP servers make skills more useful (real tools to act on)

### 2.3 Relevance to Cutctx

**Direct overlap.** Skills manage what context enters the agent. Cutctx manages how much space that context takes. They are complementary — and Cutctx should be the layer that reconciles them.

| Supabase Insight | Cutctx Opportunity |
|---|---|
| Skills load progressively to keep context small | Cutctx should understand skill boundaries: "this is skill front matter (don't compress)" vs "this is tool output (compress aggressively)" |
| Security-critical rules must be in skill.md (not external) | Cutctx already preserves system prompt via CacheAligner. Extend to **skill pinning** — prevent compression of critical instructions. |
| Eval-driven testing measures skill effectiveness | Cutctx Learn could evaluate: "did the skill survive compression? did the agent still follow it?" |
| Skills are context *selection* — deciding what enters | Cutctx is context *optimization* — making what entered smaller. Feedback loop: if Cutctx over-compresses a skill instruction, the agent loses the guidance. |
| MCP tools produce large outputs that crush context | Cutctx already compresses tool outputs (SmartCrusher at 80-95%). Skills + Cutctx = tools produce output, Cutctx compresses it, skills survive intact. |

### 2.4 Adoption Opportunities

**A — Skill-aware compression (`compression_strategy="skill_preserve"`)**
IntelligentContext currently scores all content uniformly by importance. Skills content should be scored higher by default — instructions > tool output > logs. Add metadata tagging so skills content is preserved even at high compression ratios.

**B — `cutctx wrap` with skill discovery**
When `cutctx wrap claude` runs, it could detect installed skills (`~/.claude/skills/`) and auto-configure preservation rules per skill. Agents get skill-aware compression without manual setup.

**C — Skill token budget dashboard**
Add skill-level token tracking to the Cutctx dashboard: "Supabase security skill consumed 1,300 tokens, compressed to 340 (74% savings)." Lets developers optimize skill size.

**D — Cutctx "Skill" for agent tool users**
A Cutctx-specific skill that teaches any agent how to use context compression effectively. Analogous to Supabase's security skill — "how to use Cutctx" as installable guidance. Already partially done via `llms.txt` / `AGENTS.md`, but a formal skill would be discoverable and versioned.

---

## 3. Video 2: Neo4j — Context Graphs

### 3.1 Core Thesis

> *"Context graphs give agents a persistent, structured understanding of knowledge, conversations, and decisions — not just facts, but the 'why' behind every choice."*

Agents need three layers of memory, not two. Knowledge (entities) + Conversation (state) is not enough. They also need **Reasoning Memory** — decision traces, policies, rules, precedents — stored as a graph so relationships are explicit and queryable.

### 3.2 Key Concepts

**Three-layer memory model:**

| Layer | What It Stores | How Agents Use It |
|---|---|---|
| Long-term | Organizations, people, entities, facts | Standard RAG — "who are the stakeholders?" |
| Short-term | Conversation state, session history | "What were we just discussing?" |
| Reasoning | Policies, rules, decision traces, precedents | "Has this been decided before? What policy applies?" |

**Decision framework:** Propose → Analyze (risk-value) → Decide → Record → Learn

- **Propose**: Agent generates candidate action
- **Analyze**: Risk-value analysis, reference class validation, reversibility check, cost of being wrong
- **Decide**: Commit or escalate
- **Record**: Decision trace stored as graph node (situation, rationale, action, outcome)
- **Learn**: Future queries traverse precedents

**GraphRAG vs Vector RAG:**
- Vector RAG: Semantic similarity search — finds "similar enough" chunks
- GraphRAG: Relationship traversal — follows explicit links between entities, decisions, policies
- Results are explainable: "I chose X because precedent Y applied policy Z"

**Governance:** Full delegation chains tie every agent action back to the originating human. Same graph structure that stores decisions also stores who authorized what.

### 3.3 Relevance to Cutctx

**High relevance.** Cutctx already has a hierarchical memory system with six categories including `DECISION`. But memory is stored flat (SQLite rows with vector embeddings) — not as a connected graph.

| Neo4j Insight | Cutctx Status | Opportunity |
|---|---|---|
| Three-layer memory | ✅ Short-term (session) + Long-term (user/agent) exist | Reasoning memory exists as `DECISION` category but is flat, not graph-connected |
| Decision traces linked to policies & precedents | ❌ Not supported | Decisions stored as isolated rows. No relationship between a decision, the policy it followed, and the outcome. |
| Policies as graph nodes (auditable, updateable) | ❌ Policies are in system prompt text | A policy store with graph relationships would make policies governable outside the prompt. |
| GraphRAG retrieval (traversal vs similarity) | ⚠️ FTS5 + vector search exist | No graph traversal retrieval. Adding Cypher queries or a lightweight graph layer enables relationship-aware search. |
| Causal chains (what caused what) | ❌ Not supported | No way to answer "what decision led to this outcome?" |
| Explainability via explicit relationships | ⚠️ Memory injection shows *what* was found | Cannot show *why* it's relevant (no relationship path) |

### 3.4 Adoption Opportunities

**A — Reasoning memory layer**
Add a formal third memory tier alongside short-term (session) and long-term (user/agent). Reasoning memory stores:
- Decision traces (situation, rationale, action, outcome)
- Policies and rules
- Precedents and exceptions
- Escalation records

Each is a typed node with explicit relationships to entities, conversations, and other decisions.

**B — Graph-backed memory retrieval**
Add a graph traversal retrieval strategy alongside existing vector + FTS5. When a query involves decisions/policies, traverse relationships rather than searching by similarity. Returns not just "relevant memories" but *"relevant through this path"* — enabling explainability.

**C — Decision trace recording**
Instrument the Cutctx proxy to optionally capture decision traces when the agent makes consequential choices. Stored as structured graph nodes. Future queries can traverse them as precedents.

**D — Policy-as-graph**
Instead of encoding policies in system prompt only, store them as graph nodes. Policies can then be:
- Queried by agents ("what policy applies here?")
- Updated independently of agent sessions
- Traced for audit ("which decisions used this policy version?")
- Compared for contradictions

**E — Cross-agent shared context graph**
Extend the existing cross-agent memory to include graph relationships. When Claude stores a decision and Codex queries it, Codex sees not just the decision text but its relationship to entities, policies, and outcomes.

---

## 4. The Unified Picture: Three Talks, One Stack

Together these three talks define the **context engineering stack** for production AI agents:

```
┌──────────────────────────────────────────────────┐
│                  AGENT LAYER                      │
│   (Claude Code, Cursor, Codex, custom agents)     │
├──────────────────────────────────────────────────┤
│                                                   │
│  1. INSTRUCTION LAYER  ← Supabase (Skills + MCP)  │
│     What context should the agent load?           │
│     → Skills, progressive disclosure              │
│     → Cutctx: skill-aware compression             │
│                                                   │
│  2. SESSION LAYER      ← Arize (Sub-agents)       │
│     How does context fit in the window?           │
│     → Smart truncation, CCR, sub-agent bridge     │
│     → Cutctx: IntelligentContext, compression      │
│                                                   │
│  3. MEMORY LAYER       ← Neo4j (Context Graphs)   │
│     What persists across sessions?                │
│     → Graph-structured knowledge + decisions      │
│     → Cutctx: reasoning memory, graph retrieval   │
│                                                   │
├──────────────────────────────────────────────────┤
│               CUTCTX CONTROL PLANE                │
│   (compression · governance · memory · retrieval) │
└──────────────────────────────────────────────────┘
```

Cutctx already operates across all three layers:
- **Instruction** — CacheAligner preserves system prompt and skill instructions
- **Session** — IntelligentContext, CCR, compression pipeline
- **Memory** — Cross-agent memory, hierarchical scoping, semantic retrieval

The gaps identified in this document represent the next logical extensions.

---

## 5. Validation Plan

### Phase 1: Skill-aware Compression (2 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| S1 | Analyze skill file patterns (`.md` front matter + body structure) | Characterize 5 real-world skills for metadata patterns |
| S2 | Add `skill_preserve` compression strategy: tag skill content as high-importance | Skills content survives compression at 90%+ ratio |
| S3 | Build dashboard metric: tokens by content category (skill vs tool vs conversation) | Dashboard shows per-category breakdown |
| S4 | Test: compress a session with and without skill awareness; verify skill instructions intact | Diff shows skill content preserved in `skill_preserve` mode |

### Phase 2: Decision Trace Prototype (2-3 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| D1 | Design reasoning memory data model (decision nodes, policy nodes, relationship types) | Schema reviewed and approved |
| D2 | Implement decision trace storage: capture (situation, rationale, action, outcome) | Traces stored as structured graph nodes |
| D3 | Implement graph traversal retrieval: "find related decisions via policy X" | Lightweight graph query returns correct results |
| D4 | Integrate with existing memory injection | Decisions from past sessions surface in current context |

### Phase 3: Integration & Eval (2 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| E1 | Write Cutctx agent skill (`~/.claude/skills/cutctx/`) | Agent can discover and use Cutctx guidance |
| E2 | Build `cutctx eval skill` — test whether skill instructions survive compression | Command reports: instructions preserved? quality score? |
| E3 | Add `cutctx wrap --detect-skills` — auto-configure per detected skills | Wrap command finds and registers installed skills |

### Validation Success Gates

| Gate | Entry Criteria | Go/No-Go |
|---|---|---|
| **S1-S4** | Skills content preserved at 90%+ compression; dashboard shows categories | ✅ Phase 2 can start |
| **D1-D4** | Decision traces stored and retrievable via graph traversal | ✅ Phase 3 can start |
| **E1-E3** | Cutctx skill discovered by Claude Code; eval catches a known failure | ✅ Feature complete |

---

## 6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Skill-aware compression adds complexity | Medium | Low | Opt-in strategy; existing behavior is default |
| Graph storage increases memory footprint | Medium | Medium | Graph is lightweight (nodes + edges); SQLite-backed; configurable retention |
| Decision trace capture is noisy | High | Medium | Agent explicitly calls `record_decision`; no automatic capture |
| Cross-agent graph sharing introduces consistency issues | Low | Medium | Per-agent provenance tracking already exists; extends to graph nodes |
| Policies stored as graph may drift from prompt | Low | High | Policy graph is source of truth; prompt generated from it, not separate |

---

## 7. Success Metrics

| Metric | Current Baseline | Target |
|---|---|---|
| Skills content survival at 90% compression | Not measured | 100% critical instructions intact |
| Decision trace recall | Not measured | >80% of past decisions found when relevant |
| Graph traversal latency | N/A | <50ms for depth-3 traversal |
| Cross-agent decision sharing | None | Shared decisions improve agent accuracy by >10% |
| Cutctx skill adoption | N/A | >100 installs in first month |

---

## 8. Recommendation

**Phase order:** Skill-aware compression first (quick win, low risk), then decision trace prototype (highest differentiation), then integration and eval tooling.

Skill-aware compression is the smallest code change and immediately useful — every Cutctx user who also uses Agent Skills benefits automatically. The decision trace / context graph layer is the highest-effort but highest-differentiation feature — it moves Cutctx from "compression tool" to "context control plane" with persistent, structured reasoning memory.

---

## 9. References

- Talk: "Combine Skills and MCP to Close the Context Gap" — Pedro Rodrigues, Supabase (AI Engineer EU 2026)
- Talk: "Context Graphs for Explainable, Decision-Aware AI Agents" — Andreas Kollegger & Zaid Zaim, Neo4j (AI Engineer EU 2026)
- Supabase Agent Skills: https://github.com/supabase/supabase-agent-skills
- Neo4j Agent Memory: https://neo4j.com/labs/agent-memory/
- Cutctx sub-agent adoption analysis: `docs/superpowers/specs/2026-07-04-subagent-context-management-adoption.md`
- Cutctx multi-agent state spec: `docs/specs/multi-agent-state.md`
- Cutctx memory system docs: `docs/content/docs/memory.mdx`
