# Cutctx — Pitch Deck

> Strategy update (2026-07-02): use "context control plane" as the lead framing; keep token savings on proof slides instead of the cover headline.

*Sales deck for pilot / design-partner conversations. Read-only. Mirror of pricing, ROI, and security one-pagers. Aligns with `artifacts/value-proposition.md`, `artifacts/pricing-sheet.md`, `artifacts/roi-calculator.md`, `artifacts/security-one-pager.md`.*

> **Status positioning:** Cutctx is **pilot-ready, not broadly launched** (`audit/final-verdict.md:172`, `audit/release-audit-2026-07-01.md:117`). Lead with proof, not superlatives. Use the ROI + audit links for any marketing claim.

---

## Slide 1 — Cover

**Headline:** *The context control plane for AI agents.*

**Subheadline:** *Govern what reaches the model, attribute spend and savings, and compound shared context across Anthropic, OpenAI, Bedrock, Vertex, and OpenAI-compatible endpoints. No SaaS hop; your prompts stay in your infrastructure.*

**Footer line:** `pip install cutctx-ai && cutctx proxy` — works in 60 seconds.

**Visual:** dashboard screenshot (`dashboard_main.png` in repo root) showing tokens saved + money saved + recent requests.

**Speaker note (30s):** "Cutctx is the local-first context control plane that sits in front of your LLM providers, governs the context your agents see, gives you a single dashboard for attribution and governance, and compounds team context with memory and CCR. Open source, Apache 2.0. We are running a paid pilot program now."

---

## Slide 2 — The problem (what the buyer feels)

**Title:** *Your LLM bill is outpacing your headcount.*

**Three lines, big font:**

1. **Token spend is the new cloud bill.** Fastest-growing line item for AI-native teams; 30%+ month-over-month growth is common.
2. **Tool outputs are 90% of the bill.** Bash logs, RAG passages, JSON arrays, code search results, test output — all sent verbatim to the model.
3. **No governance layer exists between the agent and the model.** Prompts, secrets, and tool results flow through; the platform team has no visibility.

**Speaker note (30s):** "Show this slide and ask: which of these three is the worst for your team? The answer is almost always #2. Let me show you what we measured."

---

## Slide 3 — The numbers (proof before claim)

**Title:** *Measured token reduction on real workloads.*

| Workload | Before | After | Reduction |
|---|---:|---:|---:|
| Code search (100 results) | 17,765 | 1,408 | **92%** |
| SRE incident debugging | 65,694 | 5,118 | **92%** |
| GitHub issue triage | 54,174 | 14,761 | **73%** |
| Codebase exploration | 78,502 | 41,254 | **47%** |
| 100 production logs (FATAL at pos 67) | 10,144 | 1,260 | **87.6%**, 4/4 answers preserved |

*Source: `wiki/index.md:296-301`, `wiki/benchmarks.md:107-118`. Headline example run 4/4 on the FATAL needle case is the most defensible single claim.*

**Caveat (one line below table, small font):** *On short conversational turns, compression is bypassed to preserve latency. Median production compression is 4.8% because most traffic is short. Eligible-workload compression is the relevant comparison.*

**Speaker note (45s):** "These are not synthetic numbers. We ran them on real production-shaped data. The headline number is the 87.6% with zero answer loss on a 100-line log that includes a critical FATAL at the 67th line. The model still found it. Walk the buyer through the table row by row."

---

## Slide 4 — How it works (the elevator pitch)

**Title:** *Three stages on every request.*

```
┌─────────────────┐    ┌────────────────────┐    ┌─────────────────────┐
│ CacheAligner    │ →  │ ContentRouter       │ →  │ Compressor per type │
│ (stabilize      │    │ detect + route to   │    │ JSON/code/log/RAG/  │
│  system prompt) │    │ right algorithm     │    │ search/diff/image   │
└─────────────────┘    └────────────────────┘    └─────────────────────┘
                              ↓
                     ┌────────────────────┐
                     │ CCR (optional)      │
                     │ original stored,    │
                     │ `cutctx_retrieve`   │
                     │ tool to get back    │
                     └────────────────────┘
```

