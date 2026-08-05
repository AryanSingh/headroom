---
id: PROMPT-CH06-HAIKU-01
kind: prompt
chapter: CH-06
model_family: haiku
workload_type: API inventory normalization
objective: Convert supplied endpoint records into a compact contract inventory with missing-evidence flags.
inputs: [OpenAPI fragments, route list, owner list, data classification notes]
boundaries: [normalize supplied records only, do not classify omitted endpoints, do not infer authorization]
evidence: [preserve supplied route and schema references in every row]
output_schema: {type: api-inventory, fields: [routes, owners, data_classes, contract_gaps, evidence_gaps]}
uncertainty: Use unknown for absent owner, classification, policy, or schema evidence.
stop_conditions: [route list is missing, source records cannot be tied to a service]
escalation: Send incomplete protected-route records to the API owner.
---

# Haiku API inventory prompt

Create one compact row per supplied route. Preserve method, path, owner,
consumer, data class, mutation status, schema reference, and evidence gap. Do
not transform a missing value into a guess.
