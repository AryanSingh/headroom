---
id: PROMPT-CH06-SONNET-01
kind: prompt
chapter: CH-06
model_family: sonnet
workload_type: focused API authorization evidence review
objective: Determine whether supplied tests prove resource-level and tenant-level authorization for one API flow.
inputs: [route handler, policy code, fixture identities, request results, trace excerpts]
boundaries: [review one declared flow, do not execute code, do not inspect production records]
evidence: [cite exact authorization branch, fixture principal, requested resource, and observed outcome]
output_schema: {type: authorization-review, fields: [status, decision_path, missing_cases, severity, remediation_tests]}
uncertainty: Mark inferred policy behavior and missing fixture coverage as unresolved.
stop_conditions: [missing handler or policy evidence, identities are not attributable to tenant and role]
escalation: Escalate cross-tenant or privilege-escalation indicators to the security owner.
---

# Sonnet API authorization review prompt

Review only the supplied endpoint and evidence. Trace authentication through
resource resolution and policy decision. Decide whether same-tenant, cross-
tenant, insufficient-role, and missing-identity behavior are proven. Give a
minimal reproduction test for every unsupported claim.
