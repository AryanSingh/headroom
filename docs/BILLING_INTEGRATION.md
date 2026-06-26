# Cutctx / Cutctx — PitchToShip Billing Integration

Cutctx billing is managed centrally by **PitchToShip** (`pitchtoship.com`) using **Razorpay** as the payment processor. The Cutctx proxy validates licenses against the PitchToShip entitlements API at startup and on-demand.

## How it works

1. Customer visits `pitchtoship.com` and subscribes to a plan via Razorpay checkout.
2. On `subscription.activated`, the PitchToShip webhook issues a license key and tags the customer's plan in Razorpay.
3. The Cutctx proxy reads `CUTCTX_LICENSE_KEY` and validates it by calling `CUTCTX_LICENSE_VALIDATION_URL` at startup.
4. If the license is valid and includes `Cutctx`, the proxy starts normally. Otherwise it enters trial or blocked mode per `CUTCTX_TRIAL_ENFORCEMENT`.

## Plans that include Cutctx

| Plan | Products included | Monthly price |
|------|------------------|---------------|
| **Starter** | Cutctx only | $49/mo |
| **Studio** | Cutctx + Bruno + VibeGuard | $149/mo |
| **Portfolio** | All products (custom terms) | Contact sales |

## Environment variables

```env
# License key issued by PitchToShip after a successful Razorpay payment
CUTCTX_LICENSE_KEY=pts_live_...

# PitchToShip entitlements endpoint — validates the license at startup
# GET /api/billing/entitlements?email=<customer-email>
CUTCTX_LICENSE_VALIDATION_URL=https://pitchtoship.com/api/billing/entitlements

# PitchToShip/Razorpay webhook secret — required when STRICT_MODE=1
CUTCTX_RAZORPAY_WEBHOOK_SECRET=pts_whsec_...

# Set to 1 to refuse startup without a valid license
CUTCTX_BILLING_STRICT_MODE=1

# Set to 0 to disable the trial countdown
CUTCTX_TRIAL_ENFORCEMENT=1
```

## API endpoints (PitchToShip backend)

### Check entitlements
```
GET https://pitchtoship.com/api/billing/entitlements?email=<customer-email>
```
Response:
```json
{
  "active": true,
  "plan": "starter",
  "products": ["Cutctx"],
  "validUntil": "2026-07-25T00:00:00.000Z",
  "customerId": "cust_...",
  "subscriptionId": "sub_..."
}
```

The proxy checks that `"Cutctx"` appears in `products` and that `active` is `true`.

### Validate a license key directly
```
POST https://pitchtoship.com/api/billing/validate
Content-Type: application/json

{ "key": "pts_live_...", "product": "Cutctx" }
```

## Webhook note

The `CUTCTX_RAZORPAY_WEBHOOK_SECRET` replaces the old `CUTCTX_STRIPE_WEBHOOK_SECRET`. If you have the old variable set in an existing deployment, rename it to `CUTCTX_RAZORPAY_WEBHOOK_SECRET`. The billing provider changed from Stripe to Razorpay via PitchToShip.

## Air-gap / offline mode

When `CUTCTX_OFFLINE_MODE=1`, license validation falls back to `CUTCTX_LICENSE_HMAC_SECRET` for offline HMAC verification. The PitchToShip entitlements URL is not called in this mode.

## Support

For billing issues, direct customers to `pitchtoship.com/billing` or `hello@pitchtoship.com`.
