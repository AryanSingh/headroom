# Headroom — Design Partner Outreach Sequence

**Goal:** land 3–5 design partners for a free, instrumented 2-week pilot. Pairs with [`design-partner-onepager.md`](design-partner-onepager.md). Builds on [`outreach-sequences.md`](outreach-sequences.md) (target roles, tracker) with messaging updated for the now-live spend ledger + measured memory impact.

## Who to target (highest-fit first)

- **AI Platform / Agent-Infra Lead** — owns the agent stack, feels the bill, has cross-team view. Best fit.
- **Developer Productivity / DevEx Lead** — owns agent tooling org-wide.
- **Staff/Principal Eng (AI infra)** — technical champion who'll run the pilot.
- **Founder/CTO of an AI-native startup** — fast decision, high agent spend.

**Qualifier (put in your list, not the email):** runs **3+ AI agents** (Claude Code / Cursor / Codex / Aider / internal) and has no single view of what they cost.

## Positioning (lead with these, in order)

1. Cross-provider cost control (not provider-locked). 2. Reversible — safe for coding agents. 3. Local-first — prompts never leave, telemetry off by default. 4. You get *measured* numbers, not claims. **Don't** lead with "prompt compression" (sounds like a commodity).

---

## Email sequence (4 touches over ~12 days)

### Touch 1 — Day 0 (cold, value-led)

**Subject:** what are your AI agents actually costing you?

> Hi {First},
>
> Quick one — you're running {Claude Code / Cursor / agents} at {Company}. Most teams I talk to can't say what each project or agent actually costs, and they're paying for a lot of tool-output and log tokens the model never needed.
>
> We built Headroom: a drop-in proxy (zero code changes) that compresses what your agents read by **60–95%** before it hits the model — same answers, originals kept retrievable — across Anthropic/OpenAI/Bedrock/Vertex, running **in your own infra** (prompts never leave).
>
> We're taking on a few design partners. It's a **free, fully instrumented 2-week pilot**: we deploy it in front of one team, agree success criteria up front, and hand you a spend dashboard + an ROI report with *your* real numbers. You keep all the data.
>
> Worth a 30-min look? I can show the savings on a workload like yours.
>
> {Name}

### Touch 2 — Day 3 (proof + specificity)

**Subject:** re: what are your AI agents actually costing you?

> {First} — concrete proof point: on real agent workloads we see code-search prompts drop **92%** (17.8k → 1.4k tokens) and SRE-debugging **92%**, with accuracy unchanged on standard benchmarks. Reversible, so the agent can pull back anything it needs.
>
> For the pilot you'd also get the part teams ask for most: a **per-project / per-agent / per-model spend ledger** ($ spent *and* saved, exportable), plus per-team budgets and model allowlists. 30 minutes this week?

### Touch 3 — Day 7 (the governance/независence angle)

**Subject:** the part provider-native caching can't do

> {First} — one more reason this matters: provider caching only helps *inside* one provider and assumes you're fine sending everything to them. Headroom is cross-provider, local-first, and lets you cap and attribute spend per team — the things a provider won't build because it helps you spend less with them.
>
> Happy to scope a 2-week pilot around whatever you care about most — cost, governance, or both. Want me to send a one-pager?

### Touch 4 — Day 12 (breakup)

**Subject:** closing the loop

> {First} — I'll stop here so I'm not cluttering your inbox. If cutting agent spend or getting cross-team cost visibility moves up the list, just reply and I'll set up a pilot. One-pager attached either way.

---

## LinkedIn DM variant (short)

> Hi {First} — you're running AI agents at {Company}. We cut agent token spend 60–95% (same answers, reversible) with a drop-in proxy that runs in your own infra, and give you per-project cost visibility + budgets. Taking on a few design partners for a free instrumented 2-week pilot — you keep the data + get an ROI report. Open to a quick look?

---

## What the pilot measures (say this on the kickoff call)

Agreed up front, captured as baseline → with-Headroom (see [`pilot-success-metrics.md`](pilot-success-metrics.md)):

- **Token + $ savings** per project/agent/model (from the spend ledger).
- **Latency impact** (target <5%).
- **Quality held** (task success unchanged; reversible retrieval as the safety net).
- **Memory lift** — success-rate delta from `headroom learn` corrections (the matched-pair memory-impact report). *This is the number that proves the moat — make sure it's instrumented from day 1.*
- **Adoption** — would the team keep it after the pilot?

## Handling the obvious objections

- *"Provider caching already does this."* → Single-provider only, lossy, no cross-team governance, and it keeps your data with them. Headroom is cross-provider, reversible, local-first, with spend control.
- *"Is it safe for coding agents?"* → Reversible (CCR): originals cached; the agent retrieves any dropped span. Accuracy preserved on benchmarks; the pilot verifies on your tasks.
- *"Data security?"* → Runs in your infra/VPC; prompts never leave; network telemetry off by default; SSO/RBAC + tamper-evident audit for review.
- *"Effort to try?"* → Drop-in proxy, zero code changes; ~30 min to deploy in front of one team.

## Run-of-show

Week 0: 30-min kickoff, agree success criteria, deploy proxy (baseline first). → Weeks 1–2: collect metrics, mid-point check-in. → Debrief: ROI report with their numbers; decide on continuing at founding-customer pricing + optional case study.

**Target:** 30–40 qualified contacts → 8–10 calls → 3–5 pilots → ≥1 validated ROI + case study. Track in the tracker in `outreach-sequences.md`.
