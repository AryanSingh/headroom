# Headroom Lead Generation Playbook

> **Product:** Headroom — AI context compression proxy for development teams.
> **Target:** Security leaders, pentest consultants, and DevSecOps engineers who hit LLM context limits daily.
> **Goal:** Generate qualified pipeline that converts to paid seats.

---

## 1. ICP Tiers

| Tier | Role | Company Profile | Primary Pain | Key Signals |
|------|------|----------------|--------------|-------------|
| **P0 (Primary)** | Director/VP of Security, CISO | SaaS, 50–500 employees, SOC 2 / HIPAA compliance | Audit evidence collection is manual; context windows overflow in security reviews | Compliance deadline within 90 days, actively using Claude Code or Cursor |
| **P1 (Secondary)** | Pentest consultant, Security analyst | Boutique pentest firms (10–100 consultants) | Reviewing 100k+ lines of code/logs per engagement; LLM context limits slow analysis | Uses LLMs for code review, bills by engagement, handles large codebases |
| **P2 (Tertiary)** | DevSecOps / Platform engineer | SaaS, 100–1000 employees, AI-augmented CI/CD pipelines | AI agents exceed context budgets in PR reviews and security scans | Runs AI-powered CI/CD, manages token costs, integrates OpenAI/Anthropic SDKs |

### P0 — AppSec Lead (Primary)
- **Title:** Director of Security, VP of Security, CISO, Head of AppSec
- **Company:** B2B SaaS with regulatory compliance obligations (SOC 2 Type II, HIPAA, ISO 27001)
- **Team size:** 5–20 in security org
- **Tooling:** GitHub Advanced Security, Semgrep, Snyk, Wiz, Okta, Claude Code, Cursor
- **Pain:** Every audit cycle requires collecting chat transcripts and LLM interactions as evidence. Context windows in Claude/Cursor overflow during codebase-wide security reviews. Engineers waste hours manually truncating and re-prompting.

### P1 — Pentest Consultant (Secondary)
- **Title:** Senior Security Consultant, Pentest Lead, Managing Consultant
- **Company:** Boutique pentest shops (e.g., 15-person firms doing 3–5 engagements/month)
- **Tooling:** Burp Suite, Metasploit, custom scripts, Claude Pro/Enterprise, OpenAI
- **Pain:** One engagement can generate 100k+ lines of logs and code. LLMs can't ingest a full engagement in one context window. Consultants manually chunk and re-prompt, losing continuity.

### P2 — DevSecOps / Platform Engineer (Tertiary)
- **Title:** Staff Platform Engineer, DevSecOps Engineer, AI Infrastructure Lead
- **Company:** Engineering orgs embedding AI into developer workflow (PR review, secret scanning, code gen)
- **Tooling:** GitHub Actions, Docker, Kubernetes, Anthropic SDK, OpenAI SDK, LangChain, vector DBs
- **Pain:** AI agents in CI/CD pipelines blow through context budgets. PR reviews exceed maximum tokens. Token costs scale linearly with context size. Engineers spend more time managing context than reviewing results.

---

## 2. Lead Scoring Model (0–100)

### Score Tiers

| Range | Label | Definition |
|-------|-------|------------|
| 80–100 | **Hot** | Actively searching for context compression. Uses Claude Code / Cursor daily. SOC 2 audit within 90 days. Headroom could directly solve an immediate blocker. |
| 60–79 | **Warm** | Using AI coding tools regularly. Has compliance requirements (SOC 2, HIPAA, ISO 27001). Headroom could replace a manual workflow they hate. |
| 40–59 | **Tepid** | AI-curious, evaluating LLM tools. No immediate compliance pressure. Context limits are a minor annoyance, not a blocker. |
| 0–39 | **Cold** | Exploring AI tooling broadly. No clear pain around context limits or compliance. Needs education before qualification. |

### Score Contributions

| Factor | Max Points | Scoring Logic |
|--------|------------|---------------|
| **Job Title** | 20 | CISO / VP Security = 20, Director Security = 18, Pentest Lead = 15, DevSecOps = 12, Engineer = 8, Other = 5 |
| **Tech Stack** | 25 | Claude Code + Cursor + Docker = 25, Anthropic SDK = 20, OpenAI SDK = 15, LangChain = 10, No AI tooling = 0 |
| **Pain Signals** | 30 | Context limit complaints (explicit) = 30, Compliance pain (SOC 2/HIPAA) = 25, Manual workaround evidence = 20, Mentions of "context window" = 15, No pain stated = 0 |
| **Timeline** | 15 | Audit within 30 days = 15, Within 90 days = 12, Within 6 months = 8, No timeline = 0, "Not right now" = -5 |
| **Engagement** | 10 | Replied to email = 4, Attended demo = 6, Shared pricing page = 2, Referral = 10, None = 0 |

