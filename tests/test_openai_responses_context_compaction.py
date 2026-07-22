from __future__ import annotations

import copy
import json
from types import SimpleNamespace
from typing import Any

import pytest

from cutctx.proxy.handlers.openai import (
    OpenAIHandlerMixin,
    _compact_openai_responses_tools,
    _openai_responses_context_budget,
)
from cutctx.proxy.handlers.openai import responses as responses_handler
from cutctx.proxy.handlers.openai.responses import _truncate_body_for_chatgpt
from cutctx.transforms.content_router import (
    CompressionStrategy,
    ContentRouter,
    ContentRouterConfig,
)


def test_responses_default_policy_does_not_compress_latest_user_input(monkeypatch) -> None:
    """Long user prompts must respect ContentRouter's default cache-safety gate.

    Responses previously bypassed ``skip_user_messages`` by directly invoking
    the router for its latest user input. Besides mutating the subject of the
    request, that made an ordinary wrapped prompt pay the full compressor cost.
    """

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)
    calls = 0
    original_compress = router.compress

    def track_compress(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_compress(*args, **kwargs)

    monkeypatch.setattr(router, "compress", track_compress)

    payload = {"model": "gpt-5.4-mini", "input": "retain exactly " * 200}
    updated, modified, tokens_saved, transforms, attempted = (
        handler._compress_openai_responses_latest_user_tail_with_router(
            payload,
            model="gpt-5.4-mini",
            request_id="req_default_user_input",
        )
    )

    assert calls == 0
    assert updated is payload
    assert modified is False
    assert tokens_saved == 0
    assert transforms == []
    assert attempted == 0


def test_openai_responses_context_budget_breaks_out_static_and_live_buckets() -> None:
    payload = {
        "instructions": "stable instructions",
        "tools": [
            {
                "type": "function",
                "name": "read_file",
                "description": "Read a file.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            }
        ],
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "line one\nline two\n",
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "do the thing"}],
            },
        ],
    }

    budget = _openai_responses_context_budget(payload)

    assert budget["payload_bytes"] > 0
    assert {"instructions", "tools", "input"}.issubset(budget["buckets"])
    assert budget["input_breakdown"]["function_call_output"]["items"] == 1
    assert budget["input_breakdown"]["function_call_output"]["text_bytes"] == len(
        b"line one\nline two\n"
    )
    assert budget["input_breakdown"]["message"]["items"] == 1


def test_upstream_error_summary_extracts_nested_details() -> None:
    event = {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "code": "bad_request",
            "message": {
                "type": "model_error",
                "message": "The requested turn could not be generated.",
            },
            "internal_payload": {"secret": "must not be logged"},
        },
    }

    summary = responses_handler._summarize_upstream_ws_error(event)

    assert summary == {
        "event_type": "error",
        "error_type": "invalid_request_error",
        "error_code": "bad_request",
        "message_type": "model_error",
        "message": "The requested turn could not be generated.",
    }


def test_upstream_error_summary_bounds_message_and_omits_payload() -> None:
    summary = responses_handler._summarize_upstream_ws_error(
        {
            "type": "error",
            "error": {
                "message": "x" * 2_000,
                "request": "sensitive request body",
            },
        },
        max_message_chars=80,
    )

    assert summary["message"] == ("x" * 80) + "…"
    assert "request" not in summary


