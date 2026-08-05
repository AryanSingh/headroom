---
id: KPI-CATALOG-OBSERVABILITY
kind: kpi-catalog
chapter: CH-19
kpis:
  - id: KPI-OBS-001
    name: Critical outcome reconstruction coverage
    decision: Whether critical outcomes can be reconstructed from retained, correlated, privacy-safe evidence.
    calculation: critical outcomes with passing normal, degraded, and recovery reconstruction fixtures divided by all critical outcomes.
    source: service inventory, telemetry contract registry, and fixture reports
    frequency: release and monthly
    owner: SRE owner
    target: 100 percent
    warning: below 100 percent or any missing correlation or unsafe telemetry field
    distortions: [testing happy paths only, treating logs alone as evidence, excluding sampled errors]
    anti_gaming: [require three-state fixture, business-ledger correlation, and redaction assertion]
    interpretation: Coverage means an operator can answer what happened and what to do next without sensitive content.
  - id: KPI-OBS-002
    name: Actionable critical alert rate
    decision: Whether critical alerts reliably detect customer-impacting conditions and route a safe first action.
    calculation: critical alert exercises with correct detection, owner route, scoped diagnostic link, and usable runbook divided by all critical alert exercises.
    source: alert registry, route tests, fixture timestamps, and incident records
    frequency: quarterly and after signal changes
    owner: Service owner
    target: 100 percent
    warning: any missed route, unactionable alert, or customer-reported detection ahead of alert
    distortions: [suppressing alerts to reduce noise, counting acknowledgements as diagnosis, excluding noisy periods]
    anti_gaming: [measure simulated detection and customer discovery, sample alert payloads, retain failed exercises]
    interpretation: Quiet alerts are useful only when detection and first response remain trustworthy.
---

# Production observability KPI catalog

Assess reconstruction and alert actionability jointly. A complete dashboard cannot compensate for unsafe telemetry or an alert that reaches nobody.
