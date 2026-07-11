from __future__ import annotations

import json

from cutctx.proxy.handlers.openai.responses import (
    _apply_model_routing_request_overrides,
    _normalize_ws_http_fallback_body,
    _responses_payload_to_routing_messages,
    _sanitize_chatgpt_subscription_responses_body,
    _sanitize_codex_responses_lite_model,
    _strip_namespace_from_upstream_event_text,
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
        "stream_options": {"reasoning_summary_delivery": "sequential_cutoff"},
        "text": {"verbosity": "low"},
    }

    sanitized, stripped = _sanitize_chatgpt_subscription_responses_body(body)

    assert sanitized == {
        "model": "gpt-5.4",
        "input": "hi",
    }
    assert stripped == [
        "client_metadata",
        "generate",
        "prompt_cache_key",
        "stream",
        "stream_options",
        "text",
    ]


def test_strip_namespace_from_upstream_event_text_fixes_dispatcher_collision():
    """Regression: Codex Desktop (cli_version 0.144.0-alpha.4) concatenates

    ``name`` + ``namespace`` without a separator when locally dispatching a
    tool call, so ``{"name": "exec", "namespace": "exec"}`` gets routed to
    a tool literally named "execexec" and fails with "unsupported custom
    tool call: execexec" (or "waitwait" for `wait`) — entirely client-side,
    after the request already succeeded upstream. Confirmed live against a
    real desktop session's transcript.
    """
    event = json.dumps(
        {
            "type": "response.output_item.added",
            "item": {
                "type": "custom_tool_call",
                "id": "ctc_1",
                "call_id": "call_1",
                "name": "exec",
                "namespace": "exec",
            },
        }
    )

    result = json.loads(_strip_namespace_from_upstream_event_text(event))

    assert "namespace" not in result["item"]
    assert result["item"]["name"] == "exec"
    assert result["item"]["call_id"] == "call_1"


def test_strip_namespace_from_upstream_event_text_handles_function_call():
    event = json.dumps(
        {
            "type": "response.output_item.done",
            "item": {
                "type": "function_call",
                "name": "wait",
                "namespace": "wait",
                "arguments": "{}",
                "call_id": "call_2",
            },
        }
    )

    result = json.loads(_strip_namespace_from_upstream_event_text(event))

    assert "namespace" not in result["item"]


def test_strip_namespace_from_upstream_event_text_leaves_other_events_untouched():
    event = json.dumps({"type": "response.completed", "response": {"id": "r_1"}})

    assert _strip_namespace_from_upstream_event_text(event) == event


def test_strip_namespace_from_upstream_event_text_leaves_items_without_namespace_untouched():
    event = json.dumps(
        {
            "type": "response.output_item.added",
            "item": {"type": "custom_tool_call", "name": "exec", "call_id": "call_1"},
        }
    )

    assert _strip_namespace_from_upstream_event_text(event) == event


def test_strip_namespace_from_upstream_event_text_passes_through_malformed_json():
    malformed = "{not valid json"
    assert _strip_namespace_from_upstream_event_text(malformed) == malformed


def test_chatgpt_subscription_sanitizer_strips_namespace_from_custom_tool_call_history():
    """Regression: chatgpt.com rejects replayed conversation history with

    "[ObjectParam] [input[N].namespace] [unknown_parameter] Unknown
    parameter: 'input[N].namespace'." when a ``custom_tool_call`` item
    (e.g. from the desktop app's namespaced Node REPL tool) carries its
    native ``namespace`` field. Confirmed live against a real multi-turn
    desktop session.
    """
    body = {
        "model": "gpt-5.6-terra",
        "input": [
            {"type": "message", "role": "user", "content": "hi"},
            {
                "type": "custom_tool_call",
                "id": "ctc_1",
                "call_id": "call_1",
                "name": "exec",
                "namespace": "exec",
                "input": "text('hi')",
                "status": "completed",
            },
        ],
    }

    sanitized, stripped = _sanitize_chatgpt_subscription_responses_body(body)

    tool_call_item = sanitized["input"][1]
    assert "namespace" not in tool_call_item
    assert tool_call_item["name"] == "exec"
    assert tool_call_item["call_id"] == "call_1"
    assert "input[*].namespace" in stripped


