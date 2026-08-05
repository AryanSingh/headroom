---
id: KPI-CATALOG-INTEGRATIONS
kind: kpi-catalog
chapter: CH-07
kpis:
  - id: KPI-INT-001
    name: Privileged integration authority coverage
    decision: Whether an integration/tool release has tested authority boundaries.
    calculation: privileged actions with current signature, tenant, replay, and approval evidence divided by all privileged actions.
    source: integration inventory and contract suite
    frequency: release
    owner: Integration owner
    target: 100 percent
    warning: below 100 percent
    distortions: [classifying privileged action as preview, excluding rarely used provider actions]
    anti_gaming: [independent action inventory review, verify execution endpoint separately from UI]
    interpretation: One untested expense-delivery action blocks release.
---

# Integration KPI catalog

Never average an unapproved privileged action away with safe read-only actions.
