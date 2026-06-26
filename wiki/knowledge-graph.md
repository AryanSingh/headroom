# Knowledge Graph Compression (Graphify)

Cutctx's knowledge graph integration uses **Graphify** (MIT, Tree-sitter + NetworkX + Leiden clustering) to build a queryable semantic graph of your codebase. When the LLM reads a file or runs a code search, the graph interceptor returns a compact **BFS subgraph** (~15 tokens/node) instead of raw file content (~800+ tokens/file), achieving **up to 71.5× token reduction** on codebase queries.

## Overview

### The Problem

Cutctx compresses each tool output **in isolation** — per-blob AST slicing, log sampling, JSON encoding. But a file read of `auth/service.py` produces ~800+ tokens of raw code. For the LLM, most of that is boilerplate: the only semantically relevant information is that `AuthService.login()` calls `UserRepository.find_by_email()` — which can be expressed in ~15 tokens.

### What Graphify Adds

Graphify builds a **cross-file, semantic layer**: a knowledge graph of your codebase where nodes are functions, classes, modules, and concepts, and edges represent relationships (calls, contains, inherits from, etc.). When the LLM reads a file, Cutctx:

1. **Extracts query intent** from the tool input (file path, grep query, glob pattern)
2. **Finds seed nodes** in the graph matching the query
3. **Runs BFS** from the seeds to collect relevant context
4. **Returns a compact subgraph** — "here's what's relevant" — instead of raw file content

### Architecture

```
Proxy startup:
┌─────────────────────┐
│  GraphifyIndexer    │  Background thread
│  (graphify.py)      │
│                     │
│  ┌───────────────┐  │  Checks graphify-out/graph.json
│  │  graphifyy    │  │  If stale/missing: runs graphify build
│  │  (subprocess) │─│─┼─► graphify-out/graph.json
│  └───────────────┘  │  Loaded into memory as GraphifyIndex
└──────────┬──────────┘
           │
           ▼
┌──────────────────────┐
│  GraphifyIndex       │  In-memory NetworkX graph
│  (graphify.py)       │
│                      │
│  query_subgraph(     │  BFS from seed terms + degree sort
│    seed_terms,       │
│    bfs_depth=2,      │
│    max_nodes=40,     │
│  ) → GraphifyQueryResult
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────┐
│  GraphifyInterceptor         │  ToolResultInterceptor
│  (graph_interceptor.py)      │
│                              │
│  matches(): Read/Glob/Grep   │
│  transform():                │
│    1. Extract seed terms     │
│    2. Query subgraph         │
│    3. Render compact output  │
│    4. Never enlarge          │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  render_subgraph()           │
│                              │
│  [KNOWLEDGE GRAPH — N nodes] │
│  ## Relevant Nodes           │
│  [FUNC] login                │
│    → Handles user login     │
│  [CLASS] AuthService         │
│  ## Relationships            │
│  login → calls → UserRepo   │
└──────────────────────────────┘
```

### Progressive Disclosure

| First Read | Second Read (same file) |
|------------|------------------------|
| `Read auth/service.py` → subgraph (15 tokens) | `Read auth/service.py` → full file passes through |
| LLM sees the graph context, decides if it needs details | AstGrepInterceptor provides code outline as next layer |

The progressive disclosure key is `"graphify:<file_path>"`. Once the LLM has seen a subgraph for a file and asks for more detail, the interceptor steps aside and lets other compressors handle it.

## Activation

### CLI Flag

```bash
cutctx proxy --knowledge-graph

# With custom depth and node limit
cutctx proxy --knowledge-graph --knowledge-graph-bfs-depth 3 --knowledge-graph-max-nodes 60
```

### Environment Variables

```bash
CUTCTX_KNOWLEDGE_GRAPH=1 cutctx proxy
CUTCTX_KG_BFS_DEPTH=3 CUTCTX_KG_MAX_NODES=60 cutctx proxy
```

### Python API

```python
from cutctx.graph.graphify import GraphifyIndexer, GraphifyIndex

# Build or load the graph
indexer = GraphifyIndexer(project_dir="/path/to/project")
indexer.start()

# Query
index = indexer.get_index()  # None if not yet built
if index:
    result = index.query_subgraph(
        seed_terms=["AuthService", "login"],
        bfs_depth=2,
        max_nodes=40,
    )
    print(f"Found {len(result.nodes)} nodes, {len(result.edges)} edges")
```

