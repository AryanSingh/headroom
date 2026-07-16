# cutctx/ccr/

## Responsibility
Implements cache-control revalidation for tool results and long agent contexts.

## Design
Markers identify cacheable payloads; context trackers and stores retain state; injection/response handlers wrap model turns; batch components coalesce persistence.

## Flow
Tool output is marked and stored, later turns resolve markers, and response handling refreshes or invalidates entries. MCP exposes the same lifecycle.

## Integration
Integrates with proxy handlers, MCP clients, and durable local stores.
