# cutctx_ee/policy/

## Responsibility
Stores, signs, resolves, and serves enterprise policy bundles.

## Design
Typed policy models, durable store, signer, resolver, and API implement a signed configuration repository with scoped precedence.

## Flow
Administrators publish signed policies; requests resolve org/project/user precedence, verify signatures, and return the effective policy.

## Integration
Consumed by proxy policy/routing/security decisions and orchestration; emits audit events and relies on enterprise identity/storage.