**Formula:** `Score = Title + TechStack + Pain + Timeline + Engagement` (capped at 100, min 0)

### Scoring Example

> **Lead:** Jane, Director of Security at Finova (SaaS, 200 employees, SOC 2 audit in 45 days). Uses Cursor daily. Mentions "we can never fit our entire codebase into Claude's context" in discovery.
>
> **Score:** Title (18) + Tech stack (Cursor + Docker = 20) + Pain (compliance + explicit context limit = 30) + Timeline (audit ≤ 90 days = 12) + Engagement (none yet = 0) = **80 (Hot)**

---

## 3. Where to Find Leads

### GitHub

| Signal | Search / Filter | Lead Type |
|--------|----------------|-----------|
| `Dockerfile` + `anthropic` or `openai` SDK dependency | Search `dependency:anthropic` in repos with a `Dockerfile` | P2 (DevSecOps) |
| Starred `headroomlabs/headroom` | Stargazers list | All tiers (signals awareness) |
| Uses Cursor / Claude Code config | `.cursorrules` or ` CLAUDE.md` in repo | P0, P1 |
| `requirements.txt` + `langchain` + `openai` | Dependency search | P2 |
| Repos with security workflows | `.github/workflows/` referencing `semgrep` or `snyk` | P0 |

**Tooling:** Use `gh search` CLI or GitHub API to automate lead sourcing. Export to CSV → import to HubSpot.

### LinkedIn

| Search Query | Target |
|-------------|--------|
| `"AppSec Director" SOC 2` | P0 |
| `"VP of Security" "context window"` | P0 |
| `pentest consultant` + `LLM` | P1 |
| `"penetration tester" "AI"` | P1 |
| `DevSecOps` + `context window` | P2 |
| `"Platform Engineer" "Claude"` | P2 |
| `"security engineer" "AI agents"` | P2 |

**Approach:** Use Sales Navigator. Save lead lists. Export to HubSpot via CSV. Send connection requests with custom notes (see Section 5).

### Job Boards

| Board | Search Terms | Why It Matters |
|-------|--------------|----------------|
| LinkedIn Jobs | `"AI Security Engineer"`, `"LLM Security"`, `"AI Governance"` | Companies hiring for these roles are dealing with context pain and compliance uncertainty |
| Indeed | `"AI Security Architect"`, `"Prompt Engineering Lead"` | Signals organizational investment in AI workflows |
| Otta / Built In | `"Security" + "AI"` at SaaS companies | Well-funded startups with compliance runway |

**Tactic:** New hire in "AI Security" = their team will need context compression within 6 months. Reach out to the hiring manager (P0) or the person filling the role.

### Hacker News

| Content Signal | Why |
|----------------|-----|
| `"Show HN: ..."` LLM-related tool | Builder is a potential partner or user |
| Comments complaining about `"cost of Claude"` or `"token limits"` | Explicit pain signal |
| Threads about `"AI code review"` or `"security at AI companies"` | Community of potential P1/P2 leads |
| `"Ask HN: Best way to handle large codebases with LLMs?"` | Direct need for Headroom |

**Tactic:** Monitor via `hn.algolia.com`. Engage thoughtfully. Only pitch Headroom if directly relevant.

### Conferences & Events

| Conference | Focus | Lead Type |
|------------|-------|-----------|
| **RSA Conference** | Enterprise security, AppSec | P0 (CISOs, AppSec Directors) |
| **Black Hat** | Offensive security, pentesting | P1 (pentest consultants) |
| **BSides** (regional) | Community security | P0, P1 (hands-on practitioners) |
| **KubeCon + CloudNativeCon** | Cloud native, CI/CD | P2 (DevSecOps, Platform) |
| **AI Engineer Summit** | AI tooling builders | P2 |
| **GitHub Universe** | Developer tools, security | All tiers |

**Tactic:** Target talks on "LLM prompt injection," "AI security audit," and "securing AI code generation." Connect with speakers and attendees. Book follow-up demos with 3 days of conference end.

