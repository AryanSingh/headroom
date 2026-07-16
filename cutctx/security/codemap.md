# cutctx/security/

## Responsibility
Provides runtime hardening, request firewalling, secret protection, MFA, integrity checks, and residency evidence.

## Design
Independent services implement rule/ML firewall decisions, encrypted state/secrets, anti-debug controls, and signed proofs.

## Flow
Requests/admin actions pass checks before sensitive work; protected state is encrypted/signed and results drive allow/deny.

## Integration
Used by proxy middleware and enterprise routes; integrates with auth, policy, OS keys, and audit.
