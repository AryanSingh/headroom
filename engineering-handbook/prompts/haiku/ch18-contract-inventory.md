---
id: PROMPT-CH18-HAIKU-01
kind: prompt
chapter: CH-18
model_family: haiku
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
workload_type: API and SDK support-inventory normalization
objective: Normalize supplied interface versions, fields, error contracts, client versions, support windows, owners, and evidence references into a compact compatibility inventory.
inputs: [API specifications, SDK registry, consumer list, support policy, error catalog, deprecation register, compatibility matrix, evidence links]
boundaries: [normalize supplied records only, do not infer compatibility, risk, usage, or deprecation completion]
evidence: [preserve interface, version, client, field, error code, tenant or scope boundary, support window, owner, and evidence reference]
output_schema: {type: compatibility-inventory, fields: [interfaces, versions, supported-consumers, fields, error-contracts, authority-boundaries, deprecations, evidence-gaps]}
uncertainty: Use unknown for absent support status, field semantics, error code, authority behavior, owner, adoption signal, or evidence reference.
stop_conditions: [missing interface version, missing support policy, records cannot be associated with an owner]
escalation: Send unowned interfaces, unversioned breaking changes, or missing authority records to the API platform owner.
---

# Haiku contract inventory prompt

Create one compact record per supplied interface-version and supported client. Preserve declared fields, error codes, authority boundaries, support window, owner, and evidence reference. Do not convert a successful endpoint response into compatibility approval.