---

## 4. Email Sequences

### Sequence A — Primary ICP (AppSec Lead)

| Touch | Timing | Subject Line | Body |
|-------|--------|--------------|------|
| **A1** | Day 0 | SOC 2 audit season coming up? | "Hey {{first_name}}, noticed {{company}} runs SOC 2. Most security teams we talk to spend 20+ hours per audit cycle manually collecting LLM chat transcripts as evidence. Headroom compresses and archives every AI interaction automatically — cutting review time by ~60%. Want to see how? Happy to share a 2-min video." |
| **A2** | Day 5 | How {{similar_company}} saved 2 engineer-weeks per audit | "{{first_name}}, [Similar Company] was in your exact position — 3 weeks out from their SOC 2 audit and drowning in LLM evidence requests. By using Headroom's compression proxy, they compressed 12GB of Claude logs into 480MB, lowered their token bill 40%, and closed their audit 2 weeks early. Full case study attached. Worth 10 minutes?" |
| **A3** | Day 12 | Quick demo — 10 mins, your own logs | "{{first_name}}, instead of me explaining, let me show you. I'll run Headroom against a sample of your team's actual Claude/Cursor usage. You'll see raw vs. compressed side-by-side. Takes 10 minutes. No commitment. Pick a time: [Calendly link]" |

**Fallback (if no reply after A3):** Move to nurture. Send the ROI calculator (Section 7, Stage 5) with a note: "No rush — here's a tool to estimate your own savings. When audit season heats up, we're here."

### Sequence B — Secondary ICP (Pentest Consultant)

| Touch | Timing | Subject Line | Body |
|-------|--------|--------------|------|
| **B1** | Day 0 | 100k lines to review? We fit it in one Claude context | "Hey {{first_name}}, I saw you're at {{company}}. If you're feeding engagement logs into Claude, you know the pain of hitting context limits mid-analysis. Headroom compresses on the fly — I've seen pentesters fit an entire 100k-line engagement into a single Claude context window. Curious? Reply and I'll send the one-pager." |
| **B2** | Day 4 | Architecture deep-dive + token benchmarks | "{{first_name}}, here's how it works under the hood: [link to architecture diagram]. TL;DR — we use semantic compression with a configurable CCR (Context Compression Ratio). In our benchmarks, a 50k-token pentest report compresses to 8k tokens with >95% semantic fidelity. That's 6x more analysis per dollar. Benchmarks attached. Want me to run it on one of your actual reports?" |
| **B3** | Day 10 | Free 30-day trial — built for pentest firms | "{{first_name}}, we're offering pentest firms a free 30-day trial. No credit card. Full access. You'll see compression working on your real engagement data within 30 minutes. Trial includes: unlimited compression, memory persistence across sessions, and audit logging. Grab it here: [trial link]" |

### Sequence C — Tertiary ICP (DevSecOps / Platform Engineer)

| Touch | Timing | Subject Line | Body |
|-------|--------|--------------|------|
| **C1** | Day 0 | Your CI/CD agents are running out of context | "Hey {{first_name}}, if you're running AI agents in CI/CD (PR reviews, secret scanning, code gen), you've seen the dreaded 'maximum context length exceeded' error. Headroom sits between your agents and the LLM API, compressing prompts transparently. No code changes. Average compression: 5–8x. Want to see the GitHub Action integration?" |
| **C2** | Day 4 | Integration guide: GitHub Actions → Docker → K8s | "{{first_name}}, here's the 5-minute setup guide: [link]. Works with: GitHub Actions (drop-in action), Docker (sidecar container), Kubernetes (helm chart), and any OpenAI/Anthropic-compatible client. The tl;dr — add one env variable to your existing workflow and you're compressing. Docs attached. Questions?" |
| **C3** | Day 10 | ROI calculator — your traffic, your savings | "{{first_name}}, instead of guessing, here's a live ROI calculator. Plug in your monthly token usage and see the savings: [link]. Most teams our size save $X,XXX/month on API costs alone — before counting productivity gains. Want to chat about your numbers?" |

---

## 5. LinkedIn Connection Notes + DM Sequences

### Connection Notes

#### P0 (AppSec Lead)

1. **Compliance-focused:**
> "Hi {{first_name}}, I'm following your work on {{company}}'s SOC 2 program. We help security teams compress LLM interaction logs for audit evidence — thought it might be relevant. Happy to connect."

