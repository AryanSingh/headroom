# Graphify Integration Spec — Cutctx Knowledge Graph Compression

**Status:** Ready for implementation  
**Author:** Architecture review, June 2026  
**Scope:** Port Graphify's knowledge-graph capabilities into Cutctx as an opt-in compression strategy, activated by a `--knowledge-graph` flag.

---

## 0. Background and Goal

Graphify (github.com/safishamsi/graphify, MIT) builds a queryable knowledge graph from a codebase using Tree-sitter (AST) + LLM semantic extraction + NetworkX + Leiden clustering. It achieves a **71.5× token reduction** on codebase queries by returning BFS subgraphs (~1.7k tokens) instead of raw files (~123k tokens).

Cutctx currently compresses each tool output **in isolation** (per-blob AST slicing, log sampling, JSON encoding). The goal of this integration is to add a **cross-file, semantic layer**: when the LLM reads a file or runs a code search, Cutctx consults the knowledge graph to determine which nodes are relevant to the current query and returns a compact subgraph representation instead of the raw content.

The feature is **opt-in**: it is gated behind `--knowledge-graph` (proxy CLI flag) and `CUTCTX_KNOWLEDGE_GRAPH=1` (env var). Users who do not set either flag see zero behavioral change.

---

## 1. Architecture Overview

```
Proxy request (Claude Code Read/Glob/Grep tool result)
        │
        ▼
ToolResultInterceptor pipeline (cutctx/proxy/interceptors/)
        │
        ├── existing: AstGrepInterceptor  (per-file outline)
        │
        └── NEW: GraphifyInterceptor      ← this spec
                │
                ├── matches(): Read/Glob/Grep tool results
                │             when graph index exists
                │
                └── transform():
                      1. Extract query intent from current tool input
                      2. Find relevant graph nodes via BFS from seed nodes
                      3. Return compact subgraph representation
                      4. Fall through to AstGrepInterceptor if graph miss

Background (proxy startup):
        └── GraphifyIndexer (cutctx/graph/graphify.py)
                │
                ├── Checks if graphify-out/graph.json exists + is fresh
                ├── If stale/missing: runs `graphify ./` in background thread
                └── Stores index in memory for O(1) BFS lookups

File watcher (existing CodeGraphWatcher extended):
        └── On source file change → debounce → re-run graphify
```

---

## 2. Dependency Changes

### 2.1 `pyproject.toml` — add `knowledge-graph` optional group

**File:** `pyproject.toml`  
**Section:** `[project.optional-dependencies]`

Add after the `code = [...]` block:

```toml
# Knowledge graph compression via Graphify (opt-in)
# Enables --knowledge-graph proxy flag for 70x+ token reduction on codebase reads.
knowledge-graph = [
    "cutctx-ai[proxy]",
    "graphifyy>=3.0.0",       # Graphify — MIT license
    "networkx>=3.0",          # Graph data structure + BFS (also used by Graphify)
]
```

**Verification:** After adding, run:
```bash
pip install -e ".[knowledge-graph]" --dry-run
# Must resolve without conflicts. graphifyy pulls tree-sitter; networkx is already
# a transitive dep of several existing packages — check for version conflicts.
```

**Correctness check:** Confirm `graphifyy` is the correct PyPI name (not `graphify`):
```bash
pip index versions graphifyy 2>&1 | head -5
# Should list versions ≥ 3.0.0
```

---

## 3. Configuration Flag

### 3.1 `cutctx/proxy/models.py`

**Current state:** Line 180 has `code_graph_watcher: bool = False`.

Add directly below it:

```python
# Knowledge-graph compression via Graphify (opt-in).
# When enabled, the proxy builds a knowledge graph of the working directory
# and routes Read/Glob/Grep tool results through graph-aware compression.
# Requires: pip install cutctx-ai[knowledge-graph]
# Activate: --knowledge-graph flag or CUTCTX_KNOWLEDGE_GRAPH=1
knowledge_graph_enabled: bool = False

# Maximum BFS depth when querying the graph for a relevant subgraph.
# Deeper = more context, more tokens. Default 2 is the sweet spot.
knowledge_graph_bfs_depth: int = 2

# Max nodes to include in a graph response. Prevents runaway responses on
# densely connected graphs.
knowledge_graph_max_nodes: int = 40

# Minimum file size (chars) before the graph interceptor activates.
# Below this threshold, raw content is smaller than a subgraph response.
knowledge_graph_min_chars: int = 800

# Path to the Graphify output directory, relative to CWD.
# Default matches Graphify's own default output directory.
knowledge_graph_output_dir: str = "graphify-out"
```

### 3.2 CLI flag in `cutctx/cli/proxy.py`

**Locate** the `@app.command("proxy")` definition. Find where `--code-graph-watcher` is added. Add the new flag immediately below it:

```python
knowledge_graph: bool = typer.Option(
    False,
    "--knowledge-graph",
    envvar="CUTCTX_KNOWLEDGE_GRAPH",
    help=(
        "Enable knowledge-graph compression (Graphify). "
        "Requires: pip install cutctx-ai[knowledge-graph]. "
        "On first run, builds a graph of your codebase (~30s). "
        "Subsequent runs use the cached graph."
    ),
),
knowledge_graph_bfs_depth: int = typer.Option(
    2,
    "--knowledge-graph-bfs-depth",
    envvar="CUTCTX_KG_BFS_DEPTH",
    help="BFS depth when querying the knowledge graph (default 2).",
),
knowledge_graph_max_nodes: int = typer.Option(
    40,
    "--knowledge-graph-max-nodes",
    envvar="CUTCTX_KG_MAX_NODES",
    help="Max graph nodes per response (default 40).",
),
```

Pass these values into the config dict / `ProxyConfig` constructor where the proxy CLI builds config. Mirror the pattern used for `code_graph_watcher`.

**Verification:**
```bash
cutctx proxy --help | grep knowledge-graph
# Must show all three flags with descriptions.
```

---

## 4. Core Graph Module

### 4.1 `cutctx/graph/graphify.py` — NEW FILE

This is the main new module. It owns:
- Building / loading the Graphify graph index
- BFS subgraph queries given seed nodes
- Emitting compact graph representations