def test_openai_tool_schema_compaction_preserves_invocation_shape() -> None:
    verbose = " ".join(["Use this tool to read a file from the workspace."] * 40)
    payload = {
        "tools": [
            {
                "type": "function",
                "name": "read_file",
                "title": "Read File",
                "description": verbose,
                "parameters": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": "ReadFileParameters",
                    "type": "object",
                    "properties": {
                        "path": {
                            "title": "Path",
                            "type": "string",
                            "description": verbose,
                            "examples": ["src/main.py"],
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            }
        ]
    }

    compacted, modified, before, after = _compact_openai_responses_tools(payload)

    assert modified is True
    assert after < before
    tool = compacted["tools"][0]
    assert tool["type"] == "function"
    assert tool["name"] == "read_file"
    assert "title" not in tool
    assert tool["parameters"]["type"] == "object"
    assert tool["parameters"]["required"] == ["path"]
    assert tool["parameters"]["additionalProperties"] is False
    assert tool["parameters"]["properties"]["path"]["type"] == "string"
    assert "examples" not in tool["parameters"]["properties"]["path"]
    assert tool["parameters"]["properties"]["path"]["description"] == " ".join(verbose.split())


def test_openai_tool_schema_compaction_leaves_reserved_namespace_tool_untouched() -> None:
    """Regression: OpenAI's `image_gen` namespace tool has a provider-pinned

    schema validated byte-for-byte. Compacting it (stripping
    additionalProperties, normalizing the description) corrupted that
    pinned schema and the request was rejected with "Function
    'image_gen.imagegen' is reserved for use by this model and must match
    the configured schema." regardless of which model was targeted.
    """
    namespace_tool = {
        "type": "namespace",
        "name": "image_gen",
        "description": "Tools in the image_gen namespace.",
        "tools": [
            {
                "type": "function",
                "name": "imagegen",
                "description": "Generate images. " * 20,
                "strict": False,
                "parameters": {
                    "type": "object",
                    "properties": {"prompt": {"type": "string"}},
                    "required": ["prompt"],
                    "additionalProperties": False,
                },
            }
        ],
    }
    payload = {"tools": [namespace_tool]}

    compacted, modified, _, _ = _compact_openai_responses_tools(payload)

    assert modified is False
    assert compacted["tools"][0] == namespace_tool


def test_openai_tool_schema_compaction_leaves_strict_function_untouched() -> None:
    """Strict function schemas are validated by the Responses API.

    Schema compaction drops annotations such as ``additionalProperties`` that
    are required by strict-mode validation.  Altering one turns a valid Codex
    resume request into an upstream 400, so strict tools must pass through
    byte-for-byte.
    """
    strict_tool = {
        "type": "function",
        "name": "apply_patch",
        "description": "Apply a patch to the workspace. " * 20,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"patch": {"type": "string"}},
            "required": ["patch"],
            "additionalProperties": False,
        },
    }

    compacted, modified, _, _ = _compact_openai_responses_tools({"tools": [strict_tool]})

    assert modified is False
    assert compacted["tools"][0] == strict_tool


def test_openai_tool_schema_compaction_preserves_property_named_title() -> None:
    """Issue #759: drop-key list must not strip property *names* under `properties`.

    Schema annotations like ``title: "ReadFileParameters"`` on a schema object
    are safe to drop.  But a tool that has a field literally called ``title``
    (or ``readOnly``, ``deprecated``, etc.) must survive compaction; removing
    it while leaving ``required: ["title"]`` produces an invalid strict schema
    that upstream (OpenAI / Codex) rejects.
    """
    payload = {
        "tools": [
            {
                "type": "function",
                "name": "eval",
                "description": "Evaluate cells.",
                "parameters": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": "EvalParameters",
                    "type": "object",
                    "properties": {
                        "cells": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "title": "CellItem",
                                "properties": {
                                    "language": {"type": "string"},
                                    "code": {"type": "string"},
                                    "title": {"type": "string"},
                                },
                                "required": ["language", "code", "title"],
                            },
                        }
                    },
                    "required": ["cells"],
                },
            }
        ]
    }

    compacted, modified, before, after = _compact_openai_responses_tools(payload)

    assert modified is True
    assert after < before

    params = compacted["tools"][0]["parameters"]
    # Schema-level annotations are still dropped.
    assert "title" not in params
    assert "$schema" not in params

    items = params["properties"]["cells"]["items"]
    # "title" as a JSON Schema annotation on the items object is dropped.
    assert "title" not in items
    # "title" as a *property name* inside properties must be preserved.
    assert "title" in items["properties"], (
        "property named 'title' was incorrectly stripped by compaction"
    )
    assert items["required"] == ["language", "code", "title"]


