# Headroom ROI Calculator & Buyer Business Case

**Date:** June 13, 2026  
**Audience:** Engineering leaders, platform teams, CFOs

---

## ROI Framework

Headroom creates value in four dimensions:

1. **Direct cost savings** — Fewer tokens sent to LLM providers
2. **Context efficiency** — More usable context fits in finite windows
3. **Reliability improvement** — Fewer context-limit errors and retries
4. **Governance value** — Team visibility, policy control, compliance

---

## Calculator Inputs

| Input | Typical Range | Example Value |
|-------|---------------|---------------|
| Monthly LLM spend | $5k–$50k | $15,000 |
| Number of agents | 2–20 | 8 |
| Average tool output tokens per request | 2,000–10,000 | 5,000 |
| Tool output requests per day | 50–500 | 200 |
| Context-limit retry rate | 5–15% | 8% |
| Average cost per retry | $0.01–$0.10 | $0.03 |
| Engineering hourly cost | $75–$200 | $125 |

---

## ROI Calculation

### Direct Token Savings

```
Monthly tool output tokens = tool_output_tokens × requests_per_day × 30 days
                           = 5,000 × 200 × 30
                           = 300,000,000 tokens/month

Compressed tokens (at 75% savings) = 300M × 0.25 = 75,000,000 tokens/month

Token cost at $3/M input tokens:
  Before: 300M × $3/M = $900/month
  After:  75M × $3/M  = $225/month
  Savings: $675/month = $8,100/year
```

### Retry Reduction

```
Monthly retries = requests_per_day × 30 × retry_rate
               = 200 × 30 × 0.08
               = 480 retries/month

Retries avoided (at 50% reduction from better context fit) = 240 retries/month

Retry cost savings = 240 × $0.03 = $7.20/month
```

### Engineering Time Savings

```
Monthly engineering hours lost to context issues = 
  (retries × avg_time_per_retry) + (context debugging × hours)
  = (480 × 0.05 hours) + (10 hours)
  = 24 + 10
  = 34 hours/month

Engineering cost savings = 34 × $125 = $4,250/month = $51,000/year
```

### Total Monthly ROI

```
Direct token savings:     $675/month
Retry cost savings:       $7/month
Engineering time savings: $4,250/month
─────────────────────────────────────
Total monthly savings:    $4,932/month
Annual savings:           $59,184/year

Headroom Team cost:       $1,500/month ($18,000/year)
Net annual benefit:       $41,184/year
ROI:                      229%
Payback period:           4.4 months
```

---

## Three ROI Case Studies

### Case 1: Coding Agents (10-person engineering team)

**Profile:**
- 10 engineers using Claude Code daily
- Average 200 tool-output requests/day across the team
- Tool outputs: code search results, file diffs, test output
- Monthly LLM spend: $12,000

**With Headroom:**
- Tool output compression: 85% average (code is highly compressible)
- Monthly token savings: $5,400
- Context-limit retries reduced by 60%
- Engineering time saved: 40 hours/month
- **Total monthly value: $8,900**
- **Annual ROI: 493%** (vs. Team tier at $18k/yr)

### Case 2: Support/Ops Agent (24/7 incident response)

**Profile:**
- 5 agents handling incidents
- Large log payloads (5,000–15,000 tokens per incident)
- 100 incidents/day
- Monthly LLM spend: $25,000

**With Headroom:**
- Log compression: 90% (logs are extremely compressible)
- Monthly token savings: $11,250
- Fewer context-limit failures during complex incidents
- Faster incident resolution (more context fits)
- **Total monthly value: $16,500**
- **Annual ROI: 680%** (vs. Business tier at $42k/yr)

### Case 3: Internal AI Platform (multi-team, multi-provider)

**Profile:**
- 50 engineers across 5 teams
- Using Anthropic, OpenAI, and Bedrock
- Platform team manages shared agent infrastructure
- Monthly LLM spend: $40,000

