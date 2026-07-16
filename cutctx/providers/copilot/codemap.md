# cutctx/providers/copilot/

## Responsibility
Configures and wraps GitHub Copilot clients for CutCtx-assisted routing.

## Design
An installer manages host configuration while the wrapper resolves auth and process environment.

## Flow
Setup detects Copilot and applies settings; launches route eligible calls through CutCtx.

## Integration
Uses Copilot credential helpers/provider registry and compatible proxy routes.
