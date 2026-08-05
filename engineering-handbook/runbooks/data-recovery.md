---
id: RB-DATA-002
kind: runbook
title: Data Recovery
triggers: [Confirmed data loss, corruption, unauthorized destructive change, failed restoration, integrity alert requiring restoration assessment]
severity: [Critical, High]
roles: [Incident Commander, Data Recovery Lead, Database Owner, Security Lead when applicable, Privacy/Legal Liaison, Service Owner]
prerequisites: [Restricted incident record, recovery-point inventory, restore environment, integrity checks, approval authority, customer-impact assessment]
decisions: [Contain writes, select recovery point, restore to isolated environment, validate, promote recovered state, notify stakeholders]
communication: [Restricted incident channel, need-to-know leadership, support/status owner, legal/privacy liaison]
containment_or_rollback: [Freeze destructive jobs and unsafe writes, revoke compromised access, isolate affected dataset, preserve recovery sources]
evidence: [Recovery-point identity, backup integrity result, restore logs, reconciliation results, access approvals, timeline, notification decisions]
recovery: [Restore to isolated environment, validate scope and integrity, promote through controlled cutover, reconcile subsequent writes]
exit_criteria: [Recovered data is verified, application behavior is stable, lost-window disposition is documented, residual risk is owned]
follow_up: [Root-cause review, backup/restore test, retention and access review, corrective controls]
standards: [NIST-IR-800-61R3, NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
---

# Data Recovery

## Purpose and safety rule

Recover trustworthy data while preserving evidence and minimizing further loss. Never restore directly over the only production copy without a documented decision, isolated validation, and an agreed treatment for writes made after the selected recovery point.

## Product Atlas example

An Atlas maintenance job incorrectly removes 2,100 tenant preference records. The recovery lead freezes the job and affected writer, identifies a recovery point from 12 minutes earlier, restores it into an isolated environment, and compares tenant counts, checksums, and sampled business rules. The team replays verified post-recovery writes from the audit stream, cuts over during a controlled window, and documents the small unrecoverable interval for customer follow-up.

## Procedure

1. Open a restricted incident and contain destructive activity. Record what is known about dataset, tenant scope, time window, access path, and whether unauthorized activity is suspected.
2. Preserve current evidence and identify viable recovery points with creation time, coverage, encryption/access status, retention, and prior restore-test result.
3. Decide whether the objective is point-in-time restoration, logical repair, selective record recovery, or reconstruction from authoritative sources. Choose the smallest path that preserves integrity.
4. Restore into an isolated environment first. Validate backup integrity before evaluating business correctness.
5. Reconcile counts, keys, tenant boundaries, referential integrity, freshness, and representative business outcomes. Compare with independent audit or event sources where available.
6. Define treatment for post-recovery writes: replay, merge, manually reconcile, or declare lost. Assign accountable owners for every ambiguous class.
7. Obtain cutover approval from the data recovery lead and service owner. Quiesce writes as necessary, preserve the pre-cutover state, and perform the controlled promotion.
8. Verify production reads, writes, authorization, monitoring, and critical customer journeys. Maintain heightened monitoring through the declared window.
9. Communicate confirmed impact and recovery status through approved channels. Legal/privacy owns notification decisions for affected data.

## Recovery decision record

| Question | Evidence required |
| --- | --- |
| Which recovery point is selected? | Identity, timestamp, scope, integrity result |
| What data may be missing or stale? | Defined time window and affected tenant/business scope |
| How are later writes handled? | Replay/merge/reconciliation plan and owner |
| Why is cutover safe? | Isolated validation, peer review, rollback/containment path |
| Who accepts residual risk? | Named authority, rationale, and next review date |

## Exit and follow-up

Exit only after recovered data is verified, production behavior is stable, communication obligations are owned, and every unreconciled record class has a named disposition. Follow up with a restore drill, recovery-point coverage review, access review, and corrective action test using the failure mode that triggered recovery.
