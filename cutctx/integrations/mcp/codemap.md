# cutctx/integrations/mcp/

## Responsibility
Exposes CutCtx operations as Model Context Protocol tools and resources.

## Design
A server adapter registers stable MCP schemas over compression, memory, and savings services.

## Flow
Clients invoke tools; the server validates arguments, delegates to core services, and serializes results.

## Integration
Used by MCP-capable hosts and protocol transports without embedding provider behavior.
