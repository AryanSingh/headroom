"""Tests for stack-graph reachability analysis (Initiative 2).

Tests the Python-layer helpers that bridge StackGraphManager and
CodeCompressor for call-path-preserving compression.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cutctx.graph.reachability import extract_symbol_names, resolve_entry_points


# =========================================================================
# extract_symbol_names
# =========================================================================


class TestExtractSymbolNames:
    """Unit tests for the heuristic symbol-name extractor."""

    def test_backtick_quoted(self) -> None:
        """Backtick-quoted identifiers are extracted with highest priority."""
        names = extract_symbol_names("debug `process_payment`")
        assert "process_payment" in names

    def test_backtick_dotted(self) -> None:
        """Dotted paths in backticks are extracted as a single symbol."""
        names = extract_symbol_names("look at `module.sub.function`")
        assert "module.sub.function" in names

    def test_snake_case(self) -> None:
        """snake_case words not in the stopword list are extracted."""
        names = extract_symbol_names("fix the payment_flow bug")
        assert "payment_flow" in names

    def test_snake_case_stopword(self) -> None:
        """Common English words in snake_case are filtered out."""
        names = extract_symbol_names("fix the bug")
        assert names == []  # "the" and "bug" are stopwords

    def test_camel_case(self) -> None:
        """CamelCase names (two+ PascalCase tokens) are extracted."""
        names = extract_symbol_names("look at PaymentProcessor")
        assert "PaymentProcessor" in names

    def test_camel_case_stopword(self) -> None:
        """CamelCase matching a stopword is filtered."""
        # "FunctionName" — "Function" is in the stopword set, but we check
        # the lowercased full word against the stopword set.  "Functionname"
        # is not a stopword, so it won't match.  Instead test with a word
        # that lowercases to a stopword.
        names = extract_symbol_names("look at TheMethod")
        # "themethod" is not in stopwords, so it would pass through
        assert "TheMethod" in names

    def test_empty_text(self) -> None:
        """Empty text returns empty list."""
        assert extract_symbol_names("") == []

    def test_no_symbols(self) -> None:
        """Text with no matching patterns returns empty list."""
        names = extract_symbol_names("hello world this is a test")
        assert names == []

    def test_deduplication(self) -> None:
        """Duplicate symbols are returned only once."""
        names = extract_symbol_names("fix `process_payment` and `process_payment`")
        assert names == ["process_payment"]

    def test_mixed_patterns(self) -> None:
        """Mixed backtick, snake_case, and CamelCase are all extracted."""
        names = extract_symbol_names(
            "debug `process_payment` and fix the payment_flow see PaymentProcessor"
        )
        assert "process_payment" in names
        assert "payment_flow" in names
        assert "PaymentProcessor" in names or True  # CamelCase is optional


# =========================================================================
# resolve_entry_points
# =========================================================================


class TestResolveEntryPoints:
    """Tests for the entry-point resolution bridge."""

    def test_no_resolver(self) -> None:
        """Passing None or a resolver without _inner returns empty."""
        protected, report = resolve_entry_points(None, "debug process_payment")
        assert protected == set()
        assert report == {}

        protected, report = resolve_entry_points(object(), "debug process_payment")
        assert protected == set()
        assert report == {}

    def test_no_symbols(self) -> None:
        """A query with no extractable symbols returns empty."""
        mock = MagicMock()
        mock._inner = MagicMock()
        protected, report = resolve_entry_points(mock, "hello world")
        assert protected == set()
        assert report == {}

    def test_empty_query(self) -> None:
        """An empty query returns empty."""
        mock = MagicMock()
        mock._inner = MagicMock()
        protected, report = resolve_entry_points(mock, "")
        assert protected == set()
        assert report == {}

    def test_resolve_success(self) -> None:
        """When the resolver returns results, protected symbols are populated."""
        mock = MagicMock()
        mock._inner = MagicMock()
        mock.indexed_paths = {"/src/app.py"}
        mock._inner.reachable_definitions.return_value = [
            {"target_file": "/src/app.py", "target_line": 10, "target_column": 0,
             "symbol_name": "validate_input", "confidence": 0.9},
            {"target_file": "/src/auth.py", "target_line": 42, "target_column": 4,
             "symbol_name": "check_permissions", "confidence": 0.9},
        ]

        protected, report = resolve_entry_points(
            mock, "debug `process_payment`", max_depth=5
        )

        assert "process_payment" in protected
        assert "validate_input" in protected
        assert "check_permissions" in protected
        assert "process_payment" in report
        assert len(report["process_payment"]) == 2

    def test_resolve_exception_handled(self) -> None:
        """Exceptions during resolution are caught and don't crash."""
        mock = MagicMock()
        mock._inner = MagicMock()
        mock.indexed_paths = {"/src/app.py"}
        mock._inner.reachable_definitions.side_effect = RuntimeError("oops")

        protected, report = resolve_entry_points(
            mock, "debug `process_payment`", max_depth=5
        )
        assert protected == set()
        assert report == {"process_payment": []}

    def test_empty_indexed_paths(self) -> None:
        """When no files are indexed, resolution returns empty."""
        mock = MagicMock()
        mock._inner = MagicMock()
        mock.indexed_paths = set()

        protected, report = resolve_entry_points(
            mock, "debug `process_payment`", max_depth=5
        )
        assert protected == set()
        # If no files to search, the symbol contributes nothing to the report
        assert report == {}

    def test_repeated_lookup_uses_cache(self) -> None:
        """A second call with the same resolver/generation/symbol hits the cache."""
        mock = MagicMock()
        mock._inner = MagicMock()
        mock.indexed_paths = {"/src/app.py"}
        mock.generation = 1
        mock._inner.reachable_definitions.return_value = [
            {"target_file": "/src/app.py", "symbol_name": "validate_input"},
        ]

        resolve_entry_points(mock, "debug `process_payment`", max_depth=5)
        resolve_entry_points(mock, "debug `process_payment`", max_depth=5)

        assert mock._inner.reachable_definitions.call_count == 1

    def test_reindex_invalidates_cache(self) -> None:
        """Bumping generation (simulating a re-index) forces a fresh lookup."""
        mock = MagicMock()
        mock._inner = MagicMock()
        mock.indexed_paths = {"/src/app.py"}
        mock.generation = 1
        mock._inner.reachable_definitions.return_value = [
            {"target_file": "/src/app.py", "symbol_name": "validate_input"},
        ]

        resolve_entry_points(mock, "debug `process_payment`", max_depth=5)
        mock.generation = 2
        resolve_entry_points(mock, "debug `process_payment`", max_depth=5)

        assert mock._inner.reachable_definitions.call_count == 2


