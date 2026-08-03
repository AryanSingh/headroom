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

## Concepts and engineering principles

Prefer expand, migrate, verify, contract. Readers and writers must tolerate the transition state. Use bounded, restartable work with an explicit checkpoint and idempotency boundary. Treat a backup as an unproven assumption until restore and reconciliation have been exercised.

## Roles and accountability

The migration owner designs and records the sequence. The database owner approves query and lock risk. The service owner accepts compatibility and customer outcomes. SRE owns change-window signals and recovery coordination. The data protection owner confirms classification, retention, and tenant boundaries.

## Prerequisites and required inputs

Obtain the schema and dependency map, row-volume estimate, sensitive-data classification, version compatibility matrix, lock/query-plan review, approved change window, backup-restore evidence, retry checkpoint design, rollback decision tree, reconciliation queries, and named stop authority.

## Standard operating procedure

1. Define the business outcome, affected records, tenant scope, data classification, compatibility window, and owner decision.
2. Expand first with additive, backward-compatible schema or storage changes; deploy readers before relying on new fields.
3. Test the query plan and lock behavior against representative volume; bound batch size, rate, transaction scope, and stop thresholds.
4. Backfill with immutable input selection, a durable checkpoint, idempotent writes, tenant-aware predicates, and observable progress.
5. Pause or abort when declared error, latency, lock, replication, integrity, or tenant-isolation thresholds breach; preserve evidence before retrying.
6. Reconcile counts, checksums, sample business outcomes, and excluded records against the approved source of truth.
7. Contract only after all supported readers/writers have moved and reconciliation, retention, rollback feasibility, and owner acceptance are recorded.

## Worked example

[Product Atlas resumable name migration](../examples/migrations/README.md) expands an account field, interrupts an Atlas A backfill, resumes exactly once, prevents a write to Atlas B, and blocks contract completion until the result is reconciled.

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

## Audit prompts

Use [Opus](../prompts/opus/ch16-migration-risk-synthesis.md), [Sonnet](../prompts/sonnet/ch16-reconciliation-evidence-review.md), and [Haiku](../prompts/haiku/ch16-migration-inventory.md) for migration-chain risk analysis, one execution record review, and inventory normalization.

## Workflow checklist

Run [CL-MIGRATION-01](../checklists/database-migrations.md) before a schema, persistent-data, index, retention, or event-format migration reaches a shared or production environment.

## Evidence requirements and retention guidance

Retain the approval, source and target schema versions, query-plan and lock review, backup-restore evidence, batch and checkpoint records, telemetry, reconciliation queries/results, exceptions, rollback decision, and owner acceptance. Store aggregate evidence or safe references rather than customer payloads, credentials, or raw sensitive records.

## Example findings with severity and remediation

**Critical — MIG-ATLAS-01.** A tenant predicate was absent from a retry worker, allowing its checkpoint to process another tenant’s records. Stop the change, contain access, reconcile the affected tenants, restore or correct data under incident control, add tenant-bound checkpoints, and repeat the isolated fixture plus an independent review.

## KPIs and domain scorecard

The [migration KPI catalog](../scorecards/migration-kpis.md) measures reconciled completion and recovery rehearsal coverage. A completed process is not a completed migration unless the designated business records reconcile.

## Common failure patterns and diagnostic guidance

- A destructive rename is released before all readers understand the replacement field.
- A single transaction or unbounded batch causes lock, replication, or latency collapse.
- A retry uses positional progress without an immutable ordering or tenant boundary.
- “Rollback” restores schema while leaving transformed, deleted, or externally consumed data unreconciled.

## Exit criteria

Exit when compatible versions were proven, work was bounded and observable, all affected data reconciles by tenant, stop and recovery paths were exercised, no unsupported reader or writer remains, and the accountable owners accept the evidence.

## Related runbooks, controls, examples, and templates

Use the migration-plan, verification-plan, release-decision, incident-review, and evidence-register templates. Use the release engineering chapter for promotion gates and the incident response runbook when integrity, availability, or confidentiality is at risk.
