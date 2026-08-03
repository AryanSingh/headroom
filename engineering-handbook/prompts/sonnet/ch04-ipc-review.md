---
id: PROMPT-CH04-SONNET-01
kind: prompt
chapter: CH-04
model_family: sonnet
workload_type: focused privileged IPC evidence review
objective: Review one IPC route for caller validation, authorization, mutation, and audit evidence.
inputs: [IPC route, caller, handler, tests, logs]
boundaries: [Inspect supplied source only, do not infer OS permissions]
evidence: [Cite route/handler/test references]
output_schema: {type: ipc-review, fields: [status, boundary_checks, gaps, regression_test]}
uncertainty: Mark missing caller or handler evidence unknown.
stop_conditions: [route or source revision unavailable]
escalation: Route privilege concerns to security owner.
---

# Sonnet IPC review prompt

Assess one boundary and propose the smallest safe regression test.
