# cutctx_ee/billing/

## Responsibility
Implements enterprise license issuance/validation and external billing integrations.

## Design
License database and signed token services own entitlement state; clients isolate PitchToShip and Stripe webhook APIs behind typed verification paths.

## Flow
Checkout/webhook events are verified, license records are created or updated, signed tokens are issued/validated, and billing clients expose current state.

## Integration
Used by proxy license/billing routes and `cutctx_ee.entitlements`; integrates with Stripe, PitchToShip, persistent license state, and signing keys.