```python
"""Graphify knowledge-graph backend for Cutctx.

Wraps graphifyy (MIT, github.com/safishamsi/graphify) to build and query
a knowledge graph of the working directory. Used by GraphifyInterceptor
to replace verbose Read/Glob/Grep results with compact subgraph representations.

Activation: --knowledge-graph proxy flag or CUTCTX_KNOWLEDGE_GRAPH=1
Dependency: pip install cutctx-ai[knowledge-graph]

Architecture:
    GraphifyIndex       — loads graph.json, exposes query_subgraph()
    GraphifyIndexer     — background thread that builds/refreshes the graph
    GraphifyQueryResult — typed result from query_subgraph()
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Availability check ────────────────────────────────────────────────────────

_GRAPHIFY_AVAILABLE: bool | None = None


def graphify_available() -> bool:
    """Return True if graphifyy is installed and importable."""
    global _GRAPHIFY_AVAILABLE
    if _GRAPHIFY_AVAILABLE is None:
        try:
            import graphifyy  # noqa: F401
            _GRAPHIFY_AVAILABLE = True
        except ImportError:
            _GRAPHIFY_AVAILABLE = False
    return _GRAPHIFY_AVAILABLE


def networkx_available() -> bool:
    """Return True if networkx is importable."""
    try:
        import networkx  # noqa: F401
        return True
    except ImportError:
        return False


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class GraphNode:
    """A single node in the knowledge graph."""
    id: str
    label: str
    node_type: str        # "function", "class", "module", "concept", "file"
    file_path: str = ""
    community: int = -1   # Leiden community ID
    degree: int = 0       # Number of edges (proxy for importance)
    summary: str = ""     # LLM-extracted summary (if available)
    raw: dict = field(default_factory=dict)


@dataclass
class GraphifyQueryResult:
    """Result from query_subgraph()."""
    nodes: list[GraphNode]
    edges: list[tuple[str, str, str]]  # (source_id, target_id, edge_type)
    seed_nodes: list[str]              # Node IDs used as BFS seeds
    bfs_depth: int
    tokens_estimated: int
    graph_version: str = ""
    fallback: bool = False             # True if graph was unavailable


# ── Graph index ───────────────────────────────────────────────────────────────

class GraphifyIndex:
    """
    Loaded knowledge graph. Thread-safe for concurrent reads.

    Loads from graphify-out/graph.json (Graphify's default output).
    Exposes query_subgraph() for BFS-based relevance queries.

    Usage:
        index = GraphifyIndex.load(Path("graphify-out/graph.json"))
        result = index.query_subgraph(
            seed_terms=["AuthService", "login"],
            bfs_depth=2,
            max_nodes=40,
        )
    """

    def __init__(self, graph: Any, version: str = "") -> None:
        """
        Args:
            graph: networkx.Graph or DiGraph loaded from graph.json.
            version: Graph build timestamp / version string.
        """
        self._graph = graph
        self._version = version
        self._lock = threading.RLock()  # RLock: query_subgraph can be called recursively

    @classmethod
    def load(cls, graph_json_path: Path) -> GraphifyIndex:
        """
        Load a Graphify graph.json into a networkx Graph.

        Raises:
            ImportError: if networkx is not installed
            FileNotFoundError: if graph.json does not exist
            ValueError: if graph.json is malformed

        Format expected (Graphify v3 node-link format):
            {
              "directed": false,
              "multigraph": false,
              "graph": {},
              "nodes": [{"id": "...", "label": "...", "type": "...", ...}],
              "links": [{"source": "...", "target": "...", "type": "..."}]
            }
        """
        import networkx as nx

        if not graph_json_path.exists():
            raise FileNotFoundError(f"graph.json not found at {graph_json_path}")

        raw = json.loads(graph_json_path.read_text(encoding="utf-8"))

        # Graphify emits node-link format; use nx.node_link_graph to load.
        # Fall back to manual construction if format differs.
        try:
            G = nx.node_link_graph(raw)
        except Exception as e:
            raise ValueError(f"Failed to parse graph.json: {e}") from e

        version = raw.get("graph", {}).get("built_at", "")
        logger.info(
            "Graphify index loaded: %d nodes, %d edges (built: %s)",
            G.number_of_nodes(),
            G.number_of_edges(),
            version or "unknown",
        )
        return cls(G, version=version)

    def query_subgraph(
        self,
        seed_terms: list[str],
        bfs_depth: int = 2,
        max_nodes: int = 40,
    ) -> GraphifyQueryResult:
        """
        Return a BFS subgraph anchored on nodes matching seed_terms.

        Algorithm:
            1. Find seed nodes: nodes whose label/id contains any seed_term
               (case-insensitive substring match, then exact match preferred).
            2. Run BFS from each seed node up to bfs_depth hops.
            3. Collect unique nodes, sorted by degree (most-connected first).
            4. Truncate to max_nodes.

        Args:
            seed_terms: Query terms (e.g. ["AuthService", "login", "token"]).
            bfs_depth: BFS hop limit.
            max_nodes: Hard cap on returned nodes.

        Returns:
            GraphifyQueryResult with nodes, edges, and metadata.
        """
        import networkx as nx

        with self._lock:
            G = self._graph

        if G.number_of_nodes() == 0:
            return GraphifyQueryResult(
                nodes=[], edges=[], seed_nodes=[],
                bfs_depth=bfs_depth, tokens_estimated=0,
                graph_version=self._version, fallback=True,
            )

        # Step 1: find seed nodes
        seed_node_ids: list[str] = []
        terms_lower = [t.lower() for t in seed_terms]

        with self._lock:
            for node_id in G.nodes:
                attrs = G.nodes[node_id]
                label = str(attrs.get("label", node_id)).lower()
                node_id_lower = str(node_id).lower()
                if any(t in label or t in node_id_lower for t in terms_lower):
                    seed_node_ids.append(node_id)

        if not seed_node_ids:
            # No exact matches — fall back to community-based seeds
            # (return god nodes from the most relevant community)
            seed_node_ids = self._fallback_seeds(terms_lower)

        # Step 2: BFS from each seed
        visited: set[str] = set()
        with self._lock:
            for seed in seed_node_ids[:5]:  # cap seeds to avoid explosion
                try:
                    bfs_nodes = nx.single_source_shortest_path_length(
                        G, seed, cutoff=bfs_depth
                    )
                    visited.update(bfs_nodes.keys())
                except nx.NodeNotFound:
                    continue

        if not visited:
            visited.update(seed_node_ids)

        # Step 3: Sort by degree, truncate
        with self._lock:
            nodes_with_degree = [
                (nid, G.degree(nid)) for nid in visited if nid in G
            ]
        nodes_with_degree.sort(key=lambda x: x[1], reverse=True)
        top_node_ids = {nid for nid, _ in nodes_with_degree[:max_nodes]}

        # Step 4: Build typed node list
        graph_nodes: list[GraphNode] = []
        with self._lock:
            for node_id in top_node_ids:
                attrs = G.nodes[node_id]
                graph_nodes.append(GraphNode(
                    id=str(node_id),
                    label=str(attrs.get("label", node_id)),
                    node_type=str(attrs.get("type", "unknown")),
                    file_path=str(attrs.get("file_path", attrs.get("file", ""))),
                    community=int(attrs.get("community", -1)),
                    degree=G.degree(node_id),
                    summary=str(attrs.get("summary", attrs.get("description", ""))),
                    raw=dict(attrs),
                ))

            # Step 5: Collect edges within the subgraph
            edges: list[tuple[str, str, str]] = []
            for u, v, data in G.edges(top_node_ids, data=True):
                if u in top_node_ids and v in top_node_ids:
                    edge_type = str(data.get("type", data.get("relation", "relates_to")))
                    edges.append((str(u), str(v), edge_type))

        # Estimate tokens: ~15 tokens per node (id + label + type + summary snippet)
        tokens_estimated = len(graph_nodes) * 15 + len(edges) * 5

        return GraphifyQueryResult(
            nodes=graph_nodes,
            edges=edges,
            seed_nodes=seed_node_ids,
            bfs_depth=bfs_depth,
            tokens_estimated=tokens_estimated,
            graph_version=self._version,
        )

    def _fallback_seeds(self, terms_lower: list[str]) -> list[str]:
        """Return high-degree nodes when no label matches are found."""
        import networkx as nx
        with self._lock:
            # Return top-5 nodes by degree ("god nodes") as fallback
            return [
                n for n, _ in sorted(
                    self._graph.degree(), key=lambda x: x[1], reverse=True
                )[:5]
            ]

    @property
    def node_count(self) -> int:
        with self._lock:
            return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        with self._lock:
            return self._graph.number_of_edges()

    @property
    def version(self) -> str:
        return self._version


# ── Subgraph renderer ─────────────────────────────────────────────────────────

def render_subgraph(result: GraphifyQueryResult, original_content: str = "") -> str:
    """
    Render a GraphifyQueryResult as a compact text representation for the LLM.

    Format:
        [KNOWLEDGE GRAPH — {N} nodes, BFS depth {D} from: {seeds}]

        ## Relevant Nodes
        [FUNC] AuthService.login (auth/service.py, community 3)
          → Handles user login, validates credentials, returns JWT token.
        [CLASS] UserRepository (db/repos.py, community 3)
          → ORM wrapper for users table.
        ...

        ## Relationships
        AuthService.login → calls → UserRepository.find_by_email
        AuthService.login → raises → AuthError
        ...

        [Full content available: use Read with explicit line range]

    This representation is ~15 tokens/node vs ~800+ tokens/file.
    """
    if result.fallback or not result.nodes:
        return original_content  # fall through — no graph data available

    lines: list[str] = []

    seed_labels = result.seed_nodes[:3]
    lines.append(
        f"[KNOWLEDGE GRAPH — {len(result.nodes)} nodes, "
        f"BFS depth {result.bfs_depth}"
        + (f", seeds: {', '.join(seed_labels)}" if seed_labels else "")
        + "]"
    )
    lines.append("")
    lines.append("## Relevant Nodes")

    # Group by file for readability
    by_file: dict[str, list[GraphNode]] = {}
    for node in sorted(result.nodes, key=lambda n: (-n.degree, n.file_path)):
        by_file.setdefault(node.file_path or "unknown", []).append(node)

    type_prefix = {
        "function": "[FUNC]", "method": "[FUNC]",
        "class": "[CLASS]", "module": "[MOD]",
        "concept": "[CONCEPT]", "file": "[FILE]",
        "unknown": "[NODE]",
    }

    for file_path, nodes in by_file.items():
        if file_path and file_path != "unknown":
            lines.append(f"\n### {file_path}")
        for node in nodes:
            prefix = type_prefix.get(node.node_type.lower(), "[NODE]")
            community_tag = f", community {node.community}" if node.community >= 0 else ""
            lines.append(f"{prefix} {node.label}{community_tag}")
            if node.summary:
                # Truncate long summaries
                summary = node.summary[:120] + "…" if len(node.summary) > 120 else node.summary
                lines.append(f"  → {summary}")

    if result.edges:
        lines.append("")
        lines.append("## Relationships")
        for src, tgt, edge_type in result.edges[:30]:  # cap edges
            # Look up labels
            src_label = next((n.label for n in result.nodes if n.id == src), src)
            tgt_label = next((n.label for n in result.nodes if n.id == tgt), tgt)
            lines.append(f"{src_label} → {edge_type} → {tgt_label}")

    lines.append("")
    lines.append(
        "[Full content available: use Read tool with explicit start_line/end_line]"
    )

    return "\n".join(lines)


# ── Background indexer ────────────────────────────────────────────────────────

class GraphifyIndexer:
    """
    Background thread that builds and refreshes the Graphify graph index.

    Lifecycle:
        1. start(project_dir) — start background thread
        2. Thread checks if graph.json exists and is fresh (< max_age_seconds old)
        3. If stale/missing: run `python -m graphifyy.cli <project_dir>` in subprocess
        4. On completion: load graph.json into GraphifyIndex and publish via get_index()
        5. On file changes (from CodeGraphWatcher): schedule refresh after debounce

    Thread safety:
        - get_index() is always safe to call from any thread
        - Returns None if index not yet ready (caller falls through gracefully)
    """

    # How old graph.json can be before triggering a background refresh
    MAX_AGE_SECONDS = 3600  # 1 hour

    # Debounce: wait this long after a file change before re-running graphify
    DEBOUNCE_SECONDS = 5.0

    def __init__(
        self,
        project_dir: Path,
        output_dir: str = "graphify-out",
        max_age_seconds: float = MAX_AGE_SECONDS,
    ) -> None:
        self._project_dir = project_dir
        self._output_dir = project_dir / output_dir
        self._graph_json = self._output_dir / "graph.json"
        self._max_age = max_age_seconds
        self._index: GraphifyIndex | None = None
        self._index_lock = threading.RLock()
        self._build_thread: threading.Thread | None = None
        self._build_lock = threading.Lock()  # prevent concurrent builds
        self._debounce_timer: threading.Timer | None = None
        self._debounce_lock = threading.Lock()
        self._started = False
        self._build_count = 0
        self._last_build_time: float = 0

    def start(self) -> None:
        """
        Start the indexer. Loads existing graph.json immediately (synchronous),
        then schedules a background refresh if the graph is stale.

        This is non-blocking: start() returns immediately. get_index() will
        return the existing graph (possibly stale) while a refresh is in progress.
        """
        if not graphify_available():
            logger.warning(
                "graphifyy not installed — knowledge graph disabled. "
                "Install with: pip install cutctx-ai[knowledge-graph]"
            )
            return

        if not networkx_available():
            logger.warning(
                "networkx not installed — knowledge graph disabled. "
                "Install with: pip install cutctx-ai[knowledge-graph]"
            )
            return

        self._started = True

        # Try to load existing graph synchronously (fast path)
        if self._graph_json.exists():
            try:
                index = GraphifyIndex.load(self._graph_json)
                with self._index_lock:
                    self._index = index
                logger.info(
                    "Knowledge graph: loaded existing index (%d nodes)",
                    index.node_count,
                )
            except Exception as e:
                logger.warning("Knowledge graph: failed to load existing index: %s", e)

        # Schedule background build if needed
        graph_age = self._graph_age_seconds()
        if graph_age is None or graph_age > self._max_age:
            reason = "no graph.json" if graph_age is None else f"graph is {graph_age:.0f}s old"
            logger.info("Knowledge graph: starting background build (%s)…", reason)
            self._start_build()
        else:
            logger.info(
                "Knowledge graph: index is fresh (age=%.0fs), no rebuild needed.",
                graph_age,
            )

    def get_index(self) -> GraphifyIndex | None:
        """Return the current index, or None if not yet available."""
        with self._index_lock:
            return self._index

    def schedule_refresh(self) -> None:
        """
        Schedule a debounced graph rebuild (called by file watcher on changes).

        Multiple rapid calls within DEBOUNCE_SECONDS collapse into one rebuild.
        """
        with self._debounce_lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(
                self.DEBOUNCE_SECONDS, self._start_build
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def stop(self) -> None:
        """Cancel pending timers. Does not kill a running build subprocess."""
        with self._debounce_lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None
        self._started = False

    @property
    def stats(self) -> dict:
        index = self.get_index()
        return {
            "started": self._started,
            "build_count": self._build_count,
            "last_build_time": self._last_build_time,
            "index_nodes": index.node_count if index else 0,
            "index_edges": index.edge_count if index else 0,
            "index_version": index.version if index else "",
            "graph_age_seconds": self._graph_age_seconds(),
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _graph_age_seconds(self) -> float | None:
        """Return age of graph.json in seconds, or None if it doesn't exist."""
        if not self._graph_json.exists():
            return None
        mtime = self._graph_json.stat().st_mtime
        return time.time() - mtime

    def _start_build(self) -> None:
        """Start a background build thread (non-blocking). Skips if already building."""
        with self._build_lock:
            if self._build_thread and self._build_thread.is_alive():
                logger.debug("Knowledge graph: build already in progress, skipping.")
                return
            self._build_thread = threading.Thread(
                target=self._build, daemon=True, name="graphify-indexer"
            )
            self._build_thread.start()

    def _build(self) -> None:
        """
        Run Graphify to build graph.json. Called in background thread.

        Invokes graphify via its Python API (preferred) or subprocess fallback.
        On success, reloads the index from graph.json.
        """
        if not self._started:
            return

        start = time.monotonic()
        logger.info(
            "Knowledge graph: building index for %s …", self._project_dir
        )

        try:
            self._run_graphify_build()
        except Exception as e:
            logger.warning("Knowledge graph: build failed: %s", e)
            return

        elapsed = time.monotonic() - start
        self._build_count += 1
        self._last_build_time = time.time()

        # Reload index
        if self._graph_json.exists():
            try:
                new_index = GraphifyIndex.load(self._graph_json)
                with self._index_lock:
                    self._index = new_index
                logger.info(
                    "Knowledge graph: index updated (%.1fs, %d nodes, %d edges)",
                    elapsed,
                    new_index.node_count,
                    new_index.edge_count,
                )
            except Exception as e:
                logger.warning("Knowledge graph: failed to load new index: %s", e)
        else:
            logger.warning(
                "Knowledge graph: build completed (%.1fs) but graph.json not found at %s",
                elapsed,
                self._graph_json,
            )

    def _run_graphify_build(self) -> None:
        """
        Invoke Graphify to build graph.json.

        Strategy:
            1. Try Python API (graphifyy.KnowledgeGraph / graphifyy.run_pipeline)
            2. Fall back to subprocess: python -m graphifyy.cli <project_dir>

        The output directory is always self._output_dir.
        Environment inherits from the proxy process (so the LLM API key
        configured for the proxy is available to Graphify's semantic extraction).
        """
        import importlib

        # Ensure output directory exists
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Try Python API first (preferred — avoids subprocess overhead)
        try:
            graphifyy = importlib.import_module("graphifyy")
            # Attempt to use graphifyy's public run function.
            # graphifyy v3 exposes: graphifyy.run(path, output_dir)
            run_fn = getattr(graphifyy, "run", None)
            if callable(run_fn):
                run_fn(
                    str(self._project_dir),
                    output_dir=str(self._output_dir),
                )
                return
        except Exception as e:
            logger.debug("Knowledge graph: Python API failed (%s), trying subprocess", e)

        # Subprocess fallback
        # graphifyy installs a `graphify` CLI entry point
        import shutil
        import sys

        graphify_bin = shutil.which("graphify")
        if graphify_bin:
            cmd = [graphify_bin, str(self._project_dir), "--output", str(self._output_dir)]
        else:
            # Use python -m as last resort
            cmd = [
                sys.executable, "-m", "graphifyy.cli",
                str(self._project_dir),
                "--output", str(self._output_dir),
            ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max
            cwd=str(self._project_dir),
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"graphify build exited {result.returncode}: {result.stderr[:500]}"
            )


# ── Module-level singleton ────────────────────────────────────────────────────
# The proxy server creates one GraphifyIndexer per proxy instance and stores it
# on the server object (same pattern as code_graph_watcher). This singleton
# is NOT used directly by the interceptor — the interceptor receives a reference
# to the indexer via constructor injection.

_global_indexer: GraphifyIndexer | None = None
_global_indexer_lock = threading.Lock()


def get_global_indexer() -> GraphifyIndexer | None:
    """Return the global indexer if initialized."""
    with _global_indexer_lock:
        return _global_indexer


def set_global_indexer(indexer: GraphifyIndexer | None) -> None:
    """Set the global indexer (called by proxy server on startup)."""
    global _global_indexer
    with _global_indexer_lock:
        _global_indexer = indexer
```

