---
id: CH-16
kind: chapter
title: Database Migration Engineering Audit
purpose: Build and assess data and schema changes that are compatible, reversible where possible, tenant-safe, observable, and supported by reconciled recovery evidence.
audience: [Database engineers, backend engineers, SREs, security engineers, release managers, data owners]
scope: Schema design, expand-contract sequencing, data backfills, transactions, locks, performance, tenant isolation, backup and restore, reconciliation, rollback, and release evidence.
applicability: Relational and non-relational stores, event streams, search indexes, caches, materialized views, data-retention changes, and all customer-impacting persistent-state changes.
owners: [Migration owner, database owner, service owner, SRE owner, data protection owner]
inputs: [approved migration plan, data classification, dependency map, compatibility assessment, backup evidence, query plans, rollback and reconciliation plans]
outputs: [migration decision, execution record, reconciliation evidence, rollback result, retained migration plan]
dependencies: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, NIST-IR-800-61R3]
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0, NIST-IR-800-61R3]
---

# Database Migration Engineering Audit

## Purpose, audience, scope, and applicability

A migration is a customer-data change with a deployment surface, not a script that happened to finish. Audit whether its compatibility, performance, recovery, isolation, and business reconciliation evidence can support a release decision.

The audit verdict answers three questions for the release owner: can the migration execute inside the approved risk bounds; can it be stopped, resumed, or reversed within the approved window; and can the affected business outcomes be proven correct and complete after it finishes? The decision chain is the migration owner, database owner, service owner, SRE owner, and data protection owner. It applies to every persistent-state change with a deployment surface — schema changes, data backfills, index rebuilds, retention jobs, event-format changes, search documents, materialized views, and cache seeds — in relational and non-relational stores, event streams, and search indexes, whether executed by hand, by scheduled job, or by release automation.

## Concepts and engineering principles

Prefer expand, migrate, verify, contract. Readers and writers must tolerate the transition state. Use bounded, restartable work with an explicit checkpoint and idempotency boundary. Treat a backup as an unproven assumption until restore and reconciliation have been exercised.

The canonical sequence is expand, migrate, verify, contract. Expansion is additive and backward compatible: new columns, tables, indexes, or event fields coexist with the old shape so deployed readers and writers keep working during the transition. Migration moves data or rewrites state inside the expanded shape. Verification proves the moved state is complete and correct. Contraction removes the old shape only after every supported reader and writer has moved and reconciliation evidence exists. A migration that skips a phase has moved risk into production rather than removed it.

Two principles carry the rest of the procedure: idempotency and isolation. Every write carries an idempotency key so a resumed worker cannot duplicate work, and every predicate carries a tenant or shard boundary so a worker cannot process another tenant's records. Without both, a retry is a corruption mechanism, not a resilience feature.

| Principle | Audit question |
|---|---|
| Expand-contract ordering | Is the old shape still supported by every deployed reader and writer at contract time? |
| Bounded work | Are batch size, transaction scope, rate, and concurrency explicitly bounded with telemetry? |
| Idempotency | Can a resumed batch be proven to have written each record exactly once? |
| Tenant isolation | Does every retry, backfill, and reconciliation query carry the tenant predicate? |
| Proof of recovery | Has a restore or forward-repair path been executed and reconciled, not merely documented? |
| Business reconciliation | Do migrated records agree with the approved source of truth on counts, hashes, and outcomes? |

## Roles and accountability

The migration owner designs and records the sequence. The database owner approves query and lock risk. The service owner accepts compatibility and customer outcomes. SRE owns change-window signals and recovery coordination. The data protection owner confirms classification, retention, and tenant boundaries.

| Role | Primary decisions | Evidence accepted | Escalation |
|---|---|---|---|
| Migration owner | Sequence, batch bounds, checkpoint design, stop thresholds | Plan, fixture runs, checkpoint records | Service owner |
| Database owner | Query and lock risk, backup-restore viability | Query plans, lock telemetry, restore result | SRE owner |
| Service owner | Compatibility and customer outcomes | Compatibility matrix, reconciliation result | Release owner |
| SRE owner | Change-window signals, recovery coordination | Window telemetry, rollback run | Incident commander |
| Data protection owner | Classification, retention, tenant boundaries | Classification record, retention decisions | Security owner |

