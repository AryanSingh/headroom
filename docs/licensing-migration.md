# Cutctx Licensing Migration

With the release of Cutctx Enterprise, we have introduced a robust licensing mechanism based on Ed25519 tokens.

## Migration Steps for Existing Users

1. Generate a new license token through your current commercial licensing workflow.
2. Update your `cutctx.toml` or set the `CUTCTX_LICENSE_KEY` environment variable with your new token.
3. Ensure that your proxy can reach the configured hosted license service (`PITCHTOSHIP_URL` / `CUTCTX_LICENSE_API_URL`) to validate the license and fetch the Certificate Revocation List (CRL).

## New Features

- **Seat Leases:** Centralized tracking for seat-based licensing.
- **Server-Side Trials:** 14-day trials are now validated through the hosted licensing workflow.
- **Offline Tolerance:** The proxy caches the CRL locally and fails open during temporary network outages.
