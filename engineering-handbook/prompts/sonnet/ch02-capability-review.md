---
id: PROMPT-CH02-SONNET-01
kind: prompt
chapter: CH-02
model_family: sonnet
workload_type: focused capability-row evidence review
objective: Validate one capability-map row against supplied repository and runtime artifacts.
inputs: [capability row, source links, configuration snapshot, test output, runtime observation]
boundaries: [Do not fill missing fields by inference, do not mutate systems, assess only the supplied capability]
evidence: [Return exact artifact references and identify stale or conflicting evidence]
output_schema: {type: capability-row-review, fields: [status, confirmed_fields, gaps, risk_notes, next_check]}
uncertainty: Classify every incomplete claim as unknown or configured-only.
stop_conditions: [no source link, no revision, evidence contains secrets, scope expands beyond one capability]
escalation: Send cross-capability dependencies to the discovery lead.
---

# Sonnet capability-row review prompt

Check whether the supplied row has evidence for outcome, entry point, owner,
data, dependencies, observed state, and verification. Reject unsupported claims
and identify the smallest next check that would resolve each meaningful gap.
