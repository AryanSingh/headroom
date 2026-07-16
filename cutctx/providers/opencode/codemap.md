# cutctx/providers/opencode/

## Responsibility
Installs the OpenCode CutCtx integration.

## Design
A Python installer manages configuration and deploys a JavaScript plugin for OpenCode hooks.

## Flow
Setup installs/updates plugin and config; subsequent sessions route eligible requests through CutCtx.

## Integration
Bridges OpenCode plugin/config APIs to proxy services.
