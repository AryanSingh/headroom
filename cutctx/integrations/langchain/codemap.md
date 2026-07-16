# cutctx/integrations/langchain/

## Responsibility
Integrates compression, retrieval, memory, streaming, and tracing with LangChain/LangGraph.

## Design
Composable wrappers mirror chat-model, agent, retriever, memory, callback, and graph-node extension points.

## Flow
Messages/documents enter a wrapper, CutCtx compacts or enriches them, the native component executes, and metadata propagates.

## Integration
Depends on optional LangChain, LangGraph, and LangSmith; delegates to core compression/memory.