## Configuration

### ProxyConfig Fields

| Field | Default | Description |
|-------|---------|-------------|
| `knowledge_graph_enabled` | `False` | Enable knowledge-graph compression |
| `knowledge_graph_bfs_depth` | `2` | BFS depth for subgraph queries |
| `knowledge_graph_max_nodes` | `40` | Max nodes per subgraph response |
| `knowledge_graph_min_chars` | `800` | Min output size (chars) before interception |
| `knowledge_graph_output_dir` | `"graphify-out"` | Directory for graph.json output |

### CLI Options

| Flag | Env Var | Default | Description |
|------|---------|---------|-------------|
| `--knowledge-graph` | `CUTCTX_KNOWLEDGE_GRAPH` | — | Enable knowledge-graph compression |
| `--knowledge-graph-bfs-depth` | `CUTCTX_KG_BFS_DEPTH` | `2` | BFS depth (1–10) |
| `--knowledge-graph-max-nodes` | `CUTCTX_KG_MAX_NODES` | `40` | Max nodes per response (5–200) |

### GraphifyIndexer Configuration

```python
from cutctx.graph.graphify import GraphifyIndexer

indexer = GraphifyIndexer(
    project_dir="/path/to/project",
    output_dir="graphify-out",
    max_age_seconds=3600,  # Rebuild after 1 hour
)
indexer.start()
```

The indexer runs a background thread that:
- Loads existing `graph.json` if fresh (< 1 hour old)
- Builds a new graph via `graphifyy` if stale or missing
- Refreshes with a 5-second debounce on file changes

## Requirements

### Dependency

```bash
# Install with knowledge-graph support
pip install cutctx-ai[knowledge-graph]

# Development
uv sync --extra dev --extra knowledge-graph
```

The `knowledge-graph` extra installs:
- `graphifyy>=3.0.0` — Graphify knowledge graph builder (MIT)
- `networkx>=3.0` — Graph data structure and BFS
- `cutctx-ai[proxy]` — Proxy server (transitive)

### First Build

On first run, building the knowledge graph takes ~30 seconds for a medium-sized project. The proxy does this in a background thread — startup is non-blocking. The cached graph is reused across restarts.

## Usage

### Subgraph Output Format

When the interceptor activates, the Bash/Read/Glob/Grep tool output is replaced with:

```
[KNOWLEDGE GRAPH]

## Relevant Nodes
  **auth/service.py:**
    [FUNC] AuthService.login — Handles user login, validates credentials, returns JWT token.
    [CLASS] AuthService — Auth service class with OAuth2 and JWT support
  **db/repos.py:**
    [CLASS] UserRepository — ORM wrapper for users table.

## Relationships
  AuthService.login —[calls]--> UserRepository.find_by_email
  AuthService —[contains]--> AuthService.login
```

Each node is represented as:
- `[TYPE]` prefix: `[FUNC]`, `[CLASS]`, `[MOD]`, `[CONCEPT]`, `[FILE]`
- Node label (function/class name)
- File path and community ID
- LLM-extracted summary (truncated to 120 chars)

Relationships are capped at 30 edges per response.

### With Read Tool

```
User: Read src/auth/service.py

Proxy intercepts → replaces with:
[KNOWLEDGE GRAPH — 8 nodes, BFS depth 2, seeds: auth, service]

## Relevant Nodes
  **auth/service.py:**
    [FUNC] login — Handles user login, validates credentials
    [CLASS] AuthService — Auth service class
    [FUNC] logout — Clears user session
  **db/repos.py:**
    [CLASS] UserRepository — ORM for users table
  **models/user.py:**
    [CLASS] User — User domain model

## Relationships
  AuthService.login —[calls]--> UserRepository.find_by_email
  AuthService —[contains]--> AuthService.login
  AuthService.login —[raises]--> AuthError

[Full content available: use Read tool with explicit start_line/end_line]
```

User reads the same file again → full content passes through.

