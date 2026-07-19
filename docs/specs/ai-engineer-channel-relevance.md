# AI Engineer Channel — Video Relevance for CutCtx

**Date:** 2026-07-19 (Updated — full 880-video catalog)
**Channel:** https://www.youtube.com/@aiDotEngineer/videos
**Scope:** All 880 published videos (AI Engineer conference series, 2024–2026)
**Method:** Keyword relevance scoring on titles + description analysis for top candidates

---

## How to Use This Document

- **Tier 1** — Watch immediately. Directly informs CutCtx product direction.
- **Tier 2** — Strong relevance. Covers adjacent or complementary topics.
- **Tier 3** — Useful context. Worth watching when time allows.
- **Tier 4** — Not directly relevant (ML training, general biz, design).

Each entry includes: video ID, title, speaker/org, why it matters for CutCtx, and what to take away.

---

## Tier 1: VERY HIGH — Watch Immediately

### 1. Make Your Own Event-Sourced Agent Harness Using Stream Processors — Jonas Templestein, Iterate

| | |
|---|---|
| **Video ID** | `vi-2nasppAg` (already watched) |
| **# in channel** | 205 |

**Core thesis:** Three-part abstraction — event stream, synchronous reducer, after-append hook. Every interaction is an event. Dynamic workers deployable as payloads.

**Why for CutCtx:** This is the foundation. Already documented in `event-sourced-agent-harness.md`.

---

### 2. Your Agents Need a Save Button — Hamza Tahir, ZenML

| | |
|---|---|
| **Video ID** | `bZISsg7H7DA` |
| **# in channel** | 5 |

**Core thesis:** Freeze agents to durable state, drop compute to zero, resume in milliseconds. Replay from any point to debug.

**Why for CutCtx:** Directly about durable agent state — the core problem the event journal solves. Aligns perfectly with the event-sourced harness spec.

---

### 3. WTF Is the Context Layer? The Missing Infrastructure for Production Agents — Prukalpa Sankar

| | |
|---|---|
| **Video ID** | (new — get from channel) |
| **# in channel** | 17 |

**Core thesis:** Argues that context management is the missing infrastructure layer for production agents. What observability was to microservices, context management is to agents.

**Why for CutCtx:** This **is** CutCtx's positioning. "Context layer" is exactly what CutCtx provides. Directly validates the product thesis.

---

### 4. Two Roads to Durable Agents: Replay vs. Snapshot — Eric Allam, CEO, Trigger.dev

| | |
|---|---|
| **Video ID** | (new) |
| **# in channel** | 215 |

**Core thesis:** Two approaches to durable agent execution — replaying the event log vs. taking state snapshots. Trade-offs between cost, speed, and complexity.

**Why for CutCtx:** Directly informs the design decision in our event-sourced harness. Replay (event sourcing) vs. snapshot (checkpointing) is the exact architectural choice we need to make.

---

### 5. Claude for Long-Horizon Tasks — Lance Martin, Anthropic

| | |
|---|---|
| **Video ID** | `9QebvrrY3KY` |
| **# in channel** | 10 |

**Core thesis:** Lessons from building agent harnesses at Anthropic. Decoupling brain and hands, self-verification, self-learning.

**Why for CutCtx:** Official Anthropic perspective on agent harness design. Lance works on Claude Managed Agents.

---

### 6. The Great Loops Debate

| | |
|---|---|
| **Video ID** | `c35YoMdnI78` |
| **# in channel** | 6 |

**Core thesis:** Do agent loops work as hyped? "Stop writing loops, start writing control loops."

**Why for CutCtx:** Provides vocabulary to position event-sourced harness as a control loop (not a naive loop). Multiple production practitioners' perspectives.

---

### 7. From Stateless Nightmares to Durable Agents — Samuel Colvin, Pydantic

| | |
|---|---|
| **Video ID** | (new) |
| **# in channel** | 359 |

