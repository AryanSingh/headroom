# cutctx/integrations/

## Responsibility
Adapts CutCtx to application frameworks and protocol hosts without changing their native contracts.

## Design
Framework-neutral ASGI and LiteLLM hooks coexist with child adapters for Agno, LangChain/LangGraph, LlamaIndex, MCP, and Strands. Wrappers use Decorator/Adapter patterns around native lifecycle hooks.

## Flow
Native messages/documents enter an adapter, are normalized and compressed or enriched, the wrapped framework component executes, and streaming/result metadata is translated back.

## Integration
Depends on optional framework packages and core compression/memory/savings services; child maps document each integration family.
