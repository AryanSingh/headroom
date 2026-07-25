# Licence activation is broken — CutCtx calls endpoints the portal does not serve

**Date:** 2026-07-25
**Verified by:** direct execution against the live portal using three real, active
CutCtx licence keys (builder / team / enterprise) supplied by the product owner.
**Severity:** Critical — revenue and onboarding blocker
**Status:** **FIXED and verified** in this pass — `cutctx license activate` now
succeeds end-to-end against the real licence API with a real enterprise key.
See "Fix applied" below. The seat-checkout and trial paths remain unrepointed.

> Every prior audit marked licensing "Implemented, **unverified**" because no
> licence key was available. With real keys in hand, the flow does not merely
> lack verification — **`cutctx license activate` fails for every customer.**

---

## Summary

Licensing is served by **Supabase Edge Functions** on project
`udeekuvifncmqvoywhlg`, base URL
`https://udeekuvifncmqvoywhlg.supabase.co/functions/v1`. CutCtx's client code
called `https://pitchtoship.com/v1/license/…`, which that host does not serve.
Because the portal is a single-page app, unmatched paths fell through to the
SPA: `GET` returned the HTML shell with status 200 and `POST` returned
**405 Method Not Allowed**.

This was a **client/server contract mismatch**, not a missing service. The
licence API is deployed and healthy — CutCtx was pointed at the wrong host and
path family.

## The real licence API

Seven Edge Functions, all deployed and current:

| Function | Purpose |
|---|---|
| **`verify-license`** | Validate a key — the activation endpoint |
| `my-licenses` | List a customer's licences (returns org identity) |
| `seat-heartbeat` | Seat occupancy tracking |
| `request-license-link` | Email a licence-delivery link |
| `list-plans` | Plan catalogue |
| `create-order` / `verify-payment` | Razorpay checkout |

Backing tables in the same project: `licenses`, `seats`, `customers`,
`billing_plans`, `payments`.

Verified contract for activation — note the field is **`key`**, not
`license_key` or `licenseKey` (both of those return HTTP 400):

```
POST https://udeekuvifncmqvoywhlg.supabase.co/functions/v1/verify-license
     {"key": "<license-key>"}
200  {"valid":true,"tier":"enterprise","seatsLimit":500,
      "expiresAt":"2027-07-23T19:03:04.128321+00:00"}
```

No anon key or JWT is required for `verify-license`.

## What CutCtx used to call — all fell through to the SPA:

| Endpoint | Method | Status |
|---|---|---|
| `/v1/license/validate` | POST | **405** |
| `/v1/license/activate` | POST | **405** |
| `/v1/license/checkout-seat` | POST | **405** |
| `/v1/license/start-trial` | POST | **405** |
| `/v1/license/check-trial` | POST | **405** |
| `/v1/license/usage` | POST | **405** |
| `/v1/license/crl` | GET | 200, but `text/html` — the SPA shell, not JSON |

## Reproduction

Using a real active enterprise key (expires 2027-07-24, 0/500 seats):

```
$ cutctx license activate <valid-enterprise-key> --no-browser
Validating license key...
  Cloud URL: https://pitchtoship.com
Error: License server returned status 405.
```

What the customer sees afterwards — still on the free tier:

```
$ cutctx license status
  License:    None (using free tier)
Trial Status
  Status:     EXPIRED — basic compression only
```

## Affected call sites

| Caller | Calls | Impact |
|---|---|---|
| `cutctx/cli/license.py:70` | `POST /v1/license/validate` | **Activation fails for every customer.** Default `--cloud-url` is `https://pitchtoship.com`. |
| `cutctx/providers/proxy_routes.py:567` → `cutctx_ee/billing/client.py:158` | `POST /v1/license/checkout-seat` | Seat purchase from the proxy fails. |
| `cutctx_ee/trial.py:114` → `start_trial` | `POST /v1/license/start-trial` | Trial activation fails. |
| `cutctx/telemetry/reporter.py:140` | `POST /v1/license/validate` | Telemetry-side licence validation fails. |
| `cutctx_ee/billing/client.py:64` `is_revoked()` | `GET /v1/license/crl` | See below. Currently **dormant** — no production caller. |

Note the client is not even internally consistent: `cutctx/cli/license.py` uses
`/v1/license/validate` while `cutctx_ee/billing/client.py` uses
`/v1/license/activate`. Neither exists on the portal.

### The revocation landmine

`is_revoked()` has no production callers today, so it causes no customer impact —
but it is wired to fail closed against the live portal. Verified with a real,
valid enterprise key:

