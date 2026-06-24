"""Code graph intelligence for headroom.

Provides live code graph reindexing via file watching, with
codebase-memory-mcp as the graph backend.

Also provides optional Graphify knowledge-graph compression:
    GraphifyIndexer  — builds and caches graph.json in background
    GraphifyIndex    — loaded graph with BFS query API
    graphify_available() — runtime availability check
"""
from headroom.graph.graphify import (
    GraphifyIndex,
    GraphifyIndexer,
    GraphifyQueryResult,
    GraphNode,
    get_global_indexer,
    graphify_available,
    render_subgraph,
    set_global_indexer,
)
