"""MCP (Model Context Protocol) integration for Cutctx.

This package provides compression utilities for MCP tool results,
helping reduce context usage when tools return large outputs.

Example:
    from cutctx.integrations.mcp import compress_tool_result

    # Compress large tool output
    result = compress_tool_result(
        tool_name="search",
        result=large_json_result,
        max_chars=5000,
    )

Imports are lazy (PEP 562): the compressor stack pulls in providers and
telemetry, but lightweight consumers — notably ``cutctx mcp gateway``,
which starts once per wrapped MCP server — must not pay that cost just
for importing the package.
"""

from typing import Any

__all__ = [
    "CutctxMCPCompressor",
    "CutctxMCPClientWrapper",
    "MCPCompressionResult",
    "MCPToolProfile",
    "compress_tool_result",
    "compress_tool_result_with_metrics",
    "create_cutctx_mcp_proxy",
    "DEFAULT_MCP_PROFILES",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import server

        return getattr(server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
