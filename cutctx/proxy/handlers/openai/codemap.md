# cutctx/proxy/handlers/openai/

## Responsibility
Implements OpenAI Chat Completions and Responses API handling, including Codex/ChatGPT subscription compatibility.

## Design
A shared mixin/base splits chat, responses, compression, passthrough, and utility concerns. Translators bridge Chat Completions and Responses schemas; websocket/SSE support, continuation safety, remote compaction passthrough, bounded interactive tool-output compression, tool namespace handling, and model-routing overrides preserve protocol semantics.

## Flow
Handlers authenticate/normalize a request, decide passthrough versus local transforms/routing, translate formats when needed, forward by HTTP or websocket, normalize streaming/non-streaming responses, and attach usage/savings metadata.

## Integration
Mixed into `CutctxProxy`; uses routing, compression, cache/memory, provider clients, streaming helpers, and OpenAI-compatible upstreams.
