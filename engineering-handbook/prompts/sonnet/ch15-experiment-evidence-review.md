---
id: PROMPT-CH15-SONNET-01
kind: prompt
chapter: CH-15
model_family: sonnet
workload_type: bounded chaos experiment evidence review
objective: Determine whether one supplied experiment record satisfies its hypothesis, scope, abort, recovery, and evidence requirements.
inputs: [experiment plan, baseline, injection timeline, telemetry queries, ledger reconciliation, recovery result]
boundaries: [review one experiment only, do not infer omitted results, do not approve release exceptions]
evidence: [cite plan field, timestamp, threshold, result query, reconciliation result, and owner]
output_schema: {type: experiment-evidence-review, fields: [requirement-status, missing-evidence, contradictions, finding-drafts, retest-steps]}
uncertainty: Mark missing or conflicting records as unknown rather than passing them by implication.
stop_conditions: [missing abort threshold, no scope evidence, unavailable business reconciliation]
escalation: Escalate a breached stop condition, duplicate outcome, or tenant-scope failure to the experiment owner.
---

# Sonnet experiment evidence review prompt

Compare the declared fault and steady state with the observed record. Return a requirement-by-requirement evidence result and a minimum safe retest plan.
