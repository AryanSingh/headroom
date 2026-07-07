# Enterprise Installation Guide

This guide covers the setup and configuration of Cutctx Enterprise Edition (`cutctx-ee`) for production deployments.

For background on Cutctx's licensing model and component distribution, see [LICENSING.md](../LICENSING.md) and [ENTERPRISE.md](../ENTERPRISE.md).

---

## Package Acquisition

### Open-core model

Cutctx uses an open-core distribution model:

- **`cutctx-ai`** (Apache-2.0) — the compression engine, proxy, SDKs, CLI, and analytics surface — is published openly on [PyPI](https://pypi.org/project/cutctx-ai/).
- **`cutctx-ee`** (proprietary) — enterprise admin controls, licensing/billing, identity/access, and audit — is distributed separately to paying customers.

### Getting `cutctx-ee`

**Current distribution method:**

Contact your Cutctx account manager to obtain access credentials and the package distribution endpoint. The commercial package is not available on the public PyPI index.

**Installation** (once you have access):

Once you have obtained credentials from the sales team, install both packages together:

```bash
pip install cutctx-ai[ee]
```

This installs:
- `cutctx-ai` version `0.30.0` (open-core client)
- `cutctx-ee` (proprietary enterprise modules)

**Version compatibility:**

The `cutctx-ai` and `cutctx-ee` packages are tested for compatibility. Ensure you maintain version alignment when updating either package. The canonical version is declared in the root `pyproject.toml`; consult your Cutctx release notes before upgrading.

---

## License Activation

Enterprise deployments require a valid license key to enable billing, seat leasing, and identity controls. License activation happens at proxy startup.

### Environment variables

Set these before starting the proxy:

| Variable | Purpose | Example |
|----------|---------|---------|
| `CUTCTX_LICENSE_KEY` | Signed license key issued by Cutctx | `enterprise-xxxxxxxx-signature` |
| `CUTCTX_LICENSE_HMAC_SECRET` | Secret for offline license cache verification (air-gap mode) | Base64-encoded 32-byte key |
| `CUTCTX_LICENSE_API_URL` | (Optional) License validation API endpoint for online verification | `https://license-api.cutctx.com` |
| `CUTCTX_LICENSE_KID` | (Optional) Key ID for residency proof signing | `key-id-001` |
| `CUTCTX_LICENSE_PRIVATE_KEY` | (Optional) Ed25519 private key for residency proof | PEM-encoded key |
| `CUTCTX_LICENSE_PUBLIC_KEY` | (Optional) Ed25519 public key for license verification | PEM-encoded key |

### Activation workflow

1. **Receive license key** from Cutctx (via email or portal).

2. **Set environment variables:**

   ```bash
   export CUTCTX_LICENSE_KEY="enterprise-abc123def456-signature"
   export CUTCTX_LICENSE_HMAC_SECRET="base64-encoded-32-byte-secret"
   ```

3. **Start the proxy:**

   ```bash
   cutctx proxy --port 8787
   ```

   The proxy validates the license key on startup and caches the result locally (encrypted with `CUTCTX_LICENSE_HMAC_SECRET`).

4. **Verify activation:**

   ```bash
   curl -s http://localhost:8787/v1/license/crl \
     -H "Authorization: Bearer $ADMIN_KEY"
   ```

   This returns the Certificate Revocation List (CRL) if the license is active.

### License types and tiers

Your license key encodes a **tier** (team, business, enterprise) and **seat count**. The tier gates feature access; the seat count is enforced at the seat-lease endpoint.

License details are available via the admin panel dashboard.

---

## Stripe Billing Integration

Enterprise subscriptions are tied to Stripe for recurring billing. The proxy receives and validates subscription lifecycle events via webhooks.

### Configuration

Set these environment variables before starting the proxy:

| Variable | Purpose | Example |
|----------|---------|---------|
| `STRIPE_API_KEY` | Stripe API key (secret key for server-side operations) | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret from Stripe Dashboard | `whsec_...` |
| `STRIPE_PRICE_TEAM` | Stripe price ID for team tier | `price_1A2B3C4D5E6F7G8H9I...` |
| `STRIPE_PRICE_BUSINESS` | Stripe price ID for business tier | `price_2B3C4D5E6F7G8H9I0J...` |
| `STRIPE_PRICE_ENTERPRISE` | Stripe price ID for enterprise tier | `price_3C4D5E6F7G8H9I0J1K...` |

### Webhook endpoint

Configure your Stripe account to send events to:

```
https://{your-domain}/webhooks/stripe
```

The proxy listens on this path and validates all incoming webhooks.

### Signature validation

Every webhook is signed with HMAC-SHA256. The proxy validates the signature before processing:

1. **Header format:**
   ```
   Stripe-Signature: t={timestamp},v1={signature}
   ```

2. **Verification process (performed automatically by the proxy):**
   - Parse the `t` (timestamp) and `v1` (signature) from the header.
   - Compute `signed_content = {timestamp}.{request_body}`
   - Compute `expected_signature = HMAC-SHA256(STRIPE_WEBHOOK_SECRET, signed_content)`
   - Compare `expected_signature` with `v1` using constant-time comparison.
   - If the timestamp is more than 5 minutes old, reject the webhook (replay protection).

3. **Example (for testing):**
   ```bash
   python -c "
   import hmac
   import hashlib
   timestamp = '1234567890'
   payload = b'{\"id\": \"evt_...\"}'
   secret = 'whsec_...'
   signed = f'{timestamp}.'.encode() + payload
   sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
   print(f't={timestamp},v1={sig}')
   "
   ```

### Webhook events handled

- **`checkout.session.completed`** — Customer completes checkout; proxy generates license key and seat count.
- **`invoice.paid`** — Invoice payment confirmed; proxy extends license expiry.
- **`customer.subscription.deleted`** — Subscription cancelled; proxy deactivates license.
- **`customer.subscription.updated`** — Subscription tier or seat count changed; proxy updates license record.

---

## Seat Management and Overage Handling

The proxy tracks active user seats under a license and enforces seat limits.

### Seat checkout

When a user first logs in to the admin panel, the proxy checks out a seat lease:

```bash
curl -X POST http://localhost:8787/v1/license/checkout-seat \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "enterprise-abc123-sig",
    "user_id": "user@example.com",
    "lease_duration": 3600.0
  }'
```

**Response on success (seat available):**
```json
{"status": "seat_leased"}
```

**Response on overage (no seats available):**
```
HTTP 409 Conflict
{"detail": "No seats available"}
```

### Overage behavior (current)

When all seats are leased:

- **New users are rejected** with HTTP 409 (Conflict).
- **Existing users can renew their lease** (same user, same license key).
- **Leases expire** after the `lease_duration` (default: 1 hour). Expired leases are cleaned up on the next checkout attempt.

### Overage behavior (not yet implemented)

The following overage-handling features are **planned but not yet available** in this release:

- **Dunning workflows** — grace periods, warning emails, or suspension thresholds for expired licenses.
- **Overage charges** — additional billing for usage beyond the included seat count.
- **Graceful degradation** — feature gating or rate limiting (instead of hard rejection) when seats are exhausted.

If your deployment requires these features, contact your Cutctx account manager.

---

## Trial and Offline Mode

### Starting a trial

Trial users do not require a license key. To issue a trial:

```bash
curl -X POST http://localhost:8787/v1/license/start-trial \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "trial_token": "trial_xyz123",
    "customer_email": "customer@example.com",
    "duration": 1209600.0
  }'
```

The `duration` is in seconds (default: 14 days).

### Checking trial status

```bash
curl -X POST http://localhost:8787/v1/license/check-trial \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"trial_token": "trial_xyz123"}'
```

**Response:**
```json
{"active": true}
```

### Offline/air-gapped mode

In air-gapped deployments (no outbound internet access):

1. **Pre-stage the license** on the instance before isolation.
2. **Set `CUTCTX_LICENSE_HMAC_SECRET`** (required for cache verification).
3. **Set `CUTCTX_OFFLINE_MODE=1`** to disable online validation calls.

See [docs/air-gap-deployment.md](./air-gap-deployment.md) for the full runbook.

---

## Support and Troubleshooting

### License validation errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| `501 Enterprise billing module not installed` | `cutctx-ee` is not installed | Run `pip install cutctx-ai[ee]` |
| `401 Invalid license` | License key is malformed or revoked | Verify the license key with your account manager |
| `403 License revoked` | License has been revoked by Cutctx | Contact support immediately |
| `409 No seats available` | All seats under the license are leased | Wait for a lease to expire, or upgrade your seat count |

### Webhook signature errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| `STRIPE_WEBHOOK_SECRET not configured` | Env var not set | Set `STRIPE_WEBHOOK_SECRET` from Stripe Dashboard |
| `Webhook signature verification failed` | Signature is invalid or timestamp is stale | Ensure the timestamp is within 5 minutes; check that the secret matches Stripe Dashboard |

### Version mismatch warnings

If you see warnings about version mismatches between `cutctx-ai` and `cutctx-ee`:

- **Check installed versions:**
  ```bash
  pip show cutctx-ai cutctx-ee
  ```

- **Upgrade both together:**
  ```bash
  pip install --upgrade cutctx-ai[ee]
  ```

- **Consult release notes** at [cutctx.dev/changelog](https://cutctx.dev/changelog) for compatibility information.

### Debug logging

Enable verbose logging to diagnose license and billing issues:

```bash
CUTCTX_LOG_LEVEL=DEBUG cutctx proxy --port 8787
```

Check the proxy logs for entries tagged with `license.*` or `billing.*`.

### Support contact

For enterprise support:

- **Email:** [support@payzli.com](mailto:support@payzli.com)
- **Security issues:** [security@cutctx.com](mailto:security@cutctx.com)
- **Slack:** (provided to enterprise customers)

---

## Related Documentation

- [BILLING_INTEGRATION.md](./BILLING_INTEGRATION.md) — Billing architecture overview and hybrid self-serve/operator-led flows.
- [air-gap-deployment.md](./air-gap-deployment.md) — Offline licensing and air-gapped deployment.
- [auth-modes.md](./auth-modes.md) — Admin authentication, RBAC, and SSO setup.
- [LICENSING.md](../LICENSING.md) — Open-core licensing model and component distribution.
- [ENTERPRISE.md](../ENTERPRISE.md) — Enterprise tier features and deployment options.
