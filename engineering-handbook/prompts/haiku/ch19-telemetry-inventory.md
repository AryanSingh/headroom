---
id: PROMPT-CH19-HAIKU-01
kind: prompt
chapter: CH-19
model_family: haiku
workload_type: telemetry contract inventory normalization
objective: Normalize supplied telemetry fields, signals, owners, retention, and redaction status into a compact inventory.
inputs: [telemetry schemas, service inventory, alert registry, retention policy]
boundaries: [copy supplied metadata only, do not classify unseen data, do not propose production queries]
evidence: [retain source contract or registry identifier for every row]
output_schema: {type: telemetry-inventory, fields: [signal_id, outcome, correlation_field, owner, retention, redaction_status, alert_link]}
uncertainty: Use unknown for unprovided fields and retain the source identifier.
stop_conditions: [unparseable telemetry source, missing signal identifier]
escalation: Flag missing correlation, owner, retention, or redaction fields for observability triage.
---

# Haiku telemetry inventory prompt

Return a compact source-linked inventory. Preserve uncertainty and identify records that require owner review.