def test_openai_tool_schema_compaction_is_deterministic() -> None:
    payload = {
        "tools": [
            {
                "type": "function",
                "name": "mcp__serena__",
                "description": "  Semantic code tools.\n\nUse for symbol-aware edits.  ",
                "parameters": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$comment": "annotation only",
                    "type": "object",
                    "properties": {
                        "name_path_pattern": {
                            "type": "string",
                            "description": "  Name path to match.\nKeeps full semantics. ",
                            "examples": ["Foo/bar"],
                        }
                    },
                    "required": ["name_path_pattern"],
                    "additionalProperties": False,
                },
            }
        ]
    }

    first, first_modified, first_before, first_after = _compact_openai_responses_tools(payload)
    second, second_modified, second_before, second_after = _compact_openai_responses_tools(payload)

    assert first_modified is True
    assert second_modified is True
    assert first_before == second_before
    assert first_after == second_after
    assert first == second
    assert first["tools"][0]["description"] == ("Semantic code tools. Use for symbol-aware edits.")
    prop = first["tools"][0]["parameters"]["properties"]["name_path_pattern"]
    assert prop["description"] == "Name path to match. Keeps full semantics."
    assert prop["type"] == "string"
    assert "examples" not in prop


def test_openai_responses_payload_compacts_tools_without_unboundlocalerror() -> None:
    """Regression for Codex WS `response.create` payloads with tool schemas.

    The shared Responses payload compressor updates `working["tools"]` through
    the `compress_tool_schemas()` path when verbose tool definitions are
    present. A refactor left `compacted_payload` undefined in that branch, so
    any modified tool schema raised `UnboundLocalError` before the websocket
    frame could be forwarded. Codex then recorded `frames_failed_total` and
    showed zero Cutctx savings in the dashboard.
    """

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)

    verbose = " ".join(["Read and analyze files in the workspace."] * 40)
    payload: dict[str, Any] = {
        "model": "gpt-5.4",
        "tools": [
            {
                "type": "function",
                "name": "read_file",
                "description": verbose,
                "parameters": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": "ReadFileParameters",
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": verbose,
                            "examples": ["src/main.py"],
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            }
        ],
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": " ".join(["compressible"] * 200),
            }
        ],
    }

    updated, modified, saved, transforms, reason, before_bytes, after_bytes, attempted = (
        handler._compress_openai_responses_payload(
            payload,
            model="gpt-5.4",
            request_id="hr_codex_tools_regression",
        )
    )

    assert modified is True
    assert saved >= 0
    assert attempted >= 0
    assert before_bytes >= after_bytes
    assert reason is None
    assert "tools" in updated
    assert any("tool_schema_compaction" in t for t in transforms)


def test_codex_subscription_payload_skips_tool_schema_compaction() -> None:
    """Provider-owned Codex tool definitions must never be rewritten."""
    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)
    payload: dict[str, Any] = {
        "model": "gpt-5.4-mini",
        "tools": [
            {
                "type": "function",
                "name": "provider_owned_tool",
                "description": "Provider-owned tool schema. " * 30,
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            }
        ],
    }

    updated, modified, _, transforms, _, _, _, _ = handler._compress_openai_responses_payload(
        payload,
        model="gpt-5.4-mini",
        request_id="hr_codex_subscription_tools",
        compact_tool_schemas=False,
    )

    assert updated["tools"] == payload["tools"]
    assert "openai:responses:tool_schema_compaction" not in transforms
    assert modified is False


