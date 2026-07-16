# cutctx/providers/antigravity/

## Responsibility
Launches Antigravity-compatible clients with CutCtx routing enabled.

## Design
A runtime adapter constructs provider-specific environment and command while preserving client semantics.

## Flow
The wrapper resolves proxy settings, augments environment, starts the client, and propagates status.

## Integration
Used by provider wrap/install CLI and connects traffic to the local proxy.
