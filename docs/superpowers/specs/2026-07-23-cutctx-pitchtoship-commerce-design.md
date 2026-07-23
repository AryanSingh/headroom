# CutCtx and PitchToShip commerce discovery

## Outcome

Visitors to `cutctx.com` can immediately find a paid plan, complete a
self-service purchase, retrieve their license, manage their subscription, and
activate CutCtx. PitchToShip remains the exclusive authority for payment,
license issuance, billing records, and customer accounts.

## Context and current gap

CutCtx's pricing page currently contains Team and Business checkout deep links
to PitchToShip, but those links are difficult to discover: its header and
footer omit Pricing and there is no visible license-management route. The
current live PitchToShip billing page compounds the problem: it presents stale
Stripe/Headroom copy rather than the current CutCtx-aware, Razorpay-first
implementation already present in the PitchToShip workspace.

The result is a broken customer journey even though the underlying systems
exist. Buyers cannot confidently tell where to purchase, where their license
arrives, or where to retrieve it later.

## Ownership boundary

PitchToShip is the merchant and licensing authority. It owns:

- The CutCtx pricing catalog and hosted Razorpay checkout.
- Payment verification, license issuance, subscription records, invoices, and
  payment methods.
- The shared customer account and license lookup portal.
- The license-validation service consumed by CutCtx.

CutCtx owns product discovery and local activation. It must only create
deterministic links to PitchToShip; it must not handle payment data, store
checkout email addresses, expose billing secrets, or build a second customer
account system.

## Customer journey

```text
CutCtx public site
  ├─ Pricing / Buy Team / Buy Business
  │    └─ PitchToShip /billing?product=cutctx&plan=<starter|studio>&billing=monthly
  ├─ Manage license
  │    └─ PitchToShip /account (customer supplies their checkout email there)
  └─ Activation instructions
       └─ cutctx license activate <issued-key>

PitchToShip
  ├─ Verifies the hosted payment and issues the CutCtx license
  ├─ Makes the license, entitlement, subscription, invoices, and payment method available in /account
  └─ Provides CutCtx's license verification endpoint
```

The canonical plan mapping is Builder → no checkout, Team → `starter`,
Business → `studio`, and Enterprise → sales/`portfolio`.

## CutCtx changes

1. Add Pricing and Manage license links to the shared public navigation and
   footer. Pricing points to `/pricing/`; Manage license points to
   `https://pitchtoship.com/account`.
2. Rename paid pricing-card CTAs to Buy Team and Buy Business. Preserve their
   canonical PitchToShip plan deep links and add concise disclosure: secure
   checkout at PitchToShip, followed by email license delivery and account
   access.
3. Add a Manage license action in the pricing merchant panel and installation
   documentation. It leads to the PitchToShip account portal, not a CutCtx
   form.
4. Document the local activation command next to the commercial purchase path.
   The command never embeds a real license key.

## PitchToShip changes

1. Bring the current CutCtx-aware billing and license-portal source to the
   deployed `pitchtoship.com` surface. Production must recognize
   `product=cutctx`, present CutCtx in its product context and covered-product
   copy, and route checkout through its configured Razorpay flow.
2. Ensure the shared `/account` surface exposes active CutCtx licenses,
   expiry, entitlements, subscription details, invoices, and payment methods
   to the purchaser after they provide the checkout email.
3. Keep billing copy accurate to the configured processor. Production must not
   claim Stripe when it is running the Razorpay implementation.

## Failure behavior and security

- CutCtx outbound links remain usable even if billing APIs are unavailable.
- PitchToShip handles invalid email, unavailable license service, canceled
  checkout, failed payment verification, missing license records, and portal
  errors using its existing explicit status states. It never reveals a raw
  license key through an unauthenticated URL.
- CutCtx validates a license locally against PitchToShip and denies paid
  capabilities for missing, invalid, expired, revoked, or unavailable trusted
  entitlement states.
- Neither site puts payment keys, gateway secrets, webhook secrets, or a
  customer checkout email into CutCtx source, browser storage, or analytics.

## Verification

1. CutCtx static-site tests confirm every global navigation/footer and pricing
   CTA uses the canonical Pricing, PitchToShip checkout, and account URLs.
2. PitchToShip unit tests confirm a CutCtx deep link preselects its context,
   the Team/Business mappings are purchasable, and its account/license lookup
   route can load the relevant entitlement state.
3. Browser smoke tests against the deployed sites confirm:
   - `cutctx.com/pricing/` exposes Buy Team, Buy Business, and Manage license
     without scrolling to an undiscoverable section;
   - Team and Business land on a CutCtx-aware PitchToShip billing page;
   - the live billing surface names CutCtx and accurately names the configured
     processor;
   - the account portal offers a license lookup and subscription-management
     journey without entering payment or license secrets.
4. A Razorpay test-mode purchase verifies the complete post-payment sequence:
   payment signature verification, issued license, account-portal visibility,
   and local `cutctx license activate` validation.

## Non-goals

- Building a CutCtx-hosted customer portal, checkout form, or payment API.
- Changing PitchToShip's payment-provider configuration without its deployment
  and secret-management process.
- Altering the Enterprise sales-led flow.