def test_chatgpt_subscription_sanitizer_leaves_non_custom_tool_call_items_untouched():
    body = {
        "model": "gpt-5.5",
        "input": [
            {"type": "message", "role": "user", "content": "hi"},
            {"type": "function_call", "name": "namespace", "call_id": "call_1"},
        ],
    }

    sanitized, stripped = _sanitize_chatgpt_subscription_responses_body(body)

    assert sanitized["input"] == body["input"]
    assert not any(s.startswith("input[") for s in stripped)


def test_chatgpt_subscription_sanitizer_skips_migration_with_reserved_tool():
    """A model-reserved built-in tool (e.g. image_gen.imagegen) is pinned to

    whichever model the client requested. Migrating gpt-5.4 -> gpt-5.5 while
    forwarding that tool unchanged causes upstream to reject with "Function
    'image_gen.imagegen' is reserved for use by this model and must match
    the configured schema." — so the model migration must be skipped
    whenever such a tool is present.
    """
    body = {
        "model": "gpt-5.4",
        "input": "generate a logo",
        "tools": [{"type": "function", "name": "image_gen.imagegen", "parameters": {}}],
    }

    sanitized, stripped = _sanitize_chatgpt_subscription_responses_body(body)

    assert sanitized["model"] == "gpt-5.4"
    assert not any(s.startswith("model:") for s in stripped)


def test_codex_responses_lite_model_sanitizer_preserves_reserved_tool_model():
    body = {
        "model": "gpt-5.6-terra",
        "input": "generate an asset",
        "tools": [{"type": "function", "name": "image_gen.imagegen", "parameters": {}}],
    }

    sanitized, migrated = _sanitize_codex_responses_lite_model(body)

    assert sanitized["model"] == "gpt-5.6-terra"
    assert migrated == []


def test_codex_responses_lite_model_sanitizer_preserves_requested_model():
    sanitized, migrated = _sanitize_codex_responses_lite_model(
        {"model": "gpt-5.6-terra", "input": "hi"}
    )

    assert sanitized["model"] == "gpt-5.6-terra"
    assert migrated == []


def test_codex_responses_lite_model_sanitizer_leaves_supported_model_untouched():
    sanitized, migrated = _sanitize_codex_responses_lite_model(
        {"model": "gpt-5.5", "input": "hi"}
    )

    assert sanitized["model"] == "gpt-5.5"
    assert migrated == []


def test_chatgpt_subscription_sanitizer_preserves_gpt_5_4_mini_over_ws():
    """The WS sanitizer must not replace a caller-requested model with

    gpt-5.5 before the upstream has a chance to accept it.
    """
    sanitized, stripped = _sanitize_chatgpt_subscription_responses_body(
        {"model": "gpt-5.4-mini", "input": "hi"}
    )

    assert sanitized["model"] == "gpt-5.4-mini"
    assert stripped == []


def test_chatgpt_subscription_sanitizer_preserves_unknown_future_model():
    """Unknown future models should be attempted, not preemptively downgraded."""
    sanitized, stripped = _sanitize_chatgpt_subscription_responses_body(
        {"model": "gpt-9000-hypothetical", "input": "hi"}
    )

    assert sanitized["model"] == "gpt-9000-hypothetical"
    assert stripped == []


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

    assert normalized == {"model": "gpt-5.4", "input": "hi"}
    assert stripped == [
        "client_metadata",
        "generate",
    ]


def test_chatgpt_subscription_sanitizer_preserves_supported_request_fields():
    body = {
        "model": "gpt-5.4",
        "input": "hi",
        "tools": [{"type": "function", "name": "lookup", "parameters": {}}],
        "tool_choice": "auto",
        "instructions": "be concise",
        "store": False,
        "stream": True,
    }

    sanitized, _ = _sanitize_chatgpt_subscription_responses_body(body)

    assert sanitized == {
        "model": "gpt-5.4",
        "input": "hi",
        "tools": [{"type": "function", "name": "lookup", "parameters": {}}],
        "tool_choice": "auto",
        "instructions": "be concise",
    }


def test_chatgpt_subscription_sanitizer_is_safe_to_apply_at_final_boundary():
    """Later transforms must not leak subscription-incompatible fields upstream."""
    body, _ = _sanitize_chatgpt_subscription_responses_body(
        {"model": "gpt-5.4", "input": "continue"}
    )
    body["stream"] = True
    body["stream_options"] = {"reasoning_summary_delivery": "sequential_cutoff"}

    final_body, stripped = _sanitize_chatgpt_subscription_responses_body(body)

    assert final_body == {"model": "gpt-5.4", "input": "continue"}
    assert stripped == ["stream", "stream_options"]


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
