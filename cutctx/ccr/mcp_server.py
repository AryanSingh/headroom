"""Backward-compatible CCR MCP exports.

The standalone MCP server implementation now lives in ``cutctx.mcp_server``.
Older code and tests still import ``cutctx.ccr.mcp_server`` directly, so this
module re-exports the shared event helpers and server factory from the new
location.
"""

from cutctx.mcp_server import (
    CCR_TOOL_NAME,
    SHARED_STATS_FILE,
    _HAS_FCNTL,
    CutctxMCPServer,
    create_ccr_mcp_server,
    _append_shared_event,
    _read_shared_events,
)

__all__ = [
    "CCR_TOOL_NAME",
    "SHARED_STATS_FILE",
    "_HAS_FCNTL",
    "CutctxMCPServer",
    "create_ccr_mcp_server",
    "_append_shared_event",
    "_read_shared_events",
]
