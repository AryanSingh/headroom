---
id: KPI-CATALOG-API
kind: kpi-catalog
chapter: CH-06
kpis:
  - id: KPI-API-001
    name: Protected-route authorization coverage
    decision: Whether protected routes have release-grade authorization evidence.
    calculation: protected routes with passing same-tenant and cross-tenant fixtures divided by all protected routes.
    source: API inventory and authorization contract suite
    frequency: release
    owner: API owner
    target: 100 percent
    warning: below 100 percent
    distortions: [excluding legacy routes, counting authentication-only checks]
    anti_gaming: [reconcile to gateway inventory, require resolved-resource fixture evidence]
    interpretation: Any untested protected route blocks release.
  - id: KPI-API-002
    name: Mutation replay safety
    decision: Whether callers can retry state mutations safely.
    calculation: mutation operations with passing duplicate and timeout-recovery tests divided by all mutation operations.
    source: mutation inventory and replay suite
    frequency: release
    owner: Service owner
    target: 100 percent
    warning: below 100 percent
    distortions: [omitting asynchronous mutations, treating a 500 as safe]
    anti_gaming: [include workers and public routes, verify resulting business state]
    interpretation: A duplicate charge or provisioning event blocks release.
---

# API KPI catalog

Review coverage alongside severity and production error budget; metrics do not
replace a specific authorization or data-exposure finding.
