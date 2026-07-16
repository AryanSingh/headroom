# crates/cutctx-proxy/src/handlers/

## Responsibility
Implements native OpenAI-compatible Responses, Chat Completions, and Conversations endpoint behavior.

## Design
Each endpoint module owns request validation, item/message traversal, compression invocation, upstream forwarding, and response shape. `mod.rs` provides shared exports/helpers while `responses_items.rs` centralizes Responses item semantics.

## Flow
Axum extracts request/state -> handler validates endpoint schema and model -> compresses supported live-zone items -> forwards through shared client -> maps status/headers/body or streaming response back to the caller.

## Integration
- Registered by `proxy::build_app`.
- Uses `compression/`, `sse/`, shared header/error types, and configured OpenAI-compatible upstreams.
