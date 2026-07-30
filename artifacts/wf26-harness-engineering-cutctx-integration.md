# WF26 Harness Engineering → CutCtx Integration Report

**Source:** [WF26: Harness Engineering & Startup Battlefield](https://www.youtube.com/watch?v=I2cbIws9j10)
**Channel:** AI Engineer
**Event:** AI Engineer World’s Fair 2026 — Day 4 (Moscone West, San Francisco)
**Duration:** ~9.2 hours (auto-captions analyzed end-to-end)
**Report date:** 2026-07-29
**Product:** CutCtx (context control plane for AI agents)

---

## Executive summary

Day 4 of WF26 was explicitly themed **harness engineering**: how teams wrap models with memory, skills, tools/MCP, loops, evals, identity, and observability so agents escape demos and run in production.

That is CutCtx’s category. The transcript does **not** suggest reinventing CutCtx as a durable-execution runtime, graph DB, or coding agent. It strongly validates deepening what CutCtx already owns:

1. **Compaction as a projection** of a durable record (CCR / reversible compression)
2. **Context-explosion defense** for schemas, tool catalogs, MCP dumps, RAG
3. **Scoped shared memory** across agents/teams with access control
4. **Scan-then-compress** security on tool I/O
5. **Fidelity contracts + attributed budgets** for long harness loops

**Highest-ROI order:** (1) CCR-as-projection UX + messaging → (2) schema/MCP catalog compression → (3) firewall on tool outputs before compress → (4) scoped shared memory ACLs → (5) harness-loop compression profile + fidelity contracts.

---

## 1. What the video is

Full Day 4 livestream of **AI Engineer World’s Fair 2026**, not a single talk.

| Field | Detail |
|---|---|
| Title | WF26: Harness Engineering & Startup Battlefield ft. Garry Tan, Mike Krieger, @t3dotgg, DSPy |
| Theme | Harness engineering + closing Startup Battlefield |
| Scale | ~7,000 attendees (stated on stage) |
| MC | Ralph / Ra’ouf (Replit DevRel) |
| Closing | Startup Battlefield finals + event wrap; tease NY Oct + next year’s fair |

### Day arc (approximate timestamps from captions)

| Time | Segment |
|---|---|
| 00:00 | Open, sponsors, day theme: harness engineering |
| 00:16 | **Bar Yaron (Amplify)** — State of AI Engineering survey |
| 00:35 | **John Ousterhout (Stanford)** — Networking for AI workloads (Homa / latency / incast) |
| 00:54 | **DSPy (Maxime Rivest & Isaac Miller)** — Contracts, reliable AI software |
| 01:12 | **Mike Krieger (Anthropic)** — Fireside (Fable/Mythos, goal-delegation, “be unreasonable”) |
| 01:39 | **Emil Eifrem (Neo4j)** — Ontologies / graphs for agent-ready enterprise data |
| 02:00–03:10 | Midday talks — token budgets/strategies, context explosion, Salesforce/MCP, Nori, **WorkOS** (agent autonomy + auth) |
| 03:15–04:40 | Harness talks + **Ralph-loops / shared-memory / compaction** debate |
| 05:00–06:30 | Durable backends (**Restate**, **Resonate**), **PostHog** agent security, DB/vector harness bits |
| 06:30–07:10 | **Vercel** — agent building; **log as primary record; compaction as projection** |
| 07:40 | Late keynotes stretch |
| 07:42 | **Theo (@t3dotgg)** — What to build now; think wider, not only deeper |
| 07:58 | **Garry Tan (YC)** — AI as workforce; wire the work; one person ≈ former large org |
| 08:19 | **Howie Liu (Airtable / Hyperagent)** — Agent-native companies / Founding 500 framing |
| 08:40 | **Startup Battlefield** finals (~$100k prizes); pitches incl. Kamod (commodity trade), Comet IO (multiplayer markdown), creator tooling |
| 09:06 | Close |

---

## 2. Transcript themes scored for CutCtx relevance

Rough keyword density from cleaned auto-captions (relative signal, not absolute importance):

| Theme cluster | Relative hits | CutCtx relevance |
|---|---:|---|
| Ontology / RAG / retrieval language | High | Medium (compress RAG/tool dumps; don’t own ontology) |
| Cost / token economics | High | High |
| Context window / compaction | High | **Core** |
| Security / injection / credentials | High | High (`cutctx_scan`, firewall) |
| Evals / observability / verification | High | High (governance + fidelity) |
| Durable execution (Restate/Resonate) | High | Low as product; interop only |
| MCP / tools | Medium-high | High (already gateway-compress tool results) |
| WorkOS / identity | Medium | Medium (attribution / tenancy, not auth OS) |
| Harness engineering language | Medium | **Core positioning** |
| Shared memory | Medium | High (extend existing memory) |
| DSPy / “what good looks like” | Medium | High (compression contracts) |
| Ralph / agent loops | Lower count, high signal | High (loop profile) |
| Vercel “log vs projection” | Lower count, **highest conceptual fit** | **Core** |
| Networking (Homa) | Present | Skip |
| Battlefield vertical apps | Present | Skip / GTM only |

---

## 3. CutCtx product context (what we map into)

CutCtx is the **local-first context control plane** under agent harnesses:

- Compress tool outputs, logs, RAG, files, history before they hit the LLM
- **CCR** — originals cached; retrieve on demand
- Cross-agent **memory**, MCP tools, proxy wrap for Claude/Codex/Cursor/etc.
- Firewall scan, savings attribution, org/workspace governance

Existing positioning already says: *“Cutctx is the local-first context control plane under your agent harnesses.”* WF26 is market confirmation of that language.

---

## 4. Integration analysis (talk-by-talk)

### 4.1 Strong fit — integrate into CutCtx

#### A. Vercel agent talk — “log is primary; compaction is a projection” (~06:50)

**What they said**

- The agent loop worker is disposable; the **durable log** is the agent.
- Model context, UI, debugging, auditing, and **compaction** are all **projections** of that log.
- Compaction is lossy. If you keep only the summary and discard the raw log, you lose part of the agent.
- Treat compaction like a materialized view / best-effort lossy fork — resumable because the full record remains.

**Why it fits CutCtx**

This is CCR’s conceptual backbone. Competitors and provider-native compaction often throw away the record. CutCtx’s differentiator is reversible projection.

**Integrate**

1. Productize messaging: “CutCtx turns harness compaction into a **projection**, not deletion.”
2. Dashboard **request inspector**: raw input → compressed projection → retrieve-by-hash → provider payload.
3. Explicit “never discard eligible originals within TTL” guarantees in docs/buyer report.
4. Harness-facing API/docs that map: `agent log` ↔ CCR store; `model view` ↔ compressed messages.

**Priority:** P0

---

#### B. Ralph-loops / harness panel — lossy compaction vs shared learning (~04:11–04:20)

**What they said**

- Everyone does compaction because windows fill; it is lossy (YouTube recompress analogy).
- Shared memory lets loops learn and converge; per-agent isolation kills shared learning.
- Need shared memory **with** access control — not isolation-by-default forever.

**Integrate**

1. **Harness loop profile**: preserve loop memory artifacts, tool traces, and decision receipts across long runs; compress payloads but keep CCR hashes in the working summary.
2. **Scoped shared memory ACLs**: workspace / agent / team scopes on `cutctx memory` (builds on existing orgs/workspaces).
3. Competitive wedge vs native Cursor/Claude/Codex compaction: “lossy fork with retrieval,” not silent truncate.

**Priority:** P0–P1

---

#### C. Salesforce / enterprise talks — “context explosion” (~02:22)

**What they said**

- Loading many schemas into the agent window burns a huge fraction of context before work starts.
- Tool/MCP catalogs and skills multiply the problem; security/tenant isolation complicate credentialed tool access.

**Integrate**

1. First-class **schema / OpenAPI / MCP tool-catalog compressor** (progressive disclosure: names + short desc in-context; full defs behind retrieve).
2. Default MCP-gateway behavior: compress large tool results **and** large tool definitions.
3. Benchmark fixture: “52 schemas / fat MCP catalog” → tokens before/after + fidelity of selected tools.

**Priority:** P0

---

#### D. PostHog — prompt injection / agent I/O scanning (~05:44)

**What they said**

- Agents can ship injection payloads into other agents (e.g. PR bots).
- Scan content at both ends; allow/block policies; false positives are common (demo logins, etc.).
- Blind blocklists (“block the word ignore”) break agents.

**Integrate**

1. Pipeline: **`cutctx_scan` → then compress** for tool outputs and retrieved RAG by default (flagged).
2. Quarantine mode: risky blob stored in CCR, model sees redacted stub + hash, human/policy can retrieve.
3. Tunable FP handling; don’t claim zero false positives — log decisions in audit.

**Priority:** P1

---

#### E. DSPy — define “what good looks like” (~01:07)

**What they said**

- Hard part of reliable AI software is defining good; hold prompts/models/code accountable to the problem.
- Separate task contract from model/harness implementation details.

**Integrate**

1. Expose **compression fidelity contracts** (extend accuracy-guard): must preserve paths, FATAL/severity, IDs, hashes, stack frames, CCR markers.
2. Ship as named profiles: `logs`, `code-diff`, `mcp-json`, `rag-prose`.
3. Market as harness-level SLAs, not “we delete more tokens.”

**Priority:** P1

---

#### F. Token budget / strategy talks (~01:57–02:05)

**What they said**

- Agents get a token budget; spend is often indiscriminate.
- Same budget + different strategies → different quality; need accountability for how tokens are used.

**Integrate**

1. Surface **eligible vs passthrough vs compressed** tokens in harness-facing stats (buyer report already separates sources — make it default in dashboard for wrap sessions).
2. Optional soft budgets that prefer compression before model downgrade / hard stop.
3. Session receipts: “why this payload was compressed / skipped.”

**Priority:** P1

---

#### G. Day theme — harness engineering as category

**What they said**

- Harness = memory, skills, tools/MCP, loop management, observability/evals, identity.
- Models improve; bad harnesses still fail. “Escaping demo world.”

**Integrate**

1. Align landing/docs/AIE outreach with harness vocabulary (already in `value-proposition.md`).
2. One diagram: **Harness claws → CutCtx context plane → providers**.
3. Don’t claim CutCtx *is* the full harness — claim it is the **shared context substrate** under changing harnesses (`wrap` / global routing).

**Priority:** P0 (messaging), low eng cost

---

### 4.2 Medium fit — useful, not identity-defining

| Source | Idea | CutCtx angle | Action |
|---|---|---|---|
| WorkOS | Agent identity, entitlements, credential issuance | Attribute spend/memory by agent/tenant; don’t rebuild IdP | Attribution fields + SCIM/RBAC polish |
| MCP everywhere | Tools as universal adapters | Strengthen `mcp gateway` compress-by-default | Product default + docs |
| AWS harness talk | Observability/evals first; no “slop ops” | Matches gateway/observability gap vs Helicone | Request tracing (existing competitive backlog P2) |
| Bar Yaron survey | Agents live; cost/control lag; escaping demos | GTM proof points | Blog/outreach, not features |
| Krieger / Theo / Garry | Longer autonomous runs; AI as workforce; think wider | Longer runs → more context pressure | Messaging only |
| Neo4j ontology | Make enterprise data agent-ready | Compress graph/RAG dumps; don’t own graph | Compressor fixtures; partner narrative |
| Oracle / vector talks | Shared team memory / vector store tips | Memory embedder / retention polish | Incremental |
| Restate / Resonate | Durable long-running agent backends | Interop: compress payloads inside durable workflows | Optional examples, not core |

### 4.3 Weak / skip for product

| Source | Why skip |
|---|---|
| Ousterhout / Homa networking | Infra networking; not context plane |
| Startup Battlefield verticals (Kamod, Comet, etc.) | Customer segments / demos at most |
| Brand constitutions / Nori sessions | Prompt/UX products |
| Vercel AI SDK / Hyperagent as features to clone | Distribution partners, not CutCtx scope |
| Building a Ralph-loop runner | CutCtx sits *under* loops; don’t own the loop |

---

## 5. Unified recommendations

### 5.1 Build next (engineering)

| # | Recommendation | Maps to | Effort (rough) | Outcome |
|---|---|---|---|---|
| 1 | **Request inspector**: raw → compressed → retrieve → provider payload | Vercel projection model; Helicone-gap observability | M | Makes CCR tangible; trust + sales |
| 2 | **Schema / MCP catalog compressor** + progressive tool disclosure | Context explosion | M | Direct token wins on agent harnesses |
| 3 | **Scan-then-compress** pipeline for tool outputs | PostHog security | S–M | Differentiated safe compression |
| 4 | **Scoped shared memory ACLs** (workspace/agent/team) | Shared-memory debate | M | Multi-agent / team readiness |
| 5 | **Harness loop profile** (preserve receipts, CCR hashes across long runs) | Ralph loops + lossy compaction critique | S–M | Better long-run fidelity |
| 6 | **Named fidelity contracts** extending accuracy-guard | DSPy contracts | S | Enterprise “quality under compression” story |
| 7 | **Harness-visible budget/savings receipts** | Token budget talks | S | Attribution buyers already ask for |

### 5.2 Ship in messaging / GTM (low eng)

1. Lead AIE-aligned one-liner: **CutCtx is the context plane under your agent harness.**
2. Publish a short post: *“Native compaction deletes the agent. CutCtx projects it.”* citing the Vercel log/projection framing (paraphrase, don’t overclaim affiliation).
3. Use Bar Yaron “escaping demo world” + Garry “AI as workforce” as demand proof for longer contexts and cross-provider control.
4. Do **not** reposition CutCtx as durable execution, ontology platform, or coding agent.

### 5.3 Explicit non-goals (from this video)

- Owning Restate/Resonate-style workflows
- Replacing Neo4j / enterprise ontology layers
- Building WorkOS-equivalent agent OAuth
- Competing with Vercel AI SDK or Hyperagent product surfaces
- Networking-stack work (Homa/TCP)

---

## 6. Mapping to existing CutCtx backlog

WF26 recommendations reinforce — not replace — existing strategy docs:

| Existing artifact | Reinforced by WF26 |
|---|---|
| `artifacts/value-proposition.md` — harness substrate | Day theme literally “harness engineering” |
| CCR / reversible compression | Vercel “compaction is projection” |
| `competitive-gap-backlog.md` P2 gateway/observability | Request inspector / traces |
| MCP gateway compress tool results | Context explosion + MCP ubiquity |
| `cutctx_scan` / firewall | PostHog injection scanning |
| Cross-agent memory | Shared memory + ACL tension |
| Accuracy-guard / evals | DSPy “define good” |
| Buyer report attribution | Token budget accountability |

---

## 7. Suggested acceptance criteria (if we execute top 5)

1. **Inspector:** For one wrap session, UI/API shows original tool output, compressed form, hash, and successful `retrieve`.
2. **Catalog compression:** Fat MCP/OpenAPI fixture reduces prompt tokens ≥30% while selected tool names remain present; full defs retrievable.
3. **Scan-then-compress:** Injected “ignore previous instructions” in a tool blob is flagged/quarantined before provider forward (configurable).
4. **Memory ACL:** Agent A cannot read Agent B’s scoped memory without shared workspace grant; shared grant enables cross-agent retrieve.
5. **Loop profile:** 50-step synthetic loop keeps CCR hashes for compressed steps; random retrieve restores exact original string.

---

## 8. Bottom line

WF26 Day 4 is a **category confirmation** for CutCtx, not a prompt to expand scope sideways.

Steal these four ideas into the product:

1. **Projection, not deletion** (CCR UX + narrative)
2. **Fight context explosion** (schemas/tools/MCP)
3. **Shared memory with scopes** (multi-agent)
4. **Scan, then compress** (safe harness I/O)

Everything else is messaging, partnerships, or out of scope.

---

## Appendix A — Source metadata

- YouTube ID: `I2cbIws9j10`
- URL: https://www.youtube.com/watch?v=I2cbIws9j10
- Captions: English auto-captions (`en`) via yt-dlp; ~90k+ words after dedupe
- Analysis method: full-caption download, timed agenda extraction, theme scoring, mapping against CutCtx README / value prop / capability matrix / competitive gap backlog

## Appendix B — Related internal docs

- `README.md` — product overview
- `artifacts/value-proposition.md` — harness substrate positioning
- `artifacts/PRODUCT_CAPABILITY_MATRIX.md` — current capabilities
- `artifacts/competitive-gap-backlog.md` — hosted entry + observability gaps
- `docs/` — CCR / architecture references