### With Grep Tool

```
User: Grep for "login" in src/

Proxy intercepts → replaces with:
[KNOWLEDGE GRAPH — 5 nodes, BFS depth 2, seeds: login]

## Relevant Nodes
  **auth/service.py:**
    [FUNC] login — Handles user login, validates credentials
    [CLASS] AuthService — Auth service class
  **routes/auth.py:**
    [FUNC] handle_login — POST /login route handler
```

### Background Indexing

```python
from pathlib import Path
from cutctx.graph.graphify import GraphifyIndexer, set_global_indexer

# Create and start the indexer
indexer = GraphifyIndexer(
    project_dir=Path.cwd(),
    output_dir="graphify-out",
)
indexer.start()

# Check if index is ready
index = indexer.get_index()
if index:
    print(f"Graph ready: {index.node_count} nodes, {index.edge_count} edges")
else:
    print("Graph building in background...")

# Schedule refresh (used by file watcher)
indexer.schedule_refresh()

# Stop on shutdown
indexer.stop()
```

## Verification

### Check Graph Availability

```bash
python -c "
from cutctx.graph.graphify import graphify_available, networkx_available
print('graphifyy available:', graphify_available())
print('networkx available:', networkx_available())
"
```

### Manual Graph Query

```bash
python -c "
import json
from pathlib import Path
from cutctx.graph.graphify import GraphifyIndex

index = GraphifyIndex.load(Path('graphify-out/graph.json'))
print(f'Graph: {index.node_count} nodes, {index.edge_count} edges')

result = index.query_subgraph(['main'], bfs_depth=2, max_nodes=10)
print(f'Query: {len(result.nodes)} nodes, {len(result.edges)} edges')
for node in result.nodes:
    print(f'  [{node.node_type}] {node.label} ({node.file_path})')
"
```

### Run Tests

```bash
# Unit tests for graph index
pytest tests/test_graphify_index.py -v

# Interceptor tests (if they exist)
pytest tests/test_graph_interceptor.py -v
```

### Verify CLI Flags

```bash
cutctx proxy --help | grep -A3 "knowledge-graph"
# Must show: --knowledge-graph, --knowledge-graph-bfs-depth, --knowledge-graph-max-nodes
```

### Check Proxy Startup Logs

```bash
cutctx proxy --knowledge-graph --log-level debug 2>&1 | grep -i "knowledge\|graph"
# Expected: "Knowledge graph: interceptor registered (bfs_depth=2, max_nodes=40)"
```

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| Interceptor never activates | graphifyy not installed | `pip install cutctx-ai[knowledge-graph]` |
| Graph not ready | First build still running | Wait ~30s for background build |
| Empty subgraph (fallback = True) | No matching nodes found | The interceptor shows top-degree "god" nodes as context |
| `graphify_available()` = False | graphifyy package missing | Install `graphifyy>=3.0.0` |
| `networkx_available()` = False | networkx missing | `pip install networkx>=3.0` |
| Rendered output = original | Subgraph not smaller than original | This is by design — the interceptor never enlarges |
| BFS too broad | `bfs_depth` too high | Lower `--knowledge-graph-bfs-depth` to 1 or 2 |
| Too many nodes returned | Graph is densely connected | Lower `--knowledge-graph-max-nodes` |

### Design Notes

- **Never enlarges**: If the rendered subgraph is not strictly shorter than the original content, `transform()` returns `None` and the original content passes through.
- **Background indexing**: The first build runs asynchronously. The interceptor only activates once the index is ready.
- **Debounced refresh**: File changes trigger a 5-second debounced rebuild via `schedule_refresh()`.
- **Thread-safe reads**: `GraphifyIndex` uses `threading.RLock` for concurrent read access.
- **Multiple indexers**: Each worker process has its own `GraphifyIndexer` — no cross-process state sharing.
- **Extensible seed extraction**: The interceptor extracts seed terms from file paths, grep queries, glob patterns, and command strings — it adapts to the tool being used.

---

## See Also

- [Transforms Reference](transforms.md) — Other compression transforms
- [Compression Overview](compression.md) — Universal compression
- [Filesystem Contract](filesystem-contract.md) — Config/workspace paths
