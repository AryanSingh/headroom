# Billing Integration Status

This document describes the **current repository state** for Cutctx billing and
licensing. It is intentionally operational and does not claim that the hosted
self-serve billing path is production-ready.

## Current architecture in this repo

The billing surface is split across two layers:

1. **Hosted checkout / portal helpers** prefer direct Stripe when it is
   explicitly configured, and retain the operator-managed PitchToShip path as
   a compatibility fallback.
2. **Enterprise subscription mapping** in the EE webhook handler is
   Stripe-based and reads `STRIPE_*` environment variables for tier mapping.

That means the current codebase reflects a **hybrid, transitional billing
surface**, not a single polished self-serve system.

## What the code does today

### Checkout helpers

- `cutctx/billing.py`
- `cutctx_ee/billing/__init__.py`

When direct Stripe is configured, these helpers:

- create a Stripe Checkout Session for the mapped tier/period Price ID
- look up the Stripe customer by email and create a Billing Portal session
- return only Stripe-hosted URLs from the direct path

Without direct Stripe configuration, these helpers retain the legacy path:

- default `PITCHTOSHIP_BASE_URL` to `https://pitchtoship.com`
- call `POST /api/billing/checkout` to request a checkout URL
- fall back to `/checkout?plan=...` if the API call fails
- call `POST /api/billing/portal` for a portal URL
- fall back to `/billing` if the API call fails

Current tier mapping in these helpers is:

| Cutctx tier | Hosted plan key |
|---|---|
| `team` | `starter` |
| `business` | `studio` |
| `enterprise` | `portfolio` |

### EE webhook handling

- `cutctx_ee/billing/stripe_webhook.py`

The enterprise webhook handler is Stripe-based. It currently reads:

- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_API_KEY`
- `STRIPE_PRICE_TEAM`
- `STRIPE_PRICE_BUSINESS`
- `STRIPE_PRICE_ENTERPRISE`

The webhook code maps Stripe price IDs back to Cutctx tiers.

### Offline / air-gapped licensing

Offline licensing does **not** depend on the hosted billing URLs.
Air-gapped and offline paths rely on signed local verification material such as:

- `CUTCTX_LICENSE_HMAC_SECRET`
- offline license data / locally cached license state

See:

- `docs/air-gap-deployment.md`

## Environment variables in active use

### Hosted helper layer

```env
# Direct Stripe self-service (all required for direct Checkout)
STRIPE_SECRET_KEY=sk_test_...
CUTCTX_STRIPE_PRICE_TEAM_ANNUAL=price_...
CUTCTX_STRIPE_PRICE_TEAM_MONTHLY=price_...
CUTCTX_STRIPE_PRICE_BUSINESS_ANNUAL=price_...
CUTCTX_STRIPE_PRICE_BUSINESS_MONTHLY=price_...
CUTCTX_STRIPE_PRICE_ENTERPRISE_ANNUAL=price_...
CUTCTX_STRIPE_PRICE_ENTERPRISE_MONTHLY=price_...
CUTCTX_STRIPE_SUCCESS_URL=https://cutctx.com/billing/success?session_id={CHECKOUT_SESSION_ID}
CUTCTX_STRIPE_CANCEL_URL=https://cutctx.com/pricing
CUTCTX_STRIPE_PORTAL_RETURN_URL=https://cutctx.com/billing

# Legacy operator-managed fallback
PITCHTOSHIP_URL=https://pitchtoship.com
```

### Stripe webhook layer

```env
STRIPE_WEBHOOK_SECRET=...
STRIPE_API_KEY=...
STRIPE_PRICE_TEAM=...
STRIPE_PRICE_BUSINESS=...
STRIPE_PRICE_ENTERPRISE=...
```

### Offline verification

```env
CUTCTX_LICENSE_HMAC_SECRET=...
CUTCTX_OFFLINE_MODE=1
```

## Important release note

The repository contains tested direct Stripe request construction, but that is
**not evidence of a working customer self-serve checkout flow**. Release,
go/no-go, and audit work must verify Checkout, Portal, and a signed webhook
against Stripe test-mode credentials and real Price IDs before treating the
flow as launch-ready.

## Support guidance

Until the hosted billing path is fully verified and customer-facing materials are
updated, treat billing and licensing issues as an operator-led support flow
rather than a self-serve flow.