2. **Context-pain focused:**
> "Hey {{first_name}}, saw your post about using Claude for code review. We built a compression proxy that fits larger codebases into context windows — seems like it'd resonate. Would love to connect."

3. **Tooling-focused:**
> "Hi {{first_name}}, noticed {{company}} uses Cursor + Semgrep. We help teams like yours capture compressed AI context for compliance. Would be great to connect and share notes."

#### P1 (Pentest Consultant)

1. **Workflow-focused:**
> "Hi {{first_name}}, I work with pentest firms that feed engagement data through LLMs. Headroom lets you fit an entire 100k-line report into one context window. Would love to connect."

2. **Peer referral:**
> "Hey {{first_name}}, [mutual connection] mentioned you do pentest work with AI tooling. We compress logs & code for LLM analysis — curious if you've hit context limits in engagements. Let's connect!"

3. **Efficiency-focused:**
> "Hi {{first_name}}, your profile mentions large-scale pentests. If chunking and re-prompting across context windows is slowing you down, I'd love to show you what we're building. Connecting to stay in touch."

#### P2 (DevSecOps / Platform Engineer)

1. **CI/CD focused:**
> "Hi {{first_name}}, saw you're working on AI-powered CI/CD at {{company}}. Our compression proxy helps agent-based workflows stay within context budgets. Would love to connect."

2. **Token-cost focused:**
> "Hey {{first_name}}, if you're managing OpenAI/Anthropic token spend for your team, we built a proxy that cuts costs 3–8x by compressing prompts. Worth a chat?"

3. **K8s/Docker focused:**
> "Hi {{first_name}}, we deploy as a Docker sidecar / Helm chart — drops into existing infrastructure with no code changes. Seems like your kind of stack. Connecting to compare notes."

### Follow-up DM Sequences (after connection accepted)

#### P0 DM Sequence

| Step | Timing | Message |
|------|--------|---------|
| DM1 | Day 0 (after accept) | "Thanks for connecting, {{first_name}}! Quick question — are you dealing with LLM context limits in your security reviews? We're seeing a lot of AppSec teams hit this wall." |
| DM2 | Day 3 (if replied) | "Makes sense. Would you be open to a 10-min screen share where I compress a sample of your team's actual Claude usage? No pitch — just seeing if it works for your data." |
| DM3 | Day 7 (if no reply to DM1) | "Hey {{first_name}} — no pressure at all. I put together a 2-min video showing how we compress LLM context for compliance evidence. Happy to share if useful. lmk!" |

#### P1 DM Sequence

| Step | Timing | Message |
|------|--------|---------|
| DM1 | Day 0 | "Thanks for connecting! Curious — how do you currently handle LLM context limits when reviewing large engagement outputs? Chunking manually?" |
| DM2 | Day 3 | "Got it. We're seeing pentest firms save 4–6 hours per engagement using our compression. Happy to run a trial on one of your actual reports — no strings." |
| DM3 | Day 7 | "Here's that trial link I mentioned: [link]. 30 days free for pentest firms. Hope it helps on your next engagement!" |

#### P2 DM Sequence

| Step | Timing | Message |
|------|--------|---------|
| DM1 | Day 0 | "Thanks for connecting, {{first_name}}! What's your AI agent stack look like? We integrate with most setups." |
| DM2 | Day 3 | "Nice. We have a GitHub Action + Docker deployment that drops in with one env var change. Happy to share the integration guide if you're curious." |
| DM3 | Day 7 | "Here's the guide: [link]. And if you want to test it in your CI pipeline, I can set up a sandbox environment for you this week." |

---

## 6. Discovery Call Script (Qualifying Questions)

**Structure:** 30-min call. First 10 min = problem discovery. Next 15 min = demo. Last 5 min = next steps.

### 10 Qualifying Questions

