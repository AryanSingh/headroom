---
id: PROMPT-CH16-HAIKU-01
kind: prompt
chapter: CH-16
model_family: haiku
workload_type: migration inventory normalization
objective: Normalize supplied migration records into a concise inventory of scope, compatibility stage, tenant boundary, checkpoint, reconciliation state, recovery evidence, and owner.
inputs: [migration tickets, schema names, service dependencies, execution statuses, evidence links]
boundaries: [summarize supplied records only, do not infer missing data or access databases, do not recommend a release decision]
evidence: [preserve supplied migration ID, schema version, dependency name, tenant scope, stage, evidence reference, and owner]
output_schema: {type: migration-inventory, fields: [migration-id, scope, compatibility-stage, tenant-boundary, checkpoint-status, reconciliation-status, recovery-evidence, owner, gaps]}
uncertainty: Mark missing fields as unknown and retain source references without filling them from context.
stop_conditions: [no supplied records]
escalation: Flag any supplied cross-tenant scope, destructive stage, missing owner, or absent recovery reference for human review.
---

# Haiku migration inventory prompt

Convert the supplied migration records into one compact, source-attributed inventory. Preserve unknowns and distinguish a planned control from evidence that it ran.
