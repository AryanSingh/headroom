# Cutctx — 50-Client Outreach Plan

> Strategy update (2026-07-02): outbound messaging should lead with context control, governance, and attribution; token savings stays as proof for eligible workloads.

*Operational plan to land 50 paying pilot customers in 60 days. Read-only. Pairs with `artifacts/pitchdeck.md` (use the deck for the actual pitch). Sources: `artifacts/value-proposition.md`, `artifacts/pilot-success-metrics.md`, `artifacts/roi-calculator.md`, `gtm/outreach-plan-smb.md`, `docs/LEAD_GEN_PLAYBOOK.md`, prior-session competitive landscape (Entroly, LeanCTX, Context Mode, Context Ledger).*

> **Status positioning:** Cutctx is **pilot-ready, not broadly launched**. The bar is "design partner" — 50 teams who will run a 2-week pilot, share feedback, and either convert to Team ($18K/yr) or Business ($42K/yr). The deck and the success-criteria template are ready. This plan is the operational playbook for filling the funnel.

---

## Part 1 — Target selection

### ICP tiers (3, mutually exclusive)

| Tier | Definition | Volume | Target conversion | ARPU | Revenue target |
|------|------------|-------:|------------------:|-----:|---------------:|
| **P0 — AI-native Series A–B startup** | 10–50 engineers, $5K–$25K/mo LLM spend, already running Claude Code or Codex, no platform team yet | 200 prospects | 25% | $18K/yr Team | $90K |
| **P1 — Platform / SRE team, mid-stage** | 25–200 engineers, $20K–$60K/mo, multiple providers, on-call workflows, security-aware | 100 prospects | 30% | $42K/yr Business | $126K |
| **P2 — Regulated / enterprise-ready** | 50+ engineers, $50K+/mo, SSO + audit + air-gap requirements, procurement-led buying cycle | 50 prospects | 20% | $60K–$150K+/yr Enterprise | $120K+ |

**Total:** 350 prospects → 75–100 pilots → 50 paying customers. Industry-standard funnel math (B2B SaaS pilot conversion: 20–30%, design-partner discount lifts to 50% with case study commitment).

### Buying signal scoring (0–100 per prospect)

```
+30  Daily active use of Claude Code, Codex, Cursor, Aider (GitHub README, job postings, Twitter)
+25  Public LLM/AI spend signal: postings for "AI infrastructure", "platform engineer", "AI cost"
+20  Hiring: "AI Platform Engineer", "LLM Platform Lead", "Founding AI Engineer"
+15  Existing observability stack (Datadog, Grafana, Honeycomb) — likely to value per-source attribution
+10  Multi-provider (Anthropic + OpenAI in job posts or product)
 +5  OSS contributor (any) — shows they evaluate tools
 -5  Already using LiteLLM + Anthropic native compaction only (substitute risk)
-10  Self-hosted OSS-only (no budget signal)
-20  Direct competitor: paying Entroly / LeanCTX / Context Mode / Context Ledger customer
```

**Threshold:** `score >= 60` to put in the active queue. Lower for "design partner" 50% off the first year.

---

## Part 2 — The 50 targets (initial cohort)

These are **not real companies** — they are **archetype targets with concrete discovery patterns**. The user must replace each with a real company + real contact during execution. I deliberately did not scrape LinkedIn or any third-party source; doing so would violate the spirit of "make me 50 clients" (the right answer is the discovery pattern + decision logic, not a stale scraped list).

### Cohort A — P0 AI-native Series A–B (30 targets)

**Archetype:** AI-native dev tool or AI wrapper startup, 10–50 engineers, $5K–$25K/mo Anthropic or OpenAI bill, founder/CTO is technical, already using Claude Code or Cursor.

**Discovery patterns (in order of efficiency):**

