---
id: PROMPT-CH04-OPUS-01
kind: prompt
chapter: CH-04
model_family: opus
workload_type: cross-lifecycle desktop risk synthesis
objective: Map install, IPC, update, local-state, and recovery risks from supplied evidence.
inputs: [installer evidence, IPC inventory, schema history, OS matrix, logs]
boundaries: [Use supplied artifacts only, do not execute installers or claim platform behavior without evidence]
evidence: [Cite artifact IDs and separate observed, configured, and inferred claims]
output_schema: {type: desktop-risk-map, fields: [lifecycle_paths, privileged_boundaries, recovery_gaps, verification_order]}
uncertainty: Label absent platform evidence unknown.
stop_conditions: [missing version matrix, unavailable local-state description]
escalation: Send data-loss or privilege ambiguity to desktop and security owners.
---

# Opus desktop lifecycle prompt

Build a risk-ranked lifecycle map from install through recovery, citing evidence.
