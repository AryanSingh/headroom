# Licensing Enforcement Verification — 2026-07-22

## Implemented controls

1. The proxy now initializes commercial entitlements at Builder. A supplied
   `CUTCTX_ENTITLEMENT_TIER` is logged as a request but cannot start a paid
   component. Only a validated active/trial result can upgrade the runtime
   checker.
2. The local validation endpoint accepts the JSON payload used by the CLI and
   usage reporter and normalizes authority responses to `status` and `plan`.
   License management mutations remain administrator/RBAC-gated.
3. The local SQLite fallback authority limits proxy-instance activations to
   the licensed seat count and renews an existing activation idempotently.
4. Strict revocation mode now denies commercial access when no fresh CRL can
   be fetched; development may explicitly select the existing non-strict mode.
5. Paid provider traffic now requires a signed `X-Cutctx-User-Token`, bound to
   the configured license and a non-expired user subject, before a seat lease
   is renewed. The user-token verifier is configured with
   `CUTCTX_USER_TOKEN_HMAC_SECRET`.

## Verification command

```sh
pytest -q tests/test_entitlement_request_path.py \
  tests/test_management_api_entitlements.py \
  tests/test_license_validation_contract.py \
  cutctx_ee/tests/test_license_e2e.py \
  cutctx_ee/tests/test_license_db.py \
  cutctx_ee/tests/test_billing_client.py \
  cutctx_ee/tests/test_pitchtoship_client.py \
  cutctx_ee/tests/test_seat_lease.py \
  cutctx_ee/tests/test_user_tokens.py
```

The focused suite collected 74 tests and completed with exit status 0 on
2026-07-22.

## Deliberate remaining boundary

User-scoped paid provider traffic is authenticated with a signed Cutctx token
in `X-Cutctx-User-Token`. Tokens must include a non-expired subject and the
configured license key, and are verified with `CUTCTX_USER_TOKEN_HMAC_SECRET`.
Anonymous traffic cannot access paid provider functionality.
