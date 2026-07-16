# plugins/openclaw/src/

## Responsibility
Implements the OpenClaw plugin's public exports, context engine, proxy lifecycle, message conversion, gateway routing, host registration, and retrieval tool.

## Design
`index.ts` is the export facade. `engine.ts` implements OpenClaw's ContextEngine contract and owns compression statistics. `proxy-manager.ts` separates local launch from remote connect-only operation with URL validation/probing. `convert.ts` normalizes agent content; `gateway-config.ts` mutates selected provider base URLs in memory.

## Flow
Plugin creates engine -> engine bootstraps proxy -> assemble normalizes messages, invokes SDK compression with budget/model, and denormalizes results -> proxy readiness triggers gateway routing -> registered tool retrieves originals; errors fall back to normalized uncompressed messages.

## Integration
- Child maps cover `plugin/` and `tools/`.
- Consumed by the package facade and OpenClaw runtime; relies on Node child processes and the TypeScript SDK.