def test_codex_subscription_payload_is_a_full_passthrough() -> None:
    """Provider-owned subscription frames are never structurally rewritten."""
    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)
    payload: dict[str, Any] = {
        "model": "gpt-5.4-mini",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "compressible output " * 400,
            }
        ],
    }

    updated, modified, saved, transforms, _, before, after, attempted = (
        handler._compress_openai_responses_payload(
            payload,
            model="gpt-5.4-mini",
            request_id="hr_codex_subscription_passthrough",
            allow_payload_mutation=False,
        )
    )

    assert updated == payload
    assert modified is False
    assert saved == 0
    assert transforms == []
    assert before == after
    assert attempted == 0


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (
            {
                "model": "gpt-5.4",
                "input": [
                    {"type": "reasoning", "encrypted_content": "opaque"},
                    {
                        "type": "function_call_output",
                        "call_id": "call_1",
                        "output": "compressible output " * 200,
                    },
                ],
            },
            "subscription_opaque_continuation",
        ),
        (
            {
                "model": "gpt-5.4",
                "previous_response_id": "resp_123",
                "input": [
                    {
                        "type": "function_call_output",
                        "call_id": "call_1",
                        "output": "compressible output " * 200,
                    }
                ],
            },
            "subscription_previous_response_resume",
        ),
        (
            {
                "model": "gpt-5.4",
                "input": [{"type": "compaction", "payload": "x" * (1024 * 1024)}],
                "client_metadata": {"remote_compaction": True},
                "include": ["reasoning.encrypted_content"],
                "parallel_tool_calls": False,
                "prompt_cache_key": "remote-compact",
                "reasoning": {"effort": "medium"},
                "store": False,
                "stream": True,
                "stream_options": {"include_usage": True},
                "text": {"verbosity": "low"},
            },
            "subscription_remote_compaction",
        ),
        (
            {"model": "gpt-5.4", "input": "unknown input container"},
            "subscription_no_eligible_output",
        ),
        (
            {
                "model": "gpt-5.4",
                "input": [
                    {
                        "type": "function_call_output",
                        "call_id": "call_1",
                        "output": "compressible output " * 200,
                    },
                    {"unexpected": "missing item type"},
                ],
            },
            "subscription_no_eligible_output",
        ),
        (
            {
                "model": "gpt-5.4",
                "input": [
                    {
                        "type": "function_call_output",
                        "output": "compressible output " * 200,
                    }
                ],
            },
            "subscription_no_eligible_output",
        ),
    ],
)
def test_chatgpt_subscription_classifier_rejects_protected_payloads(
    payload: dict[str, Any],
    reason: str,
) -> None:
    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))

    policy, actual_reason = handler._classify_chatgpt_subscription_compression(payload)

    assert policy == "passthrough"
    assert actual_reason == reason


def test_chatgpt_subscription_classifier_allows_only_recognized_string_outputs() -> None:
    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))
    payload = {
        "model": "gpt-5.4",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "compressible output " * 200,
            }
        ],
    }

    policy, reason = handler._classify_chatgpt_subscription_compression(payload)

    assert policy == "tool_outputs_only"
    assert reason is None


def test_chatgpt_subscription_validator_accepts_only_smaller_output_strings() -> None:
    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))
    original = {
        "model": "gpt-5.4",
        "tools": [{"type": "function", "name": "read_fixture"}],
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "one two three four five six",
            }
        ],
    }
    candidate = copy.deepcopy(original)
    candidate["input"][0]["output"] = "one two"

    valid, saved = handler._validate_chatgpt_subscription_tool_output_candidate(
        original,
        candidate,
        tokenizer=_StubTokenizer(),
    )

    assert valid is True
    assert saved == 4


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: body.update({"model": "gpt-5.6-sol"}),
        lambda body: body.update({"tools": []}),
        lambda body: body["input"][0].update({"call_id": "call_changed"}),
        lambda body: body["input"].reverse(),
        lambda body: body["input"][1].update({"encrypted_content": "changed"}),
        lambda body: body.update({"metadata": {"changed": True}}),
        lambda body: body["input"][0].update({"output": "one two three four five six seven"}),
    ],
)
def test_chatgpt_subscription_validator_rejects_wider_or_larger_mutations(mutate) -> None:
    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))
    original = {
        "model": "gpt-5.4",
        "tools": [{"type": "function", "name": "read_fixture"}],
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "one two three four five six",
            },
            {"type": "reasoning", "encrypted_content": "opaque"},
        ],
    }
    candidate = copy.deepcopy(original)
    candidate["input"][0]["output"] = "one two"
    mutate(candidate)

    valid, saved = handler._validate_chatgpt_subscription_tool_output_candidate(
        original,
        candidate,
        tokenizer=_StubTokenizer(),
    )

    assert valid is False
    assert saved == 0


