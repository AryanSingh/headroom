# cutctx/providers/claude/

## Responsibility
Installs and launches Claude Code integration with CutCtx.

## Design
An idempotent installer owns Claude settings; a runtime wrapper supplies proxy/auth environment.

## Flow
Setup writes managed settings; wrapped launches direct Anthropic-compatible traffic through CutCtx.

## Integration
Integrates with Claude settings, credentials, MCP configuration, and Anthropic proxy handlers.
