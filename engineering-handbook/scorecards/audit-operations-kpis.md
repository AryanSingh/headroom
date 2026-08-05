---
id: KPI-CATALOG-AUDIT-OPERATIONS
kind: kpi-catalog
chapter: CH-01
kpis:
  - id: KPI-AUDIT-001
    name: High-risk audit coverage
    decision: Whether a release has enough verification to proceed.
    calculation: verified high-risk capabilities divided by identified high-risk capabilities; report unknowns separately.
    source: audit capability matrix and evidence register
    frequency: per release
    owner: Audit lead
    target: 100 percent before approval
    warning: any critical capability unknown
    distortions: [splitting capabilities to inflate denominator, treating planned tests as verified]
    anti_gaming: [review inventory changes, require evidence links for numerator]
    interpretation: A value of 95 percent with one unknown authorization path blocks approval.
  - id: KPI-AUDIT-002
    name: Retest latency
    decision: Whether remediation feedback is fast enough to protect the release window.
    calculation: median elapsed hours from remediation-ready notification to recorded retest result over 30 days.
    source: finding register timestamps
    frequency: monthly
    owner: Engineering quality lead
    target: under 24 hours
    warning: 48 hours or more
    distortions: [marking work ready before it is deployable, excluding failed retests]
    anti_gaming: [sample deployment evidence, include all retest attempts]
    interpretation: A rising median signals a review-capacity or environment bottleneck.
---

# Audit operations KPI catalog

## Scorecard use

Do not average a blocking coverage gap away with fast retests. Product Atlas
records both KPIs, then holds the release if `KPI-AUDIT-001` is below target.
