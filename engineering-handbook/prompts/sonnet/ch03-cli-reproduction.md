---
id: PROMPT-CH03-SONNET-01
kind: prompt
chapter: CH-03
model_family: sonnet
workload_type: focused CLI failure reproduction review
objective: Assess one CLI failure transcript and define the smallest safe regression test.
inputs: [command, arguments, environment, stdout, stderr, exit status, source revision]
boundaries: [Do not run commands, do not expose secrets, do not generalize beyond supplied failure]
evidence: [Preserve exit status and stream separation in the report]
output_schema: {type: cli-reproduction-review, fields: [reproduction_status, contract_break, likely_cause, regression_test, remediation]}
uncertainty: Identify unknown environment or configuration conditions.
stop_conditions: [missing exit status, missing stream capture, secret-bearing transcript]
escalation: Send credential or mutation uncertainty to the CLI owner.
---

# Sonnet CLI failure-review prompt

Review one supplied failure as a contract issue. Confirm whether output, status,
prompt behavior, or configuration precedence differs from the stated contract.
Provide a minimal safe regression test and remediation.
