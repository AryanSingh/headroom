---
id: PROMPT-CH06-OPUS-01
kind: prompt
chapter: CH-06
model_family: opus
workload_type: cross-service API contract and risk analysis
objective: Produce a prioritized compatibility and security risk map for a changed API surface.
inputs: [route inventory, schemas, consumer list, identity model, change set, test evidence]
boundaries: [inspect supplied artifacts only, do not call services, do not assume undocumented consumers]
evidence: [cite route, schema field, consumer source, and test evidence for each claim]
output_schema: {type: api-risk-map, fields: [contract_map, compatibility_risks, authorization_risks, mutation_risks, verification_order]}
uncertainty: Separate observed contracts, reasoned inference, and unknown consumer behavior.
stop_conditions: [missing route inventory, absent identity model, unavailable schema or change set]
escalation: Route critical authorization or data-exposure concerns to the API and security owners.
---

# Opus API contract analysis prompt

Analyze the supplied API change as a versioned, multi-consumer contract. Map
routes, schemas, authorization decision points, data classes, mutations,
idempotency, errors, and dependencies. Rank risks by user impact and evidence.
Return the declared structure; do not invent traffic, consumers, or controls.
