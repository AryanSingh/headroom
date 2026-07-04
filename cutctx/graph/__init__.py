"""Code graph intelligence for cutctx.

Provides live code graph reindexing via file watching, with
codebase-memory-mcp as the graph backend.

Also provides optional Graphify knowledge-graph compression:
    GraphifyIndexer  — builds and caches graph.json in background
    GraphifyIndex    — loaded graph with BFS query API
    graphify_available() — runtime availability check

Also provides stack-graph-based code navigation:
    StackGraphResolver  — wraps the Rust StackGraphManager for cross-file
                          symbol resolution
    stack_graph_available() — runtime availability check
"""

from cutctx.graph.graphify import (
    GraphifyIndex,
    GraphifyIndexer,
    GraphifyQueryResult,
    GraphNode,
    get_global_indexer,
    graphify_available,
    render_subgraph,
    set_global_indexer,
)
from cutctx.graph.resolver import StackGraphResolver, stack_graph_available