| # | Question | Why It Matters | Signal to Listen For |
|---|----------|----------------|----------------------|
| 1 | "What LLMs are your team using today — Claude, OpenAI, local models?" | Establishes current stack. Claude = higher compression opportunity. OpenAI = larger context but still benefits. | "Both", "Claude for code, GPT-4 for chat" |
| 2 | "How often do you hit context limits? Is it a daily frustration or an occasional annoyance?" | Quantifies pain frequency. Daily = hot lead. | "Multiple times a day", "We've stopped trying to do whole-codebase reviews" |
| 3 | "What's your current audit evidence collection process for LLM interactions?" (P0 only) | Reveals manual vs automated compliance workflows. | "We screenshot chats", "There's no process" |
| 4 | "How many seats on your Claude / OpenAI plan?" | Deal sizing — larger teams = larger opportunity. | "50+ seats", "Enterprise plan" |
| 5 | "Are you in a compliance or audit period right now?" (P0) / "How many engagements are you running this quarter?" (P1) | Timeline pressure. In-audit = immediate need. | "SOC 2 renewal next month", "6 engagements in Q3" |
| 6 | "Who signs off on security tooling purchases at {{company}}?" | Understands buying authority. | "I do", "My VP", "We have a security budget committee" |
| 7 | "What's your monthly token spend?" | Quantifies the cost problem. High spend = high willingness to optimize. | "$5k+", "I don't know but it's growing" |
| 8 | "Do you use agents (Claude Code, Cursor, custom agents) or just chat interfaces?" | Agents have more aggressive context needs than chat. | "Claude Code all day", "We're building custom agents" |
| 9 | "How do you currently measure context efficiency — or do you?" | Reveals if they've already tried to solve the problem. | "We don't", "We track token usage per prompt" |
| 10 | "If you could wave a magic wand, what would a perfect solution look like for your team?" | Surfaces unstated pain points and desired outcomes. | "Zero manual chunking", "Automatic evidence capture" |

### Scoring During Call

- **Positive signal (score up):** Expands on pain, asks technical questions, names competitors/alternatives, mentions timeline.
- **Negative signal (score down):** Says "we're fine with manual work," "budget frozen," "not the decision maker," "just exploring."

### Next Steps Commitment

Always end with a clear next step:

- **Hot lead (80+):** "Let's schedule a technical evaluation with your team. I'll send a Calendly link for a 45-min session with your engineers."
- **Warm lead (60–79):** "I'll send you our ROI calculator + a case study. Let's reconnect in two weeks — does that work?"
- **Tepid lead (40–59):** "I'll add you to our monthly newsletter. If audit season heats up, you know where to find us."
- **Cold lead (<40):** "Thanks for your time. I'll send you a link to our docs in case you ever need it."

---

## 7. Demo Flow (5 Stages, 10–12 Minutes)

### Stage 1: Problem Intro (2 min)

**Script:**
> "Context compression is the new caching. Just like Redis made database queries faster by caching results, Headroom makes LLM interactions cheaper and more capable by compressing context on the fly. Every token you save is money back in your pocket and more room for actual reasoning."

**Key point to land:**
> "Your team is already paying for context they don't use. Headroom reclaims it."

**Visual:** Slide showing "Raw Context" (full bar) vs "Compressed Context" (1/5 the size) — labeled with dollar amounts.

### Stage 2: Live Compression (3 min)

**Setup:** Open a terminal. Show a raw Claude conversation (or log file) — 5,000 tokens of chat history.

**Action:**
```
# Raw input (5,000 tokens)
headroom compress input.txt --output compressed.txt
# Compressed output (850 tokens)
```

**Show side-by-side:**
- Left pane: raw text
- Right pane: compressed text
- Highlight that semantics are preserved — key facts, decisions, code references remain intact.

**Interactive:** Ask the prospect to pick a section and verify the compressed version captures the meaning.

**Transition:** "That's a 6x compression with >95% semantic preservation. Now let me show you how this compounds when you use it across a full engagement."

### Stage 3: CCR + Memory (2 min)

**Concept:** CCR (Context Compression Ratio) is configurable per use case.

**Show:**
- Default CCR: 5x (balanced)
- Aggressive CCR: 10x (high compression, some detail loss — good for summarization)
- Conservative CCR: 2x (lossless compression — good for compliance evidence)

**Memory:**
> "Headroom remembers what it compressed. If you ask about a decision made 3 sessions ago, it reconstructs the relevant context without re-ingesting the full history. Repeated tokens get reclaimed automatically."

**Visual:** Timeline showing multiple sessions → compressed summaries → cross-session retrieval.

### Stage 4: Audit Evidence (3 min) — P0 Focus

**Script:**
> "This is where Headroom shines for compliance. Every compressed interaction is automatically logged with: timestamp, user identity, original token count, compressed token count, compression ratio, and a cryptographic hash proving the compressed output matches the original."

