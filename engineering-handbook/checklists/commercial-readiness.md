---
id: CL-COMM-01
kind: checklist
title: Commercial readiness release checklist
chapter: CH-11
controls:
  - id: ENG-COMM-001
    requirement: Every offered capability must have a versioned entitlement definition enforced at all customer and background execution boundaries.
    applicability: required for packages, add-ons, trials, quotas, exports, APIs, and administrative access
    procedure: Compare the catalog matrix with UI, API, worker, export, and administrator fixtures for grant, deny, upgrade, downgrade, and cancellation transitions.
    expected_result: Each request receives the effective entitlement decision with a stable reason, and revoked access cannot complete queued or background work.
    evidence: catalog revision, entitlement matrix, fixture IDs, decision records, and owner sign-off
    automation: entitlement transition and execution-boundary suite
    owner: Commercial product owner
    frequency: release and every offer, entitlement, or lifecycle-policy change
    failure_action: block launch, disable the affected offer or feature, correct enforcement, and repeat all transition fixtures
    standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
  - id: ENG-COMM-002
    requirement: Usage, billing, credit, and customer-visible records must reconcile from idempotent source events with approved adjustments.
    applicability: required for usage-priced, subscription, consumption-limited, or internally charged products
    procedure: Reconcile accepted event IDs, aggregation output, invoice lines, credits, and support records across representative lifecycle fixtures.
    expected_result: The reconciliation delta is within the approved tolerance; duplicate events are neutralized; every adjustment has an owner and approval.
    evidence: event ledger, aggregation report, invoice reference, adjustment approval, reconciliation result, and exception record
    automation: usage idempotency and invoice-reconciliation suite
    owner: Billing owner
    frequency: each billing release, pricing or meter change, and monthly close
    failure_action: stop billing promotion, isolate affected charges, notify the commercial owner, and correct or credit through the approved process
    standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
---

# Commercial readiness release checklist

- [ ] Publish the approved offer, effective date, price, entitlement, quota, and accountable owner.
- [ ] Verify grant, deny, upgrade, downgrade, cancellation, retry, export, API, worker, and administrator enforcement.
- [ ] Reconcile signed usage events, aggregation, invoices, credits, and customer-visible usage.
- [ ] Confirm support escalation, customer communication, privacy, retention, and commitment evidence.
- [ ] Record exceptions with impact, compensating control, owner, and expiry.