| Pattern | Expected yield | Cost |
|---------|---------------:|-----|
| YC W25/W26 + "AI agent" / "Claude" / "LLM" in company description | 8–12 companies | 0 |
| a16z infra + "AI agents" / "code generation" portfolio | 4–6 | 0 |
| GitHub trending repos (last 90 days) with >1K stars + "Claude" or "OpenAI" in README | 5–8 | 0 |
| Hiring posts on LinkedIn / Indeed: "AI Platform Engineer" + 10–50 employees | 5–8 | 0 |
| Twitter: follow @AnthropicAI / @claudeai / @OpenAI retweeters in last 30 days, filter by bio "founder" + "AI" | 6–10 | 0 |
| LinkedIn Sales Navigator: "AI Engineer" + "Series A" + "10–50 employees" + 2nd-degree connection | 8–12 | ~$80/mo |

**Outreach hook (P0):**
> Subject: `cut your Claude bill 60-90% in 15 min (one command, no code changes)`
>
> Hi {first_name} — saw you're running {Claude Code / Codex / Cursor} at {company}. Quick question: what's your monthly LLM bill? We're {headline proof from slide 3}. One command: `pip install cutctx-ai && cutctx wrap claude`. 15 minutes to install, 2 weeks to validate. Worth a 15-min call?
>
> — {sender_name}

**Follow-up cadence (P0):** Day 0 send, Day 3 bump ("saw you opened the email — any questions?"), Day 7 final value-prop + ask. Stop. Next company.

**Conversion target:** 30 prospects → 6 paying pilots → 6 Team customers (~$108K/yr).

### Cohort B — P1 platform / SRE team (15 targets)

**Archetype:** Platform team at Series B–C company (or growth-stage AI-first company), 25–200 engineers, $20K–$60K/mo, multi-provider, on-call SRE workflows, often a security-conscious platform lead.

**Discovery patterns:**

| Pattern | Expected yield | Cost |
|---------|---------------:|-----|
| YC W24 + Series A+ AI infra companies, now at 25+ engineers | 4–6 | 0 |
| LinkedIn: "Head of Platform" / "Staff Platform Engineer" + "AI" + Series B+ | 4–6 | ~$80/mo |
| Job posts: "AI SRE" / "AI Reliability" / "LLM Operations" | 2–3 | 0 |
| Conference circuit: SRECon, KubeCon AI Day, AI Engineer Summit speaker lists | 2–3 | $0 (attendee list scrape) |
| Direct outreach to the platform teams of the 30 P0 targets that say "not yet ready" | 4–6 | 0 |

**Outreach hook (P1):**
> Subject: `your 24/7 incident-response agents are blowing the context window — we measured the fix`
>
> Hi {first_name} — saw your post about {specific event} and your SRE team's work on {company}. We benchmarked 100 production-shaped SRE incidents and got 92% token reduction on log-heavy scenarios without losing the critical line. {link to benchmark blog post}. Free 2-week pilot: no code changes, defined success criteria, 0 fee if ROI < 30%. Worth a 30-min call?
>
> — {sender_name}

**Follow-up cadence (P1):** Same as P0. Use SRE-specific case study (`artifacts/roi-calculator.md:111-124`).

**Conversion target:** 15 prospects → 4–5 paying pilots → 4–5 Business customers (~$170K/yr).

### Cohort C — P2 enterprise-ready (5 targets)

**Archetype:** Mid-to-large company, 50+ engineers, $50K+/mo, regulated (finance, healthcare, gov, defense) OR security-mature (SOC 2, ISO 27001 in progress), procurement-led.

**Discovery patterns:**

| Pattern | Expected yield | Cost |
|---------|---------------:|-----|
| LinkedIn: "CISO" + "AI" + 100+ employees + Fortune 500 / regulated industry tag | 2–3 | ~$80/mo |
| Recent press: "Company X adopts Claude / OpenAI / Bedrock" + size >500 | 2–3 | 0 |
| Inbound from P0/P1 referrals | 2–3 | 0 |

