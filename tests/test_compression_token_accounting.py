"""Compression must be measured in the unit providers bill for.

The router used to count "tokens" as `len(text.split())`. That is not a
rounding error against BPE, it is a different quantity, and it broke the
accept/reject gate on any content that compresses to something with few
spaces.

The case that exposed it: SmartCrusher rewrites a 400-row JSON tool_result as
comma-separated CSV. The CSV contains no spaces, so `.split()` returns 1
against the original's 3600 — a 99.97% "saving". Measured in real tokens on
the serialized wire payload it is 12,801 -> 12,818, i.e. 0.1% *worse*. The
gate accepted it, the proxy inflated the request it was asked to shrink, and
the dashboard reported the inflation as compression.

These tests pin the two invariants that follow:
  1. token counts are BPE, not whitespace words;
  2. a swap is only accepted if it shrinks the *serialized* payload.
"""

from __future__ import annotations

import json

import pytest

from cutctx.transforms.content_router import ContentRouter, _wire_ratio, token_len


def _csv_like() -> str:
    """Comma-separated text: many BPE tokens, almost no whitespace words."""
    # One line, no whitespace at all — this is the shape SmartCrusher emits,
    # and the shape `.split()` scores as a single "token".
    return ",".join(f"{i}:row-{i}:active" for i in range(400))


# ---------------------------------------------------------------------------
# 1. the unit itself
# ---------------------------------------------------------------------------


def test_token_len_is_bpe_not_whitespace_words() -> None:
    text = _csv_like()

    assert len(text.split()) < 10, "fixture must be whitespace-poor to be meaningful"
    assert token_len(text) > 1000
    # The gap is the whole bug: three orders of magnitude apart.
    assert token_len(text) > len(text.split()) * 100


def test_token_len_matches_tiktoken() -> None:
    tiktoken = pytest.importorskip("tiktoken")
    text = "The deployment succeeded. CUTCTX_TIMEOUT is 30 seconds."

    assert token_len(text) == len(tiktoken.get_encoding("cl100k_base").encode(text))


def test_token_len_handles_empty_and_unicode() -> None:
    assert token_len("") == 0
    assert token_len("café ☕ 日本語") > 0


# ---------------------------------------------------------------------------
# 2. the wire is what counts
# ---------------------------------------------------------------------------


def test_wire_ratio_measures_the_serialized_payload() -> None:
    """Quote-dense output escapes badly; the ratio must see that."""
    original = json.dumps([{"id": i, "tags": ["a", "b"]} for i in range(200)])
    quote_heavy = "\n".join(f'{i},"[""a"",""b""]"' for i in range(200))

    # Shorter as a bare string...
    assert len(quote_heavy) < len(original)
    # ...but the ratio judges it after JSON escaping, where it is not a win.
    assert _wire_ratio(original, quote_heavy) > _wire_ratio(original, "tiny")


def test_wire_ratio_rewards_a_genuine_shrink() -> None:
    original = "x" * 5000

    assert _wire_ratio(original, "x" * 100) < 0.5


def test_wire_ratio_is_safe_on_empty_input() -> None:
    assert _wire_ratio("", "anything") == 1.0


# ---------------------------------------------------------------------------
# 3. end-to-end: the router must never inflate what it was asked to shrink
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    ["json_rows", "csv_rows", "html", "logs"],
)
def test_router_never_inflates_the_serialized_payload(kind: str) -> None:
    """Whatever strategy wins, the wire payload must not grow.

    Parameterised across the shapes that route to different compressors so a
    future strategy cannot reintroduce the regression on one content type
    while the others stay green.
    """
    bodies = {
        "json_rows": json.dumps(
            [
                {"id": i, "name": f"row-{i}", "state": "active", "tags": ["a", "b"]}
                for i in range(400)
            ]
        ),
        "csv_rows": _csv_like(),
        "html": "<html><body>"
        + "".join(f"<div class='r'><span>item {i}</span></div>" for i in range(400))
        + "</body></html>",
        "logs": "\n".join(
            f"2026-07-27T10:00:00Z INFO worker-{i % 8} handled req_{i} status=200"
            for i in range(400)
        ),
    }
    content = bodies[kind]

    result = ContentRouter().compress(content)

    before = token_len(json.dumps(content))
    after = token_len(json.dumps(result.compressed))
    assert after <= before, (
        f"{kind}: compression inflated the wire payload {before} -> {after} tokens "
        f"via {result.strategy_used}"
    )
