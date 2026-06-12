# Headroom Outreach Sequences & Prospect Tracker

**Date:** June 13, 2026  
**Purpose:** Design-partner acquisition system

---

## Target Roles

| Role | Why | Where to Find |
|------|-----|---------------|
| Head of Engineering | Budget owner, cares about team productivity | LinkedIn, company pages |
| AI Platform Lead | Building agent infrastructure | LinkedIn, AI meetups |
| Staff/Principal Engineer (AI Infra) | Technical evaluator, internal advocate | GitHub, HN, Twitter |
| Developer Productivity Lead | Owns agent tooling for the org | LinkedIn, DevEx communities |
| Founder/CTO (AI-native startup) | Direct buyer, fast decision | Twitter, YC network |
| VP Engineering | Budget + strategic buyer | LinkedIn |

---

## Outreach Sequence

### Touch 1: Short Intro (Day 1)

**Channel:** Email or LinkedIn DM  
**Goal:** Create relevance quickly

**Template — Engineering Leader:**

> Subject: reducing agent context cost without changing your workflow
>
> Hi {{Name}},
>
> I noticed your team is using {{Agent}} for {{use_case}}. One pattern we see across teams running AI agents is that tool outputs, logs, and search results bloat context fast — often 60-90% of tokens are verbose payloads that could be compressed without losing information.
>
> We built Headroom, a local-first proxy that compresses those payloads by 60-95% before they hit the LLM. Same answers, fraction of the cost. Zero code changes — just point your proxy at it.
>
> Would it be worth a 15-minute call to see if this could save your team money?
>
> Best,  
> {{Sender}}

**Template — Platform Team:**

> Subject: cross-provider context optimization for your agent platform
>
> Hi {{Name}},
>
> Building agent infrastructure across multiple providers (Anthropic, OpenAI, Bedrock) usually means managing context optimization separately for each one.
>
> We built Headroom — a single proxy layer that compresses context across all providers, with reversible retrieval so nothing is lost. Teams running it typically see 60-95% token reduction on tool outputs and logs.
>
> Happy to show you how it works in a short call.
>
> Best,  
> {{Sender}}

**Template — AI-Native Startup:**

> Subject: cutting your LLM bill by 60-90%
>
> Hi {{Name}},
>
> Building with {{Agent}} is great until you see the token bill. Tool outputs and context chains compound fast.
>
> Headroom compresses those payloads by 60-95% with zero code changes. It's local-first, reversible, and works with Claude, GPT, Gemini, and Bedrock.
>
> Free to try — would love to hear if it's useful for your team.
>
> Best,  
> {{Sender}}

---

### Touch 2: Technical Proof (Day 4)

**Channel:** Email or LinkedIn DM  
**Goal:** Show credibility

**Template:**

> Subject: quick example of where Headroom helps
>
> Hi {{Name}},
>
> Following up — here's a concrete example of what Headroom does:
>
> A team running code search through Claude Code was sending 17,765 tokens per search result batch. Headroom compressed that to 1,408 tokens — a 92% reduction — with identical output quality.
>
> It works by detecting content type (JSON, code, logs, diffs) and applying the right compressor. Originals are stored locally for retrieval if the LLM needs them.
>
> If useful, I can share:
> - A 2-minute demo video
> - The benchmark methodology
> - How deployment works (usually <30 minutes)
>
> Best,  
> {{Sender}}

---

### Touch 3: ROI Angle (Day 8)

**Channel:** Email  
**Goal:** Move from curiosity to project

**Template:**

> Subject: estimated savings for {{Company}}
>
> Hi {{Name}},
>
> Based on what I know about teams using {{Agent}}, here's a rough estimate for {{Company}}:
>
> - If your team makes ~{{X}} tool-output requests/day
> - At ~{{Y}} tokens each
> - That's ~{{Z}}M tokens/month on tool outputs alone
> - At $3/M input tokens, that's ~${{cost}}/month
> - Headroom typically compresses that by 70-85%
> - Estimated savings: **${{savings}}/month**
>
> We offer a 14-day pilot with measurable success criteria. If it works, great. If not, you've lost nothing.
>
> Would it be worth 20 minutes to walk through the pilot structure?
>
> Best,  
> {{Sender}}

---

### Touch 4: Breakup / Close (Day 14)

**Channel:** Email  
**Goal:** Force a clear yes/no

**Template:**