**Core thesis:** Stateless architectures that work for demos become impossibly painful at scale. Companies like OpenAI and Vercel are moving to durable execution.

**Why for CutCtx:** Reinforces the durability argument. From the creator of Pydantic — widely used in the AI ecosystem. CutCtx could integrate with Pydantic.

---

### 8. Two Roads to Durable Agents: Replay vs. Snapshot — Eric Allam, Trigger.dev

| | |
|---|---|
| **Video ID** | (new) |
| **# in channel** | 215 |

**Core thesis:** Trigger.dev CEO compares replay-based vs. snapshot-based durable execution for agents.

**Why for CutCtx:** Trigger.dev is a direct adjacent product. Understanding their architectural choices informs ours.

---

### 9. Harness Engineering: How to Build Software When Humans Steer, Agents Execute — Ryan Lopopolo, OpenAI

| | |
|---|---|
| **Video ID** | (new) |
| **# in channel** | 278 |

**Core thesis:** Engineering principles for building agent harnesses — the software layer between humans and autonomous agents.

**Why for CutCtx:** From OpenAI's team. Directly about the "harness" concept CutCtx is building.

---

### 10. Your Agent Failed in Prod. Good Luck Reproducing It. — Tisha Chawla & Susheem Kool, Microsoft

| | |
|---|---|
| **Video ID** | (new) |
| **# in channel** | 85 |

**Core thesis:** Why agent failures in production are unreproducible and what to do about it.

**Why for CutCtx:** The event journal is **the solution** to this problem. Every interaction logged = full replayability.

---

## Tier 2: HIGH — Strong Relevance

### Agent Infrastructure & Middleware

| # | Title | Speaker | Why for CutCtx |
|---|-------|---------|----------------|
| 17 | **WTF Is the Context Layer? The Missing Infrastructure for Production Agents** | Prukalpa Sankar | Context management as infrastructure — directly CutCtx's positioning |
| 81 | **Deterministic Infra for Non-Deterministic AI Agents** | Nishant Gupta, Meta | Covers infrastructure challenges that CutCtx solves |
| 150 | **What if the network was the sandbox?** | Remy Guercio, Tailscale | Network-isolated agent sandboxing intersects with CutCtx proxy architecture |
| 183 | **Scaling Agents on Kubernetes with acpx and ACP** | Onur Solmaz, OpenClaw | Deployment patterns for scaling agents |
| 228 | **The Multi-Agent Architecture That Actually Ships** | Luke Alvoeiro, Factory | Real multi-agent deployment patterns |
| 288 | **From Chaos to Choreography: Multi-Agent Orchestration Patterns That Actually Work** | Sandipan Bhaumik | Multi-agent orchestration — aligns with CutCtx's shared event stream model |
| 304 | **Building durable Agents with Workflow DevKit & AI SDK** | Peter Wielander, Vercel | Durable agent execution on Vercel's platform |
| 343 | **Don't Build Agents, Build Skills Instead** | Barry Zhang & Mahesh Murag, Anthropic | Agent skill architecture — relevant to stream processor design |
| 360 | **I Run a Fleet of AI Agents Across Three Machines. Here's What Broke.** | Kyle Jaejun Lee, KRAFTON | Real failure patterns in multi-machine agent deployment |
| 427 | **Scaling AI Agents Without Breaking Reliability** | Preeti Somal, Temporal | Temporal's approach to agent reliability |
| 534 | **12-Factor Agents: Patterns of reliable LLM applications** | Dex Horthy, HumanLayer | Design patterns for reliable agents |

### Context & Token Optimization

