---
id: PROMPT-CH19-OPUS-01
kind: prompt
chapter: CH-19
model_family: opus
workload_type: cross-signal production observability gap analysis
objective: Assess whether supplied telemetry, alerts, dashboards, and business evidence support safe incident detection and reconstruction.
inputs: [service inventory, telemetry contracts, alert rules, dashboards, traces, logs, metrics, incident records]
boundaries: [analyze supplied artifacts only, do not access telemetry systems, do not reproduce sensitive values]
evidence: [cite outcome, signal, query, alert, retention or access decision, incident record, and owner]
output_schema: {type: observability-gap-analysis, fields: [outcome-map, correlation-gaps, unsafe-data-risks, alert-quality, prioritized-remediation]}
uncertainty: Separate observed signal behavior, supported inference, and missing instrumentation.
stop_conditions: [absent critical-outcome map, unavailable alert definitions, no sample evidence]
escalation: Escalate possible sensitive-data exposure, blind critical path, or unowned alert to security and SRE owners.
---

# Opus observability gap analysis prompt

Trace each critical outcome across client, dependency, queue, and business evidence. Identify where an operator cannot safely detect, explain, or contain an incident.
