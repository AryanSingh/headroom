---
id: PROMPT-CH01-HAIKU-01
kind: prompt
chapter: CH-01
model_family: haiku
workload_type: mechanical audit-evidence normalization
objective: Convert supplied audit artifacts into an evidence-register row set without judging risk.
inputs: [artifact list, timestamps, commands, revisions, owners]
boundaries: [Do not add facts, do not assign severity, do not access external systems]
evidence: [Preserve source artifact identifiers exactly and flag missing fields]
output_schema: {type: evidence-register-rows, fields: [artifact_id, source, revision, collected_at, owner, gap]}
uncertainty: Use gap fields for missing or ambiguous values.
stop_conditions: [artifact identifiers are absent, fields contain secrets, source data is unreadable]
escalation: Route secret-bearing or unreadable evidence to the audit recorder.
---

# Haiku evidence normalization prompt

Transform only the provided artifact metadata into evidence-register rows. Keep
identifiers verbatim, normalize timestamps to ISO 8601 when possible, and put
unavailable values in `gap`. Do not evaluate the release, infer test outcomes,
or rewrite sensitive payloads.
