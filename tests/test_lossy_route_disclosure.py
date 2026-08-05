"""Class-level invariant: every lossy route must disclose what it dropped.

Audit 2026-08-03 found the default ``text`` route discarding 99.92% of a
tool_result payload with no omission notice and no retrieval handle, while the
sibling ``log`` route disclosed both. The per-route tests could not catch that
because each one only knew about its own route.

The contract asserted here applies to *every* route the content router can
pick: if the compressed output no longer contains content that was in the
input, then the output MUST carry

1. an omission/compression notice with a count of what was dropped or
   retained, and
2. a CCR retrieval handle that ``cutctx.ccr.markers`` can parse and that
   resolves in the compression store back to the original bytes.

A route that is *not* lossy on its payload passes trivially — the invariant is
about disclosure, not about compressing.
"""

from __future__ import annotations

import json
import re

import pytest

from cutctx import compress
from cutctx.cache.compression_store import get_compression_store
from cutctx.ccr.markers import extract_marker_hashes

MODEL = "claude-sonnet-4-5-20250929"
_TOKEN_RE = re.compile(r"uniqtok[0-9a-f]{6}")
#: "[1199 of 1200 sentences omitted. ...]" / "[1200 lines compressed to 38. ...]"
_COUNTED_DISCLOSURE_RE = re.compile(
    r"\[\d+ (?:of \d+ )?\w+ (?:omitted|compressed to \d+)", re.IGNORECASE
)


def _tok(index: int) -> str:
    return f"uniqtok{index:06x}"


def _prose_payload(n: int = 1200) -> str:
    return "\n\n".join(
        f"Record {i} was processed by the ingest worker and produced the note "
        f"{_tok(i)} while the downstream reconciliation step confirmed the balance."
        for i in range(n)
    )


def _log_payload(n: int = 1200) -> str:
    levels = ("INFO", "WARN", "ERROR")
    return "\n".join(
        f"2026-08-03T10:00:{i % 60:02d}Z {levels[i % 3]} worker seq={i} note={_tok(i)}"
        for i in range(n)
    )


def _json_payload(n: int = 1200) -> str:
    return json.dumps([{"id": i, "status": "active", "note": _tok(i)} for i in range(n)], indent=2)


def _search_payload(n: int = 1200) -> str:
    return "\n".join(
        f"src/module_{i % 20}.py:{i}: def handler_{i}():  # {_tok(i)}" for i in range(n)
    )


def _diff_payload(n: int = 600) -> str:
    lines: list[str] = []
    for i in range(n):
        lines += [
            f"diff --git a/f{i}.py b/f{i}.py",
            f"--- a/f{i}.py",
            f"+++ b/f{i}.py",
            "@@ -1,3 +1,3 @@",
            f"-old_value = '{_tok(i)}'",
            f"+new_value = '{_tok(i)}'",
        ]
    return "\n".join(lines)


def _code_payload(n: int = 400) -> str:
    return "\n".join(
        f"def handler_{i}(payload):\n"
        f"    marker = '{_tok(i)}'\n"
        f"    total = sum(payload)\n"
        f"    return {{'marker': marker, 'total': total}}\n"
        for i in range(n)
    )


ROUTE_PAYLOADS = {
    "text": _prose_payload,
    "log": _log_payload,
    "smart_crusher": _json_payload,
    "search": _search_payload,
    "diff": _diff_payload,
    "code_aware": _code_payload,
}

#: Routes that must actually drop content for this suite to mean anything.
#: Without this the invariant could silently go vacuous if routing changed.
MUST_BE_LOSSY = ("text", "log", "search", "diff")


def _flatten(value: object) -> str:
    chunks: list[str] = []

    def visit(item: object) -> None:
        if isinstance(item, str):
            chunks.append(item)
        elif isinstance(item, dict):
            for nested in item.values():
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return "\n".join(chunks)


def _compress_as_tool_result(payload: str) -> str:
    messages = [
        {"role": "user", "content": "Summarise the ingest run for the reconciliation report."},
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_invariant", "content": payload}
            ],
        },
    ]
    return _flatten(compress(messages, model=MODEL).messages)


@pytest.mark.parametrize("route", sorted(ROUTE_PAYLOADS))
def test_lossy_route_discloses_drop_and_offers_retrieval(route: str) -> None:
    payload = ROUTE_PAYLOADS[route]()
    compressed = _compress_as_tool_result(payload)

    original_tokens = set(_TOKEN_RE.findall(payload))
    surviving_tokens = set(_TOKEN_RE.findall(compressed))
    dropped = original_tokens - surviving_tokens
    if not dropped:
        pytest.skip(f"route {route!r} was not lossy on this payload; nothing to disclose")

    counted = _COUNTED_DISCLOSURE_RE.search(compressed)
    assert counted is not None, (
        f"route {route!r} dropped {len(dropped)} of {len(original_tokens)} items "
        f"with no counted omission notice; tail={compressed[-300:]!r}"
    )

    handles = extract_marker_hashes(compressed)
    assert handles, (
        f"route {route!r} dropped {len(dropped)} of {len(original_tokens)} items "
        f"with no parseable CCR retrieval handle; tail={compressed[-300:]!r}"
    )

    store = get_compression_store()
    recovered = [
        entry.original_content
        for handle in handles
        if (entry := store.retrieve(handle)) is not None
    ]
    assert recovered, f"route {route!r} emitted handles {handles} that resolve to nothing"
    assert any(payload in text for text in recovered), (
        f"route {route!r} handles {handles} resolve, but not to the original payload"
    )


def test_at_least_the_known_lossy_routes_are_still_lossy() -> None:
    """Guard against the invariant above going vacuous via a routing change."""

    still_lossy = []
    for route in MUST_BE_LOSSY:
        payload = ROUTE_PAYLOADS[route]()
        compressed = _compress_as_tool_result(payload)
        if set(_TOKEN_RE.findall(payload)) - set(_TOKEN_RE.findall(compressed)):
            still_lossy.append(route)

    assert still_lossy == list(MUST_BE_LOSSY), (
        f"expected {MUST_BE_LOSSY} to drop content; only {still_lossy} did. "
        "Either routing changed or the disclosure invariant is now untested."
    )