A named stop authority — one person, not a committee — has standing to halt the migration at any point without re-litigating the decision. The stop authority's name, contact path, and escalation route are prerequisites recorded in the plan, not discoveries made during an incident. Every stop or resume decision is written to the execution record with a timestamp and the evidence that triggered it.

## Prerequisites and required inputs

Obtain the schema and dependency map, row-volume estimate, sensitive-data classification, version compatibility matrix, lock/query-plan review, approved change window, backup-restore evidence, retry checkpoint design, rollback decision tree, reconciliation queries, and named stop authority.

| Input | Why it is needed | Owner | Freshness |
|---|---|---|---|
| Schema and dependency map | Determines expand-contract ordering and the reader/writer surface | Database owner | Current at execution |
| Row-volume estimate | Sizes batches, rate limits, and the change window | Data owner | Re-validated inside the window |
| Data classification | Sets retention, redaction, and approval rules | Data protection owner | Current |
| Version compatibility matrix | Proves every deployed consumer tolerates the transition | Service owner | Every supported version listed |
| Lock and query-plan review | Approves lock and latency risk | Database owner | Before execution |
| Backup-restore evidence | Proves recovery is executable | Database owner | Exercised within the recovery interval |
| Retry checkpoint design | Proves exactly-once, tenant-safe resume | Migration owner | Fixture-verified |
| Rollback decision tree | Names which schema, data, and consumers each path restores | Migration owner | Rehearsed |
| Reconciliation queries | Define the source of truth and comparison method | Data owner | Pre-approved |
| Named stop authority | Provides a decision point for abort | Service owner | Recorded in the plan |

## Standard operating procedure

1. Define the business outcome, affected records, tenant scope, data classification, compatibility window, and owner decision.
2. Expand first with additive, backward-compatible schema or storage changes; deploy readers before relying on new fields.
3. Test the query plan and lock behavior against representative volume; bound batch size, rate, transaction scope, and stop thresholds.
4. Backfill with immutable input selection, a durable checkpoint, idempotent writes, tenant-aware predicates, and observable progress.
5. Pause or abort when declared error, latency, lock, replication, integrity, or tenant-isolation thresholds breach; preserve evidence before retrying.
6. Reconcile counts, checksums, sample business outcomes, and excluded records against the approved source of truth.
7. Contract only after all supported readers/writers have moved and reconciliation, retention, rollback feasibility, and owner acceptance are recorded.

Each step carries an owner, a threshold, and a timeline declared before execution. Step 1 (owner: migration owner; timeline: before the window opens) produces a plan that is immutable after execution starts except by stop-authority approval. Step 2 (owner: migration owner with database-owner review; threshold: every deployed reader and writer version in the compatibility matrix tolerates the expanded shape) is complete only when the matrix passes, not when the DDL runs. Step 3 (owner: database owner; threshold: query plan stays within approved cost, and lock wait, replication lag, and p99 latency stay inside declared bounds at representative volume) sizes batches so the worst case fits the window. Step 4 (owner: migration owner; threshold: the checkpoint commits every N records with the last processed key and tenant, and resume skips already-processed keys through the idempotency boundary) makes progress observable. Step 5 (owner: stop authority; timeline: act within minutes of a breach) preserves logs, telemetry, and checkpoint state before any retry so the failure can be reviewed without guessing. Step 6 (owner: data owner with migration owner; threshold: zero unexplained discrepancies per tenant) compares per-tenant counts, hash aggregates, and sampled outcomes against the pre-migration baseline. Step 7 (owner: service owner) treats contraction as a separate change with its own gate, migration evidence, retention approval, and a recorded rollback decision.

| Condition observed | Decision |
|---|---|
| Lock wait or replication lag approaching threshold | Reduce batch size or concurrency; extend window with approval |
| p99 latency breach on a dependent path | Pause writes on that path; shrink batch |
| Checkpoint lost or not durable | Abort; restart from the last verified checkpoint |
| Tenant predicate missing from a retry | Abort immediately; isolate; inspect scope |
| Reconciliation discrepancy | Stop contract; investigate before any retry |
| Window about to expire with work incomplete | Stop-authority decision: extend, resume, or roll back |

