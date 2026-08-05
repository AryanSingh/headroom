---
id: KPI-CATALOG-DASHBOARD
kind: kpi-catalog
chapter: CH-05
kpis:
  - id: KPI-UI-001
    name: Critical journey state coverage
    decision: Whether a changed dashboard journey has adequate release evidence.
    calculation: verified listed states divided by required listed states across critical journeys.
    source: state matrix and browser test report
    frequency: release
    owner: Frontend owner
    target: 100 percent
    warning: below 100 percent
    distortions: [removing difficult states, counting only visual screenshots]
    anti_gaming: [role/state inventory review, require semantic and fixture evidence]
    interpretation: A missing expired-session case blocks approval.
---

# Dashboard KPI catalog

Use state coverage with accessibility blockers and error recovery evidence.
