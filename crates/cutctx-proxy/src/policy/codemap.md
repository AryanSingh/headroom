# crates/cutctx-proxy/src/policy/

## Responsibility
Fetches, caches, and applies remote organizational policy used to constrain proxy behavior.

## Design
Typed policy documents and decisions live in `mod.rs`; `client.rs` encapsulates HTTP retrieval, authentication, cache/refresh behavior, and failure handling. Enforcement remains separate from transport handlers.

## Flow
Proxy obtains policy for its tenant/identity -> client refreshes or serves cached state -> request/config paths evaluate rules -> deny, limit, or permit behavior is surfaced through typed decisions and logs.

## Integration
- Consumed by proxy configuration and request feature gates.
- Connects to the configured policy service via the shared HTTP runtime.
