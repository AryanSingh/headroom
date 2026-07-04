# Neural KV Cache Compaction: Adopting the Baseten STILL Perspective

**Date:** 2026-07-04
**Source:** Charles O'Neill (Baseten) — "The Memory Problem" (Compile 26, 2026)
**Also:** "Towards Infinite Context Windows" / "Still: Amortized KV Cache Compaction" (Baseten Research, Apr-Jun 2026)
**Status:** Analysis & Design
**Author:** Aryan Singh

---

## 1. Executive Summary

This talk is fundamentally different from the other five analyzed. All previous talks addressed **context management at the application layer** — what to load, how to truncate, how to structure memory, what to delegate. Baseten's work addresses **compression at the model architecture layer** — compressing the KV cache tensors inside the LLM during inference.

**STILL** is a neural KV cache compactor: a small Perceiver model (~7M params, ~1% of base model) inserted into each transformer layer that compresses the full KV cache into compact keys and values in a **single forward pass** — milliseconds, not minutes. At 8x compression it retains 85%+ factual accuracy. At up to 200x it still produces coherent results.

**Relevance to Cutctx:** Complementary, not competitive. STILL compresses inside the model. Cutctx compresses before content reaches the model. They operate at different layers of the stack and can be used together. But STILL's existence has strategic implications for Cutctx's long-term positioning: if neural KV compression makes 200x context density feasible, Cutctx's value prop shifts from "enabling long context" toward "reducing cost of long context."

---

## 2. Core Thesis

> *"Current LLMs have a memory problem. Not the kind solved by longer context windows — the kind where an agent forgets everything at the end of a conversation."*

### The Memory Problem, Per Baseten

The KV cache grows linearly with context length. For long-running agents, this means:
- **Inference cost scales linearly** with conversation length — every new token attends over all prior tokens
- **GPU memory fills** — beyond ~128K context, even high-end GPUs run out of capacity
- **Session reset** — when the KV cache overflows, the agent starts fresh (losing all prior context)

Existing solutions have a speed-quality gap:

| Method | Quality | Speed | Limitation |
|---|---|---|---|
| Full KV cache | ✅ Perfect | ❌ O(n) memory, O(n²) attention | Linear scaling |
| Token selection (SnapKV, H2O) | ⚠️ Heuristic | ✅ Fast | Subset-bound — can only select, not synthesize |
| Attention Matching | ✅ Good | ❌ Slow (seconds to hours) | Per-context optimization |
| Cartridges | ✅ Good | ❌ Slow (minutes) | Gradient-based per-context |
| **STILL** | ✅ Good | ✅ **Milliseconds** | Trained once, amortized |

### How STILL Works

```
Standard inference:
  Tokens → Full KV Cache (grows O(n)) → Attention

STILL inference:
  Tokens → Full KV Cache → Perceiver (trained once, frozen LLM)
                            ↓
                    Compact KV (fixed size) → Attention

Compression: A small Perceiver uses learned query vectors to cross-attend
into the full KV cache. Produces compact keys and values in a single
forward pass. LLM is frozen — only Perceiver (~7M params/layer) trains.
```

### Key Results

- **8x compression** in milliseconds, 85%+ factual accuracy retained
- **Up to 200x compression** on Qwen and Gemma models
- **Context lengths**: tested from 8K to 128K
- **RULER benchmark**: exceeds strongest baseline (SnapKV, H2O, KV-Distill) by 8-22 points
- **Repeated compaction**: compress → append new context → compress again — works at fixed memory budget
- **Single forward pass**: no per-context optimization, no gradient steps at inference

### Repeated KV Cache for Long-Running Agents

Baseten's March 2026 follow-up tested the scenario most relevant to agents: can you compress, add new context, and compress again, maintaining a fixed memory budget as information accumulates?

Scenario: 5 patients' medical records arrive sequentially (~12K tokens each). After each arrival, compress accumulated context to fixed budget, answer questions about all patients seen so far.

Result: **True re-compaction** (cache grows incrementally, gets re-compressed) performed nearly as well as **fresh compaction** (re-prefill all text from scratch each time). This validates that an agent can accumulate context indefinitely at a fixed memory budget — as long as the compaction quality holds.

---

## 3. Relationship to the Other Five Talks

This talk operates at a fundamentally different layer:

