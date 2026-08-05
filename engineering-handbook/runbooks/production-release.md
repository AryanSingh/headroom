---
id: RB-RELEASE-001
kind: runbook
title: Production Release
triggers: [Approved production candidate, scheduled release window, approved emergency change]
severity: [Normal, High when the change has irreversible or customer-critical scope]
roles: [Release Manager, Service Owner, On-call SRE, Security Reviewer, Support Lead]
prerequisites: [Immutable artifact digest, passing required gates, approved change record, rollback plan, telemetry dashboard, communication channel]
decisions: [Proceed, hold, pause rollout, rollback, declare incident]
communication: [Release channel, on-call handoff, support status owner, customer-status owner when impact occurs]
containment_or_rollback: [Stop new cohorts, disable feature flag, shift traffic, redeploy prior immutable artifact, invoke data-specific recovery only from its approved plan]
evidence: [Release decision, artifact digest, gate results, approver identity, deployment record, telemetry snapshots, rollout actions, post-release verification]
recovery: [Restore a known-good service state, verify critical journeys and alert health, communicate outcome]
exit_criteria: [All cohorts meet declared thresholds, evidence is retained, owners accept post-release checks]
follow_up: [Record deviations, open corrective actions, review exceptions before the next release]
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OTEL-SEMCONV-1.43.0]
---

# Production Release

## Purpose and guardrails

Use this runbook to promote one already-qualified, immutable candidate. It is not a substitute for change approval, schema-migration planning, or incident response. Do not rebuild a candidate during promotion, silently widen a cohort, or treat a dashboard that has no current data as a passing check.

## Product Atlas example

Atlas promotes `inventory-api` artifact `sha256:atlas-4.8.0` to 5% of production traffic. The release manager records the approved revision, check set, feature-flag revision, and 15-minute observation window. A payment-authorization error threshold is exceeded at minute seven, so the manager pauses traffic, restores the prior artifact, and opens an incident rather than continuing to 25%.

## Procedure

1. **Establish release identity.** Record change ID, source revision, artifact digest, target environment, configuration revision, migration identifier, owner, and planned cohorts in the release decision.
2. **Reconfirm gates.** Verify required test, security, migration, accessibility, compatibility, and approval evidence applies to this exact digest and target. Hold if a result is absent, expired, or scoped to a different candidate.
3. **Confirm reversibility.** Name the person authorized to stop rollout. Confirm the prior artifact, feature-flag action, traffic action, and migration compatibility boundary are usable from the production console.
4. **Announce the window.** State start time, owner, cohort plan, health thresholds, and escalation channel. Support receives a customer-impact summary and route for reports.
5. **Deploy the first cohort.** Promote only the declared cohort. Capture deployment ID and start time. Do not combine unrelated configuration or data changes after qualification.
6. **Observe against baseline.** Evaluate request success, latency, critical business completion, security signals, queue depth, and client errors for the full observation window. Check that telemetry is current and tagged with the release identity.
7. **Decide at every cohort.** Proceed only when every required threshold passes. Pause for uncertain telemetry; roll back for a stop condition; declare an incident for active customer, integrity, or security impact.
8. **Complete or recover.** Continue through declared cohorts, or execute the approved containment action. Verify the resulting state before announcing completion.
9. **Close evidence.** Attach the decision, timestamps, telemetry links, rollout actions, exceptions, and post-release checks to the release record.

## Decision table

| Signal | Decision | Immediate action | Owner |
| --- | --- | --- | --- |
| All thresholds pass for the full window | Proceed | Promote the next declared cohort | Release Manager |
| Telemetry is missing, stale, or contradictory | Hold | Pause expansion; restore observability before deciding | On-call SRE |
| A reversible health threshold breaches | Roll back | Stop cohorts and restore the prior artifact or flag state | Release Manager |
| Data integrity, security, or broad customer impact is credible | Declare incident | Contain release and invoke incident response | Incident Commander |

## Evidence and communications

Retain stable references instead of raw customer payloads or secrets. The completion message states the release identity, final cohort, decision, known limitations, and owner for follow-up. If rollback occurs, state the customer-visible effect, containment time, and incident reference; do not speculate about cause.

## Exit and follow-up

Exit only after the agreed cohort reaches steady state, critical journeys pass, alerts are functioning, and the release record is complete. Assign an owner and due date for each deviation, waived gate, or manual action. Use the incident-response runbook when response coordination continues beyond the release decision.
