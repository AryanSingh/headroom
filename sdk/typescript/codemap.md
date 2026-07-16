# sdk/typescript/

## Responsibility
Publishes the `cutctx-ai` TypeScript/JavaScript SDK for direct compression, proxy administration, provider client wrapping, streaming, hooks, shared context, simulation, and hosted compression.

## Design
`src/index.ts` is the stable export facade. `CutctxClient` groups OpenAI/Anthropic passthrough and operational sub-APIs over one retrying/authenticated fetch layer. Standalone `compress` and `simulate` functions offer lightweight entry points; typed models/config, adapters, utilities, hooks, and filesystem path parity are separate modules.

## Flow
Consumer calls a top-level helper/client/adaptor -> messages are detected/normalized and snake-cased -> HTTP request reaches local or hosted Cutctx -> errors/retries/fallback are resolved -> JSON is camel-cased or SSE returned as an async generator.

## Integration
- Consumed by Node/browser applications and repository plugins such as OpenCode and OpenClaw.
- Builds ESM/CJS/type declarations with tsup and relies on standard `fetch`/Web Streams.
