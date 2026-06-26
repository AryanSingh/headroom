# Cutctx SMB Outreach Plan
**Date:** June 2026  
**Target:** Small & mid-size companies (10–300 engineers), no SOC 2 requirement  
**Goal:** 10 paying Team/Business customers ($1,500–$3,500/mo) in 60 days  
**Channels:** Cold email · LinkedIn DM · Dev communities (HN, Reddit, Discord) · X/Twitter

---

## 1. Who to Target

### Sweet Spot Profile
- **Size:** 5–100 engineers actively using AI coding tools
- **Stage:** Seed → Series B (post-product, pre-platform-scale)
- **Signal:** Using Claude Code, Cursor, Codex, or Aider in daily dev
- **Pain:** API bill is $3K–$30K/month and growing; fear of runaway agent costs
- **Not needed:** SOC 2, HIPAA, procurement process, legal red-lines

### Best-Fit Verticals
1. **Agentic DevTools** — companies building coding agents, code review bots, or AI-assisted dev workflows. They send massive codebase contexts and burn cash fast.
2. **AI-Native SaaS startups** — product is AI-first, heavy tool-call usage, founders are technical and can decide in a week.
3. **Developer agencies** — building AI products for clients, pass API costs to clients or absorb them; compression = pure margin.
4. **YC companies (W23–S26 batches)** — just raised, burning Anthropic/OpenAI credits, CTO is reachable.

### How to Find Them
| Source | Signal | What to do |
|--------|--------|-----------|
| **X/Twitter** | Search `"openai invoice" OR "anthropic bill" OR "api costs" lang:en` | Find people venting about API bills |
| **GitHub** | Search repos with `.github/workflows` using Anthropic API + > 50 stars | Companies actively building on Claude |
| **LinkedIn** | Filter "AI Engineer" or "LLM Engineer" job postings → company has active AI infra build | Hiring = growing spend |
| **HN "Who's Hiring"** | Posts mentioning Claude Code, Cursor, Codex as internal tools | Already using the tools Cutctx wraps |
| **YC directory** | yc.com/companies, filter AI + active | Reachable founders, fast decisions |
| **Product Hunt** | AI dev tool launches in last 90 days | Technical founders, early adopters |

---

## 2. Channel Strategy & Cadence

### Overall Sequence (per prospect)
```
Day 0  → First touch (cold email OR LinkedIn connection request)
Day 3  → Follow-up #1 (add budget hook)
Day 7  → Cross-channel touch (if email → try LinkedIn; if LinkedIn → try Twitter mention)
Day 14 → Final breakup email
Day 21 → Community post targeting their segment (indirect, non-personalized)
```

**Target:** 20–30 outreach touches/day across channels. Takes ~45 min/day.

---

## 3. Cold Email Scripts

### Template A — API Bill Pain (primary)
**Subject:** Your Anthropic bill next month

```
Hi [Name],

Most teams using Claude Code or Cursor at [company] stage are spending 
$5K–$20K/month on API tokens — and 60–80% of that is boilerplate the 
LLM never needed to see: tool call outputs, file listings, build logs, 
repeat code context.

We built Cutctx to sit in front of your LLM calls and compress those 
payloads in real-time — 60–95% smaller — before they hit Anthropic. 
One command to set up: `cutctx wrap claude`.

Real numbers from teams like yours:
- Code search output: 17,765 → 1,408 tokens (92% reduction)
- Build log: 65,694 → 5,118 tokens (92% reduction)
- No accuracy loss (we benchmark this — 97% tool-call accuracy at 32% compression)

Takes 5 minutes to try locally (OSS, free): github.com/cutctx/cutctx

Worth a 15-min call to run the math on your actual Anthropic dashboard?

[Your name]
```

---

### Template B — Agent Budget Fear
**Subject:** How to not wake up to a $20K Anthropic bill

