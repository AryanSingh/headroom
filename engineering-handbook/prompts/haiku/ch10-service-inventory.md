---
id: PROMPT-CH10-HAIKU-01
kind: prompt
chapter: CH-10
model_family: haiku
workload_type: reliability service inventory normalization
objective: Convert supplied service records into a compact inventory of objectives, dependencies, recovery requirements, and evidence gaps.
inputs: [service records, workload classes, objective registry, dependency map, recovery register, owner list]
boundaries: [normalize supplied records only, do not estimate capacity, infer recovery, or invent ownership]
evidence: [preserve each supplied service ID, objective revision, dependency reference, recovery record, owner, and source reference]
output_schema: {type: reliability-inventory, fields: [services, critical_outcomes, objectives, dependencies, recovery_status, evidence_gaps]}
uncertainty: Use unknown for absent objective, dependency, owner, telemetry, or recovery evidence.
stop_conditions: [missing service records, records cannot be associated with a workload or owner]
escalation: Send critical services without an objective, recovery record, or accountable owner to the SRE owner.
---

# Haiku reliability inventory prompt

Create one compact row per supplied service or workload. Preserve the stated objective, dependency references, recovery status, owner, and evidence gap. Do not turn an absent recovery record or a healthy-process signal into evidence of a safe business outcome.
