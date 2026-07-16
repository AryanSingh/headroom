# cutctx/providers/cursor/

## Responsibility
Installs and runs Cursor with CutCtx proxy integration.

## Design
Provider configuration is isolated in the installer while runtime remains a thin wrapper.

## Flow
Setup applies managed endpoint values; runtime launches Cursor with proxy-aware settings.

## Integration
Registered with provider setup and connects Cursor model traffic to proxy handlers.
