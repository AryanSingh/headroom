---
id: PROMPT-CH10-SONNET-01
kind: prompt
chapter: CH-10
model_family: sonnet
workload_type: focused service-objective evidence review
objective: Determine whether one declared service objective is supported by an appropriate indicator, fixture results, and bounded failure evidence.
inputs: [single objective, workload definition, measurement query, load fixture result, degradation trace, error-budget decision]
boundaries: [review one objective only, use supplied evidence only, do not calculate unstated percentiles or approve exceptions]
evidence: [cite the objective revision, measurement boundary, result window, fixture identity, degradation behavior, and decision record]
output_schema: {type: objective-evidence-review, fields: [verdict, measurement_validity, observed_results, gaps, required_follow_up]}
uncertainty: Label missing client-boundary measurement, incomplete workload shape, and unsupported correctness claims as unresolved.
stop_conditions: [missing objective window, absent measurement query, unidentifiable fixture, no evidence of failure behavior]
escalation: Send an unsupported objective, exhausted error budget, or incorrect accepted outcome to the service owner and release owner.
---

# Sonnet service-objective evidence review prompt

Review the stated objective against one workload. Confirm the indicator measures a client-visible and correct outcome, the fixture resembles its declared traffic shape, and the observed degradation is safe. List the smallest evidence or test needed to convert each unresolved claim into a release decision.
