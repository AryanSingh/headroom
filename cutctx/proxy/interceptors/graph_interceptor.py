"""Graphify knowledge-graph interceptor.

Replaces large tool outputs with a knowledge-graph subgraph summary of
the files referenced in the tool call, providing the model with compact
semantic context about the codebase instead of verbose raw output.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from cutctx.graph.graphify import (
    GraphifyIndex,
    get_global_indexer,
    render_subgraph,
)

logger = logging.getLogger(__name__)

# Tool names whose outputs may be replaced with graph context.
_TARGET_TOOLS: frozenset[str] = frozenset({
    "Read",
    "read_file",
    "Glob",
    "glob",
    "GlobFiles",
    "Grep",
    "grep",
    "search_files",
    "Bash",
})

# Minimum output size (chars) to consider interception.
_MIN_OUTPUT_CHARS: int = 800

# Maximum output size we attempt to intercept (beyond this, pass through).
_MAX_OUTPUT_CHARS: int = 200_000

# Regex to extract a file path from tool input dicts.
_FILE_PATH_RE: re.Pattern[str] = re.compile(
    r"(?:file_path|path|filePath|filename|file)[\"']?\s*[:=]\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)


class GraphifyInterceptor:
    """Interceptor that replaces large tool outputs with graph knowledge.

    When a tool output exceeds ``min_chars`` and a knowledge graph is
    available, the interceptor extracts seed terms from the tool input,
    queries the graph, and renders a compact subgraph summary.

    The interceptor never enlarges the original output — it returns
    None (pass-through) when the rendered graph is not smaller.
    """

    name = "graphify-kg"

    def __init__(
        self,
        bfs_depth: int = 2,
        max_nodes: int = 40,
        min_chars: int = 800,
        indexer: Any = None,
    ) -> None:
        """Initialize the interceptor.

        Args:
            bfs_depth: BFS depth for subgraph queries.
            max_nodes: Max nodes per query result.
            min_chars: Minimum tool output size (chars) to trigger.
            indexer: An optional GraphifyIndexer instance. If None,
                the global singleton is used.
        """
        self._bfs_depth = bfs_depth
        self._max_nodes = max_nodes
        self._min_chars = min_chars
        self._indexer = indexer

    # -- Internal helpers ---------------------------------------------------

    def _get_index(self) -> GraphifyIndex | None:
        """Return the current graph index.

        Uses the provided indexer, or falls back to the global singleton.
        Returns None if no index is available.
        """
        idx = self._indexer
        if idx is not None:
            if hasattr(idx, "ensure_ready"):
                return idx.ensure_ready()
            if hasattr(idx, "get_index"):
                return idx.get_index()
            if isinstance(idx, GraphifyIndex):
                return idx
            return None
        global_idx = get_global_indexer()
        if global_idx is not None:
            return global_idx.ensure_ready()
        return None

    # -- ToolResultInterceptor protocol ------------------------------------

    def matches(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> bool:
        """Check if this tool output should be intercepted.

        Returns True when:
        1. The tool is in ``_TARGET_TOOLS``.
        2. The output is between ``_MIN_OUTPUT_CHARS`` and ``_MAX_OUTPUT_CHARS``.
        3. A graph index is available.
        """
        if tool_name is None or tool_name not in _TARGET_TOOLS:
            return False

        output_len = len(tool_output)
        if output_len < self._min_chars:
            return False
        if output_len > _MAX_OUTPUT_CHARS:
            return False

        index = self._get_index()
        if index is None:
            return False

        return True

    def transform(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> str | None:
        """Transform the tool output into a knowledge-graph summary.

        Extracts seed terms, queries the subgraph, renders the result.
        Returns None if the rendered result would be larger than the
        original, or if graph resources are unavailable.
        """
        index = self._get_index()
        if index is None:
            return None

        try:
            seed_terms = self._extract_seed_terms(tool_name, tool_input, tool_output)
            if not seed_terms:
                return None

            result = index.query_subgraph(
                seed_terms=seed_terms,
                bfs_depth=self._bfs_depth,
                max_nodes=self._max_nodes,
            )

            rendered = render_subgraph(result, original_content=tool_output)

            # Never enlarge
            if len(rendered) >= len(tool_output):
                return None

            return rendered

        except Exception as exc:
            logger.debug(
                "GraphifyInterceptor transform failed: %s", exc, exc_info=True
            )
            return None

    def progressive_disclosure_key(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
    ) -> str | None:
        """Return a stable key for progressive disclosure.

        For tools that reference a file path, returns
        ``"graphify:<file_path>"``. For non-file tools (Grep, Bash),
        returns None (no progressive disclosure).
        """
        if tool_name is None:
            return None

        path = self._extract_file_path(tool_input)
        if path is None:
            return None

        return f"graphify:{path}"

    # -- Term/path extraction ----------------------------------------------

    @staticmethod
    def _extract_file_path(tool_input: dict[str, Any]) -> str | None:
        """Extract a file path from the tool input dict.

        Tries common keys in order of likelihood.
        """
        for key in ("file_path", "path", "filePath", "filename", "file"):
            val = tool_input.get(key)
            if isinstance(val, str) and val:
                return val
        return None

    @staticmethod
    def _extract_seed_terms(
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> list[str]:
        """Extract up to 10 seed terms from tool input/output.

        Strategy:
        - For Read/read_file: use the file path parts (dir names + stem).
        - For Glob/glob/GlobFiles: use the glob pattern words.
        - For Grep/grep: use the query pattern.
        - For Bash: use the first line of output as seed.
        - For others: fallback to first line of output.

        Terms are deduplicated and capped at 10.
        """
        terms: list[str] = []

        # File-path tools
        if tool_name in ("Read", "read_file"):
            path = None
            for key in ("file_path", "path", "filePath", "filename", "file"):
                val = tool_input.get(key)
                if isinstance(val, str) and val:
                    path = val
                    break
            if path:
                p = Path(path)
                parts = list(p.parts)
                # Include filename stem and parent directories
                terms.append(p.stem)
                for part in parts:
                    if part and part not in (".", "..", "/"):
                        # Split on non-alphanumeric to get meaningful words
                        words = re.split(r"[^a-zA-Z0-9_]+", part)
                        terms.extend(w for w in words if len(w) > 1)

        # Glob tools
        elif tool_name in ("Glob", "glob", "GlobFiles"):
            pattern = tool_input.get("pattern", tool_input.get("glob", ""))
            if isinstance(pattern, str):
                path = Path(pattern)
                parts = list(path.parts)
                for part in parts:
                    words = re.split(r"[^a-zA-Z0-9_]+", part)
                    terms.extend(w for w in words if len(w) > 1)

        # Grep tools
        elif tool_name in ("Grep", "grep"):
            query = tool_input.get("pattern", tool_input.get("query", ""))
            if isinstance(query, str):
                words = re.split(r"[^a-zA-Z0-9_]+", query)
                terms.extend(w for w in words if len(w) > 1)

        # Bash: use command being run + first output line
        elif tool_name == "Bash":
            cmd = tool_input.get("command", tool_input.get("cmd", ""))
            if isinstance(cmd, str):
                words = re.split(r"[^a-zA-Z0-9_]+", cmd)
                terms.extend(w for w in words if len(w) > 1)

        # Generic fallback: first line of output
        if not terms:
            first_line = (tool_output or "").split("\n")[0].strip()
            if first_line:
                words = re.split(r"[^a-zA-Z0-9_]+", first_line)
                terms.extend(w for w in words if len(w) > 1)

        # Deduplicate, lower-case, and cap at 10
        seen: set[str] = set()
        deduped: list[str] = []
        for t in terms:
            t_lower = t.lower().strip()
            if t_lower and t_lower not in seen and len(t_lower) > 1:
                seen.add(t_lower)
                deduped.append(t_lower)
                if len(deduped) >= 10:
                    break

        return deduped
