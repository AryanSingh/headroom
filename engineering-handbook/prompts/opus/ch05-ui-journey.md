---
id: PROMPT-CH05-OPUS-01
kind: prompt
chapter: CH-05
model_family: opus
workload_type: cross-journey UI state and authorization synthesis
objective: Map critical journeys, state transitions, permissions, and evidence gaps.
inputs: [journey map, route list, API contracts, role matrix, state designs]
boundaries: [Use supplied material only, do not assert UI behavior without tests or traces]
evidence: [Cite route, state, and fixture artifacts]
output_schema: {type: ui-journey-map, fields: [journeys, states, authorization_edges, evidence_gaps, test_order]}
uncertainty: Separate observed and designed states.
stop_conditions: [missing journey priority or role matrix]
escalation: Send protected-data or accessibility risk to owning leads.
---

# Opus UI journey prompt

Produce a risk-ranked state and authorization map with evidence gaps.
