from __future__ import annotations

from cutctx.proxy.handlers.openai.responses import (
    _apply_model_routing_request_overrides,
    _normalize_ws_http_fallback_body,
    _responses_payload_to_routing_messages,
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
        "store": False,
        "stream": True,
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

    assert normalized == {"model": "gpt-5.5", "input": "hi", "store": False, "stream": True}
    assert stripped == [
        "client_metadata",
        "generate",
        "model:gpt-5.4->gpt-5.5",
    ]


def test_apply_model_routing_request_overrides_sets_high_reasoning():
    body = {"model": "gpt-5.4-mini", "input": "fix typo"}
    savings_metadata = {
        "model_routing": {
            "request_overrides": {"reasoning": {"effort": "high"}},
        }
    }

    _apply_model_routing_request_overrides(body, savings_metadata)

    assert body["reasoning"] == {"effort": "high"}


def test_apply_model_routing_request_overrides_preserves_existing_reasoning_shape():
    body = {
        "model": "gpt-5.4-mini",
        "input": "fix typo",
        "reasoning": {"summary": "auto"},
    }
    savings_metadata = {
        "model_routing": {
            "request_overrides": {"reasoning": {"effort": "high"}},
        }
    }

    _apply_model_routing_request_overrides(body, savings_metadata)

    assert body["reasoning"] == {"summary": "auto", "effort": "high"}


def test_responses_payload_to_routing_messages_extracts_input_text():
    messages = _responses_payload_to_routing_messages(
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                }
            ]
        }
    )

    assert messages == [{"role": "user", "content": "hi"}]


def test_responses_payload_to_routing_messages_ignores_tool_context_items():
    messages = _responses_payload_to_routing_messages(
        {
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                },
                {
                    "type": "function_call_output",
                    "call_id": "call_1",
                    "output": "large tool output that should not become the task",
                },
                {
                    "type": "reasoning",
                    "summary": [{"text": "hidden chain state"}],
                },
            ]
        }
    )

    assert messages == [{"role": "user", "content": "hi"}]


def test_responses_payload_to_routing_messages_prefers_unpersisted_current_user_item():
    messages = _responses_payload_to_routing_messages(
        {
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                },
                {
                    "id": "msg_old",
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "build an orchestrator with AST parsing and retries",
                        }
                    ],
                },
            ]
        }
    )

    assert messages == [{"role": "user", "content": "hi"}]


def test_responses_payload_to_routing_messages_prefers_current_user_item_when_last():
    messages = _responses_payload_to_routing_messages(
        {
            "input": [
                {
                    "id": "msg_old",
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "build an orchestrator with AST parsing and retries",
                        }
                    ],
                },
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                },
            ]
        }
    )

    assert messages == [{"role": "user", "content": "hi"}]
