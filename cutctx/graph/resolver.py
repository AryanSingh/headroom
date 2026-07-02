"""Stack-graph-based code navigation resolver.

Provides a Python facade over the Rust StackGraphManager, integrating
it with Cutctx's code-graph system.

Usage:
    resolver = StackGraphResolver()
    resolver.index_project("/path/to/project")
    result = resolver.resolve("src/main.py", 42, 10)
    # result = {target_file, target_line, target_column, symbol_name, confidence}
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def stack_graph_available() -> bool:
    """Check whether the Rust StackGraphManager is available."""
    try:
        from cutctx._core import StackGraphManager  # noqa: F401

        return True
    except ImportError:
        return False


class StackGraphResolver:
    """Cross-file code navigation using stack graphs.

    Acts as the Python interface to the Rust StackGraphManager,
    handling project-wide indexing, incremental updates, and
    integration with the proxy pipeline.
    """

    def __init__(self) -> None:
        if not stack_graph_available():
            raise ImportError(
                "StackGraphManager not available. The Rust extension may not be built. "
                "Run: maturin develop -m crates/cutctx-py/Cargo.toml"
            )
        from cutctx._core import StackGraphManager as _RustStackGraphManager

        self._inner = _RustStackGraphManager()
        self._indexed_paths: set[str] = set()
        self._generation: int = 0

    def index_file(self, path: str | Path, source: str | None = None) -> bool:
        """Index a single file. If source is None, reads from disk."""
        path_str = str(path)
        if source is None:
            try:
                file_size = Path(path).stat().st_size
            except OSError as e:
                logger.warning("StackGraph: cannot stat %s: %s", path, e)
                return False
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
            if file_size > MAX_FILE_SIZE:
                logger.warning(
                    "StackGraph: skipping %s — size %d bytes exceeds 10 MB limit",
                    path, file_size,
                )
                return False
            try:
                source = Path(path).read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("StackGraph: cannot read %s: %s", path, e)
                return False
        try:
            self._inner.add_file(path_str, source)
            self._indexed_paths.add(path_str)
            self._generation += 1
            return True
        except ValueError as e:
            logger.warning("StackGraph: failed to index %s: %s", path, e)
            return False

    def reindex_file(self, path: str | Path, source: str | None = None) -> bool:
        """Re-index a single file, replacing any existing index.

        If source is None, reads from disk. This is the method to use
        for incremental updates from the file watcher.
        """
        path_str = str(path)
        if source is None:
            try:
                file_size = Path(path).stat().st_size
            except OSError as e:
                logger.warning("StackGraph: cannot stat %s: %s", path, e)
                return False
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
            if file_size > MAX_FILE_SIZE:
                logger.warning(
                    "StackGraph: skipping %s — size %d bytes exceeds 10 MB limit",
                    path, file_size,
                )
                return False
            try:
                source = Path(path).read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("StackGraph: cannot read %s: %s", path, e)
                return False
        try:
            self._inner.reindex_file(path_str, source)
            self._indexed_paths.add(path_str)
            self._generation += 1
            return True
        except ValueError as e:
            logger.warning("StackGraph: failed to reindex %s: %s", path, e)
            return False

    def index_project(
        self,
        root: str | Path,
        extensions: set[str] | None = None,
        max_files: int = 1000,
    ) -> int:
        """Recursively index a project directory."""
        if extensions is None:
            extensions = {".py", ".js", ".jsx", ".ts", ".tsx"}
        root = Path(root)
        if not root.is_dir():
            logger.error("StackGraph: project root not found: %s", root)
            return 0
        count = 0
        for path in root.rglob("*"):
            if count >= max_files:
                break
            if path.is_file() and path.suffix in extensions:
                if not path.resolve().is_relative_to(root.resolve()):
                    continue
                if self.index_file(path):
                    count += 1
        logger.info("StackGraph: indexed %d files in %s", count, root)
        return count

    def resolve(
        self,
        path: str | Path,
        line: int,
        column: int,
    ) -> dict[str, Any] | None:
        """Resolve a symbol reference to its definition."""
        return self._inner.resolve_reference(str(path), line, column)

    @property
    def file_count(self) -> int:
        return self._inner.file_count()

    @property
    def node_count(self) -> int:
        return self._inner.node_count()

    @property
    def indexed_paths(self) -> set[str]:
        return self._indexed_paths.copy()

    @property
    def generation(self) -> int:
        """Monotonic counter bumped on every successful index/reindex.

        Used by cutctx.graph.reachability to invalidate its per-symbol
        BFS cache when the underlying index changes.
        """
        return self._generation

    def clear(self) -> None:
        self._inner.clear()
        self._indexed_paths.clear()

    def __repr__(self) -> str:
        return f"<StackGraphResolver files={self.file_count}>"
