---
id: KPI-CATALOG-DISCOVERY
kind: kpi-catalog
chapter: CH-02
kpis:
  - id: KPI-DISC-001
    name: High-priority unknown capability rate
    decision: Whether discovery can exit or needs targeted verification.
    calculation: high-priority capability rows tagged unknown or configured-only divided by all high-priority capability rows.
    source: versioned capability matrix
    frequency: each review and material release
    owner: Discovery lead
    target: 0 percent at approval
    warning: greater than 0 percent
    distortions: [downgrading priority to improve the rate, removing hard-to-map capability rows]
    anti_gaming: [independent product-owner review, compare inventory against route and deployment extracts]
    interpretation: One unknown tenant-isolation path blocks approval even when the rate rounds to 1 percent.
  - id: KPI-DISC-002
    name: Runtime evidence freshness
    decision: Whether map evidence still represents deployed behavior.
    calculation: high-priority rows with runtime or test evidence collected after the latest material change divided by all high-priority rows.
    source: evidence register and change ledger
    frequency: release
    owner: Service owner
    target: 100 percent
    warning: below 95 percent
    distortions: [relabeling a change as non-material, counting stale screenshots as runtime evidence]
    anti_gaming: [sample revision hashes and timestamps, require reproducible sources]
    interpretation: A 96 percent result with stale payment-provider evidence holds the related capability.
---

# Discovery KPI catalog

## Scorecard use

Product Atlas pairs unknown rate with evidence freshness. A complete-looking
inventory does not pass the scorecard when its runtime evidence predates a
provider or authorization change.
