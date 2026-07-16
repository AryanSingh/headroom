# cutctx/memory/adapters/

## Responsibility
Implements storage, retrieval, embedding, graph, and cache ports for memory.

## Design
Adapters follow `memory.ports`: SQLite/FTS5, vector/HNSW, graph, caching, and embedding strategies.

## Flow
Core services persist normalized records, build indexes, and combine text, vector, and graph results.

## Integration
Consumed by memory factories/storage routing; integrates with SQLite and optional vector libraries.
