# Cutctx Pilot Success Metrics & Reporting Format

**Date:** June 13, 2026  
**Purpose:** Standardized framework for measuring and reporting pilot value

---

## Pilot Structure

### Duration
- **Standard:** 14 days (2 weeks)
- **Extended:** 30 days (for complex deployments)

### Success Criteria (Agreed at Kickoff)
Every pilot must have measurable success criteria defined before deployment:

1. **Primary metric:** Token savings percentage (target: >50%)
2. **Secondary metric:** Latency impact (target: <5% increase)
3. **Quality metric:** Output quality maintained (subjective + objective)
4. **Governance metric:** Required admin or enterprise controls verified if in scope
5. **Adoption metric:** Team willingness to continue after pilot

---

## Baseline Metrics (Pre-Cutctx)

Capture these BEFORE deploying Cutctx:

### Usage Metrics
| Metric | How to Measure | Example |
|--------|---------------|---------|
| Monthly LLM spend | Provider billing dashboard | $15,000/month |
| Daily API requests | Provider usage API or logs | 500 requests/day |
| Average input tokens/request | Provider usage API | 8,000 tokens |
| Average output tokens/request | Provider usage API | 2,000 tokens |
| Tool output requests/day | Agent logs or proxy logs | 200 requests/day |
| Context-limit errors/week | Agent error logs | 12 errors/week |
| Retry rate | Agent logs | 8% of requests |

### Workflow Metrics
| Metric | How to Measure | Example |
|--------|---------------|---------|
| Average agent run time | Timing logs | 45 seconds |
| Time to first useful response | User observation | 12 seconds |
| Context-limit workarounds | User interviews | "We truncate logs manually" |
| Provider switching frequency | Provider logs | "Sometimes fall back to cheaper model" |

---

## During-Cutctx Metrics

### Compression Metrics (from Cutctx /stats)
| Metric | Source | Target |
|--------|--------|--------|
| Compression ratio | /stats endpoint | >60% |
| Tokens saved per request | /stats endpoint | >3,000 |
| Total tokens saved (daily) | /stats endpoint | Growing |
| Compression latency (p50) | /stats endpoint | <10ms |
| Compression latency (p99) | /stats endpoint | <50ms |
| Transforms applied | /stats endpoint | By type |

### Quality Metrics
| Metric | How to Measure | Target |
|--------|---------------|--------|
| Output quality (subjective) | User feedback survey | "Same or better" |
| Context-limit errors | Agent error logs | Reduced by >50% |
| Retry rate | Agent logs | Reduced by >30% |
| Compression rollbacks | Cutctx logs | <2% of requests |
| Agent failure rate | Agent logs | No increase |

### Governance Metrics
| Metric | How to Measure | Target |
|--------|---------------|--------|
| Admin auth verified | Admin walkthrough | Pass |
| Audit export verified | Export endpoint | Pass when in scope |
| Retention settings reviewed | Admin checklist | Pass when in scope |
| RBAC roles validated | Role-based endpoint access | Pass when in scope |

### Performance Metrics
| Metric | How to Measure | Target |
|--------|---------------|--------|
| Proxy latency (p50) | Cutctx logs | <15ms |
| Proxy latency (p99) | Cutctx logs | <100ms |
| End-to-end agent latency | Agent timing | <5% increase |
| Memory usage | System monitoring | <500MB |

---

## Weekly Pilot Report Template

### Week N Report — [Customer Name]

**Period:** [Start Date] – [End Date]  
**Pilot Day:** [N] of 14

#### Executive Summary
> [1-2 sentence summary of the week's results]

#### Key Metrics

| Metric | Baseline | This Week | Change | Status |
|--------|----------|-----------|--------|--------|
| Compression ratio | — | 72% | — | ✅ On track |
| Tokens saved (weekly) | — | 1.2M | — | ✅ |
| Estimated cost savings | — | $3,600 | — | ✅ |
| Context-limit errors | 12/week | 4/week | -67% | ✅ |
| Quality (user feedback) | — | "Good" | — | ✅ |
| Proxy latency (p50) | — | 8ms | — | ✅ |
| Governance milestone | — | Audit export verified | — | ✅ |

#### Deployment Status
- [ ] Proxy running stable
- [ ] Dashboard accessible
- [ ] No critical issues
- [ ] Team onboarded

#### Issues & Resolutions
| Issue | Severity | Status | Resolution |
|-------|----------|--------|------------|
| [Issue 1] | Low | Resolved | [How it was fixed] |

#### User Feedback
> "[Direct quote from pilot participant]"

#### Next Week Plan
- [ ] [Planned action 1]
- [ ] [Planned action 2]

#### Risk Assessment
- **Technical risk:** Low / Medium / High
- **Adoption risk:** Low / Medium / High
- **Timeline risk:** Low / Medium / High

---

## Final Pilot Report Template

### Pilot Completion Report — [Customer Name]

**Pilot Duration:** [Start] – [End] (14 days)  
**Overall Result:** ✅ Successful / ⚠️ Partial / ❌ Unsuccessful

#### ROI Summary

| Metric | Baseline | Post-Cutctx | Improvement | Annual Value |
|--------|----------|---------------|-------------|--------------|
| Monthly LLM spend | $15,000 | $6,750 | -55% | $99,000 saved |
| Context-limit errors | 48/month | 12/month | -75% | — |
| Retry rate | 8% | 3% | -63% | $1,800 saved |
| Engineering time (context issues) | 40 hrs/month | 15 hrs/month | -63% | $37,500 saved |
| **Total annual value** | | | | **$138,300** |

#### Recommended Tier
- **Team ($18k/yr):** [Justification]
- **Business ($42k/yr):** [Justification]
- **Enterprise ($60k+/yr):** [Justification]

#### Quality Assessment
- **Compression quality:** Excellent / Good / Acceptable / Poor
- **Output quality impact:** None / Minimal / Noticeable / Significant
- **User satisfaction:** Very satisfied / Satisfied / Neutral / Dissatisfied

#### Deployment Assessment
- **Installation ease:** Easy / Moderate / Difficult
- **Configuration complexity:** Simple / Moderate / Complex
- **Ongoing maintenance:** Minimal / Low / Moderate / High

#### Recommendations
1. [Recommendation 1]
2. [Recommendation 2]
3. [Recommendation 3]

#### Next Steps
- [ ] [Action item 1 — owner — date]
- [ ] [Action item 2 — owner — date]
- [ ] [Action item 3 — owner — date]

---

## Pilot Kickoff Checklist

Before starting a pilot, confirm:

- [ ] Success criteria defined and agreed
- [ ] Baseline metrics captured
- [ ] Deployment path chosen (local/Docker/K8s)
- [ ] Access to /stats endpoint confirmed
- [ ] Dashboard access configured
- [ ] Weekly review cadence set (recommend: Wednesday)
- [ ] Escalation path defined
- [ ] Point of contact identified
- [ ] Trial license key issued (if applicable)
- [ ] Rollback plan documented

---

## Pilot Success Criteria Rubric

| Criterion | Weight | Threshold | How Measured |
|-----------|--------|-----------|--------------|
| Token savings >50% | 30% | Must pass | /stats compression ratio |
| Quality maintained | 25% | Must pass | User survey + error logs |
| Latency <5% impact | 15% | Must pass | Timing comparison |
| Team adoption >70% | 15% | Should pass | Usage tracking |
| No critical issues | 15% | Must pass | Issue log |

**Scoring:**
- **Pass (proceed to contract):** All "must pass" criteria met
- **Conditional (extend pilot):** 1 "must pass" not met, but fixable
- **Fail (do not proceed):** 2+ "must pass" not met
