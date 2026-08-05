---
id: TMPL-MIGRATION-PLAN-001
kind: template
title: Database Migration Plan
field_instructions:
  change_scope: State schema or data change, impacted services, and compatibility period.
  verification: Define preflight, reconciliation, and rollback checks.
  rollback: State trigger, owner, and reversible action.
completed_example:
  change_scope: Atlas adds tenant_region to inventory_records for 4.8.0 with dual-read compatibility.
  verification: Compare active-row count and checksum before and after backfill.
  rollback: Data Steward Noor restores the prior index and disables dual-write on checksum mismatch.
---

# Database Migration Plan

## Field instructions

| Field | How to complete it |
| --- | --- |
| Change and compatibility | Describe schema/data change, callers, and coexistence strategy. |
| Preconditions | List backup, capacity, access, and rehearsal evidence. |
| Execution | Give ordered, observable migration steps. |
| Verification | Define counts, checksums, application checks, and acceptance thresholds. |
| Rollback | Name triggers, owner, time limit, and reversal action. |

## Completed example: Product Atlas

**Change:** Atlas 4.8.0 adds nullable `tenant_region` to `inventory_records`, backfills from tenant configuration, then enables dual-read for seven days.  
**Preconditions:** Noor Patel verified backup restore, indexed the source field, and completed a staging rehearsal against 12 million rows.  
**Execution:** Deploy additive schema change; run rate-limited backfill; compare results; enable dual-read after reconciliation.  
**Verification:** Active-row count and SHA-256 batch checksums match the pre-migration export; ten tenant API smoke checks return the expected region.  
**Rollback:** If counts or checksums diverge, Noor disables dual-read, stops the backfill, restores the previous index plan, and opens an incident record.