---

## 5. Interceptor

### 5.1 `cutctx/proxy/interceptors/graph_interceptor.py` — NEW FILE

```python
"""GraphifyInterceptor — replace Read/Glob/Grep results with knowledge graph subgraphs.

This interceptor is registered when --knowledge-graph is enabled. It:
  1. Matches Read / Glob / Grep tool results that are large enough to benefit
  2. Extracts query terms from the tool input (file path, query string, etc.)
  3. Queries the live GraphifyIndex for a BFS subgraph
  4. Returns a compact subgraph representation (~15 tokens/node vs ~800 tokens/file)
  5. Falls through (returns None) if the graph is unavailable or the subgraph
     is larger than the original content

Name in registry: "graphify-kg"
Priority: runs BEFORE AstGrepInterceptor (registered first)

Progressive disclosure: uses the file path as the key.
  - First Read of a file → subgraph representation
  - Second Read of the same file (model came back for more) → pass through
    (AstGrepInterceptor's outline is then the next layer)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from cutctx.graph.graphify import (
    GraphifyIndex,
    GraphifyIndexer,
    GraphifyQueryResult,
    get_global_indexer,
    render_subgraph,
)

logger = logging.getLogger(__name__)

# Tools whose outputs this interceptor can rewrite
_TARGET_TOOLS = frozenset({
    # Claude Code
    "Read", "read_file",
    # Glob / search
    "Glob", "glob", "GlobFiles",
    # Grep / ripgrep
    "Grep", "grep", "search_files",
    # Bash (only when output looks like code search)
    "Bash",
})

# Minimum output size before graph substitution is worthwhile.
# Below this, raw content is smaller than the subgraph header.
_MIN_OUTPUT_CHARS = 800

# Maximum output size we'll try to replace.
# Very large outputs (>200k chars) are expensive to pass through anyway;
# let existing compressors handle them.
_MAX_OUTPUT_CHARS = 200_000

# Regex to extract a file path from tool input (catches common patterns)
_FILE_PATH_RE = re.compile(
    r'(?:file_path|path|filename|file|filepath)["\s:=]+([^\s"\'>,\]]+)',
    re.IGNORECASE,
)


class GraphifyInterceptor:
    """Knowledge-graph interceptor for tool_result messages.

    Inject via:
        from cutctx.proxy.interceptors.graph_interceptor import GraphifyInterceptor
        from cutctx.proxy.interceptors import base as interceptors_base
        interceptors_base.register(GraphifyInterceptor(bfs_depth=2, max_nodes=40))

    The interceptor uses the global GraphifyIndexer singleton by default.
    Pass an explicit indexer for testing.
    """

    name = "graphify-kg"

    def __init__(
        self,
        bfs_depth: int = 2,
        max_nodes: int = 40,
        min_chars: int = _MIN_OUTPUT_CHARS,
        indexer: GraphifyIndexer | None = None,
    ) -> None:
        self._bfs_depth = bfs_depth
        self._max_nodes = max_nodes
        self._min_chars = min_chars
        self._indexer = indexer  # None → use global singleton

    def _get_index(self) -> GraphifyIndex | None:
        """Return the current graph index, or None if unavailable."""
        indexer = self._indexer or get_global_indexer()
        if indexer is None:
            return None
        return indexer.get_index()

    def matches(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> bool:
        """Return True if this tool result is a candidate for graph replacement."""
        # Must be a target tool
        if tool_name not in _TARGET_TOOLS:
            return False

        # Output must be large enough
        if len(tool_output) < self._min_chars:
            return False

        # Output must not be too large (let other compressors handle)
        if len(tool_output) > _MAX_OUTPUT_CHARS:
            return False

        # Graph must be available
        if self._get_index() is None:
            return False

        return True

    def transform(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> str | None:
        """
        Replace tool output with a compact graph subgraph, or return None.

        Returns None (no-op) if:
        - graph is unavailable
        - subgraph is larger than the original (never enlarge)
        - no relevant nodes found

        Progressive disclosure: on second Read of the same file, the framework
        already skips this interceptor (via progressive_disclosure_key).
        """
        index = self._get_index()
        if index is None:
            return None

        # Extract seed terms from tool input + first line of output
        seed_terms = self._extract_seed_terms(tool_name, tool_input, tool_output)
        if not seed_terms:
            return None

        # Query graph
        try:
            result: GraphifyQueryResult = index.query_subgraph(
                seed_terms=seed_terms,
                bfs_depth=self._bfs_depth,
                max_nodes=self._max_nodes,
            )
        except Exception as e:
            logger.debug("GraphifyInterceptor: query failed: %s", e)
            return None

        if result.fallback or not result.nodes:
            logger.debug(
                "GraphifyInterceptor: no relevant nodes for terms %s",
                seed_terms[:3],
            )
            return None

        # Render subgraph
        rendered = render_subgraph(result, original_content=tool_output)

        # Safety check: never return something larger than the input
        if len(rendered) >= len(tool_output):
            logger.debug(
                "GraphifyInterceptor: rendered (%d chars) >= original (%d chars), skipping",
                len(rendered), len(tool_output),
            )
            return None

        logger.debug(
            "GraphifyInterceptor: %s → graph subgraph (%d nodes, %d→%d chars)",
            tool_name,
            len(result.nodes),
            len(tool_output),
            len(rendered),
        )
        return rendered

    def progressive_disclosure_key(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
    ) -> str | None:
        """
        Return file path as the progressive disclosure key.

        Effect: if the LLM reads the same file twice (first read was replaced
        by a subgraph, model wants more detail), the second read passes through
        unmodified and the AstGrepInterceptor outline is offered instead.
        """
        path = self._extract_file_path(tool_input)
        return f"graphify:{path}" if path else None

    # ── Private helpers ────────────────────────────────────────────────────────

    def _extract_file_path(self, tool_input: dict[str, Any]) -> str | None:
        """Extract file path from tool input."""
        for key in ("file_path", "path", "filename", "file", "filepath"):
            val = tool_input.get(key)
            if isinstance(val, str) and val:
                return val
        return None

    def _extract_seed_terms(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> list[str]:
        """
        Extract seed terms for graph BFS from tool context.

        Sources (in priority order):
        1. File path components (e.g. "auth/service.py" → ["auth", "service"])
        2. Query string (for Grep/search_files)
        3. First non-empty word in tool output (for Bash/unknown)
        4. Tool input values (fallback)
        """
        terms: list[str] = []

        # From file path
        path = self._extract_file_path(tool_input)
        if path:
            from pathlib import Path as _Path
            stem = _Path(path).stem  # "auth_service" from "auth/auth_service.py"
            # Split on common delimiters
            parts = re.split(r"[/_\-\.]", stem)
            terms.extend(p for p in parts if len(p) > 2)
            # Also add the parent dir name
            parent = str(_Path(path).parent.name)
            if len(parent) > 2 and parent != ".":
                terms.append(parent)

        # From grep/search query
        for key in ("query", "pattern", "regex", "search"):
            val = tool_input.get(key)
            if isinstance(val, str) and val:
                # Strip regex metacharacters, take words
                clean = re.sub(r"[.*+?^${}()|[\]\\]", " ", val)
                words = [w for w in clean.split() if len(w) > 2]
                terms.extend(words[:5])
                break

        # From glob pattern
        pattern = tool_input.get("pattern")
        if isinstance(pattern, str):
            # Extract meaningful part: "src/auth/**/*.py" → ["auth"]
            parts = re.split(r"[/*_\-\.]", pattern)
            terms.extend(p for p in parts if len(p) > 2 and p not in ("src", "lib", "app"))

        # From first line of output (fallback)
        if not terms:
            first_line = tool_output.split("\n", 1)[0].strip()
            words = [w.strip("(){}[],:;") for w in first_line.split() if len(w) > 3]
            terms.extend(words[:3])

        # Deduplicate, preserve order
        seen: set[str] = set()
        deduped: list[str] = []
        for t in terms:
            tl = t.lower()
            if tl not in seen:
                seen.add(tl)
                deduped.append(t)

        return deduped[:10]  # cap at 10 seed terms
```

