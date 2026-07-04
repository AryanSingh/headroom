# Decision Traces, Not Just Documents: Adopting the Neo4j Context Graph Pattern

**Date:** 2026-07-04
**Source:** Zach Blumenfeld (Neo4j) — "Why your agents need decision traces, not just documents" (AI Engineer EU 2026)
**Status:** Analysis & Design
**Author:** Aryan Singh

---

## 1. Executive Summary

Zach Blumenfeld (Neo4j) makes a crisp, practical argument: **RAG answers "what" questions. Context graphs answer "why" and "what now."** A standard knowledge base returns documents about policies and entities. A context graph returns *decision traces* — structured records of past decisions, their causal chains, their precedents, and their outcomes — enabling agents to make explainable, auditable decisions grounded in institutional history.

This is a companion talk to the earlier Neo4j analysis (Kollegger & Zaim) but narrower and more implementation-focused. Where Kollegger & Zaim described the *architecture* of three-layer memory, Blumenfeld provides the *data structure* (Situation, Rationale, Action, Outcome) and the *tooling* (`create-context-graph`, hybrid graph embeddings, graph evals).

For Cutctx, this is the most immediately implementable Neo4j insight. The DECISION memory category already exists — it just needs structured trace format, relationship linking, and graph-aware retrieval.

---

## 2. Core Thesis

> *"A knowledge base tells you what the rules are. A context graph tells you what the organization has actually done under those rules, and why, and what happened next."*

### RAG vs Context Graphs

| Capability | Standard RAG | Context Graph |
|---|---|---|
| Answers "what" | ✅ "What is the policy?" | ✅ |
| Answers "why" | ❌ "Why was this rejected?" | ✅ Traces causal chains |
| Answers "what now" | ❌ "What should we do?" | ✅ Surfaces relevant precedents |
| Explainability | "Because the document says so" | "Because precedent X used policy Y under conditions matching situation Z" |
| Audit trail | ❌ Flat documents | ✅ Graph-structured causal chains |
| Learning over time | ❌ Static documents | ✅ Growing graph of decisions |

### The Financial Analyst Agent Demo

Blumenfeld's demo is the most concrete illustration of context graphs in action:

```
User: "Approve credit limit increase for customer #12345?"

Agent flow:
1. Retrieve customer profile (entities, transactions)
2. Pull historical decision traces for this customer
3. Hybrid search for precedents:
   - Semantic: "credit limit increase" → vector similarity
   - Structural: find decisions with similar relationship topology
4. Evaluate against policies and precedents
5. Return: "Reject. Reason: fraud flag on transaction #7890
   matches precedent decision #452 (rejected for same pattern).
   Escalation recommended to risk team."

Why this matters: The agent doesn't just retrieve facts.
It navigates a reasoning path: entity → decision → precedent → policy → outcome.
Each step is traceable, auditable, and grounded in organizational history.
```

### The Decision Trace Data Structure

The core primitive is a structured trace:

```
Node: Decision
├── situation  → "Customer #12345 requested credit limit increase from $5K to $15K"
├── rationale  → "Customer has clean history for 3 years, but recent transaction #7890 has fraud flags matching pattern from precedent #452"
├── action     → "Reject. Escalate to risk team."
└── outcome    → "Escalation confirmed by risk team. Account flagged for review."

Edges (relationships to other nodes):
──► CUSTOMER (#12345)
──► PRECEDENT (#452 — fraud rejection)
──► POLICY (credit_limit_policy_v3)
──► ARTIFACT (transaction #7890)
──► DECISION_OUTCOME (account review initiated)
```

This structure enables **causal chain traversal**: "Show me all decisions that used this policy and resulted in escalation." No flat document structure can answer that query.

### Hybrid Search: Semantic + Graph Embeddings

The key technical advance: **graph embeddings** for structural similarity.

- **Text embeddings** (sentence-transformers): "fraud rejection" matches "fraudulent transaction denial" — semantic similarity
- **Graph embeddings** (FastRP, Node2Vec): two decisions are similar because they share the same *relationship topology* — same entity types linked by same edge types, even if the text content differs

