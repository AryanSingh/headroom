# CutCtx Billing and Licensing Integration

## Hosted commerce authority

**PitchToShip is the single hosted commerce authority for CutCtx.** It owns
the pricing catalogue, Razorpay Standard Checkout, payment-signature
verification, license issuance, and customer account portal. CutCtx never
creates a payment order, calls Razorpay, or receives a Razorpay key or webhook
secret.

The historical name **Headroom** is a compatibility alias only. Customer-facing
purchase, installation, and support material uses **CutCtx**.

## Customer flow

1. A CutCtx purchase action calls `get_checkout_url()`.
2. The helper opens a deterministic PitchToShip deep link:

   ```text
   https://pitchtoship.com/billing?product=cutctx&plan=starter&billing=monthly
   ```

3. PitchToShip displays the selected CutCtx context and opens Razorpay Standard
   Checkout. The backend derives the amount and currency; CutCtx does not send
   a price.
4. PitchToShip verifies Razorpay's HMAC payment signature, issues a license,
   and sends the customer to the account portal.
5. The customer configures CutCtx with the issued license key. CutCtx verifies
   it through PitchToShip and applies the returned entitlement tier/features.

`get_portal_url(email)` opens `https://pitchtoship.com/account?email=...` so a
customer can find active licenses and expiry information.

## CutCtx activation contract

Set only the hosted license-service base URL in CutCtx:

```env
PITCHTOSHIP_URL=https://pitchtoship.com
CUTCTX_LICENSE_KEY=PTS-...
```

The `cutctx_ee.billing.pitchtoship_client` calls:

```text
POST /api/licenses/verify
{ "license_key": "PTS-...", "hwid": "machine-id" }
```

When valid, PitchToShip returns an ECDSA P-256 signed token in
`pts1.<payload>.<signature>` format. CutCtx caches the token encrypted on the
machine and verifies it with PitchToShip's public key for offline use. Invalid,
tampered, or expired tokens deny commercial features.

## Plan mapping

| CutCtx commercial tier | PitchToShip plan |
| --- | --- |
| `team` | `starter` |
| `business` | `studio` |
| `enterprise` | `portfolio` (contact sales) |

This mapping is for navigation only. The PitchToShip license service remains
the authority for actual entitlement tier, features, seats, and expiry.

## Environment boundary

CutCtx must not set any `RAZORPAY_*` secret. Configure Razorpay credentials
only in PitchToShip's server/Pages environment.

The legacy `STRIPE_*` configuration and `/webhooks/stripe` handler exist only
for explicitly managed enterprise compatibility. They are not part of CutCtx
self-serve checkout. In particular, CutCtx **does not create a Stripe Checkout
Session**.

## Local verification

1. Run a local PitchToShip license service with a temporary database and
   Razorpay test credentials.
2. Complete a Razorpay test-mode checkout from the PitchToShip billing page.
3. Configure `PITCHTOSHIP_URL` to that local service and activate CutCtx with
   the issued test license key.
4. Confirm the online response is valid, then verify a cached token while the
   service is unavailable.

Never place production Razorpay secrets, customer payment details, or a real
license key in CutCtx source, fixtures, or documentation examples.