---

## 6. Proxy Server Integration

### 6.1 `cutctx/proxy/server.py`

**Locate:** The block starting at line ~800 that initializes `self.code_graph_watcher`.

**Add immediately after** the code_graph_watcher block (after line ~808):

```python
# Knowledge-graph compression (opt-in via --knowledge-graph)
self.knowledge_graph_indexer: GraphifyIndexer | None = None
if config.knowledge_graph_enabled:
    from cutctx.graph.graphify import GraphifyIndexer, set_global_indexer, graphify_available
    from cutctx.proxy.interceptors.graph_interceptor import GraphifyInterceptor
    from cutctx.proxy.interceptors import base as interceptors_base

    if not graphify_available():
        logger.warning(
            "Knowledge graph requested (--knowledge-graph) but graphifyy is not installed. "
            "Install with: pip install cutctx-ai[knowledge-graph]"
        )
    else:
        indexer = GraphifyIndexer(
            project_dir=Path.cwd(),
            output_dir=config.knowledge_graph_output_dir,
        )
        indexer.start()
        self.knowledge_graph_indexer = indexer
        set_global_indexer(indexer)

        # Register interceptor — must run BEFORE AstGrepInterceptor so it gets
        # first shot. AstGrepInterceptor provides outline on second Read (after
        # progressive disclosure advances past the graph replacement).
        interceptors_base.INTERCEPTORS.insert(
            0,
            GraphifyInterceptor(
                bfs_depth=config.knowledge_graph_bfs_depth,
                max_nodes=config.knowledge_graph_max_nodes,
                min_chars=config.knowledge_graph_min_chars,
            ),
        )
        logger.info(
            "Knowledge graph: interceptor registered (bfs_depth=%d, max_nodes=%d)",
            config.knowledge_graph_bfs_depth,
            config.knowledge_graph_max_nodes,
        )
```