> Subject: last note on Headroom
>
> Hi {{Name}},
>
> I've reached out a few times about Headroom — a local-first context optimization layer for AI agents.
>
> Quick summary of what it does:
> - Compresses tool outputs, logs, and search results by 60-95%
> - Works across Anthropic, OpenAI, Google, Bedrock
> - Reversible — originals stored locally for retrieval
> - Local-first — no data leaves your infrastructure
>
> If the timing isn't right, no worries at all. Feel free to reach out whenever it makes sense.
>
> If you'd like to explore, I'm here for a quick call.
>
> Best,  
> {{Sender}}

---

## LinkedIn DM Templates

### Connection Request

> Hi {{Name}} — I'm building Headroom, a context optimization layer for AI agents. Would love to connect and share what we're seeing across teams running Claude Code and Codex.

### Follow-up DM

> Hey {{Name}}, thanks for connecting. Quick question — does your team use AI coding agents? We're seeing teams save 60-90% on tool output tokens with a local proxy layer. Happy to share more if relevant.

---

## Community Outreach

### Hacker News (Show HN)

> **Show HN: Headroom – 60-95% fewer tokens for AI agents, reversible, local-first**
>
> We built a context compression layer that sits between AI agents and LLM providers. It detects content type (JSON, code, logs, diffs, search results) and applies the right compressor. Originals are stored locally for retrieval.
>
> Key features:
> - Rust core, sub-millisecond compression
> - 6 algorithms + multimodal support
> - Reversible (CCR) — originals retrievable on demand
> - Local-first — no data leaves your infrastructure
> - Works with Claude Code, Cursor, Codex, Copilot, and any OpenAI-compatible client
>
> Benchmarks: 92% on code search, 92% on SRE incident debugging, 73% on GitHub issue triage.
>
> Apache 2.0. Would love feedback.

### Twitter/X Thread

> 1/ AI agents burn tokens on verbose tool outputs, logs, and search results. We measured: 60-90% of context is compressible payloads.
>
> We built Headroom to fix this. Here's what it does 🧵
>
> 2/ Headroom sits between your agent and the LLM. It detects content type and applies the right compressor:
> - JSON → SmartCrusher (92%)
> - Code → CodeCompressor (AST-aware)
> - Logs → LogCompressor (90%)
> - Diffs → DiffCompressor (73%)
>
> 3/ The key difference: it's reversible. Originals are stored locally and retrievable on demand. No quality loss.
>
> 4/ It's local-first. Your prompts never leave your infrastructure. No SaaS, no external API calls.
>
> 5/ Works with Claude Code, Cursor, Codex, Copilot, and any OpenAI-compatible client. One proxy, all providers.
>
> 6/ Try it: `pip install headroom-ai` then `headroom wrap claude`. 60 seconds to first savings.
>
> GitHub: github.com/chopratejas/headroom

---

## Prospect Tracker Template

| Company | Agent Stack | Monthly Spend | Likely Buyer | Champion | Pain | Urgency | Status | Last Touch | Next Step |
|---------|------------|---------------|--------------|----------|------|---------|--------|------------|-----------|
| [Company] | Claude Code + Cursor | $15k | VP Eng | [Name] | Tool output bloat | High | Contacted | 2026-06-15 | Follow up 6/19 |
| [Company] | Codex + Copilot | $8k | AI Platform Lead | [Name] | Cross-provider context | Medium | Discovery scheduled | 2026-06-14 | Call 6/17 |

---

## Discovery Call Rubric

### Must-Ask Questions

1. **Current stack:** What agents and providers do you use?
2. **Monthly spend:** What's your approximate monthly LLM spend?
3. **Pain:** What's your biggest pain with agent context today?
4. **Tool outputs:** How large are your tool outputs on average?
5. **Security:** Do you have any security or compliance requirements for deployment?
6. **Timeline:** When do you need this solved?
7. **Budget:** Is there budget allocated for this?
8. **Decision process:** Who else needs to be involved?

### Scoring Criteria

| Criterion | Score 1-5 | Threshold |
|-----------|-----------|-----------|
| Pain severity | | ≥3 |
| Budget | | ≥3 |
| Urgency | | ≥3 |
| Technical fit | | ≥4 |
| Reference potential | | ≥2 |
| **Total** | | **≥15/25** |

**Decision:**
- 20-25: Priority pilot candidate
- 15-19: Good pilot candidate
- 10-14: Nurture, revisit in 3 months
- <10: Pass

---

## Objection Log Template

| Objection | Frequency | Response | Updated |
|-----------|-----------|----------|---------|
| "We already use provider caching" | Common | [See value proposition] | 2026-06-13 |
| "We don't want another SaaS" | Common | [Local-first pitch] | 2026-06-13 |
| "Our spend isn't that high" | Occasional | [ROI calculator] | 2026-06-13 |
| "Worried about quality" | Occasional | [CCR + safety story] | 2026-06-13 |
