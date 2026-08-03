---
id: CL-MIGRATION-01
kind: checklist
title: Database migration readiness and recovery checklist
chapter: CH-16
controls:
  - id: ENG-MIGRATION-001
    requirement: Persistent-state migrations must use an approved compatible sequence with bounded, restartable, tenant-scoped work and an explicit decision boundary before destructive contract changes.
    applicability: required for schemas, data backfills, indexes, streams, search documents, retention jobs, materialized views, and customer-impacting persistent-state changes
    procedure: Review expand-contract ordering, reader/writer compatibility, query plan, batch limits, checkpoint semantics, idempotency key, tenant predicate, stop thresholds, and contract prerequisite.
    expected_result: A failed worker can resume without duplicate or cross-tenant writes, compatible clients remain usable, and destructive changes remain blocked until reconciliation passes.
    evidence: approved plan, compatibility matrix, query plan, fixture result, checkpoint record, tenant-scoped logs, and contract decision
    automation: isolated interruption-and-resume fixture plus query-plan and compatibility gate
    owner: Migration owner
    frequency: every persistent-state migration and each material change to its data, batch, or retry logic
    failure_action: stop the migration, preserve checkpoint and telemetry evidence, contain affected access, correct the sequence or predicate, reconcile records, and rerun the fixture
    standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
  - id: ENG-MIGRATION-002
    requirement: A migration must have tested recovery and reconciliation evidence that proves affected business outcomes are complete, correct, and recoverable within approved limits.
    applicability: required for migrations affecting customer data, authorization data, balances, entitlements, retention, billing, or production availability
    procedure: Restore a scoped backup or equivalent recovery point in isolation, execute rollback or forward repair, reconcile counts and business outcomes by tenant, and obtain accountable acceptance.
    expected_result: Recovery is executable, discrepancies are identified and resolved, and no owner treats process completion as proof of data correctness.
    evidence: backup-restore result, recovery run, reconciliation queries/results, exception register, owner acceptance, and release decision
    automation: backup-restore rehearsal and tenant-scoped reconciliation gate
    owner: Database owner
    frequency: before high-risk migration, quarterly for recovery paths, and after a backup, restore, or migration-platform change
    failure_action: block the release, use the incident path for integrity or confidentiality impact, repair recovery evidence, and repeat reconciliation before approval
    standards: [NIST-SSDF-1.1, NIST-IR-800-61R3]
---

# Database migration readiness and recovery checklist

- [ ] Name the migration, data owner, tenant scope, sensitivity, business outcome, change window, stop authority, and decision record.
- [ ] Prove expand-contract compatibility across deployed readers, writers, workers, indexes, and external consumers.
- [ ] Bound transaction, batch, rate, lock, replication, and error-budget risk with telemetry and stop thresholds.
- [ ] Use a durable checkpoint, idempotent write boundary, immutable work ordering, and tenant predicate; simulate interruption and repeat resume.
- [ ] Test backup restore or equivalent recovery, reconcile business outcomes by tenant, retain evidence, and contract only after owner acceptance.
