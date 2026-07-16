# crates/cutctx-proxy/src/sse/

## Responsibility
Frames, parses, observes, and optionally incrementally compresses Anthropic and OpenAI server-sent event streams without breaking streaming semantics.

## Design
`framing.rs` is a byte-tolerant SSE state machine. Provider modules interpret Anthropic, Chat Completions, and Responses events into bounded stream state. `StreamingCompressor` can modify text deltas after a threshold while passing metadata events through; tee-based observers avoid blocking the wire path.

## Flow
Upstream byte chunks pass immediately toward the client and into a bounded parser tee -> framer emits events -> provider state accumulates usage/status/tool data -> optional compressor rewrites eligible text events -> close emits summary metrics.

## Integration
- Used by generic proxy forwarding, handlers, Bedrock translation, and Vertex streaming.
- Reports to `observability/` and uses core deletion/token logic for incremental compression.