Blumenfeld's agent uses **both** simultaneously. An agent querying for precedents gets signals from both dimensions:
- "This decision used the same policy as yours" (structural)
- "This decision involved a fraud scenario" (semantic)

This is meaningfully different from vector-only search. Two decisions can use completely different language but follow the same reasoning path through the same organizational structure — and graph embeddings will surface them.

### The Tooling: `create-context-graph`

Blumenfeld introduced `uvx create-context-graph`, a scaffolding CLI that generates a full-stack context graph application in one command:
- Neo4j graph backend
- Frontend (Next.js)
- 22 prebuilt domain ontologies (financial services, healthcare, support, etc.)
- Data connectors for GitHub, Notion, Jira, Slack
- Integrated with Pydantic AI, LangGraph, CrewAI, Google ADK
- Entity extraction pipeline: spaCy → GLiNER → LLM fallback

This dramatically lowers the barrier to experimenting with context graphs — from "months of design" to "one command."

### Graph Evals

A separate but related concept: storing every agent step (actions, states, tool calls, reasoning hops, failure points) as a knowledge graph. This enables:
- **Structural failure analysis**: "Agents that follow reasoning path X → Y → Z fail 40% more often"
- **Loop detection**: "The agent revisits the same entity 3+ times — it's stuck"
- **Policy refinement**: "80% of escalations at this step involve missing data field A"

This is a *testing* application of the same graph technology — using decision traces to evaluate agent quality.

---

## 3. Relationship to Earlier Neo4j Analysis

The Kollegger & Zaim talk (already analyzed in `docs/superpowers/specs/2026-07-04-skills-mcp-context-graphs-adoption.md`) was architectural: the three-layer memory model, the decision framework, the "why" of context graphs.

Blumenfeld's talk is **implementation-focused**:

| Dimension | Kollegger & Zaim | Blumenfeld |
|---|---|---|
| Focus | Architecture | Implementation |
| Core concept | Three memory layers | Decision trace data structure |
| Novelty | "Agents need reasoning memory" | "Here's the 4-field trace format + hybrid search" |
| Tooling | Theoretical | `create-context-graph`, Neo4j Agent Memory package |
| Evaluation | Mentioned as future work | Graph evals — concrete technique |
| Threat model | Not discussed | Poisoned traces as attack vector |

They're complementary — K&Z provide the "why," Blumenfeld provides the "how."

---

## 4. Relevance to Cutctx

**High relevance — and more immediately actionable than the earlier Neo4j analysis.**

Cutctx already has a `DECISION` memory category (one of six categories alongside PREFERENCE, FACT, CONTEXT, ENTITY, INSIGHT). But decisions are stored as flat text rows with vector embeddings — no structured trace fields, no relationship linking, no graph traversal retrieval.

### Gap Analysis

| Blumenfeld Feature | Cutctx Status | Gap |
|---|---|---|
| Decision trace as structured record (S/R/A/O) | ⚠️ DECISION category exists but is free-text | No structured fields for situation, rationale, action, outcome |
| Decision → Entity relationships | ❌ Not stored | Decisions exist in isolation; no links to customer, policy, precedent nodes |
| Decision → Precedent links | ❌ Not stored | No "this decision was informed by that decision" edges |
| Causal chain traversal | ❌ Not supported | Cannot answer "what decisions led to this outcome?" |
| Hybrid search (semantic + graph embeddings) | ⚠️ Vector + FTS5 exist | No graph embedding-based retrieval for structural similarity |
| Graph evals | ❌ Not supported | Cutctx Learn mines text-based failure patterns, but cannot query structural failure paths |
| Poisoned trace detection | ❌ Not considered | No mechanism to detect or prevent injected traces from becoming precedents |

### What Cutctx Already Has That Maps

