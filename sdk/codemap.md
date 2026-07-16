# sdk/

## Responsibility
Provides application-facing Cutctx clients and integration helpers for TypeScript, Go, and Python.

## Design
All SDKs wrap the HTTP proxy rather than embedding compression algorithms. TypeScript is the richest surface, with typed clients, hooks, adapters, streaming, simulation, and hosted compression; Go adds idiomatic clients, transports/middleware, memory, options, and shared context; Python supplies a small synchronous client and thread-safe shared context.

## Flow
Applications construct a language client -> messages or provider requests are serialized to proxy endpoints -> auth/config headers and timeouts are applied -> responses/streams are normalized into language-native models; optional fallback paths preserve original messages.

## Integration
- Targets the Cutctx `/v1/compress`, provider passthrough, retrieve, memory, health, stats, telemetry, and related endpoints.
- TypeScript adapters wrap OpenAI, Anthropic, Gemini, and Vercel AI clients; Go can intercept `http.RoundTripper` traffic.
