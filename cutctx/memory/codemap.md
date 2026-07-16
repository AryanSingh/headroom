# cutctx/memory/

## Responsibility
Implements hierarchical long-term memory extraction, storage, retrieval, synchronization, and prompt injection.

## Design
Ports and typed models define boundaries; factories/storage routing select child backend/adapters; hierarchical core and budgeting rank context; extractors derive memories; bridges, wrappers, writers, MCP, and sync expose them to agents. Child packages own persistence engines, port adapters, sync readers, and provider writers.

## Flow
Conversation/tool traffic is tracked and extracted into normalized records, persisted/indexed via selected stores, queried and ranked under a token budget, then injected or written into agent context; sync and export provide external lifecycle paths.

## Integration
Used by proxy memory decisions/handlers, CLI, MCP, integrations, and observability. Integrates with SQLite/vector/graph/Mem0 engines and provider histories/config via child packages.
