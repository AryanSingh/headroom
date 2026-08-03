---
id: RB-RELEASE-003
kind: runbook
title: Emergency Hotfix
triggers: [Active production defect, security exposure, urgent customer-impacting regression requiring a change before the normal release window]
severity: [High, Critical]
roles: [Incident Commander, Hotfix Owner, Release Manager, On-call SRE, Security Lead when relevant]
prerequisites: [Problem statement, bounded change proposal, accountable authority, rollback path, target environment, evidence location]
decisions: [Use mitigation only, approve hotfix, hold for evidence, roll back, continue incident response]
communication: [Incident channel, release channel, support and status owners, executive delegate for critical impact]
containment_or_rollback: [Use reversible mitigation first; deploy one minimal immutable hotfix; immediately roll back if stop criteria breach]
evidence: [Incident ID, source revision, diff review, focused test results, artifact digest, deployment record, decision authority, post-deploy observations]
recovery: [Verify the specific failure is contained, monitor for regressions, restore normal release controls]
exit_criteria: [Impact is controlled, hotfix evidence is complete, deferred review is scheduled]
follow_up: [Perform retrospective qualification, merge lessons into normal controls, expire temporary exceptions]
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
---

# Emergency Hotfix

## Purpose and guardrails

Use this procedure for a minimal, time-sensitive production correction. Urgency reduces scope; it does not remove accountability. A hotfix may not bundle feature work, dependency upgrades, schema redesign, or unrelated cleanup. If a reversible mitigation controls impact, prefer it while the team obtains stronger evidence.

## Product Atlas example

Atlas discovers that a cache-key regression can expose a prior tenant's recommendation title to the next request. The incident commander disables the cache feature flag, which stops exposure. A hotfix adds tenant identity to the key and includes a focused isolation test. Security reviews the diff; the release manager promotes the signed artifact to a 1% cohort with a five-minute observation window.

## Procedure

1. Open or link an incident record. State the customer, integrity, security, and availability impact; identify the decision authority.
2. Apply the quickest safe mitigation. Verify it with production telemetry or a controlled request and record the result.
3. Write a one-sentence hotfix objective and explicit exclusions. If the diff exceeds that objective, split it or return to normal release planning.
4. Review the change with the service owner and relevant security or data owner. Check authorization, tenant isolation, logging, dependency, configuration, and rollback consequences.
5. Run focused tests that reproduce the fault and prove the correction, plus required build and security gates that can be completed in time. Record unavailable evidence as a time-bounded exception, not as a pass.
6. Build one immutable artifact. Verify its digest, provenance, target configuration, and rollback artifact.
7. Deploy in the smallest viable cohort with a named observer and stop criteria. Do not bypass monitoring or alter the test target after approval.
8. Verify the original fault is contained and watch adjacent critical journeys. Roll back immediately on a breach or uncertainty that expands risk.
9. Restore normal release controls, communicate the decision, and schedule retrospective qualification within the next business day.

## Required decision record

| Field | Required content |
| --- | --- |
| Authority | Name and role approving the exceptional path |
| Scope | Fault addressed, excluded changes, affected services/tenants |
| Evidence gap | Missing gate, reason, compensating control, expiry |
| Stop criteria | Threshold and person authorized to halt/rollback |
| Follow-up | Owner and due date for full review and exception closure |

## Exit and follow-up

Exit only after the mitigation or hotfix is stable and the incident owner accepts handoff. A hotfix without retrospective evidence remains an open governance item; it must not become the template for routine releases.
