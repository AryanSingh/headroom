---
id: PROMPT-CH05-SONNET-01
kind: prompt
chapter: CH-05
model_family: sonnet
workload_type: focused UI state evidence review
objective: Review one route/state transition for safe content, semantics, recovery, and regression coverage.
inputs: [route, role, fixture response, trace, screenshot, accessibility result]
boundaries: [Do not access live accounts or infer unobserved responsive behavior]
evidence: [Cite fixture and test artifacts]
output_schema: {type: ui-state-review, fields: [status, observed_state, risks, accessibility_notes, regression_test]}
uncertainty: Mark missing viewport/role evidence unresolved.
stop_conditions: [missing fixture, protected customer content, absent route context]
escalation: Send authorization or accessibility blockers to owners.
---

# Sonnet UI state prompt

Assess one supplied state transition and define a deterministic regression test.
