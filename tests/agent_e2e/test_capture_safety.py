from __future__ import annotations

import base64
import json

import pytest

from cutctx.capture.fixture_safety import (
    FixtureSafetyError,
    assert_fixture_safe,
    sanitize_capture_record,
)


def test_capture_sanitizer_remaps_references_and_redacts_nested_content() -> None:
    record = {
        "headers": {
            "Authorization": "Bearer sk-secret",
            "ChatGPT-Account-ID": "acct-real",
            "openai-beta": "responses=v1",
        },
        "body": {
            "model": "gpt-5.4",
            "session_id": "019f796c-b3ad-7021-a8e3-8b529e1d9f9c",
            "input": [
                {"role": "user", "content": "Read /Users/alice/private/repo for a@example.com"},
                {
                    "type": "custom_tool_call",
                    "call_id": "call_real_123",
                    "name": "exec",
                    "input": "cat secret.txt",
                },
                {
                    "type": "custom_tool_call_output",
                    "call_id": "call_real_123",
                    "output": "API_KEY=sk-live-secret",
                },
            ],
            "reasoning": {"encrypted_content": "opaque-provider-state"},
            "stream": True,
            "store": False,
        },
    }

    sanitized = sanitize_capture_record(record)

    assert sanitized["headers"]["Authorization"] == "<redacted>"
    assert sanitized["headers"]["ChatGPT-Account-ID"].startswith("acct_fixture_")
    assert sanitized["body"]["session_id"].startswith("session_fixture_")
    call = sanitized["body"]["input"][1]["call_id"]
    assert call.startswith("call_fixture_")
    assert sanitized["body"]["input"][2]["call_id"] == call
    assert sanitized["body"]["stream"] is True
    assert sanitized["body"]["store"] is False
    assert sanitized["body"]["reasoning"]["encrypted_content"].startswith("encrypted_fixture_")
    assert_fixture_safe(sanitized)


def test_secret_scanner_refuses_unredacted_fixtures() -> None:
    with pytest.raises(FixtureSafetyError, match="secret"):
        assert_fixture_safe({"headers": {"authorization": "Bearer sk-test-unredacted"}})
    with pytest.raises(FixtureSafetyError, match="prompt"):
        assert_fixture_safe({"messages": [{"role": "user", "content": "unredacted prompt"}]})


def test_sanitized_fixture_is_deterministic() -> None:
    record = {"body": {"request_id": "req-real", "content": "hello world"}}
    assert json.dumps(sanitize_capture_record(record), sort_keys=True) == json.dumps(
        sanitize_capture_record(record), sort_keys=True
    )


def test_encoded_bodies_and_images_are_replaced_not_copied() -> None:
    private = base64.b64encode(b"private prompt from person@example.com").decode()
    sanitized = sanitize_capture_record(
        {
            "request_body_b64": private,
            "body": {
                "image_url": f"data:image/png;base64,{private}",
                "source": {"type": "base64", "data": private},
            },
        }
    )

    serialized = json.dumps(sanitized)
    assert private not in serialized
    base64.b64decode(sanitized["request_body_b64"], validate=True)
    assert sanitized["body"]["image_url"].startswith("data:image/png;base64,")
