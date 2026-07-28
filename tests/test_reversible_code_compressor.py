"""Contract tests for reversible code compression.

Source code is the largest incompressible surface the proxy sees, and the
existing `code_aware` path is off because it fails a coding agent in the worst
way: it drops ~a quarter of function-body statements while keeping signatures,
and emits invalid Python on half the files tested. An agent reads a file in
order to edit it, so silent partial removal is worse than no compression.

This compressor is allowed to remove code only because it removes it
*visibly and reversibly*. These tests pin that bargain:

  1. output parses
  2. every elided body is retrievable under the hash in its marker
  3. the skeleton — imports, signatures, decorators, docstrings — survives
  4. it never inflates, and it fails closed on anything it cannot guarantee
"""

from __future__ import annotations

import ast
import re

import pytest

from cutctx.cache.compression_store import get_compression_store
from cutctx.transforms.reversible_code_compressor import ReversibleCodeCompressor

_HASH = re.compile(r"sha256=([0-9a-fA-F]+)")


def _sample(functions: int = 6, body_lines: int = 14) -> str:
    parts = ["import os", "import sys", "", ""]
    for i in range(functions):
        parts.append("@decorator")
        parts.append(f"def handler_{i}(request: dict, context: str) -> dict:")
        parts.append(f'    """Handle case {i}."""')
        for j in range(body_lines):
            parts.append(f"    step_{j} = request.get('k{j}', {j}) + {i}")
        parts.append("    return {'ok': True}")
        parts.append("")
    return "\n".join(parts)


def test_output_always_parses() -> None:
    result = ReversibleCodeCompressor().compress(_sample())

    ast.parse(result.compressed)  # raises if the contract is broken


def test_every_elided_body_is_retrievable() -> None:
    """A marker pointing at nothing is data loss wearing a compression badge."""
    store = get_compression_store()
    result = ReversibleCodeCompressor(ccr_store=store).compress(_sample())
    assert result.changed

    digests = _HASH.findall(result.compressed)
    assert digests, "compressed output carries no retrieval markers"
    for digest in digests:
        entry = store.retrieve(digest)
        assert entry is not None, f"elided body {digest} is not retrievable"
        assert entry.original_content.strip(), "retrieved body is empty"


def test_retrieved_body_is_the_original_source() -> None:
    store = get_compression_store()
    source = _sample(functions=2)
    result = ReversibleCodeCompressor(ccr_store=store).compress(source)

    for digest in _HASH.findall(result.compressed):
        body = store.retrieve(digest).original_content
        assert body in source, "retrieved text is not a verbatim span of the input"


def test_skeleton_survives() -> None:
    """Signatures, imports and docstrings are what the agent navigates by."""
    source = _sample(functions=4)
    result = ReversibleCodeCompressor().compress(source)

    before = ast.parse(source)
    after = ast.parse(result.compressed)

    def names(tree: ast.AST) -> set[str]:
        return {
            n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        }

    assert names(before) == names(after)
    assert "import os" in result.compressed
    assert '"""Handle case 0."""' in result.compressed
    for node in ast.walk(after):
        if isinstance(node, ast.FunctionDef):
            assert node.decorator_list, "decorators were dropped"
            assert node.args.args, "signature arguments were dropped"


def test_marker_is_visible_to_the_model() -> None:
    """Silent removal is the failure mode. The gap must be self-describing."""
    result = ReversibleCodeCompressor().compress(_sample())

    assert "cutctx:code_elided" in result.compressed
    assert "retrieve to view" in result.compressed


def test_it_actually_saves_on_real_source() -> None:
    from pathlib import Path

    from cutctx.transforms.content_router import token_len

    source = Path("cutctx/transforms/reversible_code_compressor.py").read_text()
    result = ReversibleCodeCompressor().compress(source)

    assert result.changed
    assert token_len(result.compressed) < token_len(source) * 0.85


def test_never_inflates() -> None:
    from cutctx.transforms.content_router import token_len

    for functions in (1, 3, 8):
        source = _sample(functions=functions)
        result = ReversibleCodeCompressor().compress(source)
        assert token_len(result.compressed) <= token_len(source)


def test_small_bodies_are_left_alone() -> None:
    source = "def tiny(a):\n    return a + 1\n"

    result = ReversibleCodeCompressor().compress(source)

    assert not result.changed
    assert result.reason == "no_elidable_bodies"


def test_non_python_is_returned_untouched() -> None:
    """Guess with a regex here and you corrupt somebody's file.

    The fixture has to be genuinely unparseable as Python. A JSON
    object literal is *not* — `{"k": [1, 2]}` parses fine as a dict
    display — so using one asserts the wrong branch.
    """
    source = "function handler(req) {\n  const x = req.body;\n  return x;\n}\n"

    result = ReversibleCodeCompressor().compress(source)

    assert not result.changed
    assert result.reason == "not_python"


def test_fails_closed_when_nothing_can_be_stored() -> None:
    """No retrieval path means no elision — the body stays inline."""

    class _Broken:
        def store(self, *a: object, **k: object) -> str:
            raise RuntimeError("store is down")

    source = _sample()
    result = ReversibleCodeCompressor(ccr_store=_Broken()).compress(source)

    assert not result.changed
    assert result.reason == "storage_unavailable"


@pytest.mark.parametrize("source", ["", "   \n\n  "])
def test_empty_input_is_safe(source: str) -> None:
    assert ReversibleCodeCompressor().compress(source).compressed == source
