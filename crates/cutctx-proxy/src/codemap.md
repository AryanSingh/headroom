# crates/cutctx-proxy/src/

## Responsibility
Implements proxy process lifecycle, shared state/router construction, transparent forwarding, provider adapters, compression dispatch, cache stabilization, policy/licensing, and observability.

## Design
`main.rs` is the composition root; `lib.rs` exposes modules and panic-hook setup; `proxy.rs` owns `AppState`, router assembly, and generic HTTP/WebSocket forwarding. Child modules isolate provider formats and cross-cutting concerns. Configuration and typed errors are centralized.

## Flow
CLI config -> initialize clients/stores/credentials/tasks -> build Axum router -> classify request and attach model/auth state -> dispatch specialized or generic handler -> stabilize/compress/sign/forward -> tee/parse response metrics without perturbing wire bytes.

## Integration
- Child maps: `bedrock/`, `cache_stabilization/`, `compression/`, `handlers/`, `license/`, `observability/`, `policy/`, `sse/`, and `vertex/`.
- Root modules also handle headers, health, protection, Responses item traversal, WebSockets, config, and errors.
