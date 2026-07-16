# cutctx/providers/aider/

## Responsibility
Installs and runs Aider through the CutCtx proxy.

## Design
Installation owns config mutation; runtime builds the wrapped process environment.

## Flow
Setup detects Aider and writes managed settings; runtime launches it with traffic directed to CutCtx.

## Integration
Registered by provider installation; integrates with Aider config and proxy endpoints.
