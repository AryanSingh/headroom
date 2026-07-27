"""CompactTable must actually be reachable for the payloads it was built for.

CompactTableCompressor turns JSON arrays of homogeneous dicts — file listings,
search results, database rows, the most common shape of agent tool output —
into pipe tables, worth ~80% on the wire. It was wired into the router behind
this gate:

    if result.strategy in ("lossless", "passthrough"):

But the Rust SmartCrusher decorates the label with detail, so the value is
``"lossless:table(400->len=13829)"``, never the bare ``"lossless"``. The
equality test could only ever match ``"passthrough"`` — which is what
SmartCrusher returns for logs, prose and CSV, exactly the shapes CompactTable
declines. The compressor was unreachable in production for its entire life.

Behind that sat a second defect: the CCR marker path imported
``cutctx.proxy.compression_store``, a module that has never existed, and the
handler logged it at debug. So even once the gate matched, CompactTable threw
and was swallowed.

These tests pin the contract at both ends: the label parsing, and the fact
that a compressed payload can still be retrieved in full.
"""

from __future__ import annotations

import json
import re

import pytest

from cutctx.transforms.content_router import ContentRouter, token_len


def _rows(n: int = 400) -> str:
    return json.dumps(
        [{"id": i, "name": f"row-{i}", "state": "active", "tags": ["a", "b"]} for i in range(n)]
    )


def _wire(text: str) -> int:
    return token_len(json.dumps(text))


# ---------------------------------------------------------------------------
# 1. the upstream contract that broke
# ---------------------------------------------------------------------------


def test_smart_crusher_decorates_the_lossless_label() -> None:
    """The bare string "lossless" is never emitted — only "lossless:...".

    If a future SmartCrusher stops decorating, this test fails and the prefix
    match in the router can be simplified. If it starts decorating
    "passthrough" too, the router already handles it.
    """
    crusher = ContentRouter()._get_smart_crusher()
    if crusher is None:
        pytest.skip("SmartCrusher extension not built")

    strategy = str(crusher.crush(_rows(), query="", bias=0.0).strategy)

    assert strategy.startswith("lossless")
    assert strategy != "lossless", "bare label would mean the old equality gate worked"
    assert strategy.split(":", 1)[0] == "lossless"


# ---------------------------------------------------------------------------
# 2. the compressor is reachable and wins
# ---------------------------------------------------------------------------


def test_compact_table_is_selected_for_json_arrays() -> None:
    result = ContentRouter().compress(_rows())

    assert "compact_table" in result.strategy_chain, (
        f"CompactTable was not reached; chain was {result.strategy_chain}"
    )


def test_compact_table_beats_the_alternative_substantially() -> None:
    """Guards the regression that made this 0%: a real, large wire saving."""
    payload = _rows()

    result = ContentRouter().compress(payload)

    saving = 1 - _wire(result.compressed) / _wire(payload)
    assert saving > 0.5, f"expected a large saving on tabular JSON, got {saving:.1%}"


@pytest.mark.parametrize("rows", [50, 400])
def test_tabular_json_never_inflates_the_wire(rows: int) -> None:
    payload = _rows(rows)

    result = ContentRouter().compress(payload)

    assert _wire(result.compressed) <= _wire(payload)


def test_non_tabular_content_is_unaffected() -> None:
    """CompactTable must not capture shapes it has no business compressing."""
    prose = "The deployment succeeded. " * 300

    result = ContentRouter().compress(prose)

    assert "compact_table" not in result.strategy_chain


# ---------------------------------------------------------------------------
# 3. compression must stay reversible
# ---------------------------------------------------------------------------


def test_ccr_marker_resolves_to_the_original() -> None:
    """A dropped row is only acceptable if the agent can still fetch it.

    The store key and the hash inside the marker must be identical or
    /v1/retrieve/{hash} 404s on content that is present.
    """
    from cutctx.cache.compression_store import get_compression_store

    router = ContentRouter()
    if not (router.config.ccr_enabled and router.config.ccr_inject_marker):
        pytest.skip("CCR marker injection disabled in this config")
    payload = _rows()

    result = router.compress(payload)

    marker = re.search(r'sha256="([0-9a-fA-F]+)"', result.compressed)
    assert marker is not None, "compressed output carries no retrieval marker"
    entry = get_compression_store().retrieve(marker.group(1))
    assert entry is not None, "marker hash does not resolve in the compression store"
    assert entry.original_content == payload
