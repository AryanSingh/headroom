from __future__ import annotations

from cutctx.proxy.handlers.openai.responses import (
    _normalize_ws_http_fallback_body,
    _sanitize_chatgpt_subscription_responses_body,
    _ws_connect_header_kwargs,
)


class _WSModuleAdditional:
    @staticmethod
    async def connect(*, additional_headers=None, **kwargs):
        return additional_headers, kwargs


class _WSModuleExtra:
    @staticmethod
    async def connect(*, extra_headers=None, **kwargs):
        return extra_headers, kwargs


def test_ws_connect_header_kwargs_prefers_additional_headers_when_supported():
    kwargs = _ws_connect_header_kwargs(_WSModuleAdditional, {"x-test": "1"})
    assert kwargs == {"additional_headers": {"x-test": "1"}}


def test_ws_connect_header_kwargs_falls_back_to_extra_headers():
    kwargs = _ws_connect_header_kwargs(_WSModuleExtra, {"x-test": "1"})
    assert kwargs == {"extra_headers": {"x-test": "1"}}


def test_chatgpt_subscription_sanitizer_strips_backend_rejected_fields():
    body = {
        "model": "gpt-5.4",
        "input": "hi",
        "client_metadata": {"thread_id": "t_123"},
        "prompt_cache_key": "pk_123",
        "generate": {"foo": "bar"},
        "stream": True,
        "text": {"verbosity": "low"},
    }

    sanitized, stripped = _sanitize_chatgpt_subscription_responses_body(body)

    assert sanitized == {
        "model": "gpt-5.5",
        "input": "hi",
    }
    assert stripped == [
        "client_metadata",
        "generate",
        "prompt_cache_key",
        "stream",
        "text",
        "model:gpt-5.4->gpt-5.5",
    ]


def test_ws_http_fallback_normalization_unwraps_and_sanitizes_subscription_body():
    parsed = {
        "type": "response.create",
        "response": {
            "model": "gpt-5.4",
            "input": "hi",
            "client_metadata": {"thread_id": "t_123"},
            "generate": {"foo": "bar"},
        },
    }

    normalized, stripped = _normalize_ws_http_fallback_body(
        parsed,
        body=None,
        strip_chatgpt_subscription_fields=True,
    )

    assert normalized == {"model": "gpt-5.5", "input": "hi", "stream": True}
    assert stripped == [
        "client_metadata",
        "generate",
        "model:gpt-5.4->gpt-5.5",
    ]
