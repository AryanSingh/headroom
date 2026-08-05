---
id: PROMPT-CH11-HAIKU-01
kind: prompt
chapter: CH-11
model_family: haiku
workload_type: commercial offer and entitlement inventory normalization
objective: Convert supplied commercial records into a compact inventory of offers, effective dates, entitlements, meters, owners, and missing evidence.
inputs: [offer catalog, entitlement records, meter definitions, pricing revisions, owner list, support routes]
boundaries: [normalize supplied records only, do not infer price, grant access, or invent lifecycle rules]
evidence: [preserve offer ID, revision, effective date, entitlement reference, meter ID, owner, and source reference]
output_schema: {type: commercial-offer-inventory, fields: [offers, entitlements, meters, lifecycle-rules, owners, evidence-gaps]}
uncertainty: Use unknown for an absent effective date, entitlement boundary, meter, owner, or support route.
stop_conditions: [missing offer records, records cannot be associated with an owner or effective revision]
escalation: Send active offers without a stable entitlement or accountable owner to the commercial product owner.
---

# Haiku commercial offer inventory prompt

Create one compact row per offer or add-on. Preserve the declared effective revision, entitlement and meter references, owner, and support route. Do not turn an absent catalog field into a product promise.