## Worked example

[Product Atlas resumable name migration](../examples/migrations/README.md) expands an account field, interrupts an Atlas A backfill, resumes exactly once, prevents a write to Atlas B, and blocks contract completion until the result is reconciled.

Phase one expands the schema with `display_name` and a `migration_version` marker while `name` stays authoritative for readers. Phase two backfills `display_name` in bounded, checkpointed batches; each batch carries `tenant_id` and an idempotency key. The fixture interrupts the Atlas A backfill mid-batch and resumes it — the resumed run must skip already-processed rows instead of rewriting them. Phase three blocks a concurrent write to Atlas B until its own backfill reaches the same checkpoint, proving a tenant can never observe half-migrated state. Phase four computes per-tenant counts and hash aggregates against the pre-migration baseline and blocks contraction until every tenant reconciles.

| Phase | Action | Owner | Passing evidence |
|---|---|---|---|
| Expand | Add `display_name`, `migration_version` | Migration owner | Compatibility matrix passes |
| Migrate | Backfill in bounded, checkpointed batches | Migration owner | Fixture: interrupted at Atlas A, resumed once |
| Isolate | Block writes to Atlas B until aligned | Service owner | Fixture: cross-tenant write rejected |
| Verify | Reconcile counts, hashes, outcomes by tenant | Data owner | Reconciliation report with zero discrepancies |
| Contract | Remove the old field only after sign-off | Service owner | Owner acceptance; rollback decision recorded |

## Automation examples

```bash
python3 migration_fixture.py
# MIGRATION_FIXTURE_PASS expand-compatible resumed-once tenant-isolated contract-safe
```

```sql
SELECT tenant_id, COUNT(*) AS incomplete_rows
FROM accounts
WHERE migration_version = 'atlas-display-name-v2'
  AND display_name IS NULL
GROUP BY tenant_id;
```

```sql
-- Idempotency check: rows written more than once within a tenant
SELECT tenant_id, idempotency_key, COUNT(*) AS writes
FROM migration_write_log
WHERE migration_version = 'atlas-display-name-v2'
GROUP BY tenant_id, idempotency_key
HAVING COUNT(*) > 1;
```

```bash
# Bounded batch loop that preserves evidence on threshold breach
while [ "$(reconciliation_status)" = "pending" ]; do
  python3 backfill_batch.py --checkpoint "$(latest_checkpoint)" || break
  check_thresholds || abort --preserve-evidence
done
```

> **Application note — Cutctx.** In the Cutctx token-compression proxy, changes to compression state (route dictionaries, token maps, savings ledgers) follow the same sequence: additive dictionary columns first, checkpointed backfills keyed by tenant or workspace, and per-tenant reconciliation of token-savings totals before any destructive dictionary change. The interruption-and-resume fixture applies directly because compression jobs are batch-shaped and retried.

## Audit prompts

Use [Opus](../prompts/opus/ch16-migration-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch16-reconciliation-evidence-review.md), and [Haiku](../prompts/haiku/ch16-migration-inventory.md) for migration-chain risk analysis, one execution record review, and inventory normalization.

## Workflow checklist

Run [CL-MIGRATION-01](../checklists/database-migrations.md) before a schema, persistent-data, index, retention, or event-format migration reaches a shared or production environment. The checklist's five controls — `ENG-MIGRATION-001` (compatible, bounded, tenant-scoped execution), `ENG-MIGRATION-002` (tested recovery and reconciliation), `ENG-MIGRATION-003` (immutable baseline snapshot), `ENG-MIGRATION-004` (resumability), and `ENG-MIGRATION-005` (rollback decision tree and cutover) — must each be answered with evidence, not intent, before the release decision is signed.

## Evidence requirements and retention guidance

Retain the approval, source and target schema versions, query-plan and lock review, backup-restore evidence, batch and checkpoint records, telemetry, reconciliation queries/results, exceptions, rollback decision, and owner acceptance. Store aggregate evidence or safe references rather than customer payloads, credentials, or raw sensitive records.

