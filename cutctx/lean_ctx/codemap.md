# cutctx/lean_ctx/

## Responsibility
Installs and configures Lean Context compatibility for agent environments.

## Design
A focused installer detects current state, verifies platform-pinned release digests through the shared safe archive installer, and applies idempotent configuration updates.

## Flow
It locates host configuration, applies bridge settings, and reports installation state.

## Integration
Called from setup/integration CLI and writes provider-local settings pointing to CutCtx.
