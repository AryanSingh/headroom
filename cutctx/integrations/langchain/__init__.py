"""LangChain integration for Cutctx.

This package provides seamless integration with LangChain, including:
- CutctxChatModel: Drop-in wrapper for any LangChain chat model
- CutctxChatMessageHistory: Automatic conversation compression
- CutctxDocumentCompressor: Relevance-based document filtering
- CutctxToolWrapper: Tool output compression for agents
- StreamingMetricsTracker: Token counting during streaming
- CutctxLangSmithCallbackHandler: LangSmith trace enrichment
- compress_tool_messages: LangGraph pre-model hook for ToolMessage compression
- create_compress_tool_messages_node: LangGraph node factory

Example:
    from langchain_openai import ChatOpenAI
    from cutctx.integrations.langchain import CutctxChatModel

    # Wrap any LangChain model
    llm = CutctxChatModel(ChatOpenAI(model="gpt-4o"))

    # Use like normal - optimization happens automatically
    response = llm.invoke("Hello!")

Install: pip install cutctx[langchain]
"""

# Agent tool wrapping
from .agents import (
    CutctxToolWrapper,
    ToolCompressionMetrics,
    ToolMetricsCollector,
    get_tool_metrics,
    reset_tool_metrics,
    wrap_tools_with_cutctx,
)

# Core chat model wrapper
from .chat_model import (
    CutctxCallbackHandler,
    CutctxChatModel,
    CutctxRunnable,
    OptimizationMetrics,
    langchain_available,
    optimize_messages,
)

# LangGraph integration
from .langgraph import (
    CompressToolMessagesConfig,
    CompressToolMessagesResult,
    ToolMessageCompressionMetrics,
    compress_tool_messages,
    create_compress_tool_messages_node,
)

# LangSmith integration
from .langsmith import (
    CutctxLangSmithCallbackHandler,
    is_langsmith_available,
    is_langsmith_tracing_enabled,
)

# Memory integration
from .memory import CutctxChatMessageHistory

# Provider auto-detection
from .providers import (
    detect_provider,
    get_cutctx_provider,
    get_model_name_from_langchain,
)

# Retriever integration
from .retriever import CompressionMetrics, CutctxDocumentCompressor

# Streaming metrics
from .streaming import (
    StreamingMetrics,
    StreamingMetricsCallback,
    StreamingMetricsTracker,
    track_async_streaming_response,
    track_streaming_response,
)

__all__ = [
    # Core
    "CutctxChatModel",
    "CutctxCallbackHandler",
    "CutctxRunnable",
    "OptimizationMetrics",
    "optimize_messages",
    "langchain_available",
    # Provider Detection
    "detect_provider",
    "get_cutctx_provider",
    "get_model_name_from_langchain",
    # Memory
    "CutctxChatMessageHistory",
    # Retrievers
    "CutctxDocumentCompressor",
    "CompressionMetrics",
    # Agents
    "CutctxToolWrapper",
    "ToolCompressionMetrics",
    "ToolMetricsCollector",
    "wrap_tools_with_cutctx",
    "get_tool_metrics",
    "reset_tool_metrics",
    # LangGraph
    "compress_tool_messages",
    "create_compress_tool_messages_node",
    "CompressToolMessagesConfig",
    "CompressToolMessagesResult",
    "ToolMessageCompressionMetrics",
    # LangSmith
    "CutctxLangSmithCallbackHandler",
    "is_langsmith_available",
    "is_langsmith_tracing_enabled",
    # Streaming
    "StreamingMetricsTracker",
    "StreamingMetricsCallback",
    "StreamingMetrics",
    "track_streaming_response",
    "track_async_streaming_response",
]
