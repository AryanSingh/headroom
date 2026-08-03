---
id: PROMPT-CH19-SONNET-01
kind: prompt
chapter: CH-19
model_family: sonnet
workload_type: critical alert evidence review
objective: Review one alert and its exercise record for threshold quality, ownership, route, correlation, first action, and privacy-safe evidence.
inputs: [alert definition, exercise timestamps, alert payload, route test, dashboard query, runbook, redacted trace]
boundaries: [review one alert only, do not change thresholds, do not infer production delivery from an absent route test]
evidence: [cite threshold, timestamp, owner, route, query, runbook step, and redaction assertion]
output_schema: {type: alert-evidence-review, fields: [alert-status, actionability-gaps, evidence-gaps, false-positive-risks, repair-steps]}
uncertainty: Mark absent route, query, or redaction evidence as unknown.
stop_conditions: [missing alert definition, no owner, unavailable exercise evidence]
escalation: Escalate an unowned critical alert, unsafe payload, or missed critical condition to the service owner.
---

# Sonnet alert evidence review prompt

Determine whether a responder receives enough safe, scoped information to take the first action without guessing or exposing customer content.
