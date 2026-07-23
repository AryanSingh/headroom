# CutCtx Inline Checkout and Database Pricing

## Goal

Keep CutCtx buyers on `cutctx.com` from plan selection through license access, and make the database the single source of truth for displayed and charged plan prices.

## Scope

- Add a Supabase billing-plan catalog for the public CutCtx Team and Business plans.
- Seed Team (`starter`) and Business (`studio`) at the current temporary $2 monthly price.
- Add a read-only catalog endpoint for the CutCtx site.
- Make the existing create-order function resolve the selected plan and price from the catalog rather than hard-coded constants.
- Replace CutCtx pricing-page links to `pitchtoship.com/billing` with an inline email-and-checkout interaction that loads Razorpay on CutCtx.
- Continue to verify payment, issue the license, send the license email, and return the buyer to `cutctx.com/licenses` through the existing Supabase functions.

## Data model

`billing_plans` is a server-owned catalog with:

- product identifier (`cutctx`)
- external plan id (`starter` or `studio`)
- customer-facing name and description
- price in minor currency units, currency, and billing interval
- active state and display ordering

The database grants no browser write access. A public endpoint exposes only active public fields. `create-order` queries the catalog with server credentials and uses its returned price when creating the Razorpay order.

## CutCtx checkout flow

1. The pricing page fetches active CutCtx plans from Supabase and renders their names, copy, and price.
2. Selecting a plan opens the inline checkout area on CutCtx and requires a valid checkout email.
3. CutCtx asks `create-order` to create a Razorpay order for the selected plan and email.
4. Razorpay Checkout opens in place; its public key and order amount come only from the server response.
5. CutCtx sends the signed payment response to `verify-payment`.
6. On success, the existing issuance and Resend email behavior runs, and the browser navigates to `https://cutctx.com/licenses`.

## Security and error handling

- The client sends only plan id and email; it never supplies an amount.
- The Edge Function validates plan/product/active state and retrieves the amount from Supabase.
- Razorpay order notes retain product and plan identifiers to support payment verification.
- Static-site CSP adds only Razorpay Checkout and the configured Supabase origin.
- The page gives clear recoverable errors for unavailable plan data, invalid email, dismissed checkout, order creation failure, and payment verification failure.

## Verification

- Unit tests cover catalog selection and server-side price authority, including rejection of inactive or unknown plans.
- Frontend/static tests cover catalog rendering and the CutCtx-only checkout handoff.
- Existing payment verification and license-email tests remain green.
- Live smoke checks confirm plan retrieval, CORS, static CSP, and CutCtx route behavior. A full Razorpay test payment remains an explicit manual action.

## Out of scope

- Subscription recurrence, invoice portal redesign, coupon support, tax calculation, and plan-admin UI.
- Changes to existing PitchToShip pricing pages outside of the shared secure order function.
