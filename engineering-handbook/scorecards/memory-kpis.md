---
id: KPI-CATALOG-MEMORY
kind: kpi-catalog
chapter: CH-09
kpis:
  - id: KPI-MEM-001
    name: Retrieval scope-enforcement coverage
    decision: Whether every retrieval path enforces current scope before disclosure.
    calculation: retrieval paths with passing tenant, role, expiry, and revocation fixtures divided by all retrieval paths.
    source: memory inventory and access contract suite
    frequency: release
    owner: Memory owner
    target: 100 percent
    warning: below 100 percent
    distortions: [excluding caches, testing only same-tenant happy paths]
    anti_gaming: [enumerate index and cache paths independently, require denied-result evidence]
    interpretation: One cross-tenant or revoked retrieval blocks release.
  - id: KPI-MEM-002
    name: Verified deletion completion
    decision: Whether subject deletion reaches every retrievable memory layer on time.
    calculation: deletion requests with verified primary, index, cache, and export completion within objective divided by completed deletion requests.
    source: deletion job ledger and all-layer verification suite
    frequency: weekly and release
    owner: Privacy owner
    target: 100 percent
    warning: below 100 percent
    distortions: [closing jobs after primary deletion, ignoring delayed index queues]
    anti_gaming: [sample retrieval after closure, reconcile layers to topology inventory]
    interpretation: Any incomplete deletion stays open and triggers containment review.
---

# Memory KPI catalog

Report deletion completion by layer and age; a blended average can conceal an exposed derivative.