**Speaker note (60s):** "Three stages. First, the cache aligner stabilizes the system prompt so provider prompt caching stays warm. Second, the content router inspects each block — JSON, code, log, RAG, diff, image — and routes it to the right algorithm. Third, the compressor runs. There's an optional fourth stage called CCR — Compress-Cache-Retrieve — that lets the LLM ask for the original if it needs a specific token. The LLM never loses information, the user never sees the bill, and you can audit every byte."

---

## Slide 5 — Coverage matrix (universal)

**Title:** *Works with everything you already run.*

| Provider | Coverage |
|---|---|
| Claude Code / Anthropic | ✅ Native, with subscription-auth support |
| Codex CLI / OpenAI | ✅ Native, with chatgpt-auth detection |
| Google Gemini | ✅ Native, with Cloud Code Assist + Vertex |
| Bedrock | ✅ Native |
| OpenAI-compatible (vLLM, LM Studio, Ollama) | ✅ Passthrough |
| **Agent framework** | |
| LangChain / LlamaIndex / Agno / Strands | ✅ Drop-in wrapper class each |
| LiteLLM | ✅ Callback handler |
| Vercel AI SDK | ✅ Middleware |
| MCP clients | ✅ `cutctx mcp install` |
| **Coding agent** | |
| Claude Code, Cursor, Aider, Copilot CLI, OpenCode, OpenClaw, Codex CLI, Gemini CLI, Windsurf, Zed | ✅ `cutctx wrap <agent>` |

*Source: `wiki/integration-guide.md:7-21`, `wiki/cli.md:32-41`, `artifacts/PRODUCT_CAPABILITY_MATRIX.md:54-72`.*

**Speaker note (30s):** "Whatever your stack is, you don't have to throw it out. Run `cutctx wrap claude` and you're done. One command. No code changes. Same for Codex, Cursor, Aider, Copilot, the others."

---

## Slide 6 — Cost attribution (the CFO answer)

**Title:** *Five sources of savings, never double-counted.*

```
$ Saved by source
  Provider cache:    ████████ $4,200
  Cutctx compression:████████ $11,500
  Semantic cache:    ███      $1,800
  Self-hosted prefix:███      $1,400
  Model routing:     █        $600
                      ──────────
  Total:             $19,500
```

**Invariant:** *Total = sum of per-source tokens, never the difference between raw and optimized.* (`cutctx/savings/types.py:23-30`)

**Speaker note (45s):** "This is the slide for the CFO. We attribute savings to five sources and we never double-count. Provider cache is what you already had. Cutctx compression is what we add. Semantic cache is repeated questions. Prefix cache is the same system prompt. Model routing is 'use a cheaper model for the easy parts.' The dashboard shows the breakdown; the weekly report is a CSV finance can drop into their own tool. Show this exact invariant — it's the line that closes the 'how do I trust this' objection."

---

## Slide 7 — Governance (the CISO answer)

**Title:** *Built for the procurement review.*

| | |
|---|---|
| **Data residency** | Local-first. Your prompts never leave your infrastructure. |
| **Authentication** | SSO via OIDC / SAML (Entra ID, Okta, Google). Per-user RBAC. |
| **Authorization** | 15+ permissions across Viewer / Operator / Admin roles. |
| **Audit** | Tamper-evident hash-chained log. Export as JSON / JSONL. |
| **Retention** | Per-data-class retention controls (audit, logs, episodic memory). |
| **Deployment** | Docker, Helm, Kubernetes. Air-gap supported. |
| **Compliance** | SOC 2 Type I/II (in progress, see `gtm/soc2-roadmap.md`). DPA / MSA templates available. |

*Source: `artifacts/security-one-pager.md:6-22`, `ENTERPRISE.md:9-13, 78-82`.*

**Speaker note (30s):** "This is the slide for the CISO. Local-first means no data leaves your VPC. SSO via your IdP. RBAC. Audit log that you can hand to a regulator. Air-gap option for the most sensitive environments. We have SOC 2 in progress and the templates for DPA / MSA ready to go."

---

## Slide 8 — Pricing (the procurement answer)

**Title:** *Four tiers. Pay for what you use.*

| Tier | Price | Who it's for |
|---|---|---|
| **Builder** | Free | Individual engineers, OSS evaluators |
| **Team** | $18,000 / yr | Engineering team adopting shared AI workflows |
| **Business** | $42,000 / yr | Platform team, multi-project, audit + retention |
| **Enterprise** | $60,000 – $150,000+ / yr | SSO, RBAC, SCIM, air-gap, premium support |

