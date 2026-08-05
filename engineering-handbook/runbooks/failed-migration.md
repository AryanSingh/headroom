---
id: RB-DATA-001
kind: runbook
title: Failed Database Migration
triggers: [Migration gate failure, reconciliation mismatch, timeout, lock contention, partial backfill, unsafe contract step]
severity: [High, Critical when integrity or broad availability is at risk]
roles: [Migration Owner, Database Owner, On-call SRE, Service Owner, Incident Commander when activated]
prerequisites: [Migration identifier, approved expand/backfill/contract plan, checkpoint evidence, backup/restore reference, reconciliation query, rollback boundary]
decisions: [Pause, resume, roll forward, restore, isolate writes, declare incident]
communication: [Migration channel, release channel, incident channel when activated, support owner when customer impact occurs]
containment_or_rollback: [Stop contract step, pause writers or job, keep compatible schema, isolate affected tenant/workload, restore only through approved recovery]
evidence: [Migration logs, checkpoint, row counts, checksums, lock/latency metrics, affected scope, decision log]
recovery: [Resume idempotently or restore verified data; reconcile source and destination; validate application compatibility]
exit_criteria: [Data and application behavior reconcile, unsafe writes are contained, recovery decision is documented]
follow_up: [Correct plan, add test or guardrail, rehearse recovery, close exception]
standards: [NIST-SSDF-1.1, NIST-IR-800-61R3, OWASP-ASVS-5.0.0]
---

# Failed Database Migration

## Purpose and boundary

Use this runbook for an interrupted or unsafe data/schema change. Preserve compatibility first. Do not run destructive repair queries, drop old columns, or restore a broad backup merely to make a dashboard green. The data-recovery runbook governs verified restoration after corruption or loss.

## Product Atlas example

Atlas's tenant-preference backfill times out after 62% completion. The migration owner pauses workers, records the checkpoint and per-tenant counts, and confirms the expanded schema remains readable by both application versions. The team fixes the batch limit, resumes only unfinished tenant partitions with idempotent writes, and compares counts and checksums before scheduling the separate contract step.

## Procedure

1. Stop advancement and record migration ID, phase, start time, source revision, target schema, affected tenant scope, and exact failure evidence.
2. Determine whether writes, reads, or asynchronous consumers can compound the problem. Pause the smallest affected writer or queue; keep the compatible expand state when possible.
3. Preserve checkpoints, logs, row counts, checksums, and lock metrics. Snapshot references must be access-controlled and must not expose sensitive rows in broad channels.
4. Classify the state: safe to resume idempotently, requires repair, requires rollback to compatible state, or requires data recovery. A timeout alone is not a reason to restore.
5. For a resume, prove the job selects unfinished work deterministically and is duplicate-safe. Run a bounded tenant or partition cohort, then reconcile before expansion.
6. For repair, peer review the query and test it against a representative copy or approved fixture. Record before/after counts and reversible boundaries.
7. Do not execute the contract/delete phase until application compatibility, replication/consumer state, and reconciliation all pass.
8. Communicate current customer effect, containment, data-confidence level, next decision time, and owner.

## Reconciliation minimums

- Compare expected and actual rows by tenant or equivalent isolation boundary.
- Check duplicate, null, orphan, and referential-integrity conditions relevant to the migration.
- Validate application read/write paths against the expanded state.
- Retain query version, execution time, scope, output location, and reviewer.

## Exit and follow-up

Exit when the data state and customer-facing behavior reconcile, affected writers are safely restored, and any remaining migration phase has a new approved decision. Add a regression fixture for the failure mechanism and update the migration plan with the observed checkpoint and recovery guardrail.
