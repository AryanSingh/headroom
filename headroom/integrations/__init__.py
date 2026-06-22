"""Cutctx integrations with popular LLM frameworks.

Available integrations:

LangChain (pip install headroom[langchain]):
    - CutctxChatModel: Drop-in wrapper for any LangChain chat model
    - CutctxChatMessageHistory: Automatic conversation compression
    - CutctxDocumentCompressor: Relevance-based document filtering
    - CutctxToolWrapper: Tool output compression for agents
    - StreamingMetricsTracker: Token counting during streaming
    - CutctxLangSmithCallbackHandler: LangSmith trace enrichment

Agno (pip install agno):
    - CutctxAgnoModel: Drop-in wrapper for any Agno model
    - CutctxPreHook/HeadroomPostHook: Agent-level hooks for tracking
    - create_headroom_hooks: Convenience function to create hook pairs

LlamaIndex (pip install cutctx-ai[llamaindex]):
    - CutCtxNodePostprocessor: drop-in NodePostprocessor for relevance filtering
      and optional compression of retrieved nodes

MCP (Model Context Protocol):
    - CutctxMCPCompressor: Compress MCP tool results
    - compress_tool_result: Simple function for tool compression

Example:
    # LangChain integration
    from headroom.integrations import CutctxChatModel
    # or explicitly:
    from headroom.integrations.langchain import CutctxChatModel

    # Agno integration
    from headroom.integrations.agno import CutctxAgnoModel
    # or explicitly:
    from headroom.integrations.agno import CutctxAgnoModel

    # LlamaIndex integration
    from headroom.integrations.llamaindex import CutCtxNodePostprocessor

    # MCP integration
    from headroom.integrations import compress_tool_result
    # or explicitly:
    from headroom.integrations.mcp import compress_tool_result
"""

# Re-export from langchain subpackage for backwards compatibility
from .langchain import (
    # Retrievers
    CompressionMetrics,
    # Core
    CutctxCallbackHandler,
    # Memory
    CutctxChatMessageHistory,
    CutctxChatModel,
    CutctxDocumentCompressor,
    # LangSmith
    CutctxLangSmithCallbackHandler,
    CutctxRunnable,
    # Agents
    CutctxToolWrapper,
    OptimizationMetrics,
    # Streaming
    StreamingMetrics,
    StreamingMetricsCallback,
    StreamingMetricsTracker,
    ToolCompressionMetrics,
    ToolMetricsCollector,
    # Provider Detection
    detect_provider,
    get_headroom_provider,
    get_model_name_from_langchain,
    get_tool_metrics,
    is_langsmith_available,
    is_langsmith_tracing_enabled,
    langchain_available,
    optimize_messages,
    reset_tool_metrics,
    track_async_streaming_response,
    track_streaming_response,
    wrap_tools_with_headroom,
)

# Re-export from mcp subpackage for backwards compatibility
from .mcp import (
    DEFAULT_MCP_PROFILES,
    CutctxMCPClientWrapper,
    CutctxMCPCompressor,
    MCPCompressionResult,
    MCPToolProfile,
    compress_tool_result,
    compress_tool_result_with_metrics,
    create_headroom_mcp_proxy,
)

# Re-export from agno subpackage (optional dependency)
try:
    from .agno import (
        CutctxAgnoModel,
        CutctxPostHook,
        CutctxPreHook,
        agno_available,
        create_headroom_hooks,
        get_model_name_from_agno,
    )
    from .agno import OptimizationMetrics as AgnoOptimizationMetrics
    from .agno import get_headroom_provider as get_agno_provider
    from .agno import optimize_messages as optimize_agno_messages

    _AGNO_AVAILABLE = True
except ImportError:
    _AGNO_AVAILABLE = False

# Re-export from llamaindex subpackage (optional dependency - pip install cutctx-ai[llamaindex])
try:
    from .llamaindex import (
        CutCtxNodePostprocessor,
        NodeFilterMetrics,
    )

    _LLAMAINDEX_AVAILABLE = True
except ImportError:
    _LLAMAINDEX_AVAILABLE = False

__all__ = [
    # LangChain Core
    "HeadroomChatModel",
    "HeadroomCallbackHandler",
    "HeadroomRunnable",
    "OptimizationMetrics",
    "optimize_messages",
    "langchain_available",
    # Provider Detection
    "detect_provider",
    "get_headroom_provider",
    "get_model_name_from_langchain",
    # Memory
    "HeadroomChatMessageHistory",
    # Retrievers
    "HeadroomDocumentCompressor",
    "CompressionMetrics",
    # Agents
    "HeadroomToolWrapper",
    "ToolCompressionMetrics",
    "ToolMetricsCollector",
    "wrap_tools_with_headroom",
    "get_tool_metrics",
    "reset_tool_metrics",
    # LangSmith
    "HeadroomLangSmithCallbackHandler",
    "is_langsmith_available",
    "is_langsmith_tracing_enabled",
    # Streaming
    "StreamingMetricsTracker",
    "StreamingMetricsCallback",
    "StreamingMetrics",
    "track_streaming_response",
    "track_async_streaming_response",
    # MCP
    "HeadroomMCPCompressor",
    "HeadroomMCPClientWrapper",
    "MCPCompressionResult",
    "MCPToolProfile",
    "compress_tool_result",
    "compress_tool_result_with_metrics",
    "create_headroom_mcp_proxy",
    "DEFAULT_MCP_PROFILES",
    # Agno
    "HeadroomAgnoModel",
    "HeadroomPreHook",
    "HeadroomPostHook",
    "agno_available",
    "create_headroom_hooks",
    "get_agno_provider",
    "get_model_name_from_agno",
    "AgnoOptimizationMetrics",
    "optimize_agno_messages",
    # LlamaIndex
    "CutCtxNodePostprocessor",
    "NodeFilterMetrics",
]