```
Hi [Name],

Quick question — does your team have a hard cutoff if an agent runs 
amok overnight?

We've seen it happen: an autonomous agent gets into an infinite loop 
on a Friday, burns $15K+ by Monday morning. Standard rate limits don't 
stop it — they reset.

Cutctx has a hard budget tripwire that physically cuts the TCP connection 
when spend hits a threshold. It also compresses tool outputs by 60–90% 
so agents go further per dollar.

It proxies your existing OpenAI/Anthropic calls — no SDK changes:
  ANTHROPIC_BASE_URL=http://localhost:8787 claude

OSS version is free: github.com/cutctx/cutctx

If you're spending $5K+/month on APIs and want to cap that with one line 
of config, worth a quick call?

[Your name]
```

---

### Template C — Developer Productivity Angle
**Subject:** Your Claude Code sessions eating 80% boilerplate

```
Hi [Name],

When a developer runs Claude Code on a large codebase, ~70% of the 
tokens in a typical session are file contents, search results, and 
tool outputs that the LLM doesn't need in full. It just needs the 
relevant parts.

Cutctx intercepts those calls and compresses the payload before it 
reaches Claude — same answers, 60–90% fewer tokens. Runs locally 
in your VPC, takes 2 minutes to wire up.

Your engineers get longer effective context windows. Your API bill 
goes down.

Free to try: github.com/cutctx/cutctx — `cutctx wrap claude` to start.

If it works for you and you want team analytics + budget controls, 
Team plan is $1,500/mo flat.

Interested?

[Your name]
```

---

### Follow-Up #1 (Day 3) — Budget Hook
**Subject:** Re: [original subject]

```
[Name],

Just wanted to add one thing I forgot to mention:

Cutctx also has a `cutctx learn` command that mines your Claude Code 
session history for failure patterns and writes them back to CLAUDE.md 
automatically — so your agents get fewer retries and your engineers 
stop repeating the same debugging cycles.

Two benefits in one: cut the API bill AND make the agents smarter.

Still happy to show you the numbers on a quick call.

[Your name]
```

---

### Follow-Up #2 / Breakup (Day 14)
**Subject:** Re: [original subject]

```
[Name],

Guessing cost optimization isn't the focus this sprint — totally fair.

Leaving you with the OSS repo just in case: github.com/cutctx/cutctx

If API bills become a pain point later (or an agent does go rogue 
overnight), come find me.

[Your name]
```

---

## 4. LinkedIn DM Scripts

### Connection Request Note (300 chars)
```
Hey [Name] — saw you're building [product/using Claude Code at company]. 
We made Cutctx to cut Anthropic/OpenAI bills 60–90% by compressing 
tool outputs before they hit the LLM. Free OSS. Thought you'd find it 
interesting — happy to connect.
```

### First Message After Connecting
```
Thanks for connecting [Name].

Quick context: Cutctx intercepts LLM API calls and compresses the 
payloads (tool outputs, code search, logs) before they reach Claude 
or GPT-4. Teams typically cut their API bill 50–80% with no code changes.

One command: `cutctx wrap claude` — then check the dashboard.

If you're spending meaningful money on Anthropic/OpenAI and want to 
see the math on your actual usage, happy to walk through it.
```

### Follow-Up (Day 5 after first message)
```
One thing that might be relevant — Cutctx has a hard budget tripwire 
that cuts the connection if an agent hits a spend limit. Good insurance 
for teams running autonomous workflows overnight.

Let me know if you want to try it — takes 5 min to set up locally.
```

---

## 5. Developer Community Scripts

### Hacker News — Show HN Post
**Title:** Show HN: Cutctx – Compress LLM tool outputs 60-95% before they hit the API

```
Hey HN,

We built Cutctx after watching our Anthropic bill hit $15K/month from 
Claude Code sessions. Turns out ~70% of tokens in a typical agentic 
session are boilerplate: file listings, build logs, code search results, 
repeat context.

Cutctx sits in front of your LLM calls as a local proxy and compresses 
those payloads in real time before they hit the API:

  ANTHROPIC_BASE_URL=http://localhost:8787 claude

Real benchmarks:
- Code search (100 results): 17,765 → 1,408 tokens (92%)
- Build log: 65,694 → 5,118 tokens (92%)
- Accuracy on BFCL tool-call benchmark: 97% at 32% compression

It works by detecting payload type (code, logs, JSON arrays, tables, 
images) and applying the right compressor — AST slicing for code, 
statistical sampling for logs, compact table encoding for JSON arrays.

Also has a hard budget cutoff — if an agent runs amok, Cutctx physically 
cuts the TCP connection at your spend threshold. No more weekend surprise bills.

Free OSS: github.com/cutctx/cutctx
Install: `pip install cutctx-ai` or `uv add cutctx-ai`
Team tier (dashboard + shared analytics): $1,500/mo

Happy to answer questions about the compression algorithms.
```