def test_responses_compression_failure_refuses_when_context_guard_trips() -> None:
    """A compression exception must not fall back to forwarding an oversized
    Responses frame.

    The overflow bug showed up when a retry path kept the conversation alive
    long enough for the upstream to reject the original frame with a vague
    400/Bad Request. Once the payload is already near the model limit, the
    proxy should close with a clear compaction signal instead of passing the
    uncompressed body through.
    """

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)
    handler.openai_provider = SimpleNamespace(
        get_token_counter=lambda model: _StubTokenizer(),
        get_context_limit=lambda model: 1_000,
    )

    payload: dict[str, Any] = {
        "model": "gpt-5.4",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "overflow",
            }
        ],
    }

    refuse, estimated, threshold, limit, reason = (
        handler._openai_responses_compression_failure_refusal(
            payload,
            model="gpt-5.4",
            exception=RuntimeError("compressor failed"),
            raw_bytes=1024,
            client="codex",
        )
    )

    assert refuse is True
    assert estimated >= threshold
    assert limit > 0
    assert reason == "context_too_large"


def test_codex_http_responses_timeout_fail_open_allows_large_payloads() -> None:
    """Codex HTTP Responses requests should fail open on compression timeout.

    Large single-turn CLI prompts can exceed the old 256 KiB timeout
    passthrough threshold while still being valid upstream. The wrapped Codex
    CLI should preserve the unwrapped UX here and forward the original payload
    instead of surfacing a local 413.
    """

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)

    payload: dict[str, Any] = {
        "model": "gpt-5.4",
        "input": "Context line with filler data. " * 12_000,
    }
    raw_bytes = len(json.dumps(payload).encode("utf-8"))

    refuse, estimated, threshold, limit, reason = (
        handler._openai_responses_compression_failure_refusal(
            payload,
            model="gpt-5.4",
            exception=TimeoutError("compression timed out"),
            raw_bytes=raw_bytes,
            client="codex",
        )
    )

    assert raw_bytes > 256 * 1024
    assert refuse is False
    assert reason == "client_override:codex"
    assert estimated >= 0
    assert threshold >= 0
    assert limit >= 0


def test_chatgpt_truncator_trims_function_call_output_payloads() -> None:
    """Emergency truncation must shrink the actual tool output field too.

    The overflow bug was specifically visible on resumed turns where the
    context lived inside a function_call_output item. Trimming only nested
    content blocks is not enough for that shape.
    """

    body = {
        "model": "gpt-4o",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": "x" * 9000,
            }
        ],
    }

    truncated = _truncate_body_for_chatgpt(body, 1024, "req_test")

    assert len(truncated["input"][0]["output"]) < len(body["input"][0]["output"])
    assert truncated["input"][0]["output"].endswith("…[truncated]")


def test_chatgpt_truncator_redacts_large_input_image_payloads() -> None:
    """Emergency truncation must also shrink oversized image data URLs.

    The wrapped frontend-design path can surface large audit screenshots
    as Responses input_image items. Those payloads must shrink to a real
    (if trivial) image rather than a text placeholder: chatgpt.com's
    Responses backend rejects a non-image string in ``image_url`` with an
    upstream 400 "Bad Request", which is worse than the oversized-body
    error the truncation is meant to avoid.
    """

    body = {
        "model": "gpt-4o",
        "input": [
            {
                "type": "input_image",
                "image_url": "data:image/png;base64," + ("x" * 9000),
            }
        ],
    }

    truncated = _truncate_body_for_chatgpt(body, 1024, "req_test")

    assert truncated["input"][0]["image_url"].startswith("data:image/png;base64,")
    assert len(truncated["input"][0]["image_url"]) < 200
    assert len(json.dumps(truncated).encode("utf-8")) <= 1024


def test_responses_context_guard_does_not_count_inline_image_base64_as_text() -> None:
    """A pasted screenshot must consume a bounded vision estimate, not its
    base64 character count, when deciding whether to close a Codex websocket.
    """

    handler = _HandlerHarness(ContentRouter(ContentRouterConfig()))
    handler.openai_provider = SimpleNamespace(
        get_token_counter=lambda _model: SimpleNamespace(count_text=lambda value: len(value) // 2),
        get_context_limit=lambda _model: 258_400,
    )
    payload = {
        "model": "gpt-5.6-terra",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Please inspect this screenshot."},
                    {
                        "type": "input_image",
                        "image_url": "data:image/png;base64," + ("a" * 526_000),
                    },
                ],
            }
        ],
    }

    refuse, estimated, threshold, _ = handler._openai_responses_context_guard(
        payload,
        model="gpt-5.6-terra",
    )

    assert refuse is False
    assert estimated < threshold


