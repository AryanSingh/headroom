---
id: PROMPT-CH08-HAIKU-01
kind: prompt
chapter: CH-08
model_family: haiku
workload_type: routing inventory normalization
objective: Convert supplied route records into a compact, auditable workload-to-policy inventory.
inputs: [route records, workload classes, provider allowlists, policy identifiers, owner list]
boundaries: [normalize supplied records only, do not guess constraints or provider capabilities]
evidence: [preserve each supplied policy ID, workload label, owner, and source reference]
output_schema: {type: route-inventory, fields: [workloads, allowed_candidates, required_constraints, owners, evidence_gaps]}
uncertainty: Use unknown for absent ownership, fallback rule, evaluation, or constraint evidence.
stop_conditions: [missing workload records, source records cannot be tied to a policy]
escalation: Send routes without a policy or owner to the routing owner.
---

# Haiku routing inventory prompt

Create one compact row per supplied workload class. Preserve policy ID, allowed candidates, constraint labels, owner, and evidence gap. Do not turn an omitted fallback rule into an assumed safe default.