**With Headroom:**
- Cross-provider optimization (single layer for all providers)
- Tool output compression: 75% average
- Monthly token savings: $15,000
- Team analytics showing where spend goes
- Policy presets per team
- Governance and audit trail
- **Total monthly value: $22,000**
- **Annual ROI: 471%** (vs. Business tier at $42k/yr)

---

## Value Translation Cheat Sheet

| Technical Metric | Business Value |
|-----------------|----------------|
| 60–95% token compression | $5k–$20k/month savings on $15k–$50k spend |
| Reversible retrieval (CCR) | No quality loss — original data available on demand |
| Cross-provider optimization | Single infrastructure layer, no vendor lock-in |
| Context window efficiency | Fewer retries, faster agent runs, more reliable workflows |
| Team analytics | Visibility into AI spend by team, project, and agent |
| Policy presets | Consistent compression behavior across teams |
| Local-first deployment | No data leaves infrastructure, no compliance risk |
| Audit logs (Enterprise) | Procurement approval, regulatory compliance |

---

## Buyer-Facing Business Case Template

### For the Engineering Leader

> **Problem:** Our AI agents are spending $X/month on tokens, and a significant portion goes to verbose tool outputs, logs, and code search results that could be compressed without losing information.
>
> **Solution:** Headroom compresses these payloads by 60–95% with zero code changes. It runs locally, preserves originals for retrieval, and gives us visibility into where our AI spend goes.
>
> **ROI:** Based on our current spend of $X/month, we estimate $Y/month in direct savings plus reduced engineering time from fewer context-limit errors. Payback period is under 6 months.
>
> **Risk mitigation:** Headroom is local-first (no data leaves our infrastructure), uses reversible compression (no quality loss), and has a free tier we can evaluate before committing.

### For the CFO

> **Investment:** $18,000/year (Team tier) or $42,000/year (Business tier)
>
> **Return:** $59,000/year in token savings + engineering time savings
>
> **Payback:** 4.4 months
>
> **Risk:** Low — local deployment, no vendor lock-in, free tier available for evaluation
>
> **Strategic value:** As our AI usage grows, Headroom's savings scale proportionally. A 2x increase in AI spend doubles the savings while the Headroom cost stays flat.

### For the Security Buyer

> **Data residency:** All prompts and tool outputs stay on our infrastructure. Headroom never sees our data.
>
> **Compliance:** Self-hosted deployment, no external API calls for compression, aggregate-only telemetry (opt-in).
>
> **Enterprise features:** SSO/SAML, RBAC, audit logs, retention controls coming in Enterprise tier.
>
> **Air-gap support:** Fully operable offline after initial model download.

---

## Pricing Justification

| Tier | Annual Price | Target ROI | Break-Even |
|------|-------------|------------|------------|
| Team ($18k/yr) | $18,000 | >$54k value (3x) | $1,500/month savings |
| Business ($42k/yr) | $42,000 | >$126k value (3x) | $3,500/month savings |
| Enterprise ($60k–$150k) | $60,000–$150,000 | >$180k value (3x) | $5,000–$12,500/month savings |

**Pricing rule:** Capture 10–20% of measurable customer value. If Headroom saves a customer $60k/year, pricing at $18k/year (30%) is aggressive but justified for early lighthouse accounts. Standard pricing should target 15–20% of value.

---

## Competitive ROI Comparison

| Solution | Annual Cost | What You Get | ROI Comparison |
|----------|------------|--------------|----------------|
| Headroom Team | $18k | 60–95% compression, reversible, cross-provider, local | Best value for teams |
| Headroom Business | $42k | + analytics, workspace, policy | Best value for orgs |
| Token Company (hosted) | $30k–$100k | Lossy compression, cloud-only | Higher cost, less control |
| Morph Compact (hosted) | $24k+ | Verbatim deletion, cloud-only | Higher cost, no reversibility |
| Native caching (free) | $0 | Provider-locked, no governance | No cross-provider, no analytics |
| Manual optimization | $50k+ (engineering time) | Fragile, doesn't scale | Higher total cost |
