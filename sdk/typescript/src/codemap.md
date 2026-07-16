# sdk/typescript/src/

## Responsibility
Implements the TypeScript SDK's public facade, HTTP clients, compression/simulation helpers, lifecycle hooks, shared context, path contracts, errors, types, provider adapters, and serialization utilities.

## Design
`index.ts` re-exports the supported API. `client.ts` is a facade over proxy/provider/metrics/retrieve/telemetry endpoints; `compress.ts` is the minimal operation with fallback; `hosted.ts` targets managed compression. `CompressionHooks` provides observer callbacks, and `SharedContext` is a bounded TTL key-value context store.

## Flow
Inputs pass through format/case conversion -> request helpers attach config/auth/timeout and call Cutctx -> status maps to the error hierarchy -> responses become typed camel-case models or SSE iterators -> hooks observe start/success/error events.

## Integration
- Child maps cover `adapters/`, `types/`, and `utils/`.
- Used by the package entry point, examples, plugins, and applications across Node and browser-compatible fetch runtimes.
