"""Tests for the hosted compression Python client."""

from __future__ import annotations

import pytest

from cutctx.hosted import (
    HostedCompressionClient,
    HostedCompressionError,
    HostedCompressionResult,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        return self._payload


def test_hosted_client_compress_text_posts_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    def fake_post(url, **kwargs):  # type: ignore[no-untyped-def]
        calls.append({"url": url, **kwargs})
        return _FakeResponse(
            200,
            {
                "object": "cutctx.compression",
                "input_kind": "text",
                "compatibility_mode": "tool_output",
                "model": "gpt-4o",
                "text": "compressed",
                "messages": [{"role": "tool", "content": "compressed"}],
                "tokens_before": 100,
                "tokens_after": 40,
                "tokens_saved": 60,
                "compression_ratio": 0.6,
                "transforms_applied": ["router:smart_crusher:0.40"],
            },
        )

    monkeypatch.setattr("httpx.post", fake_post)
    client = HostedCompressionClient("https://cutctx.example/", api_key="secret", timeout=12.5)

    result = client.compress_text(
        "hello",
        model="gpt-4o",
        protect_recent=0,
        min_tokens_to_compress=10,
        compatibility_mode="tool_output",
    )

    assert isinstance(result, HostedCompressionResult)
    assert result.text == "compressed"
    assert result.tokens_saved == 60
    assert result.compatibility_mode == "tool_output"
    assert result.transforms_applied == ["router:smart_crusher:0.40"]
    assert calls == [
        {
            "url": "https://cutctx.example/v1/hosted/compress",
            "json": {
                "text": "hello",
                "model": "gpt-4o",
                "protect_recent": 0,
                "min_tokens_to_compress": 10,
                "compatibility_mode": "tool_output",
            },
            "headers": {"Authorization": "Bearer secret"},
            "timeout": 12.5,
        }
    ]


def test_hosted_client_accepts_compatibility_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, **kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return _FakeResponse(
            200,
            {
                "input_kind": "text",
                "compatibility_mode": "rag_text",
                "model": "gpt-4o",
                "text": "compressed-rag",
                "messages": [{"role": "user", "content": "compressed-rag"}],
                "tokens_before": 30,
                "tokens_after": 10,
                "tokens_saved": 20,
                "compression_ratio": 0.67,
                "transforms_applied": ["router:kompress:0.33"],
            },
        )

    monkeypatch.setattr("httpx.post", fake_post)
    client = HostedCompressionClient("https://cutctx.example")

    result = client.compress_text("hello", compatibility_mode="rag_text")

    assert captured["json"] == {
        "text": "hello",
        "model": "gpt-4o",
        "compatibility_mode": "rag_text",
    }
    assert result.compatibility_mode == "rag_text"


def test_hosted_client_compress_messages_posts_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, **kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return _FakeResponse(
            200,
            {
                "input_kind": "messages",
                "compatibility_mode": "messages",
                "model": "gpt-4o",
                "text": None,
                "messages": kwargs["json"]["messages"],
                "tokens_before": 1,
                "tokens_after": 1,
                "tokens_saved": 0,
                "compression_ratio": 0.0,
                "transforms_applied": [],
            },
        )

    monkeypatch.setattr("httpx.post", fake_post)
    client = HostedCompressionClient("http://localhost:8787")
    messages = [{"role": "user", "content": "hello"}]

    result = client.compress_messages(messages)

    assert captured["json"] == {"messages": messages, "model": "gpt-4o"}
    assert captured["headers"] == {}
    assert result.input_kind == "messages"
    assert result.compatibility_mode == "messages"
    assert result.messages == messages


def test_hosted_client_raises_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "httpx.post",
        lambda *args, **kwargs: _FakeResponse(  # type: ignore[no-untyped-def]
            401,
            {"error": {"message": "Invalid hosted key"}},
        ),
    )
    client = HostedCompressionClient("https://cutctx.example")

    with pytest.raises(HostedCompressionError) as exc_info:
        client.compress_text("hello")

    assert exc_info.value.status_code == 401
    assert "Invalid hosted key" in str(exc_info.value)
    assert exc_info.value.payload == {"error": {"message": "Invalid hosted key"}}


def test_hosted_client_lazy_package_export() -> None:
    import cutctx

    assert cutctx.HostedCompressionClient is HostedCompressionClient
    assert cutctx.HostedCompressionError is HostedCompressionError
    assert "HostedCompressionClient" in dir(cutctx)
