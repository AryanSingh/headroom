# cutctx/providers/openclaw/

## Responsibility
Installs and wraps OpenClaw so model calls pass through CutCtx.

## Design
The installer performs idempotent config changes; wrapper injects proxy/model environment.

## Flow
Setup applies managed routes, then wrapped commands launch OpenClaw against CutCtx.

## Integration
Integrates with OpenClaw files/plugins and compatible proxy endpoints.