**Show:**
- Audit log table: Date | User | Original Tokens | Compressed | Ratio | Hash
- Export as CSV / JSON — ready for SOC 2 evidence collection
- Retention policy controls (e.g., keep compressed logs for 7 years)

**For P1:** Skip audit slide. Show multi-engagement context persistence instead.

**For P2:** Skip audit slide. Show API integration — how Headroom plugs into existing CI/CD pipelines with zero code changes.

### Stage 5: ROI Calculator (2 min)

**Script:**
> "Let's make this real. If your team sends 50M tokens/month to Claude at $3/MTok input, that's $150/month just on input. With 5x compression, you're sending 10M tokens — $30/month. Same output quality. That's $1,440/year saved on API costs alone."

**Table:**

| Metric | Before Headroom | With Headroom (5x CCR) |
|--------|----------------|------------------------|
| Monthly input tokens | 50M | 10M |
| Monthly input cost | $150 | $30 |
| Avg context per prompt | 10K tokens | 2K tokens |
| Max codebase review size | 50K tokens | 250K tokens |
| Audit evidence collection | Manual (8 hrs/cycle) | Automated (5 min/cycle) |

**Close:**
> "Based on your team's scale — {{customize}} — you'd save roughly $X/month and reclaim Y engineer-hours per audit cycle. Want to run the calculator on your actual numbers?"

---

## 8. Objection Handling Table

| # | Objection | Root Cause | Response |
|---|-----------|------------|----------|
| 1 | **"It's too expensive."** | Price sensitivity or unclear value | "Understood. What budget were you thinking? Our pricing scales with usage, so teams your size typically pay $X-$Y/month. And if you're spending $Z/month on LLM tokens, the compression alone pays for itself within 30 days. Want me to show you the math?" |
| 2 | **"We're concerned about security — you're proxying our LLM traffic."** | Trust / data governance | "Great question. Headroom runs as a forward proxy in your own VPC. Data never leaves your infrastructure. We have customers handling HIPAA data. Here's our security white paper: [link]. Happy to set up a private deployment for your review." |
| 3 | **"We'll build this ourselves."** | Not invented here / engineer ego | "We hear that a lot. Here's what teams find: compression that preserves semantic meaning without hallucinations is harder than it looks — we've spent 18 months on the algorithm. Our average customer saves 400+ engineering hours on the build vs. buy decision alone. But if you want to try, our OSS version is available. Most teams end up upgrading within 2 months." |
| 4 | **"We're worried about vendor lock-in."** | Long-term commitment fear | "Headroom compresses to standard token formats compatible with any LLM provider. If you leave, your compressed contexts are plain JSON — no proprietary format. Plus, you can export everything. It's a proxy, not a platform." |
| 5 | **"There's an open-source alternative."** | Cost avoidance | "We maintain our own OSS version! The difference is: managed infrastructure, compliance logging, team management, priority support, and SLA guarantees. Most OSS users graduate to paid within 6 weeks once they hit scale. Start with OSS, upgrade when ready." |
| 6 | **"I'm not sure how this fits with our compliance requirements."** | Uncertainty / risk aversion | "Let's set up a 15-min call with our compliance team. We've mapped Headroom to SOC 2, HIPAA, and ISO 27001 control requirements. We'll share our compliance deck and you can assess against your specific framework. No commitment." |
| 7 | **"We're too small for this."** | Mistaken about eligibility | "Actually, Headroom works great for small teams! Our 'Starter' tier is designed for teams under 10 seats. You get the same compression, just fewer admin features. And when you grow, you can upgrade seamlessly. Want to see the Starter pricing?" |
| 8 | **"Not the right time — we're focused on shipping."** | No urgency / competing priority | "I get it. When is a better time? In 3 months? 6 months? I'll set a calendar reminder to follow up. In the meantime, here's our ROI calculator — if your token costs spike, you'll know exactly what you'd save. I'll check back in [agreed timeframe]." |

---

## 9. Post-Call Follow-up Template