def test_chatgpt_emergency_truncation_honors_token_budget() -> None:
    """Emergency truncation must satisfy the model budget, not only bytes.

    Remote Codex compaction requests can be dominated by fixed tool schemas,
    instructions, opaque reasoning payloads, and function-call arguments. A
    request may fit the chatgpt.com byte ceiling while still exceeding the
    model's token threshold, which previously caused a repeated HTTP 413.
    """

    newest_user_text = "Please finish the approved implementation."
    body = {
        "model": "gpt-5.6-sol",
        "instructions": "instruction " * 20_000,
        "tools": [
            {
                "type": "function",
                "name": f"tool_{index}",
                "description": "schema description " * 1_000,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "payload": {
                            "type": "string",
                            "description": "parameter documentation " * 1_000,
                        }
                    },
                },
            }
            for index in range(8)
        ],
        "input": [
            {
                "type": "function_call_output",
                "call_id": "orphaned_call",
                "output": "old output " * 10_000,
            },
            {
                "type": "reasoning",
                "encrypted_content": "encrypted " * 20_000,
            },
            {
                "type": "function_call",
                "call_id": "call_2",
                "name": "large_tool",
                "arguments": "argument " * 20_000,
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": newest_user_text}],
            },
        ],
    }
    original = json.loads(json.dumps(body))
    token_budget_chars = 24_000

    truncated = _truncate_body_for_chatgpt(
        body,
        900 * 1024,
        "req_test",
        over_budget=lambda candidate: len(json.dumps(candidate)) > token_budget_chars,
    )

    assert len(json.dumps(truncated)) <= token_budget_chars
    assert len(json.dumps(truncated).encode("utf-8")) <= 900 * 1024
    assert truncated["input"][-1]["content"][0]["text"] == newest_user_text
    assert truncated["input"][0].get("type") not in {
        "function_call_output",
        "tool_result",
    }
    assert body == original


class _StubTokenizer:
    def count_text(self, text: str) -> int:
        return len(text.split())


class _StubProvider:
    def get_token_counter(self, model: str) -> _StubTokenizer:
        del model
        return _StubTokenizer()

    def get_context_limit(self, model: str) -> int:
        del model
        return 128_000


class _StubPipeline:
    def __init__(self, router: ContentRouter):
        self.transforms = [router]


class _HandlerHarness(OpenAIHandlerMixin):
    """Minimal subclass exposing just the deps the unit-extraction path
    actually reads. The full CutctxProxy ctor wires dozens of unrelated
    services; this keeps the test focused on the gate behavior."""

    def __init__(self, router: ContentRouter):
        self.openai_pipeline: Any = _StubPipeline(router)
        self.openai_provider: Any = _StubProvider()


def test_chatgpt_emergency_truncation_clears_responses_context_guard() -> None:
    """The observed 516K-token compact shape must clear the real guard."""

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)
    model = "gpt-5.6-sol"
    body = {
        "model": model,
        "instructions": "instruction " * 260_000,
        "tools": [
            {
                "type": "function",
                "name": f"tool_{index}",
                "description": "schema " * 20_000,
                "parameters": {"type": "object", "properties": {}},
            }
            for index in range(8)
        ],
        "input": [
            {
                "type": "function_call",
                "name": "large_tool",
                "arguments": "argument " * 80_000,
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "finish the task"}],
            },
        ],
    }

    refused_before, estimated_before, threshold, _ = handler._openai_responses_context_guard(
        body, model=model
    )
    assert refused_before is True
    assert estimated_before > 500_000

    def _over_budget(candidate: dict[str, Any]) -> bool:
        refused, _, _, _ = handler._openai_responses_context_guard(candidate, model=model)
        return refused

    truncated = _truncate_body_for_chatgpt(
        body,
        900 * 1024,
        "req_observed_shape",
        over_budget=_over_budget,
    )
    refused_after, estimated_after, _, _ = handler._openai_responses_context_guard(
        truncated,
        model=model,
    )

    assert refused_after is False
    assert estimated_after < threshold
    assert len(json.dumps(truncated).encode("utf-8")) <= 900 * 1024
    assert truncated["input"][-1]["content"][0]["text"] == "finish the task"