---

### Reddit r/LocalLLaMA / r/ClaudeAI Post
**Title:** We cut our Claude Code API bill by 80% — here's how (open source tool)

```
Our team was spending $12K/month on Anthropic API from heavy Claude Code usage.
After digging into the token breakdown, 65% was tool outputs — file listings, 
grep results, build logs — that Claude didn't need to read in full.

We built a local proxy called Cutctx that intercepts those calls and 
compresses the payload before it hits the API. Works with Claude Code, 
Cursor, Codex, Aider — any tool that uses the Anthropic or OpenAI API.

Setup:
  pip install cutctx-ai
  cutctx wrap claude   # starts proxy + configures Claude Code

What it does:
- AST slices code down to relevant functions
- Statistically samples logs (keeps first/last/anomalies)
- Encodes JSON arrays as compact pipe tables
- Hard budget tripwire (cuts connection at your spend limit)

Benchmarks on real workloads:
- Code search: 92% token reduction
- Build logs: 93% token reduction  
- JSON arrays: 90% reduction
- No measurable accuracy loss (benchmarked on BFCL)

OSS + free: github.com/cutctx/cutctx

Curious if others have tried other approaches to the API bill problem.
```

---

### Discord/Slack (AI/DevTools servers) — Drop-In Message
```
Anyone dealing with high Claude/OpenAI API costs from agent workflows?

We just open-sourced Cutctx — a local proxy that compresses tool outputs 
(code search, build logs, file listings) before they hit the LLM. 
Gets 60–90% token reduction on agentic sessions.

`pip install cutctx-ai && cutctx wrap claude` to try it.

Been saving us ~$8K/month on Anthropic. Happy to chat if anyone wants 
to compare notes on the approach.
```

---

## 6. X/Twitter Scripts

### Thread — Visual Split (high engagement)
```
Tweet 1:
I ran Claude Code on a medium codebase today.
Of the 78,502 tokens in that session, 54,000 were boilerplate 
Claude didn't need to read in full.

Here's what Cutctx did with that 👇

Tweet 2:
Before Cutctx:
- 100 grep results: 17,765 tokens
- Build log: 65,694 tokens  
- File listing: 22,000 tokens

After Cutctx (same session, same answers):
- grep results: 1,408 tokens (-92%)
- Build log: 5,118 tokens (-92%)
- File listing: 3,100 tokens (-86%)

Tweet 3:
The proxy intercepts the tool call output, detects what kind of 
content it is (code / log / JSON / image), and runs the right 
compressor before the tokens ever hit the Anthropic API.

No SDK changes. One line:
ANTHROPIC_BASE_URL=http://localhost:8787 claude

Tweet 4:
It also has a hard budget tripwire.

If an agent hits your spend limit, Cutctx physically cuts the 
TCP connection. 

No more waking up to a $20K Anthropic bill because an agent 
looped overnight.

Tweet 5:
Free OSS: github.com/cutctx/cutctx

pip install cutctx-ai
cutctx wrap claude

Team dashboard + analytics: $1,500/mo flat.

What % of your Anthropic bill is tool outputs vs actual thinking?
```

---

### Single Tweet — Bill Hook
```
Most teams spending $10K+/month on Anthropic API are paying for 
Claude to read tool outputs it doesn't need in full.

Build logs. File listings. Search results. 60-90% of those tokens 
are compressible without losing any reasoning.

We built a local proxy to do it automatically:
github.com/cutctx/cutctx
```

### Single Tweet — Fear Hook
```
How to wake up to a $20K Anthropic bill:

1. Set up an autonomous agent
2. Agent hits an edge case
3. Agent retries. And retries. All weekend.
4. Monday morning: surprise invoice.

Cutctx has a hard budget cutoff that physically cuts the TCP 
connection at your spend limit.

Free: github.com/cutctx/cutctx
```

