# crates/cutctx-proxy/src/bedrock/

## Responsibility
Adapts Anthropic-style content inside Amazon Bedrock InvokeModel requests and responses, including authentication classification, SigV4 signing, and binary EventStream translation.

## Design
`BedrockEnvelope` preserves strict envelope fields/order around the inner message payload. Separate handlers cover invoke and invoke-with-response-stream; signing always occurs over final post-compression bytes. EventStream framing validates CRCs and translation can emit SSE-compatible events.

## Flow
Route extracts model/envelope -> attach auth mode -> compress inner Anthropic live zone -> re-emit envelope -> SigV4-sign outgoing bytes -> forward to Bedrock -> return JSON or parse binary EventStream and translate frames while recording stream state.

## Integration
- Routed from `proxy.rs`; uses startup AWS credentials and region config.
- Delegates content mutation to `compression/` and `cutctx-core`; feeds `sse/`/observability for streaming metrics.
