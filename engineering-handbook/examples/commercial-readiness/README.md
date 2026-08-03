---
id: EX-CH11-COMMERCIAL
kind: worked-example
chapter: CH-11
standards: [NIST-SSDF-1.1, OWASP-ASVS-5.0.0]
preconditions: [isolated Atlas billing tenant, versioned offer catalog, signed usage-event fixtures, payment gateway simulator]
placement: engineering-handbook/examples/commercial-readiness
dependencies: [entitlement service fixture, usage aggregator, invoice simulator, support-case sandbox]
invocation: Apply the Atlas Standard-to-Enterprise upgrade, submit duplicate and valid usage events, then issue a cancellation and credit fixture.
expected_output: Every entitlement verdict matches the effective offer; duplicate usage is deduplicated; the invoice reconciles to accepted events; access changes are visible to support.
failure_output: A feature remains available after cancellation, a duplicate event is billed twice, a credit lacks approval, or tenant data appears in another account's support view.
interpretation: Commercial evidence is passing only when entitlement, usage, invoice, and support records agree on the same customer outcome.
remediation: Correct effective-date handling, use idempotent usage keys, enforce access at execution boundaries, link credits to approvals, and rerun the reconciliation fixture.
cleanup: Delete sandbox invoices and support cases, reset tenant entitlements, and remove generated event fixtures according to the test retention policy.
---

# Product Atlas commercial readiness evidence

Atlas tenant `atlas-42` upgrades from Standard to Enterprise at 12:00 UTC with a 10,000-request monthly quota and export entitlement. The test uses one signed usage event twice, one distinct event once, a queued export, a cancellation at 13:00 UTC, and an approved overage credit.

| Check | Expected result | Evidence |
| --- | --- | --- |
| Upgrade | Enterprise entitlement applies after the approved effective time | catalog revision, entitlement verdict |
| Meter | Duplicate `usage-0031` counts once; `usage-0032` counts once | event IDs, aggregation record |
| Invoice | Invoice line equals two accepted events plus approved credit | invoice reference, reconciliation delta |
| Cancellation | New and queued export work is denied after 13:00 UTC | execution verdict, support timeline |

**Product Atlas result.** `usage-0031` was deduplicated, the August reconciliation delta was `0 USD`, and the queued export received `plan-entitlement-missing` at execution after cancellation. The support case showed the offer revision, cancellation time, and credit approval without exposing billing data from another tenant.
