"""Graphify knowledge-graph compression for cutctx.

Provides:
    graphify_available() / networkx_available() — guarded try/import probes
    GraphNode — dataclass representing a node in the knowledge graph
    GraphifyQueryResult — result of a subgraph query
    GraphifyIndex — loaded graph with BFS query API
    render_subgraph() — compact text representation
    GraphifyIndexer — background builder that caches graph.json
    get_global_indexer() / set_global_indexer() — module-level singleton access
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability probes
# ---------------------------------------------------------------------------


def networkx_available() -> bool:
    """Return True if networkx is installed."""
    try:
        import networkx  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A single node in the knowledge graph."""

    id: str
    label: str
    node_type: str = "NODE"
    file_path: str = ""
    community: str = ""
    degree: int = 0
    summary: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphifyQueryResult:
    """Result of a knowledge-graph subgraph query."""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[tuple[str, str, str]] = field(default_factory=list)
    seed_nodes: list[str] = field(default_factory=list)
    bfs_depth: int = 2
    tokens_estimated: int = 0
    graph_version: str = ""
    fallback: bool = False


# ---------------------------------------------------------------------------
# GraphifyIndex — loaded graph with BFS query API
# ---------------------------------------------------------------------------


class GraphifyIndex:
    """In-memory knowledge graph loaded from a graph.json file.

    Supports BFS-based subgraph queries for term matching.
    """

    def __init__(self, graph: Any, version: str = "") -> None:
        """Store a networkx graph and a version string.

        Args:
            graph: A networkx.Graph instance (duck-typed).
            version: Optional version identifier from the graph build.
        """
        self._graph = graph
        self._version = version
        self._lock = threading.RLock()

    @classmethod
    def load(cls, graph_json_path: Path) -> GraphifyIndex:
        """Load a graph from a JSON file exported by graphify.

        The file must contain a node-link graph as produced by
        ``networkx.node_link_graph``.

        Args:
            graph_json_path: Path to the graph.json file.

        Returns:
            A new GraphifyIndex instance.

        Raises:
            FileNotFoundError: The path does not exist.
            ValueError: The JSON cannot be parsed or does not contain
                a valid node-link graph.
        """
        if not graph_json_path.exists():
            raise FileNotFoundError(f"Graph file not found: {graph_json_path}")

        try:
            raw = json.loads(graph_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Failed to parse graph JSON: {exc}") from exc

        # Check for minimum node-link structure
        if not isinstance(raw, dict):
            raise ValueError("Graph JSON must be a dictionary (node-link format)")

        graph_version = raw.get("version", "")

        try:
            import networkx as nx

            graph = nx.node_link_graph(raw)
        except ImportError:
            raise ValueError("networkx is required to load graph files") from None
        except Exception as exc:
            raise ValueError(f"Failed to build graph from node-link data: {exc}") from exc

        return cls(graph=graph, version=graph_version)

    def query_subgraph(
        self,
        seed_terms: list[str],
        bfs_depth: int = 2,
        max_nodes: int = 40,
    ) -> GraphifyQueryResult:
        """Find a subgraph around nodes matching *seed_terms*.

        Uses case-insensitive substring matching against node labels.
        Expands via BFS from each matching seed node, collects results,
        sorts by degree, truncates to *max_nodes*, and returns as a
        ``GraphifyQueryResult``.

        Args:
            seed_terms: List of search terms (case-insensitive substring).
            bfs_depth: BFS expansion depth from each seed node.
            max_nodes: Maximum number of nodes in the result.

        Returns:
            A GraphifyQueryResult with nodes, edges, and metadata.
        """
        max_nodes = max(max_nodes, 0)
        terms_lower = [t.lower() for t in seed_terms]

        with self._lock:
            try:
                if importlib.util.find_spec("networkx") is None:
                    raise ImportError("networkx unavailable")
            except ImportError:
                # NetworkX not available — return empty result
                return GraphifyQueryResult(
                    bfs_depth=bfs_depth, graph_version=self._version, fallback=True
                )

            graph = self._graph
            if graph is None:
                return GraphifyQueryResult(
                    bfs_depth=bfs_depth, graph_version=self._version, fallback=True
                )

            # Find seed nodes matching any term
            seed_node_ids: set[str] = set()
            node_label_map: dict[str, str] = {}

            for node_id, data in graph.nodes(data=True):
                label = str(data.get("label", data.get("name", node_id)))
                node_label_map[node_id] = label
                label_lower = label.lower()
                if any(term in label_lower for term in terms_lower):
                    seed_node_ids.add(node_id)

            # If no seed nodes found, fall back to top-degree nodes
            fallback = False
            if not seed_node_ids:
                fallback = True
                seed_node_ids = self._fallback_seeds(terms_lower)

            # BFS from each seed
            collected: set[str] = set(seed_node_ids)
            frontier: set[str] = set(seed_node_ids)
            for _depth in range(bfs_depth):
                if not frontier:
                    break
                next_frontier: set[str] = set()
                for node_id in frontier:
                    try:
                        neighbors = list(graph.neighbors(node_id))
                    except Exception:
                        neighbors = []
                    for nb in neighbors:
                        if nb not in collected:
                            collected.add(nb)
                            next_frontier.add(nb)
                frontier = next_frontier

            # Sort by degree descending
            node_degree_list: list[tuple[str, int]] = []
            for nid in collected:
                try:
                    deg = graph.degree(nid) if hasattr(graph, "degree") else 0
                except Exception:
                    deg = 0
                node_degree_list.append((nid, deg))

            node_degree_list.sort(key=lambda x: -x[1])
            selected_nodes = [nid for nid, _deg in node_degree_list[:max_nodes]]
            selected_set = set(selected_nodes)

            # Build GraphNode list
            nodes_out: list[GraphNode] = []
            for nid in selected_nodes:
                data = dict(graph.nodes[nid]) if nid in graph.nodes else {}
                label = node_label_map.get(nid, str(nid))
                degree = 0
                try:
                    degree = graph.degree(nid) if hasattr(graph, "degree") else 0
                except Exception:
                    pass
                nodes_out.append(
                    GraphNode(
                        id=nid,
                        label=label,
                        node_type=data.get("type", data.get("node_type", "NODE")),
                        file_path=data.get("file_path", data.get("file", "")),
                        community=data.get("community", ""),
                        degree=degree,
                        summary=data.get("summary", data.get("description", "")),
                        raw=data,
                    )
                )

            # Build edge list (only between selected nodes)
            edges_out: list[tuple[str, str, str]] = []
            if hasattr(graph, "edges"):
                try:
                    for u, v, edata in graph.edges(data=True):
                        if u in selected_set and v in selected_set:
                            rel = edata.get(
                                "relationship", edata.get("label", edata.get("type", "related_to"))
                            )
                            if isinstance(rel, bytes):
                                rel = rel.decode("utf-8", errors="replace")
                            edges_out.append((str(u), str(v), str(rel)))
                except Exception:
                    # Duck-typing fallback for non-standard graph types
                    for _u, _v in getattr(graph, "edges", lambda: [])():
                        if callable(getattr(graph, "edges", None)):
                            break

            # Estimate tokens (rough: 3 tokens per node + 2 per edge + overhead)
            tokens_est = len(nodes_out) * 3 + len(edges_out) * 2 + 10

            return GraphifyQueryResult(
                nodes=nodes_out,
                edges=edges_out,
                seed_nodes=sorted(seed_node_ids),
                bfs_depth=bfs_depth,
                tokens_estimated=tokens_est,
                graph_version=self._version,
                fallback=fallback,
            )

    def _fallback_seeds(self, terms_lower: list[str]) -> set[str]:
        """Fallback: return the top-5 nodes sorted by degree.

        Args:
            terms_lower: Lowercase search terms (unused in fallback).

        Returns:
            A set of node IDs for the top-5 highest-degree nodes.
        """
        graph = self._graph
        if graph is None:
            return set()

        try:
            degree_iter = graph.degree() if hasattr(graph, "degree") else []
            sorted_nodes = sorted(degree_iter, key=lambda x: -x[1]) if degree_iter else []
            return {nid for nid, _deg in sorted_nodes[:5]}
        except Exception:
            # If degree lookup fails, return first 5 nodes
            nodes = list(graph.nodes())[:5] if hasattr(graph, "nodes") else []
            return set(nodes)

    @property
    def node_count(self) -> int:
        """Number of nodes in the graph."""
        try:
            return len(self._graph.nodes) if self._graph is not None else 0
        except Exception:
            return 0

    @property
    def edge_count(self) -> int:
        """Number of edges in the graph."""
        try:
            return len(self._graph.edges) if self._graph is not None else 0
        except Exception:
            return 0

    @property
    def version(self) -> str:
        """Graph version string."""
        return self._version


# ---------------------------------------------------------------------------
# Text rendering
# ---------------------------------------------------------------------------


def render_subgraph(result: GraphifyQueryResult, original_content: str = "") -> str:
    """Render a ``GraphifyQueryResult`` as compact text.

    Produces a ``[KNOWLEDGE GRAPH]``-prefixed block with grouped nodes
    and capped relationship lines.  If the result is empty, returns
    the *original_content* unchanged.

    Args:
        result: The query result to render.
        original_content: Fallback content when no nodes are present.

    Returns:
        A string (never larger than the original when *original_content*
        is empty).
    """
    if not result.nodes:
        return original_content

    lines: list[str] = []
    lines.append("[KNOWLEDGE GRAPH]")

    # Type-to-prefix mapping
    type_prefix = {
        "function": "[FUNC]",
        "class": "[CLASS]",
        "module": "[MOD]",
        "concept": "[CONCEPT]",
        "file": "[FILE]",
    }

    # Group nodes by file_path
    by_file: dict[str, list[GraphNode]] = {}
    for node in result.nodes:
        fp = node.file_path or "(global)"
        by_file.setdefault(fp, []).append(node)

    lines.append("")
    lines.append("## Relevant Nodes")
    for file_path, nodes_in_file in sorted(by_file.items()):
        label = file_path if file_path != "(global)" else "Global"
        lines.append(f"  **{label}:**")
        for node in nodes_in_file:
            prefix = type_prefix.get(node.node_type.lower(), "[NODE]")
            summary = node.summary.strip()
            if summary:
                # Truncate summary at 120 chars
                if len(summary) > 120:
                    summary = summary[:117] + "..."
                entry = f"    {prefix} {node.label}: {summary}"
            else:
                entry = f"    {prefix} {node.label}"
            lines.append(entry)

    lines.append("")
    lines.append("## Relationships")
    # Cap edges at 30
    for src, dst, rel in result.edges[:30]:
        lines.append(f"  {src} --[{rel}]--> {dst}")

    if len(result.edges) > 30:
        lines.append(f"  ... and {len(result.edges) - 30} more relationships")

    if result.fallback:
        lines.append("")
        lines.append("[Note: No exact term match found — showing top-degree nodes as context]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GraphifyIndexer — background builder
# ---------------------------------------------------------------------------


class GraphifyIndexer:
    """Builds and caches a knowledge-graph index in the background.

    On ``start()``, loads an existing ``graph.json`` if one is still
    fresh; otherwise schedules a background build via ``graphifyy``.
    """

    MAX_AGE_SECONDS = 3600
    DEBOUNCE_SECONDS = 5.0

    def __init__(
        self,
        project_dir: str | Path,
        output_dir: str | Path = "graphify-out",
        max_age_seconds: int | None = None,
    ) -> None:
        """Initialize the indexer.

        Args:
            project_dir: Root directory of the project to index.
            output_dir: Directory for graph.json output (relative or absolute).
            max_age_seconds: Maximum age (seconds) of an existing graph.json
                before a rebuild is triggered. Defaults to 3600.
        """
        self.project_dir = Path(project_dir).resolve()
        self.output_dir = Path(output_dir)
        if not self.output_dir.is_absolute():
            self.output_dir = self.project_dir / self.output_dir
        self._max_age = max_age_seconds if max_age_seconds is not None else self.MAX_AGE_SECONDS

        self._index: GraphifyIndex | None = None
        self._lock = threading.RLock()
        self._debounce_lock = threading.Lock()
        self._build_lock = threading.Lock()
        self._index_lock = threading.Lock()
        self._build_thread: threading.Thread | None = None
        self._debounce_timer: threading.Timer | None = None
        self._build_count = 0
        self._last_build_time: float = 0.0
        self._start_time: float = 0.0
        self._last_error: str | None = None
        self._build_in_progress = False
        self._stopped = False
        self._started = False

    # -- Lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Start the indexer (non-blocking).

        If a recent graph.json exists, loads it synchronously.
        Otherwise schedules a background build on a daemon thread.
        """
        self._start_time = time.time()
        graph_path = self.output_dir / "graph.json"

        if graph_path.exists():
            age = time.time() - graph_path.stat().st_mtime
            if age < self._max_age:
                try:
                    self._index = GraphifyIndex.load(graph_path)
                    logger.info(
                        "GraphifyIndexer: loaded existing graph (%d nodes, %d edges)",
                        self._index.node_count,
                        self._index.edge_count,
                    )
                    return
                except Exception as exc:
                    logger.warning("GraphifyIndexer: failed to load existing graph: %s", exc)
            else:
                logger.info(
                    "GraphifyIndexer: graph is stale (age=%.0fs, max_age=%ds) — rebuilding",
                    age,
                    self._max_age,
                )

        # Schedule background build
        logger.info("GraphifyIndexer: scheduling background build...")
        self._build()

    def get_index(self) -> GraphifyIndex | None:
        """Return the current graph index, or None if not yet built."""
        with self._lock:
            return self._index

    def schedule_refresh(self) -> None:
        """Schedule a debounced rebuild of the graph.

        Each call resets the debounce timer, preventing a rebuild
        storm during rapid file changes.
        """
        with self._lock:
            if self._stopped:
                return
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(self.DEBOUNCE_SECONDS, self._build)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def stop(self) -> None:
        """Stop the indexer and cancel any pending build."""
        with self._debounce_lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None
        self._stopped = True
        with self._build_lock:
            if self._build_thread and self._build_thread.is_alive():
                self._build_thread.join(timeout=5)
        self._started = False

    # -- Stats --------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        """Return a dict with build and version statistics."""
        idx = self.get_index()
        with self._lock:
            build_count = self._build_count
            last_build = self._last_build_time
            last_error = self._last_error
            build_in_progress = self._build_in_progress
        return {
            "build_count": build_count,
            "last_build_time": last_build,
            "node_count": idx.node_count if idx else 0,
            "edge_count": idx.edge_count if idx else 0,
            "version": idx.version if idx else "",
            "age_seconds": round(time.time() - self._start_time, 1) if self._start_time else 0,
            "available": idx is not None,
            "building": build_in_progress,
            "last_error": last_error,
        }

    def ensure_ready(self) -> GraphifyIndex | None:
        """Best-effort recovery when the index is missing but recoverable."""
        index = self.get_index()
        if index is not None:
            return index

        graph_path = self.output_dir / "graph.json"
        if graph_path.exists():
            try:
                new_index = GraphifyIndex.load(graph_path)
                with self._index_lock:
                    self._index = new_index
                with self._lock:
                    self._last_error = None
                logger.info(
                    "GraphifyIndexer: recovered index from graph.json (%d nodes, %d edges)",
                    new_index.node_count,
                    new_index.edge_count,
                )
                return new_index
            except Exception as exc:
                with self._lock:
                    self._last_error = f"load_failed:{exc.__class__.__name__}"
                logger.warning("GraphifyIndexer: recovery load failed: %s", exc)

        with self._lock:
            build_thread = self._build_thread
            build_in_progress = self._build_in_progress or (
                build_thread is not None and build_thread.is_alive()
            )
        if not build_in_progress:
            self.schedule_refresh()
        return self.get_index()

    # -- Build internals ----------------------------------------------------

    def _build(self) -> None:
        """Run a graph build in a background thread."""
        with self._lock:
            if self._stopped:
                return
            if self._build_thread and self._build_thread.is_alive():
                logger.debug("GraphifyIndexer: build already in progress, skipping")
                return
            self._build_thread = threading.Thread(target=self._build_sync, daemon=True)
            self._build_thread.start()

    def _build_sync(self) -> None:
        """Synchronous build — runs on the background thread."""
        with self._lock:
            self._build_in_progress = True
        try:
            start = time.monotonic()
            logger.info("GraphifyIndexer: starting graph build...")

            # Ensure output dir exists
            self.output_dir.mkdir(parents=True, exist_ok=True)

            success = self._run_graphify_build()

            if not success:
                logger.warning("GraphifyIndexer: graph build returned unsuccessful")
                return

            if self._stopped:
                return

            elapsed = time.monotonic() - start
            graph_path = self.output_dir / "graph.json"

            if graph_path.exists():
                new_index = GraphifyIndex.load(graph_path)
                with self._index_lock:
                    if self._stopped:
                        return
                    self._index = new_index
                with self._lock:
                    self._build_count += 1
                    self._last_build_time = time.time()
                    self._last_error = None
                logger.info(
                    "GraphifyIndexer: build complete (%.1fs, %d nodes, %d edges)",
                    elapsed,
                    new_index.node_count,
                    new_index.edge_count,
                )
            else:
                with self._lock:
                    self._last_error = "graph_json_missing"
                logger.warning(
                    "GraphifyIndexer: build ran but graph.json not found at %s",
                    graph_path,
                )

        except Exception as exc:
            with self._lock:
                self._last_error = exc.__class__.__name__
            logger.error("GraphifyIndexer: build failed: %s", exc, exc_info=True)
        finally:
            with self._lock:
                self._build_in_progress = False

    def _run_graphify_build(self) -> bool:
        """Run the graphify build, preferring the Python API over subprocess.

        Returns True if the build appears to have succeeded.
        """
        # Try Python API first
        if graphify_available():
            try:
                import graphifyy

                # The graphifyy Python API varies; try a common interface.
                if hasattr(graphifyy, "run"):
                    graphifyy.run(
                        project_dir=str(self.project_dir),
                        output_dir=str(self.output_dir),
                    )
                    _graph_json = self.output_dir / "graph.json"
                    if not _graph_json.exists():
                        logger.warning("Graphify API completed but graph.json not found")
                        return False
                    return True

                if hasattr(graphifyy, "build_graph"):
                    graphifyy.build_graph(
                        project_dir=str(self.project_dir),
                        output_path=str(self.output_dir / "graph.json"),
                    )
                    _graph_json = self.output_dir / "graph.json"
                    if not _graph_json.exists():
                        logger.warning("Graphify API completed but graph.json not found")
                        return False
                    return True
            except Exception as exc:
                logger.debug(
                    "GraphifyIndexer: Python API failed, falling back to subprocess: %s",
                    exc,
                )

        # Fallback: subprocess
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "graphifyy.cli",
                    "build",
                    "--project-dir",
                    str(self.project_dir),
                    "--output-dir",
                    str(self.output_dir),
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                return True
            logger.warning(
                "GraphifyIndexer: subprocess exited %d: %s",
                result.returncode,
                (result.stderr or "")[:500],
            )
            return False
        except FileNotFoundError:
            logger.warning("GraphifyIndexer: graphifyy.cli module not found")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("GraphifyIndexer: subprocess timed out after 300s")
            return False
        except Exception as exc:
            logger.warning("GraphifyIndexer: subprocess error: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Module-level global indexer
# ---------------------------------------------------------------------------

_global_indexer: GraphifyIndexer | None = None
_global_indexer_lock = threading.Lock()


def get_global_indexer() -> GraphifyIndexer | None:
    """Return the module-level global ``GraphifyIndexer`` (or None)."""
    with _global_indexer_lock:
        return _global_indexer


def set_global_indexer(indexer: GraphifyIndexer | None) -> None:
    """Set the module-level global ``GraphifyIndexer``.

    Args:
        indexer: A ``GraphifyIndexer`` instance, or None to clear.
    """
    with _global_indexer_lock:
        global _global_indexer
        _global_indexer = indexer


def _graphify_module_name() -> str | None:
    """Return the installed Graphify module name, if any."""
    for name in ("graphifyy", "graphify"):
        if importlib.util.find_spec(name) is not None:
            return name
    return None


def graphify_available() -> bool:
    """Return True if a supported Graphify Python package is installed."""
    return _graphify_module_name() is not None


def _graphify_cli_module_name() -> str:
    module_name = _graphify_module_name()
    return f"{module_name}.cli" if module_name else "graphify.cli"


def _graphify_build_with_alias_support(self: GraphifyIndexer) -> bool:
    """Run graphify build, accepting either ``graphify`` or ``graphifyy``."""
    module_name = _graphify_module_name()
    if module_name:
        try:
            graphify_module = importlib.import_module(module_name)

            if hasattr(graphify_module, "run"):
                graphify_module.run(
                    project_dir=str(self.project_dir),
                    output_dir=str(self.output_dir),
                )
                graph_json = self.output_dir / "graph.json"
                if not graph_json.exists():
                    logger.warning("Graphify API completed but graph.json not found")
                    return False
                return True

            if hasattr(graphify_module, "build_graph"):
                graphify_module.build_graph(
                    project_dir=str(self.project_dir),
                    output_path=str(self.output_dir / "graph.json"),
                )
                graph_json = self.output_dir / "graph.json"
                if not graph_json.exists():
                    logger.warning("Graphify API completed but graph.json not found")
                    return False
                return True
        except Exception as exc:
            logger.debug(
                "GraphifyIndexer: Python API failed, falling back to subprocess: %s",
                exc,
            )

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                _graphify_cli_module_name(),
                "build",
                "--project-dir",
                str(self.project_dir),
                "--output-dir",
                str(self.output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return True
        logger.warning(
            "GraphifyIndexer: subprocess exited %d: %s",
            result.returncode,
            (result.stderr or "")[:500],
        )
        return False
    except FileNotFoundError:
        logger.warning("GraphifyIndexer: graphify CLI module not found")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("GraphifyIndexer: subprocess timed out after 300s")
        return False
    except Exception as exc:
        logger.warning("GraphifyIndexer: subprocess error: %s", exc)
        return False


GraphifyIndexer._run_graphify_build = _graphify_build_with_alias_support
