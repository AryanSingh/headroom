# Design Partner Outreach Templates

## Target Persona

**VP Engineering or Staff Engineer** at a company with 5-50 engineers actively using Claude Code, Codex, or Cursor. Monthly LLM bill > $2,000.

**Ideal signals:**
- Company blog posts about AI-assisted development
- Open-source repos with AI agent tooling
- Job postings for "AI infrastructure" or "developer tooling"
- Active presence in AI coding communities

---

## 1. Cold Outreach Email

**Subject:** Cut your LLM context costs by 60% — free pilot for your team

Hi [NAME],

I noticed your team is using [Claude Code / Codex / Cursor] for development. Most teams we talk to are spending 3-5x more on LLM tokens than necessary because their context windows are bloated with redundant information.

CutCtx is a context compression layer that sits between your agents and LLM APIs. It strips redundant tokens while preserving everything that matters — and it's fully reversible (zero quality loss).

**What we're offering:**
- Free Team tier ($49/mo value) for 3 months
- Direct input into our roadmap
- Weekly 30-min call to help optimize your workflows

**What we need:**
- Honest feedback on what works and what doesn't
- Permission to publish a case study after the pilot

Our early users are seeing 50-70% token reduction on multi-turn agent sessions. Would you be open to a 15-minute call this week to see if it's a fit?

Best,
[YOUR_NAME]
CutCtx — Context compression for AI agents

---

## 2. Follow-Up Email (Day 7)

**Subject:** Re: Cut your LLM context costs by 60%

Hi [NAME],

Just following up on my note from last week. I know you're busy, so here's the 30-second version:

CutCtx compresses AI agent context by 50-70% with zero quality loss. We're looking for 3-5 design partners to help shape the product.

Free for 3 months. No commitment required.

Would a quick 10-minute demo work better than a call? I can send a Loom walkthrough instead.

Best,
[YOUR_NAME]

---

## 3. Demo Talking Points (15-Minute Call)

1. **The Problem:** AI agents (Claude Code, Codex, Cursor) send massive context windows with redundant information. Every token costs money, and context bloat degrades response quality.

2. **How CutCtx Works:** A transparent proxy layer that sits in front of your LLM APIs. It compresses context before it reaches the model, then decompresses the response. The agent never knows it's there.

3. **Key Differentiator:** CutCtx is the only compression tool that's fully reversible. Other tools (LLMLingua, Morph) delete tokens permanently. CutCtx stores compressed data in a local cache and retrieves it when needed. Zero information loss.

4. **Early Results:** 50-70% token reduction on multi-turn sessions. 10-30% cost reduction on typical agent workflows. Sub-millisecond latency overhead.

5. **What We're Building Next:** Task-aware compression (understands what the agent is working on), semantic deduplication (removes repeated content across sessions), and cost forecasting (predicts spend before it happens).

---

## 4. Design Partner Agreement Terms

### What They Get:
- **Free Team tier** for 3 months ($49/mo value, $147 total)
- **Direct roadmap input** — quarterly planning sessions
- **Priority support** — dedicated Slack channel or email
- **Custom features** — up to 2 feature requests fast-tracked
- **Case study co-authorship** — they approve all content before publication

### What We Get:
- **Weekly 30-minute feedback call** during the pilot
- **Access to anonymized usage data** (compression ratios, error rates)
- **Permission to publish a case study** (with their approval)
- **Logo and quote** for our website (optional but appreciated)
- **First right of refusal** for annual contract at discounted rate

### Terms:
- Pilot starts on [START_DATE] and runs for 90 days
- Either party can end with 2 weeks' notice
- No financial commitment required during pilot
- Data stays on their infrastructure (local-first)
- Provider does not access prompt data or LLM interactions

---

## 5. Email Templates by Persona

### For VP Engineering:
> Focus on cost savings and team productivity. Mention specific dollar amounts if possible.
> "Your team is likely spending $X/mo on context tokens. CutCtx can reduce that by 50-70%."

### For Staff Engineer:
> Focus on technical architecture and integration. Mention zero-config proxy mode.
> "Drop-in replacement for your existing LLM proxy. Same API, 60% fewer tokens."

### For AI/ML Lead:
> Focus on quality preservation and reversibility. Mention the CCR cache.
> "Unlike LLMLingua, CutCtx is fully reversible. Compressed context is cached and retrievable."

---

## 6. Outreach Tracker

| Name | Company | Role | Contact Date | Follow-up | Status | Notes |
|------|---------|------|-------------|-----------|--------|-------|
| | | | | | | |

---

*Review and customize templates before sending. Personalization is key.*
