# plugins/openclaw/src/plugin/

## Responsibility
Registers Cutctx capabilities with the OpenClaw host and wires runtime configuration to the context engine.

## Design
The default plugin factory adapts untyped host APIs to typed internal modules. It validates explicit proxy URLs, creates the engine/logger bridge, registers the context-engine factory and conditional retrieval tool, and installs proxy-ready/gateway-start routing callbacks.

## Flow
Read plugin config -> construct engine and provider-id selection -> register engine/tool -> ensure proxy availability -> when ready, update selected gateway provider base URLs -> log registration/routing outcomes.

## Integration
- OpenClaw entry point re-exported by `src/index.ts`.
- Depends on `engine.ts`, `proxy-manager.ts`, `gateway-config.ts`, and `tools/cutctx-retrieve.ts`.
