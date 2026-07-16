# cutctx/providers/zed/

## Responsibility
Launches Zed with CutCtx-compatible model routing.

## Design
A runtime adapter owns Zed-specific environment and command construction.

## Flow
The wrapper resolves proxy settings, launches Zed, and propagates completion status.

## Integration
Used by provider setup/wrapping and integrates Zed assistant traffic with CutCtx.