| # | Title | Speaker | Why for CutCtx |
|---|-------|---------|----------------|
| 52 | **Stop Burning Tokens: Why self-improvement needs domain expertise first** | Annabell Schäfer, Langfuse | Token waste — directly CutCtx's value prop |
| 88 | **We Cut 94% of AI Coding Tokens With a Local Code Index** | Rajkumar Sakthivel, Tesco | Token reduction case study — validates CutCtx approach |
| 89 | **Your Agent Is Wasting Tokens and You Don't Know It** | Erik Hanchett, AWS | Token waste identification — CutCtx's market |
| 98 | **User Signal Dies at the Retrieval Boundary** | Sonam Pankaj | Retrieval/context boundary problem CutCtx solves |
| 128 | **Road to 5 Million Tokens: Breaking Barriers in Long Context Training** | Max Ryabinin, Together AI | Long context — relevant to compression strategy |
| 216 | **How we solved Context Management in Agents** | Sally-Ann Delucia | Practical context management patterns |
| 237 | **Mergeable by default: Building the context engine to save time and tokens** | Peter Werry, Unblocked | Context engine for token savings |
| 364 | **Context Platform Engineering to Reduce Token Anxiety** | Val Bercovici, WEKA | Token anxiety — CutCtx's target customer pain |
| 584 | **GraphRAG methods to create optimized LLM context windows** | Jonathan Larson, Microsoft | Context window optimization |

### Agent Evaluation & Observability

| # | Title | Speaker | Why for CutCtx |
|---|-------|---------|----------------|
| 70 | **SWE-Marathon: Evaluating Coding Agents at Billion-Token Scale** | Rishi Desai, Abundant AI | Evaluation at scale — aligns with cutctx learn |
| 110 | **Production Evals For Agentic AI Systems** | Nishant Gupta, Meta | Production evaluation patterns |
| 131 | **LLM Observability, Evaluation, Experimentation Platform** | Dat Ngo, Arize | Observability patterns applicable to CutCtx |
| 161 | **How agent o11y differs from traditional o11y** | Phil Hetzel, Braintrust | Agent-specific observability |
| 204 | **Mind the Gap (In your Agent Observability)** | Amy Boyd & Nitya Narasimhan, Microsoft | Gaps in agent observability that CutCtx can fill |
| 226 | **Everything You Need To Know About Agent Observability** | Danny Gollapalli & Zubin Koticha, Raindrop | Comprehensive o11y overview |
| 563 | **Taming Rogue AI Agents with Observability-Driven Evaluation** | Jim Bennett, Galileo | Observability for agent safety |
| 604 | **The State of MCP observability: Observable.tools** | Alex Volkov & Benjamin Eckel | MCP observability |

### Multi-Agent Systems

| # | Title | Speaker | Why for CutCtx |
|---|-------|---------|----------------|
| 3 | **Agents Need Receipts, Not More Tool Calls** | Armanas Povilionis, Alithea Bio | Agent-to-agent verification protocol — potential CutCtx integration |
| 177 | **The Missing Primitive for Agent Swarms** | Lou Bichard, Ona | Missing primitives in agent swarms |
| 302 | **Automating Large Scale Refactors with Parallel Agents** | Robert Brennan, OpenHands | Parallel agent coordination |
| 377 | **Multi Agent AI and Network Knowledge Graphs for Change** | Ola Mabadeje, Cisco | Multi-agent coordination |
| 483 | **UX Design Principles for Semi Autonomous Multi Agent Systems** | Victor Dibia, Microsoft | Multi-agent UX patterns |
| 717 | **Building Multi agent Systems with Finite State Machines** | — | State machine approach to multi-agent |

### Agent Memory & State

| # | Title | Speaker | Why for CutCtx |
|---|-------|---------|----------------|
| 104 | **Turn 10,994 Notes Into Memory** | Paul Iusztin, Decoding AI | Memory management for agents |
| 308 | **Jack Morris: Stuffing Context is not Memory, Updating Weights is** | Jack Morris | Agent memory architecture |
| 478 | **Stop Using RAG as Memory** | Daniel Chalef, Zep | Correct agent memory patterns |
| 579 | **Architecting Agent Memory: Principles, Patterns, and Best Practices** | Richmond Alake, MongoDB | Agent memory design |
| 582 | **Memory Masterclass: Make Your AI Agents Remember What They Do!** | Mark Bain, AIUS | Practical agent memory |