```
Application Layer (what the other 5 talks address):
┌──────────────────────────────────────────────────────┐
│  What context to load  │  How to structure it         │
│  (Supabase - Skills)   │  (Neo4j - Context Graphs)    │
├──────────────────────────────────────────────────────┤
│  How descriptions fit  │  How session fits window     │
│  (Cloudflare - Code)   │  (Arize - Sub-agents)        │
├──────────────────────────────────────────────────────┤
│  How to store traces   │                              │
│  (Neo4j - Decisions)   │                              │
└──────────────────────────────────────────────────────┘

Model Architecture Layer (this talk):
┌──────────────────────────────────────────────────────┐
│  How KV cache tensors are stored during inference    │
│  (Baseten - STILL neural compression)               │
└──────────────────────────────────────────────────────┘
```

**They are complementary, not competing:**
- Application-layer strategies (Cutctx, Skills, truncation) reduce what enters the KV cache
- Model-layer strategies (STILL) reduce how much space what entered takes up in the KV cache
- A system could use both: Cutctx for input compression + STILL for inference compression

---

## 4. Relevance to Cutctx

### Direct Relevance Assessment

| Dimension | Assessment |
|---|---|
| **Competition** | None. Different layers of the stack. |
| **Complementarity** | High. Input compression + KV compression compound. |
| **Strategic** | High. STILL validates that "context compression" is a crucial infrastructure layer — and shows a path where context becomes effectively unbounded, which changes Cutctx's value prop. |
| **Immediate action** | Low. This is research, not a product Cutctx should build or integrate. |

### Why This Matters for Cutctx (Even Though It's Not Directly Actionable)

**1. Validation of the compression thesis**
Baseten is an inference infrastructure company — they make money serving models efficiently. Their investment in neural KV cache compression is a strong signal that **context compression is a critical bottleneck** in the AI stack. The fact that they're building this at the model layer while Cutctx builds at the input layer independently validates the same thesis from opposite directions.

**2. The value prop shift**

| Scenario | Cutctx Value Prop |
|---|---|
| **Today** (no neural KV compression) | "Fit your context in the window. Without Cutctx, you hit the limit." |
| **Future** (200x KV compression deployed) | "Fit everything. But Cutctx makes it affordable. 200x KV compression × 8x Cutctx compression = 1600x effective density." |

If STILL-like techniques become standard, Cutctx's value prop shifts from **enabling** long context to **optimizing the economics** of long context. The multiplicative effect (both layers compressing independently) makes Cutctx *more* valuable in a world with neural KV compression, not less.

**3. The repeated cache finding validates Cutctx's approach**
Baseten's finding that "compress → append → compress again" works for KV caches mirrors what Cutctx does at the text layer. IntelligentContext scores messages by importance, drops low-value content, and the next turn's compression works on the already-compressed state. Both systems independently converged on the same pattern.

**4. Architectural listening post**
Cutctx should monitor:
- When STILL-like techniques hit production deployment (not just research)
- How they interact with text-level compression (does Cutctx-compressed content compress differently in KV cache?)
- Whether inference providers offer KV cache compaction as a service

### What Cutctx Should NOT Do

- **Do NOT** build neural KV cache compression — that's a model-infrastructure problem, not Cutctx's domain
- **Do NOT** treat STILL as a competitor — different layer, different use case
- **Do NOT** pivot messaging away from "fit in the window" — that's still the dominant pain point today

### What Cutctx Should Do

**A — Update the "layers of compression" narrative**
Position Cutctx as one layer in a multi-layer compression stack. Include KV cache techniques as the inference layer. This makes Cutctx look like a mature platform that understands the full picture, not a tool that will be made obsolete by model improvements.

**B — Track STILL's trajectory**
Set a quarterly check: has STILL been adopted by any major inference provider? Is the quality gap closing? Has anyone benchmarked Cutctx + STILL combined? This determines when (if ever) to update Cutctx's messaging.

**C — Explore combined benchmarks (optional, low effort)**
If Baseten releases STILL as a deployable tool, run a combined benchmark:
- Cutctx alone: X tokens in, Y tokens after compression
- STILL alone: Y tokens in, Z KV cache memory after compaction
- Combined: X tokens → Cutctx → STILL → effective density
- Result: "1600x effective context density" (8x text × 200x KV)

This is a compelling marketing number if reproducible.

---

## 5. Where This Fits: The Full Stack (6 Talks)

