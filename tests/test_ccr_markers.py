"""Focused conformance tests for shared CCR marker helpers."""

from __future__ import annotations

from cutctx.ccr.markers import extract_marker_hashes, format_dedup_ref
from cutctx.ccr.tool_injection import CCRToolInjector


def test_extract_marker_hashes_supports_multiple_marker_shapes() -> None:
    text = "\n".join(
        [
            "[100 items compressed to 10. Retrieve more: hash=aaaabbbbccccdddd]",
            "<<ccr:1111222233334444,base64,4.5KB>>",
            "[50 items compressed. hash=deadbeefdeadbeef]",
            "[Content compressed for reuse. hash=feedfacefeedface]",
        ]
    )

    assert extract_marker_hashes(text) == [
        "aaaabbbbccccdddd",
        "1111222233334444",
        "deadbeefdeadbeef",
        "feedfacefeedface",
    ]


def test_extract_marker_hashes_dedupes_in_text_encounter_order() -> None:
    text = "\n".join(
        [
            "<<ccr:1111222233334444,base64,4.5KB>>",
            "[100 items compressed to 10. Retrieve more: hash=aaaabbbbccccdddd]",
            "[Content compressed for reuse. hash=1111222233334444]",
            "[50 items compressed. hash=deadbeefdeadbeef]",
        ]
    )

    assert extract_marker_hashes(text) == [
        "1111222233334444",
        "aaaabbbbccccdddd",
        "deadbeefdeadbeef",
    ]


def test_format_dedup_ref_uses_shared_pointer_contract() -> None:
    assert format_dedup_ref("abc123def4567890") == "[cutctx:ref:abc123def4567890]"


def test_tool_injector_scanning_delegates_to_shared_marker_parser(
    monkeypatch,
) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    def fake_extract_marker_hashes(text: str, *, patterns):
        calls.append((text, patterns))
        return ["aaaabbbbccccdddd", "1111222233334444"]

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

    assert hashes == ["aaaabbbbccccdddd", "1111222233334444"]
    assert calls == [
        (
            "marker payload placeholder",
            tuple(injector._marker_patterns),
        )
    ]
