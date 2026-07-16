# crates/cutctx-proxy/

## Responsibility
Builds the native Cutctx CLI/server: an Axum reverse proxy that compresses provider payloads while preserving HTTP, streaming, authentication, and cache semantics.

## Design
The binary parses configuration and initializes credentials, licensing, CCR, tracing, and shared state; the library builds a router over provider-specific handlers. Transport-independent transforms remain in `cutctx-core`, while this crate owns provider envelopes, forwarding, SSE/WebSocket paths, policy, metrics, and operational endpoints.

## Flow
Startup constructs `AppState` and routes -> inbound requests are classified and authorized -> bodies may be stabilized/compressed -> requests are signed or authenticated and forwarded -> responses stream or buffer back with metrics -> graceful shutdown drains work.

## Integration
- Depends on `cutctx-core`, Axum/Tokio/Reqwest, AWS/GCP auth, Prometheus/OpenTelemetry, and license services.
- Exposes OpenAI, Anthropic, Bedrock, Vertex, health, metrics, policy, and administrative endpoints.