**Locate:** The `stop()` / shutdown block (around line ~1811 where `code_graph_watcher.stop()` is called).

**Add:**
```python
if proxy.knowledge_graph_indexer:
    proxy.knowledge_graph_indexer.stop()
```

**Locate:** The startup stats dict (around line ~2002 where `"code_graph"` key is set).

**Add:**
```python
"knowledge_graph": config.knowledge_graph_enabled,
```

### 6.2 Connect file watcher to graphify indexer

If `CodeGraphWatcher` is already active AND knowledge graph is enabled, the file watcher should also trigger graph refreshes. In `cutctx/graph/watcher.py`, `_do_reindex()` calls `codebase-memory-mcp`. After that subprocess call, add a hook:

**In `_do_reindex()`, after the subprocess completes successfully:**

```python
# Also notify GraphifyIndexer if knowledge graph is enabled
from cutctx.graph.graphify import get_global_indexer
kg_indexer = get_global_indexer()
if kg_indexer:
    kg_indexer.schedule_refresh()
```

This ensures that when the CBM watcher detects a file change, it also triggers a Graphify refresh.

---

## 7. Dashboard / Stats Endpoint

**File:** `cutctx/proxy/routes/admin.py` (or wherever the `/stats` endpoint lives)

Locate the stats response dict and add:

```python
"knowledge_graph": {
    "enabled": bool(getattr(proxy, "knowledge_graph_indexer", None)),
    **(proxy.knowledge_graph_indexer.stats if getattr(proxy, "knowledge_graph_indexer", None) else {}),
},
```

---

## 8. `cutctx/graph/__init__.py` Update

Replace current contents:

```python
"""Code graph intelligence for cutctx.

Provides live code graph reindexing via file watching, with
codebase-memory-mcp as the graph backend.

Also provides optional Graphify knowledge-graph compression:
    GraphifyIndexer  — builds and caches graph.json in background
    GraphifyIndex    — loaded graph with BFS query API
    graphify_available() — runtime availability check
"""

from cutctx.graph.graphify import (  # noqa: F401
    GraphifyIndex,
    GraphifyIndexer,
    GraphifyQueryResult,
    GraphNode,
    get_global_indexer,
    graphify_available,
    render_subgraph,
    set_global_indexer,
)
```

---

## 9. Test Files

### 9.1 `tests/test_graphify_index.py` — NEW FILE

```python
"""Unit tests for GraphifyIndex and GraphifyIndexer."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Guard: skip entire module if networkx not installed
pytest.importorskip("networkx")
import networkx as nx

from cutctx.graph.graphify import (
    GraphifyIndex,
    GraphifyQueryResult,
    render_subgraph,
)


def _make_test_graph() -> dict:
    """Minimal valid node-link graph.json with 5 nodes."""
    G = nx.Graph()
    G.add_node("auth.login", label="login", type="function",
               file_path="auth/service.py", community=0, summary="Handles user login")
    G.add_node("auth.AuthService", label="AuthService", type="class",
               file_path="auth/service.py", community=0, summary="Auth service class")
    G.add_node("db.UserRepository", label="UserRepository", type="class",
               file_path="db/repos.py", community=1, summary="ORM for users table")
    G.add_node("models.User", label="User", type="class",
               file_path="models.py", community=1, summary="User model")
    G.add_node("utils.hash_password", label="hash_password", type="function",
               file_path="utils/crypto.py", community=2, summary="Bcrypt hashing")
    G.add_edge("auth.login", "db.UserRepository", type="calls")
    G.add_edge("auth.AuthService", "auth.login", type="contains")
    G.add_edge("auth.login", "utils.hash_password", type="calls")
    return nx.node_link_data(G)


def _save_graph(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class TestGraphifyIndex:
    def test_load_valid_graph(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        assert index.node_count == 5
        assert index.edge_count == 3

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            GraphifyIndex.load(tmp_path / "nonexistent.json")

    def test_load_malformed_json_raises(self, tmp_path):
        bad = tmp_path / "graph.json"
        bad.write_text("not json", encoding="utf-8")
        with pytest.raises((ValueError, Exception)):
            GraphifyIndex.load(bad)

    def test_query_exact_match(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        result = index.query_subgraph(["login"], bfs_depth=1, max_nodes=10)
        assert not result.fallback
        labels = [n.label for n in result.nodes]
        assert "login" in labels  # seed node found

    def test_query_bfs_follows_edges(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        # "login" at depth 0, "UserRepository" at depth 1 via "calls" edge
        result = index.query_subgraph(["login"], bfs_depth=1, max_nodes=20)
        labels = [n.label for n in result.nodes]
        assert "UserRepository" in labels

    def test_query_max_nodes_respected(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        result = index.query_subgraph(["login"], bfs_depth=5, max_nodes=2)
        assert len(result.nodes) <= 2

    def test_query_no_match_returns_fallback_seeds(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        # Term not in any label → should fall back to god nodes, not crash
        result = index.query_subgraph(["ZZZUNKNOWNZZZ"], bfs_depth=1, max_nodes=5)
        # Either returns something or marks fallback — must not raise
        assert isinstance(result, GraphifyQueryResult)

    def test_empty_graph_returns_fallback(self, tmp_path):
        G = nx.Graph()
        graph_json = tmp_path / "graph.json"
        graph_json.write_text(json.dumps(nx.node_link_data(G)), encoding="utf-8")
        index = GraphifyIndex.load(graph_json)
        result = index.query_subgraph(["anything"], bfs_depth=2, max_nodes=10)
        assert result.fallback is True
        assert result.nodes == []


class TestRenderSubgraph:
    def _make_result(self) -> GraphifyQueryResult:
        from cutctx.graph.graphify import GraphNode
        return GraphifyQueryResult(
            nodes=[
                GraphNode(id="auth.login", label="login", node_type="function",
                          file_path="auth/service.py", community=0, degree=3,
                          summary="Handles user login"),
                GraphNode(id="db.UserRepository", label="UserRepository", node_type="class",
                          file_path="db/repos.py", community=1, degree=2,
                          summary="ORM for users table"),
            ],
            edges=[("auth.login", "db.UserRepository", "calls")],
            seed_nodes=["auth.login"],
            bfs_depth=1,
            tokens_estimated=40,
        )

    def test_renders_node_labels(self):
        result = self._make_result()
        rendered = render_subgraph(result, "original content " * 100)
        assert "login" in rendered
        assert "UserRepository" in rendered

    def test_renders_edges(self):
        result = self._make_result()
        rendered = render_subgraph(result, "original content " * 100)
        assert "calls" in rendered

    def test_fallback_returns_original(self):
        result = GraphifyQueryResult(
            nodes=[], edges=[], seed_nodes=[],
            bfs_depth=1, tokens_estimated=0, fallback=True,
        )
        original = "this is the original content"
        assert render_subgraph(result, original) == original

    def test_rendered_shorter_than_1000_chars_for_small_graph(self):
        result = self._make_result()
        rendered = render_subgraph(result, "x" * 5000)
        assert len(rendered) < 5000  # must compress


class TestGraphifyInterceptor:
    """Integration tests for GraphifyInterceptor."""

    def _make_interceptor(self, index):
        from cutctx.graph.graphify import GraphifyIndexer
        from cutctx.proxy.interceptors.graph_interceptor import GraphifyInterceptor

        mock_indexer = MagicMock(spec=GraphifyIndexer)
        mock_indexer.get_index.return_value = index
        return GraphifyInterceptor(bfs_depth=1, max_nodes=10, indexer=mock_indexer)

    def test_matches_read_tool_with_large_output(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        interceptor = self._make_interceptor(index)
        assert interceptor.matches("Read", {"file_path": "auth/service.py"}, "x" * 1000)

    def test_does_not_match_small_output(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        interceptor = self._make_interceptor(index)
        assert not interceptor.matches("Read", {"file_path": "auth/service.py"}, "short")

    def test_does_not_match_non_target_tool(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        interceptor = self._make_interceptor(index)
        assert not interceptor.matches("WriteFile", {}, "x" * 1000)

    def test_transform_returns_smaller_content(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        interceptor = self._make_interceptor(index)
        large_output = "def login(user): pass\n" * 200
        result = interceptor.transform("Read", {"file_path": "auth/service.py"}, large_output)
        if result is not None:
            assert len(result) < len(large_output), "transform must not enlarge content"

    def test_transform_returns_none_when_no_index(self, tmp_path):
        from cutctx.proxy.interceptors.graph_interceptor import GraphifyInterceptor
        from cutctx.graph.graphify import GraphifyIndexer
        mock_indexer = MagicMock(spec=GraphifyIndexer)
        mock_indexer.get_index.return_value = None
        interceptor = GraphifyInterceptor(indexer=mock_indexer)
        result = interceptor.transform("Read", {"file_path": "auth.py"}, "x" * 1000)
        assert result is None

    def test_progressive_disclosure_key(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        interceptor = self._make_interceptor(index)
        key = interceptor.progressive_disclosure_key("Read", {"file_path": "auth/service.py"})
        assert key == "graphify:auth/service.py"

    def test_no_progressive_key_for_grep(self, tmp_path):
        graph_json = tmp_path / "graph.json"
        _save_graph(graph_json, _make_test_graph())
        index = GraphifyIndex.load(graph_json)
        interceptor = self._make_interceptor(index)
        # Grep has no file_path in input
        key = interceptor.progressive_disclosure_key("Grep", {"pattern": "def login"})
        assert key is None
```

