---
id: KPI-CATALOG-ROUTING
kind: kpi-catalog
chapter: CH-08
kpis:
  - id: KPI-ROUTE-001
    name: Explainable policy-decision coverage
    decision: Whether route decisions can be reconstructed and governed.
    calculation: production route decisions with policy revision, reason code, tenant, and correlation ID divided by all production route decisions.
    source: route telemetry and policy registry
    frequency: release and weekly
    owner: Routing owner
    target: 100 percent
    warning: below 100 percent
    distortions: [excluding fallback decisions, counting logs without policy revision]
    anti_gaming: [sample raw traces, reconcile decisions to request volume]
    interpretation: Any unexplainable privileged route requires investigation before release.
  - id: KPI-ROUTE-002
    name: Boundary-preserving fallback coverage
    decision: Whether failure behavior stays within approved constraints.
    calculation: tested failure scenarios that queue or select an approved fallback divided by all declared failure scenarios.
    source: routing fixture suite and outage drills
    frequency: release
    owner: SRE owner
    target: 100 percent
    warning: below 100 percent
    distortions: [omitting regional outages, treating an untested default as approved]
    anti_gaming: [review denied candidates, inject provider and budget failures]
    interpretation: A cross-boundary fallback is a release blocker regardless of coverage.
---

# Routing KPI catalog

Read cost and latency with policy conformance; a cheap or fast forbidden route is not a successful outcome.
