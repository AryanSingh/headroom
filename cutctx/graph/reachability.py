"""Reachability analysis bridge between StackGraphManager and CodeCompressor.

Extracts function names from user queries, resolves them through the stack graph,
and computes the set of symbols reachable from entry points.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stopword list for heuristic symbol-name extraction
# ---------------------------------------------------------------------------
_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "this", "that", "with", "from", "function",
    "method", "class", "file", "code", "bug", "fix", "debug", "test",
    "error", "issue", "problem", "work", "need", "want", "help",
    "call", "use", "get", "set", "run", "add", "remove", "update",
    "change", "make", "implement", "create", "delete", "find",
    "where", "what", "how", "why", "when", "has", "have", "not",
    "are", "was", "were", "been", "being", "does", "did", "done",
    "doing", "go", "went", "gone", "going", "check", "look",
    "see", "try", "trying", "tell", "ask", "asking", "say",
    "saying", "know", "known", "show", "showing",
})


def extract_symbol_names(text: str) -> list[str]:
    """Extract likely function/symbol names from natural language text.

    Matches:
    - Backtick-quoted identifiers: ``process_payment``
    - CamelCase names: ``ProcessPayment``
    - snake_case names: ``process_payment``
    - Dotted paths: ``module.function``

    Args:
        text: User query text.

    Returns:
        Deduplicated list of extracted symbol names (lowercase for
        snake_case, preserved case for CamelCase/backtick).
    """
    symbols: list[str] = []

    # Backtick-quoted identifiers (highest confidence)
    symbols.extend(re.findall(r"`([a-zA-Z_][a-zA-Z0-9_.]*)`", text))

    # snake_case words (3+ chars, filtered against stopwords)
    snake_words = re.findall(r"\b([a-z]+_[a-z][a-zA-Z0-9]*)\b", text)
    symbols.extend(w for w in snake_words if w.lower() not in _STOPWORDS)

    # CamelCase (two or more PascalCase tokens concatenated)
    camel_words = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", text)
    symbols.extend(w for w in camel_words if w.lower() not in _STOPWORDS)

    return list(set(symbols))


def resolve_entry_points(
    resolver: Any,
    query: str,
    project_root: str | Path | None = None,
    max_depth: int = 5,
) -> tuple[set[str], dict[str, list[dict[str, Any]]]]:
    """Given a user query, extract symbol names and resolve through StackGraph.

    Args:
        resolver: A ``StackGraphResolver`` instance (or ``None``).
        query: The user query string.
        project_root: Optional project root (currently unused, reserved
            for future scoping).
        max_depth: Maximum BFS depth for reachability analysis.

    Returns:
        A tuple of ``(protected_symbols, reachability_report)``:

        - **protected_symbols**: Set of function qualified names to
          preserve during compression (e.g. ``{"process_payment"}``).
        - **reachability_report**: Dict mapping each extracted symbol
          name to the list of reachable definition dicts.

        If the resolver is unavailable, no symbols are found, or any
        error occurs, returns ``(set(), {})``.
    """
    # Gracefully handle missing / unconfigured resolver
    if resolver is None or not hasattr(resolver, "_inner"):
        return set(), {}

    symbols = extract_symbol_names(query)
    if not symbols:
        return set(), {}

    protected: set[str] = set()
    report: dict[str, list[dict[str, Any]]] = {}

    for symbol in symbols:
        reachable: list[dict[str, Any]] = []

        # Try resolution for each indexed file
        indexed_paths: set[str] = getattr(resolver, "indexed_paths", set())
        if not indexed_paths:
            # Fall back: try the query as a short path fragment
            continue

        for file_path in indexed_paths:
            try:
                result = resolver._inner.reachable_definitions(
                    str(file_path), symbol, max_depth
                )
                if result:
                    reachable.extend(result)
                    protected.add(symbol)
                    for ref in result:
                        name = ref.get("symbol_name", "")
                        if name:
                            protected.add(name)
            except Exception:
                continue

        report[symbol] = reachable

    return protected, report