```
Subject: Thanks, {{prospect_name}} — next steps with Headroom

Hi {{prospect_name}},

Thanks for the great conversation today. I wanted to recap what we discussed and outline next steps.

**Pain Identified:**
- {{pain_point_1}}
- {{pain_point_2}}

**Demo Highlights:**
- {{demo_highlight_1}} (e.g., "6x compression on their actual logs")
- {{demo_highlight_2}} (e.g., "Audit export ready for SOC 2 evidence collection")

**Estimated Impact:**
- Monthly token savings: {{token_savings}} tokens ({{cost_savings}}/month)
- Time saved per audit cycle: {{time_savings}} hours

**Next Steps:**
- [ ] {{action_1}} (owner: {{owner_1}}, by {{date_1}})
- [ ] {{action_2}} (owner: {{owner_2}}, by {{date_2}})
- [ ] {{action_3}} (owner: {{owner_3}}, by {{date_3}})

**Mutual Action Items:**
| Owner | Action | Due |
|-------|--------|-----|
| {{prospect_name}} | Share sample logs / traffic pattern for personalized ROI | {{date}} |
| {{sales_rep}} | Send pricing proposal and compliance deck | {{date}} |
| Both | Schedule technical eval with {{prospect_engineer_name}} | {{date}} |

**Attachments:**
- [Link to ROI calculator with their numbers pre-loaded]
- [Link to compliance mapping document]
- [Link to recording (if applicable)]

Looking forward to {{next_milestone}}!

Best,
{{sales_rep_name}}
```

---

## 10. HubSpot Deal Stage Definitions

| Stage | Definition | Entry Criteria | Exit Criteria / Actions |
|-------|------------|----------------|------------------------|
| **1. Lead** | New inquiry — inbound form, event scan, LinkedIn connection, sourced list import. No qualification yet. | - Contact exists in HubSpot<br>- Source tracked (GH, LI, conference, inbound) | - Score ≥ 40 → move to Qualified<br>- Score < 40 → keep in Lead, nurture monthly<br>- No engagement in 90 days → archive |
| **2. Qualified** | Pain confirmed, budget exists or can be allocated, timeline identified. | - Discovery call completed (Section 6)<br>- Score ≥ 60 (Warm) ideally<br>- At least 2 of: pain, budget, authority, timeline | - Demo booked → move to Demo Completed<br>- Prospect declines demo → move back to Lead, set 60-day nurture |
| **3. Demo Completed** | Prospect has seen Headroom working on their own data (not just a generic demo). Compression ratio verified on their logs. | - Demo completed (Section 7)<br>- ROI calculated with their numbers<br>- Next steps agreed (Section 9) | - Verbal commitment / "ready to move forward" → Negotiation<br>- Needs internal buy-in → set follow-up with decision maker<br>- Ghosted > 14 days → reach out, then move back to Qualified |
| **4. Negotiation** | Active pricing discussion. Contract sent or under legal review. | - Deal size scoped (seats or token volume)<br>- Pricing proposal sent<br>- Legal / security review initiated | - Signed contract → Closed Won<br>- Lost to competitor / no decision → Closed Lost<br>- Stalled > 30 days → set "snooze" and re-engage in 90 days |
| **5. Closed Won** | Contract signed. Implementation kickoff scheduled. | - Signed agreement in CRM<br>- Payment method collected<br>- Implementation call booked | - Handoff to customer success<br>- First value achieved within 14 days |
| **6. Closed Lost** | Deal is definitively not happening. | - Prospect explicitly says no OR<br>- Radio silence > 60 days in Negotiation | - Log reason (price, competitor, no need, built internally)<br>- Suppress from outbound for 12 months<br>- Add to re-activation nurture flow |

### Stage Transition Rules

- **Skip allowed?** Yes — a hot lead can go Lead → Negotiation if they come in with budget, authority, and urgency.
- **Demote allowed?** Yes — if a Qualified lead goes quiet for 60 days, demote to Lead with a nurture touch.
- **Re-activation:** Closed Lost leads re-enter as new Lead after 12 months or if a significant trigger event occurs (e.g., new CISO, SOC 2 audit failure, competitor acquisition).

---

## 11. 30-Day Quick-Start Plan

### Week 1: Source + Score

| Day | Activity | Target | Tooling |
|-----|----------|--------|---------|
| Mon | GitHub lead sourcing — scan repos for `Dockerfile` + `openai`/`anthropic` deps | 80 leads | `gh search`, custom script |
| Tue | LinkedIn Sales Navigator — P0 search + export | 50 leads | Sales Navigator + CSV export |
| Wed | LinkedIn Sales Navigator — P1 + P2 search + export | 50 leads | Sales Navigator |
| Thu | Job board scanning — "AI Security Engineer" hires + event attendee lists | 20 leads | Otta, LinkedIn Jobs |
| Fri | Score all 200 leads. Tier into P0/P1/P2. Tag Hot/Warm/Tepid/Cold. | 200 scored | HubSpot + scoring sheet |

