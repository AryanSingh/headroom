# cutctx/memory/backends/

## Responsibility
Provides complete memory-engine strategies behind the public API.

## Design
Local, Mem0, direct-Mem0, and USEARCH implementations conform to shared backend behavior.

## Flow
The factory selects a backend; CRUD/search calls are normalized, delegated, and converted to CutCtx models.

## Integration
Used by easy APIs, MCP, and proxy injection; optional engines depend on Mem0 or USEARCH.
