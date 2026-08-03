---
id: PROMPT-CH02-HAIKU-01
kind: prompt
chapter: CH-02
model_family: haiku
workload_type: mechanical entry-point and dependency inventory normalization
objective: Normalize supplied route, command, job, provider, and owner records into capability-map candidates.
inputs: [route list, command list, job list, provider configuration, ownership records]
boundaries: [Do not infer user value or reachability, retain original identifiers, do not access external systems]
evidence: [Preserve source artifact and line/location fields for each normalized record]
output_schema: {type: inventory-candidates, fields: [kind, identifier, source, owner_hint, dependency_hint, missing_fields]}
uncertainty: Put ambiguous labels and omitted fields in missing_fields.
stop_conditions: [input lacks source identifiers, records contain credentials, format is unreadable]
escalation: Route ambiguous categories or secret-bearing records to the discovery recorder.
---

# Haiku inventory-normalization prompt

Normalize only the supplied records into candidate rows. Preserve source
identifiers, classify the record kind, and flag missing ownership or source
location. Do not claim that a candidate is a user capability or that a provider
is active.
