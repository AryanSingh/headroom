---
id: PROMPT-CH18-SONNET-01
kind: prompt
chapter: CH-18
model_family: sonnet
standards: [NIST-SSDF-1.1, OWASP-API-TOP10-2023]
workload_type: focused supported-consumer compatibility evidence review
objective: Determine whether one declared consumer-version has sufficient request, response, error, authority, and rollback evidence for a candidate contract release.
inputs: [consumer version, prior and candidate contract, fixture results, generated-client result, error catalog, authorization test, migration guidance, rollback plan]
boundaries: [review one supplied consumer-version only, do not infer unprovided runtime outcomes or approve retirement]
evidence: [cite consumer version, contract field, fixture case, error code, tenant or scope check, test result, owner, and rollback reference]
output_schema: {type: consumer-compatibility-review, fields: [verdict, compatible-behaviors, regressions, authority-check, error-contract-check, missing-evidence, required-remediation]}
uncertainty: Mark missing runtime tests, unresolved generated-client behavior, absent authority evidence, and unsupported migration assumptions as unknown.
stop_conditions: [missing consumer version, no prior contract, absent fixture output, missing authorization test, no rollback reference]
escalation: Send a supported-consumer regression, changed authority behavior, or removed required field to API, SDK, security, and release owners.
---

# Sonnet consumer evidence review prompt

Review a single supported consumer against its stated contract. Confirm its accepted and rejected requests, decoded responses, machine-readable errors, tenant and scope behavior, migration path, and rollback evidence. Return the smallest missing proof that blocks a release decision.