```
┌──────────────────────────────────────────────────────────────────────┐
│                      APPLICATION LAYER                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. INSTRUCTION   ← Supabase (Skills + MCP)                          │
│     What context to load                                             │
│                                                                       │
│  2. TOOL           ← Cloudflare (Code Mode)                          │
│     How tool descriptions fit                                        │
│                                                                       │
│  3. SESSION        ← Arize (Sub-agents)                              │
│     How session context fits in window                               │
│                                                                       │
│  4. MEMORY         ← Neo4j K&Z (Context Graphs)                      │
│     Three-layer memory architecture                                  │
│                                                                       │
│  5. DECISION       ← Neo4j Blumenfeld (Decision Traces)              │
│     Structured decision trace storage                                │
│                                                                       │
├──────────────────────────────────────────────────────────────────────┤
│                      INFERENCE LAYER                                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  6. KV CACHE        ← Baseten (STILL) ◄── THIS TALK                   │
│     Neural KV cache compaction                                       │
│                                                                       │
├──────────────────────────────────────────────────────────────────────┤
│                      CUTCTX CONTROL PLANE                              │
│   (text compression · governance · memory · retrieval)                │
│   (sits above, below and across all six layers)                      │
└──────────────────────────────────────────────────────────────────────┘
```

Cutctx spans across all six layers in practice — it compresses input text (layers 1-5) and its memory store persists across sessions (layers 3-5). The KV cache layer (6) is the only one Cutctx doesn't touch — and shouldn't.

---

## 6. Risks & Strategic Considerations

### Risk: "If KV compression makes context effectively infinite, why do I need Cutctx?"

**Answer: Cost.** Even with 200x KV compression, the *input token count* (what you pay for) hasn't changed. Cutctx reduces input tokens 60-90%. If you're running a long-running agent:
- Without Cutctx: 200x KV compression helps you *fit* the context, but you still pay for all the tokens
- With Cutctx: 200x KV compression + 8x input compression = pay for 1/8 the tokens AND fit 200x more in KV cache

The compound effect is multiplicative. KV compression makes Cutctx *more* valuable, not less.

### Risk: "Should Cutctx invest in KV cache integration?"

**No.** This is a model-infrastructure problem. Inference providers (Baseten, Together, Fireworks, Anyscale) are the right owners. Cutctx should:
- Track the space
- Be ready to integrate with providers that offer KV compaction (e.g., proxy headers for `accept-compacted-cache`)
- Not build its own KV cache compaction

### Risk: "What if STILL quality doesn't generalize?"

The community single-GPU reproduction showed slightly lower quality than the paper claims (4.3x vs 4.5x effective on one benchmark). This is normal for research. Cutctx should treat STILL as directional validation, not a deployable dependency.

---

## 7. Success Metrics

| Metric | Current Status | Target |
|---|---|---|
| Cutctx + KV compression narrative | Not documented | Included in product guide |
| STILL tracking | Not tracked | Quarterly check-in |
| Combined benchmark (Cutctx × STILL) | Not run | Ready to run if STILL becomes deployable |
| KV cache integration in proxy | Not planned | Monitor; design doc if providers add support |

---

## 8. Recommendation

**Do not build anything. Do track and position.**

This talk is the only one of the six where the right response is **monitoring, not implementation**. STILL is research-stage, operates at a different layer, and is best owned by inference infrastructure providers. Cutctx's response should be:
1. Update the narrative to include KV cache compression as a complementary layer
2. Track STILL's production trajectory quarterly
3. Be ready to run combined benchmarks if it becomes deployable
4. Do not invest engineering time

---

## 9. References

- Talk: "The Memory Problem" — Charles O'Neill, Baseten (Compile 26, 2026)
- Baseten Research: "Towards Infinite Context Windows: Neural KV Cache Compaction" (Apr 2026)
- Baseten Research: "STILL: Amortized KV Cache Compaction in a Single Forward Pass" (Jun 2026)
- Baseten Research: "Repeated KV Cache for Long-Running Agents" (Mar 2026)
- Community reproduction: github.com/shreyansh26/STILL-Towards-Infinite-Context-Windows
- Paper: "STILL: Amortized KV Cache Compaction in a Single Forward Pass" — arXiv:2606.07878
- Earlier adoption analyses (all in `docs/superpowers/specs/`):
  - `2026-07-04-subagent-context-management-adoption.md` (Arize)
  - `2026-07-04-skills-mcp-context-graphs-adoption.md` (Supabase + Neo4j K&Z)
  - `2026-07-04-mcp-mega-context-problem-adoption.md` (Cloudflare)
  - `2026-07-04-decision-traces-adoption.md` (Neo4j Blumenfeld)