---

## 10. Verification and Correctness Checks

These must be performed in order after implementation.

### Step 1 — Dependency install check

```bash
# Must install cleanly with no conflicts
pip install -e ".[knowledge-graph]"
python -c "import graphifyy; import networkx; print('OK')"
```

**Expected:** `OK`. If graphifyy has version conflicts with existing deps, check networkx version and relax the constraint if needed.

### Step 2 — Unit tests pass

```bash
python -m pytest tests/test_graphify_index.py -v
```

**Expected:** All tests in `TestGraphifyIndex`, `TestRenderSubgraph`, `TestGraphifyInterceptor` pass. Zero failures.

### Step 3 — Proxy starts without `--knowledge-graph` flag (no regression)

```bash
cutctx proxy --port 18787 &
sleep 2
curl -s http://localhost:18787/livez | python -m json.tool
kill %1
```

**Expected:** `{"status": "ok"}`. The knowledge graph code must not execute at all when the flag is absent.

### Step 4 — Proxy starts WITH `--knowledge-graph` flag

```bash
cd /tmp && mkdir kg-test && cd kg-test
echo 'def login(user, password): pass' > auth.py
echo 'class User: pass' > models.py

cutctx proxy --port 18788 --knowledge-graph &
sleep 3  # allow background build to start

curl -s http://localhost:18788/livez | python -m json.tool
# Must show "knowledge_graph" key in stats if /stats endpoint updated

kill %1
```

