"""Hosted compression endpoint contract tests."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from cutctx.compress import compress
from cutctx.proxy.server import ProxyConfig, create_app

_HOSTED_RESPONSE_KEYS = {
    "object",
    "input_kind",
    "compatibility_mode",
    "model",
    "text",
    "messages",
    "tokens_before",
    "tokens_after",
    "tokens_saved",
    "compression_ratio",
    "transforms_applied",
}


def _client(*, enabled: bool, api_key: str | None = None) -> TestClient:
    app = create_app(
        ProxyConfig(
            optimize=True,
            cache_enabled=False,
            rate_limit_enabled=False,
            cost_tracking_enabled=False,
            hosted_compression_enabled=enabled,
            hosted_compression_api_key=api_key,
        )
    )
    return TestClient(app)


def _tool_output_messages(text: str) -> list[dict[str, object]]:
    return [
        {"role": "user", "content": "Compress this payload."},
        {
            "role": "tool",
            "tool_call_id": "hosted_compression_input",
            "content": text,
        },
    ]


def _rag_text_messages(text: str) -> list[dict[str, object]]:
    return [{"role": "user", "content": text}]


def _agentic_text_messages(text: str) -> list[dict[str, object]]:
    return [
        {"role": "user", "content": "Continue the task using the latest tool result."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "hosted_compression_input",
                    "type": "function",
                    "function": {"name": "agent_context", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "hosted_compression_input",
            "content": text,
        },
    ]


def _payload(size: int = 120) -> str:
    return json.dumps(
        [
            {
                "id": i,
                "status": "ok" if i % 7 else "error",
                "message": f"repeated hosted compression payload {i % 5}",
                "value": i,
            }
            for i in range(size)
        ],
        indent=2,
    )


def test_hosted_compression_route_disabled_by_default() -> None:
    with _client(enabled=False) as client:
        response = client.post("/v1/hosted/compress", json={"text": "hello"})

    assert response.status_code == 404


def test_hosted_compression_requires_api_key_when_configured() -> None:
    with _client(enabled=True, api_key="hosted-key") as client:
        denied = client.post("/v1/hosted/compress", json={"text": "hello"})
        allowed = client.post(
            "/v1/hosted/compress",
            json={"text": "hello"},
            headers={"x-cutctx-api-key": "hosted-key"},
        )

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_hosted_text_contract_matches_local_pipeline() -> None:
    payload = _payload()
    expected = compress(
        _tool_output_messages(payload),
        model="gpt-4o",
        protect_recent=0,
        min_tokens_to_compress=10,
    )

    with _client(enabled=True) as client:
        response = client.post(
            "/v1/hosted/compress",
            json={
                "text": payload,
                "model": "gpt-4o",
                "protect_recent": 0,
                "min_tokens_to_compress": 10,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert set(data) == _HOSTED_RESPONSE_KEYS
    assert data["object"] == "cutctx.compression"
    assert data["input_kind"] == "text"
    assert data["compatibility_mode"] == "tool_output"
    assert data["model"] == "gpt-4o"
    assert data["messages"] == expected.messages
    assert data["text"] == expected.messages[1]["content"]
    assert data["tokens_before"] == expected.tokens_before
    assert data["tokens_after"] == expected.tokens_after
    assert data["tokens_saved"] == expected.tokens_saved
    assert data["transforms_applied"] == expected.transforms_applied


@pytest.mark.parametrize(
    ("compatibility_mode", "message_factory", "compress_kwargs"),
    [
        (
            "rag_text",
            _rag_text_messages,
            {"compress_user_messages": True, "protect_recent": 0},
        ),
        (
            "agentic_text",
            _agentic_text_messages,
            {},
        ),
    ],
)
def test_hosted_text_compatibility_modes_match_local_pipeline(
    compatibility_mode: str,
    message_factory: Callable[[str], list[dict[str, object]]],
    compress_kwargs: dict[str, object],
) -> None:
    payload = _payload(size=80)
    expected = compress(
        message_factory(payload),
        model="gpt-4o",
        min_tokens_to_compress=10,
        **compress_kwargs,
    )

    with _client(enabled=True) as client:
        response = client.post(
            "/v1/hosted/compress",
            json={
                "text": payload,
                "model": "gpt-4o",
                "compatibility_mode": compatibility_mode,
                "min_tokens_to_compress": 10,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["input_kind"] == "text"
    assert data["compatibility_mode"] == compatibility_mode
    assert data["messages"] == expected.messages
    assert data["tokens_before"] == expected.tokens_before
    assert data["tokens_after"] == expected.tokens_after
    assert data["tokens_saved"] == expected.tokens_saved


def test_hosted_messages_contract_accepts_message_arrays() -> None:
    messages = _tool_output_messages(json.dumps([{"id": i} for i in range(40)]))

    with _client(enabled=True) as client:
        response = client.post(
            "/v1/hosted/compress",
            json={"messages": messages, "model": "gpt-4o", "protect_recent": 0},
        )

    assert response.status_code == 200
    data = response.json()
    assert set(data) == _HOSTED_RESPONSE_KEYS
    assert data["input_kind"] == "messages"
    assert data["compatibility_mode"] == "messages"
    assert isinstance(data["messages"], list)
    assert data["text"] is None


def test_hosted_response_schema_stable_across_text_modes() -> None:
    payload = _payload(size=16)

    with _client(enabled=True) as client:
        responses = {
            mode: client.post(
                "/v1/hosted/compress",
                json={
                    "text": payload,
                    "model": "gpt-4o",
                    "compatibility_mode": mode,
                    "min_tokens_to_compress": 10,
                },
            )
            for mode in ("tool_output", "rag_text", "agentic_text")
        }

    for mode, response in responses.items():
        assert response.status_code == 200, mode
        data = response.json()
        assert set(data) == _HOSTED_RESPONSE_KEYS
        assert data["input_kind"] == "text"
        assert data["compatibility_mode"] == mode


def test_hosted_compression_rejects_unknown_compatibility_mode() -> None:
    with _client(enabled=True) as client:
        response = client.post(
            "/v1/hosted/compress",
            json={"text": "hello", "compatibility_mode": "unknown_mode"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request"


def test_hosted_compression_rejects_missing_payload() -> None:
    with _client(enabled=True) as client:
        response = client.post("/v1/hosted/compress", json={"model": "gpt-4o"})

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request"
