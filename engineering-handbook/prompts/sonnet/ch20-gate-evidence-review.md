---
id: PROMPT-CH20-SONNET-01
kind: prompt
chapter: CH-20
model_family: sonnet
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
workload_type: single-candidate release-gate evidence review
objective: Determine whether one candidate's required checks, evidence references, waiver state, and promotion decision satisfy the declared release policy.
inputs: [candidate manifest, policy version, required-check results, evidence references, waiver records, release decision]
boundaries: [review one supplied candidate only, do not execute checks, approve a release, modify records, or infer missing evidence]
evidence: [quote check ID, candidate binding, result, evidence location, waiver owner and expiry, policy requirement, and decision discrepancy]
output_schema: {type: gate-evidence-review, fields: [decision, missing-evidence, failed-checks, waiver-validity, policy-violations, required-actions]}
uncertainty: Mark inaccessible references, ambiguous policy clauses, and evidence that is present but not candidate-bound as unresolved.
stop_conditions: [missing policy version, missing candidate identity, absent required-check list, unavailable evidence reference, or unowned waiver]
escalation: Escalate any failed required check, expired or unauthorized exception, candidate mismatch, or unsupported approval to the release engineering owner.
---

# Sonnet release-gate evidence review prompt

Review the supplied candidate record line by line. Confirm that every declared required check has a candidate-bound result and resolvable evidence, and that any exception is authorized, scoped, and unexpired. Return a decision only from the supplied policy; do not fill gaps with assumptions.