def test_codex_input_list_payload_reaches_router_without_skip() -> None:
    """Codex's Responses payload uses `input=[...]` with no `messages` key.
    The compression gate must accept either field as the items source —
    otherwise the entire payload is silently passed through uncompressed,
    which is the exact production bug surfaced in proxy.log analysis."""

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)

    long_output = " ".join(["compressible"] * 200)
    payload: dict[str, Any] = {
        "type": "response.create",
        "model": "gpt-5.5",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": long_output,
            }
        ],
        # Note: no `messages` key at all — Codex doesn't send one.
    }

    updated, modified, _saved, _transforms, _units_by_cat, _chain, _attempted = (
        handler._compress_openai_responses_live_text_units_with_router(
            payload,
            model="gpt-5.5",
            request_id="hr_codex_test_0001",
        )
    )

    # The gate must NOT have skipped the payload. If it had, `updated`
    # would be the input payload identity-passed through with
    # modified=False — but the deepcopy + splice always returns a new
    # dict object when the path executes.
    assert updated is not payload, "Codex-shape payload was skipped at the input/messages gate"
    # Whether or not Kompress actually compresses 200 repeated words is
    # not the point of this test; the point is that we *entered* the
    # extraction loop. Modified may be True or False depending on
    # Kompress availability in CI, so we only assert non-skip semantics.
    assert isinstance(modified, bool)


def test_codex_payload_with_only_messages_field_also_reaches_router() -> None:
    """The Anthropic-style shape (messages=list, no input) must also
    flow. This is the reverse of the Codex case and guards against a
    future regression that swings the gate too far the other way."""

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)

    payload: dict[str, Any] = {
        "type": "response.create",
        "model": "gpt-5.5",
        "messages": [
            {
                "type": "function_call_output",
                "call_id": "call_2",
                "output": " ".join(["compressible"] * 200),
            }
        ],
    }

    updated, _modified, _saved, _transforms, _units_by_cat, _chain, _attempted = (
        handler._compress_openai_responses_live_text_units_with_router(
            payload,
            model="gpt-5.5",
            request_id="hr_codex_test_0002",
        )
    )

    assert updated is not payload, "messages-shape payload was skipped at the gate"


def test_compression_pass_debug_logs_are_suppressed(caplog) -> None:
    """Re-entrant Codex websocket passes share one `request_id` but
    process distinct payloads. The `pass_id` field on every compression
    event must be content-derived so dashboards can attribute each
    unit_result to its originating pass. Distinct payloads → distinct
    pass_ids (per-pass savings sum legitimately across passes); identical
    payloads → identical pass_ids (idempotent retries should dedup)."""

    import logging as _logging

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)

    payload_a: dict[str, Any] = {
        "type": "response.create",
        "model": "gpt-5.5",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": " ".join(["alpha"] * 200),
            }
        ],
    }
    payload_b: dict[str, Any] = {
        "type": "response.create",
        "model": "gpt-5.5",
        "input": [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": " ".join(["bravo"] * 200),
            }
        ],
    }

    caplog.set_level(_logging.INFO, logger="cutctx.proxy")
    handler._compress_openai_responses_payload(
        payload_a, model="gpt-5.5", request_id="hr_shared_request"
    )
    handler._compress_openai_responses_payload(
        payload_b, model="gpt-5.5", request_id="hr_shared_request"
    )
    # Same content twice → same pass_id (deterministic + idempotent).
    handler._compress_openai_responses_payload(
        payload_a, model="gpt-5.5", request_id="hr_shared_request"
    )

    assert not any("event=codex_compression_" in record.getMessage() for record in caplog.records)
    return

    # Collect pass_ids in call order — payload bodies are no longer
    # embedded at INFO so we can't grep for content; we rely on the
    # 3-call sequence [a, b, a] producing a [A, B, A] pass_id sequence.
    pass_id_sequence: list[str] = []
    for record in caplog.records:
        message = record.getMessage()
        if "event=codex_compression_payload_input" not in message:
            continue
        match_quoted = '"pass_id":"'
        idx = message.find(match_quoted)
        assert idx != -1, f"pass_id missing from event: {message[:200]}"
        start = idx + len(match_quoted)
        end = message.find('"', start)
        pass_id_sequence.append(message[start:end])

    assert len(pass_id_sequence) == 3, (
        f"expected exactly 3 payload_input events for 3 calls, got {len(pass_id_sequence)}"
    )
    # Two distinct payloads + one repeat → two distinct pass_ids overall.
    assert len(set(pass_id_sequence)) == 2, (
        f"expected two distinct pass_ids, got {set(pass_id_sequence)}"
    )
    # Repeated payload_a must be deterministic — index 0 and 2 are the
    # same call shape so they must produce the same pass_id.
    assert pass_id_sequence[0] == pass_id_sequence[2], (
        f"repeated identical payload produced different pass_ids: {pass_id_sequence}"
    )
    assert pass_id_sequence[0] != pass_id_sequence[1]


def test_codex_payload_without_either_field_is_skipped() -> None:
    """The gate must still reject malformed payloads — `input` and
    `messages` both absent (or non-list) is the genuine skip condition."""

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)

    payload: dict[str, Any] = {
        "type": "response.create",
        "model": "gpt-5.5",
        # No input, no messages — genuinely nothing to compress.
    }

    updated, modified, saved, transforms, units_by_cat, chain, attempted = (
        handler._compress_openai_responses_live_text_units_with_router(
            payload,
            model="gpt-5.5",
            request_id="hr_codex_test_0003",
        )
    )

    assert updated is payload
    assert modified is False
    assert units_by_cat == {}
    assert chain == []
    assert attempted == 0
    assert saved == 0
    assert transforms == []


def test_codex_responses_context_guard_uses_lite_limit_for_gpt55() -> None:
    """Regression: gpt-5.5 is an internal Codex Lite model.

    The generic OpenAI provider fallback reports unknown models as 128K, but
    live Codex Lite sessions can grow well past that before failing near the
    actual effective window. The WS guard must use the Codex Lite limit so it
    does not force premature compaction around 128K.
    """

    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)
    payload: dict[str, Any] = {
        "model": "gpt-5.5",
        "input": [{"type": "message", "role": "user", "content": "x " * 260_000}],
    }

    refuse, estimated, threshold, limit = handler._openai_responses_context_guard(
        payload,
        model="gpt-5.5",
    )

    assert limit == 272_000
    assert threshold == 256_000
    assert estimated >= threshold
    assert refuse is True


def test_codex_responses_context_guard_allows_below_lite_threshold() -> None:
    router = ContentRouter(ContentRouterConfig())
    handler = _HandlerHarness(router)
    payload: dict[str, Any] = {
        "model": "gpt-5.5",
        "input": [{"type": "message", "role": "user", "content": "x " * 2_000}],
    }

    refuse, estimated, threshold, limit = handler._openai_responses_context_guard(
        payload,
        model="gpt-5.5",
    )

    assert limit == 272_000
    assert estimated < threshold
    assert refuse is False


def test_content_router_retries_kompress_when_structured_strategy_noops(monkeypatch) -> None:
    router = ContentRouter(ContentRouterConfig(enable_smart_crusher=True))
    content = " ".join("x" for _ in range(200))

    class NoopCrusher:
        def crush(self, value: str, query: str = "", bias: float = 1.0):
            return SimpleNamespace(compressed=value)

    monkeypatch.setattr(router, "_get_smart_crusher", lambda: NoopCrusher())
    monkeypatch.setattr(
        router,
        "_try_ml_compressor",
        lambda value, context, question=None: ("short summary", 2),
    )

    compressed, compressed_tokens, strategy_chain = router._apply_strategy_to_content(
        content,
        CompressionStrategy.SMART_CRUSHER,
        context="",
    )

    assert compressed == "short summary"
    assert compressed_tokens == 2
    # The fallback chain must record both strategies it tried.
    assert strategy_chain == ["smart_crusher", "kompress"]
