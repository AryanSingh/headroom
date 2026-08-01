<!-- markdownlint-disable MD013 -->

# Commercialization Report: Verified Billing Risk

**Date:** 2026-07-31
**Final verification:** 2026-08-01
**Method:** Stripe webhook and license-database inspection with sequential and concurrent replay tests.

## Verified outcome

The original report identified the wrong billing defect. `checkout.session.completed` is the correct fulfillment event for the implemented Stripe Checkout flow; adding a parallel `subscription.created` fulfillment path would risk issuing duplicate licenses.

The real defects were replay safety and durable delivery-hook state. Duplicate or concurrent checkout events could issue multiple license records, while a post-commit hook failure could become permanently ineligible for retry. A partial unique index now protects nonempty Stripe subscription IDs. Fulfillment queues delivery-hook work in the same transaction, retries failed calls, and does not repeat a recorded success.

The current `_send_license_email` hook logs issuance and does not call an external mail provider. The outbox proves durable hook processing, not customer email delivery. Paid checkout must not rely on email delivery until an owner configures a real transport with a provider-side idempotency contract.

## Remaining commercial decisions

These are legitimate business or product initiatives, not verified code bugs:

| Initiative | Decision needed |
| --- | --- |
| Direct payment-provider checkout fallback | Decide whether the hosted CutCtx checkout needs a second provider path and define failure ownership before adding one. |
| Self-serve billing UI | Define plan changes, proration, cancellation, invoice access, and account-owner permissions. |
| Professional-services SKU | Validate buyer demand, delivery capacity, scope boundaries, and margin targets. |
| Pricing changes and trial policy | Validate with pipeline, conversion, retention, and willingness-to-pay evidence before changing published prices. |

## Controls to retain

- Stripe signature verification before event processing.
- Database-enforced replay protection for fulfillment.
- Durable retry for failed delivery-hook calls and no replay after recorded success.
- An external mail transport gate before paid checkout depends on email delivery.
- Explicit operational alerting for webhook failures and rejected events.

## Reproduction record

```bash
rtk pytest cutctx/tests/test_billing_integration.py cutctx_ee/tests/test_license_db.py tests/test_capability_extensions.py
```

The billing integration tests passed 15 cases. The database and webhook suites prove sequential and concurrent subscription replay returns one license key, failed hook calls retry, and recorded hook success does not replay.

---
*This report supersedes the unverified fresh-run commercialization audit.*
