---
id: APP-COMPETITIVE-BENCHMARKING-001
kind: reference
title: Competitive Benchmarking Framework
purpose: Provide a repeatable evidence method for product, engineering, and operational comparisons.
audience: [product leaders, engineering leaders, audit leads]
standards: [NIST-SSDF-1.1]
---

# Competitive Benchmarking Framework

## Purpose and boundary

Benchmarking answers a defined decision question; it is not a claim that a competitor is secure, reliable, or inferior. Use public material, authorized trials, customer-provided artifacts, and internal product evidence. Do not evade access controls, collect personal data unnecessarily, or represent inference as observed fact.

## Step 1: Write a decision brief

Record the decision, target customer segment, comparison cohort, review date, owner, and expiry. A useful question is narrow: “Which self-service diagnostic capability should Product Atlas prioritize for mid-market retailers?” A weak question is “Which competitor is best?”

Define the minimum comparable workflow before collecting evidence. For the Atlas example, the workflow is: connect a warehouse, detect invalid source data, identify affected records, correct the issue, and confirm the next forecast.

## Step 2: Build an evidence register

Each row must state the offering, claim, evidence URL or artifact, collection date, reviewer, environment, confidence, and limitation. Preserve screenshots or exports where licensing permits; otherwise retain the date, URL, and a precise observation note.

| Evidence ID | Observation | Source | Confidence | Limitation |
| --- | --- | --- | --- | --- |
| BEN-ATLAS-01 | Connector setup shows warehouse-specific examples. | Atlas trial, 2026-08-03 | High | Trial tenant has sample data only. |
| BEN-PEER-04 | Error screen identifies a failed file but not rows. | Public help article | Medium | Article may not match current enterprise plan. |

Use **observed**, **vendor-stated**, and **inferred** as separate evidence types. Only observed evidence may receive the highest confidence rating.

## Step 3: Score an observable rubric

Use a five-point scale with anchored definitions. Do not average unknown values into a positive result.

| Score | Meaning |
| --- | --- |
| 0 | Capability absent or contradicted by evidence. |
| 1 | Manual workaround exists; normal operator flow is unsupported. |
| 2 | Basic capability exists with material operator ambiguity or delay. |
| 3 | Workflow is complete for the stated cohort with documented limitations. |
| 4 | Workflow is complete, observable, and has useful recovery guidance. |
| 5 | Workflow is complete, measurable, and reduces likely operator error at scale. |

Weight criteria only after the decision owner approves the weights. Product Atlas may weight data diagnostics at 40%, time to first forecast at 30%, connector coverage at 20%, and recovery guidance at 10%. Publish both weighted and unweighted scores; the unweighted view exposes a decision distorted by weights.

## Step 4: Separate facts from interpretation

Write findings in three fields:

1. **Observation:** “The trial error screen names the import but does not list rejected rows.”
2. **Interpretation:** “Operators may need support to locate invalid records.”
3. **Decision implication:** “Test row-level diagnostics before increasing connector breadth.”

Never convert an unavailable feature into an absence claim. Use “not observed in the reviewed evidence” and record the review boundary.

## Product Atlas worked example

**Decision:** choose the next onboarding investment for a retail-planning product.

**Cohort:** Atlas, StockPilot, DemandMesh, and SupplyMap. Evidence consisted of two authorized trials, public guides, and sales demonstrations recorded with permission between 2026-07-20 and 2026-07-30.

**Result:** Atlas received 4/5 for connector setup because warehouse-specific examples reduced configuration ambiguity. It received 2/5 for diagnostics because users could see a failing import but not the affected records. The recommendation was a four-week prototype for row-level diagnostics, measured by time-to-resolution and support escalation rate. The report explicitly excluded enterprise support quality because it was not observable.

## Review and publication checklist

- [ ] The decision question, cohort, date window, and owner are recorded.
- [ ] Each scored claim has an evidence ID and confidence rating.
- [ ] Scores use approved anchored definitions; unknowns remain unknown.
- [ ] Observations, interpretation, and recommendations are separate.
- [ ] Product, legal, and security reviewers remove unsupported comparative marketing claims.
- [ ] The report includes limitations and a review-expiry date.

## Report handoff

Use [the benchmark report template](../templates/benchmark-report.md). Attach the evidence register, scoring sheet, decision record, and follow-up experiment result. Re-run a benchmark when the decision changes, the cohort changes, or the evidence expires; do not carry scores forward as perpetual truth.
