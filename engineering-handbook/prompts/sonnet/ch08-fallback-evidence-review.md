---
id: PROMPT-CH08-SONNET-01
kind: prompt
chapter: CH-08
model_family: sonnet
workload_type: focused routing fallback evidence review
objective: Decide whether one declared fallback path preserves its workload constraints and safely handles failure.
inputs: [single route policy, fixture request, candidate list, failure trace, decision record]
boundaries: [review one path only, do not call providers, do not generalize beyond supplied constraints]
evidence: [cite each retained predicate, rejected candidate, reason code, and observed terminal state]
output_schema: {type: fallback-review, fields: [verdict, preserved_constraints, missing_evidence, failure_outcome, remediation_tests]}
uncertainty: Label unsupplied provider behavior and ambiguous predicates as unresolved.
stop_conditions: [missing fixture identity, no policy revision, absent terminal decision record]
escalation: Escalate a residency, tenant, safety, or approval-boundary loss to the security owner.
---

# Sonnet fallback evidence review prompt

Review the supplied fallback path only. Verify that every original constraint survives timeout, budget, and candidate rejection. State whether queueing is the safe terminal outcome and propose the smallest regression fixture for each gap.
