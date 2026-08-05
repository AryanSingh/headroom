---
id: KPI-CATALOG-RELIABILITY
kind: kpi-catalog
chapter: CH-10
kpis:
  - id: KPI-RELPERF-001
    name: Critical outcome objective attainment
    decision: Whether each critical workload meets its approved availability, correctness, and latency objective.
    calculation: objective windows meeting all declared success, correctness, and percentile-latency thresholds divided by all evaluated objective windows.
    source: client-boundary telemetry, business outcome ledger, and objective registry
    frequency: daily, release, and incident review
    owner: Service owner
    target: 100 percent of critical objectives met
    warning: any critical objective below target or error budget exhaustion
    distortions: [counting HTTP success without business completion, aggregating incompatible workload classes, excluding degraded periods]
    anti_gaming: [reconcile telemetry with business ledger, report by workload and tenant class, retain degradation windows]
    interpretation: A successful response is insufficient when an accepted business outcome is duplicated, delayed beyond its objective, or lost.
  - id: KPI-RELPERF-002
    name: Verified recovery exercise coverage
    decision: Whether recoverable services have current proof that their restoration path meets recovery objectives and preserves integrity.
    calculation: recovery-sensitive services with a passing restore, integrity, scope, and bounded-replay exercise inside the required interval divided by all recovery-sensitive services.
    source: recovery evidence register and service inventory
    frequency: quarterly and before persistence or topology changes
    owner: Data owner
    target: 100 percent
    warning: below 100 percent or any failed integrity check
    distortions: [counting backup completion as recovery, restoring empty fixtures, skipping authorization and replay checks]
    anti_gaming: [require representative fixture identity, independent integrity query, and per-service owner attestation]
    interpretation: A passed backup job does not count until restoration and business-safety checks are evidenced.
---

# Reliability KPI catalog

Review objective attainment alongside correctness and recovery coverage. Capacity gains do not offset a failed integrity check, unbounded queue, or unverified restore.