```
WARNING cutctx_ee.billing.client: CRL fetch failed (CRL endpoint
  https://pitchtoship.com/v1/license/crl returned 200 with content-type
  'text/html; charset=utf-8', not JSON — the licence API is probably not
  deployed at this URL …)
WARNING cutctx_ee.billing.client: No fresh CRL is available; strict mode
  denies license cutctx_7…
is_revoked(<valid enterprise key>) -> True
```

The chain: the SPA answers 200 → `resp.json()` fails → the `except` branch keeps
an empty cache → strict mode (the production default,
`cutctx_ee/billing/client.py:24`) **denies the licence**. The moment anything
calls `is_revoked()`, every valid paid licence is treated as revoked.

*Fixed in this pass:* a `content-type` guard now raises an actionable error
naming the misconfiguration instead of surfacing an opaque `JSONDecodeError`.
That is a diagnostic improvement only — it does not change control flow, and the
28 existing EE billing tests still pass. The path mismatch itself is unfixed.

## What does work

The entitlement model is sound and correctly tiered — this is a wiring failure,
not a design failure:

| Tier | Features |
|---|---|
| builder | 27 |
| team | 34 |
| business | 47 |
| enterprise | 62 |

35 features are enterprise-only (`air_gap`, `audit_logs`, `episodic_memory`,
`code_graph`, `compliance`, `cross_agent_memory`, …).

The only working route to a paid tier today is the manual override
`CUTCTX_ENTITLEMENT_TIER=enterprise` (read at `cutctx/cli/proxy.py:1291` and
`cutctx/proxy/server.py:5475`). That is an honour-system escape hatch, not
licence enforcement — it grants any self-hoster every paid feature without a key.

## Fix applied

`cutctx/cli/license.py` now targets the Supabase Edge Function:

- New `DEFAULT_LICENSE_API_URL` constant pointing at the functions base, with
  `--cloud-url` overridable via `CUTCTX_LICENSE_API_URL` (legacy
  `PITCHTOSHIP_URL` still honoured for back-compat).
- Request changed to `POST /verify-license` with `{"key": …}`.
- Response parsing changed to `{valid, tier, seatsLimit, expiresAt}`. A 200
  carrying `valid: false` is now a rejection rather than a silent activation,
  and HTTP 400 surfaces the server's own `message`.
- `license status` displays seats and expiry, and no longer prints an empty
  `Org:` field (that identity comes from `my-licenses`, not `verify-license`).

Verified with a real enterprise key:

```
$ cutctx license activate <enterprise-key> --no-browser
  Cloud URL: https://udeekuvifncmqvoywhlg.supabase.co/functions/v1
License activated successfully!
  Status:     active
  Plan:       ENTERPRISE (enterprise)
  Seats:      500
  Expires:    2027-07-23T19:03:04.128321+00:00
  Features:   62 available

$ cutctx license status
  License:    Active
  Plan:       ENTERPRISE (enterprise)
```

Exit codes confirmed: 0 for a valid key, 1 for an invalid one.

New coverage: `tests/test_license_activate_contract.py` — 7 offline tests
pinning the wire contract (URL, `key` field name, `valid:false` rejection, 400
handling, `--cloud-url` override, and a guard that the default URL is never a
pitchtoship host), plus one **live** test gated on `CUTCTX_LIVE_LICENSE_KEY`
that asserts the endpoint returns JSON with `valid: true`. All 8 pass with a
real key. The live test is the class of test that was missing.

## Still outstanding

1. **Seat checkout and trial are still unrepointed.**
   `cutctx_ee/billing/client.py` continues to call `/v1/license/checkout-seat`,
   `/v1/license/start-trial`, `/v1/license/check-trial`, and
   `/v1/license/crl` against `pitchtoship.com`, and
   `cutctx/telemetry/reporter.py:140` still calls `/v1/license/validate`. The
   Supabase equivalents appear to be `seat-heartbeat`, `my-licenses`, and
   `list-plans`, but I did not verify their contracts, so I have not guessed at
   the mapping.
2. **`is_revoked()` has no Supabase equivalent identified.** There is no
   published CRL function among the seven; revocation may be expressed as a
   status column on the `licenses` table instead. Decide the model before
   wiring it, since strict mode fails closed.
3. **Gate release on the live contract test** so this cannot regress silently.

## Why prior audits missed it

Every licence test in the repo mocks the portal
(`cutctx_ee/tests/test_billing_client.py`, `cutctx_ee/tests/test_license_e2e.py`),
so the suite is green while activation is broken in production. The mocks encode
the `/v1/license/*` contract the server never implemented — mocked-only coverage
of a paid, network-dependent flow is the root cause of the blind spot.

---

*No licence keys are recorded in this document. Verification passed keys through
environment variables only.*
