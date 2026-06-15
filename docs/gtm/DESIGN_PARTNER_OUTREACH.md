# CutCtx Design Partner Outreach

## 1. Cold Outreach Email

### Subject Lines (A/B Test)

- **A:** "Your LLM API bill — quick question"
- **B:** "Cutting Claude Code spend at [Company] — 60 seconds"

### Body

Hi [First Name],

LLM API bills at AI-heavy teams can spiral fast — $2–5K/month before you've even noticed. Most of it is repeated context getting sent with every request.

We built CutCtx: a transparent proxy that sits between your agents and the Claude/OpenAI APIs and compresses context 60–95%. Nothing changes in your code. No data leaves your infra.

A few teams are already running it in prod and cutting token spend by more than half. We're looking for 5 design partners to shape the roadmap — free access in exchange for honest feedback.

Would a 20-minute call be worth it to see if the math works for your stack?

[Your Name]

---

## 2. Follow-up Email (Day 7, No Response)

### Subject: Re: Your LLM API bill — quick question

Hi [First Name],

Following up on my note from last week.

Quick math worth running: if your team pushes 10M tokens/month at $3/M, that's $30K/year. CutCtx typically cuts that 60–95%.

I put together a 2-minute walkthrough here: [Loom/Doc link]

Happy to dig into your specific numbers if it's relevant.

[Your Name]

---

## 3. LinkedIn DM

Hi [First Name] — noticed [Company] is shipping a lot with Claude/Codex. Curious what your monthly token spend looks like. We built a compression proxy that's cutting API costs 60–95% for teams like yours. Worth a quick chat?

---

## 4. Intro Call Agenda (20 minutes)

**Goal:** Understand their pain, show real compression, and present the design partner offer.

| Time | Topic | Notes |
|------|-------|-------|
| 0–3 min | **Their LLM usage today** | What are they building? Rough monthly token spend? Which APIs (Claude, OpenAI, Codex, Cursor)? |
| 3–8 min | **Live compression demo** | Run a real request through CutCtx — show before/after token counts. Use their stack if possible (Claude Code, agent loops, etc.). |
| 8–13 min | **The design partner offer** | Walk through what they get and what we ask (see Section 5). Emphasize: free Team tier, direct roadmap input, no obligation after 12 months. |
| 13–17 min | **Their questions** | Let them drive. Common ones: data privacy, latency overhead, integration complexity, what "anonymized metrics" means. |
| 17–20 min | **Next steps / access** | If interested: send agreement, provision seats, schedule first weekly call. If not sure: send doc, follow up in 3 days. |

---

## 5. Design Partner Agreement Terms

*Plain English — no legalese.*

### What You Get

- **Free CutCtx Team license (5 seats) for 12 months** — that's ~$2,940 at list price, on us.
- **Weekly 30-minute product call with the founding team** for months 1–3, then monthly for months 4–12. You talk directly to the people building it.
- **Direct influence on next quarter's roadmap** — if you need a feature, we'll prioritize it if it makes sense for the product.
- **Beta access to all new features** before public release.

### What We Ask

- **Attend feedback calls** — weekly for months 1–3, monthly for months 4–12. If you can't make one, just let us know.
- **Share anonymized usage metrics** — tokens compressed, cost saved. We never see the content of your prompts or context. Just the numbers.
- **Allow an anonymized case study** — we'll write it, you review it before it goes anywhere. If you're not happy with it, we don't publish.
- **Intro to 2 other potential design partners** at your 3-month check-in — just people you think might have the same problem. No pressure on them.

### The Fine Print (Still Plain English)

- Either party can exit with 30 days notice, no hard feelings.
- Your data stays in your infra. CutCtx is a local-first proxy — nothing is stored on our servers.
- The case study right only covers aggregated metrics and your general experience. We won't quote you or name your company without separate written approval.
- After 12 months, you move to a paid plan or we part ways cleanly.

---

## 6. Target Company Tracking Template

| Company | Contact | Title | LLM Usage Signal | Outreach Date | Status | Notes |
|---------|---------|-------|-----------------|--------------|--------|-------|
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |
| | | | | | | |

**Status options:** `Identified` / `Emailed` / `Followed Up` / `Replied` / `Call Scheduled` / `Call Done` / `Agreement Sent` / `Active Partner` / `Passed`

**LLM Usage Signal examples:** "Claude Code heavy user (GitHub)", "Posted about GPT-4 costs on Twitter", "Job listing requires LLM API experience", "Using Cursor at scale (blog post)", "Raised Series A, AI-native product"
