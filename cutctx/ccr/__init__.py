"""CCR (Compress-Cache-Retrieve) public exports."""

from .batch_processor import (
    BatchResultProcessor,
    BatchResultProcessorConfig,
    ProcessedBatchResult,
    process_batch_results,
)
from .batch_store import (
    BatchContext,
    BatchContextStore,
    BatchRequestContext,
    get_batch_context_store,
    reset_batch_context_store,
)
from .context_tracker import (
    CompressedContext,
    ContextTracker,
    ContextTrackerConfig,
    ExpansionRecommendation,
    get_context_tracker,
    reset_context_tracker,
)
from .response_handler import (
    CCRResponseHandler,
    CCRToolCall,
    CCRToolResult,
    ResponseHandlerConfig,
    StreamingCCRBuffer,
    StreamingCCRHandler,
)
from .tool_injection import (
    CCR_TOOL_NAME,
    CCRToolInjector,
    create_ccr_tool_definition,
    create_system_instructions,
    parse_tool_call,
)

CCRStore = BatchContextStore

try:
    from .mcp_server import CutctxMCPServer, create_ccr_mcp_server

    MCP_SERVER_AVAILABLE = True
except ImportError:
    CutctxMCPServer = None  # type: ignore[assignment]
    create_ccr_mcp_server = None  # type: ignore[assignment]
    MCP_SERVER_AVAILABLE = False

__all__ = [
    "BatchContext",
    "BatchContextStore",
    "BatchRequestContext",
    "BatchResultProcessor",
    "BatchResultProcessorConfig",
    "CCRResponseHandler",
    "CCRStore",
    "CCRToolCall",
    "CCRToolInjector",
    "CCRToolResult",
    "CCR_TOOL_NAME",
    "CompressedContext",
    "ContextTracker",
    "ContextTrackerConfig",
    "CutctxMCPServer",
    "ExpansionRecommendation",
    "MCP_SERVER_AVAILABLE",
    "ProcessedBatchResult",
    "ResponseHandlerConfig",
    "StreamingCCRBuffer",
    "StreamingCCRHandler",
    "create_ccr_mcp_server",
    "create_ccr_tool_definition",
    "create_system_instructions",
    "get_batch_context_store",
    "get_context_tracker",
    "parse_tool_call",
    "process_batch_results",
    "reset_batch_context_store",
    "reset_context_tracker",
]
