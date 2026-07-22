# License and Billing Handoff

This assisted pilot uses manual payment confirmation and manual license
issuance. Self-serve checkout remains outside scope.

## Before issuing a license

- Confirm the contracting entity and approved pilot agreement.
- Confirm payment or invoice approval.
- Record customer name, billing contact, plan, seats, start date, expiry date,
  and support terms.
- Confirm the customer accepts the data and telemetry settings.

## Issue and activate

Issue the license through the approved license authority. Send the full key only
through the approved secret channel. Configure it as `CUTCTX_LICENSE_KEY`, then
verify that the runtime reports an active or trial entitlement for the intended
plan.

Do not use `CUTCTX_ENTITLEMENT_TIER` as proof of payment. An invalid, expired,
revoked, or unverifiable license must retain Builder access.

## Security and records

Logs, screenshots, tickets, and support bundles must redact the full license
key. Store only an approved key prefix when an operational record needs an
identifier. Record renewal, revocation, seat changes, and authority outages in
the customer record.

## Handoff sign-off

- Payment confirmed by:
- License issued by:
- License prefix:
- Plan and seats:
- Expiry or renewal date:
- Customer activation confirmed by:
- Support owner:

