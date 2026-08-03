"""Focused conformance tests for shared CCR marker helpers.

The fixtures below are deliberately NOT hand-written hex literals. Until the
audit of 2026-08-03 they were, and every one of them happened to be 16 chars
while ``CCRStore.put()`` emitted 24 — so the whole suite passed while no real
marker could ever be parsed and CCR retrieval was dead end-to-end. Fixtures are
now produced by the real store (or derived from ``CCR_HASH_LENGTH``) so any
future drift between producer and parser fails here.
"""

from __future__ import annotations

from cutctx.ccr.markers import (
    MARKER_PATTERNS,
    extract_marker_hashes,
    extract_marker_hashes_from_payload,
    format_dedup_ref,
)
from cutctx.ccr.store import CCRStore
from cutctx.ccr.tool_injection import CCRToolInjector


def _store_hash(payload: str) -> str:
    """A content address as the production store actually emits it."""

    return CCRStore().put(payload)


HASH_A = _store_hash("alpha payload")
HASH_B = _store_hash("bravo payload")
HASH_C = _store_hash("charlie payload")
HASH_D = _store_hash("delta payload")


def test_store_emitted_hash_is_parseable_by_every_marker_pattern() -> None:
    """Producer/parser contract: the store's key must match every shape.

    This is the regression pin for the 24-vs-16 drift.
    """
    key = _store_hash("some compressible payload")

    markers = [
        f"[100 items compressed to 10. Retrieve more: hash={key}]",
        f"[50 items compressed. hash={key}]",
        f"<<ccr:{key},base64,4.5KB>>",
        f"[Content compressed for reuse. hash={key}]",
    ]
    for marker in markers:
        assert extract_marker_hashes(marker) == [key], f"unparseable marker: {marker}"

    assert any(pattern.search(markers[0]) for pattern in MARKER_PATTERNS)


def test_store_and_parsers_share_one_hash_length_constant() -> None:
    """The producer must not carry its own literal truncation length."""

    from cutctx.ccr.markers import CCR_HASH_LENGTH

    assert len(_store_hash("constant contract payload")) == CCR_HASH_LENGTH


def test_extract_marker_hashes_supports_multiple_marker_shapes() -> None:
    text = "\n".join(
        [
            f"[100 items compressed to 10. Retrieve more: hash={HASH_A}]",
            f"<<ccr:{HASH_B},base64,4.5KB>>",
            f"[50 items compressed. hash={HASH_C}]",
            f"[Content compressed for reuse. hash={HASH_D}]",
        ]
    )

    assert extract_marker_hashes(text) == [HASH_A, HASH_B, HASH_C, HASH_D]


def test_extract_marker_hashes_dedupes_in_text_encounter_order() -> None:
    text = "\n".join(
        [
            f"<<ccr:{HASH_B},base64,4.5KB>>",
            f"[100 items compressed to 10. Retrieve more: hash={HASH_A}]",
            f"[Content compressed for reuse. hash={HASH_B}]",
            f"[50 items compressed. hash={HASH_C}]",
        ]
    )

    assert extract_marker_hashes(text) == [HASH_B, HASH_A, HASH_C]


def test_extract_marker_hashes_from_payload_handles_nested_content() -> None:
    payload = {
        "messages": [
            {"content": f"<<ccr:{HASH_B},base64,4.5KB>>"},
            {
                "content": [
                    {"type": "text", "text": f"[Content compressed. hash={HASH_A}]"},
                    {"type": "tool_result", "content": f"<<ccr:{HASH_B}>>"},
                ]
            },
        ]
    }

    assert extract_marker_hashes_from_payload(payload) == [HASH_B, HASH_A]


def test_format_dedup_ref_uses_shared_pointer_contract() -> None:
    assert format_dedup_ref(HASH_A) == f"[cutctx:ref:{HASH_A}]"


def test_tool_injector_detects_a_marker_carrying_a_real_store_hash() -> None:
    """End-to-end: a marker the store could have emitted must trigger injection."""

    key = _store_hash("payload the agent may want back")
    injector = CCRToolInjector()

    hashes = injector.scan_for_markers(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "content": f"summary\n[1200 items compressed to 1."
                        f" Retrieve more: hash={key}]",
                    }
                ],
            }
        ]
    )

    assert hashes == [key]
    assert injector.has_compressed_content


def test_tool_injector_scanning_delegates_to_shared_marker_parser(
    monkeypatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    def fake_extract_marker_hashes(text: str, *, patterns):
        calls.append((text, patterns))
        return [HASH_A, HASH_B]

    monkeypatch.setattr(
        "cutctx.ccr.tool_injection.extract_marker_hashes",
        fake_extract_marker_hashes,
    )

    injector = CCRToolInjector()
    hashes = injector.scan_for_markers(
        [
            {
                "role": "assistant",
                "content": "marker payload placeholder",
            }
        ]
    )

    assert hashes == [HASH_A, HASH_B]
    assert calls == [
        (
            "marker payload placeholder",
            tuple(injector._marker_patterns),
        )
    ]