| Evidence | Minimum retention | Access | Notes |
|---|---|---|---|
| Approved plan and decision | Life of the data or release record | Migration, data protection | Immutable after the window opens |
| Compatibility matrix, query plans | One year or two release cycles | Database owner | Reused at contract |
| Backup-restore and recovery runs | One year | SRE, database owner | Include restore timestamps |
| Checkpoint and batch records | One year | Migration owner | Proves exactly-once resume |
| Reconciliation queries and results | One year | Data owner | Per-tenant result references |
| Exceptions and rollback decisions | Life of the release record | Release owner | Include stop-authority approval |

## Example findings with severity and remediation

**Critical — MIG-ATLAS-01.** A tenant predicate was absent from a retry worker, allowing its checkpoint to process another tenant's records. Stop the change, contain access, reconcile the affected tenants, restore or correct data under incident control, add tenant-bound checkpoints, and repeat the isolated fixture plus an independent review.

**High — MIG-ATLAS-02.** The recovery plan referenced a backup that had never been restored; the first restore attempt failed because the backup predated the schema change. Block the migration, restore the backup in isolation under incident control, rebuild the recovery plan against the current schema, and re-run the restore rehearsal before any execution resumes.

**High — MIG-ATLAS-03.** Reconciliation compared only row counts while the backfill had silently transformed a date-format field, leaving values unreconciled. Stop the contract phase, add hash aggregates and sampled business-outcome checks per tenant, correct the affected records, and require field-level comparison in the reconciliation gate.

## KPIs and domain scorecard

The [migration KPI catalog](../scorecards/migration-kpis.md) measures reconciled completion and recovery rehearsal coverage. A completed process is not a completed migration unless the designated business records reconcile. Review `KPI-MIGRATION-001` (reconciled completion), `KPI-MIGRATION-002` (recovery readiness), and `KPI-MIGRATION-003` (change-window and stop-threshold adherence) together; each covers a different failure mode and no single number authorizes a release.

## Common failure patterns and diagnostic guidance

- A destructive rename is released before all readers understand the replacement field.
- A single transaction or unbounded batch causes lock, replication, or latency collapse.
- A retry uses positional progress without an immutable ordering or tenant boundary.
- "Rollback" restores schema while leaving transformed, deleted, or externally consumed data unreconciled.

| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| Migration finishes fast; business data wrong | Count-only reconciliation | Compare field-level hashes and sampled outcomes | Reconcile by tenant with business queries |
| Resume duplicates rows | Positional progress without an idempotency key | Inspect the write log for duplicate keys | Add an idempotency boundary; rebuild the checkpoint |
| Lock waits spike at fixed times | Batch size ignores concurrent jobs | Correlate lock telemetry with job schedules | Bound concurrency; stagger batches |
| Replication lag grows during backfill | Rate exceeds replica apply capacity | Watch lag per replica | Throttle rate; shrink batch |
| Rollback restores schema but not data | Rollback plan covers only DDL | Compare schema and data after rollback | Restore from backup or forward-repair |
| One tenant's records appear in another batch | Missing tenant predicate in a retry | Query worker logs by tenant | Abort; isolate; add predicate; re-run fixture |

## Exit criteria

Exit when compatible versions were proven, work was bounded and observable, all affected data reconciles by tenant, stop and recovery paths were exercised, no unsupported reader or writer remains, and the accountable owners accept the evidence.

| Criterion | Evidence | Owner |
|---|---|---|
| Compatible versions proven | Compatibility matrix; reader/writer sign-off | Service owner |
| Work bounded and observable | Batch, rate, checkpoint, telemetry records | Migration owner |
| All affected data reconciles by tenant | Per-tenant reconciliation report | Data owner |
| Stop and recovery paths exercised | Abort fixture, restore rehearsal, rollback run | SRE owner |
| No unsupported reader or writer remains | Deployment inventory cross-check | Service owner |
| Owners accept the evidence | Signed release decision | Release owner |

## Related runbooks, controls, examples, and templates

Use the migration-plan, verification-plan, release-decision, incident-review, and evidence-register templates. Use the release engineering chapter for promotion gates and the incident response runbook when integrity, availability, or confidentiality is at risk.
