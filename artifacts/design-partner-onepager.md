# Headroom — Design Partner One-Pager

**The context, cost, and governance layer for AI agents.** Cut agent token spend 60–95%, keep the same answers, and finally see and control what your agents cost — across every provider, without your prompts leaving your infrastructure.

---

## The problem

Teams now run multiple AI coding/agent tools (Claude Code, Cursor, Codex, Aider, internal agents). Three things hurt:

1. **Cost** — tool outputs, logs, RAG chunks, and file dumps balloon every prompt. You pay for tokens the model didn't need.
2. **No visibility or control** — nobody can say what each team/project/agent/model actually costs, or cap it.
3. **Lock-in & exposure** — provider-native caching only helps inside one provider, and assumes you're fine sending everything to them.

## What Headroom does

A drop-in proxy (zero code changes) — or library / CLI wrap / MCP server — that compresses everything your agent reads *before* it hits the model, and keeps the original retrievable on demand (reversible, so it's safe for coding agents).

- **60–95% fewer tokens**, same answers — verified on real agent workloads.
- **Cross-provider** (Anthropic, OpenAI, Bedrock, Vertex, any OpenAI-compatible) — one layer, not provider-locked.
- **Local-first** — prompts stay on your infrastructure; **no telemetry egress by default**.
- **Reversible (CCR)** — originals cached locally; the agent pulls back any dropped span if it needs it.

## Proof (representative agent workloads)

| Workload | Before | After | Savings |
|---|--:|--:|--:|
| Code search (100 results) | 17,765 | 1,408 | **92%** |
| SRE incident debugging | 65,694 | 5,118 | **92%** |
| GitHub issue triage | 54,174 | 14,761 | **73%** |
| Codebase exploration | 78,502 | 41,254 | **47%** |

Accuracy preserved on standard benchmarks (e.g. GSM8K: **±0.000** vs baseline). *Your pilot measures your own numbers — see below.*

## What's new (and hard to copy)

- **Live spend ledger** — token + dollar spend *and savings* broken out per org / workspace / project / agent / model, with CSV export for finance.
- **Policy guardrails** — per-team budgets (block or auto-compress on breach), model allowlists, rate limits — enforced at the proxy.
- **Memory that compounds** — `headroom learn` turns failed agent sessions into corrections your whole team's agents reuse; we **measure the success-rate lift** it produces.
- **Tamper-evident audit + SSO/RBAC** — exportable for security review and SOC 2.

## The design-partner offer

A **free, fully instrumented 2-week pilot** (extendable to 30 days):

- We deploy the proxy in front of one team's agent traffic — **zero code changes**, runs in your infra/VPC.
- We agree success criteria up front (token savings, latency, quality, $ saved).
- You get a **spend dashboard + a written ROI report** with *your* actual numbers at the end.
- **You keep all the data.** Local-first; nothing leaves your environment.
- In exchange: a 30-minute kickoff + a debrief, and — if the numbers are good — a reference/case study (your call) and **founding-customer pricing**.

## Illustrative ROI (your pilot produces the real figure)

> Team of 8 agents, ~$15k/mo LLM spend, ~70% of tokens in compressible tool output → **~$6–9k/mo** direct token savings at observed ratios, before counting fewer context-limit retries and the governance value. *Illustrative only — the pilot measures yours.*

## Who this is for

Platform / AI-infra / developer-productivity leaders at teams running **3+ AI agents** who feel the cost and have no cross-team visibility.

**Next step:** a 30-minute call to scope a 2-week pilot. → hello@headroomlabs.ai

<sub>Headroom runs local-first; network telemetry is off by default and opt-in. Apache-2.0 core; enterprise control plane under commercial license.</sub>
