"""Tests for the Graphify knowledge-graph compression feature.

Covers GraphifyIndex loading/query, render_subgraph, and GraphifyInterceptor.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("networkx")

import networkx as nx  # noqa: E402

from cutctx.graph.graphify import (  # noqa: E402
    GraphifyIndex,
    GraphifyQueryResult,
    GraphNode,
    graphify_available,
    render_subgraph,
)
from cutctx.proxy.interceptors.graph_interceptor import (  # noqa: E402
    GraphifyInterceptor,
)

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def sample_nx_graph() -> nx.Graph:
    """Build a small networkx graph with typed nodes."""
    g = nx.Graph()
    # Module nodes
    g.add_node("mod:auth", label="auth.py", type="module", file_path="src/auth.py")
    g.add_node("mod:main", label="main.py", type="module", file_path="src/main.py")
    g.add_node("mod:utils", label="utils.py", type="module", file_path="src/utils.py")
    # Function nodes
    g.add_node("func:login", label="login()", type="function", file_path="src/auth.py", summary="Authenticate a user with credentials")
    g.add_node("func:logout", label="logout()", type="function", file_path="src/auth.py", summary="End a user session")
    g.add_node("func:hash_pwd", label="hash_password()", type="function", file_path="src/utils.py", summary="Hash a password using bcrypt")
    g.add_node("func:run", label="run()", type="function", file_path="src/main.py", summary="Application entrypoint")
    # Concept node
    g.add_node("concept:auth", label="Authentication", type="concept", file_path="")
    # Edges
    g.add_edge("mod:auth", "func:login", relationship="contains")
    g.add_edge("mod:auth", "func:logout", relationship="contains")
    g.add_edge("mod:utils", "func:hash_pwd", relationship="contains")
    g.add_edge("mod:main", "func:run", relationship="contains")
    g.add_edge("func:login", "func:hash_pwd", relationship="calls")
    g.add_edge("concept:auth", "func:login", relationship="describes")
    g.add_edge("concept:auth", "func:logout", relationship="describes")
    g.add_edge("mod:auth", "concept:auth", relationship="related")
    g.add_edge("mod:main", "mod:auth", relationship="imports")
    return g


@pytest.fixture
def sample_graph_json(tmp_path: Path, sample_nx_graph: nx.Graph) -> Path:
    """Write a sample node-link graph and return path."""
    data = nx.node_link_data(sample_nx_graph)
    data["version"] = "test-v1"
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# =========================================================================
# TestGraphifyIndex
# =========================================================================


class TestGraphifyIndex:
    """Tests for GraphifyIndex loading and querying."""

    def test_load_valid(self, sample_graph_json: Path) -> None:
        """Load a valid graph.json and verify node/edge counts."""
        idx = GraphifyIndex.load(sample_graph_json)
        assert idx.node_count == 8
        assert idx.edge_count == 9
        assert idx.version == "test-v1"

    def test_load_missing(self) -> None:
        """Loading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            GraphifyIndex.load(Path("/nonexistent/graph.json"))

    def test_load_malformed(self, tmp_path: Path) -> None:
        """Loading invalid JSON raises ValueError."""
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="Failed to parse"):
            GraphifyIndex.load(path)

        # Also test empty dict (not node-link format)
        path2 = tmp_path / "empty.json"
        path2.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Failed to build graph"):
            GraphifyIndex.load(path2)

    def test_query_exact_match(self, sample_graph_json: Path) -> None:
        """Query by exact label substring returns relevant nodes."""
        idx = GraphifyIndex.load(sample_graph_json)
        result = idx.query_subgraph(["login"], bfs_depth=1, max_nodes=20)

        assert len(result.nodes) >= 1
        labels = [n.label for n in result.nodes]
        assert "login()" in labels
        assert result.seed_nodes
        assert result.graph_version == "test-v1"

    def test_query_bfs_follows_edges(self, sample_graph_json: Path) -> None:
        """BFS from a seed node includes neighbors."""
        idx = GraphifyIndex.load(sample_graph_json)
        result = idx.query_subgraph(["login"], bfs_depth=1, max_nodes=20)

        # At bfs_depth=1, should include login() and its immediate neighbors
        labels = [n.label for n in result.nodes]
        # login() neighbors: auth.py (contains), hash_password() (calls),
        # Authentication (describes)
        assert any("auth.py" in l for l in labels), "Expected neighbor auth.py in results"
        assert any("hash_password" in l for l in labels), "Expected neighbor hash_password() in results"

        # At bfs_depth=1 from login(), we should see the edges connecting
        # login to its neighbors
        edge_src_dst = {(e[0], e[1]) for e in result.edges}
        assert any(
            "func:login" in e or "login" in str(e) for e in edge_src_dst
        ), "Expected login edges in result"

    def test_max_nodes_respected(self, sample_graph_json: Path) -> None:
        """Query with max_nodes=1 returns at most 1 node."""
        idx = GraphifyIndex.load(sample_graph_json)
        result = idx.query_subgraph(["a"], bfs_depth=2, max_nodes=1)
        assert len(result.nodes) <= 1

    def test_empty_graph_fallback(self) -> None:
        """Querying an empty graph returns fallback (empty result)."""
        empty = nx.Graph()
        idx = GraphifyIndex(graph=empty, version="empty-v1")
        result = idx.query_subgraph(["nonexistent"], bfs_depth=2, max_nodes=10)
        # No matching nodes -> fallback mode or empty result
        assert result.fallback or len(result.nodes) == 0

    def test_max_nodes_zero_returns_empty(self, sample_nx_graph: nx.Graph) -> None:
        """Query with max_nodes=0 returns no nodes (edge case)."""
        idx = GraphifyIndex(graph=sample_nx_graph, version="test-v1")
        result = idx.query_subgraph(["login"], bfs_depth=2, max_nodes=0)
        assert len(result.nodes) == 0

    def test_bfs_depth_zero_returns_only_seeds(self, sample_nx_graph: nx.Graph) -> None:
        """Query with bfs_depth=0 returns only matching seed nodes, no neighbors."""
        idx = GraphifyIndex(graph=sample_nx_graph, version="test-v1")
        result = idx.query_subgraph(["login"], bfs_depth=0, max_nodes=20)
        # Should contain only the seed node itself, not its neighbors
        labels = [n.label for n in result.nodes]
        assert "login()" in labels
        # bfs_depth=0 means no expansion, so neighbors like auth.py should NOT be present
        assert not any("auth.py" in l for l in labels), (
            "bfs_depth=0 should not include neighbor auth.py"
        )

    def test_self_loop_does_not_crash(self, sample_nx_graph: nx.Graph) -> None:
        """Self-loop edges do not cause duplicate count errors or crashes."""
        # Add a self-loop (node referencing itself)
        sample_nx_graph.add_edge("func:login", "func:login", relationship="self_loop")
        idx = GraphifyIndex(graph=sample_nx_graph, version="test-v1")
        result = idx.query_subgraph(["login"], bfs_depth=1, max_nodes=20)
        # Should complete without error; nodes should be valid
        assert len(result.nodes) > 0
        # No duplicate node IDs in the result
        node_ids = [n.id for n in result.nodes]
        assert len(node_ids) == len(set(node_ids)), "Duplicate node IDs in result"

    def test_no_match_on_populated_graph_uses_fallback(
        self, sample_graph_json: Path
    ) -> None:
        """Querying a populated graph with a non-existent term returns fallback."""
        idx = GraphifyIndex.load(sample_graph_json)
        result = idx.query_subgraph(["xyznonexistent"], bfs_depth=2, max_nodes=10)
        assert result.fallback is True
        # Fallback should return some nodes (top-degree)
        assert len(result.nodes) > 0, "Fallback should return top-degree nodes"


# =========================================================================
# TestRenderSubgraph
# =========================================================================


class TestRenderSubgraph:
    """Tests for render_subgraph()."""

    def test_renders_labels(self) -> None:
        """render_subgraph includes node labels grouped by file."""
        nodes = [
            GraphNode(id="n1", label="login()", node_type="function", file_path="src/auth.py", summary="Auth a user"),
            GraphNode(id="n2", label="auth.py", node_type="module", file_path="src/auth.py"),
        ]
        result = GraphifyQueryResult(nodes=nodes, edges=[], graph_version="v1")
        rendered = render_subgraph(result)
        assert "[KNOWLEDGE GRAPH]" in rendered
        assert "## Relevant Nodes" in rendered
        assert "auth.py" in rendered
        assert "login()" in rendered
        assert "[FUNC]" in rendered
        assert "[MOD]" in rendered

    def test_renders_edges(self) -> None:
        """render_subgraph includes relationship lines."""
        nodes = [
            GraphNode(id="n1", label="func_a", node_type="function", file_path="f.py"),
            GraphNode(id="n2", label="func_b", node_type="function", file_path="f.py"),
        ]
        edges = [("n1", "n2", "calls")]
        result = GraphifyQueryResult(nodes=nodes, edges=edges, graph_version="v1")
        rendered = render_subgraph(result)
        assert "n1 --[calls]--> n2" in rendered

    def test_fallback_returns_original(self) -> None:
        """render_subgraph with empty nodes returns original_content."""
        result = GraphifyQueryResult(nodes=[], graph_version="v1")
        original = "original content here"
        rendered = render_subgraph(result, original_content=original)
        assert rendered == original

    def test_rendered_shorter_than_5000_chars(self) -> None:
        """render_subgraph output is compact (<5000 chars for small graphs)."""
        nodes = [
            GraphNode(id=str(i), label=f"node_{i}", node_type="function", file_path=f"file_{i}.py", summary="x" * 50)
            for i in range(20)
        ]
        edges = [(f"node_{i}", f"node_{i+1}", "calls") for i in range(19)]
        result = GraphifyQueryResult(nodes=nodes, edges=edges, graph_version="v1")
        rendered = render_subgraph(result)
        assert len(rendered) < 5000


