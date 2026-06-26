"""Cutctx integrations with popular LLM frameworks.

Available integrations:

LangChain (pip install cutctx[langchain]):
    - CutctxChatModel: Drop-in wrapper for any LangChain chat model
    - CutctxChatMessageHistory: Automatic conversation compression
    - CutctxDocumentCompressor: Relevance-based document filtering
    - CutctxToolWrapper: Tool output compression for agents
    - StreamingMetricsTracker: Token counting during streaming
    - CutctxLangSmithCallbackHandler: LangSmith trace enrichment

Agno (pip install agno):
    - CutctxAgnoModel: Drop-in wrapper for any Agno model
    - CutctxPreHook/CutctxPostHook: Agent-level hooks for tracking
    - create_cutctx_hooks: Convenience function to create hook pairs

LlamaIndex (pip install cutctx-ai[llamaindex]):
    - CutctxNodePostprocessor: drop-in NodePostprocessor for relevance filtering
      and optional compression of retrieved nodes

MCP (Model Context Protocol):
    - CutctxMCPCompressor: Compress MCP tool results
    - compress_tool_result: Simple function for tool compression

Example:
    # LangChain integration
    from cutctx.integrations import CutctxChatModel
    # or explicitly:
    from cutctx.integrations.langchain import CutctxChatModel

    # Agno integration
    from cutctx.integrations.agno import CutctxAgnoModel
    # or explicitly:
    from cutctx.integrations.agno import CutctxAgnoModel

    # LlamaIndex integration
    from cutctx.integrations.llamaindex import CutctxNodePostprocessor

    # MCP integration
    from cutctx.integrations import compress_tool_result
    # or explicitly:
    from cutctx.integrations.mcp import compress_tool_result
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
    get_cutctx_provider,
    get_model_name_from_langchain,
    get_tool_metrics,
    is_langsmith_available,
    is_langsmith_tracing_enabled,
    langchain_available,
    optimize_messages,
    reset_tool_metrics,
    track_async_streaming_response,
    track_streaming_response,
    wrap_tools_with_cutctx,
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
    create_cutctx_mcp_proxy,
)

# Re-export from agno subpackage (optional dependency)
try:
    from .agno import (
        CutctxAgnoModel,
        CutctxPostHook,
        CutctxPreHook,
        agno_available,
        create_cutctx_hooks,
        get_model_name_from_agno,
    )
    from .agno import OptimizationMetrics as AgnoOptimizationMetrics
    from .agno import get_cutctx_provider as get_agno_provider
    from .agno import optimize_messages as optimize_agno_messages

    _AGNO_AVAILABLE = True
except ImportError:
    _AGNO_AVAILABLE = False

# Re-export from llamaindex subpackage (optional dependency - pip install cutctx-ai[llamaindex])
try:
    from .llamaindex import (
        CutctxNodePostprocessor,
        NodeFilterMetrics,
    )

    _LLAMAINDEX_AVAILABLE = True
except ImportError:
    _LLAMAINDEX_AVAILABLE = False

__all__ = [
    # LangChain Core
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
    # MCP
    "CutctxMCPCompressor",
    "CutctxMCPClientWrapper",
    "MCPCompressionResult",
    "MCPToolProfile",
    "compress_tool_result",
    "compress_tool_result_with_metrics",
    "create_cutctx_mcp_proxy",
    "DEFAULT_MCP_PROFILES",
    # Agno
    "CutctxAgnoModel",
    "CutctxPreHook",
    "CutctxPostHook",
    "agno_available",
    "create_cutctx_hooks",
    "get_agno_provider",
    "get_model_name_from_agno",
    "AgnoOptimizationMetrics",
    "optimize_agno_messages",
    # LlamaIndex
    "CutctxNodePostprocessor",
    "NodeFilterMetrics",
]
