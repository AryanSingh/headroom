---
id: KPI-CATALOG-DESKTOP
kind: kpi-catalog
chapter: CH-04
kpis:
  - id: KPI-DESKTOP-001
    name: Interrupted upgrade recovery rate
    decision: Whether desktop update can proceed.
    calculation: successful restart/recovery cases divided by supported interrupted-upgrade cases.
    source: desktop upgrade suite
    frequency: each updater or schema release
    owner: Desktop owner
    target: 100 percent
    warning: below 100 percent
    distortions: [excluding prior versions, avoiding interruption stages]
    anti_gaming: [independent version matrix review, include migration and first-launch interruption]
    interpretation: One data-loss case blocks release.
---

# Desktop KPI catalog

Use this as a release gate for persistent desktop state.
