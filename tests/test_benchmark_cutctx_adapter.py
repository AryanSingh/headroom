from __future__ import annotations

from benchmarks._cutctx_adapter import extract_message_text


def test_extract_message_text_handles_string_content() -> None:
    message = {"role": "tool", "content": "plain text"}
    assert extract_message_text(message, "fallback") == "plain text"


def test_extract_message_text_handles_list_content() -> None:
    message = {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "hello"},
            {"type": "output_text", "content": "world"},
        ],
    }
    assert extract_message_text(message, "fallback") == "hello\nworld"


def test_extract_message_text_falls_back_for_none() -> None:
    message = {"role": "tool", "content": None}
    assert extract_message_text(message, "fallback") == "fallback"
