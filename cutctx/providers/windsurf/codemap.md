# cutctx/providers/windsurf/

## Responsibility
Launches Windsurf with CutCtx routing configuration.

## Design
A runtime adapter centralizes discovery, environment construction, and process lifecycle.

## Flow
The wrapper resolves the proxy, augments launch environment, starts Windsurf, and returns status.

## Integration
Used by provider wrap commands and connects model traffic to compatible endpoints.
