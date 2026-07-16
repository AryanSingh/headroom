# cutctx/mcp_registry/

## Responsibility
Discovers, displays, installs, and tracks MCP registrations across agent hosts.

## Design
A registry adapter contract has Claude and Codex implementations; a ledger makes changes reversible and idempotent.

## Flow
Installation compares desired servers with host state/ledger, applies changes, persists results, and formats status.

## Integration
Used by MCP CLI and provider setup; reads and writes Claude/Codex MCP configuration.
