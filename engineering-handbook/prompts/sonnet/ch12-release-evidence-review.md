---
id: PROMPT-CH12-SONNET-01
kind: prompt
chapter: CH-12
model_family: sonnet
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
workload_type: focused release candidate evidence review
objective: Determine whether one release candidate has the attributable source, artifact, gate, deployment, and rollback evidence required for a promotion decision.
inputs: [release record, source revision, artifact digest, dependency record, test results, configuration revision, rollout observations, rollback rehearsal]
boundaries: [review one candidate only, use supplied evidence only, do not approve exceptions or reconstruct missing artifacts]
evidence: [cite release ID, source revision, digest, test run ID, target, telemetry query, rollback result, and accountable owner]
output_schema: {type: release-evidence-review, fields: [verdict, traceability-chain, gate-status, gaps, required-follow-up]}
uncertainty: Mark an unlinked configuration, missing digest, incomplete component inventory, or absent outcome query as unresolved.
stop_conditions: [missing release record, absent artifact digest, unavailable gate result, no declared rollback criterion]
escalation: Send a mismatched digest, failed stop criterion, or unsupported rollback claim to the release owner.
---

# Sonnet release candidate evidence review prompt

Review one candidate as a bounded chain of evidence. Confirm that the tested digest is the deployable digest, required gates apply to the declared change, rollout evidence uses the stated threshold, and rollback covers every affected component. Identify the smallest record or rehearsal needed for each gap.
