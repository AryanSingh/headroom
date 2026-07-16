# crates/cutctx-proxy/src/license/

## Responsibility
Verifies license credentials and enforces machine binding, revocation, heartbeat/seat leases, and clock-rollback protections.

## Design
`mod.rs` maps signed tokens/keys to license tiers using cryptographic verification. `client.rs` activates instances, fetches and periodically refreshes CRLs, and checks out seats. `fingerprint.rs` derives stable machine identity and persists clock state.

## Flow
Startup fingerprints the install -> verifies/activates configured license -> loads CRL and checks revocation/binding -> background tasks refresh CRL and heartbeat leases -> feature gates consult the effective tier; invalid or stale state degrades safely.

## Integration
- Initialized by `main.rs` and consumed by config/policy/feature gates.
- Communicates with the configured Cutctx license API and uses core signature primitives plus Ed25519/HMAC/base64.