### MCP & Tool-Use

| # | Title | Speaker | Why for CutCtx |
|---|-------|---------|----------------|
| 21 | **"I've never seen anything scarier than an LLM with tool calls."** | Erik Meijer | Tool-use safety concerns |
| 74 | **MCP Apps: Primitives, discovery, and the Future of Software** | Pietro Zullo | MCP ecosystem relevant to CutCtx plugin model |
| 117 | **Why MCP and ChatGPT Apps Use Double Iframes** | Frédéric Barthelet | MCP implementation patterns |
| 119 | **The agent-ready web: Simplify user actions with WebMCP** | Tara Agyemang, Google | WebMCP — new standard relevant to CutCtx |
| 137 | **Building Agent Interfaces: Lessons from Chrome DevTools (MCP) for Agents** | Michael Hablich, Google | MCP interface design |
| 201 | **Combine Skills and MCP to Close the Context Gap** | Pedro Rodrigues, Supabase | MCP for context management |
| 259 | **MCP = Mega Context Problem** | Matt Carey | MCP context challenges |
| 274 | **The Future of MCP** | David Soria Parra, Anthropic | MCP roadmap from Anthropic |
| 292 | **Your Insecure MCP Server Won't Survive Production** | Tun Shwe, Lenses | MCP security — relevant to CutCtx proxy |
| 294 | **Bending a Public MCP Server Without Breaking It** | Nimrod Hauser, Baz | MCP reliability |
| 299 | **Your MCP Server is Bad (and you should feel bad)** | Jeremiah Lowin, Prefect | MCP server quality |
| 500 | **The rise of the agentic economy on the shoulders of MCP** | Jan Curn, Apify | MCP ecosystem growth |
| 501 | **MCP is all you need** | Samuel Colvin, Pydantic | MCP-centric architecture |
| 535 | **MCP Is Not Good Yet** | David Cramer, Sentry | Critical perspective on MCP |
| 606 | **Remote MCPs: What we learned from shipping** | John Welsh, Anthropic | Remote MCP lessons |
| 607 | **MCP: Origins and Requests For Startups** | Theodora Chu, MCP PM at Anthropic | MCP origin story and opportunities |
| 638 | **Will Agent evaluation via MCP Stabilize Agent Networks?** | Ari Heljakka | MCP as evaluation interface |

### Agent Economics & Cost

| # | Title | Speaker | Why for CutCtx |
|---|-------|---------|----------------|
| 1 | **Stop Renting Your Cognitive Infrastructure** | Thiyagarajan Maruthavanan, Kalmantic Labs | Inference cost optimization — complementary to CutCtx |
| 4 | **Agents Need Feature Flags** | Sachin Gupta | Feature flags as CutCtx Enterprise product feature |
| 136 | **Building safe Payment Infrastructure for the autonomous economy** | Steve Kaliski, Stripe | Agent commerce infrastructure |
| 210 | **Lessons from Trillion Token Deployments at Fortune 500s** | Alessandro Cappelli, Adaptive ML | Token optimization at scale |
| 706 | **Mission-Critical Evals at Scale (Learnings from 100k medical decisions)** | — | Evaluation at enterprise scale |

### Production Agent Patterns