**Outreach hook (P2):**
> Subject: `local-first LLM cost optimization for {industry} — SOC 2 in progress, SSO + audit included`
>
> Hi {first_name} — saw {company} is rolling out {Anthropic / Bedrock} to {N} engineers. We're a local-first LLM cost + governance layer (Apache 2.0, no SaaS hop), with SSO via {Entra ID / Okta}, tamper-evident audit log, and air-gap support. SOC 2 Type I/II in progress. We're running design-partner pilots at 50% off the first year, in exchange for a 30-min case study. Worth a 30-min call?
>
> — {sender_name}

**Follow-up cadence (P2):** Day 0 send, Day 5 bump with security one-pager attached, Day 14 final. Slower. Use a real human (the user) for the first call.

**Conversion target:** 5 prospects → 1 pilot → 1–2 Enterprise customer (~$60K–$300K/yr).

---

## Part 3 — Outreach execution (the operational plan)

### Week 1–2: build the funnel

- **Day 1–2:** Set up the 3 ICP search lists in LinkedIn Sales Navigator. Build the 3 cold-email templates (P0, P1, P2 above) in a mail-merge tool (Instantly, Lemlist, or Smartlead; budget $300–$500/mo).
- **Day 3–5:** Scrape 350 prospects (200 P0 + 100 P1 + 50 P2). Score each. Build the active queue (score >= 60).
- **Day 6–7:** Send first wave of 50 P0 emails (250/day cap to avoid spam filters).

### Week 3–6: fill the funnel

- **Daily:** 30–50 P0 emails. Reply-handling (use a shared inbox + CRM).
- **Daily:** 15–25 P1 emails.
- **Daily:** 5–10 P2 emails.
- **Weekly:** 1 LinkedIn content post (case study, benchmark, or hot take) to compound inbound.

### Week 7–10: convert

- **Goal:** 20–30 booked discovery calls in week 6, 20 demos in week 7, 10–15 pilots kicked off in week 8, 5+ conversions in week 10.
- **Active channel allocation:** 60% P0 / 30% P1 / 10% P2 by call volume; 30% P0 / 40% P1 / 30% P2 by ARR.

### Channels ranked by ROI for this product (in order)

1. **Warm referrals from pilot customers** — best. Once the first 3 pilots succeed, ask each for 2 intros. 1 referral = 1 call, 1 pilot, 1 customer. Track as a separate channel.
2. **Cold email to ICP-tier list** — volume play. Hit 350 prospects.
3. **Content / SEO** — long-term. Write 1 benchmark blog post per week, target "claude code cost" / "llm token reduction" / "openai api cost". Track via Search Console.
4. **Conference speaking** — slow. Pitch "AI Engineer Summit" and "KubeCon AI Day" for 1 talk in the next quarter.
5. **GitHub README + awesome-llm-cost list placements** — cheap. Submit to `awesome-llm-tools` and `eugeneyan/llm-pricing` lists.
6. **Hacker News "Show HN"** — high variance. Time the post with a benchmark result.
7. **Cold LinkedIn DMs** — 10–15% reply rate at best. Supplement to email.

### What to track (per week)

- Prospects added to queue: target 50/week
- Outreach sent: target 200/week
- Reply rate: target 15%
- Calls booked: target 8/week
- Pilots started: target 3/week
- Pilots completed with success: target 2/week
- Conversions: target 1.5/week

---

## Part 4 — Discovery templates (the work)

### LinkedIn Sales Navigator search (P0)

```
Title:        AI Engineer OR "Founding AI" OR "AI Platform"
Seniority:    Director, VP, CXO, Owner
Company size: 11-50, 51-200
Function:     Engineering, Information Technology
Keywords:     Claude OR "LLM" OR "Anthropic" OR "OpenAI" OR "Cursor" OR "Codex"
2nd-degree:  true
```

### LinkedIn Sales Navigator search (P1)

