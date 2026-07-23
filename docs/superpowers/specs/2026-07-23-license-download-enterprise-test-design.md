# License download and enterprise test design

## Goal

Let a signed-in CutCtx customer download the non-sensitive details of each
license they own, and validate tier-gated licensing with a dedicated Enterprise
test entitlement.

## Scope

- Provision one dedicated, active Enterprise test license for the existing
  customer account. It remains separate from Builder and Team licenses.
- Test the expected seat boundaries: Builder permits one active seat, Team
  permits ten, and Enterprise permits five hundred.
- Exercise the existing hosted verification and seat-heartbeat endpoints with
  the correct tier-specific keys.
- Add one Download key control per displayed license card. The generated text
  file contains only the license key, tier, status, seat capacity, and expiry.

## Data flow

1. The license portal loads the authenticated customer's existing licenses.
2. For each card, its download control creates a client-side text file from the
   already-authorized license response and starts a download. No new backend
   request and no token or payment data are included.
3. The Enterprise test license is issued through the existing Supabase billing
   migration path and is checked through the same public license verification
   and seat allocation paths used in production.

## Safety and testing

- The download file excludes browser sessions, Supabase tokens, customer data,
  payment identifiers, and internal database ids.
- Automated portal tests assert the control and safe file content contract.
- Automated hosted-function tests cover Builder, Team, and Enterprise limits.
- A live browser test verifies that the Enterprise card and download control
  appear after a Magic Link sign-in.

## Out of scope

- Changing pricing, payment behavior, or production Enterprise sales flow.
- Adding a general-purpose license export API.