| Cutctx Feature | How It Maps |
|---|---|
| `DECISION` memory category | Natural home for decision traces |
| Cross-agent memory sharing | Decision traces from Claude are visible to Codex (but flat, not graph) |
| Hierarchical scoping (USER → SESSION → AGENT → TURN) | Decision provenance — who decided what, in which session? |
| Memory injection (semantic search → context) | Can inject *related decisions* today; cannot inject *causal chains* |
| `cutctx_retrieve` tool | Agent can retrieve full decision text, but not traverse relationships |
| Cutctx Learn (failure mining) | Could be extended to do graph evals — analyzing structural failure paths |

---

## 5. Adoption Opportunities

### A — Structured Decision Trace Format (Quick Win, ~1 week)

Extend the existing `DECISION` memory category with structured fields:

```python
# Current (flat text):
Memory(content="Rejected credit limit increase for customer #12345", category="DECISION")

# Proposed (structured trace):
Memory(
    category="DECISION",
    trace=DecisionTrace(
        situation="Customer #12345 requested increase from $5K to $15K",
        rationale="Fraud flag on transaction #7890 matching precedent #452",
        action="Reject. Escalate to risk team.",
        outcome="Escalation confirmed. Account flagged.",
        entities=["customer:12345", "transaction:7890", "precedent:452"],
        policies=["credit_limit_policy_v3"],
        causal_parents=["decision:452"],   # this decision was informed by precedent #452
        causal_children=["decision:453"],  # this escalated transaction is now a case
    )
)
```

**What changes:**
- Extend `Memory` model with optional `DecisionTrace` field
- Add structured extraction: when the proxy detects a decision being recorded, parse it into S/R/A/O fields
- Backward compatible: existing `DECISION` memories remain valid; structured traces are a superset
- Injection: when injecting decisions, include structured fields so the agent can reason about causal chains

**Estimated effort:** ~1 week. Model change + extraction logic + injection formatting.

### B — Decision → Entity Relationship Index (Medium, ~1 week)

Build a lightweight relationship index that links decisions to entities, policies, and other decisions.

```python
# Relationship store (separate table, or graph extension of existing memory DB)
class DecisionLink(Base):
    decision_id: str      # FK to memory entry
    target_type: str      # "entity" | "policy" | "decision" | "outcome"
    target_id: str        # ID of the linked node
    relationship: str     # "informed_by" | "applied" | "resulted_in" | "escalated_to"
    created_at: datetime
```

**What this enables:**
- "Show all decisions that applied policy v3" → graph traversal
- "What decisions did this customer trigger?" → entity → decision links
- "Which precedents were cited in this session?" → decision → decision links

**Estimated effort:** ~1 week. New table + CRUD operations + query paths.

### C — Graph Embedding Hybrid Search (Medium, ~2-3 weeks)

Add graph embedding-based retrieval alongside existing vector + FTS5:

```python
# Existing: semantic search over memory content
results = memory.search("fraud rejection")  # vector similarity

# New: structural similarity search
results = memory.search_graph(
    query="fraud rejection",
    structure={
        "entities": ["customer", "transaction"],
        "relationships": ["precedent_of", "applied_policy"],
        "depth": 2  # traverse up to 2 hops
    }
)  # graph embedding similarity
```

This requires:
1. Building graph embeddings (Node2Vec or similar) over the relationship index
2. A query interface that accepts structural constraints
3. Hybrid scoring: combine semantic + structural similarity scores
4. Integration with existing memory injection (can inject structurally similar decisions alongside semantically similar ones)

**Note:** This is a meaningful differentiator. Vector-only memory stores cannot do relationship-aware retrieval. Adding graph embeddings moves Cutctx from "fast vector search" to "reasoning-aware retrieval."

**Estimated effort:** 2-3 weeks. Graph embedding pipeline + hybrid retriever + integration.

### D — Graph Eval for Cutctx Learn (Medium, ~2 weeks)

Extend `cutctx learn` with graph-based failure analysis:

```python
# Current: text pattern mining
cutctx learn  # "Read failed 5 times" → "FirstClassEntity is at axion-scala-common/"

# New: structural failure pattern mining
cutctx learn --graph  # "3 failures followed path: lookup entity → retry → escalate → fail"
```