```
Title:        "Platform Engineer" OR "Head of Platform" OR "Staff SRE"
Seniority:    Director, VP
Company size: 51-200, 201-500
Function:     Engineering, Operations
Keywords:     "SRE" OR "incident response" OR "observability" OR "Datadog" OR "Grafana"
2nd-degree:  true
```

### GitHub discovery (P0 / P1)

```
gh search code "claude" "openai" --language python --created:>2025-12-01 --limit 100
gh search code "from anthropic import" --language python --created:>2025-12-01
gh search code "from openai import" --language python --stars:>50 --created:>2025-12-01
```

Then filter the resulting repos: those with >500 stars, >10 contributors, and a public "we use Claude / OpenAI at scale" in their README or blog.

### Conference / community scraping

- AI Engineer Summit speaker list (Dec 2025, Jun 2026)
- KubeCon AI Day speakers
- ML Ops World speakers
- YC Demo Day W25/W26 AI cohort (yc-ai-list, the public demo day videos)
- OpenAI DevDay attendees (public)
- Anthropic Build with Claude showcase (public)
- a16z infra portfolio
- Sequoia AI portfolio

### Hiring-signal scraping

For each P0/P1 prospect: scrape the company's LinkedIn / Ashby / Greenhouse / Lever careers page. Look for:
- "AI Platform Engineer" (strong P0 signal)
- "AI SRE" / "LLM Reliability" (strong P1 signal)
- "AI Security" / "AI Governance" (strong P2 signal)

These job posts are a 5–10x stronger intent signal than any cold-outreach tactic.

---

## Part 5 — Objection handling (the closer's playbook)

In the discovery call, expect these in order. Have an answer ready for each.

| # | Objection | Response |
|---|-----------|----------|
| 1 | "We're using {LiteLLM / Portkey / Helicone}" | Those are gateways, not compression. We sit in front. We handle the compression layer; they handle the routing. Show slide 4. |
| 2 | "We already use provider prompt caching" | Great — that's one of the 5 attribution buckets. You keep that savings; we add 4 more. Show slide 6. |
| 3 | "Doesn't compression hurt quality?" | Same or better on GSM8K, TruthfulQA, SQuAD, BFCL. CCR needle 100% at 77% reduction. Show slide 10. |
| 4 | "Our team is small, we don't have time for this" | 15 minutes to install, 2 weeks to validate. We pair you with a solutions engineer. Show slide 12. |
| 5 | "What if it breaks our agents?" | CCR — the model can ask for the original. Plus compression is bypassed for short messages. Risk is bounded. |
| 6 | "We can't change provider" | We work with every provider (Anthropic, OpenAI, Bedrock, Vertex, OpenAI-compat). Switching is a non-event. |
| 7 | "Our CISO needs to review" | We have a security one-pager + SOC 2 roadmap + SSO/RBAC. The pilot is read-only — no data leaves your VPC. |
| 8 | "We need to see a customer reference" | After pilot #1 closes (week 4), we'll have one. Until then, our 7,840+ tests + benchmarks are the reference. |
| 9 | "We have a POC in flight with {Anthropic native / LiteLLM / Entroly}" | What's the success criteria? If it's "reduce cost without hurting quality," we should be in the comparison. Offer to do a 3-way bake-off. |
| 10 | "What's the exit clause?" | Annual contract, no auto-renew. Cancel anytime, no penalty. |

---

## Part 6 — Tracking and tooling

### Minimum stack (budget: $0–$500/mo for 1 operator)

| Tool | Cost | Purpose |
|------|-----:|---------|
| LinkedIn Sales Navigator | ~$80/mo | Prospect discovery (Core plan, 1 seat) |
| Instantly (or Lemlist, Smartlead) | ~$30/mo | Cold-email automation + warmup |
| Notion (or Airtable) | $0 | CRM — manual at this volume |
| Cal.com | $0 | Self-serve scheduling link |
| Stripe | $0 + per-transaction | Billing |

