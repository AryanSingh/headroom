"""End-to-end tests for Initiative 2: stack graph → CodeCompressor integration.

Tests the full pipeline from reachability analysis through compression,
using mocked StackGraphManager where the Rust extension is not available.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cutctx.graph.reachability import resolve_entry_points
from cutctx.transforms.code_compressor import CodeAwareCompressor


# =========================================================================
# E2E: resolve_entry_points → CodeCompressor
# =========================================================================


def test_reachability_feeds_code_compressor() -> None:
    """Resolved entry points are passed to the compressor and bodies are preserved."""
    from cutctx.transforms.code_compressor import CodeCompressorConfig

    # Build a resolver mock that returns reachable definitions
    mock_resolver = MagicMock()
    mock_resolver._inner = MagicMock()
    mock_resolver.indexed_paths = {"/src/app.py"}
    mock_resolver._inner.reachable_definitions.return_value = [
        {"target_file": "/src/app.py", "target_line": 5, "target_column": 0,
         "symbol_name": "validate", "confidence": 0.9},
        {"target_file": "/src/app.py", "target_line": 15, "target_column": 0,
         "symbol_name": "helper_func", "confidence": 0.9},
    ]

    query = "debug `process_payment`"
    protected, report = resolve_entry_points(mock_resolver, query, max_depth=5)

    # Check that the entry point and its reachable symbols are protected
    assert "process_payment" in protected
    assert "validate" in protected
    assert "helper_func" in protected

    # Use a config with low min_tokens so test code gets compressed
    config = CodeCompressorConfig(min_tokens_for_compression=30)
    compressor = CodeAwareCompressor(config)

    code = '''\
def process_payment():
    amount = 100
    fee = 5
    total = amount + fee
    validate()
    return total

def validate():
    x = 1
    y = 2
    return x > 0

def helper_func():
    a = 10
    b = 20
    c = 30
    d = 40
    e = 50
    f = 60
    return a + b + c + d + e + f

def other_stuff():
    p = 1
    q = 2
    r = 3
    s = 4
    t = 5
    u = 6
    v = 7
    return p + q + r + s + t + u + v
'''

    # Without protected symbols, bodies should be compressed
    result_no_protect = compressor.compress(code, language="python")
    assert result_no_protect.compression_ratio < 1.0

    # With protected symbols, keep bodies for protected funcs
    result_protected = compressor.compress(
        code, language="python", protected_symbols=protected,
    )

    # Protected version should keep more content (higher ratio = less compression)
    assert result_protected.compression_ratio >= result_no_protect.compression_ratio

    # Protected symbols should have their bodies preserved
    assert "amount = 100" in result_protected.compressed
    assert "fee = 5" in result_protected.compressed


def test_set_protected_symbols_on_compressor() -> None:
    """The set_protected_symbols method works via instance attribute."""
    compressor = CodeAwareCompressor()

    # Initially None
    assert compressor._protected_symbols is None

    # Set some symbols
    compressor.set_protected_symbols({"main", "helper"})
    assert compressor._protected_symbols == {"main", "helper"}

    # Clear them
    compressor.set_protected_symbols(None)
    assert compressor._protected_symbols is None


def test_compress_with_protected_symbols_passthrough() -> None:
    """When protected_symbols is None, behavior is unchanged."""
    compressor = CodeAwareCompressor()

    code = "x = 1\ny = 2\n"
    result_default = compressor.compress(code, language="python", protected_symbols=None)
    result_no_arg = compressor.compress(code, language="python")
    assert result_default.compressed == result_no_arg.compressed


def test_pre_compress_hook_on_router_config() -> None:
    """The pre_compress_hook on ContentRouterConfig is callable and non-crashing."""
    from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig

    config = ContentRouterConfig()
    assert config.pre_compress_hook is None  # Default

    hook_called = False

    def my_hook(router: object, content: str, context: str) -> None:
        nonlocal hook_called
        hook_called = True

    config.pre_compress_hook = my_hook
    router = ContentRouter(config)

    # Calling compress should invoke the hook
    result = router.compress("hello world")
    assert hook_called
    assert result.compressed == "hello world"  # Too small to compress


def test_pre_compress_hook_does_not_crash() -> None:
    """A failing pre_compress_hook does not crash compression."""
    from cutctx.transforms.content_router import ContentRouter, ContentRouterConfig

    config = ContentRouterConfig()

    def crashing_hook(router: object, content: str, context: str) -> None:
        raise RuntimeError("hook failed")

    config.pre_compress_hook = crashing_hook
    router = ContentRouter(config)

    # Should not raise despite the crashing hook
    result = router.compress("hello world")
    assert result.compressed is not None
