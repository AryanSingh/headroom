---
id: PROMPT-CH15-HAIKU-01
kind: prompt
chapter: CH-15
model_family: haiku
workload_type: chaos experiment inventory normalization
objective: Normalize supplied experiment metadata into a compact inventory of scope, fault, owner, abort, evidence location, and status.
inputs: [experiment records, service inventory, owner directory]
boundaries: [copy supplied metadata only, do not rank risks, do not manufacture missing ownership]
evidence: [retain source record identifier for every inventory row]
output_schema: {type: chaos-experiment-inventory, fields: [experiment_id, outcome, fault, scope, abort_threshold, owner, evidence_status]}
uncertainty: Use unknown for absent fields and preserve source identifiers.
stop_conditions: [unparseable source record, missing experiment identifier]
escalation: Flag experiments without scope, abort threshold, or owner for SRE triage.
---

# Haiku chaos experiment inventory prompt

Return a concise evidence inventory. Preserve unknowns and never convert absent evidence into a passing status.