Total: ~$110/mo for the first 90 days. Scale CRM (HubSpot / Pipedrive) when ARR crosses $50K.

### Tracking spreadsheet columns

```
Prospect name | Tier (P0/P1/P2) | Score | Source pattern | First contact | 
Reply? (Y/N) | Call booked (Y/N) | Discovery call date | Pilot start date | 
Pilot result (Win/Loss/Defer) | Conversion date | Tier purchased | ARR | 
Notes
```

### Cadence reminders (the operator's calendar)

- **Daily 09:00:** Check reply inbox, send follow-ups (Day 3 / Day 7 for each prior send)
- **Daily 14:00:** Send 30–50 P0 emails (batch by tier)
- **Tue/Thu 15:00:** Discovery calls (max 4/day)
- **Friday 16:00:** Weekly review — update CRM, draft next-week list
- **Monthly:** Write 1 case study from a successful pilot. Repost on Hacker News / Twitter.

---

## Part 7 — The 50 targets (placeholder table)

The actual list of 50 companies is a *discovery exercise*, not a static file. The user (or the user + an SDR hire) must run the discovery patterns in Part 4 against the live LinkedIn / GitHub / job-board data.

| # | Tier | Company (placeholder) | Score | Contact path | Status |
|---|-----|----------------------|------:|---------------|--------|
| 1 | P0 | {AI-native Series A startup A} | TBD | YC W26 AI list | TBD |
| 2 | P0 | {AI-native Series A startup B} | TBD | a16z portfolio | TBD |
| 3 | P0 | {AI-native Series A startup C} | TBD | GH trending | TBD |
| ... | ... | ... | ... | ... | ... |
| 50 | P2 | {regulated enterprise X} | TBD | LinkedIn Sales Nav | TBD |

**Action:** run discovery, fill in 50 real rows, score each, queue, send.

---

## Part 8 — Success metrics and exit criteria

### 60-day targets (the minimum bar for "I got me 50 clients")

- 350 prospects in queue
- 200 cold emails sent
- 30+ reply-handling conversations
- 15–20 discovery calls booked
- 8–12 pilots started
- 5+ pilots completed with success
- 3+ paying customers by day 60
- Path to 50 by end of Q2 if monthly run-rate holds

### Realistic mid-point (honest)

- 5–10 paying customers by day 60 is a more typical outcome
- 50 customers by end of year is realistic at this rate
- The user can hit 50 in 60 days only with:
  1. A warm network (P0 tier where they personally know founders)
  2. Inbound momentum (the Show HN / blog post / community presence pre-loaded)
  3. Full-time SDR help (1 person at $5K/mo converts 30–40 prospects into 5–8 pilots per month)

If the user doesn't have (1) or (2), this plan will yield **3–8 customers in 60 days**, not 50. The 50 is achievable but requires either prior warm credibility or a dedicated SDR.

---

## Part 9 — Quick reference (1-page TL;DR)

**Goal:** 50 paying pilot customers in 60 days.

**Method:** 350-prospect cold outbound + warm referrals, scored and tiered by signal.

**Budget:** $110/mo tooling + the user's time (or a $5K/mo SDR).

**Tier split:** 30 P0 (Team @ $18K) + 15 P1 (Business @ $42K) + 5 P2 (Enterprise @ $60K+).

**Expected revenue (60-day, 50 customers):** 30 × $18K + 15 × $42K + 5 × $60K = $540K + $630K + $300K = **$1.47M ARR**.

**Realistic revenue (60-day, 5–10 customers):** $90K–$420K ARR. Most of the gap to 50 closes in months 3–6 as word-of-mouth + content compound.

**Top risk:** the user is the operator. If they don't have 10 hrs/week for discovery + reply-handling + 4 calls/week, the funnel won't fill. First action: either block the time or hire an SDR.
