---
id: KPI-CATALOG-MIGRATION
kind: kpi-catalog
chapter: CH-16
kpis:
  - id: KPI-MIGRATION-001
    name: Reconciled migration completion coverage
    decision: Whether completed migration executions have evidence that intended business records are correct and complete for every affected tenant.
    calculation: approved migration executions with completed tenant-scoped reconciliation and owner acceptance divided by all approved migration executions in the period.
    source: migration ledger, reconciliation results, exception register, and release decisions
    frequency: every migration and monthly
    owner: Migration owner
    target: 100 percent
    warning: below 100 percent, any unreviewed discrepancy, or a contract change without reconciliation evidence
    distortions: [counting process success as reconciliation, excluding failed or rolled-back executions, aggregating tenants that hide a sparse tenant failure]
    anti_gaming: [require per-tenant result references, sample business-level outcomes, include retries and rollback runs, independently review discrepancies]
    interpretation: Completion means the designated source of truth and migrated outcome reconcile, not that a job returned zero.
  - id: KPI-MIGRATION-002
    name: Tested recovery readiness coverage
    decision: Whether high-risk migration classes have current evidence that interruption, restore, forward repair, and customer-outcome reconciliation are usable.
    calculation: high-risk migration classes with a passing isolated interruption/recovery/reconciliation rehearsal in the required interval divided by all high-risk migration classes.
    source: migration inventory, rehearsal reports, backup-restore logs, and verification plans
    frequency: quarterly, before high-risk migrations, and after recovery-platform changes
    owner: Database owner
    target: 100 percent
    warning: below 100 percent, failed restore, missing checkpoint semantics, or a recovery result without customer-outcome reconciliation
    distortions: [testing empty datasets, restoring schema only, accepting a clean restart without proving deduplication or tenant isolation]
    anti_gaming: [use representative isolated records, inject interruption, verify repeat resume, require tenant-scoped business outcome checks]
    interpretation: Recovery is ready only when it restores a safe, reconciled state under the conditions that make the migration risky.
---

# Database migration KPI catalog

Review reconciliation and recovery together. A fast migration with no tenant-level evidence or rehearseable recovery path is an unbounded integrity risk, not an operational success.
