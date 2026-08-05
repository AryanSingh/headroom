---
id: PROMPT-CH17-SONNET-01
kind: prompt
chapter: CH-17
model_family: sonnet
standards: [NIST-AI-RMF-1.0, NIST-AI-600-1]
workload_type: focused candidate-versus-baseline regression evidence review
objective: Determine whether one task class has enough case-level evidence to support or block a candidate route-policy release decision.
inputs: [candidate results, baseline results, rubric, case IDs, route traces, safety decisions, human adjudications, materiality threshold]
boundaries: [review the supplied task class and time window only, do not score missing outputs or infer route traces]
evidence: [cite case ID, rubric version, candidate and baseline versions, route trace, safety record, adjudication, and threshold]
output_schema: {type: regression-evidence-review, fields: [verdict, regressions, route-check, safety-check, adjudication-summary, missing-evidence, release-recommendation]}
uncertainty: Mark unavailable outputs, unresolved rubric disagreement, missing traces, and unsupported baseline comparisons as unknown.
stop_conditions: [missing case identifiers, absent candidate or baseline version, no rubric, unavailable safety evidence]
escalation: Send material regression, unsafe route selection, or unresolved evaluator disagreement to the evaluation and release owners.
---

# Sonnet AI regression evidence review prompt

Review a single task class case by case. Confirm the candidate and baseline are comparable, the expected route and safety decision were observed, and the quality change exceeds or stays within the stated materiality threshold. Return the smallest concrete evidence gap that prevents a release recommendation.