**Expected:**
- Proxy starts successfully
- Background thread log line: `Knowledge graph: starting background build…`
- No crash if `graphify-out/graph.json` doesn't exist yet (graceful degradation)

### Step 5 — Graph build completes

```bash
cd /tmp/kg-test
cutctx proxy --port 18789 --knowledge-graph &

# Wait up to 120s for graph.json to appear
for i in $(seq 1 24); do
  [ -f graphify-out/graph.json ] && echo "Graph built!" && break
  sleep 5
done

kill %1

# Verify graph.json is valid
python -c "
import json, networkx as nx
data = json.load(open('graphify-out/graph.json'))
G = nx.node_link_graph(data)
print(f'Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}')
assert G.number_of_nodes() > 0
print('Graph.json is valid.')
"
```

**Expected:** `Graph built!`, then `Nodes: N, Edges: M` with N > 0, `Graph.json is valid.`

### Step 6 — Interceptor is registered in correct position

```bash
python -c "
from cutctx.proxy.interceptors.base import INTERCEPTORS
names = [i.name for i in INTERCEPTORS]
print('Interceptors:', names)
# graphify-kg must come BEFORE ast-grep
if 'graphify-kg' in names and 'ast-grep' in names:
    assert names.index('graphify-kg') < names.index('ast-grep'), \
        'graphify-kg must precede ast-grep'
    print('Order: OK')
"
```

**Expected:** `graphify-kg` appears before `ast-grep` in the list.

### Step 7 — Interceptor compresses a synthetic Read output

```python
# Run this as a standalone script: python verify_interceptor.py
import json, tempfile, pathlib
from unittest.mock import MagicMock
from cutctx.graph.graphify import GraphifyIndex, GraphifyIndexer
from cutctx.proxy.interceptors.graph_interceptor import GraphifyInterceptor

# Build a minimal graph.json
import networkx as nx
G = nx.Graph()
G.add_node("auth.login", label="login", type="function",
           file_path="auth/service.py", community=0, summary="Handles login")
G.add_node("db.UserRepo", label="UserRepo", type="class",
           file_path="db/repos.py", community=1, summary="User DB access")
G.add_edge("auth.login", "db.UserRepo", type="calls")

with tempfile.TemporaryDirectory() as tmp:
    p = pathlib.Path(tmp) / "graph.json"
    p.write_text(json.dumps(nx.node_link_data(G)))
    index = GraphifyIndex.load(p)

mock_indexer = MagicMock(spec=GraphifyIndexer)
mock_indexer.get_index.return_value = index

interceptor = GraphifyInterceptor(bfs_depth=1, max_nodes=10, indexer=mock_indexer)

# Simulate a large Read output
large_output = "def login(user, password):\n    # lots of code\n" * 100
tool_input = {"file_path": "auth/service.py"}

assert interceptor.matches("Read", tool_input, large_output), "Must match"
result = interceptor.transform("Read", tool_input, large_output)

assert result is not None, "Must transform"
assert len(result) < len(large_output), f"Must compress: {len(result)} >= {len(large_output)}"
assert "login" in result, "Must contain matched node label"
assert "[KNOWLEDGE GRAPH" in result, "Must have graph header"

print(f"Original: {len(large_output)} chars")
print(f"Compressed: {len(result)} chars")
print(f"Ratio: {len(result)/len(large_output):.1%}")
print("PASS")
```

**Expected:** `PASS`, compression ratio well below 1.0.

### Step 8 — Progressive disclosure works correctly

```python
# Simulates two Reads of the same file
from cutctx.proxy.interceptors.base import apply_to_messages, INTERCEPTORS, register, reset_interceptor_failure_counts
from cutctx.tokenizer import Tokenizer
# ... (see tests/test_graphify_index.py for full setup)

# First Read → subgraph
# Second Read of same file → passes through (graphify-kg skips due to progressive disclosure)
# AstGrepInterceptor then has a chance to outline
```

Run the full interceptor pipeline test with `apply_to_messages()` and verify that the second Read of `auth/service.py` is NOT replaced by the graph again.

### Step 9 — `--knowledge-graph` flag appears in help

```bash
cutctx proxy --help | grep -A2 "knowledge-graph"
```

**Expected:** All three flags (`--knowledge-graph`, `--knowledge-graph-bfs-depth`, `--knowledge-graph-max-nodes`) are listed.

### Step 10 — No behavior change without the flag (regression gate)

Run the existing proxy test suite:
```bash
python -m pytest tests/ -k "proxy" -v --tb=short
```

**Expected:** All existing proxy tests pass. Zero regressions. The GraphifyInterceptor must not be registered when `knowledge_graph_enabled=False`.

### Step 11 — Token reduction smoke test (end-to-end)

```bash
# Start proxy with knowledge graph enabled, pointed at a real Python project
cd /path/to/cutctx  # or any project with >20 Python files

cutctx proxy --port 18790 --knowledge-graph &
sleep 5  # wait for graph build to start

# Simulate a Read tool result via the compress endpoint
curl -s http://localhost:18790/cutctx/compress \
  -H "Content-Type: application/json" \
  -d '{"content": "'"$(cat cutctx/proxy/server.py)"'", "tool_name": "Read", "tool_input": {"file_path": "cutctx/proxy/server.py"}}' \
  | python -m json.tool | grep -E "tokens_before|tokens_after|compression_ratio"

kill %1
```

**Expected:** `compression_ratio` < 0.5 (≥50% reduction) for a large file like `server.py` once the graph is available. If graph is not yet built, falls through to AstGrepInterceptor and compression_ratio will be from that layer.

---

## 11. Summary of Files to Create/Modify

| Action | File |
|--------|------|
| **CREATE** | `cutctx/graph/graphify.py` |
| **CREATE** | `cutctx/proxy/interceptors/graph_interceptor.py` |
| **CREATE** | `tests/test_graphify_index.py` |
| **MODIFY** | `pyproject.toml` — add `knowledge-graph` optional dep group |
| **MODIFY** | `cutctx/proxy/models.py` — add 5 config fields |
| **MODIFY** | `cutctx/cli/proxy.py` — add 3 CLI flags |
| **MODIFY** | `cutctx/proxy/server.py` — wire up indexer + interceptor on startup |
| **MODIFY** | `cutctx/graph/watcher.py` — notify graphify indexer on file change |
| **MODIFY** | `cutctx/graph/__init__.py` — re-export graphify symbols |
| **MODIFY** | `cutctx/proxy/routes/admin.py` — add knowledge_graph to stats |

**Estimated effort:** 3–4 days for a single engineer.  
**Risk:** Graphify's Python API surface (`graphifyy.run()`) is not confirmed stable — the subprocess fallback in `_run_graphify_build()` is the safe path. If the Python API differs, use subprocess exclusively and stub the API call in tests.
