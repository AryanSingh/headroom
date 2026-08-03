---
id: KPI-CATALOG-COMMERCIAL
kind: kpi-catalog
chapter: CH-11
kpis:
  - id: KPI-COMM-001
    name: Entitlement transition enforcement coverage
    decision: Whether offered capability transitions are consistently enforced across all execution boundaries.
    calculation: passing grant, deny, upgrade, downgrade, cancellation, and queued-work enforcement fixtures divided by required fixtures across offered capabilities.
    source: entitlement fixture suite, service decision logs, and catalog registry
    frequency: release and weekly
    owner: Commercial product owner
    target: 100 percent
    warning: below 100 percent or any post-revocation execution
    distortions: [testing UI only, excluding workers or exports, counting stale catalog revisions]
    anti_gaming: [require fixture coverage by boundary and lifecycle transition, reconcile against active offer catalog]
    interpretation: A hidden button is not enforcement; every executable boundary must deny unavailable capability.
  - id: KPI-COMM-002
    name: Commercial reconciliation completion
    decision: Whether customer usage, invoices, adjustments, and support records reconcile to approved source evidence.
    calculation: billable accounts with a completed zero-or-approved-tolerance reconciliation divided by billable accounts in the evaluation period.
    source: usage ledger, billing aggregation, invoice system, credit register, and support case references
    frequency: monthly close and billing release
    owner: Billing owner
    target: 100 percent
    warning: any unexplained charge, missing approval, or unreconciled account
    distortions: [excluding disputed accounts, netting duplicate usage without event-level evidence, treating issued invoices as proof]
    anti_gaming: [retain source event IDs, review adjustments independently, sample customer-visible usage]
    interpretation: Revenue reported without an explainable ledger-to-invoice chain is a financial and trust risk.
---

# Commercial readiness KPI catalog

Review entitlement coverage with reconciliation completion. An on-target revenue figure does not override an unauthorized access path, duplicate meter event, or customer charge without evidence.
