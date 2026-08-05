---
id: PROMPT-CH05-HAIKU-01
kind: prompt
chapter: CH-05
model_family: haiku
workload_type: mechanical UI route and state inventory
objective: Normalize supplied routes, roles, fixtures, and components into state-matrix candidates.
inputs: [route list, role list, fixture list, component inventory]
boundaries: [Do not infer accessibility or authorization correctness]
evidence: [Preserve source identifiers]
output_schema: {type: ui-inventory, fields: [route, role, state, fixture, source, gap]}
uncertainty: Record incomplete mappings as gaps.
stop_conditions: [missing route identifiers or secret-bearing fixtures]
escalation: Send ambiguous mappings to UI recorder.
---

# Haiku UI inventory prompt

Normalize routes and state fixtures without judging correctness.