Graph evals enable:
- **Structural loop detection**: "Agent revisits the same tool 4+ times in a row"
- **Policy violation detection**: "Agent skipped policy check before escalation in 60% of cases"
- **Precedent quality metrics**: "Decisions citing precedent X are 30% more likely to be overturned"

**Estimated effort:** ~2 weeks. Graph eval pipeline + integration with existing cutctx learn.

### E — Decision Trace Security (Requires Thought)

The BuzzRAG analysis of Blumenfeld's talk raises a critical point not addressed by Neo4j: **poisoned traces**. If an adversary can inject plausible-looking decision traces early in a system's life, those traces become precedents. Graph embedding means structurally similar future decisions will surface those poisoned traces as relevant prior art. The agent isn't hallucinating — it's reasoning correctly from compromised data.

For Cutctx, this is relevant because:
- Cross-agent memory sharing amplifies the blast radius (one poisoned trace infects Claude + Codex + Cursor)
- CCR (Compress-Cache-Retrieve) means compressed traces are preserved — including compromised ones

**Mitigations to design for:**
- Trace provenance: every decision trace records which agent created it, in which session, using which tools
- Trace integrity: hash-chain linking of related traces to detect tampering
- Trace decay: older traces deprioritized in search unless explicitly cited recently
- Human verification markers: traces marked as "verified by human" vs "generated by agent"

---

## 6. Where This Fits: The Unified Stack (5 Talks)

```
┌─────────────────────────────────────────────────────────────────┐
│                       AGENT LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. INSTRUCTION   ← Supabase (Skills + MCP)                      │
│     What context to load                                         │
│     → Skill-aware compression                                    │
│                                                                  │
│  2. TOOL           ← Cloudflare (Code Mode)                      │
│     How tool descriptions fit                                    │
│     → Progressive loading, stub mode, code gen                   │
│                                                                  │
│  3. SESSION        ← Arize (Sub-agents)                          │
│     How session context fits in window                           │
│     → IntelligentContext, CCR, sub-agent bridge                  │
│                                                                  │
│  4. MEMORY         ← Neo4j (Kollegger & Zaim)                    │
│     Three-layer memory (knowledge, conversation, reasoning)      │
│     → Reasoning memory layer, policy-as-graph                    │
│                                                                  │
│  5. DECISION       ← Neo4j (Blumenfeld) ◄── THIS TALK            │
│     Decision traces as structured data                           │
│     → Structured trace format, graph retrieval, graph evals      │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                      CUTCTX CONTROL PLANE                         │
│   (compression · governance · memory · retrieval · evals)         │
└─────────────────────────────────────────────────────────────────┘
```

Layer 4 (memory architecture) and Layer 5 (decision traces) are complementary parts of the same Neo4j story. Layer 4 asks "what should we store?" Layer 5 answers "how should we store it and how do we find it again?"

---

## 7. Validation Plan

### Phase 1: Structured Decision Traces (1 week)

| Step | Action | Success Criteria |
|---|---|---|
| D1 | Extend `Memory` model with optional `DecisionTrace` fields | Schema change rolled; backward compatible |
| D2 | Implement trace extraction when agent records a decision | Parsed S/R/A/O fields populated from free-text |
| D3 | Update injection to include structured trace context | Agent receives structured traces, not just flat text |
| D4 | Test: record decision → inject in next session → agent references precedent by causal link | End-to-end test passes |

### Phase 2: Decision Relationship Index (1 week)

| Step | Action | Success Criteria |
|---|---|---|
| R1 | Build `DecisionLink` table (source, target_type, target_id, relationship) | CRUD operations work |
| R2 | Implement link creation: when a decision trace cites entities/policies/precedents, create edges | Edges created automatically |
| R3 | Implement traversal queries: "precedents of this decision," "entity's decision history" | Query returns correct results |
| R4 | Wire into memory injection: when injecting decisions, include linked entities | Agent sees relationship context |

