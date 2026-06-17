# Headroom Enterprise Outbound — 4-Touch Email Sequence

Target: AI-native startups with $5M+ funding, hiring AI/Platform Engineers, likely spending $5k+/mo on LLM APIs.

---

## Touch 1 — Day 1: The Hook

**Subject:** Your team is burning $[X]/mo on LLM tokens. We cut it 60%.

Hi [First Name],

I noticed [Company] is scaling fast — congrats on the [recent milestone/funding].

Quick question: how much is your team spending on Claude/GPT-4 API calls per month?

Most AI-native teams we talk to are in the $8k-$30k/mo range. That's $100k-$360k/year on tokens alone.

Headroom is a local-first context compression proxy that sits between your agents and the API. It compresses context by 60-95% before it hits the model — same quality, fraction of the cost.

We built it because we were tired of watching context windows balloon with redundant JSON, repeated system prompts, and uncompressed logs.

**The math:** If you're spending $15k/mo, Headroom brings that to ~$6k/mo. That's $108k/year back in your budget.

Would a 15-minute demo be worth your time this week?

Best,
[Your Name]
Pitch to Ship

P.S. — We're offering a 14-day free pilot with full engineering support. No commitment.

---

## Touch 2 — Day 4: The ROI Proof

**Subject:** Here's what $[X]/mo looks like compressed

[First Name],

I ran the numbers for a team your size. Here's what token savings look like:

| Metric | Without Headroom | With Headroom |
|--------|------------------|---------------|
| Monthly tokens | 50M prompt + 10M completion | 20M prompt + 7M completion |
| Monthly cost (Claude 3.5 Sonnet) | $15,000 | $5,850 |
| Annual savings | — | **$110,000** |

The key insight: most of what you send to models is repetitive — system prompts, tool definitions, conversation history, JSON schemas. Headroom's SmartCrusher strips that down to semantic essence, and CodeCompressor uses AST-aware compression for code-heavy contexts.

We have a live ROI calculator you can plug your own numbers into:
**[roi-calculator link]**

Want me to run a custom estimate for [Company]'s actual usage patterns?

Best,
[Your Name]

---

## Touch 3 — Day 8: The Security One-Pager

**Subject:** "Is my code safe?" — Here's our answer

[First Name],

The #1 objection we hear from enterprise teams: "If you're proxying our prompts, isn't that a security risk?"

Fair question. Here's our answer:

**Headroom never sees your data.**

- **Local-first:** Runs on your infrastructure (Docker, K8s, or bare metal)
- **No credential storage:** We never touch your API keys
- **Passthrough mode:** Tokens pass through encrypted, never logged
- **Self-hosted option:** Air-gapped deployment available
- **SSO/RBAC:** Enterprise tier includes SAML, audit logging, retention controls

We put this all in a one-pager for your InfoSec team:
**[security-one-pager link]**

No vendor lock-in. No data leaves your network. No surprises.

Happy to jump on a call with your security team if that's helpful.

Best,
[Your Name]

---

## Touch 4 — Day 12: The Breakup

**Subject:** Closing the loop

[First Name],

I've reached out a few times about cutting your LLM costs with Headroom. I know you're busy, so I'll keep this short:

If reducing your token spend by 60%+ while keeping your agents fast and accurate is a priority — I'd love 15 minutes to show you how.

If not, no worries at all. I'll get out of your hair.

Either way, here's the ROI calculator if you want to play with the numbers yourself: **[roi-calculator link]**

Best of luck with [Company]'s growth.

[Your Name]
Pitch to Ship

P.S. — We're running a pilot program for the next 10 teams. If timing is better in a few weeks, just reply and I'll set something up.

---

## Sequence Metrics

| Metric | Target |
|--------|--------|
| Open rate | 40%+ |
| Reply rate | 8%+ |
| Demo booked | 3-5 per 50 contacts |
| Pilot conversion | 50% of demos |
| Pilot → paid | 30%+ |

## Tools Recommended

- **Prospecting:** Apollo.io, LinkedIn Sales Navigator
- **Email automation:** Instantly.ai, Lemlist, or Smartlead
- **CRM:** HubSpot (free tier) or Attio
- **ROI Calculator:** headroom.sh/roi (your local HTML file)
- **Security One-Pager:** headroom.sh/security (your markdown doc)