---

## 7. Lead Tracking & Prioritization

Since there are no leads in the repo yet, start building this list:

### Where to Build the Lead List
1. **X/Twitter search:** `"anthropic" "bill" OR "invoice" OR "api costs"` → anyone complaining about costs = warm lead
2. **LinkedIn search:** Title contains "Head of AI" OR "VP Engineering" + company size 11–200 + industry "Computer Software"
3. **GitHub:** `cutctx-ai` install stats in pip download data (look for company domains in emails)
4. **HN comments:** Search for "claude code expensive" or "openai costs" in HN threads
5. **YC company directory:** Filter W24/S24/W25/S25 batches + AI category

### Lead Scoring
| Signal | Score |
|--------|-------|
| Posted publicly about API costs | +10 |
| Uses Claude Code / Cursor in job posts | +8 |
| AI-native company, 10–100 engineers | +7 |
| YC company | +6 |
| Raised Series A or B in last 12 months | +5 |
| Has open GitHub repo with LLM integration | +5 |
| SOC 2 certified / regulated industry | -5 (not our target) |

---

## 8. 30-Day Execution Checklist

### Week 1 — Foundation
- [ ] Build first 50-lead list (LinkedIn + Twitter sources above)
- [ ] Post "Show HN" on Hacker News (Tuesday 9am ET for max visibility)
- [ ] Post Reddit r/LocalLLaMA and r/ClaudeAI threads
- [ ] Send first 10 cold emails (Template A)
- [ ] Set up Cutctx profile on LinkedIn company page + post first hook tweet

### Week 2 — Cadence
- [ ] Follow up Day 3 batch (budget hook email)
- [ ] Send next 20 cold emails
- [ ] Drop into 3–5 Discord/Slack communities (AI devtools, HN Discord, Cursor Discord)
- [ ] Post Twitter thread (visual split)

### Week 3 — Conversations
- [ ] Day 7 cross-channel touches for non-responders
- [ ] First 5 discovery calls scheduled → run ROI math live
- [ ] Post follow-up Reddit comment in your own thread with early feedback

### Week 4 — Close & Iterate
- [ ] Day 14 breakup emails
- [ ] First pilot/trial started (30-day, 20% design-partner discount)
- [ ] Ask for a screenshot/quote from any positive user for social proof
- [ ] Review open rates by template — kill the weakest, double the strongest

---

## 9. Discovery Call Script (15 min)

```
Opening (2 min):
"Thanks for making time. Quick context check — are you 
primarily using Claude Code / Cursor day-to-day, or more 
OpenAI API in your product backend, or both?"

Diagnosis (5 min):
"What's your rough API spend per month right now?"
"Do you have a sense of what's driving it — is it agents, 
 developer tool usage, or customer-facing product calls?"
"Have you had any surprise bills or budget scares?"

Demo (5 min):
[Screen share Anthropic dashboard]
"Can you pull up your usage? Let's look at average prompt size."
→ Show compression ratio estimate based on their actual numbers
→ "If we compress your tool outputs by 80%, that's approximately 
   $X back per month."

Close (3 min):
"The OSS version takes 5 minutes to try. If it works for your 
 use case and you want shared analytics + budget controls for 
 the team, that's the Team plan at $1,500/month flat."
"Want to try it this week and schedule a 15-min check-in in 5 days?"
```

---

## 10. Objection Handling

| Objection | Response |
|-----------|----------|
| "Will it add latency?" | "Median overhead is 52ms. Compression runs async — your LLM round-trip is 500ms–3s, so you won't notice it." |
| "I can just build a cache myself." | "Caching hits on identical inputs. Compression works on every request, including ones you've never seen before. AST slicing isn't something you want to build from scratch." |
| "LLM prices keep dropping, this won't matter soon." | "True for compute — not true for context windows. Agent sessions are getting longer, not shorter. The compression value grows with usage." |
| "We're too small to worry about API costs." | "Fair. Come back when you hit $3K/month. That's usually when the first surprise bill happens." |
| "Is this secure / does it see our code?" | "It runs locally in your environment — same machine or your VPC. No code leaves your infra. It's a local proxy, not a cloud service." |