# =========================================================================
# TestGraphifyInterceptor
# =========================================================================


class TestGraphifyInterceptor:
    """Tests for GraphifyInterceptor."""

    def test_matches_read_large_output(self) -> None:
        """matches() returns True for Read with large output when index exists."""
        # Create a minimal index
        g = nx.Graph()
        g.add_node("n1", label="test", type="module", file_path="test.py")
        idx = GraphifyIndex(graph=g, version="test")
        interceptor = GraphifyInterceptor(indexer=_FakeIndexer(idx))

        result = interceptor.matches("Read", {"file_path": "test.py"}, "x" * 1000)
        assert result is True

    def test_no_match_small_output(self) -> None:
        """matches() returns False for small output."""
        g = nx.Graph()
        idx = GraphifyIndex(graph=g, version="test")
        interceptor = GraphifyInterceptor(indexer=_FakeIndexer(idx))

        result = interceptor.matches("Read", {"file_path": "x.py"}, "small")
        assert result is False

    def test_no_match_non_target(self) -> None:
        """matches() returns False for non-target tools."""
        g = nx.Graph()
        idx = GraphifyIndex(graph=g, version="test")
        interceptor = GraphifyInterceptor(indexer=_FakeIndexer(idx))

        result = interceptor.matches("Write", {"file_path": "x.py"}, "x" * 1000)
        assert result is False

    def test_transform_returns_smaller_content(self) -> None:
        """transform() returns rendered graph smaller than original."""
        import networkx as nx

        g = nx.Graph()
        g.add_node("n1", label="test_app", type="module", file_path="test.py")
        g.add_node("n2", label="run()", type="function", file_path="test.py", summary="Main entry point")
        g.add_edge("n1", "n2", relationship="contains")
        idx = GraphifyIndex(graph=g, version="test")
        interceptor = GraphifyInterceptor(indexer=_FakeIndexer(idx))

        large_output = "x" * 2000
        result = interceptor.transform("Read", {"file_path": "test.py"}, large_output)
        assert result is not None
        assert len(result) < len(large_output)

    def test_transform_returns_none_without_index(self) -> None:
        """transform() returns None when no index is available."""
        interceptor = GraphifyInterceptor()
        result = interceptor.transform("Read", {"file_path": "x.py"}, "x" * 1000)
        assert result is None

    def test_matches_supports_get_index_only_indexer(self) -> None:
        """matches() accepts lightweight indexers that only expose get_index()."""
        g = nx.Graph()
        g.add_node("n1", label="test", type="module", file_path="test.py")
        idx = GraphifyIndex(graph=g, version="test")
        interceptor = GraphifyInterceptor(indexer=_FakeIndexer(idx))

        assert interceptor.matches("Read", {"file_path": "test.py"}, "x" * 1000) is True

    def test_progressive_disclosure_key(self) -> None:
        """progressive_disclosure_key returns file-path key for Read."""
        interceptor = GraphifyInterceptor()
        key = interceptor.progressive_disclosure_key("Read", {"file_path": "src/main.py"})
        assert key == "graphify:src/main.py"

def test_no_key_for_grep() -> None:
    """progressive_disclosure_key returns None for Grep (no file path)."""
    interceptor = GraphifyInterceptor()
    key = interceptor.progressive_disclosure_key("Grep", {"pattern": "foo"})
    assert key is None


# =========================================================================
# Helpers
# =========================================================================


class _FakeIndexer:
    """Minimal fake indexer for interceptor tests."""

    def __init__(self, index: GraphifyIndex) -> None:
        self._index = index

    def get_index(self) -> GraphifyIndex:
        return self._index


def test_graphify_available_accepts_graphify_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cutctx.graph.graphify as graphify_mod

    original_find_spec = graphify_mod.importlib.util.find_spec

    def fake_find_spec(name: str):  # type: ignore[no-untyped-def]
        if name == "graphifyy":
            return None
        if name == "graphify":
            return object()
        return original_find_spec(name)

    monkeypatch.setattr(graphify_mod.importlib.util, "find_spec", fake_find_spec)

    assert graphify_available() is True