| # | Title | Speaker | Why for CutCtx |
|---|-------|---------|----------------|
| 34 | **Stop AI Agent Hallucinations: 5 Techniques + Production Patterns** | Elizabeth Fuentes, AWS | Production pattern for reducing hallucinations |
| 85 | **Your Agent Failed in Prod. Good Luck Reproducing It.** | Tisha Chawla & Susheem Koul, Microsoft | Reproducibility problem — event journal solves this |
| 106 | **Agents in Production: How OpenGov Built and Scaled OG Assist** | Gabe De Mesa, OpenGov | Real production agent deployment story |
| 114 | **The Production AI Playbook: Deploying Agents at Enterprise Scale** | Sandipan Bhaumik, Databricks | Enterprise deployment playbook |
| 173 | **How Google DeepMind Runs Agents at Scale** | KP Sawhney & Ian Ballantyne, Google DeepMind | Google-scale agent operations |
| 193 | **Anthropic Workshop: Build Agents That Run for Hours** | Ash Prabaker & Andrew Wilson, Anthropic | Long-running agent architecture |
| 278 | **Harness Engineering: How to Build Software When Humans Steer, Agents Execute** | Ryan Lopopolo, OpenAI | Agent harness engineering from OpenAI |
| 330 | **What We Learned Deploying AI within Bloomberg's Engineering Organization** | Lei Zhang, Bloomberg | Enterprise AI deployment |
| 463 | **POC to PROD: Hard Lessons from 200+ Enterprise GenAI Deployments** | Randall Hunt, Caylent | Production deployment lessons |
| 566 | **Effective agent design patterns in production** | Laurie Voss, LlamaIndex | Production agent patterns from LlamaIndex |
| 635 | **How agents broke app-level infrastructure** | Evan Boyle | Infrastructure challenges agents create |

---

## Tier 3: Useful Context (Watch When Time Allows)

These videos cover adjacent topics that inform CutCtx's roadmap.

### Agent Architecture & Skills (~70 videos)

Notable mentions:

| # | Title | Why |
|---|-------|-----|
| 63 | **Beyond the Harness: A Journey Towards Adaptative Engineering** | Adaptive agent harness patterns |
| 65 | **What if the harness mattered more than the model?** | Harness-first architecture |
| 77 | **Building Great Agent Skills: The Missing Manual** | Agent skill design |
| 109 | **Recursive Coding Agents** | Recursive agent patterns |
| 155 | **How I deleted 95% of my agent skills and got better results** | Skill minimization |
| 206 | **Self-Training Agents: Hermes Agent, HF Traces, Skills, MCP & Finetuning** | Self-training agent patterns |
| 235 | **Ralph Loops: Build Dumb AI Loops That Ship** | Practical agent loop patterns |
| 240 | **I Gave an AI Agent the Keys to My Life** | Agent autonomy limits |
| 260 | **AgentCraft: Putting the Orc in Orchestration** | Agent orchestration |
| 398 | **Agents vs Workflows: Why Not Both?** | Agents vs workflow debate |
| 458 | **3 ingredients for building reliable enterprise agents** | Harrison Chase, LangChain |
| 462 | **Building Agents (the hard parts!)** | Rita Kozlov, Cloudflare |
| 565 | **Don't get one-shotted: Use AI to test, review, merge, and deploy code** | Agent CI/CD |
| 674 | **Building and evaluating AI Agents** | Sayash Kapoor, AI Snake Oil |
| 806 | **Architecting and Testing Controllable Agents** | Lance Martin, Anthropic |
| 827 | **Building Reliable Agentic Systems** | Eno Reyes |

### Evals & Testing (~60 videos)

