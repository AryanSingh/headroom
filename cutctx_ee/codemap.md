# cutctx_ee/

## Responsibility
Provides proprietary multi-tenant governance, billing, policy, audit, ledger, identity, retention, and memory-service extensions.

## Design
Top-level facades implement org/RBAC/SSO/SCIM/seats/trials/retention/abuse/release-marker/entitlements, while child packages isolate audit, billing, usage ledger, tenant memory, and signed policy services. The package is designed for optional loading by the OSS runtime.

## Flow
The proxy detects enterprise availability, authenticates tenant/admin operations, resolves entitlements/policy, executes metered requests, and records audit/ledger state; lifecycle APIs manage organizations, identities, seats, retention, and licenses.

## Integration
Loaded dynamically by core proxy routes and CLI so OSS remains functional without it; integrates external identity/billing systems, enterprise stores, security controls, and child service packages.

## Release-marker boundary

`watermark.py` only serializes/parses existing `CTXWM:` release markers and
verifies supplied license IDs against an explicit local SQLite database. It
does not modify package source or scan binaries. Release engineering owns any
signed manifest creation and artifact forensics outside the runtime package.
