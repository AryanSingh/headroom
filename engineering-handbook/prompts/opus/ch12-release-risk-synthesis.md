---
id: PROMPT-CH12-OPUS-01
kind: prompt
chapter: CH-12
model_family: opus
workload_type: cross-system release-chain risk synthesis
objective: Produce a prioritized release risk assessment spanning source provenance, dependencies, artifacts, configuration, deployment, observability, rollback, and customer outcome integrity.
inputs: [change approval, source revision, dependency evidence, artifact record, test results, deployment plan, telemetry, rollback rehearsal]
boundaries: [analyze supplied evidence only, do not deploy or roll back systems, do not infer a matching artifact from a tag name]
evidence: [cite change ID, source revision, artifact digest, test run, configuration revision, deployment observation, rollback result, and owner for each conclusion]
output_schema: {type: release-risk-synthesis, fields: [release-chain, evidence-gaps, failure-chains, ranked-risks, promotion-recommendation]}
uncertainty: Separate observed evidence, supported inference, and unknown deployment or rollback behavior.
stop_conditions: [missing artifact identity, absent test evidence, unavailable deployment plan, no rollback criteria]
escalation: Escalate provenance failure, unsafe rollback, data-loss risk, or breached stop criterion to the release and SRE owners.
---

# Opus release-chain risk synthesis prompt

Trace the candidate from approved change to observed deployment and rollback. Rank failure chains by customer impact, correctness, reversibility, and evidence strength. Treat a rebuilt artifact, unlinked configuration, or untested affected component as a release-blocking evidence gap.