*Annual default. Monthly billing available at +20% premium. Source: `artifacts/pricing-sheet.md:16-150`.*

**Add-ons:** Onboarding Package ($5K), Deployment Hardening ($3K), Premium SLA ($10K/yr), Security Review Support ($7.5K).

**Speaker note (45s):** "Builder is free forever for individual use. Team is what most pilots convert into. Business is for platform teams that need multi-project reporting and audit. Enterprise is for orgs that need SSO, SCIM, retention controls, and air-gap. ROI is documented at 229% to 680% on the listed case studies — show the ROI slide from `artifacts/roi-calculator.md`."

---

## Slide 9 — ROI (the CFO close)

**Title:** *Three illustrative case study examples.*

| Profile | Annual spend | Cutctx tier | Annual value | ROI |
|---|---:|---|---:|---:|
| AI-native Series A–B startup, 10 engineers, ~$12K/mo Anthropic | $144,000 | Team ($18K) | $106,800 | **493%** |
| SRE platform team, 24/7 incident-response agents, ~$25K/mo | $300,000 | Business ($42K) | $198,000 | **680%** |
| Internal AI platform team, 50 engineers, multi-provider, ~$40K/mo | $480,000 | Business ($42K) | $264,000 | **471%** |

*Methodology: token spend × 60–95% eligible-workload reduction × support / governance uplift. Sources: `artifacts/roi-calculator.md:91-143`. Numbers are conservative (lower bound of the 60–95% range).*

**Speaker note (45s):** "Three documented case studies. Numbers are conservative — we used the lower bound of the 60–95% range. Series A AI startup pays $18K, gets back $106K of value. SRE platform team pays $42K, gets back $198K. Internal platform pays $42K, gets back $264K. The buyer picks which profile matches them and we walk through the math."

---

## Slide 10 — Quality (the "but does the model still get the right answer?" objection)

**Title:** *Compression preserves answer quality.*

| Benchmark | Baseline | With Cutctx | Δ |
|---|---:|---:|---:|
| GSM8K | 0.870 | 0.870 | **0.000** |
| TruthfulQA | 0.530 | 0.560 | **+0.030** |
| SQuAD v2 | — | 97% | 19% compression |
| BFCL | — | 97% | 32% compression |
| CCR needle (worst-case) | — | 100% recall | 77% reduction |

*Source: `wiki/benchmarks.md:84-128`, `wiki/index.md:303-311`.*

**Speaker note (30s):** "This is the slide for the engineer who says 'but the model needs the full context.' The answer is: same or better answers, fewer tokens, on the benchmarks that matter. CCR needle 100% means we still find the FATAL in the 100-line log even after 77% reduction. Show this slide whenever you hear 'won't compression hurt quality' — it doesn't."

---

## Slide 11 — Cross-agent memory (the moat)

**Title:** *One memory store, every agent, zero code.*

- **Hierarchical scoping:** USER → SESSION → AGENT → TURN
- **Provenance tracking:** every memory tagged with the agent that produced it
- **Auto-dedup:** >92% cosine similarity triggers merge automatically
- **Anthropic-native tool format:** works with `memory_20250818` and `context-management-2025-06-27` beta headers
- **Verified working end-to-end** in the live proxy audit (`audit/release-audit-2026-07-01.md:27-43`)

*Source: `wiki/memory.md:18-32, 197-292`, `audit/release-audit-2026-07-01.md:27-43`.*

**Speaker note (30s):** "When an engineer in Claude Code finds a useful pattern, the next engineer in Cursor gets it for free. One memory store, every agent. No SDK changes. Auto-dedup means the store doesn't grow forever. This is the moat — every other compression vendor stops at the provider boundary. We go across it."

---

## Slide 12 — Pilot plan (the close)

**Title:** *Two-week pilot, zero risk, defined success criteria.*

