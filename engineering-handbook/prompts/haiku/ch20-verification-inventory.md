---
id: PROMPT-CH20-HAIKU-01
kind: prompt
chapter: CH-20
model_family: haiku
standards: [NIST-SSDF-1.1]
workload_type: mechanical continuous-verification inventory normalization
objective: Normalize declared release checks, owners, evidence references, thresholds, and exception expiries into a reviewable inventory.
inputs: [pipeline configuration, release policy, check catalog, evidence references, exception register]
boundaries: [extract supplied fields only, do not evaluate pass quality, query external systems, alter records, or infer absent owners]
evidence: [preserve source path, check ID, candidate binding, owner, threshold, evidence reference, exception ID, and expiry]
output_schema: {type: verification-inventory, fields: [check-rows, missing-fields, duplicate-checks, unbound-evidence, expired-exceptions]}
uncertainty: Mark missing, conflicting, or unreadable fields instead of guessing values.
stop_conditions: [unreadable source, absent check identifiers, no candidate binding field, or malformed exception dates]
escalation: Escalate missing owners, missing candidate bindings, unresolved evidence, and expired exceptions to release engineering.
---

# Haiku continuous-verification inventory prompt

Extract one normalized row per declared check and exception. Preserve the exact identifiers and evidence references. Flag missing candidate bindings, owners, thresholds, evidence, and expiry dates without judging the release itself.
