# plugins/openclaw/hook-shim/

## Responsibility
Provides the minimal callable hook module required by OpenClaw link/install workflows for a plugin whose real behavior is registered through the context-engine entry point.

## Design
`handler.js` exports an async no-op default function; it intentionally carries no compression or lifecycle state.

## Flow
Host invokes the compatibility hook -> handler resolves immediately -> primary plugin/context-engine execution continues through `src/plugin/`.

## Integration
- Packaged by OpenClaw distribution preparation.
- Complements, but does not replace, the main plugin registration entry point.
