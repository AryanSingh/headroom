---
id: PROMPT-CH04-HAIKU-01
kind: prompt
chapter: CH-04
model_family: haiku
workload_type: mechanical desktop artifact inventory
objective: Normalize installer, IPC, permission, storage, and update records.
inputs: [artifact list, OS matrix, IPC list, storage paths]
boundaries: [Do not infer security properties or execute files]
evidence: [Preserve source identifiers]
output_schema: {type: desktop-inventory, fields: [kind, identifier, platform, source, gap]}
uncertainty: Record absent fields as gaps.
stop_conditions: [records contain secrets or lack identifiers]
escalation: Return ambiguous records to desktop recorder.
---

# Haiku desktop inventory prompt

Normalize supplied desktop artifacts without risk judgments.