**Week 1 Metric:** 200 leads sourced and scored.

### Week 2: Sequence A — Top 50 P0 Leads

| Day | Activity | Target |
|-----|----------|--------|
| Mon | Send Sequence A, Touch 1 to top 50 scored P0 leads | 50 emails sent |
| Tue–Thu | Track open rates. Reply to any responses. Qualify for demo. | Monitor |
| Fri | Send Sequence B, Touch 1 to top 25 P1 leads. Prep Sequence A Touch 2. | 25 emails sent |

**Week 2 Metric:** Open rate ≥ 50% on Sequence A Touch 1.

### Week 3: Nurture + Demos

| Day | Activity | Target |
|-----|----------|--------|
| Mon | Send Sequence A, Touch 2 to non-responders from Week 2 | ~40 emails |
| Tue | Send Sequence B, Touch 2 to P1 leads | ~20 emails |
| Wed | Sequence C, Touch 1 to top 25 P2 leads | 25 emails |
| Thu | Book demos from P0 email replies + LinkedIn DM responses | ≥ 5 demos booked |
| Fri | Run demos for hot leads. Send post-call follow-ups (Section 9). | 3 demos |

**Week 3 Metric:** 5+ demos booked.

### Week 4: Close + Handoff

| Day | Activity | Target |
|-----|----------|--------|
| Mon | Send Sequence A Touch 3 + Sequence C Touch 2 to remaining leads | Remaining leads |
| Tue | Follow up with demo prospects — send pricing proposals for hot leads | 2 proposals |
| Wed | Close-won handoff to customer success for signed deals | Handoff |
| Thu | Remaining demos. Re-engage stalled leads with new Angle. | 2 demos |
| Fri | Review weekly metrics. Plan next 30-day cycle. | Retro |

**Week 4 Metric:** ≥ 1 closed-won deal or ≥ 3 active negotiations.

### Overall 30-Day Targets

| Metric | Target |
|--------|--------|
| Leads sourced | 200 |
| Emails sent | ~200 |
| Open rate | ≥ 50% |
| Reply rate | ≥ 10% |
| Demos booked | ≥ 10 |
| Demos completed | ≥ 8 |
| Demos → negotiation | ≥ 3 |
| Closed won | ≥ 1 |

---

## Appendix: Quick Reference

### Monthly Email Calendar Template

| Week | P0 Action | P1 Action | P2 Action |
|------|-----------|-----------|-----------|
| 1 | Source + score | Source + score | Source + score |
| 2 | Sequence A (T1) | Sequence B (T1) | — |
| 3 | Sequence A (T2) | Sequence B (T2) | Sequence C (T1) |
| 4 | Sequence A (T3) + Demos | Sequence B (T3) | Sequence C (T2) |

### Lead Status Definitions (HubSpot)

| Status | Meaning | Next Action |
|--------|---------|-------------|
| New | Imported, not contacted | Score + add to sequence |
| Contacted | Sequence touch sent | Monitor engagement |
| Responded | Replied to email/DM | Qualify → book demo |
| Demo Scheduled | Calendly booked | Prep personalized demo |
| Demo Completed | Demo done | Send follow-up + proposal |
| Negotiation | Pricing discussion | Close or set next step |
| Closed Won | Signed | Handoff to CS |
| Closed Lost | No deal | Log reason, archive |
| Nurture | Not ready | Add to monthly newsletter |

### Key Links

- **Headroom website:** [headroomlabs.com](https://headroomlabs.com)
- **Docs:** [docs.headroomlabs.com](https://docs.headroomlabs.com)
- **Open source:** [github.com/headroomlabs/headroom](https://github.com/headroomlabs/headroom)
- **Pricing:** [headroomlabs.com/pricing](https://headroomlabs.com/pricing)
- **Security white paper:** [docs.headroomlabs.com/security](https://docs.headroomlabs.com/security)
- **Demo booking:** [calendly.com/headroomlabs/demo](https://calendly.com/headroomlabs/demo)

---

> **Maintainer:** Headroom Sales & Marketing
> **Last updated:** {{date}}
> **Version:** 1.0