### Phase 3: Graph Embedding Hybrid Search (2-3 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| G1 | Build graph embedding pipeline (Node2Vec over relationship index) | Embeddings generated; dimensionality compatible with existing vector store |
| G2 | Implement structural similarity scorer | Scores are meaningful (similar relationship topologies → high score) |
| G3 | Hybrid retriever: combine semantic + structural scores | Weighted scoring returns relevant results from both dimensions |
| G4 | Integration test: query for "fraud rejection" → finds semantically similar → finds structurally similar decisions using same relationship pattern | Both result types present |

### Phase 4: Graph Evals for Cutctx Learn (2 weeks)

| Step | Action | Success Criteria |
|---|---|---|
| E1 | Design graph eval data model (agent steps as graph nodes) | Schema reviewed |
| E2 | Implement agent step capture (actions, tool calls, states, failures) | Steps stored as traversable graph |
| E3 | Build query patterns: loop detection, policy skip detection | Queries catch known failure patterns |
| E4 | Integrate into `cutctx learn --graph` | Command produces structural failure insights |

### Success Gates

| Gate | Entry | Go/No-Go |
|---|---|---|
| **D1-D4** | Structured traces working end-to-end | ✅ Phase 2 |
| **R1-R4** | Decisions linked to entities/policies; traversal works | ✅ Phase 3 |
| **G1-G4** | Hybrid search returns structurally similar results | ✅ Phase 4 |
| **E1-E4** | Graph evals catch known failure patterns | ✅ Feature complete |

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Structured trace extraction is noisy (free-text → fields) | High | Medium | Extraction is best-effort; fall through to flat text if parsing fails |
| Graph embeddings add complexity and storage | Medium | Low | Embeddings table bounded by decision count; configurable retention |
| Relationship index grows linearly with decisions | Low | Low | Index is lightweight (edges are small); tree million decisions ~ a few hundred MB |
| Poisoned trace injection is hard to detect | Medium | High | Provenance tracking (agent, session, timestamp) built into every trace |
| Graph evals only useful for structured agent workflows | Medium | Low | Eval is opt-in; existing text-based failure mining continues |

---

## 9. Success Metrics

| Metric | Current Baseline | Target |
|---|---|---|
| Decision trace retrieval precision | Flat text search (baseline) | +20% precision with structured fields |
| Cross-decision precedent discovery | None (decisions isolated) | Agent cites relevant precedents >60% of the time |
| Graph embedding search recall @5 | Not measured | >80% for structurally similar decisions |
| Graph eval catch rate | Not measured (text-only today) | Detects 100% of known failure paths in test sessions |
| Poisoned trace detection | No mechanism | Provenance chain verifiable for every trace |

---

## 10. Recommendation

**Phase order: D1-D4, then R1-R4, then G1-G4, then E1-E4.**

The structured decision trace format (Phase 1) is the smallest change with the highest near-term value — it makes every decision memory richer and more actionable without requiring graph infrastructure.

The relationship index (Phase 2) is the foundation for all graph features. Without edges between decisions, entities, and policies, graph traversal and graph embeddings have nothing to work with. Build this early.

Graph embedding hybrid search (Phase 3) is the highest-differentiation feature. No other agent memory system (Letta, Mem0, Zep) offers structural similarity search alongside semantic search. This would be a genuine competitive moat.

Graph evals (Phase 4) are valuable but directional — they depend on adoption of structured agent workflows.

---

## 11. References

- Talk: "Why your agents need decision traces, not just documents" — Zach Blumenfeld, Neo4j (AI Engineer EU 2026)
- Neo4j Agent Memory: https://neo4j.com/labs/agent-memory/
- `create-context-graph`: https://create-context-graph.dev/
- Neo4j blog: "Hands on with context graphs and Neo4j" (Jan 2026)
- Neo4j blog: "From recall to reasoning: How context graphs upgrade an agent's brain" (Apr 2026)
- BuzzRAG: "AI Agents Need Decision Traces — And a Threat Model" (May 2026)
- Foundation Capital: "Context Graphs: AI's Trillion-Dollar Opportunity"
- Cutctx memory docs: `docs/content/docs/memory.mdx`
- Earlier Neo4j analysis (Kollegger & Zaim): `docs/superpowers/specs/2026-07-04-skills-mcp-context-graphs-adoption.md`