**Week 1:** install + baseline
- Day 1: `pip install cutctx-ai && cutctx wrap claude` (or `cutctx wrap codex`) — 15 minutes
- Days 2–7: shadow mode (proxy records savings, doesn't change behavior)

**Week 2:** enabled + measured
- Day 8: enable compression
- Days 8–14: measure

**Success criteria** (from `artifacts/pilot-success-metrics.md:111-167`):
- ≥ 30% token reduction on the buyer's actual workload
- < 5% latency increase P99
- 100% answer parity on the buyer's test suite
- No P0 / P1 incidents

**Speaker note (60s):** "Two weeks. Shadow mode the first week, enabled the second week. We commit in writing to the four success criteria on the right. If we miss any of them, you don't pay the pilot fee. After the pilot, conversion to Team is $18K/year, Business is $42K. The pilot is the no-risk way to prove the value to your CFO before you commit to a year."

---

## Slide 13 — Objection handling (the closer)

**Title:** *Things you'll ask. Answers.*

| Objection | Answer |
|---|---|
| "Doesn't compression hurt quality?" | No. Same or better on GSM8K, TruthfulQA, SQuAD v2, BFCL. CCR needle 100% at 77% reduction. (Slide 10.) |
| "What about data privacy?" | Local-first by default. No SaaS hop. Your prompts never leave your infrastructure. Air-gap option. (Slide 7.) |
| "What if my agent breaks?" | CCR — the model can ask for the original. And compression is bypassed for short messages and tool-call structures. (Slide 4.) |
| "How do I know it's not double-counting?" | Invariant: total = sum of per-source tokens, never the difference between raw and optimized. (Slide 6.) |
| "What about lock-in?" | Apache 2.0. No SaaS. You can self-host, audit, and even disable any module. Your data stays in your VPC. |
| "We already use provider prompt caching." | Provider cache is one of our 5 attribution buckets. You keep that savings; we add 4 more. (Slide 6.) |
| "Our compliance team needs SOC 2." | In progress. See `gtm/soc2-roadmap.md`. DPA and MSA templates ready. |
| "Why not just use Anthropic's native compaction?" | Native compaction is one-shot, lossy, and you lose the cross-provider lens. We do lossless with CCR, plus 4 other savings buckets. |

**Speaker note (30s):** "These are the eight objections we get in every first call. Memorize the table. The most important one is #4 — the invariant. Once the buyer trusts the numbers, the rest follow."

---

## Slide 14 — How to start

**Title:** *Start in 60 seconds.*

```bash
# 1. Install
pip install cutctx-ai

# 2. Wrap your agent
cutctx wrap claude       # or codex, cursor, aider, copilot, ...

# 3. Watch the savings
open http://127.0.0.1:8787/dashboard
```

**For the pilot:**
- Email `pilot@cutctx.dev` with subject "Pilot" — we respond within 24h.
- We pair you with a solutions engineer for the 2-week run.
- Success criteria signed in writing. No ROI = no fee.

**Speaker note (15s):** "That's the close. One install command, one wrap command, one URL. The dashboard is at the URL on screen. If anyone in this room wants a pilot, talk to me in the next 5 minutes or email pilot@cutctx.dev."

---

## Appendix A — Source-of-truth citations

Every claim on every slide traces to one of:
- `wiki/index.md`, `wiki/benchmarks.md`, `wiki/cli.md`, `wiki/memory.md`, `wiki/integration-guide.md`, `wiki/transforms.md`
- `artifacts/value-proposition.md`, `artifacts/pricing-sheet.md`, `artifacts/roi-calculator.md`, `artifacts/security-one-pager.md`, `artifacts/pilot-success-metrics.md`, `artifacts/PRODUCT_CAPABILITY_MATRIX.md`, `artifacts/IMPLEMENTATION_STATUS_CHECKLIST.md`
- `audit/final-verdict.md`, `audit/release-audit-2026-07-01.md`, `audit/PHASE6_REPORT.md`, `audit/production-readiness.md`

## Appendix B — Honest positioning

Cutctx is **pilot-ready, not broadly launched** (`audit/final-verdict.md:172`). The deck is calibrated for pilot / design-partner conversations, not a public marketing event. Two things to avoid:
1. **"Best in market" claims** — recent audits explicitly say local evidence does not support this (`audit/production-readiness.md:158-159`).
2. **Universal compression-ratio claims** — the median production compression is 4.8% because most traffic is short. The 60–95% range applies to *eligible* workloads only.

The defensible claim from `audit/production-readiness.md:215` is:
> "strong structured-data savings and materially smaller benchmarked model footprint than LLMLingua-2 in the local comparison harness."
