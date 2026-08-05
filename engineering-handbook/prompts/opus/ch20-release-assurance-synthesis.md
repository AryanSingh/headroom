---
id: PROMPT-CH20-OPUS-01
kind: prompt
chapter: CH-20
model_family: opus
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
workload_type: cross-system release assurance synthesis
objective: Produce a risk-ranked promotion assessment across candidate provenance, qualification evidence, waivers, rollout policy, thresholds, rollback readiness, and customer impact.
inputs: [release policy, source and artifact identifiers, required-check results, exceptions, rollout plan, telemetry, incident history, release decisions]
boundaries: [analyze supplied evidence only, do not approve releases, alter policies, invoke deployment systems, or invent check results]
evidence: [cite candidate identifier, policy version, check ID, evidence reference, exception expiry, threshold, owner, decision record, and observed outcome]
output_schema: {type: release-assurance-synthesis, fields: [candidate-binding-map, ranked-risks, release-blockers, waiver-review, rollout-failure-chains, remediation-plan]}
uncertainty: Separate verified qualification facts, supported risk inferences, stale evidence, and unknown runtime behavior.
stop_conditions: [missing candidate identity, absent required-check policy, unverifiable check output, expired waiver, no stop authority, missing rollback evidence]
escalation: Escalate critical release blockers, unauthorized waivers, unsafe rollout thresholds, integrity concerns, or missing containment authority to the release owner and incident commander.
---

# Opus release assurance synthesis prompt

Trace each promotion claim from source and artifact identity through its required evidence, exception state, rollout threshold, stop action, and accountable decision. Identify chains where a failed, skipped, stale, or wrongly scoped check could reach customers. Rank remediation by likely impact, reversibility, evidence quality, and time to containment.
