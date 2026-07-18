"""Semantic-quality guarantees for AST code compression.

Two defects surfaced by the 2026-07-18 local benchmark run
(``benchmark_results.md``):

1. ``from __future__ import annotations`` is a distinct tree-sitter node
   (``future_import_statement``) that the Python LangConfig did not treat
   as an import, so reassembly rendered it *after* function definitions —
   syntactically invalid Python.
2. Elided function bodies kept identifier anchors but dropped numeric
   constants (``timeout=10.0``, backoff ``0.25``), so configuration-value
   questions went dark without a CCR retrieval round-trip.
"""

from __future__ import annotations

import pytest

from cutctx.transforms.code_compressor import CodeAwareCompressor

RETRY_HELPER = '''from __future__ import annotations

import asyncio
import httpx


async def fetch_with_retry(client: httpx.AsyncClient, url: str, retries: int = 3) -> dict:
    last_error = None
    for attempt in range(retries):
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            await asyncio.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"request failed after {retries} attempts: {last_error}")


def summarize_user(payload: dict) -> str:
    user = payload.get("user") or {}
    return f"{user.get('name', 'unknown')}<{user.get('email', 'n/a')}>"
'''


@pytest.fixture()
def compressed() -> str:
    pytest.importorskip("tree_sitter_language_pack")
    # These guarantees hold on the AST path. Reset the module-level
    # availability cache so a previous test that ran (or patched) the
    # fallback path cannot leak a stale "unavailable" verdict in here.
    import cutctx.transforms.code_compressor as code_compressor_module

    code_compressor_module._tree_sitter_available = None
    result = CodeAwareCompressor().compress(RETRY_HELPER, language="python")
    return result.compressed


def _first_statement(code: str) -> str:
    for line in code.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def test_future_import_stays_first(compressed: str) -> None:
    assert "from __future__ import annotations" in compressed
    assert _first_statement(compressed) == "from __future__ import annotations"


def test_compressed_python_remains_syntactically_valid(compressed: str) -> None:
    # Strip the trailing CCR retrieval marker comment before parsing; it is
    # a comment and must not be what makes or breaks validity.
    compile(compressed, "<compressed>", "exec")


def test_omitted_numeric_constants_survive_as_anchors(compressed: str) -> None:
    # The elided body's configuration constants must stay visible in the
    # anchor summary so questions like "what is the timeout?" remain
    # answerable without a retrieval round-trip.
    assert "10.0" in compressed
    assert "0.25" in compressed