| # | Title | Speaker |
|---|-------|---------|
| 18 | **Don't Ship Skills Without Evals** | Philipp Schmid, Google DeepMind |
| 55 | **Build Evals That Actually Matter** | Nick Ung, Lyft |
| 110 | **Production Evals For Agentic AI Systems** | Nishant Gupta, Meta |
| 135 | **Evals Are Broken, Use Them Anyway** | Ara Khan, Cline |
| 141 | **The Art & Science of Benchmarking Agents** | Vincent Chen, Snorkel AI |
| 142 | **SWE-rebench: Lessons from Evaluating Coding Agents** | Ibragim Badertdinov, Nebius |
| 166 | **The maturity phases of running evals** | Phil Hetzel, Braintrust |
| 170 | **Agentic Evaluations at Scale, For Everybody** | Nicholas Kang & Michael Aaron, Google DeepMind |
| 211 | **Malleable Evals: Why Are We Evaluating Adaptive Systems with Static Tests?** | Vincent Koc, OpenClaw |
| 224 | **Agent Optimization with Pydantic AI: GEPA, Evals, Feedback Loops** | Samuel Colvin, Pydantic |
| 253 | **Why building eval platforms is hard** | Phil Hetzel, Braintrust |
| 283 | **Judge the Judge: Building LLM Evaluators That Actually Work with GEPA** | Mahmoud Mabrouk, Agenta AI |
| 303 | **Build a Prompt Learning Loop** | SallyAnn DeLucia & Fuad Ali, Arize |
| 310 | **Shipping AI That Works: An Evaluation Framework for PMs** | Aman Khan, Arize |
| 332 | **Coding Evals: From Code Snippets to Codebases** | Naman Jain, Cursor |
| 372 | **Five hard earned lessons about Evals** | Ankur Goyal, Braintrust |
| 385 | **Evals Are Not Unit Tests** | Ido Pesok, Vercel v0 |
| 430 | **Strategies for LLM Evals (GuideLLM, lm-eval-harness, OpenAI Evals Workshop)** | Taylor Jordan Smith |
| 472 | **How to run Evals at Scale: Thinking beyond Accuracy or Similarity** | Muktesh Mishra, Adobe |
| 546 | **Turning Fails into Features: Zapier's Hard-Won Eval Lessons** | Rafal Willinski, Vitor Balocco, Zapier |
| 549 | **Evals 101** | Doug Guthrie, Braintrust |
| 551 | **Engineering Better Evals: Scalable LLM Evaluation Pipelines That Work** | Dat Ngo, Aman Khan, Arize |
| 594 | **CI in the Era of AI: From Unit Tests to Stochastic Evals** | Nathan Sobo, Zed |
| 626 | **7 Habits of Highly Effective Generative AI Evaluations** | Justin Muller |
| 664 | **Ensure AI Agents Work: Evaluation Frameworks for Scaling Success** | Aparna Dhinkaran, CEO Arize |
| 666 | **Evaluating Domain Specific LLMs for Real World Finance** | Waseem Alshikh, Writer |
| 705 | **Agent Evals: Finally, With The Map** | — |
| 707 | **Your Evals Are Meaningless (And Here's How to Fix Them)** | — |
| 757 | **Lessons from the Trenches: Building LLM Evals That Work IRL** | Aparna Dhinkaran |
| 814 | **How to Construct Domain Specific LLM Evaluation Systems** | Hamel Husain and Emil Sedgh |

### Knowledge, RAG & Retrieval (~40 videos)

| # | Title | Speaker |
|---|-------|---------|
| 64 | **How we taught agents to use good retrieval** | Hanna Lichtenberg, Mixedbread AI |
| 232 | **Demand-Driven Context: A Methodology for Coherent Knowledge Bases Through Agent Failure** | — |
| 377 | **Multi Agent AI and Network Knowledge Graphs for Change** | Ola Mabadeje, Cisco |
| 477 | **When Vectors Break Down: Graph-Based RAG for Dense Enterprise Knowledge** | Sam Julien, Writer |
| 479 | **HybridRAG: A Fusion of Graph and Vector Retrieval** | Mitesh Patel, NVIDIA |
| 578 | **The State of AI Powered Search and Retrieval** | Frank Liu, MongoDB |
| 583 | **Graph Intelligence: Enhance Reasoning and Retrieval Using Graph Analytics** | Alison & Andreas, Neo4j |
| 585 | **Agentic GraphRAG: Simplifying Retrieval Across Structured & Unstructured Data** | Zach Blumenfeld |
| 647 | **The RAG Stack We Landed On After 37 Fails** | Jonathan Fernandes |
| 682 | **RAG Agents in Prod: 10 Lessons We Learned** | Douwe Kiela, creator of RAG |
| 716 | **The Hidden Costs of Building Your Own RAG Stack** | Ofer, Vectara |
| 792 | **Navigating RAG Optimization with an Evaluation Driven Compass** | Atita Arora and Deanna Emery |
| 857 | **Retrieval Augmented Generation in the Wild** | Anton Troynikov |

### Architecture & Design Patterns (~30 videos)

| # | Title | Speaker |
|---|-------|---------|
| 41 | **Design Patterns for AI Trust: Juries, Libraries, and Agent Tiers** | Alex Bauer |
| 92 | **AI System Design: From Idea to Production** | Apoorva Joshi, MongoDB |
| 188 | **What Breaks When You Build AI Under Sovereignty Constraints** | Bilge Yücel |
| 483 | **UX Design Principles for Semi Autonomous Multi Agent Systems** | Victor Dibia, Microsoft |
| 722 | **The LLM Triangle: Engineering Principles for Robust AI Applications** | Almog Baku |
| 871 | **Building Blocks for LLM Systems & Products** | Eugene Yan |

---

## Tier 4: LOW — Not Directly Relevant (~500 videos)

These videos cover ML training, fine-tuning, computer vision, speech/audio, general business, design, hardware, etc. Not actionable for CutCtx product direction.

**Examples of what's excluded:**
- All "Daniel Han" kernel/RL workshops (#835, 836)
- All computer vision / image gen talks (FLUX, diffusion, video)
- Voice/speech/TTS/Audio content
- Model training, fine-tuning, post-training sessions
- General business/startup keynotes
- Edge device / mobile inference talks
- Finance-specific applications
- Healthcare/biotech applications
- Gaming applications
- Educational content about programming fundamentals

---

## Summary Statistics

| Relevance | Count | % |
|-----------|-------|---|
| HIGH (Tier 1-2) | ~120 | 14% |
| MEDIUM (Tier 3) | ~260 | 30% |
| LOW (Tier 4) | ~500 | 57% |

**Total relevant to CutCtx:** ~380 out of 880 (43%)

---

## Recommended Viewing Strategy

### Sprint 1: Product Foundations (watch now)
1. Make your own event-sourced agent harness — vi-2nasppAg (already done)
2. Your Agents Need a Save Button — bZISsg7H7DA
3. WTF Is the Context Layer? — #17
4. Two Roads to Durable Agents — #215
5. Claude for Long-Horizon Tasks — 9QebvrrY3KY

### Sprint 2: Architecture Decisions
6. From Stateless Nightmares to Durable Agents — #359
7. The Great Loops Debate — c35YoMdnI78
8. Harness Engineering — #278
9. The Multi-Agent Architecture That Actually Ships — #228
10. How we solved Context Management in Agents — #216

### Sprint 3: Adjacent & Integration
11. Agents Need Receipts — Fu45geO3zX8 (Froglet protocol — potential integration)
12. Agents Need Feature Flags — zU4EagB311U (CutCtx Enterprise feature)
13. MCP: Origins and Requests For Startups — #607
14. Deterministic Infra for Non-Deterministic AI Agents — #81
15. 12-Factor Agents — #534

### Sprint 4: Evaluation & Observability (for `cutctx learn`)
16. How agent o11y differs from traditional o11y — #161
17. Your Agent Failed in Prod. Good Luck Reproducing It. — #85
18. Production Evals For Agentic AI Systems — #110
19. Stop Burning Tokens — #52
20. We Cut 94% of AI Coding Tokens — #88

---

## References

- `docs/specs/event-sourced-agent-harness.md` — CutCtx event-sourced agent harness design
- `docs/content/docs/architecture.mdx` — Current CutCtx architecture
- Channel: https://www.youtube.com/@aiDotEngineer/videos