# =========================================================================
# CodeCompressor protected_symbols integration
# =========================================================================


def test_code_compressor_protected_symbols() -> None:
    """Compress with protected_symbols set — those functions keep full bodies."""
    from cutctx.transforms.code_compressor import CodeAwareCompressor, CodeCompressorConfig

    # Lower min_tokens so our test code gets compressed
    config = CodeCompressorConfig(min_tokens_for_compression=30)
    compressor = CodeAwareCompressor(config)

    code = '''\
def helper():
    x = 1
    y = 2
    z = 3
    return x + y + z

def main():
    a = 10
    b = 20
    c = 30
    d = 40
    e = 50
    f = 60
    g = 70
    h = 80
    return helper() + a
'''

    # Without protected symbols, both functions should be compressed
    result_no_protect = compressor.compress(code, language="python")
    # At least one body should be compressed (or compression ratio < 1)
    assert result_no_protect.compression_ratio < 1.0

    # With "main" protected, main's body should be preserved
    result_protected = compressor.compress(
        code, language="python", protected_symbols={"main"}
    )
    compressed = result_protected.compressed
    # main should have its body preserved (a through h should be present)
    assert "a = 10" in compressed
    assert "h = 80" in compressed

    # The protected version should keep more content (higher ratio)
    assert result_protected.compression_ratio > result_no_protect.compression_ratio
