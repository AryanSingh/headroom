# Licensing Enforcement Design

## Outcome

Paid Cutctx capabilities must be enabled only by a current, verified license
entitlement. A locally supplied tier, missing validation response, corrupt
cache, expired trial, or unavailable seat must not grant a commercial feature.
Builder capabilities remain usable without a license.

## Boundary

The existing license authority (PitchToShip or a verified signed offline
token) remains the authority for commercial entitlement. This work does not
replace billing providers, pricing, checkout, or the public product catalogue.

## Design

### Entitlement activation

`ProxyConfig.entitlement_tier` is retained as an operator request for
backward-compatible configuration, but it is not evidence of a paid
entitlement. At proxy construction, entitlement starts at Builder unless a
trusted cached validation result is available. Startup validation may upgrade
to the returned active/trial plan. Invalid, expired, malformed, or unavailable
validation results leave the checker at Builder.

Paid components are initialized only after this decision. Components that are
enabled after startup must use the proxy's current checker, never raw config.

### License contract

License clients and the local validation route use the same JSON request and
response contract. Requests are `{ "license_key": "..." }`; successful
responses carry `status` (`active` or `trial`) and `plan`, with optional
organization, seat, expiry, and signed-token metadata. The local route can
normalize legacy `{valid, tier}` authority responses to this contract.

The machine-facing validation endpoint is not an administrative mutation.
Activation, CRL, seat allocation, and trial-management endpoints remain
admin/RBAC-gated. The validation endpoint accepts the configured license key
as a request body value and does not require an administrator credential that
the proxy cannot possess.

### Trial and seat enforcement

The proxy uses a single commercial-access decision before performing
commercial-only work. It denies paid capability use when a trial is expired or
a current validated license does not permit that capability. Seat checkout is
performed only for authenticated, identity-bearing commercial requests; the
current proxy has no universal user identity on provider traffic, so this pass
will enforce proxy-instance activation and preserve the seat API for an
identity-aware gateway rather than falsely treating anonymous requests as
seats.

Instance activation is limited by the licensed seat count at the authoritative
SQLite fallback store. Existing activation renewals remain idempotent.

### Offline behavior

Cached signed tokens are acceptable only when their signature and expiry have
been verified. A cache that is missing, malformed, or expired cannot elevate a
tier. The existing seven-day cached validation grace applies only to a prior
active/trial result and is never extended by a failed validation attempt.

## Verification

Tests must prove:

1. An unlicensed `entitlement_tier=business` configuration does not enable
   episodic memory.
2. A valid active Business result upgrades and enables the feature after
   startup validation; expired/invalid results retain Builder.
3. CLI/reporter JSON validation requests interoperate with the local route and
   normalize the result into `status` and `plan`.
4. Expired/invalid license states do not authorize commercial work.
5. Instance activation refuses a new instance after the licensed limit but
   permits idempotent renewal.
6. Existing management/entitlement, license, and relevant proxy test suites
   pass.
