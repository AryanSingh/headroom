"""Tests for the StackGraphResolver Python facade."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cutctx.graph.resolver import StackGraphResolver, stack_graph_available


class TestStackGraphAvailability:
    """Tests for the stack_graph_available() function."""

    def test_available_returns_bool(self) -> None:
        """Should return a boolean without raising."""
        result = stack_graph_available()
        assert isinstance(result, bool)


class TestStackGraphResolverConstruction:
    """Tests for StackGraphResolver construction."""

    def test_raises_if_core_unavailable(self) -> None:
        """Should raise ImportError if Rust extension not available."""
        with patch("cutctx.graph.resolver.stack_graph_available", return_value=False):
            with pytest.raises(ImportError, match="StackGraphManager not available"):
                StackGraphResolver()

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    @patch("cutctx._core.StackGraphManager", create=True)
    def test_creates_inner_manager(
        self, mock_rust_mgr_cls: MagicMock, mock_avail: MagicMock
    ) -> None:
        """Should create the inner Rust manager."""
        mock_instance = MagicMock()
        mock_instance.file_count.return_value = 0
        mock_instance.node_count.return_value = 0
        mock_rust_mgr_cls.return_value = mock_instance
        resolver = StackGraphResolver()
        assert resolver._inner is not None
        assert resolver.file_count == 0
        assert resolver.node_count == 0
        assert resolver.indexed_paths == set()

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_repr(self, mock_avail: MagicMock) -> None:
        """__repr__ should show file count."""
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.file_count.return_value = 42
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            assert "StackGraphResolver" in repr(resolver)


class TestStackGraphResolverIndexing:
    """Tests for index_file and index_project."""

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_index_file_success(self, mock_avail: MagicMock) -> None:
        """index_file should delegate to inner.add_file."""
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.add_file.return_value = None
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            result = resolver.index_file("/tmp/test.py", "def foo(): pass")
            assert result is True
            mock_instance.add_file.assert_called_once()

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_index_file_with_source_none_reads_disk(
        self, mock_avail: MagicMock, tmp_path: Path
    ) -> None:
        """index_file with source=None should read from disk."""
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.add_file.return_value = None
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            result = resolver.index_file(test_file)
            assert result is True

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_index_file_value_error_returns_false(
        self, mock_avail: MagicMock
    ) -> None:
        """index_file should return False when add_file raises ValueError."""
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.add_file.side_effect = ValueError("unsupported language")
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            result = resolver.index_file("test.rs", "fn foo() {}")
            assert result is False

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_index_project_empty_dir(
        self, mock_avail: MagicMock, tmp_path: Path
    ) -> None:
        """index_project on empty dir should return 0."""
        with patch("cutctx._core.StackGraphManager", create=True):
            resolver = StackGraphResolver()
            count = resolver.index_project(tmp_path)
            assert count == 0

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_index_project_with_files(
        self, mock_avail: MagicMock, tmp_path: Path
    ) -> None:
        """index_project should index matching files."""
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        (tmp_path / "c.txt").write_text("plain text\n")
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.add_file.return_value = None
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            count = resolver.index_project(tmp_path)
            assert count == 2  # Only .py files
            assert len(resolver.indexed_paths) == 2

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_index_project_respects_extensions(
        self, mock_avail: MagicMock, tmp_path: Path
    ) -> None:
        """index_project should respect custom extensions."""
        (tmp_path / "a.js").write_text("const x = 1;\n")
        (tmp_path / "a.ts").write_text("const x: number = 1;\n")
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.add_file.return_value = None
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            count = resolver.index_project(tmp_path, extensions={".js"})
            assert count == 1

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_index_project_respects_max_files(
        self, mock_avail: MagicMock, tmp_path: Path
    ) -> None:
        """index_project should respect max_files limit."""
        for i in range(10):
            (tmp_path / f"f{i}.py").write_text("x = 1\n")
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.add_file.return_value = None
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            count = resolver.index_project(tmp_path, max_files=3)
            assert count == 3


class TestStackGraphResolverResolution:
    """Tests for resolve()."""

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_resolve_returns_none_on_empty_graph(
        self, mock_avail: MagicMock
    ) -> None:
        """resolve should return None when graph has no data."""
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.resolve_reference.return_value = None
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            result = resolver.resolve("test.py", 0, 0)
            assert result is None

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_resolve_returns_dict_on_match(self, mock_avail: MagicMock) -> None:
        """resolve should return a dict when a definition is found."""
        expected = {
            "target_file": "src/helper.py",
            "target_line": 5,
            "target_column": 0,
            "symbol_name": "helper",
            "confidence": 1.0,
        }
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_instance.resolve_reference.return_value = expected
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            result = resolver.resolve("test.py", 3, 0)
            assert result == expected
            assert result["target_file"] == "src/helper.py"


class TestStackGraphResolverCleanup:
    """Tests for clear()."""

    @patch("cutctx.graph.resolver.stack_graph_available", return_value=True)
    def test_clear_resets_state(self, mock_avail: MagicMock) -> None:
        """clear should reset both inner and tracked paths."""
        with patch("cutctx._core.StackGraphManager", create=True) as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            resolver = StackGraphResolver()
            resolver._indexed_paths.add("/tmp/test.py")
            resolver.clear()
            mock_instance.clear.assert_called_once()
            assert len(resolver.indexed_paths) == 0
