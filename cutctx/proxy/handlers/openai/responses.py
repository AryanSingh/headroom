"""OpenAI handler mixin for CutctxProxy.

Contains all OpenAI Chat Completions, Responses API, and passthrough handlers.
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import hashlib
import inspect
import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from cutctx.proxy.helpers import (
    COMPRESSION_TIMEOUT_SECONDS,
    extract_tags,
    jitter_delay_ms,
)
from cutctx.proxy.stage_timer import StageTimer, emit_stage_timings_log
from cutctx.proxy.ws_session_registry import (
    TerminationCause,
    WebSocketSessionRegistry,
    WSSessionHandle,
)
from cutctx.tokenizers import get_tokenizer

if TYPE_CHECKING:
    from fastapi import Request, WebSocket
    from fastapi.responses import Response, StreamingResponse

import httpx

from cutctx.copilot_auth import apply_copilot_api_auth, build_copilot_upstream_url
from cutctx.proxy.auth_mode import classify_auth_mode, classify_client
from cutctx.proxy.cost import _summarize_transforms
from cutctx.proxy.outcome import RequestOutcome
from cutctx.proxy.project_context import classify_project, set_current_project
from cutctx.proxy.savings_metadata import extract_savings_metadata, merge_savings_metadata
from cutctx.proxy.tool_surface import (
    estimate_tool_scaffolding_tokens,
    extract_responses_query,
    slim_tool_surface,
)

logger = logging.getLogger("cutctx.proxy")
_MISSING_ROUTING_FIELD = object()
_RESPONSES_ML_TOOL_OUTPUT_MAX_BYTES_ENV = "CUTCTX_RESPONSES_ML_TOOL_OUTPUT_MAX_BYTES"
_RESPONSES_ML_TOOL_OUTPUT_MAX_BYTES_DEFAULT = 4 * 1024


def _responses_ml_tool_output_max_bytes() -> int:
    """Return the interactive byte budget for ML-routed tool outputs.

    ``0`` is an explicit operator opt-in to the historical unbounded behavior.
    Invalid values retain the safe interactive default.
    """

    raw = os.environ.get(_RESPONSES_ML_TOOL_OUTPUT_MAX_BYTES_ENV)
    if raw is None:
        return _RESPONSES_ML_TOOL_OUTPUT_MAX_BYTES_DEFAULT
    try:
        return max(0, int(raw))
    except ValueError:
        return _RESPONSES_ML_TOOL_OUTPUT_MAX_BYTES_DEFAULT


def _should_passthrough_large_ml_tool_output(router: Any, text: str) -> bool:
    """Keep large ML-only Responses tool outputs byte-faithful and responsive.

    Structured routes (JSON, logs, search, diffs) retain their deterministic
    compressors.  Plain, mixed, and generic-Kompress routes above the budget
    pass through exactly instead of making one synchronous ONNX call per
    350-word chunk.  The whole Responses compression pass already runs in a
    bounded executor; this guard also bounds the work occupying that executor.
    """

    limit = _responses_ml_tool_output_max_bytes()
    if limit == 0 or len(text.encode("utf-8", errors="replace")) <= limit:
        return False
    if not bool(getattr(getattr(router, "config", None), "enable_kompress", False)):
        return False
    determine_strategy = getattr(router, "_determine_strategy", None)
    if not callable(determine_strategy):
        return False
    try:
        from cutctx.transforms.content_router import CompressionStrategy

        strategy = determine_strategy(text)
    except Exception:
        # Custom routers keep their previous behavior. The outer compression
        # timeout/failure policy remains the final fail-open boundary.
        return False
    return strategy in {
        CompressionStrategy.TEXT,
        CompressionStrategy.KOMPRESS,
        CompressionStrategy.MIXED,
    }


def _summarize_upstream_ws_error(
    event: dict[str, Any], *, max_message_chars: int = 500
) -> dict[str, str]:
    """Return bounded, non-payload metadata for an upstream WS error event."""

    summary: dict[str, str] = {"event_type": str(event.get("type") or "error")}
    error = event.get("error")
    if not isinstance(error, dict):
        error = {}

    for source_key, summary_key in (("type", "error_type"), ("code", "error_code")):
        value = error.get(source_key)
        if value is not None:
            summary[summary_key] = str(value)

    message = error.get("message")
    if isinstance(message, dict):
        message_type = message.get("type")
        if message_type is not None:
            summary["message_type"] = str(message_type)
        message = message.get("message")
    if message is not None:
        text = str(message)
        limit = max(0, int(max_message_chars))
        summary["message"] = text if len(text) <= limit else text[:limit] + "…"
    return summary


_CHATGPT_SUBSCRIPTION_UNSUPPORTED_RESPONSE_FIELDS = frozenset(
    # Fields the chatgpt.com/backend-api/codex/responses endpoint rejects.
    # "stream" is included because the subscription HTTP path has historically
    # rejected ``stream: true`` with a bare 400. We keep the safer non-streaming
    # path unless and until that endpoint is re-verified live.
    #
    # Additional extended OpenAI API fields are stripped conservatively because
    # chatgpt.com is stricter than api.openai.com and tends to respond with a
    # plain 400 when it dislikes request-shape fields.
    #   reasoning          — o-series extended thinking ({"effort": "medium"})
    #   include            — encrypted reasoning retrieval (["reasoning.encrypted_content"])
    #   text               — response verbosity control ({"verbosity": "low"})
    #   store              — request storage flag (false)
    #   stream_options     — streaming-only delivery controls
    #   parallel_tool_calls — tool parallelism flag
    #   client_metadata, generate, prompt_cache_key — internal/legacy fields
    {
        "client_metadata",
        "generate",
        "include",
        "parallel_tool_calls",
        "prompt_cache_key",
        "reasoning",
        "store",
        "stream",
        "stream_options",
        "text",
    }
)

_REMOTE_COMPACTION_REQUIRED_FIELDS = frozenset(
    {
        "client_metadata",
        "include",
        "parallel_tool_calls",
        "prompt_cache_key",
        "reasoning",
        "store",
        "stream",
        "stream_options",
        "text",
    }
)
_REMOTE_COMPACTION_MIN_BODY_BYTES = 1024 * 1024


def _is_remote_compaction_subscription_request(body: dict[str, Any]) -> bool:
    """Identify Codex's provider-owned, large remote-compaction envelope.

    The envelope is accepted by ChatGPT's Codex backend but cannot survive the
    ordinary Responses sanitizer or structural context trimmer. Keep the
    predicate intentionally narrow so normal subscription requests retain
    their safety policy.
    """

    if not _REMOTE_COMPACTION_REQUIRED_FIELDS.issubset(body):
        return False
    try:
        return len(json.dumps(body).encode("utf-8", errors="replace")) >= (
            _REMOTE_COMPACTION_MIN_BODY_BYTES
        )
    except (TypeError, ValueError):
        return False

# Codex Responses Lite is a client hint, not proof that the model itself
# must be rewritten. The proxy strips the internal Lite header before
# forwarding api.openai.com requests, and chatgpt.com model availability is
# account/server controlled. Proactively rewriting every non-allowlisted
# model to gpt-5.5 caused newer/cheaper supported models (for example
# gpt-5.6-terra and gpt-5.4) to be discarded before the upstream could try
# them. Keep model names intact; request-shape sanitizers below still strip
# fields the target backend rejects.
_CODEX_RESPONSES_LITE_CONTEXT_LIMITS: dict[str, int] = {
    # The generic OpenAI provider fallback is 128K for unknown model names,
    # but Codex Responses Lite accepts much larger gpt-5.5 sessions before
    # failing near the effective model window. Keep this path-specific limit
    # local to the Codex Lite sanitizer/WS guard instead of teaching the
    # global OpenAI registry about an internal subscription-only model.
    "gpt-5.5": 272_000,
    # gpt-5.6-sol / gpt-5.6-terra are Codex-only subscription models with no
    # entry in the global OpenAI context-limit registry, so unknown-model
    # requests fell back to the generic 128K default — well under Codex's
    # own reported model_context_window (258400) for these models. That made
    # _openai_responses_context_guard misfire "too large" on ordinary
    # sessions long before they were actually near the real limit, triggering
    # emergency truncation (dropping messages) that can produce a
    # structurally invalid conversation and an upstream 400 "Bad Request".
    "gpt-5.6-sol": 258_400,
    "gpt-5.6-terra": 258_400,
}
_CODEX_RESPONSES_CONTEXT_RESERVE_TOKENS = 16_000
_CODEX_RESPONSES_CONTEXT_RESERVE_RATIO = 0.05


def _resolve_codex_responses_lite_model(current_model: str) -> str | None:
    """Return a Lite-safe replacement for ``current_model`` if one is known.

    Deliberately returns ``None`` for all models today. Older code used a
    hard allow-list and migrated every unknown model to gpt-5.5 before
    forwarding. That turned a transient/transport compatibility problem into
    a permanent model-selection bug: any newly supported model could never be
    attempted. Until this path has a real retry-after-upstream-failure
    mechanism, preserving the caller's model is the only safe behavior.
    """
    return None


def _codex_responses_context_limit(provider: Any, model: str) -> int:
    """Resolve the effective context limit for Codex Responses WS preflight."""

    if model in _CODEX_RESPONSES_LITE_CONTEXT_LIMITS:
        return _CODEX_RESPONSES_LITE_CONTEXT_LIMITS[model]

    get_context_limit = getattr(provider, "get_context_limit", None)
    if callable(get_context_limit):
        try:
            limit = int(get_context_limit(model))
            if limit > 0:
                return limit
        except Exception:
            pass
    return 0


_MAX_IMAGE_DATA_URI_CHARS = 2 * 1024  # 2 KB before an inline image is shrunk

# A real, minimal 1x1 transparent PNG. Used to shrink oversized inline image
# data URIs while keeping the field a schema-valid image — unlike a text
# placeholder, which chatgpt.com's Responses backend rejects with a 400
# ("Bad Request") because ``image_url`` no longer decodes as image data.
_PLACEHOLDER_IMAGE_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _responses_context_estimate_payload(payload: Any) -> tuple[Any, int]:
    """Return a text-countable payload plus bounded inline-image token cost.

    Responses frames embed pasted screenshots as base64 data URIs. Those bytes
    are transport encoding, not prompt text; counting them with the text
    tokenizer can turn a normal screenshot into a fictitious hundreds of
    thousands of tokens and make the websocket context guard reject it.
    """

    def _inline_image_tokens(value: str) -> int:
        encoded_bytes = max(0, len(value.partition(",")[2]) * 3 // 4)
        if encoded_bytes < 50 * 1024:
            return 400
        if encoded_bytes < 500 * 1024:
            return 1_200
        return 1_600

    def _visit(value: Any, *, key: str | None = None) -> tuple[Any, int]:
        if (
            key == "image_url"
            and isinstance(value, str)
            and value.startswith("data:image/")
        ):
            return "<inline image data>", _inline_image_tokens(value)
        if isinstance(value, dict):
            copied: dict[str, Any] = {}
            image_tokens = 0
            for child_key, child_value in value.items():
                copied[child_key], child_tokens = _visit(child_value, key=child_key)
                image_tokens += child_tokens
            return copied, image_tokens
        if isinstance(value, list):
            copied_items: list[Any] = []
            image_tokens = 0
            for item in value:
                copied_item, child_tokens = _visit(item)
                copied_items.append(copied_item)
                image_tokens += child_tokens
            return copied_items, image_tokens
        return value, 0

    estimated_payload, image_tokens = _visit(payload)
    return estimated_payload, image_tokens


def _shrink_oversized_images(payload: Any) -> Any:
    """Recursively replace oversized inline ``image_url`` data URIs.

    Unlike ``_truncate_body_for_chatgpt``, this touches nothing except
    ``image_url`` fields — it never inspects, truncates, or drops
    ``encrypted_content`` or any other field. Safe to run even on payloads
    carrying opaque model-bound continuation state (see
    ``_contains_opaque_responses_continuation``): a reconstructed HTTP
    continuation can legitimately be dominated by inline screenshots (a
    single pasted image easily exceeds a megabyte of base64), and treating
    the context guard as advisory for those payloads must not mean forwarding
    raw image bytes uncapped — only the encrypted state is untouchable.
    """
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            if (
                key == "image_url"
                and isinstance(value, str)
                and value.startswith("data:image/")
                and len(value) > _MAX_IMAGE_DATA_URI_CHARS
            ):
                out[key] = _PLACEHOLDER_IMAGE_DATA_URI
            else:
                out[key] = _shrink_oversized_images(value)
        return out
    if isinstance(payload, list):
        return [_shrink_oversized_images(item) for item in payload]
    return payload


def _contains_opaque_responses_continuation(payload: Any, *, max_nodes: int = 4096) -> bool:
    """Return whether a Responses payload carries model-bound opaque state.

    ``encrypted_content`` is produced and interpreted by the upstream model.
    CutCtx must not decode or estimate it as ordinary prompt text. The bounded
    iterative walk avoids recursion depth failures on adversarial JSON shapes.
    """

    remaining = max(0, int(max_nodes))
    stack = [payload]
    while stack and remaining:
        remaining -= 1
        value = stack.pop()
        if isinstance(value, dict):
            encrypted = value.get("encrypted_content")
            if isinstance(encrypted, str) and encrypted:
                return True
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return False


def _ws_connect_header_kwargs(
    websockets_module: Any, upstream_headers: dict[str, str]
) -> dict[str, dict[str, str]]:
    """Use the header kwarg supported by the installed websockets client."""
    try:
        connect_sig = inspect.signature(websockets_module.connect)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        connect_sig = None
    if connect_sig and "additional_headers" in connect_sig.parameters:
        return {"additional_headers": upstream_headers}
    return {"extra_headers": upstream_headers}


def _compute_responses_ws_conversation_session_id(
    session_tracker_store: Any,
    ws_headers: dict[str, str],
    body: dict[str, Any] | None,
    *,
    fallback_session_id: str,
) -> str:
    """Derive a stable conversation key for Responses WebSocket sessions.

    The socket itself has a short-lived connection UUID, but sticky helpers
    should follow the logical conversation so reconnects and proxy restarts can
    recover the same session state.
    """
    if session_tracker_store is None:
        return fallback_session_id

    payload = body if isinstance(body, dict) else {}
    response_body = (
        payload.get("response") if isinstance(payload.get("response"), dict) else payload
    )
    if not isinstance(response_body, dict):
        response_body = {}

    normalized_headers = dict(ws_headers)
    has_explicit_session_header = any(
        key.lower() == "x-cutctx-session-id" for key in normalized_headers
    )
    if not has_explicit_session_header:
        previous_response_id = response_body.get("previous_response_id")
        conversation = response_body.get("conversation")
        derived_session_key: str | None = None

        if isinstance(previous_response_id, str) and previous_response_id.strip():
            derived_session_key = f"resp:{previous_response_id.strip()}"
        elif isinstance(conversation, str) and conversation.strip():
            derived_session_key = f"conv:{conversation.strip()}"
        elif isinstance(conversation, dict):
            conversation_id = conversation.get("id")
            if isinstance(conversation_id, str) and conversation_id.strip():
                derived_session_key = f"conv:{conversation_id.strip()}"

        if derived_session_key:
            normalized_headers["x-cutctx-session-id"] = derived_session_key

    model = str(response_body.get("model") or payload.get("model") or "unknown")
    instructions = response_body.get("instructions")
    if instructions is None:
        instructions = payload.get("instructions")

    messages: list[dict[str, Any]] = []
    if isinstance(instructions, str) and instructions:
        messages = [{"role": "system", "content": instructions}]
    elif isinstance(instructions, list) and instructions:
        messages = [{"role": "system", "content": instructions}]

    try:
        synthetic_request = SimpleNamespace(headers=normalized_headers)
        return session_tracker_store.compute_session_id(
            synthetic_request,
            model,
            messages,
        )
    except Exception:
        logger.debug("Failed to derive stable Responses WS session id", exc_info=True)
        return fallback_session_id


def _has_model_reserved_tool(tools: Any) -> bool:
    """Detect tool declarations reserved for a specific model (e.g. built-in
    ``image_gen.imagegen``). Their schema is pinned to whichever model the
    client originally requested; forwarding them unchanged after silently
    migrating the model to a different one causes upstream to reject with
    "Function '<name>' is reserved for use by this model and must match the
    configured schema." Ordinary function-tool names never contain a literal
    dot, so a dotted name is the signal that this is one of these reserved,
    model-pinned built-ins rather than a client-defined function.
    """
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        if isinstance(name, str) and "." in name:
            return True
    return False


def _strip_namespace_from_custom_tool_call_input_items(
    input_items: Any,
) -> tuple[Any, bool]:
    """Drop the ``namespace`` field from ``custom_tool_call`` conversation

    history items. Codex natively tags custom tool calls that originate
    from a namespaced plugin/skill tool (e.g. the desktop app's built-in
    Node REPL) with ``"namespace": "<name>"``. Confirmed live: the
    chatgpt.com Codex backend rejects this field on replayed history with
    ``[ObjectParam] [input[N].namespace] [unknown_parameter] Unknown
    parameter: 'input[N].namespace'.`` — the field is only needed for
    Codex's own local bookkeeping, not for the model to understand what
    happened, so dropping it on replay is safe.
    """
    if not isinstance(input_items, list):
        return input_items, False
    changed = False
    cleaned: list[Any] = []
    for item in input_items:
        if (
            isinstance(item, dict)
            and item.get("type") == "custom_tool_call"
            and "namespace" in item
        ):
            item = {k: v for k, v in item.items() if k != "namespace"}
            changed = True
        cleaned.append(item)
    return (cleaned if changed else input_items), changed


_NAMESPACED_OUTPUT_ITEM_TYPES = frozenset({"custom_tool_call", "function_call"})


def _strip_namespace_from_upstream_event_text(raw: str) -> str:
    """Strip the client-breaking ``namespace`` field from tool-call items in

    upstream streaming events before relaying to the client.

    Codex Desktop's tool dispatcher (confirmed on cli_version
    0.144.0-alpha.4) concatenates ``name`` + ``namespace`` without a
    separator when routing a tool call locally, so a call like
    ``{"name": "exec", "namespace": "exec"}`` gets misrouted to a tool
    literally named "execexec" and fails with "unsupported custom tool
    call: execexec" (or "waitwait" for the `wait` tool) — entirely inside
    the client, after the request already succeeded upstream. ``name`` +
    ``call_id`` fully identify the call without ``namespace``, so dropping
    it before it reaches the buggy dispatcher is a safe, response-shape-
    preserving workaround. Parse failures or non-matching shapes return
    ``raw`` unchanged — this must never be what breaks a working relay.
    """
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if not isinstance(event, dict):
        return raw
    item = event.get("item")
    if (
        not isinstance(item, dict)
        or item.get("type") not in _NAMESPACED_OUTPUT_ITEM_TYPES
        or "namespace" not in item
    ):
        return raw
    new_item = {k: v for k, v in item.items() if k != "namespace"}
    return json.dumps({**event, "item": new_item})


def _sanitize_chatgpt_subscription_responses_body(
    body: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Strip/translate request fields the ChatGPT Codex backend rejects."""
    sanitized = dict(body)
    stripped: list[str] = []
    for key in sorted(_CHATGPT_SUBSCRIPTION_UNSUPPORTED_RESPONSE_FIELDS):
        if key in sanitized:
            sanitized.pop(key, None)
            stripped.append(key)
    cleaned_input, input_changed = _strip_namespace_from_custom_tool_call_input_items(
        sanitized.get("input")
    )
    if input_changed:
        sanitized["input"] = cleaned_input
        stripped.append("input[*].namespace")
    # Preserve the caller's model. Earlier versions translated model names
    # here, but that prevented the upstream from accepting newer models as
    # account/server support changed.
    current_model = sanitized.get("model", "")
    migrated = _resolve_codex_responses_lite_model(current_model)
    if migrated and not _has_model_reserved_tool(sanitized.get("tools")):
        sanitized["model"] = migrated
        stripped.append(f"model:{current_model}->{migrated}")
    return sanitized, stripped


def _sanitize_codex_responses_lite_model(
    body: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Apply model-level Lite normalization without guessing fallbacks.

    Currently this preserves every requested model. The helper remains as
    the single model-normalization hook for HTTP, chat, WS, and fallback
    paths if a future verified alias requires deterministic translation.
    """
    sanitized = dict(body)
    current_model = sanitized.get("model", "")
    migrated = _resolve_codex_responses_lite_model(current_model)
    if migrated and not _has_model_reserved_tool(sanitized.get("tools")):
        sanitized["model"] = migrated
        return sanitized, [f"model:{current_model}->{migrated}"]
    return sanitized, []


def _sanitize_codex_responses_lite_body(
    body: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Apply Lite-safe request normalization without chatgpt.com field stripping."""
    sanitized, migrated_fields = _sanitize_codex_responses_lite_model(body)
    return sanitized, migrated_fields


def _apply_model_routing_request_overrides(
    body: dict[str, Any],
    savings_metadata: dict[str, Any] | None,
) -> None:
    """Apply request-shape overrides attached by model routing."""

    overrides = (savings_metadata or {}).get("model_routing", {}).get("request_overrides") or {}
    if not isinstance(overrides, dict):
        return

    reasoning_override = overrides.get("reasoning")
    if isinstance(reasoning_override, dict):
        existing_reasoning = body.get("reasoning")
        if isinstance(existing_reasoning, dict):
            merged_reasoning = dict(existing_reasoning)
            merged_reasoning.update(reasoning_override)
            body["reasoning"] = merged_reasoning
        else:
            body["reasoning"] = dict(reasoning_override)


def _responses_payload_to_routing_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Build minimal chat-shaped messages for model-routing classification."""

    messages: list[dict[str, Any]] = []
    instructions = payload.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions})

    input_data = payload.get("input")
    if isinstance(input_data, str):
        messages.append({"role": "user", "content": input_data})
    elif isinstance(input_data, list):
        input_messages: list[dict[str, Any]] = []
        current_user_candidates: list[dict[str, Any]] = []
        for item in input_data:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            if isinstance(item_type, str) and item_type not in {
                "message",
                "input_message",
                "input_text",
            }:
                # Responses input arrays include tool outputs, reasoning, and
                # call records. Those are context, not the user's current task.
                continue

            role = str(item.get("role") or "user")
            if role not in {"system", "developer", "user", "assistant"}:
                continue

            if item_type == "input_text":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    message = {"role": role, "content": text}
                    input_messages.append(message)
                    if role == "user" and not item.get("id"):
                        current_user_candidates.append(message)
                continue

            content = item.get("content")
            if isinstance(content, str):
                message = {"role": role, "content": content}
                input_messages.append(message)
                if role == "user" and not item.get("id"):
                    current_user_candidates.append(message)
            elif isinstance(content, list):
                text_parts: list[str] = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        text_parts.append(text)
                if text_parts:
                    message = {"role": role, "content": "\n".join(text_parts)}
                    input_messages.append(message)
                    if role == "user" and not item.get("id"):
                        current_user_candidates.append(message)

        if current_user_candidates:
            messages.append(current_user_candidates[-1])
        else:
            messages.extend(input_messages)

    return messages


def _responses_payload_to_chat_completions_body(payload: dict[str, Any]) -> dict[str, Any]:
    """Best-effort adapter from Responses HTTP payload to Chat Completions body."""

    messages: list[dict[str, Any]] = []

    instructions = payload.get("instructions")
    if isinstance(instructions, str) and instructions.strip():
        messages.append({"role": "system", "content": instructions})

    input_data = payload.get("input")
    if isinstance(input_data, str):
        messages.append({"role": "user", "content": input_data})
    elif isinstance(input_data, list):
        for item in input_data:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type") or "")
            role = str(item.get("role") or "user")

            if item_type in {"message", "input_message", "input_text", ""}:
                if item_type == "input_text":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        messages.append({"role": role, "content": text})
                    continue

                content = item.get("content")
                if isinstance(content, str):
                    messages.append({"role": role, "content": content})
                elif isinstance(content, list):
                    text_parts: list[str] = []
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        text = part.get("text")
                        if isinstance(text, str) and text.strip():
                            text_parts.append(text)
                    if text_parts:
                        messages.append({"role": role, "content": "\n".join(text_parts)})
                continue

            if item_type == "function_call_output":
                output = item.get("output")
                tool_text = output if isinstance(output, str) else json.dumps(output, default=str)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": item.get("call_id") or item.get("id") or "tool_call",
                        "content": tool_text,
                    }
                )

    chat_body: dict[str, Any] = {
        "model": payload.get("model"),
        "messages": messages,
    }

    parameter_map = {
        "max_output_tokens": "max_tokens",
        "temperature": "temperature",
        "top_p": "top_p",
        "tool_choice": "tool_choice",
    }
    for responses_key, chat_key in parameter_map.items():
        if responses_key in payload:
            chat_body[chat_key] = payload[responses_key]

    tools = payload.get("tools")
    if isinstance(tools, list):
        converted_tools: list[dict[str, Any]] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            if tool.get("type") == "function":
                converted_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name"),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                        },
                    }
                )
            else:
                converted_tools.append(tool)
        if converted_tools:
            chat_body["tools"] = converted_tools

    return chat_body


def _chat_completions_response_to_responses_payload(
    response_body: dict[str, Any],
    *,
    model: str,
) -> dict[str, Any]:
    """Best-effort adapter from Chat Completions response to Responses payload."""

    def _int(value: Any) -> int:
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 0

    choice0 = {}
    choices = response_body.get("choices")
    if isinstance(choices, list) and choices:
        if isinstance(choices[0], dict):
            choice0 = choices[0]

    message = choice0.get("message") if isinstance(choice0, dict) else {}
    if not isinstance(message, dict):
        message = {}

    output: list[dict[str, Any]] = []

    content = message.get("content")
    if isinstance(content, str) and content:
        output.append(
            {
                "type": "message",
                "id": f"msg_{uuid.uuid4().hex[:24]}",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": content,
                        "annotations": [],
                    }
                ],
            }
        )

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function") or {}
            if not isinstance(function, dict):
                function = {}
            output.append(
                {
                    "type": "function_call",
                    "id": tool_call.get("id") or f"fc_{uuid.uuid4().hex[:24]}",
                    "call_id": tool_call.get("id") or f"call_{uuid.uuid4().hex[:24]}",
                    "name": function.get("name", "function"),
                    "arguments": function.get("arguments", "{}"),
                    "status": "completed",
                }
            )

    usage = response_body.get("usage") if isinstance(response_body, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    cached_tokens = (
        prompt_details.get("cached_tokens", 0) if isinstance(prompt_details, dict) else 0
    )

    return {
        "id": response_body.get("id") or f"resp_{uuid.uuid4().hex[:24]}",
        "object": "response",
        "model": response_body.get("model") or model,
        "status": "completed",
        "output": output,
        "usage": {
            "input_tokens": _int(usage.get("prompt_tokens")),
            "output_tokens": _int(usage.get("completion_tokens")),
            "total_tokens": _int(usage.get("total_tokens")),
            "input_tokens_details": {"cached_tokens": _int(cached_tokens)},
        },
    }


def _truncate_body_for_chatgpt(
    body: dict[str, Any],
    max_bytes: int,
    request_id: str,
    *,
    over_budget: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    """Aggressively reduce a chatgpt.com request to its transport budgets.

    ``max_bytes`` protects the subscription endpoint's body-size ceiling.
    ``over_budget`` optionally adds a model-token predicate, which matters for
    Codex compaction requests that can fit the byte ceiling while remaining far
    beyond the model context window.

    Strategy (in order):
    1. Truncate large nested payload strings and inline images.
    2. Drop oldest messages from the ``input`` array (keep the newest item).
    3. Remove fixed-cost tool schemas.
    4. Progressively reduce instructions.
    5. Prune nested lists and strings in the final retained input item.
    Returns a shallow copy with modified fields; never raises.
    """
    import copy as _copy

    _MAX_TOOL_OUTPUT_CHARS = 4 * 1024  # 4 KB per tool output text
    _MAX_INSTRUCTIONS_CHARS = 200 * 1024  # 200 KB for system instructions
    _MAX_IMAGE_DATA_URI_CHARS = 2 * 1024  # 2 KB before an inline image is shrunk

    # A real, minimal 1x1 transparent PNG. Used to shrink oversized inline
    # image data URIs while keeping the field a schema-valid image — unlike a
    # text placeholder, which chatgpt.com's Responses backend rejects with a
    # 400 ("Bad Request") because ``image_url`` no longer decodes as image
    # data. Swapping in a tiny real image keeps the retry request valid.
    _PLACEHOLDER_IMAGE_DATA_URI = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )

    body = _copy.deepcopy(body)

    def _body_bytes(candidate: dict[str, Any] | None = None) -> int:
        try:
            return len(
                json.dumps(candidate if candidate is not None else body).encode(
                    "utf-8", errors="replace"
                )
            )
        except Exception:
            return max_bytes + 1

    def _is_over_budget() -> bool:
        if _body_bytes() > max_bytes:
            return True
        if over_budget is None:
            return False
        try:
            return bool(over_budget(body))
        except Exception as exc:
            logger.warning(
                "[%s] chatgpt emergency token-budget predicate failed: %s",
                request_id,
                exc,
            )
            return False

    def _shrink_image_url(value: str) -> str:
        if value.startswith("data:image/") and len(value) > _MAX_IMAGE_DATA_URI_CHARS:
            return _PLACEHOLDER_IMAGE_DATA_URI
        return value

    _PAYLOAD_STRING_KEYS = {
        "arguments",
        "content",
        "data",
        "encrypted_content",
        "output",
        "text",
    }

    def _truncate_nested(
        value: Any,
        *,
        char_limit: int,
        parent_key: str | None = None,
        truncate_all_strings: bool = False,
    ) -> Any:
        """Recursively cap payload strings without corrupting image fields."""

        if isinstance(value, str):
            if parent_key == "image_url":
                return _shrink_image_url(value)
            if (
                (truncate_all_strings or parent_key in _PAYLOAD_STRING_KEYS)
                and len(value) > char_limit
            ):
                return value[:char_limit] + "…[truncated]"
            return value
        if isinstance(value, list):
            return [
                _truncate_nested(
                    child,
                    char_limit=char_limit,
                    parent_key=parent_key,
                    truncate_all_strings=truncate_all_strings,
                )
                for child in value
            ]
        if isinstance(value, dict):
            return {
                key: _truncate_nested(
                    child,
                    char_limit=char_limit,
                    parent_key=key,
                    truncate_all_strings=truncate_all_strings,
                )
                for key, child in value.items()
            }
        return value

    def _prune_nested_lists(value: Any, max_items: int) -> Any:
        if isinstance(value, list):
            return [_prune_nested_lists(child, max_items) for child in value[-max_items:]]
        if isinstance(value, dict):
            return {key: _prune_nested_lists(child, max_items) for key, child in value.items()}
        return value

    def _truncate_input_item(item: Any) -> Any:
        if not isinstance(item, dict):
            return item
        return _truncate_nested(item, char_limit=_MAX_TOOL_OUTPUT_CHARS)

    # Step 1: truncate large tool outputs within all messages
    if isinstance(body.get("input"), list):
        body["input"] = [_truncate_input_item(msg) for msg in body["input"]]
    if not _is_over_budget():
        return body

    # Step 2: drop oldest messages (keep at least 1 to preserve the user turn).
    # After dropping, ensure the first remaining item is a user/system message —
    # the Codex API rejects inputs that start with function_call_output or
    # assistant items whose preceding function_call was dropped.
    _TOOL_RESULT_TYPES = {"function_call_output", "tool_result"}
    if isinstance(body.get("input"), list) and len(body["input"]) > 1:
        msgs = body["input"]
        while len(msgs) > 1 and _is_over_budget():
            msgs.pop(0)
        # Drop any leading tool-result items that lost their paired tool-call.
        while (
            len(msgs) > 1
            and isinstance(msgs[0], dict)
            and msgs[0].get("type") in _TOOL_RESULT_TYPES
        ):
            msgs.pop(0)
        body["input"] = msgs
    if not _is_over_budget():
        return body

    # Step 3: the live tool surface is fixed-cost context. Compression has
    # already compacted it before this emergency path, so remove it if the
    # request still cannot fit.
    if body.get("tools") and _is_over_budget():
        body.pop("tools", None)
    if not _is_over_budget():
        return body

    # Step 4: progressively reduce instructions. A fixed 200 KB cap is still
    # much too large for token-dense prompts, so keep halving until the actual
    # request budget is satisfied or only a minimal marker remains.
    instructions = body.get("instructions")
    if isinstance(instructions, str):
        instruction_limit = min(len(instructions), _MAX_INSTRUCTIONS_CHARS)
        while instruction_limit > 1024 and _is_over_budget():
            instruction_limit //= 2
            body["instructions"] = (
                instructions[:instruction_limit]
                + "\n…[instructions truncated by cutctx]"
            )
        if _is_over_budget():
            body["instructions"] = "[instructions truncated by cutctx]"
    if not _is_over_budget():
        return body

    # Step 5: a single retained input item can itself contain thousands of
    # nested blocks or token-dense opaque strings. Tighten both dimensions in
    # bounded stages while preserving the newest tail of every list.
    for max_items, char_limit in ((64, 2048), (16, 1024), (4, 512), (1, 256), (1, 64)):
        if not _is_over_budget():
            break
        if isinstance(body.get("input"), list):
            body["input"] = _prune_nested_lists(body["input"], max_items)
            body["input"] = _truncate_nested(
                body["input"],
                char_limit=char_limit,
                truncate_all_strings=True,
            )
    return body


def _normalize_ws_http_fallback_body(
    parsed: Any,
    body: dict[str, Any] | None,
    *,
    strip_chatgpt_subscription_fields: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """Convert a WS response.create payload into an HTTP /v1/responses body."""
    http_body: dict[str, Any]
    if isinstance(parsed, dict) and isinstance(parsed.get("response"), dict):
        http_body = dict(parsed["response"])
    elif isinstance(parsed, dict):
        http_body = dict(parsed)
        if http_body.get("type") == "response.create":
            http_body.pop("type", None)
    else:
        http_body = body if isinstance(body, dict) else {}

    if http_body.get("type") in {"response.create", "response"}:
        http_body.pop("type", None)

    stripped: list[str] = []
    if strip_chatgpt_subscription_fields:
        http_body, stripped = _sanitize_chatgpt_subscription_responses_body(http_body)
    else:
        http_body["stream"] = True
    return http_body, stripped


def _usage_int(value: Any, default: int = 0) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def _openai_chat_usage_to_responses_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(usage, dict):
        return {
            "input_tokens": 0,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 0,
            "total_tokens": 0,
        }

    prompt_tokens = _usage_int(usage.get("prompt_tokens"))
    completion_tokens = _usage_int(usage.get("completion_tokens"))
    total_tokens = _usage_int(usage.get("total_tokens"), prompt_tokens + completion_tokens)
    prompt_details = usage.get("prompt_tokens_details")
    cached_tokens = 0
    if isinstance(prompt_details, dict):
        cached_tokens = _usage_int(prompt_details.get("cached_tokens"))

    return {
        "input_tokens": prompt_tokens,
        "input_tokens_details": {"cached_tokens": cached_tokens},
        "output_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


_CLIENT_PROVIDER_MAP: dict[str, str] = {
    "claude-code": "claude",
    "claude-vscode": "claude",
    "claude-cli": "claude",
}


def _provider_for_client(client: str | None) -> str:
    """Map a detected client identifier to its provider label for metrics."""
    return _CLIENT_PROVIDER_MAP.get(client or "", "openai")


def _tool_schema_savings_metadata(
    tokenizer: Any,
    original_tools: Any,
    compacted_tools: Any,
) -> dict[str, dict[str, int]] | None:
    if not original_tools or not compacted_tools:
        return None
    try:
        tokens_saved = max(
            0,
            tokenizer.count_text(json.dumps(original_tools, ensure_ascii=False))
            - tokenizer.count_text(json.dumps(compacted_tools, ensure_ascii=False)),
        )
    except Exception:
        return None
    if tokens_saved <= 0:
        return None
    return {"tool_schema_compaction": {"tokens": tokens_saved}}


_OPENAI_RESPONSES_UNIT_CACHE_MAX_ENTRIES = 10_000
_OPENAI_RESPONSES_UNIT_CACHE_VERSION = "openai_responses_unit_v1"
_OPENAI_RESPONSES_UNIT_PARALLELISM_ENV = "CUTCTX_TOOL_OUTPUT_COMPRESSION_PARALLELISM"
_OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT = 4
_OPENAI_RESPONSES_UNIT_PARALLELISM_MAX = 16
_OPENAI_RESPONSES_UNIT_CACHE_INIT_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR: ThreadPoolExecutor | None = None

from cutctx.proxy.handlers.openai.utils import *  # noqa: E402, F403
from cutctx.proxy.handlers.openai.utils import (  # noqa: E402
    _codex_compression_debug_enabled,
    _codex_ws_text_shape,
    _extract_codex_handshake_headers,
    _extract_responses_usage,
    _infer_openai_cache_write_tokens,
    _json_debug_dumps,
    _json_shape,
    _log_codex_compression_debug,
    _openai_responses_context_budget,
    _openai_responses_result_with_cache_hit,
    _openai_responses_unit_cache_key,
    _openai_responses_unit_executor,
    _openai_responses_unit_parallelism,
    _resolve_codex_routing_headers,
    _routing_log_debug,
)


class OpenAIResponsesMixin:
    @staticmethod
    def _model_routing_responses_text(payload: dict[str, Any] | None) -> str:
        if not isinstance(payload, dict):
            return ""
        output = payload.get("output")
        if not isinstance(output, list):
            return ""
        texts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return "\n".join(texts).strip()

    async def _maybe_model_routing_responses_shadow(
        self,
        *,
        request_id: str,
        source_model: str,
        candidate_model: str,
        url: str,
        headers: dict[str, Any],
        candidate_body: dict[str, Any],
        routing_metadata: dict[str, Any] | None,
        messages: list[dict[str, Any]],
        candidate_json: dict[str, Any] | None,
        original_reasoning: Any,
        client: str | None = None,
    ) -> None:
        """Replay a sampled Responses request on its requested model."""

        if (
            not routing_metadata
            or source_model == candidate_model
            or routing_metadata.get("target_model") != candidate_model
        ):
            return
        from cutctx.proxy.model_routing_evals import maybe_run_model_routing_shadow
        from cutctx.proxy.savings_tracker import estimate_request_cost_usd

        def cost_for(model_name: str, payload: dict[str, Any] | None) -> float:
            usage = payload.get("usage", {}) if payload else {}
            total = int(usage.get("input_tokens", 0) or 0)
            details = usage.get("input_tokens_details") or {}
            cached = int(details.get("cached_tokens", 0) or 0)
            return estimate_request_cost_usd(
                model_name,
                input_tokens=total,
                cache_read_tokens=cached,
                uncached_input_tokens=max(0, total - cached),
            )

        async def baseline_call() -> tuple[str, float]:
            baseline_body = copy.deepcopy(candidate_body)
            baseline_body["model"] = source_model
            if original_reasoning is _MISSING_ROUTING_FIELD:
                baseline_body.pop("reasoning", None)
            else:
                baseline_body["reasoning"] = copy.deepcopy(original_reasoning)
            response = await self._retry_request("POST", url, headers, baseline_body)
            if response.status_code >= 400:
                raise RuntimeError(f"model-routing shadow returned HTTP {response.status_code}")
            payload = response.json()
            return self._model_routing_responses_text(payload), cost_for(source_model, payload)

        await maybe_run_model_routing_shadow(
            request_id=request_id,
            messages=messages,
            source_model=source_model,
            candidate_model=candidate_model,
            scorer=str(routing_metadata.get("scorer", "heuristic")),
            confidence=float(routing_metadata.get("confidence", 0.0) or 0.0),
            candidate_response=self._model_routing_responses_text(candidate_json),
            candidate_cost_usd=cost_for(candidate_model, candidate_json),
            baseline_call=baseline_call,
            category="openai_responses",
            segments={"client": client or "openai", "task_type": "openai_responses"},
        )

    def _openai_responses_unit_cache(self) -> tuple[Any, OrderedDict[str, Any]]:
        with _OPENAI_RESPONSES_UNIT_CACHE_INIT_LOCK:
            lock = getattr(self, "_openai_responses_unit_cache_lock", None)
            if lock is None:
                lock = threading.RLock()
                self._openai_responses_unit_cache_lock = lock
            cache = getattr(self, "_openai_responses_unit_result_cache", None)
            if cache is None:
                cache = OrderedDict()
                self._openai_responses_unit_result_cache = cache
            return lock, cache

    def _get_openai_responses_cached_unit(self, key: str) -> Any | None:
        lock, cache = self._openai_responses_unit_cache()
        with lock:
            result = cache.get(key)
            if result is None:
                return None
            cache.move_to_end(key)
        return _openai_responses_result_with_cache_hit(result)

    def _store_openai_responses_cached_unit(self, key: str, result: Any) -> None:
        lock, cache = self._openai_responses_unit_cache()
        with lock:
            cache[key] = result
            cache.move_to_end(key)
            while len(cache) > _OPENAI_RESPONSES_UNIT_CACHE_MAX_ENTRIES:
                cache.popitem(last=False)

    def _openai_responses_context_guard(
        self,
        payload: dict[str, Any],
        *,
        model: str,
    ) -> tuple[bool, int, int, int]:
        """Return whether a Responses payload is too close to the model limit."""

        context_limit = _codex_responses_context_limit(self.openai_provider, model)
        if context_limit <= 0:
            return False, 0, 0, 0

        try:
            tokenizer = self.openai_provider.get_token_counter(model)
            text_payload, inline_image_tokens = _responses_context_estimate_payload(payload)
            estimated_tokens = int(tokenizer.count_text(_json_debug_dumps(text_payload)))
            estimated_tokens += inline_image_tokens
        except Exception:
            estimated_tokens = max(
                0,
                len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) // 4,
            )

        reserve = max(
            _CODEX_RESPONSES_CONTEXT_RESERVE_TOKENS,
            int(context_limit * _CODEX_RESPONSES_CONTEXT_RESERVE_RATIO),
        )
        threshold = max(1, context_limit - reserve)
        return estimated_tokens >= threshold, estimated_tokens, threshold, context_limit

    def _openai_responses_compression_failure_refusal(
        self,
        payload: dict[str, Any],
        *,
        model: str,
        exception: BaseException,
        raw_bytes: int,
        client: str | None = None,
    ) -> tuple[bool, int, int, int, str]:
        """Decide whether a Responses compression failure should close.

        The WS relay used to fall back to forwarding the original frame on
        some compression exceptions. That is unsafe once the payload is
        already near the model limit: the upstream can reject the retry with an
        opaque 400/Bad Request, and Codex never gets a clean compaction signal.

        This helper keeps the old small-frame passthrough behavior for truly
        transient failures, but refuses immediately once the context guard says
        the payload is already too large.
        """

        guard_refuse, guard_estimated, guard_threshold, guard_limit = (
            self._openai_responses_context_guard(payload, model=model)
        )
        if guard_refuse:
            return True, guard_estimated, guard_threshold, guard_limit, "context_too_large"

        # HTTP Codex requests intentionally fail open on a compressor timeout
        # after the context guard clears. Keep this shared decision helper in
        # sync with ``handle_openai_responses`` so the WebSocket path and its
        # direct unit contract do not turn a transient local timeout into a
        # spurious client-visible refusal.
        if client == "codex" and isinstance(exception, TimeoutError):
            return (
                False,
                guard_estimated,
                guard_threshold,
                guard_limit,
                "client_override:codex",
            )

        from cutctx.proxy.helpers import decide_compression_failure_action

        failure_action = decide_compression_failure_action(
            exception,
            raw_bytes,
            client=client,
        )
        return (
            failure_action.refuse,
            guard_estimated,
            guard_threshold,
            guard_limit,
            failure_action.reason,
        )

    def _compress_openai_responses_live_text_units_with_router(
        self,
        payload: dict[str, Any],
        *,
        model: str,
        request_id: str,
        pass_id: str | None = None,
        timing: dict[str, float] | None = None,
    ) -> tuple[dict[str, Any], bool, int, list[str], dict[str, int], list[str], int]:
        """Run ContentRouter on OpenAI Responses text units.

        This is the Responses provider scaffold: it extracts text-bearing
        request slots into provider-neutral ``CompressionUnit`` objects, lets
        the shared router enforce role/type policy and choose compressors, then
        splices accepted replacements back into the Responses payload. Opaque
        items such as reasoning, compaction, tool calls, and non-string outputs
        are intentionally not exposed as text units.
        """

        debug_enabled = _codex_compression_debug_enabled()

        def _log(_event: str, **_fields: Any) -> None:
            if debug_enabled:
                _log_codex_compression_debug(
                    _event,
                    request_id=request_id,
                    pass_id=pass_id,
                    model=model,
                    **_fields,
                )

        input_items = payload.get("input")
        messages_items = payload.get("messages")
        items = input_items if isinstance(input_items, list) else messages_items
        if not isinstance(items, list):
            return payload, False, 0, [], {}, [], 0
        try:
            from cutctx.transforms.compression_units import (
                CompressionUnit,
                RoutedCompressionUnit,
                compress_unit_with_router,
                find_content_router,
            )
        except Exception as exc:
            logger.debug(
                "[%s] CompressionUnit adapter unavailable: %s",
                request_id,
                exc,
            )
            return payload, False, 0, [], {}, [], 0

        router = find_content_router(self.openai_pipeline)
        if router is None:
            logger.debug("[%s] OpenAI Responses ContentRouter unavailable", request_id)
            return payload, False, 0, [], {}, [], 0

        try:
            tokenizer = self.openai_provider.get_token_counter(model)
        except Exception as exc:
            logger.debug(
                "[%s] OpenAI Responses ContentRouter tokenizer unavailable: %s",
                request_id,
                exc,
            )
            return payload, False, 0, [], {}, [], 0

        def _slot_text(item: dict[str, Any]) -> tuple[str, tuple[str, int | None]] | None:
            # Only tool-output items are eligible for in-place compression.
            # Message items (user/system/assistant) sit inside the request's
            # cacheable prefix; mutating them busts prefix caching on every
            # subsequent turn. Role-level guards in compression_units.py
            # remain as defense-in-depth.
            type_tag = item.get("type")
            if type_tag in self.OPENAI_RESPONSES_OUTPUT_TYPES:
                output = item.get("output")
                if isinstance(output, str):
                    return output, ("output", None)
            return None

        def _set_slot_text(
            item: dict[str, Any],
            slot: tuple[str, int | None],
            replacement: str,
        ) -> None:
            kind, _ = slot
            if kind == "output":
                item["output"] = replacement

        cutctx_retrieve_call_ids: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function_call":
                continue
            name = item.get("name")
            if isinstance(name, str) and (
                name == "cutctx_retrieve" or name.endswith("__cutctx_retrieve")
            ):
                call_id = item.get("call_id")
                if isinstance(call_id, str) and call_id:
                    cutctx_retrieve_call_ids.add(call_id)

        timing_sink: dict[str, float] = timing if timing is not None else {}

        def _add_timing(name: str, started_at: float) -> None:
            timing_sink[name] = (
                timing_sink.get(name, 0.0) + (time.perf_counter() - started_at) * 1000.0
            )

        extraction_started = time.perf_counter()
        candidates: list[tuple[int, tuple[str, int | None], str]] = []
        extraction_debug: list[dict[str, Any]] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                if debug_enabled:
                    extraction_debug.append(
                        {
                            "index": idx,
                            "eligible": False,
                            "reason": "item_not_dict",
                            "item_type": type(item).__name__,
                            "item": item,
                        }
                    )
                continue
            item_type = item.get("type")
            if item_type in self.OPENAI_RESPONSES_OUTPUT_TYPES:
                call_id = item.get("call_id")
                if isinstance(call_id, str) and call_id in cutctx_retrieve_call_ids:
                    if debug_enabled:
                        extraction_debug.append(
                            {
                                "index": idx,
                                "eligible": False,
                                "reason": "cutctx_retrieve_output_protected",
                                "item_type": item_type,
                                "call_id": call_id,
                                "item": item,
                            }
                        )
                    continue
                slot = _slot_text(item)
                if slot is not None:
                    text, slot_ref = slot
                    if _should_passthrough_large_ml_tool_output(router, text):
                        if debug_enabled:
                            extraction_debug.append(
                                {
                                    "index": idx,
                                    "eligible": False,
                                    "reason": "interactive_ml_latency_guard",
                                    "item_type": item_type,
                                    "call_id": call_id,
                                    "text_chars": len(text),
                                    "text_bytes": len(
                                        text.encode("utf-8", errors="replace")
                                    ),
                                    "item": item,
                                }
                            )
                        continue
                    candidates.append((idx, slot_ref, text))
                    if debug_enabled:
                        extraction_debug.append(
                            {
                                "index": idx,
                                "eligible": True,
                                "item_type": item_type,
                                "role": item.get("role"),
                                "slot": slot_ref,
                                "text_chars": len(text),
                                "text_bytes": len(text.encode("utf-8", errors="replace")),
                                "text_json_shape": _json_shape(text),
                                "item": item,
                                "text": text,
                            }
                        )
                else:
                    if debug_enabled:
                        extraction_debug.append(
                            {
                                "index": idx,
                                "eligible": False,
                                "reason": "output_type_without_text_slot",
                                "item_type": item_type,
                                "item": item,
                            }
                        )
            else:
                if debug_enabled:
                    extraction_debug.append(
                        {
                            "index": idx,
                            "eligible": False,
                            "reason": "unsupported_item_type",
                            "item_type": item_type,
                            "role": item.get("role"),
                            "item": item,
                        }
                    )

        _add_timing("compression_live_unit_extraction", extraction_started)
        _log(
            "codex_compression_extraction",
            item_count=len(items),
            candidate_count=len(candidates),
            payload=payload,
            extraction=extraction_debug,
        )
        if not candidates:
            _log(
                "codex_compression_payload_result",
                modified=False,
                reason="no_candidates",
                tokens_saved_total=0,
                transforms=[],
                input_payload=payload,
                output_payload=payload,
            )
            return payload, False, 0, [], {}, [], 0

        deepcopy_started = time.perf_counter()
        updated = copy.deepcopy(payload)
        _add_timing("compression_payload_deepcopy", deepcopy_started)
        updated_input_items = updated.get("input")
        updated_messages_items = updated.get("messages")
        updated_items = (
            updated_input_items if isinstance(updated_input_items, list) else updated_messages_items
        )
        if not isinstance(updated_items, list):
            return payload, False, 0, [], {}, [], 0

        modified = False
        tokens_saved_total = 0
        # `attempted_input_tokens` is the *compressible* portion of the
        # request — only the tokens we actually fed to the router (i.e.
        # extracted units that passed the floor + role + cache_zone
        # gates). It excludes user messages, system prompts, prior-turn
        # assistant content, and other frozen prefix bytes. This is the
        # right denominator for the dashboard savings ratio: comparing
        # tokens_saved against tokens we ATTEMPTED to compress, not
        # against everything in the request.
        attempted_input_tokens = 0
        transforms: list[str] = []
        routed_units: list[RoutedCompressionUnit] = []

        unit_build_started = time.perf_counter()
        unit_debug: list[dict[str, Any]] = []
        for item_idx, slot_ref, original_text in candidates:
            item = items[item_idx] if item_idx < len(items) else {}
            item_type = item.get("type", "unknown") if isinstance(item, dict) else "unknown"
            role = str(item.get("role") or "tool") if isinstance(item, dict) else "tool"
            unit = CompressionUnit(
                text=original_text,
                provider="openai",
                endpoint="responses",
                role=role,
                item_type=str(item_type),
                cache_zone="live",
                mutable=True,
                min_bytes=self.OPENAI_RESPONSES_ROUTER_MIN_BYTES,
            )
            routed_units.append(RoutedCompressionUnit(unit=unit, slot=(item_idx, slot_ref)))
            if debug_enabled:
                unit_debug.append(
                    {
                        "item_index": item_idx,
                        "slot": slot_ref,
                        "provider": unit.provider,
                        "endpoint": unit.endpoint,
                        "role": unit.role,
                        "item_type": unit.item_type,
                        "cache_zone": unit.cache_zone,
                        "mutable": unit.mutable,
                        "min_bytes": unit.min_bytes,
                        "text_chars": len(unit.text),
                        "text_bytes": len(unit.text.encode("utf-8", errors="replace")),
                        "text_json_shape": _json_shape(unit.text),
                        "text": unit.text,
                    }
                )
        _add_timing("compression_unit_build", unit_build_started)

        _log(
            "codex_compression_units",
            units=unit_debug,
        )

        # Tally per-category counts as units stream in so the pass_summary
        # event below can emit a one-line breakdown — log readers shouldn't
        # have to re-aggregate from scattered unit_result events.
        units_by_category: dict[str, int] = {}
        strategy_chain_union: list[str] = []

        def _compress_routed_unit(
            routed: RoutedCompressionUnit,
        ) -> tuple[object, Any, float]:
            # `elapsed_ms` is pure compute time. Prior to the P2 scheduler
            # fix this was wall-clock-from-submit, which conflated
            # semaphore wait with real work — passthrough units showed
            # `elapsed_ms=60000+` in production logs even though they did
            # no work. With the semaphore deleted, this timer is honest.
            unit_started = time.perf_counter()
            result = compress_unit_with_router(routed.unit, router=router, tokenizer=tokenizer)
            elapsed_ms = (time.perf_counter() - unit_started) * 1000.0
            return routed.slot, result, elapsed_ms

        router_total_started = time.perf_counter()
        routed_results: list[tuple[object, Any, float] | None] = [None] * len(routed_units)
        cache_misses: list[tuple[int, str, RoutedCompressionUnit]] = []
        cache_miss_followers: dict[str, list[int]] = {}
        for unit_idx, routed in enumerate(routed_units):
            cache_key = _openai_responses_unit_cache_key(routed.unit, model=model)
            cached = self._get_openai_responses_cached_unit(cache_key)
            if cached is not None:
                routed_results[unit_idx] = (routed.slot, cached, 0.0)
                continue
            if cache_key in cache_miss_followers:
                cache_miss_followers[cache_key].append(unit_idx)
                continue
            cache_miss_followers[cache_key] = []
            cache_misses.append((unit_idx, cache_key, routed))

        def _compress_and_store(
            unit_idx: int,
            cache_key: str,
            routed: RoutedCompressionUnit,
        ) -> tuple[int, str, tuple[object, Any, float]]:
            slot, result, elapsed_ms = _compress_routed_unit(routed)
            self._store_openai_responses_cached_unit(cache_key, result)
            return unit_idx, cache_key, (slot, result, elapsed_ms)

        def _record_routed_result(
            unit_idx: int,
            cache_key: str,
            routed_result: tuple[object, Any, float],
        ) -> None:
            routed_results[unit_idx] = routed_result
            _slot, result, _elapsed_ms = routed_result
            for follower_idx in cache_miss_followers.get(cache_key, []):
                routed_results[follower_idx] = (
                    routed_units[follower_idx].slot,
                    _openai_responses_result_with_cache_hit(result),
                    0.0,
                )

        parallelism = _openai_responses_unit_parallelism()
        if len(cache_misses) > 1 and parallelism > 1:
            executor = _openai_responses_unit_executor()
            for start in range(0, len(cache_misses), parallelism):
                batch = cache_misses[start : start + parallelism]
                futures = [executor.submit(_compress_and_store, *item) for item in batch]
                for future in as_completed(futures):
                    unit_idx, cache_key, routed_result = future.result()
                    _record_routed_result(unit_idx, cache_key, routed_result)
        else:
            for unit_idx, cache_key, routed in cache_misses:
                _record_routed_result(
                    unit_idx,
                    cache_key,
                    _compress_and_store(unit_idx, cache_key, routed)[2],
                )

        ordered_routed_results = [result for result in routed_results if result is not None]

        for _, result, elapsed_ms in ordered_routed_results:
            router_chain = list(result.router_result.strategy_chain) if result.router_result else []
            router_content_type = (
                result.router_result.routing_log[0].content_type.value
                if result.router_result and result.router_result.routing_log
                else "unknown"
            )
            timing_sink["compression_unit_router_total"] = (
                timing_sink.get("compression_unit_router_total", 0.0) + elapsed_ms
            )
            timing_sink[f"compression_unit_router_strategy_{result.strategy}"] = (
                timing_sink.get(f"compression_unit_router_strategy_{result.strategy}", 0.0)
                + elapsed_ms
            )
            timing_sink[f"compression_unit_router_category_{result.reason_category}"] = (
                timing_sink.get(f"compression_unit_router_category_{result.reason_category}", 0.0)
                + elapsed_ms
            )
            record_unit = getattr(getattr(self, "metrics", None), "record_codex_ws_unit", None)
            if record_unit is not None:
                record_unit(
                    strategy=result.strategy,
                    reason_category=result.reason_category,
                    elapsed_ms=elapsed_ms,
                    text_bytes=result.text_bytes,
                    tokens_before=result.tokens_before,
                    tokens_after=result.tokens_after,
                    tokens_saved=result.tokens_saved,
                    modified=result.modified,
                    strategy_chain=router_chain,
                    content_type=router_content_type,
                    text_shape=_codex_ws_text_shape(result.original),
                )
            if elapsed_ms >= 1000.0:
                logger.info(
                    "[%s] WS /v1/responses slow compression unit "
                    "elapsed_ms=%.0f strategy=%s category=%s modified=%s "
                    "content_type=%s text_shape=%s bytes=%d min_bytes=%d "
                    "tokens_before=%d tokens_after=%d tokens_saved=%d "
                    "strategy_chain=%s",
                    request_id,
                    elapsed_ms,
                    result.strategy,
                    result.reason_category,
                    result.modified,
                    router_content_type,
                    _codex_ws_text_shape(result.original),
                    result.text_bytes,
                    result.min_bytes,
                    result.tokens_before,
                    result.tokens_after,
                    result.tokens_saved,
                    router_chain,
                )
        _add_timing("compression_units_router_loop", router_total_started)

        apply_started = time.perf_counter()
        for slot, result, _elapsed_ms in ordered_routed_results:
            item_idx, slot_ref = slot
            router_chain = list(result.router_result.strategy_chain) if result.router_result else []
            for s in router_chain:
                if s not in strategy_chain_union:
                    strategy_chain_union.append(s)
            cat = result.reason_category or "applied"
            units_by_category[cat] = units_by_category.get(cat, 0) + 1
            # A unit "reached the router" iff the result carries a
            # router_result OR was modified — both indicate we got
            # past the early gates. Units that were size-floored,
            # role-protected, or in a frozen cache_zone don't count.
            if result.router_result is not None or result.modified:
                attempted_input_tokens += result.tokens_before
            if debug_enabled:
                _log(
                    "codex_compression_unit_result",
                    item_index=item_idx,
                    slot=slot_ref,
                    modified=result.modified,
                    reason=result.reason,
                    reason_category=cat,
                    text_bytes=result.text_bytes,
                    min_bytes=result.min_bytes,
                    strategy=result.strategy,
                    strategy_chain=router_chain,
                    tokens_before=result.tokens_before,
                    tokens_after=result.tokens_after,
                    tokens_saved=result.tokens_saved,
                    transforms_applied=result.transforms_applied,
                    router_strategy=(
                        result.router_result.strategy_used.value if result.router_result else None
                    ),
                    router_summary=result.router_result.summary() if result.router_result else None,
                    router_routing_log=_routing_log_debug(result.router_result),
                    router_cache_hit=(
                        result.router_result.cache_hit if result.router_result else False
                    ),
                    original=result.original,
                    compressed=result.compressed,
                )
            if not result.modified:
                continue

            target_item = updated_items[item_idx]
            if not isinstance(target_item, dict):
                continue
            _set_slot_text(target_item, slot_ref, result.compressed)
            modified = True
            tokens_saved_total += result.tokens_saved
            for transform in result.transforms_applied:
                if transform not in transforms:
                    transforms.append(transform)
        _add_timing("compression_unit_apply_results", apply_started)

        _log(
            "codex_compression_payload_result",
            modified=modified,
            tokens_saved_total=tokens_saved_total,
            attempted_input_tokens=attempted_input_tokens,
            transforms=transforms,
            units_by_category=units_by_category,
            strategy_chain=strategy_chain_union,
            input_payload=payload,
            output_payload=updated if modified else payload,
        )
        return (
            updated,
            modified,
            tokens_saved_total,
            transforms,
            units_by_category,
            strategy_chain_union,
            attempted_input_tokens,
        )

    def _compress_openai_responses_payload(
        self,
        payload: dict[str, Any],
        *,
        model: str,
        request_id: str,
        timing: dict[str, float] | None = None,
        compact_tool_schemas: bool = True,
        allow_payload_mutation: bool = True,
    ) -> tuple[dict[str, Any], bool, int, list[str], str | None, int, int, int]:
        """Compress an OpenAI Responses payload through the shared router.

        Provider adapters pass only the inner Responses payload here. This
        function is envelope-agnostic: it extracts Responses text slots into
        provider-neutral compression units, lets ContentRouter choose the
        compressor, then splices accepted replacements back into the payload.
        """

        timing_sink: dict[str, float] = timing if timing is not None else {}

        def _add_timing(name: str, started_at: float) -> None:
            timing_sink[name] = (
                timing_sink.get(name, 0.0) + (time.perf_counter() - started_at) * 1000.0
            )

        input_serialization_started = time.perf_counter()
        input_bytes = json.dumps(payload).encode("utf-8")
        _add_timing("compression_input_json_dump", input_serialization_started)
        if not allow_payload_mutation:
            return (
                payload,
                False,
                0,
                [],
                "subscription_passthrough",
                len(input_bytes),
                len(input_bytes),
                0,
            )
        # Codex/Responses requests can re-enter this method many times per
        # request_id (one per turn over the same websocket). Tag every
        # event in this single pass with a content-derived id so dashboards
        # can attribute each unit_result to its originating pass.
        # Aggregation note: per-pass `tokens_saved` SHOULD sum across
        # passes — every pass independently avoided sending those tokens
        # upstream, regardless of any prefix cache the upstream applies.
        # Identical pass_ids within one request_id indicate idempotent
        # retries on the same input bytes and are the only thing that
        # should be deduped.
        debug_enabled = _codex_compression_debug_enabled()
        pass_id = hashlib.sha256(input_bytes).hexdigest()[:12] if debug_enabled else None
        input_context_budget: dict[str, Any] | None = None
        if debug_enabled:
            input_context_budget = _openai_responses_context_budget(payload)
            _log_codex_compression_debug(
                "codex_compression_payload_input",
                request_id=request_id,
                pass_id=pass_id,
                model=model,
                input_bytes=len(input_bytes),
                context_budget=input_context_budget,
                input_top_level_keys=list(payload.keys()),
                input_field_type=type(payload.get("input")).__name__,
                messages_field_type=type(payload.get("messages")).__name__,
                payload=payload,
            )
        working = payload
        canary_arm = str(
            getattr(self, "_savings_canary_assignments", {}).get(request_id, "control")
        )
        modified = False
        tokens_saved = 0
        transforms: list[str] = []
        reason: str | None = None

        tool_compaction_started = time.perf_counter()
        if compact_tool_schemas:
            # Use shared schema compressor (30+ key drops + description truncation)
            try:
                from cutctx.proxy.schema_compress import (
                    compress_tool_results,
                    compress_tool_schemas,
                )

                _tools_list = working.get("tools")
                if isinstance(_tools_list, list) and _tools_list:
                    compacted_tools, tools_modified, tools_before_bytes, tools_after_bytes = (
                        compress_tool_schemas(
                            _tools_list,
                            max_description_length=120 if canary_arm == "tool_api_slimming" else 200,
                            aggressive=canary_arm == "tool_api_slimming",
                        )
                    )
                    if tools_modified:
                        compacted_payload = {**working, "tools": compacted_tools}
                        working = compacted_payload
                else:
                    tools_modified, tools_before_bytes, tools_after_bytes = False, 0, 0
            except ImportError:
                compacted_payload, tools_modified, tools_before_bytes, tools_after_bytes = (
                    _compact_openai_responses_tools(working)
                )
                if tools_modified:
                    working = compacted_payload
        else:
            tools_modified, tools_before_bytes, tools_after_bytes = False, 0, 0
        _add_timing("compression_tool_schema_compaction", tool_compaction_started)
        if tools_modified:
            working = compacted_payload
            modified = True
            reason = None
            transforms.append("openai:responses:tool_schema_compaction")
            try:
                tool_token_started = time.perf_counter()
                tokenizer = self.openai_provider.get_token_counter(model)
                tokens_saved += max(
                    0,
                    tokenizer.count_text(_json_debug_dumps(payload.get("tools")))
                    - tokenizer.count_text(_json_debug_dumps(working.get("tools"))),
                )
                _add_timing("compression_tool_schema_token_count", tool_token_started)
            except Exception:
                pass
            if debug_enabled:
                _log_codex_compression_debug(
                    "codex_tool_schema_compaction",
                    request_id=request_id,
                    pass_id=pass_id,
                    model=model,
                    modified=True,
                    tools_bytes_before=tools_before_bytes,
                    tools_bytes_after=tools_after_bytes,
                    tools_bytes_saved=tools_before_bytes - tools_after_bytes,
                )

        live_units_started = time.perf_counter()

        # Compress tool results (positional array format for homogeneous data)
        try:
            from cutctx.proxy.schema_compress import compress_tool_results

            if working.get("input") and isinstance(working["input"], list):
                working = {
                    **working,
                    "input": compress_tool_results(
                        working["input"],
                        max_array_items_for_positional=25 if canary_arm == "mutable_tail" else 10,
                        min_fields_for_positional=2 if canary_arm == "mutable_tail" else 3,
                    ),
                }
        except Exception:
            pass

        (
            router_payload,
            router_modified,
            router_saved,
            router_transforms,
            units_by_category,
            strategy_chain,
            router_attempted_tokens,
        ) = self._compress_openai_responses_live_text_units_with_router(
            working,
            model=model,
            request_id=request_id,
            pass_id=pass_id,
            timing=timing_sink,
        )
        _add_timing("compression_live_units_total", live_units_started)
        if router_modified:
            working = router_payload
            modified = True
            reason = None
            tokens_saved += int(router_saved)
            transforms.extend(router_transforms)
        elif not modified:
            reason = "router_no_compression"

        live_user_started = time.perf_counter()
        (
            live_user_payload,
            live_user_modified,
            live_user_saved,
            live_user_transforms,
            live_user_attempted_tokens,
        ) = self._compress_openai_responses_latest_user_tail_with_router(
            working,
            model=model,
            request_id=request_id,
            question=None,
            timing=timing,
        )
        _add_timing("compression_live_user_tail_total", live_user_started)
        if live_user_modified:
            working = live_user_payload
            modified = True
            reason = None
            tokens_saved += int(live_user_saved)
            transforms.extend(live_user_transforms)

        # Total tokens we *attempted* to compress on this pass:
        # router-fed unit tokens + the original (pre-compaction) tool
        # schema tokens we ran schema_compaction against. Excludes
        # instructions, user messages, prior assistant turns, and
        # other prefix bytes we never tried to touch — those belong
        # to the prefix-cache denominator, not the active-compression
        # one.
        attempted_input_tokens = int(router_attempted_tokens) + int(live_user_attempted_tokens)
        if tools_modified:
            try:
                attempted_token_started = time.perf_counter()
                tokenizer = self.openai_provider.get_token_counter(model)
                attempted_input_tokens += tokenizer.count_text(
                    _json_debug_dumps(payload.get("tools"))
                )
                _add_timing(
                    "compression_tool_schema_attempted_token_count",
                    attempted_token_started,
                )
            except Exception:
                pass

        dedupe_started = time.perf_counter()
        deduped: list[str] = []
        for transform in transforms:
            if transform not in deduped:
                deduped.append(transform)
        _add_timing("compression_transform_dedupe", dedupe_started)

        output_serialization_started = time.perf_counter()
        output_bytes = json.dumps(working).encode("utf-8")
        _add_timing("compression_output_json_dump", output_serialization_started)
        output_context_budget = _openai_responses_context_budget(working) if debug_enabled else None
        # One-line summary at INFO — the single event a human reading
        # logs should scan first to understand "what happened on this
        # pass". All the verbose per-event debug data stays available
        # but at DEBUG level. Contains: byte totals, savings, the
        # strategy chain we walked, unit-outcome counts by category,
        # and the transforms applied.
        savings_pct = (
            (1.0 - len(output_bytes) / len(input_bytes)) * 100.0 if len(input_bytes) else 0.0
        )
        # Active-compression ratio: savings as a fraction of what we
        # *attempted* to compress, not of the whole request. The whole-
        # request ratio is in `savings_pct`; this one is the metric the
        # dashboard should display (otherwise frozen prefix bytes drown
        # the wins from the compressible tail).
        #
        # Math note: `attempted_input_tokens` is the pre-compression
        # size of the eligible content (sum of unit.tokens_before +
        # original tool schema). `tokens_saved` is what we removed
        # from it. So the savings rate is plain `saved / attempted` —
        # NOT `saved / (attempted + saved)`, which would double-count.
        attempted_pct = (
            (tokens_saved / attempted_input_tokens) * 100.0 if attempted_input_tokens > 0 else 0.0
        )
        if debug_enabled:
            _log_codex_compression_debug(
                "codex_compression_pass_summary",
                request_id=request_id,
                pass_id=pass_id,
                model=model,
                modified=modified,
                reason=reason,
                input_bytes=len(input_bytes),
                output_bytes=len(output_bytes),
                bytes_saved=len(input_bytes) - len(output_bytes),
                savings_pct=round(savings_pct, 2),
                tokens_saved=tokens_saved,
                attempted_input_tokens=attempted_input_tokens,
                attempted_pct=round(attempted_pct, 2),
                strategy_chain=strategy_chain,
                units_by_category=units_by_category,
                transforms=deduped,
            )
            _log_codex_compression_debug(
                "codex_compression_payload_output",
                request_id=request_id,
                pass_id=pass_id,
                model=model,
                modified=modified,
                reason=reason,
                tokens_saved=tokens_saved,
                attempted_input_tokens=attempted_input_tokens,
                transforms=deduped,
                input_bytes=len(input_bytes),
                output_bytes=len(output_bytes),
                context_budget_before=input_context_budget,
                context_budget_after=output_context_budget,
                input_payload=payload,
                output_payload=working,
            )
        return (
            working,
            modified,
            tokens_saved,
            deduped,
            reason,
            len(input_bytes),
            len(output_bytes),
            attempted_input_tokens,
        )

    async def _compress_openai_responses_payload_in_executor(
        self,
        payload: dict[str, Any],
        *,
        model: str,
        request_id: str,
        compact_tool_schemas: bool = True,
        allow_payload_mutation: bool = True,
    ) -> tuple[dict[str, Any], bool, int, list[str], str | None, int, int, int, dict[str, float]]:
        timing: dict[str, float] = {}

        def _compress():  # noqa: ANN202
            compress_fn = self._compress_openai_responses_payload
            kwargs: dict[str, Any] = {
                "model": model,
                "request_id": request_id,
                "timing": timing,
                "compact_tool_schemas": compact_tool_schemas,
                "allow_payload_mutation": allow_payload_mutation,
            }
            # Tests, plugins, and older subclasses may replace this method with
            # the pre-policy signature. Filter only unsupported keyword
            # parameters up front so timing still flows whenever the override
            # supports it, without catching TypeError raised inside compression.
            parameters = inspect.signature(compress_fn).parameters
            accepts_kwargs = any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )
            if not accepts_kwargs:
                kwargs = {name: value for name, value in kwargs.items() if name in parameters}
            return compress_fn(payload, **kwargs)

        result = await self._run_compression_in_executor(
            _compress,
            timeout=COMPRESSION_TIMEOUT_SECONDS,
        )
        if len(result) == 8:
            return (*result, timing)
        return result

    def _compress_openai_responses_latest_user_tail_with_router(
        self,
        payload: dict[str, Any],
        *,
        model: str,
        request_id: str,
        question: str | None = None,
        timing: dict[str, float] | None = None,
    ) -> tuple[dict[str, Any], bool, int, list[str], int]:
        """Compress the latest user turn only."""

        debug_enabled = _codex_compression_debug_enabled()
        timing_sink: dict[str, float] = timing if timing is not None else {}

        def _add_timing(name: str, started_at: float) -> None:
            timing_sink[name] = (
                timing_sink.get(name, 0.0) + (time.perf_counter() - started_at) * 1000.0
            )

        input_data = payload.get("input")
        if not isinstance(input_data, str | list):
            return payload, False, 0, [], 0

        latest_user_index: int | None = None
        latest_user_block_index: int | None = None
        original_text: str | None = None
        is_string_input = isinstance(input_data, str)

        if is_string_input:
            original_text = input_data
        else:
            for item_index in range(len(input_data) - 1, -1, -1):
                item = input_data[item_index]
                if not isinstance(item, dict) or item.get("role") != "user":
                    continue
                if "cache_control" in item:
                    continue
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    latest_user_index = item_index
                    original_text = content
                    break
                if isinstance(content, list):
                    for block_index, block in enumerate(content):
                        if not isinstance(block, dict) or "cache_control" in block:
                            continue
                        if block.get("type") not in {"input_text", "text"}:
                            continue
                        block_text = block.get("text")
                        if isinstance(block_text, str) and block_text.strip():
                            latest_user_index = item_index
                            latest_user_block_index = block_index
                            original_text = block_text
                            break
                    if original_text is not None:
                        break

        if original_text is None or not original_text.strip():
            return payload, False, 0, [], 0

        try:
            tokenizer = self.openai_provider.get_token_counter(model)
        except Exception as exc:
            logger.debug(
                "[%s] OpenAI Responses live user-tail tokenizer unavailable: %s",
                request_id,
                exc,
            )
            return payload, False, 0, [], 0

        if (
            len(original_text.encode("utf-8", errors="replace"))
            < self.OPENAI_RESPONSES_ROUTER_MIN_BYTES
        ):
            return payload, False, 0, [], 0

        try:
            from cutctx.transforms.compression_units import find_content_router
        except Exception as exc:
            logger.debug(
                "[%s] OpenAI Responses live user-tail adapter unavailable: %s",
                request_id,
                exc,
            )
            return payload, False, 0, [], 0

        router = find_content_router(self.openai_pipeline)
        if router is None:
            logger.debug("[%s] OpenAI Responses live user-tail router unavailable", request_id)
            return payload, False, 0, [], 0

        # Keep Responses aligned with the shared router's default safety
        # policy. User input is the subject of the request and part of the
        # provider's cacheable prefix, so it must not pay compressor latency
        # (or be mutated) unless the operator explicitly enabled
        # ``--compress-user-messages``.
        if router.config.skip_user_messages:
            return payload, False, 0, [], 0

        user_question = question or original_text
        started = time.perf_counter()
        try:
            router_result = router.compress(original_text, question=user_question, bias=1.0)
        except Exception as exc:
            logger.debug(
                "[%s] OpenAI Responses live user-tail compression failed: %s",
                request_id,
                exc,
            )
            return payload, False, 0, [], 0
        finally:
            _add_timing("compression_live_user_tail_router", started)

        replacement = router_result.compressed
        if replacement == original_text:
            tokens_before = tokenizer.count_text(original_text)
            return payload, False, 0, [], tokens_before

        tokens_before = tokenizer.count_text(original_text)
        tokens_after = tokenizer.count_text(replacement)
        if tokens_after >= tokens_before:
            return payload, False, 0, [], tokens_before

        if is_string_input:
            payload["input"] = replacement
        else:
            assert latest_user_index is not None
            user_item = dict(input_data[latest_user_index])
            content = user_item.get("content")
            if isinstance(content, str):
                user_item["content"] = replacement
            elif isinstance(content, list) and latest_user_block_index is not None:
                updated_blocks = list(content)
                block = dict(updated_blocks[latest_user_block_index])
                block["text"] = replacement
                updated_blocks[latest_user_block_index] = block
                user_item["content"] = updated_blocks
            else:
                return payload, False, 0, [], 0
            updated_input = list(input_data)
            updated_input[latest_user_index] = user_item
            payload["input"] = updated_input

        strategy = router_result.strategy_used.value
        if debug_enabled:
            logger.info(
                "[%s] /v1/responses live user-tail compressed %d→%d tokens (strategy=%s)",
                request_id,
                tokens_before,
                tokens_after,
                strategy,
            )
        return (
            payload,
            True,
            tokens_before - tokens_after,
            [
                f"router:openai:responses:user_input:{strategy}",
                strategy,
            ],
            tokens_before,
        )

    async def handle_openai_responses(
        self,
        request: Request,
    ) -> Response | StreamingResponse:
        """Handle OpenAI /v1/responses endpoint (new Responses API).

        The Responses API differs from /v1/chat/completions:
        - Input: `input` (string or array) instead of `messages`
        - System: `instructions` instead of system message
        - Output: `output[]` array instead of `choices[].message`
        - State: `previous_response_id` for multi-turn
        - Built-in tools: web_search, file_search, code_interpreter
        """
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse, Response

        from cutctx.proxy.helpers import (
            MAX_REQUEST_BODY_SIZE,
            _read_request_json,
        )
        from cutctx.tokenizers import get_tokenizer
        from cutctx.utils import extract_user_query

        start_time = time.time()
        request_id = (
            getattr(getattr(request, "state", None), "cutctx_request_id", None)
            or await self._next_request_id()
        )

        # Phase F PR-F1: classify auth mode at request entry. The result
        # is stored on `request.state` so downstream handlers (cache
        # gates, header injection, lossy-compressor gates) read it
        # without re-classifying. Pure function, well under 10us.
        auth_mode = classify_auth_mode(request.headers)
        request.state.auth_mode = auth_mode
        logger.debug(f"[{request_id}] auth_mode_classified mode={auth_mode.value}")

        # Check request body size
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "message": f"Request body too large. Maximum size is {MAX_REQUEST_BODY_SIZE // (1024 * 1024)}MB",
                        "type": "invalid_request_error",
                        "code": "request_too_large",
                    }
                },
            )

        # Parse request
        try:
            body = await _read_request_json(request)
        except (json.JSONDecodeError, ValueError) as e:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": f"Invalid request body: {e!s}",
                        "type": "invalid_request_error",
                        "code": "invalid_json",
                    }
                },
            )

        model = body.get("model", "unknown")
        requested_model = model
        original_reasoning = (
            copy.deepcopy(body["reasoning"]) if "reasoning" in body else _MISSING_ROUTING_FIELD
        )
        stream = body.get("stream", False)
        _bypass = self._cutctx_bypass_enabled(request.headers)
        if _bypass:
            logger.info(
                "[%s] Responses passthrough reason=bypass_header mutation=disabled",
                request_id,
            )

        from cutctx.proxy.helpers import capture_codex_wire_debug

        capture_codex_wire_debug(
            "http_inbound_request",
            request_id=request_id,
            transport="http",
            direction="client_to_cutctx",
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers.items()),
            body=body,
            metadata={"path": request.url.path, "stream": stream},
        )

        # /v1/responses uses provider-specific CompressionUnit extraction
        # below, then routes mutable text through ContentRouter. The
        # standalone Rust proxy has native item-aware handling, but the
        # Python CLI runtime does not run that proxy today. We synthesise a
        # minimal `messages` list purely for downstream memory injection and
        # telemetry; list-typed `input` is consulted directly by the unit
        # extraction helpers.
        input_data = body.get("input", "")
        instructions = body.get("instructions")
        request_savings_metadata = extract_savings_metadata(
            request_headers=request.headers,
            body=body,
        )
        schema_savings_metadata = None
        tool_surface_query = extract_responses_query(body)

        messages: list[dict[str, Any]] = []
        if instructions:
            messages.append({"role": "system", "content": instructions})
        if isinstance(input_data, str):
            messages.append({"role": "user", "content": input_data})
        routing_messages = _responses_payload_to_routing_messages(body)
        from cutctx.proxy.canary_identity import resolve_canary_identity
        from cutctx.proxy.model_router import prepare_model_routing
        from cutctx.proxy.savings_canary import get_savings_canary_coordinator

        _canary_coordinator = get_savings_canary_coordinator()
        _canary_identity = resolve_canary_identity(
            headers=dict(request.headers.items()),
            body=body,
            request_id=request_id,
            salt=_canary_coordinator.salt,
        )
        raw_request_headers = dict(request.headers.items())
        _, is_chatgpt_subscription = _resolve_codex_routing_headers(raw_request_headers)
        is_remote_compaction = (
            is_chatgpt_subscription
            and _is_remote_compaction_subscription_request(body)
        )
        from cutctx.proxy.handlers.openai.utils import _has_codex_responses_lite_hint

        codex_responses_lite = _has_codex_responses_lite_hint(raw_request_headers)

        if not is_remote_compaction:
            model, request_savings_metadata = prepare_model_routing(
                self,
                model,
                request_savings_metadata=request_savings_metadata,
                tool_calls=len(body.get("tools") or []),
                num_messages=len(routing_messages),
                messages=routing_messages,
                request_id=_canary_identity.value,
                client=classify_client(dict(request.headers.items())),
                assignment_identity_source=_canary_identity.source,
                assignment_sticky=_canary_identity.sticky,
                transport_provider="openai",
                implicit_downgrade_allowed=not (
                    is_chatgpt_subscription or codex_responses_lite
                ),
                allow_transport_safe_targets=not is_chatgpt_subscription,
            )
        _canary_assignments = getattr(self, "_savings_canary_assignments", None)
        if _canary_assignments is None:
            _canary_assignments = {}
            self._savings_canary_assignments = _canary_assignments
        _canary_assignments[request_id] = str(
            ((request_savings_metadata or {}).get("savings_canary") or {}).get("arm", "control")
        )
        while len(_canary_assignments) > 2048:
            _canary_assignments.pop(next(iter(_canary_assignments)))
        if not is_remote_compaction:
            body["model"] = model
            _apply_model_routing_request_overrides(body, request_savings_metadata)

        headers = dict(request.headers.items())
        headers.pop("host", None)
        headers.pop("content-length", None)
        # Strip accept-encoding so httpx negotiates its own encoding.
        # Cloudflare Workers forward "br, zstd" which OpenAI may honor;
        # if httpx lacks brotli support the response body is undecipherable → 502.
        headers.pop("accept-encoding", None)
        tags = extract_tags(headers)
        client = classify_client(headers)
        # PR-A5 (P5-49): strip internal x-cutctx-* from upstream-bound
        # headers AFTER `_extract_tags` reads them. Memory user-id reads
        # `request.headers` below.
        from cutctx.proxy.handlers.openai.utils import _strip_openai_internal_headers
        from cutctx.proxy.helpers import _strip_internal_headers, log_outbound_headers

        _pre_strip_count_resp = sum(1 for k in headers if k.lower().startswith("x-cutctx-"))
        headers = _strip_internal_headers(headers)
        headers = _strip_openai_internal_headers(headers)
        from cutctx.proxy.auth_keyring import inject_provider_authorization

        if inject_provider_authorization(headers, "openai"):
            logger.debug(
                "[%s] injected OpenAI Authorization from configured credentials", request_id
            )
        log_outbound_headers(
            forwarder="openai_responses",
            stripped_count=_pre_strip_count_resp,
            request_id=request_id,
        )

        # PR-A6 (P5-50, preps P0-6): session-sticky `OpenAI-Beta` merge
        # for /v1/responses. Compute a session_id off the same store the
        # chat handler uses so multi-endpoint clients within one
        # conversation share the sticky-token set.
        _responses_session_id = self.session_tracker_store.compute_session_id(
            request, model, messages
        )
        from cutctx.proxy.helpers import (
            get_session_beta_tracker as _get_session_beta_tracker_resp,
        )
        from cutctx.proxy.helpers import (
            log_beta_header_merge as _log_beta_header_merge_resp,
        )

        _client_resp_beta = headers.get("openai-beta")
        _client_resp_beta_count = (
            len([t for t in (_client_resp_beta or "").split(",") if t.strip()])
            if _client_resp_beta
            else 0
        )
        _sticky_resp_beta = _get_session_beta_tracker_resp().record_and_get_sticky_betas(
            provider="openai",
            session_id=_responses_session_id,
            client_value=_client_resp_beta,
        )
        _sticky_resp_beta_count = (
            len([t for t in _sticky_resp_beta.split(",") if t.strip()]) if _sticky_resp_beta else 0
        )
        if _sticky_resp_beta and _sticky_resp_beta != (_client_resp_beta or ""):
            headers["openai-beta"] = _sticky_resp_beta
        _log_beta_header_merge_resp(
            provider="openai",
            session_id=_responses_session_id,
            client_betas_count=_client_resp_beta_count,
            sticky_betas_count=_sticky_resp_beta_count,
            cutctx_added=[],
            request_id=request_id,
        )

        # Memory: Get user ID when memory is enabled. Reads `request.headers`
        # directly because `headers` was stripped of `x-cutctx-*` (PR-A5).
        memory_user_id: str | None = None
        memory_request_ctx = None
        if self.memory_handler:
            memory_user_id = request.headers.get(
                "x-cutctx-user-id",
                os.environ.get("USER", os.environ.get("USERNAME", "default")),
            )
            from cutctx.memory.storage_router import (
                RequestContext as _MemRequestContext,
            )
            from cutctx.memory.storage_router import (
                extract_system_prompt as _extract_sys_prompt,
            )

            memory_request_ctx = _MemRequestContext(
                headers=dict(request.headers),
                system_prompt=_extract_sys_prompt(body),
                base_user_id=memory_user_id,
                project_root_override=(
                    getattr(self.memory_handler.config, "project_root_override", "") or None
                ),
            )

        # Rate limiting
        if self.rate_limiter:
            rate_key = headers.get("authorization", "default")[:20]
            allowed, wait_seconds = await self.rate_limiter.check_request(rate_key)
            if not allowed:
                await self.metrics.record_rate_limited(provider="openai")
                self.record_rate_limit_denial(
                    request_id=request_id,
                    provider="openai",
                    model=model,
                    wait_seconds=wait_seconds,
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limited. Retry after {wait_seconds:.1f}s",
                    headers={
                        "Retry-After": str(max(1, int(wait_seconds))),
                        "X-Request-ID": request_id,
                    },
                )

        # Token counting on converted messages
        tokenizer = get_tokenizer(model)
        original_tokens = tokenizer.count_messages(messages)

        # Defaults below feed downstream telemetry and memory injection.
        # If optimization remains enabled, the Responses payload is compressed
        # later through `_compress_openai_responses_payload`.
        optimized_messages = messages
        optimized_tokens = original_tokens
        tokens_saved = 0
        # Eligible-only denominator for the active compression ratio.
        # Populated by `_compress_openai_responses_payload` if it runs;
        # stays 0 on bypass / passthrough paths so we don't fabricate a
        # denominator we haven't earned.
        attempted_input_tokens = 0
        transforms_applied: list[str] = []
        optimization_latency = (time.time() - start_time) * 1000

        # Memory: inject context and tools for Responses API requests.
        # Gated on MemoryDecision — uniformly respects bypass across all
        # five injection sites. The Responses path is the only one that
        # injects BEFORE compression today (sites 1/2/3 inject after);
        # bringing this into alignment is queued as a follow-up
        # (FUTURE: move context injection to post-compression for
        # uniform "memory text rides uncompressed across all
        # handlers" semantics — separate PR with cache-stability tests).
        from cutctx.proxy.helpers import get_memory_injection_mode
        from cutctx.proxy.memory_decision import MemoryDecision
        from cutctx.proxy.memory_query import MemoryQuery

        responses_memory_decision = MemoryDecision.decide(
            headers=request.headers,
            memory_handler=self.memory_handler,
            memory_user_id=memory_user_id,
            mode_name=get_memory_injection_mode(),
            messages=optimized_messages,
        )
        responses_memory_decision.apply_to_tags(tags)
        if responses_memory_decision.inject:
            try:
                # Memory context now routes exclusively to the live-zone tail
                # (latest non-frozen user item). Instructions are part of the
                # cache hot zone and must never be mutated — invariant I2.
                # See REALIGNMENT/03-phase-A-lockdown.md PR-A2.
                if self.memory_handler.config.inject_context:
                    try:
                        memory_context = await asyncio.wait_for(
                            self.memory_handler.search_and_format_context(
                                memory_user_id,
                                optimized_messages,
                                request_context=memory_request_ctx,
                                query=MemoryQuery.from_messages(optimized_messages),
                            ),
                            timeout=RESPONSES_CONTEXT_SEARCH_TIMEOUT_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        memory_context = None
                        logger.info(
                            f"[{request_id}] Memory context lookup exceeded "
                            f"{RESPONSES_CONTEXT_SEARCH_TIMEOUT_SECONDS:.1f}s; continuing without it"
                        )
                    if memory_context:
                        from cutctx.proxy.helpers import (
                            append_text_to_latest_user_input_item,
                            get_memory_injection_mode,
                            log_memory_injection,
                        )

                        injection_mode = get_memory_injection_mode()
                        user_query = extract_user_query(optimized_messages) or ""
                        if injection_mode == "disabled":
                            log_memory_injection(
                                request_id=request_id,
                                session_id=None,
                                decision="skipped_disabled",
                                bytes_injected=0,
                                query=user_query,
                            )
                        else:
                            # Route into body["input"] (the canonical Responses API
                            # field) targeting the latest user item's first text
                            # block. body["instructions"] (cache hot zone) is left
                            # untouched.
                            current_input = body.get("input")
                            if isinstance(current_input, str):
                                # String input: append to it. The string IS the
                                # latest user content; appending here is the
                                # equivalent of the live-zone tail.
                                body["input"] = (
                                    current_input + "\n\n" + memory_context
                                    if current_input
                                    else memory_context
                                )
                                log_memory_injection(
                                    request_id=request_id,
                                    session_id=None,
                                    decision="injected_live_zone_tail_string",
                                    bytes_injected=len(memory_context),
                                    query=user_query,
                                )
                            elif isinstance(current_input, list):
                                new_input, bytes_appended = append_text_to_latest_user_input_item(
                                    current_input, memory_context
                                )
                                if bytes_appended > 0:
                                    body["input"] = new_input
                                    log_memory_injection(
                                        request_id=request_id,
                                        session_id=None,
                                        decision="injected_live_zone_tail",
                                        bytes_injected=bytes_appended,
                                        query=user_query,
                                    )
                                else:
                                    log_memory_injection(
                                        request_id=request_id,
                                        session_id=None,
                                        decision="no_eligible_user_item",
                                        bytes_injected=0,
                                        query=user_query,
                                    )
                            else:
                                log_memory_injection(
                                    request_id=request_id,
                                    session_id=None,
                                    decision="no_input_field",
                                    bytes_injected=0,
                                    query=user_query,
                                )

                # Inject memory tools (Responses API format) — PR-A7 (P0-6).
                # Pre-convert the Chat-Completions schema to Responses API
                # format BEFORE handing to the sticky tracker so the
                # canonical bytes pinned in turn 1 already reflect the
                # exact bytes that will hit the wire.
                from cutctx.proxy.helpers import (
                    apply_session_sticky_memory_tools as _apply_sticky_mem_tools_resp,
                )

                memory_tool_defs_chat = (
                    self.memory_handler.compute_memory_tool_definitions("openai")
                    if self.memory_handler.config.inject_tools
                    else []
                )
                memory_tool_defs_responses: list[dict[str, Any]] = []
                for t in memory_tool_defs_chat:
                    if t.get("type") == "function" and "function" in t:
                        fn = t["function"]
                        memory_tool_defs_responses.append(
                            {
                                "type": "function",
                                "name": fn.get("name"),
                                "description": fn.get("description", ""),
                                "parameters": fn.get("parameters", {}),
                            }
                        )
                    else:
                        memory_tool_defs_responses.append(t)

                resp_tools = body.get("tools") or []
                resp_tools, mem_tools_injected = _apply_sticky_mem_tools_resp(
                    provider="openai",
                    session_id=_responses_session_id,
                    request_id=request_id,
                    existing_tools=resp_tools,
                    memory_tools_to_inject=memory_tool_defs_responses,
                    inject_this_turn=bool(self.memory_handler.config.inject_tools),
                )
                if mem_tools_injected:
                    body["tools"] = resp_tools
                    logger.info(f"[{request_id}] Memory: Injected memory tools (openai/responses)")
            except Exception as e:
                logger.warning(f"[{request_id}] Memory injection failed (responses): {e}")
        elif self.memory_handler and memory_user_id and _bypass:
            logger.info(
                "[%s] Responses memory passthrough reason=bypass_header",
                request_id,
            )

        # /v1/responses is OpenAI-specific (Codex) — always routes direct.
        # LiteLLM/AnyLLM backends use /v1/chat/completions or /v1/messages.
        if self.anthropic_backend is not None:
            logger.debug(
                f"[{request_id}] /v1/responses always routes to OpenAI direct "
                f"(backend '{self.anthropic_backend.name}' not used for Responses API)"
            )

        headers, is_chatgpt_auth = _resolve_codex_routing_headers(headers)

        # Route to correct endpoint based on auth mode.
        # ChatGPT session auth (codex login) uses chatgpt.com, not api.openai.com.
        if is_chatgpt_auth:
            url = "https://chatgpt.com/backend-api/codex/responses"
            stripped_fields = []
            if not is_remote_compaction:
                body, stripped_fields = _sanitize_chatgpt_subscription_responses_body(body)
            if stripped_fields:
                logger.info(
                    "[%s] /v1/responses stripped unsupported subscription fields: %s",
                    request_id,
                    ", ".join(stripped_fields),
                )
        else:
            url = build_copilot_upstream_url(self.OPENAI_API_URL, "/v1/responses")
            if codex_responses_lite:
                body, migrated_fields = _sanitize_codex_responses_lite_model(body)
                if migrated_fields:
                    logger.info(
                        "[%s] /v1/responses normalized Codex Responses Lite model: %s",
                        request_id,
                        ", ".join(migrated_fields),
                    )

        # The standalone Rust proxy has native /v1/responses item handling,
        # but the default CLI runtime is this Python proxy. Compress the
        # Python runtime path here by extracting mutable Responses text into
        # CompressionUnits and routing them through ContentRouter. Policy
        # gating already happened upstream (auth_mode classify,
        # CompressionPolicy resolve at request entry).
        if self.config.optimize and not (_bypass or is_remote_compaction):
            try:
                tool_scaffolding_tokens = estimate_tool_scaffolding_tokens(
                    body.get("tools"),
                    tokenizer,
                )
                tool_surface_result = slim_tool_surface(
                    body.get("tools"),
                    query=tool_surface_query,
                    tokenizer=tokenizer,
                    tool_choice=body.get("tool_choice"),
                    config=self.config,
                    messages=body.get("input"),
                )
                tool_surface_tokens_saved = tool_surface_result.tokens_saved
                if tool_surface_result.modified:
                    body["tools"] = tool_surface_result.tools
                    tokens_saved += tool_surface_tokens_saved
                    optimized_tokens = max(
                        0,
                        original_tokens - tokens_saved,
                    )
                    schema_savings_metadata = merge_savings_metadata(
                        schema_savings_metadata,
                        {"api_surface_slimming": {"tokens": tool_surface_result.tokens_saved}},
                    )
                    transforms_applied = [
                        "openai:responses:tool_surface_slimming",
                        *list(transforms_applied),
                    ]
                original_tools_payload = copy.deepcopy(body.get("tools"))
                (
                    body,
                    _modified,
                    _tokens_saved,
                    _transforms,
                    _reason,
                    _bytes_before,
                    _bytes_after,
                    _attempted_tokens,
                    _compression_timing,
                ) = await self._compress_openai_responses_payload_in_executor(
                    body,
                    model=model,
                    request_id=request_id,
                )
                if (
                    original_tools_payload
                    and "openai:responses:tool_schema_compaction" in _transforms
                ):
                    schema_savings_metadata = merge_savings_metadata(
                        schema_savings_metadata,
                        _tool_schema_savings_metadata(
                            tokenizer,
                            original_tools_payload,
                            body.get("tools"),
                        ),
                    )
                residual_ghost_tokens = max(
                    0,
                    tool_scaffolding_tokens
                    - tool_surface_tokens_saved
                    - max(0, int(_tokens_saved)),
                )
                if tool_scaffolding_tokens > 0:
                    schema_savings_metadata = merge_savings_metadata(
                        schema_savings_metadata,
                        {
                            "ghost_token_audit": {
                                "scaffolding_tokens": tool_scaffolding_tokens,
                                "ghost_tokens": residual_ghost_tokens,
                            }
                        },
                    )
                attempted_input_tokens = int(_attempted_tokens) + tool_surface_tokens_saved
                if _modified:
                    tokens_saved = int(_tokens_saved)
                    optimized_tokens = max(0, original_tokens - tokens_saved)
                    transforms_applied = [*_transforms, *list(transforms_applied)]
                    logger.info(
                        "[%s] /v1/responses compressed %d→%d bytes "
                        "(%d tokens saved, auth_mode=%s, transforms=%s)",
                        request_id,
                        _bytes_before,
                        _bytes_after,
                        tokens_saved,
                        auth_mode.value,
                        transforms_applied,
                    )
                else:
                    logger.info(
                        "[%s] /v1/responses compression passthrough "
                        "reason=%s bytes=%d auth_mode=%s model=%s",
                        request_id,
                        _reason or "no_compression",
                        _bytes_before,
                        auth_mode.value,
                        model or "unknown",
                    )
            except Exception as _e:
                _http_body_bytes = len(json.dumps(body).encode("utf-8", errors="replace"))
                logger.warning(
                    f"[{request_id}] /v1/responses compression failed "
                    f"(bytes={_http_body_bytes}): {type(_e).__name__}: {_e}"
                )
                # Fail-closed protection (default): refuse to forward
                # oversized requests after compression failure. Same
                # decision matrix and override env var as the WS path
                # (CUTCTX_WS_FAIL_OPEN_ON_COMPRESSION_FAILURE) — see
                # helpers.decide_compression_failure_action.
                from cutctx.proxy.helpers import (
                    decide_compression_failure_action,
                )

                _http_action = decide_compression_failure_action(
                    _e,
                    _http_body_bytes,
                    client=client,
                )
                # chatgpt.com has a strict body-size limit and returns HTTP 400
                # "Bad Request" when the payload is too large. The default
                # fail-open policy (refuse=False) for Codex clients would
                # forward the uncompressed body and trigger that 400.
                # Strategy: if routing to chatgpt.com and the body is oversized,
                # apply aggressive structural truncation so Codex can still
                # proceed rather than getting an opaque 400 or being blocked.
                _CHATGPT_MAX_BODY_BYTES = 900 * 1024  # 900 KB conservative limit
                if is_chatgpt_auth and _http_body_bytes > _CHATGPT_MAX_BODY_BYTES:
                    logger.warning(
                        "[%s] /v1/responses body too large for chatgpt.com "
                        "(%d bytes > %d limit) — applying emergency truncation",
                        request_id,
                        _http_body_bytes,
                        _CHATGPT_MAX_BODY_BYTES,
                    )
                    body = _truncate_body_for_chatgpt(body, _CHATGPT_MAX_BODY_BYTES, request_id)
                    _truncated_bytes = len(json.dumps(body).encode("utf-8", errors="replace"))
                    logger.info(
                        "[%s] /v1/responses emergency truncation: %d → %d bytes",
                        request_id,
                        _http_body_bytes,
                        _truncated_bytes,
                    )
                elif _http_action.refuse:
                    if (
                        not is_chatgpt_auth
                        and client == "codex"
                        and _http_action.reason == "timeout"
                    ):
                        logger.warning(
                            "[%s] /v1/responses compression timed out on a Codex "
                            "request (%d bytes); failing open to preserve the "
                            "standalone CLI UX.",
                            request_id,
                            _http_body_bytes,
                        )
                    else:
                        logger.error(
                            "[%s] /v1/responses REFUSING to forward request "
                            "after compression failure (reason=%s, bytes=%d); "
                            "returning HTTP 413 so the client can compact "
                            "context and retry. To restore legacy passthrough "
                            "behaviour set "
                            "CUTCTX_WS_FAIL_OPEN_ON_COMPRESSION_FAILURE=1.",
                            request_id,
                            _http_action.reason,
                            _http_body_bytes,
                        )
                        raise HTTPException(
                            status_code=413,
                            detail={
                                "error": {
                                    "type": "compression_refused",
                                    "message": (
                                        f"cutctx: compression "
                                        f"{_http_action.reason} on a "
                                        f"{_http_body_bytes}-byte request "
                                        "— please compact context and retry."
                                    ),
                                }
                            },
                        ) from _e

        # Request transforms can add API fields after the initial routing
        # sanitizer runs. Keep the ChatGPT subscription boundary strict so a
        # reconnect after a proxy restart cannot forward a stale streaming
        # field and receive an opaque upstream 400.
        if is_chatgpt_auth and not is_remote_compaction:
            body, final_stripped_fields = _sanitize_chatgpt_subscription_responses_body(body)
            if final_stripped_fields:
                logger.info(
                    "[%s] /v1/responses final subscription sanitization stripped: %s",
                    request_id,
                    ", ".join(final_stripped_fields),
                )
            stream = False
        elif codex_responses_lite:
            body, final_migrated_fields = _sanitize_codex_responses_lite_model(body)
            if final_migrated_fields:
                logger.info(
                    "[%s] /v1/responses final Codex Responses Lite model normalization: %s",
                    request_id,
                    ", ".join(final_migrated_fields),
                )

        # The HTTP Responses path can still reach the upstream with a payload
        # that is individually valid but too large for the model context
        # window. That shows up to callers as an opaque upstream 400 / "Bad
        # Request" after a proxy restart, because the session state the client
        # is trying to continue is now sitting inside the request body itself.
        #
        # Apply the same guard the WS path uses before we hand the body to the
        # backend. ChatGPT subscription traffic gets one last chance via the
        # structural truncator; all other transports fail with a clear 413 so
        # the client can compact context instead of starting a fresh thread.
        _guard_model = str(body.get("model") or model or "unknown")
        _guard_refuse = False
        _guard_estimated = _guard_threshold = _guard_limit = 0
        if not is_remote_compaction:
            (
                _guard_refuse,
                _guard_estimated,
                _guard_threshold,
                _guard_limit,
            ) = self._openai_responses_context_guard(body, model=_guard_model)
        _opaque_subscription_continuation = (
            is_chatgpt_auth and _contains_opaque_responses_continuation(body)
        )
        if _guard_refuse and _opaque_subscription_continuation:
            # Advisory only for the encrypted continuation state itself — a
            # reconstructed continuation can independently carry oversized
            # inline screenshots, which are safe to shrink (untouched by the
            # opaque-content check) and must still be capped before forwarding.
            body = _shrink_oversized_images(body)
            logger.warning(
                "[%s] /v1/responses treating approximate context guard as advisory "
                "for opaque ChatGPT subscription continuation "
                "(estimated_tokens=%d threshold=%d context_limit=%d model=%s)",
                request_id,
                _guard_estimated,
                _guard_threshold,
                _guard_limit,
                _guard_model,
            )
        elif _guard_refuse:
            _CHATGPT_MAX_BODY_BYTES = 900 * 1024  # conservative chatgpt.com ceiling
            if is_chatgpt_auth:
                def _chatgpt_context_over_budget(candidate: dict[str, Any]) -> bool:
                    candidate_model = str(candidate.get("model") or _guard_model)
                    candidate_refuse, _, _, _ = self._openai_responses_context_guard(
                        candidate,
                        model=candidate_model,
                    )
                    return candidate_refuse

                truncated_body = _truncate_body_for_chatgpt(
                    body,
                    _CHATGPT_MAX_BODY_BYTES,
                    request_id,
                    over_budget=_chatgpt_context_over_budget,
                )
                (
                    _retry_refuse,
                    _retry_estimated,
                    _retry_threshold,
                    _retry_limit,
                ) = self._openai_responses_context_guard(
                    truncated_body,
                    model=str(truncated_body.get("model") or _guard_model),
                )
                if not _retry_refuse:
                    logger.warning(
                        "[%s] /v1/responses context guard tripped on chatgpt.com "
                        "(estimated_tokens=%d threshold=%d context_limit=%d model=%s) "
                        "— applying emergency truncation to %d bytes and retrying",
                        request_id,
                        _guard_estimated,
                        _guard_threshold,
                        _guard_limit,
                        _guard_model,
                        _CHATGPT_MAX_BODY_BYTES,
                    )
                    body = truncated_body
                else:
                    logger.error(
                        "[%s] /v1/responses context guard still tripped after "
                        "chatgpt.com truncation (estimated_tokens=%d threshold=%d "
                        "context_limit=%d retry_estimated_tokens=%d retry_threshold=%d "
                        "retry_context_limit=%d model=%s)",
                        request_id,
                        _guard_estimated,
                        _guard_threshold,
                        _guard_limit,
                        _retry_estimated,
                        _retry_threshold,
                        _retry_limit,
                        _guard_model,
                    )
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "error": {
                                "type": "context_too_large",
                                "message": (
                                    "cutctx: context too large for chatgpt.com even after "
                                    "emergency truncation — compact context and retry."
                                ),
                            }
                        },
                    )
            else:
                logger.error(
                    "[%s] /v1/responses refusing oversized payload after "
                    "compression (estimated_tokens=%d threshold=%d context_limit=%d "
                    "model=%s); returning HTTP 413 so the client can compact context "
                    "and retry",
                    request_id,
                    _guard_estimated,
                    _guard_threshold,
                    _guard_limit,
                    _guard_model,
                )
                raise HTTPException(
                    status_code=413,
                    detail={
                        "error": {
                            "type": "context_too_large",
                            "message": ("cutctx: context too large — compact context and retry."),
                        }
                    },
                )

        capture_codex_wire_debug(
            "http_upstream_request",
            request_id=request_id,
            transport="http",
            direction="cutctx_to_upstream",
            method="POST",
            url=url,
            headers=headers,
            body=body,
            metadata={
                "path": request.url.path,
                "stream": stream,
                "auth_mode": auth_mode.value,
                "is_chatgpt_auth": is_chatgpt_auth,
                "tokens_saved": tokens_saved,
                "transforms_applied": transforms_applied,
            },
        )

        try:
            if stream:
                # Streaming for Responses API uses semantic events
                return await self._stream_response(
                    url,
                    headers,
                    body,
                    "openai",
                    model,
                    request_id,
                    original_tokens,
                    optimized_tokens,
                    tokens_saved,
                    transforms_applied,
                    tags,
                    optimization_latency,
                    memory_user_id=memory_user_id,
                    memory_request_ctx=memory_request_ctx,
                    savings_metadata=merge_savings_metadata(
                        request_savings_metadata,
                        schema_savings_metadata,
                    ),
                )
            else:
                headers = await apply_copilot_api_auth(headers, url=url)
                response = await self._retry_request("POST", url, headers, body)
                if response.status_code >= 400:
                    try:
                        _err_body = response.text[:2000]
                    except Exception:
                        _err_body = "<unreadable>"
                    logger.error(
                        "[%s] upstream %s returned HTTP %d — url=%s body_keys=%s body_sample=%s response_body=%s",
                        request_id,
                        url,
                        response.status_code,
                        url,
                        list(body.keys()),
                        json.dumps(
                            {
                                k: v
                                for k, v in body.items()
                                if k not in ("input", "instructions", "tools")
                            }
                        )[:300],
                        _err_body,
                    )
                _response_body_for_debug: Any = None
                _response_raw_for_debug: str | None = None
                try:
                    _response_body_for_debug = response.json()
                except Exception:
                    try:
                        _response_raw_for_debug = response.text[:200_000]
                    except Exception:
                        _response_raw_for_debug = None
                capture_codex_wire_debug(
                    "http_upstream_response",
                    request_id=request_id,
                    transport="http",
                    direction="upstream_to_cutctx",
                    method="POST",
                    url=url,
                    headers=dict(response.headers),
                    body=_response_body_for_debug,
                    raw_text=_response_raw_for_debug,
                    status_code=response.status_code,
                    metadata={"stream": stream, "auth_mode": auth_mode.value},
                )
                total_latency = (time.time() - start_time) * 1000

                total_input_tokens = original_tokens  # fallback
                output_tokens = 0
                cache_read_tokens = 0
                try:
                    resp_json = response.json()
                    usage = resp_json.get("usage", {})

                    def _usage_int(value: Any, default: int = 0) -> int:
                        try:
                            return max(int(value), 0)
                        except (TypeError, ValueError):
                            return default

                    total_input_tokens = _usage_int(
                        usage.get("input_tokens"),
                        original_tokens,
                    )
                    output_tokens = _usage_int(usage.get("output_tokens"))
                    details = usage.get("input_tokens_details")
                    if isinstance(details, dict):
                        cache_read_tokens = _usage_int(details.get("cached_tokens"))
                except (KeyError, TypeError, AttributeError) as e:
                    logger.debug(
                        f"[{request_id}] Failed to extract cached tokens from OpenAI passthrough response: {e}"
                    )

                # Memory: handle memory tool calls in Responses API response
                if (
                    self.memory_handler
                    and memory_user_id
                    and resp_json
                    and response.status_code == 200
                    and self.memory_handler.has_memory_tool_calls(resp_json, "openai")
                ):
                    try:
                        # Extract function_call items from output
                        from cutctx.proxy.memory_handler import MEMORY_TOOL_NAMES

                        output_items = resp_json.get("output", [])
                        memory_fc_items = [
                            item
                            for item in output_items
                            if isinstance(item, dict)
                            and item.get("type") == "function_call"
                            and item.get("name") in MEMORY_TOOL_NAMES
                        ]

                        # Execute memory tool calls
                        tool_outputs: list[dict[str, Any]] = []
                        for fc in memory_fc_items:
                            call_id = fc.get("call_id", fc.get("id", ""))
                            name = fc.get("name", "")
                            args_str = fc.get("arguments", "{}")
                            try:
                                args = json.loads(args_str)
                            except json.JSONDecodeError:
                                args = {}

                            await self.memory_handler._ensure_initialized()
                            if self.memory_handler._backend:
                                result = await self.memory_handler._execute_memory_tool(
                                    name, args, memory_user_id, "openai"
                                )
                            else:
                                result = json.dumps({"error": "Memory backend not initialized"})

                            tool_outputs.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": call_id,
                                    "output": result,
                                }
                            )

                        if tool_outputs:
                            # Make continuation request with tool results
                            response_id = resp_json.get("id")
                            continuation_body = {
                                "model": model,
                                "input": tool_outputs,
                            }
                            if response_id:
                                continuation_body["previous_response_id"] = response_id
                            existing_tools = body.get("tools")
                            if existing_tools:
                                continuation_body["tools"] = existing_tools

                            cont_response = await self._retry_request(
                                "POST", url, headers, continuation_body
                            )
                            resp_json = cont_response.json()
                            response = cont_response
                            logger.info(
                                f"[{request_id}] Memory: Handled {len(tool_outputs)} "
                                f"tool call(s) with continuation for user {memory_user_id} (responses)"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[{request_id}] Memory tool handling failed (responses): {e}"
                        )

                routing_metadata = (
                    request_savings_metadata.get("model_routing")
                    if isinstance(request_savings_metadata, dict)
                    else None
                )
                from cutctx.proxy.model_routing_evals import schedule_model_routing_shadow

                schedule_model_routing_shadow(
                    self._maybe_model_routing_responses_shadow(
                        request_id=request_id,
                        source_model=requested_model,
                        candidate_model=model,
                        url=url,
                        headers=headers,
                        candidate_body=body,
                        routing_metadata=routing_metadata,
                        messages=routing_messages,
                        candidate_json=resp_json,
                        original_reasoning=original_reasoning,
                        client=client,
                    )
                )

                if self.cost_tracker:
                    cache_write_tokens = _infer_openai_cache_write_tokens(
                        total_input_tokens,
                        cache_read_tokens,
                    )
                    uncached_input_tokens = max(0, total_input_tokens - cache_read_tokens)
                    self.cost_tracker.record_tokens(
                        model,
                        tokens_saved,
                        total_input_tokens,
                        cache_read_tokens=cache_read_tokens,
                        cache_write_tokens=cache_write_tokens,
                        uncached_tokens=uncached_input_tokens,
                    )
                else:
                    cache_write_tokens = _infer_openai_cache_write_tokens(
                        total_input_tokens,
                        cache_read_tokens,
                    )
                    uncached_input_tokens = max(0, total_input_tokens - cache_read_tokens)

                effective_optimized_tokens = (
                    total_input_tokens if total_input_tokens > 0 else optimized_tokens
                )
                effective_original_tokens = max(
                    original_tokens,
                    effective_optimized_tokens + tokens_saved,
                )

                _resp_log_tags = {
                    **(tags or {}),
                    "auth_mode": auth_mode.value if auth_mode else "payg",
                    "endpoint": "responses_http",
                }

                # OpenAI Responses HTTP (non-WS, non-streaming). Codex
                # uses this path when configured for HTTP transport.
                # Pre-refactor `cache_hit` was hardcoded False on
                # RequestLog even when cache_read>0 — funnel derives
                # it correctly.
                from cutctx.proxy.helpers import compute_turn_id

                await self._record_request_outcome(
                    RequestOutcome(
                        request_id=request_id,
                        provider=_provider_for_client(client),
                        model=model,
                        original_tokens=effective_original_tokens,
                        optimized_tokens=effective_optimized_tokens,
                        output_tokens=output_tokens,
                        tokens_saved=tokens_saved,
                        attempted_input_tokens=attempted_input_tokens,
                        cache_read_tokens=cache_read_tokens,
                        cache_write_tokens=cache_write_tokens,
                        uncached_input_tokens=uncached_input_tokens,
                        total_latency_ms=total_latency,
                        overhead_ms=optimization_latency,
                        transforms_applied=tuple(transforms_applied),
                        num_messages=len(messages) if isinstance(messages, list) else 0,
                        tags=_resp_log_tags,
                        turn_id=compute_turn_id(model, body.get("instructions"), messages),
                        request_messages=messages
                        if getattr(self.config, "log_full_messages", False)
                        else None,
                        client=client,
                        savings_metadata=merge_savings_metadata(
                            request_savings_metadata,
                            extract_savings_metadata(
                                request_headers=request.headers,
                                response_headers=response.headers,
                                body=body,
                            ),
                            schema_savings_metadata,
                        ),
                    )
                )

                logger.info(f"[{request_id}] /v1/responses {model}: {total_input_tokens:,} tokens")

                # Capture Codex rate-limit window data from response headers
                from cutctx.subscription.codex_rate_limits import (
                    get_codex_rate_limit_state,
                )

                get_codex_rate_limit_state().update_from_headers(dict(response.headers))

                # Remove compression headers
                response_headers = dict(response.headers)
                response_headers.pop("content-encoding", None)
                response_headers.pop("content-length", None)

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response_headers,
                )
        except Exception as e:
            fallback_provider = getattr(self.config, "fallback_provider", None)
            fallback_backend = getattr(self, "fallback_backend", None) or getattr(
                self, "openai_fallback_backend", None
            )
            if (
                not stream
                and getattr(self.config, "fallback_enabled", False)
                and fallback_provider
                and fallback_backend is not None
            ):
                logger.info(
                    "[%s] Attempting OpenAI responses fallback to %s",
                    request_id,
                    fallback_provider,
                )

                def _fallback_reason(exc: Exception) -> str:
                    if isinstance(exc, httpx.ConnectError):
                        return "connect_error"
                    if isinstance(exc, httpx.TimeoutException):
                        return "timeout"
                    if isinstance(exc, httpx.HTTPStatusError):
                        return "upstream_5xx"
                    return type(exc).__name__.lower()

                tags["fallback_provider"] = fallback_provider
                tags["fallback_attempted"] = "true"
                tags["fallback_reason"] = _fallback_reason(e)
                tags["fallback_source_provider"] = "openai"
                tags["upstream_provider"] = fallback_provider
                for key in (
                    "failover_active_provider",
                    "failover_active_base_url",
                    "failover_active_healthy",
                    "circuit_breaker_state",
                    "circuit_breaker_retry_after_s",
                    "circuit_breaker_consecutive_failures",
                    "circuit_breaker_failure_threshold",
                ):
                    tags.pop(key, None)

                try:
                    fallback_request_body = _responses_payload_to_chat_completions_body(body)
                    backend_response = await fallback_backend.send_openai_message(
                        fallback_request_body,
                        dict(headers),
                    )
                except Exception as fallback_exc:
                    logger.error(
                        "[%s] OpenAI responses fallback to %s failed: %s: %s",
                        request_id,
                        fallback_provider,
                        type(fallback_exc).__name__,
                        fallback_exc,
                    )
                else:
                    if not backend_response.error and backend_response.status_code < 500:
                        response_payload = _chat_completions_response_to_responses_payload(
                            backend_response.body,
                            model=model,
                        )
                        total_latency = (time.time() - start_time) * 1000
                        usage = response_payload.get("usage", {})

                        def _fallback_usage_int(value: Any, default: int = 0) -> int:
                            try:
                                return max(int(value), 0)
                            except (TypeError, ValueError):
                                return default

                        total_input_tokens = _fallback_usage_int(
                            usage.get("input_tokens") or optimized_tokens
                        )
                        output_tokens = _fallback_usage_int(usage.get("output_tokens"))
                        details = usage.get("input_tokens_details")
                        cache_read_tokens = 0
                        if isinstance(details, dict):
                            cache_read_tokens = _fallback_usage_int(details.get("cached_tokens"))
                        cache_write_tokens = _infer_openai_cache_write_tokens(
                            total_input_tokens,
                            cache_read_tokens,
                        )
                        uncached_input_tokens = max(0, total_input_tokens - cache_read_tokens)
                        effective_optimized_tokens = (
                            total_input_tokens if total_input_tokens > 0 else optimized_tokens
                        )
                        effective_original_tokens = max(
                            original_tokens,
                            effective_optimized_tokens + tokens_saved,
                        )

                        _resp_log_tags = {
                            **(tags or {}),
                            "auth_mode": auth_mode.value if auth_mode else "payg",
                            "endpoint": "responses_http",
                        }

                        from cutctx.proxy.helpers import compute_turn_id

                        await self._record_request_outcome(
                            RequestOutcome(
                                request_id=request_id,
                                provider=fallback_provider,
                                model=model,
                                original_tokens=effective_original_tokens,
                                optimized_tokens=effective_optimized_tokens,
                                output_tokens=output_tokens,
                                tokens_saved=tokens_saved,
                                attempted_input_tokens=attempted_input_tokens,
                                cache_read_tokens=cache_read_tokens,
                                cache_write_tokens=cache_write_tokens,
                                uncached_input_tokens=uncached_input_tokens,
                                total_latency_ms=total_latency,
                                overhead_ms=optimization_latency,
                                transforms_applied=tuple(transforms_applied),
                                num_messages=len(messages) if isinstance(messages, list) else 0,
                                tags=_resp_log_tags,
                                turn_id=compute_turn_id(model, body.get("instructions"), messages),
                                request_messages=messages
                                if getattr(self.config, "log_full_messages", False)
                                else None,
                                client=client,
                                savings_metadata=merge_savings_metadata(
                                    request_savings_metadata,
                                    extract_savings_metadata(
                                        request_headers=request.headers,
                                        response_headers=backend_response.headers,
                                        body=body,
                                    ),
                                    schema_savings_metadata,
                                ),
                            )
                        )

                        response_headers = dict(backend_response.headers)
                        response_headers.pop("content-encoding", None)
                        response_headers.pop("content-length", None)
                        return Response(
                            content=json.dumps(response_payload).encode("utf-8"),
                            status_code=backend_response.status_code,
                            headers=response_headers,
                            media_type="application/json",
                        )

            await self.metrics.record_failed(provider="openai")
            logger.error(f"[{request_id}] OpenAI responses request failed: {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "message": "An error occurred while processing your request. Please try again.",
                        "type": "server_error",
                        "code": "proxy_error",
                    }
                },
            )

    async def handle_openai_responses_ws(self, websocket: WebSocket) -> None:
        """WebSocket proxy for /v1/responses (Codex gpt-5.4+).

        Newer Codex versions use WebSocket instead of HTTP POST for the
        Responses API.  This handler:
        1. Accepts the client WebSocket
        2. Receives the first message (``response.create`` request)
        3. Opens an upstream WebSocket to OpenAI
        4. Compresses eligible `response.create` text through the Python
           ContentRouter path, then sends the request upstream
        5. Relays all subsequent messages bidirectionally
        """
        try:
            import websockets
        except ImportError:
            await websocket.accept()
            await websocket.close(
                code=1011,
                reason="websockets package not installed. pip install websockets",
            )
            return

        request_id = await self._next_request_id()
        session_id = uuid.uuid4().hex

        # Stage-timer — captures per-stage durations for the structured
        # log emitted on session close. Unit 2 instrumentation.
        stage_timer = StageTimer()
        session_started_at = time.perf_counter()

        # Unit 3: initialize registry variables *before* accept so the
        # outermost ``finally`` can rely on them existing even if
        # registration itself fails for some reason.
        ws_sessions: WebSocketSessionRegistry | None = getattr(self, "ws_sessions", None)
        session_handle: WSSessionHandle | None = None
        termination_cause: TerminationCause = "unknown"

        # Forward client headers to upstream, adding required OpenAI-Beta header
        ws_headers = dict(websocket.headers)
        conversation_session_id = _compute_responses_ws_conversation_session_id(
            self.session_tracker_store,
            ws_headers,
            None,
            fallback_session_id=session_id,
        )
        # Identify the WS harness before downstream auth/header rewrites.
        # Captured in closure so per-turn RequestOutcome can stamp it.
        client = classify_client(ws_headers)
        # WS sessions bypass the HTTP middleware, so bind the project here;
        # per-turn outcome emission inside this task inherits the context.
        set_current_project(classify_project(ws_headers))
        _ws_url_obj = getattr(websocket, "url", None)
        _ws_url = str(_ws_url_obj) if _ws_url_obj is not None else ""
        _ws_path = getattr(_ws_url_obj, "path", "") if _ws_url_obj is not None else ""
        if not _ws_path:
            _ws_path = "/v1/responses"
        metrics_for_inbound_ws = getattr(self, "metrics", None)
        if metrics_for_inbound_ws is not None and hasattr(
            metrics_for_inbound_ws, "record_inbound_request"
        ):
            with contextlib.suppress(Exception):
                metrics_for_inbound_ws.record_inbound_request(method="WS", path=_ws_path)
        logger.info(
            "event=proxy_inbound_websocket request_id=%s session_id=%s path=%s "
            "client=%s header_count=%d",
            request_id,
            session_id,
            _ws_path,
            getattr(websocket, "client", ""),
            len(ws_headers),
        )
        from cutctx.proxy.helpers import capture_codex_wire_debug

        capture_codex_wire_debug(
            "ws_inbound_handshake",
            request_id=request_id,
            session_id=session_id,
            transport="websocket",
            direction="client_to_cutctx",
            url=_ws_url,
            headers=ws_headers,
            metadata={"path": _ws_path},
        )
        # Extract per-request tags from headers up front so the
        # session-end RequestLog can attach them. `_extract_tags` is
        # the same helper the HTTP handlers use; on a WebSocket the
        # tags come from `x-cutctx-tag-*` headers in the upgrade
        # handshake. Returns `{}` when no tags are present.
        _extract_ws_tags = getattr(self, "_extract_tags", None)
        ws_tags = _extract_ws_tags(ws_headers) if callable(_extract_ws_tags) else {}

        # Extract subprotocol from client — this is an application-level negotiation
        # that MUST be forwarded end-to-end (unlike sec-websocket-key which is per-connection).
        # Codex and OpenAI negotiate a subprotocol; stripping it causes OpenAI to return 500.
        client_subprotocols: list[str] = []
        raw_protocol = ws_headers.get("sec-websocket-protocol", "")
        if raw_protocol:
            client_subprotocols = [p.strip() for p in raw_protocol.split(",") if p.strip()]

        # Forward all client headers except hop-by-hop / per-connection headers.
        # These are WebSocket handshake mechanics that the `websockets` library
        # generates fresh for the upstream connection — forwarding them would conflict.
        # Everything else (auth, org, beta, user-agent, custom headers) is forwarded as-is.
        _skip_headers = frozenset(
            {
                "host",  # must match upstream, not local proxy
                "connection",  # hop-by-hop
                "upgrade",  # hop-by-hop
                "sec-websocket-key",  # per-connection cryptographic nonce
                "sec-websocket-version",  # protocol version (websockets lib sets this)
                "sec-websocket-extensions",  # per-connection negotiation
                "sec-websocket-accept",  # server-side only
                "sec-websocket-protocol",  # handled via subprotocols param below
                "content-length",  # hop-by-hop
                "transfer-encoding",  # hop-by-hop
            }
        )
        # PR-A5 (P5-49): also drop internal x-cutctx-* from the upstream
        # WebSocket handshake. Inbound reads on `ws_headers` (memory user-id
        # below) keep working because we filter only when building
        # `upstream_headers`, not when reading from `ws_headers`.
        from cutctx.proxy.handlers.openai.utils import (
            _strip_openai_internal_headers as _strip_openai_internal,
        )
        from cutctx.proxy.helpers import (
            _strip_internal_headers as _strip_internal,
        )
        from cutctx.proxy.helpers import (
            log_outbound_headers as _log_outbound_headers,
        )

        _ws_pre_strip_filtered: dict[str, str] = {}
        for k, v in ws_headers.items():
            if k.lower() not in _skip_headers:
                _ws_pre_strip_filtered[k] = v
        _ws_pre_strip_count = sum(
            1 for k in _ws_pre_strip_filtered if k.lower().startswith("x-cutctx-")
        )
        upstream_headers = _strip_internal(_ws_pre_strip_filtered)
        upstream_headers = _strip_openai_internal(upstream_headers)
        _log_outbound_headers(
            forwarder="openai_responses_ws",
            stripped_count=_ws_pre_strip_count,
            request_id=request_id,
        )

        upstream_headers, is_chatgpt_auth = _resolve_codex_routing_headers(upstream_headers)
        # Build upstream WebSocket URL based on auth mode
        if is_chatgpt_auth:
            # ChatGPT session auth → route to chatgpt.com backend
            upstream_url = "wss://chatgpt.com/backend-api/codex/responses"
            logger.debug(
                f"[{request_id}] WS: ChatGPT session auth detected, routing to chatgpt.com"
            )
        else:
            # API key auth → route to configured OpenAI API URL
            base = self.OPENAI_API_URL
            ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
            upstream_url = build_copilot_upstream_url(ws_base, "/v1/responses")

        capture_codex_wire_debug(
            "ws_upstream_handshake",
            request_id=request_id,
            session_id=session_id,
            transport="websocket",
            direction="cutctx_to_upstream",
            url=upstream_url,
            headers=upstream_headers,
            metadata={
                "is_chatgpt_auth": is_chatgpt_auth,
                "subprotocols": client_subprotocols,
            },
        )

        logger.info(
            "[%s] WS /v1/responses accepted (route=%s, auth_mode=%s, subprotocols=%s)",
            request_id,
            "chatgpt_subscription" if is_chatgpt_auth else "openai_api",
            classify_auth_mode(ws_headers).value,
            client_subprotocols,
        )

        # Safety net for clients that don't forward auth headers via the
        # WebSocket upgrade. The helper never overwrites client credentials.
        from cutctx.proxy.auth_keyring import inject_provider_authorization

        if inject_provider_authorization(upstream_headers, "openai"):
            logger.debug(
                "[%s] WS injected OpenAI Authorization from configured credentials", request_id
            )

        upstream_headers = await apply_copilot_api_auth(upstream_headers, url=upstream_url)

        # Ensure the required beta header is present — OpenAI returns 500 without it.
        # PR-A6 (P5-50): use the deterministic `merge_openai_beta` helper
        # so the auto-injected `responses_websockets=2026-02-06` is
        # appended to the client's value (preserving order, deduping
        # case-insensitively) rather than overwriting it. The
        # SessionBetaTracker also records the merge so a future cross-
        # connection sticky model can replay tokens by session_id.
        from cutctx.proxy.helpers import (
            get_session_beta_tracker as _get_session_beta_tracker_ws,
        )
        from cutctx.proxy.helpers import (
            log_beta_header_merge as _log_beta_header_merge_ws,
        )
        from cutctx.proxy.helpers import merge_openai_beta as _merge_openai_beta_ws

        _ws_required_tokens = ["responses_websockets=2026-02-06"]
        # Read the original (pre-merge) client value from the WS headers
        # to preserve casing and ordering.
        _ws_client_beta_value: str | None = None
        for _k, _v in upstream_headers.items():
            if _k.lower() == "openai-beta":
                _ws_client_beta_value = _v
                break
        # Record session-stickiness BEFORE adding required tokens so the
        # tracker stores the canonical client baseline.
        _ws_sticky_beta = _get_session_beta_tracker_ws().record_and_get_sticky_betas(
            provider="openai",
            session_id=conversation_session_id,
            client_value=_ws_client_beta_value,
        )
        _ws_merged_beta = _merge_openai_beta_ws(_ws_sticky_beta, _ws_required_tokens)
        # Replace any existing case-variants of openai-beta with the
        # canonical "OpenAI-Beta" key carrying the merged value.
        _ws_existing_keys = [_k for _k in upstream_headers if _k.lower() == "openai-beta"]
        for _k in _ws_existing_keys:
            del upstream_headers[_k]
        if _ws_merged_beta:
            upstream_headers["OpenAI-Beta"] = _ws_merged_beta
        _ws_client_beta_count = (
            len([t for t in (_ws_client_beta_value or "").split(",") if t.strip()])
            if _ws_client_beta_value
            else 0
        )
        _ws_merged_beta_count = (
            len([t for t in _ws_merged_beta.split(",") if t.strip()]) if _ws_merged_beta else 0
        )
        _log_beta_header_merge_ws(
            provider="openai",
            session_id=conversation_session_id,
            client_betas_count=_ws_client_beta_count,
            sticky_betas_count=_ws_merged_beta_count,
            cutctx_added=_ws_required_tokens,
            request_id=request_id,
        )

        capture_codex_wire_debug(
            "ws_upstream_handshake_final",
            request_id=request_id,
            session_id=session_id,
            transport="websocket",
            direction="cutctx_to_upstream",
            url=upstream_url,
            headers=upstream_headers,
            metadata={
                "is_chatgpt_auth": is_chatgpt_auth,
                "subprotocols": client_subprotocols,
            },
        )

        logger.debug(
            f"[{request_id}] WS upstream headers: "
            f"{[k for k in upstream_headers if k.lower() != 'authorization']}, "
            f"subprotocols={client_subprotocols}"
        )

        try:
            # --- Accept the client WebSocket FIRST ---
            # Previously we connected to upstream before accepting the client so
            # we could forward x-codex-* rate-limit headers from chatgpt.com's
            # 101 response.  However chatgpt.com's WebSocket handshake can take
            # 20+ seconds, which causes Codex to time out waiting for our 101
            # ("WebSocket protocol error: Handshake not finished").
            #
            # Fix: accept the client immediately, then connect upstream.
            # The x-codex-* headers are updated into /stats state after the
            # upstream handshake completes; they are no longer forwarded in the
            # client-facing 101 but that is a cosmetic loss — the session works.
            async with stage_timer.measure("accept"):
                await websocket.accept(
                    subprotocol=client_subprotocols[0] if client_subprotocols else None,
                )

            # --- Connect to upstream OpenAI WebSocket ---
            logger.info(f"[{request_id}] WS /v1/responses connecting to {upstream_url}")

            # Use ssl=True to let the websockets library handle SSL natively.
            # Manual ssl.create_default_context() + certifi doesn't load the
            # Windows system cert store, causing HTTP 500 on wss:// connections.
            use_ssl: bool | None = True if upstream_url.startswith("wss://") else None

            ws_connected = False
            ws_connect_attempts = max(1, getattr(self.config, "retry_max_attempts", 3))
            ws_last_err: Exception | None = None
            _upstream_connect_started = time.perf_counter()
            _upstream_connect_recorded = False
            _upstream_first_event_started: float | None = None
            upstream: Any = None

            for ws_attempt in range(ws_connect_attempts):
                try:
                    connect_header_kwargs = _ws_connect_header_kwargs(websockets, upstream_headers)
                    upstream = await websockets.connect(
                        upstream_url,
                        **connect_header_kwargs,
                        subprotocols=(
                            [websockets.Subprotocol(p) for p in client_subprotocols]
                            if client_subprotocols and hasattr(websockets, "Subprotocol")
                            else client_subprotocols or None
                        ),
                        ssl=use_ssl,
                        open_timeout=max(30, self.config.connect_timeout_seconds * 3),
                        close_timeout=10,
                        # Matches the client-facing uvicorn ws_ping_interval/timeout
                        # (see cutctx/proxy/server.py, run_proxy_server): a Codex turn
                        # can go quiet on the socket for minutes during a long local
                        # tool call (shell command, test suite) while this upstream
                        # connection sits idle. The previous 20s ping timeout closed
                        # this leg mid-turn from our side, and a fresh WS can't resume
                        # the prior turn's pending tool-call state — surfacing to the
                        # user as "stream disconnected before completion" followed by
                        # a reconnect that fails with "Bad Request".
                        ping_interval=600,
                        ping_timeout=600,
                    )
                    ws_connected = True
                    if not _upstream_connect_recorded:
                        stage_timer.record(
                            "upstream_connect",
                            (time.perf_counter() - _upstream_connect_started) * 1000.0,
                        )
                        _upstream_connect_recorded = True
                        _upstream_first_event_started = time.perf_counter()
                    break
                except Exception as ws_err:
                    ws_last_err = ws_err
                    if ws_attempt >= ws_connect_attempts - 1:
                        break
                    delay_with_jitter = jitter_delay_ms(
                        self.config.retry_base_delay_ms,
                        self.config.retry_max_delay_ms,
                        ws_attempt,
                    )
                    logger.warning(
                        f"[{request_id}] WS upstream connect failed "
                        f"(attempt {ws_attempt + 1}/{ws_connect_attempts}): {ws_err}; "
                        f"retrying in {delay_with_jitter:.0f}ms"
                    )
                    await asyncio.sleep(delay_with_jitter / 1000)

            # Update /stats rate-limit state from chatgpt.com handshake headers
            # (no longer forwarded in the client 101, but still tracked internally).
            if ws_connected:
                _codex_handshake = _extract_codex_handshake_headers(upstream)
                if _codex_handshake:
                    from cutctx.subscription.codex_rate_limits import (
                        get_codex_rate_limit_state,
                    )

                    with contextlib.suppress(Exception):
                        get_codex_rate_limit_state().update_from_headers(dict(_codex_handshake))
            else:
                err_msg = str(ws_last_err) if ws_last_err else "upstream connect failed"
                fallback_provider = getattr(self.config, "fallback_provider", None)
                fallback_enabled = bool(getattr(self.config, "fallback_enabled", False))
                fallback_backend = getattr(self, "fallback_backend", None) or getattr(
                    self, "openai_fallback_backend", None
                )
                if fallback_enabled and (
                    fallback_provider == "openai" or fallback_backend is not None
                ):
                    logger.warning(
                        "[%s] WS upstream connect failed after all retries: %s; "
                        "reading first frame and falling back",
                        request_id,
                        err_msg,
                    )
                    try:
                        async with stage_timer.measure("first_client_frame"):
                            first_msg_raw = await asyncio.wait_for(
                                websocket.receive_text(),
                                timeout=WS_FIRST_FRAME_TIMEOUT_SECONDS,
                            )
                    except asyncio.TimeoutError:
                        termination_cause = "client_timeout"
                        with contextlib.suppress(Exception):
                            await websocket.close(code=1001, reason="first-frame timeout")
                        return

                    try:
                        body = json.loads(first_msg_raw)
                    except (json.JSONDecodeError, TypeError):
                        body = {}
                    if not isinstance(body, dict):
                        body = {}

                    fallback_summary = await self._ws_http_fallback(
                        websocket,
                        body,
                        first_msg_raw,
                        upstream_headers,
                        request_id,
                        ws_tags=ws_tags,
                    )
                    response_completed_seen = bool(fallback_summary.get("response_completed"))
                    termination_cause = (
                        "response_completed" if response_completed_seen else "upstream_disconnect"
                    )
                    ws_inner_for_telemetry = body.get("response", body)
                    if not isinstance(ws_inner_for_telemetry, dict):
                        ws_inner_for_telemetry = {}
                    model_name = str(ws_inner_for_telemetry.get("model") or "unknown")
                    outcome_provider = str(
                        ws_tags.get("fallback_provider") or _provider_for_client(client)
                    )
                    ws_session_tags = {
                        **(ws_tags or {}),
                        "auth_mode": classify_auth_mode(ws_headers).value,
                        "endpoint": "responses_ws",
                        "compression_scope": "live_zone",
                        "cache_policy": "prefix_safe",
                        "transport": "websocket",
                        "route": "chatgpt_subscription" if is_chatgpt_auth else "openai_api",
                        "ws_response_create_frames": "1",
                        "ws_frames_compressed": "0",
                        "ws_client_frames_total": "1",
                        "ws_upstream_frames_total": "1",
                        "ws_cancel_frames": "0",
                        "ws_last_client_frame_type": str(body.get("type") or "unknown"),
                        "ws_last_upstream_frame_type": str(
                            fallback_summary.get("last_event_type") or "unknown"
                        ),
                        "ws_client_disconnect_seen": "False",
                        "ws_termination_cause": termination_cause,
                        "cache_read_tokens": str(
                            int(fallback_summary.get("cache_read_tokens", 0) or 0)
                        ),
                        "cache_write_tokens": str(
                            int(fallback_summary.get("cache_write_tokens", 0) or 0)
                        ),
                        "uncached_input_tokens": str(
                            int(fallback_summary.get("uncached_input_tokens", 0) or 0)
                        ),
                    }
                    await self._record_request_outcome(
                        RequestOutcome(
                            request_id=request_id,
                            provider=outcome_provider,
                            model=model_name,
                            original_tokens=int(fallback_summary.get("input_tokens", 0) or 0),
                            optimized_tokens=int(fallback_summary.get("input_tokens", 0) or 0),
                            output_tokens=int(fallback_summary.get("output_tokens", 0) or 0),
                            tokens_saved=0,
                            attempted_input_tokens=0,
                            cache_read_tokens=int(
                                fallback_summary.get("cache_read_tokens", 0) or 0
                            ),
                            cache_write_tokens=int(
                                fallback_summary.get("cache_write_tokens", 0) or 0
                            ),
                            uncached_input_tokens=int(
                                fallback_summary.get("uncached_input_tokens", 0) or 0
                            ),
                            total_latency_ms=(time.perf_counter() - session_started_at) * 1000.0,
                            overhead_ms=0.0,
                            transforms_applied=(),
                            tags=ws_session_tags,
                            client=client,
                            savings_metadata=extract_savings_metadata(
                                request_headers=ws_headers,
                                response_headers={},
                                body=ws_inner_for_telemetry,
                            ),
                        )
                    )
                    return

                # Upstream connect failed after all retries — close client cleanly.
                logger.error(
                    f"[{request_id}] WS upstream connect failed after all retries: {err_msg}"
                )
                with contextlib.suppress(Exception):
                    await websocket.close(code=1014, reason="upstream connect failed")
                return

            # --- Unit 3: register the session as soon as accept succeeds ---
            client_addr: str | None = None
            client_info = getattr(websocket, "client", None)
            if client_info is not None:
                host = getattr(client_info, "host", None)
                port = getattr(client_info, "port", None)
                if host is not None and port is not None:
                    client_addr = f"{host}:{port}"
                elif host is not None:
                    client_addr = str(host)
            if ws_sessions is not None:
                session_handle = WSSessionHandle(
                    session_id=session_id,
                    request_id=request_id,
                    client_addr=client_addr,
                    upstream_url=upstream_url,
                )
                ws_sessions.register(session_handle)
                metrics = getattr(self, "metrics", None)
                if metrics is not None and hasattr(metrics, "inc_active_ws_sessions"):
                    try:
                        metrics.inc_active_ws_sessions()
                    except Exception:  # pragma: no cover - defensive
                        pass
            # Receive the first message from client (the response.create request).
            # Bound the wait with WS_FIRST_FRAME_TIMEOUT_SECONDS so a zombie
            # client that opens the WS but never sends a frame cannot hold a
            # session slot indefinitely. The StageTimer measurement still
            # captures the elapsed time up to the timeout so operators can
            # see the slow-client pattern in the stage-timings log.
            try:
                async with stage_timer.measure("first_client_frame"):
                    first_msg_raw = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=WS_FIRST_FRAME_TIMEOUT_SECONDS,
                    )
            except asyncio.TimeoutError:
                logger.info(
                    f"[{request_id}] WS first-frame timeout after "
                    f"{WS_FIRST_FRAME_TIMEOUT_SECONDS:.0f}s; closing session "
                    f"{session_id} (no client data)"
                )
                termination_cause = "client_timeout"
                with contextlib.suppress(Exception):
                    # 1001 (going away): server is cleanly terminating a slow
                    # client, not an internal error.
                    await websocket.close(code=1001, reason="first-frame timeout")
                # Exit the outer try so the session-lifecycle ``finally`` runs
                # deregister / metrics / stage-timings emission as usual.
                return

            # The standalone Rust proxy has a native Responses path, but the
            # CLI runtime runs this Python proxy. Compress eligible
            # `response.create` frames through the shared Python
            # CompressionUnit + ContentRouter path before upstream send.
            # Subsequent client→upstream frames are now ALSO compressed
            # via `_maybe_compress_response_create_frame` in
            # `_client_to_upstream` so long-lived subscription Codex
            # sessions get savings on every turn, not just the first.

            def _log_ws_passthrough(
                reason: str,
                *,
                frame_index: int,
                raw_bytes: int,
                frame_type: str = "",
                model: str = "",
            ) -> None:
                logger.info(
                    "[%s] WS /v1/responses frame passthrough "
                    "reason=%s frame=%d bytes=%d type=%s auth_mode=%s model=%s",
                    request_id,
                    reason,
                    frame_index,
                    raw_bytes,
                    frame_type or "unknown",
                    classify_auth_mode(ws_headers).value,
                    model or "unknown",
                )

            body: dict[str, Any] = {}
            tokens_saved = 0
            # Session-scoped accumulator for tokens we *attempted* to
            # compress (extracted units + schema). Drives the active-
            # compression ratio surfaced to the dashboard.
            attempted_input_tokens_total = 0
            transforms_applied: list[str] = []
            ws_frames_compressed = 0
            try:
                body = json.loads(first_msg_raw)
            except json.JSONDecodeError:
                # Not JSON — pass through as-is
                pass
            conversation_session_id = _compute_responses_ws_conversation_session_id(
                self.session_tracker_store,
                ws_headers,
                body,
                fallback_session_id=conversation_session_id,
            )
            ws_savings_metadata = extract_savings_metadata(
                request_headers=ws_headers,
                body=body,
            )
            from cutctx.proxy.canary_identity import resolve_canary_identity
            from cutctx.proxy.model_router import prepare_model_routing
            from cutctx.proxy.savings_canary import get_savings_canary_coordinator

            ws_routing_body = body.get("response", body) if isinstance(body, dict) else {}
            if not isinstance(ws_routing_body, dict):
                ws_routing_body = {}
            ws_model = str(
                ws_routing_body.get("model")
                or (body.get("model") if isinstance(body, dict) else None)
                or "unknown"
            )
            ws_messages = _responses_payload_to_routing_messages(ws_routing_body)
            _ws_canary_coordinator = get_savings_canary_coordinator()
            _ws_canary_identity = resolve_canary_identity(
                headers=ws_headers,
                body=body,
                request_id=session_id,
                salt=_ws_canary_coordinator.salt,
                existing_session_id=conversation_session_id,
            )
            ws_num_messages = len(ws_messages)
            if isinstance(ws_routing_body, dict):
                if isinstance(ws_routing_body.get("messages"), list):
                    ws_messages = ws_routing_body.get("messages")
                    ws_num_messages = len(ws_messages or [])
            from cutctx.proxy.handlers.openai.utils import _has_codex_responses_lite_hint

            ws_model, ws_savings_metadata = prepare_model_routing(
                self,
                ws_model,
                request_savings_metadata=ws_savings_metadata,
                num_messages=ws_num_messages,
                messages=ws_messages,
                request_id=_ws_canary_identity.value,
                client=classify_client(ws_headers),
                assignment_identity_source=_ws_canary_identity.source,
                assignment_sticky=_ws_canary_identity.sticky,
                implicit_downgrade_allowed=not (
                    is_chatgpt_auth or _has_codex_responses_lite_hint(ws_headers)
                ),
                allow_transport_safe_targets=not is_chatgpt_auth,
            )
            if isinstance(body, dict):
                body["model"] = ws_model
                if isinstance(body.get("response"), dict):
                    body["response"]["model"] = ws_model
                _apply_model_routing_request_overrides(body, ws_savings_metadata)
                # The native WS relay must run the same ChatGPT-subscription
                # request-shape sanitizer as HTTP so rejected fields do not
                # leak upstream. The sanitizer deliberately preserves the
                # requested model.
                if is_chatgpt_auth:
                    body, _ws_stripped_fields = _sanitize_chatgpt_subscription_responses_body(body)
                    if isinstance(body.get("response"), dict):
                        body["response"]["model"] = body.get("model", ws_model)
                    if _ws_stripped_fields:
                        logger.info(
                            "[%s] WS /v1/responses stripped unsupported subscription fields: %s",
                            request_id,
                            ", ".join(_ws_stripped_fields),
                        )
                # `first_msg_raw` (the string), not `body` (the parsed dict),
                # is what memory-injection/compression re-derive their working
                # copy from below, and what gets sent upstream verbatim when
                # neither of those run (memory disabled, compression disabled,
                # or the request too small to compress). Without this
                # resync, every mutation above — model routing, the ChatGPT
                # subscription sanitizer, request overrides — is
                # silently discarded and the client's original bytes go
                # upstream unchanged.
                first_msg_raw = json.dumps(body)
            ws_input_tokens_total = 0
            ws_output_tokens_total = 0
            ws_cache_read_tokens_total = 0
            ws_cache_write_tokens_total = 0
            ws_uncached_input_tokens_total = 0
            ws_recorded_input_tokens_total = 0
            ws_recorded_output_tokens_total = 0
            ws_recorded_cache_read_tokens_total = 0
            ws_recorded_cache_write_tokens_total = 0
            ws_recorded_uncached_input_tokens_total = 0
            ws_recorded_tokens_saved_total = 0
            ws_recorded_attempted_input_tokens_total = 0
            ws_response_create_frames = 1
            ws_client_frames_total = 1
            ws_upstream_frames_total = 0
            ws_cancel_frames = 0
            ws_last_client_frame_type = str(body.get("type") or "unknown") if body else "unknown"
            ws_last_upstream_frame_type = "unknown"
            ws_client_disconnect_seen = False
            ws_overhead_ms_total = 0.0
            ws_recorded_overhead_ms_total = 0.0
            ws_compression_timing_totals: dict[str, float] = {}
            ws_recorded_compression_timing_totals: dict[str, float] = {}
            ws_ttfb_ms: float | None = None
            ws_recorded_ttfb_ms = False
            _ws_bypass = self._cutctx_bypass_enabled(ws_headers)
            if _ws_bypass:
                logger.info(
                    "[%s] WS /v1/responses passthrough reason=bypass_header mutation=disabled",
                    request_id,
                )

            capture_codex_wire_debug(
                "ws_inbound_first_frame",
                request_id=request_id,
                session_id=conversation_session_id,
                transport="websocket",
                direction="client_to_cutctx",
                url=_ws_url,
                body=body if body else None,
                raw_text=None if body else first_msg_raw,
                metadata={"frame": 1},
            )

            def _record_ws_compression_overhead(duration_ms: float) -> None:
                nonlocal ws_overhead_ms_total
                ws_overhead_ms_total += max(0.0, float(duration_ms))
                if ws_overhead_ms_total > 0:
                    stage_timer.record("compression", ws_overhead_ms_total)

            def _record_ws_compression_timing(name: str, duration_ms: float) -> None:
                ws_compression_timing_totals[name] = ws_compression_timing_totals.get(
                    name, 0.0
                ) + max(0.0, float(duration_ms))

            def _codex_ws_final_strategies(timing: dict[str, float]) -> list[str]:
                prefix = "compression_unit_router_strategy_"
                return [
                    name.removeprefix(prefix)
                    for name, ms in timing.items()
                    if name.startswith(prefix) and ms > 0
                ]

            def _codex_ws_strategy_chain(transforms: list[str]) -> list[str]:
                chain: list[str] = []
                for transform in transforms:
                    if ":" in transform:
                        continue
                    if transform not in chain:
                        chain.append(transform)
                return chain

            def _current_ws_overhead_ms() -> float:
                summary = stage_timer.summary()
                return ws_overhead_ms_total + max(0.0, float(summary.get("memory_context") or 0.0))

            def _ws_dashboard_pipeline_timing(
                *,
                overhead_ms: float,
                ttfb_ms: float,
            ) -> dict[str, float]:
                timing: dict[str, float] = {}
                if overhead_ms > 0:
                    timing["codex_ws.compression"] = overhead_ms
                if ttfb_ms > 0:
                    timing["codex_ws.ttfb"] = ttfb_ms

                for stage_name, total_ms in ws_compression_timing_totals.items():
                    recorded_ms = ws_recorded_compression_timing_totals.get(stage_name, 0.0)
                    delta_ms = max(0.0, total_ms - recorded_ms)
                    if delta_ms > 0:
                        timing[f"codex_ws.{stage_name}"] = delta_ms

                summary = stage_timer.summary()
                for stage_name in (
                    "memory_context",
                    "upstream_connect",
                    "upstream_first_event",
                ):
                    value = summary.get(stage_name)
                    if value is not None and value > 0:
                        timing[f"codex_ws.{stage_name}"] = float(value)
                return timing

            def _prepare_ws_performance_metrics() -> tuple[float, float, dict[str, float]]:
                current_overhead_ms = _current_ws_overhead_ms()
                overhead_delta_ms = max(
                    0.0,
                    current_overhead_ms - ws_recorded_overhead_ms_total,
                )
                ttfb_for_record_ms = (
                    max(0.0, float(ws_ttfb_ms))
                    if ws_ttfb_ms is not None and not ws_recorded_ttfb_ms
                    else 0.0
                )
                return (
                    overhead_delta_ms,
                    ttfb_for_record_ms,
                    _ws_dashboard_pipeline_timing(
                        overhead_ms=overhead_delta_ms,
                        ttfb_ms=ttfb_for_record_ms,
                    ),
                )

            # --- Memory: inject context, tools, and instructions ---
            # Gated on MemoryDecision — uniform bypass-respect across
            # all five sites. WS sets memory_user_id only on the inject
            # path (matches pre-PR behaviour); MemoryDecision is the
            # canonical gate.
            memory_user_id: str | None = None
            memory_request_ctx = None
            if self.memory_handler and body:
                _ws_memory_user_id_candidate = ws_headers.get(
                    "x-cutctx-user-id",
                    os.environ.get("USER", os.environ.get("USERNAME", "default")),
                )
            else:
                _ws_memory_user_id_candidate = None
            from cutctx.proxy.helpers import get_memory_injection_mode
            from cutctx.proxy.memory_decision import MemoryDecision
            from cutctx.proxy.memory_query import MemoryQuery

            ws_memory_decision = MemoryDecision.decide(
                headers=ws_headers,
                memory_handler=self.memory_handler if body else None,
                memory_user_id=_ws_memory_user_id_candidate,
                mode_name=get_memory_injection_mode(),
                messages=ws_messages,
            )
            # ws_tags was extracted at handler entry (L3028); applying
            # the memory skip reason here so per-turn RequestOutcomes
            # carry it for dashboard slicing.
            ws_memory_decision.apply_to_tags(ws_tags)
            if ws_memory_decision.inject:
                memory_user_id = _ws_memory_user_id_candidate
                try:
                    # Unwrap response.create envelope to access the response body
                    ws_response_body = body.get("response", body)

                    # Per-project memory routing (GH #462). For WS,
                    # ``ws_response_body`` carries ``instructions`` —
                    # that's the system-prompt-equivalent we feed to the
                    # resolver.
                    from cutctx.memory.storage_router import (
                        RequestContext as _MemRequestContext,
                    )

                    memory_request_ctx = _MemRequestContext(
                        headers=dict(ws_headers),
                        system_prompt=str(ws_response_body.get("instructions") or ""),
                        base_user_id=memory_user_id,
                        project_root_override=(
                            getattr(self.memory_handler.config, "project_root_override", "") or None
                        ),
                    )

                    # Debug: log what Codex sends so we can see the full tool list
                    existing_tool_names = [
                        t.get("name") or t.get("function", {}).get("name", "?")
                        for t in (ws_response_body.get("tools") or [])
                    ]
                    instr_preview = (ws_response_body.get("instructions") or "")[:200]
                    logger.info(
                        f"[{request_id}] WS Memory: Codex tools={existing_tool_names}, "
                        f"instructions_len={len(ws_response_body.get('instructions') or '')}, "
                        f"instructions_preview={instr_preview!r}"
                    )

                    # Inject memory context into instructions
                    if self.memory_handler.config.inject_context:
                        ws_input = ws_response_body.get("input", "")
                        ws_instructions = ws_response_body.get("instructions")
                        ws_msgs: list[dict[str, Any]] = []
                        if ws_instructions:
                            ws_msgs.append({"role": "system", "content": ws_instructions})
                        if isinstance(ws_input, str) and ws_input:
                            ws_msgs.append({"role": "user", "content": ws_input})
                        # PR-C5: list-typed `input` no longer feeds memory
                        # search via the Python converter — the Rust handler
                        # owns native item-aware processing. Memory context
                        # for list-input WS sessions falls back to the
                        # `instructions` system message only.

                        try:
                            async with stage_timer.measure("memory_context"):
                                memory_context = await asyncio.wait_for(
                                    self.memory_handler.search_and_format_context(
                                        memory_user_id,
                                        ws_msgs,
                                        request_context=memory_request_ctx,
                                        query=MemoryQuery.from_messages(ws_msgs),
                                    ),
                                    timeout=RESPONSES_CONTEXT_SEARCH_TIMEOUT_SECONDS,
                                )
                        except asyncio.TimeoutError:
                            memory_context = None
                            logger.info(
                                f"[{request_id}] WS Memory: Context lookup exceeded "
                                f"{RESPONSES_CONTEXT_SEARCH_TIMEOUT_SECONDS:.1f}s; "
                                f"continuing without it"
                            )
                        if memory_context:
                            # Route memory into ws_response_body["input"]
                            # (the user-input field) rather than
                            # ws_response_body["instructions"] (the
                            # system/cache-hot-zone field). All other
                            # handlers inject at the user-message tail
                            # so the cache prefix bytes stay byte-
                            # stable across turns — invariant I2. The
                            # WS path was the lone outlier writing to
                            # instructions (system); fixed here for
                            # uniformity with sites 1/2/3/4.
                            ws_input_for_inject = ws_response_body.get("input", "")
                            if isinstance(ws_input_for_inject, str):
                                if ws_input_for_inject:
                                    ws_response_body["input"] = (
                                        ws_input_for_inject + "\n\n" + memory_context
                                    )
                                else:
                                    ws_response_body["input"] = memory_context
                                logger.info(
                                    f"[{request_id}] WS Memory: Injected {len(memory_context)} chars "
                                    f"into input tail (string-shaped input)"
                                )
                            else:
                                # List-shaped WS input is owned by the
                                # Rust handler (per PR-C5 comment). The
                                # Python path leaves memory un-injected
                                # for list inputs rather than touching
                                # instructions.
                                logger.info(
                                    f"[{request_id}] WS Memory: list-shaped input — "
                                    f"injection deferred to Rust handler"
                                )

                    # Inject memory tools (Responses API format) — PR-A7 (P0-6).
                    # WS path uses a per-connection UUID; tracker scope is
                    # the WS session (short-lived). Pre-convert to Responses
                    # API format so canonical bytes match the wire format.
                    from cutctx.proxy.helpers import (
                        apply_session_sticky_memory_tools as _apply_sticky_mem_tools_ws,
                    )

                    ws_mem_defs_chat = (
                        self.memory_handler.compute_memory_tool_definitions("openai")
                        if self.memory_handler.config.inject_tools
                        else []
                    )
                    ws_mem_defs_responses: list[dict[str, Any]] = []
                    for t in ws_mem_defs_chat:
                        if t.get("type") == "function" and "function" in t:
                            fn = t["function"]
                            ws_mem_defs_responses.append(
                                {
                                    "type": "function",
                                    "name": fn.get("name"),
                                    "description": fn.get("description", ""),
                                    "parameters": fn.get("parameters", {}),
                                }
                            )
                        else:
                            ws_mem_defs_responses.append(t)

                    ws_tools = ws_response_body.get("tools") or []
                    ws_tools, mem_injected = _apply_sticky_mem_tools_ws(
                        provider="openai",
                        session_id=conversation_session_id,
                        request_id=request_id,
                        existing_tools=ws_tools,
                        memory_tools_to_inject=ws_mem_defs_responses,
                        inject_this_turn=bool(self.memory_handler.config.inject_tools),
                    )
                    if mem_injected:
                        ws_response_body["tools"] = ws_tools

                        # Add memory instruction so the model uses
                        # memory tools as persistent cross-session knowledge.
                        mem_instruction = (
                            "\n\n## Memory\n"
                            "You have persistent memory via memory_search and "
                            "memory_save tools. Memory stores knowledge across "
                            "sessions — user info, project details, org context, "
                            "decisions, architecture, conventions, anything worth "
                            "remembering.\n\n"
                            "- ALWAYS call memory_search BEFORE searching files "
                            "when the user asks a question that could be answered "
                            "from prior knowledge.\n"
                            "- Call memory_save to store important facts, decisions, "
                            "or context that would be useful in future sessions.\n"
                            "- Memory is your first source of truth for anything "
                            "not visible in the current conversation."
                        )
                        existing_instr = ws_response_body.get("instructions") or ""
                        ws_response_body["instructions"] = existing_instr + mem_instruction
                        logger.info(
                            f"[{request_id}] WS Memory: Injected memory tools + instruction"
                        )

                    # Write back into envelope if it was wrapped
                    if "response" in body and isinstance(body["response"], dict):
                        body["response"] = ws_response_body
                    else:
                        body = ws_response_body

                    first_msg_raw = json.dumps(body)
                except Exception as e:
                    logger.warning(f"[{request_id}] WS Memory injection failed: {e}")
            elif self.memory_handler and body and _ws_bypass:
                logger.info(
                    "[%s] WS memory passthrough reason=bypass_header",
                    request_id,
                )

            # Hot-fix follow-up to PR #406 — inline Rust compression on the
            # WS first frame before forwarding upstream. PR #406 enabled
            # the same call for HTTP /v1/responses; PR-C5's "WS-side
            # compression is a follow-up" note is closed here. Codex
            # subscription users default to WebSocket transport for
            # /v1/responses (proxy-confirmed via #409 reviewer testing),
            # so without this call subscription traffic flows through
            # Cutctx uncompressed.
            #
            # The first frame may be either:
            #   • {"type": "response.create", "response": {...payload...}}
            #   • the payload directly (older shapes)
            # We unwrap, compress the inner payload via the PyO3 dispatcher,
            # and re-wrap so both shapes work.
            #
            # Re-parses from `first_msg_raw` rather than reusing `body`
            # because `body` may be partially mutated if memory injection
            # raised an exception above (in which case `first_msg_raw` is
            # the canonical pre-memory bytes that will actually be sent
            # upstream). The PyO3 binding never raises (passthrough on
            # internal errors), but we wrap the call site in try/except
            # anyway so a JSON-shape edge case can never break the WS
            # session.
            if self.config.optimize and not _ws_bypass:
                _first_frame_compression_elapsed_ms = 0.0
                try:
                    _preflight_started = time.perf_counter()
                    _ws_auth_mode = classify_auth_mode(ws_headers)
                    try:
                        _send_body = json.loads(first_msg_raw)
                    except json.JSONDecodeError:
                        _send_body = None

                    if isinstance(_send_body, dict):
                        _wrapped = "response" in _send_body and isinstance(
                            _send_body["response"], dict
                        )
                        _inner = _send_body["response"] if _wrapped else _send_body
                        _model = (_inner.get("model") if isinstance(_inner, dict) else None) or ""

                        _preflight_ms = (time.perf_counter() - _preflight_started) * 1000.0
                        _record_ws_compression_timing(
                            "compression_preflight_serialization",
                            _preflight_ms,
                        )
                        _record_ws_compression_overhead(_preflight_ms)
                        _compression_started = time.perf_counter()
                        try:
                            _tool_scaffolding_tokens = estimate_tool_scaffolding_tokens(
                                _inner.get("tools") if isinstance(_inner, dict) else None,
                                get_tokenizer(_model),
                            )
                            _tool_surface_result = slim_tool_surface(
                                _inner.get("tools") if isinstance(_inner, dict) else None,
                                query=extract_responses_query(
                                    _inner if isinstance(_inner, dict) else {}
                                ),
                                tokenizer=get_tokenizer(_model),
                                config=self.config,
                                tool_choice=_inner.get("tool_choice")
                                if isinstance(_inner, dict)
                                else None,
                                messages=_inner if isinstance(_inner, dict) else None,
                            )
                            _tool_surface_saved = _tool_surface_result.tokens_saved
                            if _tool_surface_result.modified and isinstance(_inner, dict):
                                _inner = {**_inner, "tools": _tool_surface_result.tools}
                                ws_savings_metadata = merge_savings_metadata(
                                    ws_savings_metadata,
                                    {"api_surface_slimming": {"tokens": _tool_surface_saved}},
                                )
                            if _tool_scaffolding_tokens > 0:
                                _schema_saved = 0
                                ws_savings_metadata = merge_savings_metadata(
                                    ws_savings_metadata,
                                    {
                                        "ghost_token_audit": {
                                            "scaffolding_tokens": _tool_scaffolding_tokens,
                                            "ghost_tokens": max(
                                                0,
                                                _tool_scaffolding_tokens
                                                - _tool_surface_saved
                                                - _schema_saved,
                                            ),
                                        }
                                    },
                                )
                            _original_ws_tools = copy.deepcopy(_inner.get("tools"))
                            (
                                _new_inner,
                                _modified,
                                _ws_saved,
                                _ws_transforms,
                                _ws_reason,
                                _bytes_before,
                                _bytes_after,
                                _ws_attempted_tokens,
                                _ws_compression_timing,
                            ) = await self._compress_openai_responses_payload_in_executor(
                                _inner,
                                model=_model,
                                request_id=request_id,
                            )
                            if (
                                _original_ws_tools
                                and "openai:responses:tool_schema_compaction" in _ws_transforms
                            ):
                                ws_savings_metadata = merge_savings_metadata(
                                    ws_savings_metadata,
                                    _tool_schema_savings_metadata(
                                        get_tokenizer(_model),
                                        _original_ws_tools,
                                        _new_inner.get("tools"),
                                    ),
                                )
                            for _timing_name, _timing_ms in _ws_compression_timing.items():
                                _record_ws_compression_timing(_timing_name, _timing_ms)
                        finally:
                            _first_frame_compression_elapsed_ms = (
                                time.perf_counter() - _compression_started
                            ) * 1000.0
                            _record_ws_compression_timing(
                                "compression_executor_wait_run",
                                _first_frame_compression_elapsed_ms,
                            )
                            _record_ws_compression_overhead(_first_frame_compression_elapsed_ms)
                        record_frame = getattr(
                            getattr(self, "metrics", None), "record_codex_ws_frame", None
                        )
                        if record_frame is not None:
                            record_frame(
                                elapsed_ms=_first_frame_compression_elapsed_ms,
                                bytes_before=_bytes_before,
                                bytes_after=_bytes_after,
                                attempted_tokens=_ws_attempted_tokens,
                                tokens_saved=_ws_saved,
                                modified=_modified,
                                strategy_chain=_codex_ws_strategy_chain(_ws_transforms),
                                final_strategies=_codex_ws_final_strategies(_ws_compression_timing),
                            )
                        if _modified:
                            if isinstance(_new_inner, dict):
                                _rewrite_started = time.perf_counter()
                                if _wrapped:
                                    _send_body["response"] = _new_inner
                                else:
                                    _send_body = _new_inner
                                first_msg_raw = json.dumps(_send_body)
                                _rewrite_ms = (time.perf_counter() - _rewrite_started) * 1000.0
                                _record_ws_compression_timing(
                                    "compression_payload_rewrite_json_dump",
                                    _rewrite_ms,
                                )
                                _record_ws_compression_overhead(_rewrite_ms)
                            tokens_saved += int(_tool_surface_saved)
                            attempted_input_tokens_total += int(_tool_surface_saved)
                            if _tool_surface_result.modified:
                                if (
                                    "openai:responses:tool_surface_slimming"
                                    not in transforms_applied
                                ):
                                    transforms_applied.append(
                                        "openai:responses:tool_surface_slimming"
                                    )
                            tokens_saved += int(_ws_saved)
                            attempted_input_tokens_total += int(_ws_attempted_tokens)
                            for _t in _ws_transforms:
                                if _t not in transforms_applied:
                                    transforms_applied.append(_t)
                            logger.info(
                                "[%s] WS /v1/responses compressed "
                                "%d→%d bytes (%d tokens saved, "
                                "auth_mode=%s, transforms=%s)",
                                request_id,
                                _bytes_before,
                                _bytes_after,
                                int(_ws_saved),
                                _ws_auth_mode.value,
                                transforms_applied,
                            )
                            ws_frames_compressed += 1
                        else:
                            _log_ws_passthrough(
                                _ws_reason or "no_compression",
                                frame_index=1,
                                raw_bytes=_bytes_before,
                                frame_type=str(_send_body.get("type") or "response.create"),
                                model=_model or "unknown",
                            )
                    else:
                        _log_ws_passthrough(
                            "first_frame_non_json",
                            frame_index=1,
                            raw_bytes=len(first_msg_raw.encode("utf-8", errors="replace")),
                            frame_type="unknown",
                        )
                except Exception as _ce:
                    _ws_frame_bytes = len(first_msg_raw.encode("utf-8", errors="replace"))
                    if _first_frame_compression_elapsed_ms > 0:
                        record_frame = getattr(
                            getattr(self, "metrics", None), "record_codex_ws_frame", None
                        )
                        if record_frame is not None:
                            record_frame(
                                elapsed_ms=_first_frame_compression_elapsed_ms,
                                bytes_before=_ws_frame_bytes,
                                failed=True,
                            )
                    logger.warning(
                        f"[{request_id}] WS /v1/responses compression failed "
                        f"(bytes={_ws_frame_bytes}): {type(_ce).__name__}: {_ce}"
                    )
                    _log_ws_passthrough(
                        "compression_exception",
                        frame_index=1,
                        raw_bytes=_ws_frame_bytes,
                        frame_type="response.create" if body else "unknown",
                        model=str(body.get("model") or "unknown")
                        if isinstance(body, dict)
                        else "unknown",
                    )
                    # Fail-closed protection (default): refuse to forward
                    # oversized frames after a compression failure. Forwarding
                    # the original to the upstream would cause a
                    # context-window-exceeded response that the client
                    # (e.g. Codex) cannot recover from, because Cutctx's
                    # earlier successful compressions hid the cumulative
                    # context pressure from the client's auto-compaction
                    # heuristic. Close the client WS with 1009 instead so the
                    # client gets a clear "compact and retry" signal.
                    # See helpers.decide_compression_failure_action for the
                    # decision matrix and env-var overrides.
                    from cutctx.proxy.helpers import (
                        decide_compression_failure_action,
                    )

                    _ws_action = decide_compression_failure_action(
                        _ce,
                        _ws_frame_bytes,
                        client=client,
                    )
                    if _ws_action.refuse:
                        logger.error(
                            "[%s] WS /v1/responses REFUSING to forward "
                            "frame after compression failure "
                            "(reason=%s, bytes=%d); closing client "
                            "websocket with 1009 so client can compact "
                            "context and retry. To restore legacy "
                            "passthrough behaviour set "
                            "CUTCTX_WS_FAIL_OPEN_ON_COMPRESSION_FAILURE=1.",
                            request_id,
                            _ws_action.reason,
                            _ws_action.frame_bytes,
                        )
                        termination_cause = "compression_refused"
                        with contextlib.suppress(Exception):
                            await websocket.close(
                                code=1009,
                                reason=(
                                    "cutctx: compression "
                                    f"{_ws_action.reason} — please "
                                    "compact context and retry"
                                ),
                            )
                        return
            else:
                _log_ws_passthrough(
                    "bypass_header" if _ws_bypass else "optimize_disabled",
                    frame_index=1,
                    raw_bytes=len(first_msg_raw.encode("utf-8", errors="replace")),
                    frame_type="response.create" if body else "unknown",
                    model=str(body.get("model") or "unknown")
                    if isinstance(body, dict)
                    else "unknown",
                )

            _first_upstream_body: Any = None
            try:
                _first_upstream_body = json.loads(first_msg_raw)
            except json.JSONDecodeError:
                _first_upstream_body = None
            if self.config.optimize and not _ws_bypass and isinstance(_first_upstream_body, dict):
                _guard_inner = (
                    _first_upstream_body["response"]
                    if isinstance(_first_upstream_body.get("response"), dict)
                    else _first_upstream_body
                )
                if isinstance(_guard_inner, dict):
                    _guard_model = str(_guard_inner.get("model") or "unknown")
                    (
                        _guard_refuse,
                        _guard_estimated,
                        _guard_threshold,
                        _guard_limit,
                    ) = self._openai_responses_context_guard(
                        _guard_inner,
                        model=_guard_model,
                    )
                    _opaque_subscription_continuation = (
                        is_chatgpt_auth
                        and _contains_opaque_responses_continuation(_guard_inner)
                    )
                    if _guard_refuse and _opaque_subscription_continuation:
                        logger.warning(
                            "[%s] WS /v1/responses treating approximate first-frame "
                            "context guard as advisory for opaque ChatGPT subscription "
                            "continuation (estimated_tokens=%d threshold=%d "
                            "context_limit=%d model=%s)",
                            request_id,
                            _guard_estimated,
                            _guard_threshold,
                            _guard_limit,
                            _guard_model,
                        )
                    elif _guard_refuse:
                        logger.error(
                            "[%s] WS /v1/responses refusing oversized first frame "
                            "after compression (estimated_tokens=%d threshold=%d "
                            "context_limit=%d model=%s tokens_saved=%d transforms=%s)",
                            request_id,
                            _guard_estimated,
                            _guard_threshold,
                            _guard_limit,
                            _guard_model,
                            tokens_saved,
                            transforms_applied,
                        )
                        termination_cause = "context_refused"
                        with contextlib.suppress(Exception):
                            await websocket.close(
                                code=1009,
                                reason="cutctx: context too large — compact context and retry",
                            )
                        return
            capture_codex_wire_debug(
                "ws_upstream_first_frame",
                request_id=request_id,
                session_id=session_id,
                transport="websocket",
                direction="cutctx_to_upstream",
                url=upstream_url,
                body=_first_upstream_body,
                raw_text=None if _first_upstream_body is not None else first_msg_raw,
                metadata={
                    "frame": 1,
                    "tokens_saved": tokens_saved,
                    "transforms_applied": transforms_applied,
                },
            )

            if ws_connected:
                # websockets 13.x: an already-awaited WebSocketClientProtocol
                # does not support the async context manager protocol — use an
                # explicit try/finally for cleanup instead.
                try:
                    await upstream.send(first_msg_raw)

                    # Unit 3: flag the upstream side flips on seeing
                    # ``response.completed`` so the outer cause
                    # classifier can prefer it over the raw
                    # "upstream iterator ended" default.
                    response_completed_seen = False
                    # Captures the first exception surfaced by the
                    # inner relay ``except`` blocks so the outer
                    # classifier can still tell ``upstream_error``
                    # from ``upstream_disconnect`` / ``response_completed``
                    # even though the halves swallow and log.
                    upstream_relay_error: BaseException | None = None
                    client_relay_error: BaseException | None = None

                    async def _maybe_compress_response_create_frame(
                        raw_msg: str,
                        *,
                        frame_index: int,
                    ) -> tuple[str, bool, str | None]:
                        """Compress a single client→upstream frame
                        when its `type` is `response.create`. Other
                        event types (response.cancel, session.update,
                        etc.) pass through unchanged. Errors are
                        warned and the original frame is returned —
                        fail loud in logs, fail safe on the wire.
                        Updates outer-scope ``tokens_saved``,
                        ``transforms_applied``, and
                        ``ws_frames_compressed`` so the session-end
                        log reports cumulative savings across all
                        frames in the WS session.
                        """
                        nonlocal tokens_saved, transforms_applied, attempted_input_tokens_total
                        nonlocal ws_frames_compressed, ws_savings_metadata
                        nonlocal termination_cause
                        if _ws_bypass:
                            _log_ws_passthrough(
                                "bypass_header",
                                frame_index=frame_index,
                                raw_bytes=len(raw_msg.encode("utf-8", errors="replace")),
                            )
                            return raw_msg, False, "bypass_header"
                        if not self.config.optimize:
                            _log_ws_passthrough(
                                "optimize_disabled",
                                frame_index=frame_index,
                                raw_bytes=len(raw_msg.encode("utf-8", errors="replace")),
                            )
                            return raw_msg, False, "optimize_disabled"
                        _preflight_started = time.perf_counter()
                        try:
                            parsed_frame = json.loads(raw_msg)
                        except json.JSONDecodeError:
                            _log_ws_passthrough(
                                "non_json",
                                frame_index=frame_index,
                                raw_bytes=len(raw_msg.encode("utf-8", errors="replace")),
                            )
                            return raw_msg, False, "non_json"
                        if (
                            not isinstance(parsed_frame, dict)
                            or parsed_frame.get("type") != "response.create"
                        ):
                            _log_ws_passthrough(
                                "not_response_create",
                                frame_index=frame_index,
                                raw_bytes=len(raw_msg.encode("utf-8", errors="replace")),
                                frame_type=(
                                    parsed_frame.get("type")
                                    if isinstance(parsed_frame, dict)
                                    else type(parsed_frame).__name__
                                ),
                            )
                            return raw_msg, False, "not_response_create"
                        wrapped_frame = isinstance(parsed_frame.get("response"), dict)
                        inner_payload = parsed_frame["response"] if wrapped_frame else parsed_frame
                        if not isinstance(inner_payload, dict):
                            _log_ws_passthrough(
                                "invalid_inner_payload",
                                frame_index=frame_index,
                                raw_bytes=len(raw_msg.encode("utf-8", errors="replace")),
                                frame_type="response.create",
                            )
                            return raw_msg, False, "invalid_inner_payload"
                        frame_routed = False
                        from cutctx.proxy.model_router import prepare_model_routing

                        original_frame_model = str(inner_payload.get("model") or "unknown")
                        frame_messages = _responses_payload_to_routing_messages(inner_payload)
                        from cutctx.proxy.handlers.openai.utils import (
                            _has_codex_responses_lite_hint,
                        )

                        routed_frame_model, ws_savings_metadata = prepare_model_routing(
                            self,
                            original_frame_model,
                            request_savings_metadata=ws_savings_metadata,
                            num_messages=len(frame_messages),
                            messages=frame_messages,
                            request_id=_ws_canary_identity.value,
                            client=classify_client(ws_headers),
                            assignment_identity_source=_ws_canary_identity.source,
                            assignment_sticky=_ws_canary_identity.sticky,
                            implicit_downgrade_allowed=not (
                                is_chatgpt_auth or _has_codex_responses_lite_hint(ws_headers)
                            ),
                            allow_transport_safe_targets=not is_chatgpt_auth,
                        )
                        if routed_frame_model != original_frame_model:
                            inner_payload = {**inner_payload, "model": routed_frame_model}
                            frame_routed = True
                        # Turn 1 of a WS session runs the
                        # ChatGPT-subscription request-shape sanitizer; this
                        # per-frame path for turn 2+ must do the same while
                        # preserving the requested model.
                        if is_chatgpt_auth:
                            inner_payload, _frame_stripped_fields = (
                                _sanitize_chatgpt_subscription_responses_body(inner_payload)
                            )
                            if _frame_stripped_fields:
                                frame_routed = True
                        if frame_routed:
                            if wrapped_frame:
                                parsed_frame["response"] = inner_payload
                            else:
                                parsed_frame = inner_payload
                            _apply_model_routing_request_overrides(
                                inner_payload,
                                ws_savings_metadata,
                            )
                        frame_compression_elapsed_ms = 0.0
                        try:
                            model_for_frame = inner_payload.get("model") or ""
                            _frame_auth_mode = classify_auth_mode(ws_headers)
                            _preflight_ms = (time.perf_counter() - _preflight_started) * 1000.0
                            _record_ws_compression_timing(
                                "compression_preflight_serialization",
                                _preflight_ms,
                            )
                            _record_ws_compression_overhead(_preflight_ms)
                            _compression_started = time.perf_counter()
                            try:
                                frame_surface_result = slim_tool_surface(
                                    inner_payload.get("tools")
                                    if isinstance(inner_payload, dict)
                                    else None,
                                    query=extract_responses_query(
                                        inner_payload if isinstance(inner_payload, dict) else {}
                                    ),
                                    config=self.config,
                                    tokenizer=get_tokenizer(model_for_frame),
                                    tool_choice=inner_payload.get("tool_choice")
                                    if isinstance(inner_payload, dict)
                                    else None,
                                    messages=inner_payload
                                    if isinstance(inner_payload, dict)
                                    else None,
                                )
                                frame_surface_saved = frame_surface_result.tokens_saved
                                if not is_chatgpt_auth and frame_surface_result.modified and isinstance(
                                    inner_payload, dict
                                ):
                                    inner_payload = {
                                        **inner_payload,
                                        "tools": frame_surface_result.tools,
                                    }
                                    ws_savings_metadata = merge_savings_metadata(
                                        ws_savings_metadata,
                                        {"api_surface_slimming": {"tokens": frame_surface_saved}},
                                    )
                                original_frame_tools = copy.deepcopy(inner_payload.get("tools"))
                                (
                                    new_inner,
                                    modified,
                                    frame_saved,
                                    frame_transforms,
                                    frame_reason,
                                    bytes_before,
                                    bytes_after,
                                    frame_attempted_tokens,
                                    frame_compression_timing,
                                ) = await self._compress_openai_responses_payload_in_executor(
                                    inner_payload,
                                    model=model_for_frame,
                                    request_id=request_id,
                                    compact_tool_schemas=not is_chatgpt_auth,
                                    allow_payload_mutation=not is_chatgpt_auth,
                                )
                                if (
                                    original_frame_tools
                                    and "openai:responses:tool_schema_compaction"
                                    in frame_transforms
                                ):
                                    ws_savings_metadata = merge_savings_metadata(
                                        ws_savings_metadata,
                                        _tool_schema_savings_metadata(
                                            get_tokenizer(model_for_frame),
                                            original_frame_tools,
                                            new_inner.get("tools"),
                                        ),
                                    )
                                for (
                                    _timing_name,
                                    _timing_ms,
                                ) in frame_compression_timing.items():
                                    _record_ws_compression_timing(
                                        _timing_name,
                                        _timing_ms,
                                    )
                            finally:
                                frame_compression_elapsed_ms = (
                                    time.perf_counter() - _compression_started
                                ) * 1000.0
                                _record_ws_compression_timing(
                                    "compression_executor_wait_run",
                                    frame_compression_elapsed_ms,
                                )
                                _record_ws_compression_overhead(frame_compression_elapsed_ms)
                            record_frame = getattr(
                                getattr(self, "metrics", None),
                                "record_codex_ws_frame",
                                None,
                            )
                            if record_frame is not None:
                                record_frame(
                                    elapsed_ms=frame_compression_elapsed_ms,
                                    bytes_before=bytes_before,
                                    bytes_after=bytes_after,
                                    attempted_tokens=frame_attempted_tokens,
                                    tokens_saved=frame_saved,
                                    modified=modified,
                                    strategy_chain=_codex_ws_strategy_chain(frame_transforms),
                                    final_strategies=_codex_ws_final_strategies(
                                        frame_compression_timing
                                    ),
                                )
                        except Exception as _frame_err:
                            if frame_compression_elapsed_ms > 0:
                                record_frame = getattr(
                                    getattr(self, "metrics", None),
                                    "record_codex_ws_frame",
                                    None,
                                )
                                if record_frame is not None:
                                    record_frame(
                                        elapsed_ms=frame_compression_elapsed_ms,
                                        bytes_before=len(raw_msg.encode("utf-8", errors="replace")),
                                        failed=True,
                                    )
                                logger.warning(
                                    "[%s] WS /v1/responses frame compression "
                                    "failed; forwarding %s: %s: %s",
                                    request_id,
                                    "routed frame" if frame_routed else "original",
                                    type(_frame_err).__name__,
                                    _frame_err,
                                )
                                _log_ws_passthrough(
                                    "compression_exception",
                                    frame_index=frame_index,
                                    raw_bytes=len(raw_msg.encode("utf-8", errors="replace")),
                                    frame_type="response.create",
                                    model=str(inner_payload.get("model") or "unknown"),
                                )
                                refusal_client = classify_client(ws_headers)
                                (
                                    guard_refuse,
                                    guard_estimated,
                                    guard_threshold,
                                    guard_limit,
                                    refusal_reason,
                                ) = self._openai_responses_compression_failure_refusal(
                                    inner_payload,
                                    model=str(inner_payload.get("model") or "unknown"),
                                    exception=_frame_err,
                                    raw_bytes=len(raw_msg.encode("utf-8", errors="replace")),
                                    client=refusal_client,
                                )
                                if guard_refuse and not (
                                    is_chatgpt_auth
                                    and _contains_opaque_responses_continuation(inner_payload)
                                ):
                                    logger.error(
                                        "[%s] WS /v1/responses refusing frame after "
                                        "compression failure (reason=%s, estimated_tokens=%d "
                                        "threshold=%d context_limit=%d model=%s frame=%d)",
                                        request_id,
                                        refusal_reason,
                                        guard_estimated,
                                        guard_threshold,
                                        guard_limit,
                                        str(inner_payload.get("model") or "unknown"),
                                        frame_index,
                                    )
                                    termination_cause = "context_refused"
                                    with contextlib.suppress(Exception):
                                        await websocket.close(
                                            code=1009,
                                            reason=(
                                                "cutctx: context too large — "
                                                "compact context and retry"
                                            ),
                                        )
                                    with contextlib.suppress(Exception):
                                        await upstream.close()
                                    return raw_msg, False, "context_refused"
                                if frame_routed:
                                    _rewrite_started = time.perf_counter()
                                    rewritten = json.dumps(parsed_frame)
                                    _rewrite_ms = (time.perf_counter() - _rewrite_started) * 1000.0
                                    _record_ws_compression_timing(
                                        "compression_payload_rewrite_json_dump",
                                        _rewrite_ms,
                                    )
                                    _record_ws_compression_overhead(_rewrite_ms)
                                    return rewritten, True, "model_routing"
                                return raw_msg, False, "compression_exception"
                        if not modified:
                            reason = frame_reason or "no_compression"
                            (
                                guard_refuse,
                                guard_estimated,
                                guard_threshold,
                                guard_limit,
                            ) = self._openai_responses_context_guard(
                                inner_payload,
                                model=str(inner_payload.get("model") or "unknown"),
                            )
                            if guard_refuse and not (
                                is_chatgpt_auth
                                and _contains_opaque_responses_continuation(inner_payload)
                            ):
                                logger.error(
                                    "[%s] WS /v1/responses refusing oversized frame "
                                    "after no-op compression (estimated_tokens=%d "
                                    "threshold=%d context_limit=%d model=%s "
                                    "frame=%d reason=%s)",
                                    request_id,
                                    guard_estimated,
                                    guard_threshold,
                                    guard_limit,
                                    str(inner_payload.get("model") or "unknown"),
                                    frame_index,
                                    reason,
                                )
                                termination_cause = "context_refused"
                                with contextlib.suppress(Exception):
                                    await websocket.close(
                                        code=1009,
                                        reason=(
                                            "cutctx: context too large — compact context and retry"
                                        ),
                                    )
                                with contextlib.suppress(Exception):
                                    await upstream.close()
                                return raw_msg, False, "context_refused"
                            if frame_routed:
                                _rewrite_started = time.perf_counter()
                                rewritten = json.dumps(parsed_frame)
                                _rewrite_ms = (time.perf_counter() - _rewrite_started) * 1000.0
                                _record_ws_compression_timing(
                                    "compression_payload_rewrite_json_dump",
                                    _rewrite_ms,
                                )
                                _record_ws_compression_overhead(_rewrite_ms)
                                return rewritten, True, "model_routing"
                            _log_ws_passthrough(
                                reason,
                                frame_index=frame_index,
                                raw_bytes=bytes_before,
                                frame_type="response.create",
                                model=str(inner_payload.get("model") or "unknown"),
                            )
                            return raw_msg, False, reason
                        if not isinstance(new_inner, dict):
                            _log_ws_passthrough(
                                "compressed_payload_not_dict",
                                frame_index=frame_index,
                                raw_bytes=len(raw_msg.encode("utf-8", errors="replace")),
                                frame_type="response.create",
                                model=str(inner_payload.get("model") or "unknown"),
                            )
                            return raw_msg, False, "compressed_payload_not_dict"
                        if wrapped_frame:
                            _rewrite_started = time.perf_counter()
                            parsed_frame["response"] = new_inner
                            rewritten = json.dumps(parsed_frame)
                        else:
                            _rewrite_started = time.perf_counter()
                            rewritten = json.dumps(new_inner)
                        _rewrite_ms = (time.perf_counter() - _rewrite_started) * 1000.0
                        _record_ws_compression_timing(
                            "compression_payload_rewrite_json_dump",
                            _rewrite_ms,
                        )
                        _record_ws_compression_overhead(_rewrite_ms)
                        tokens_saved += int(frame_surface_saved)
                        attempted_input_tokens_total += int(frame_surface_saved)
                        if frame_surface_result.modified:
                            if "openai:responses:tool_surface_slimming" not in transforms_applied:
                                transforms_applied.append("openai:responses:tool_surface_slimming")
                        tokens_saved += int(frame_saved)
                        attempted_input_tokens_total += int(frame_attempted_tokens)
                        for t in frame_transforms:
                            if t not in transforms_applied:
                                transforms_applied.append(t)
                        (
                            guard_refuse,
                            guard_estimated,
                            guard_threshold,
                            guard_limit,
                        ) = self._openai_responses_context_guard(
                            new_inner,
                            model=str(new_inner.get("model") or "unknown"),
                        )
                        if guard_refuse and not (
                            is_chatgpt_auth
                            and _contains_opaque_responses_continuation(new_inner)
                        ):
                            logger.error(
                                "[%s] WS /v1/responses refusing oversized frame "
                                "after compression (estimated_tokens=%d threshold=%d "
                                "context_limit=%d model=%s frame=%d tokens_saved=%d)",
                                request_id,
                                guard_estimated,
                                guard_threshold,
                                guard_limit,
                                str(new_inner.get("model") or "unknown"),
                                frame_index,
                                int(frame_saved),
                            )
                            termination_cause = "context_refused"
                            with contextlib.suppress(Exception):
                                await websocket.close(
                                    code=1009,
                                    reason=(
                                        "cutctx: context too large — compact context and retry"
                                    ),
                                )
                            with contextlib.suppress(Exception):
                                await upstream.close()
                            return raw_msg, False, "context_refused"
                        ws_frames_compressed += 1
                        logger.info(
                            "[%s] WS /v1/responses frame compressed "
                            "%d→%d bytes (%d tokens saved, "
                            "auth_mode=%s, frame=%d)",
                            request_id,
                            bytes_before,
                            bytes_after,
                            int(frame_saved),
                            _frame_auth_mode.value,
                            ws_frames_compressed,
                        )
                        return rewritten, True, frame_reason or "compressed"

                    async def _client_to_upstream() -> None:
                        nonlocal client_relay_error, ws_response_create_frames
                        nonlocal ws_client_frames_total, ws_cancel_frames
                        nonlocal ws_last_client_frame_type, ws_client_disconnect_seen
                        client_frame_index = 1
                        try:
                            while True:
                                msg = await websocket.receive_text()
                                client_frame_index += 1
                                ws_client_frames_total += 1
                                if session_handle is not None:
                                    session_handle.mark_activity()
                                _inbound_frame_body: Any = None
                                try:
                                    _inbound_frame_body = json.loads(msg)
                                except json.JSONDecodeError:
                                    _inbound_frame_body = None
                                ws_last_client_frame_type = (
                                    str(_inbound_frame_body.get("type") or "unknown")
                                    if isinstance(_inbound_frame_body, dict)
                                    else "non_json"
                                )
                                if ws_last_client_frame_type == "response.cancel":
                                    ws_cancel_frames += 1
                                    logger.info(
                                        "[%s] WS client sent response.cancel "
                                        "session_id=%s frame=%d cancels=%d",
                                        request_id,
                                        session_id,
                                        client_frame_index,
                                        ws_cancel_frames,
                                    )
                                else:
                                    logger.debug(
                                        "[%s] WS client frame session_id=%s frame=%d type=%s",
                                        request_id,
                                        session_id,
                                        client_frame_index,
                                        ws_last_client_frame_type,
                                    )
                                capture_codex_wire_debug(
                                    "ws_inbound_client_frame",
                                    request_id=request_id,
                                    session_id=conversation_session_id,
                                    transport="websocket",
                                    direction="client_to_cutctx",
                                    url=_ws_url,
                                    body=_inbound_frame_body,
                                    raw_text=None if _inbound_frame_body is not None else msg,
                                    metadata={"frame": client_frame_index},
                                )
                                if (
                                    isinstance(_inbound_frame_body, dict)
                                    and _inbound_frame_body.get("type") == "response.create"
                                ):
                                    ws_response_create_frames += 1
                                (
                                    msg,
                                    _frame_modified,
                                    _frame_reason,
                                ) = await _maybe_compress_response_create_frame(
                                    msg,
                                    frame_index=client_frame_index,
                                )
                                if _frame_reason == "context_refused":
                                    return
                                _outbound_frame_body: Any = None
                                try:
                                    _outbound_frame_body = json.loads(msg)
                                except json.JSONDecodeError:
                                    _outbound_frame_body = None
                                capture_codex_wire_debug(
                                    "ws_upstream_client_frame",
                                    request_id=request_id,
                                    session_id=conversation_session_id,
                                    transport="websocket",
                                    direction="cutctx_to_upstream",
                                    url=upstream_url,
                                    body=_outbound_frame_body,
                                    raw_text=None if _outbound_frame_body is not None else msg,
                                    metadata={
                                        "frame": client_frame_index,
                                        "tokens_saved_total": tokens_saved,
                                        "transforms_applied": transforms_applied,
                                    },
                                )
                                await upstream.send(msg)
                        except asyncio.CancelledError:
                            # Explicit cancel from the outer
                            # orchestrator — re-raise so
                            # ``t.cancelled()`` and ``t.exception()``
                            # behave correctly in the caller.
                            raise
                        except Exception as relay_err:
                            # Surface real errors to the classifier
                            # without re-raising (existing fork
                            # behavior: log and return so the
                            # partner task can be cancelled
                            # deterministically).
                            if "WebSocketDisconnect" not in type(relay_err).__name__:
                                client_relay_error = relay_err
                                logger.debug(
                                    f"[{request_id}] WS client→upstream relay ended: {relay_err}"
                                )
                            else:
                                ws_client_disconnect_seen = True
                                logger.info(
                                    "[%s] WS client disconnected session_id=%s "
                                    "frames=%d cancels=%d last_type=%s",
                                    request_id,
                                    session_id,
                                    ws_client_frames_total,
                                    ws_cancel_frames,
                                    ws_last_client_frame_type,
                                )
                            with contextlib.suppress(Exception):
                                await upstream.close()

                    async def _upstream_to_client() -> None:
                        """Relay upstream→client with transparent memory tool handling.

                        Uses a buffer-then-decide approach:
                        1. Buffer events until first output item arrives
                        2. If first output is a memory tool → suppress entire response,
                           execute tools silently, send continuation upstream
                        3. If first output is non-memory → flush buffer, stream normally
                        4. Continuation response events are relayed to Codex seamlessly

                        This prevents orphaned response.created events from confusing Codex.
                        """
                        from cutctx.proxy.memory_handler import MEMORY_TOOL_NAMES

                        # Unit 3: surface response.completed observation
                        # to the outer scope so the termination-cause
                        # classifier can prefer ``response_completed``
                        # over ``upstream_disconnect``.
                        nonlocal response_completed_seen
                        nonlocal upstream_relay_error
                        nonlocal ws_input_tokens_total, ws_output_tokens_total
                        nonlocal ws_cache_read_tokens_total, ws_cache_write_tokens_total
                        nonlocal ws_uncached_input_tokens_total
                        nonlocal ws_recorded_input_tokens_total
                        nonlocal ws_recorded_output_tokens_total
                        nonlocal ws_recorded_cache_read_tokens_total
                        nonlocal ws_recorded_cache_write_tokens_total
                        nonlocal ws_recorded_uncached_input_tokens_total
                        nonlocal ws_recorded_tokens_saved_total
                        nonlocal ws_recorded_overhead_ms_total, ws_recorded_ttfb_ms
                        nonlocal ws_upstream_frames_total, ws_last_upstream_frame_type
                        nonlocal ws_ttfb_ms

                        memory_enabled = bool(self.memory_handler and memory_user_id)

                        # Per-response state (reset after each response.completed)
                        event_buffer: list[str] = []
                        decided = False
                        suppress_response = False
                        pending_fcs: list[dict[str, Any]] = []
                        resp_id: str | None = None

                        def _reset() -> None:
                            nonlocal decided, suppress_response, resp_id
                            event_buffer.clear()
                            decided = False
                            suppress_response = False
                            pending_fcs.clear()
                            resp_id = None

                        response_started_ms: float | None = None

                        async def _record_ws_response_metrics() -> None:
                            """Record one completed Responses turn on long-lived WS sessions."""
                            nonlocal ws_recorded_input_tokens_total
                            nonlocal ws_recorded_output_tokens_total
                            nonlocal ws_recorded_cache_read_tokens_total
                            nonlocal ws_recorded_cache_write_tokens_total
                            nonlocal ws_recorded_uncached_input_tokens_total
                            nonlocal ws_recorded_tokens_saved_total
                            nonlocal ws_recorded_attempted_input_tokens_total
                            nonlocal ws_recorded_overhead_ms_total, ws_recorded_ttfb_ms

                            input_delta = ws_input_tokens_total - ws_recorded_input_tokens_total
                            output_delta = ws_output_tokens_total - ws_recorded_output_tokens_total
                            cache_read_delta = (
                                ws_cache_read_tokens_total - ws_recorded_cache_read_tokens_total
                            )
                            cache_write_delta = (
                                ws_cache_write_tokens_total - ws_recorded_cache_write_tokens_total
                            )
                            uncached_delta = (
                                ws_uncached_input_tokens_total
                                - ws_recorded_uncached_input_tokens_total
                            )
                            saved_delta = tokens_saved - ws_recorded_tokens_saved_total
                            attempted_delta = (
                                attempted_input_tokens_total
                                - ws_recorded_attempted_input_tokens_total
                            )
                            (
                                overhead_delta_ms,
                                ttfb_for_record_ms,
                                dashboard_pipeline_timing,
                            ) = _prepare_ws_performance_metrics()
                            if (
                                input_delta <= 0
                                and output_delta <= 0
                                and cache_read_delta <= 0
                                and cache_write_delta <= 0
                                and uncached_delta <= 0
                                and saved_delta <= 0
                                and attempted_delta <= 0
                                and overhead_delta_ms <= 0
                                and ttfb_for_record_ms <= 0
                            ):
                                return

                            model_for_metrics = str(body.get("model") or "unknown")
                            latency_ms = (
                                (time.perf_counter() * 1000.0 - response_started_ms)
                                if response_started_ms is not None
                                else 0.0
                            )
                            # Per-turn record: delta values capture
                            # this turn's contribution since the
                            # Codex WS handler accumulates session
                            # totals. Pre-refactor this site
                            # emitted only metrics + cost_tracker
                            # — no RequestLog, no PERF — so Codex
                            # traffic was invisible to
                            # ``cutctx perf`` and the recent-
                            # requests feed. Funnel restores all
                            # four effects uniformly per turn. Per-
                            # turn outcomes carry ``ws_tags`` (the
                            # `x-cutctx-tag-*` headers extracted
                            # at the WS upgrade) so dashboards can
                            # slice WS turns by tag — same surface
                            # as HTTP turns.
                            await self._record_request_outcome(
                                RequestOutcome(
                                    request_id=request_id,
                                    provider=_provider_for_client(client),
                                    model=model_for_metrics,
                                    original_tokens=max(0, input_delta) + max(0, saved_delta),
                                    optimized_tokens=max(0, input_delta),
                                    output_tokens=max(0, output_delta),
                                    tokens_saved=max(0, saved_delta),
                                    attempted_input_tokens=max(0, attempted_delta),
                                    cache_read_tokens=max(0, cache_read_delta),
                                    cache_write_tokens=max(0, cache_write_delta),
                                    uncached_input_tokens=max(0, uncached_delta),
                                    total_latency_ms=latency_ms,
                                    overhead_ms=overhead_delta_ms,
                                    ttfb_ms=ttfb_for_record_ms,
                                    pipeline_timing=dashboard_pipeline_timing,
                                    transforms_applied=tuple(transforms_applied),
                                    num_messages=len(
                                        body.get("messages") or body.get("input") or []
                                    )
                                    if isinstance(body, dict)
                                    else 0,
                                    tags=ws_tags,
                                    savings_metadata=ws_savings_metadata,
                                    client=client,
                                )
                            )

                            # Structured PERF log line so ``cutctx perf``
                            # counts this Codex turn. Pre-P2 this emit was
                            # missing, which is why Codex traffic showed up
                            # as ``Requests: 0`` in the perf report even
                            # under heavy load — the same visibility bug
                            # class as #327's "Cache write: 0" report.
                            _perf_input_tokens = max(0, input_delta)
                            _perf_cache_read = max(0, cache_read_delta)
                            _perf_cache_write = max(0, cache_write_delta)
                            _perf_cache_hit_pct = (
                                round(
                                    _perf_cache_read / (_perf_cache_read + _perf_cache_write) * 100
                                )
                                if (_perf_cache_read + _perf_cache_write) > 0
                                else 0
                            )
                            _perf_tok_before = _perf_input_tokens + max(0, saved_delta)
                            _perf_num_msgs = (
                                len(body.get("messages") or body.get("input") or [])
                                if isinstance(body, dict)
                                else 0
                            )
                            logger.info(
                                f"[{request_id}] PERF "
                                f"model={model_for_metrics} msgs={_perf_num_msgs} "
                                f"tok_before={_perf_tok_before} "
                                f"tok_after={_perf_input_tokens} "
                                f"tok_saved={max(0, saved_delta)} "
                                f"cache_read={_perf_cache_read} "
                                f"cache_write={_perf_cache_write} "
                                f"cache_hit_pct={_perf_cache_hit_pct} "
                                f"opt_ms={overhead_delta_ms:.0f} "
                                f"transforms={_summarize_transforms(transforms_applied)}"
                            )

                            ws_recorded_input_tokens_total = ws_input_tokens_total
                            ws_recorded_output_tokens_total = ws_output_tokens_total
                            ws_recorded_cache_read_tokens_total = ws_cache_read_tokens_total
                            ws_recorded_cache_write_tokens_total = ws_cache_write_tokens_total
                            ws_recorded_uncached_input_tokens_total = ws_uncached_input_tokens_total
                            ws_recorded_tokens_saved_total = tokens_saved
                            ws_recorded_attempted_input_tokens_total = attempted_input_tokens_total
                            ws_recorded_overhead_ms_total = _current_ws_overhead_ms()
                            ws_recorded_compression_timing_totals.update(
                                ws_compression_timing_totals
                            )
                            if ttfb_for_record_ms > 0:
                                ws_recorded_ttfb_ms = True

                        # The retry-loop variable is safe to close over here:
                        # ``_upstream_to_client`` is defined and awaited within
                        # a single iteration and never escapes.
                        _first_event_started_at = _upstream_first_event_started  # noqa: B023

                        try:
                            upstream_frame_index = 0
                            async for msg in upstream:
                                upstream_frame_index += 1
                                ws_upstream_frames_total += 1
                                if session_handle is not None:
                                    session_handle.mark_activity()
                                if (
                                    _first_event_started_at is not None
                                    and "upstream_first_event" not in stage_timer
                                ):
                                    if ws_ttfb_ms is None:
                                        ws_ttfb_ms = (
                                            time.perf_counter() - session_started_at
                                        ) * 1000.0
                                    stage_timer.record(
                                        "upstream_first_event",
                                        (time.perf_counter() - _first_event_started_at) * 1000.0,
                                    )
                                if isinstance(msg, bytes):
                                    ws_last_upstream_frame_type = "binary"
                                    capture_codex_wire_debug(
                                        "ws_upstream_binary_frame",
                                        request_id=request_id,
                                        session_id=conversation_session_id,
                                        transport="websocket",
                                        direction="upstream_to_cutctx",
                                        url=upstream_url,
                                        metadata={
                                            "frame": upstream_frame_index,
                                            "byte_count": len(msg),
                                        },
                                    )
                                    await websocket.send_bytes(msg)
                                    continue
                                msg_str = msg if isinstance(msg, str) else str(msg)
                                _upstream_frame_body: Any = None
                                try:
                                    _upstream_frame_body = json.loads(msg_str)
                                except json.JSONDecodeError:
                                    _upstream_frame_body = None
                                capture_codex_wire_debug(
                                    "ws_upstream_text_frame",
                                    request_id=request_id,
                                    session_id=conversation_session_id,
                                    transport="websocket",
                                    direction="upstream_to_cutctx",
                                    url=upstream_url,
                                    body=_upstream_frame_body,
                                    raw_text=None if _upstream_frame_body is not None else msg_str,
                                    metadata={"frame": upstream_frame_index},
                                )

                                # Parse event
                                try:
                                    event = json.loads(msg_str)
                                except (json.JSONDecodeError, TypeError):
                                    ws_last_upstream_frame_type = "non_json"
                                    await websocket.send_text(msg_str)
                                    continue

                                event_type = event.get("type", "")
                                ws_last_upstream_frame_type = str(event_type or "unknown")
                                if event_type == "error":
                                    logger.warning(
                                        "[%s] WS upstream error session_id=%s frame=%d error=%s",
                                        request_id,
                                        session_id,
                                        upstream_frame_index,
                                        json.dumps(
                                            _summarize_upstream_ws_error(event),
                                            sort_keys=True,
                                        ),
                                    )
                                logger.debug(
                                    "[%s] WS upstream frame session_id=%s frame=%d type=%s",
                                    request_id,
                                    session_id,
                                    upstream_frame_index,
                                    ws_last_upstream_frame_type,
                                )
                                if event_type == "response.created":
                                    response_started_ms = time.perf_counter() * 1000.0
                                (
                                    usage_input_tokens,
                                    usage_output_tokens,
                                    usage_cache_read_tokens,
                                    usage_cache_write_tokens,
                                    usage_uncached_tokens,
                                ) = _extract_responses_usage(event)
                                if usage_input_tokens or usage_output_tokens:
                                    ws_input_tokens_total += usage_input_tokens
                                    ws_output_tokens_total += usage_output_tokens
                                    ws_cache_read_tokens_total += usage_cache_read_tokens
                                    ws_cache_write_tokens_total += usage_cache_write_tokens
                                    ws_uncached_input_tokens_total += usage_uncached_tokens

                                if not memory_enabled:
                                    if event_type == "response.completed":
                                        response_completed_seen = True
                                        await _record_ws_response_metrics()
                                    await websocket.send_text(
                                        _strip_namespace_from_upstream_event_text(msg_str)
                                    )
                                    continue

                                # --- Phase 1: Buffer until first output item ---
                                if not decided:
                                    event_buffer.append(msg_str)

                                    if event_type == "response.output_item.added":
                                        item = event.get("item", {})
                                        if (
                                            item.get("type") == "function_call"
                                            and item.get("name") in MEMORY_TOOL_NAMES
                                        ):
                                            # Memory tool first → suppress entire response
                                            suppress_response = True
                                            decided = True
                                            event_buffer.clear()
                                            logger.info(
                                                f"[{request_id}] WS Memory: Detected "
                                                f"{item.get('name')} — suppressing response"
                                            )
                                        else:
                                            # Non-memory first → flush buffer, pass through
                                            decided = True
                                            for buf in event_buffer:
                                                await websocket.send_text(
                                                    _strip_namespace_from_upstream_event_text(buf)
                                                )
                                            event_buffer.clear()

                                    elif event_type == "response.completed":
                                        # No output items at all — flush
                                        decided = True
                                for buf in event_buffer:
                                    await websocket.send_text(
                                        _strip_namespace_from_upstream_event_text(buf)
                                    )
                                event_buffer.clear()
                                await _record_ws_response_metrics()
                                _reset()
                                response_completed_seen = True

                                continue

                                # --- Phase 2a: Suppress mode (memory response) ---
                                if suppress_response:
                                    if event_type == "response.output_item.done":
                                        item = event.get("item", {})
                                        if (
                                            item.get("type") == "function_call"
                                            and item.get("name") in MEMORY_TOOL_NAMES
                                        ):
                                            pending_fcs.append(item)

                                    elif event_type == "response.completed":
                                        response_completed_seen = True
                                        await _record_ws_response_metrics()
                                        resp = event.get("response", {})
                                        resp_id = resp.get("id")

                                        if pending_fcs:
                                            logger.info(
                                                f"[{request_id}] WS Memory: Executing "
                                                f"{len(pending_fcs)} tool(s) transparently"
                                            )

                                            # Execute memory tool calls
                                            tool_outputs: list[dict[str, Any]] = []
                                            for fc in pending_fcs:
                                                call_id = fc.get("call_id", fc.get("id", ""))
                                                fc_name = fc.get("name", "")
                                                args_str = fc.get("arguments", "{}")
                                                try:
                                                    fc_args = json.loads(args_str)
                                                except json.JSONDecodeError:
                                                    fc_args = {}

                                                await self.memory_handler._ensure_initialized()
                                                if self.memory_handler._backend:
                                                    result = await self.memory_handler._execute_memory_tool(
                                                        fc_name,
                                                        fc_args,
                                                        memory_user_id,
                                                        "openai",
                                                    )
                                                else:
                                                    result = json.dumps(
                                                        {"error": "backend not ready"}
                                                    )

                                                tool_outputs.append(
                                                    {
                                                        "type": "function_call_output",
                                                        "call_id": call_id,
                                                        "output": result,
                                                    }
                                                )
                                                logger.info(
                                                    f"[{request_id}] WS Memory: Executed "
                                                    f"{fc_name} for user {memory_user_id}"
                                                )

                                            # Send continuation upstream
                                            cont: dict[str, Any] = {
                                                "type": "response.create",
                                                "response": {"input": tool_outputs},
                                            }
                                            if resp_id:
                                                cont["response"]["previous_response_id"] = resp_id
                                            await upstream.send(json.dumps(cont))
                                            logger.info(
                                                f"[{request_id}] WS Memory: Sent continuation "
                                                f"with {len(tool_outputs)} result(s)"
                                            )

                                        _reset()
                                    # All events suppressed in this mode
                                    continue

                                # --- Phase 2b: Pass-through mode ---
                                await websocket.send_text(
                                    _strip_namespace_from_upstream_event_text(msg_str)
                                )

                        except asyncio.CancelledError:
                            raise
                        except Exception as relay_err:
                            if "WebSocketDisconnect" not in type(relay_err).__name__:
                                # Capture for the outer classifier
                                # so ``upstream_error`` can be
                                # distinguished from a clean
                                # upstream disconnect.
                                upstream_relay_error = relay_err
                                logger.debug(
                                    f"[{request_id}] WS upstream→client relay ended: {relay_err}"
                                )
                        finally:
                            with contextlib.suppress(Exception):
                                await websocket.close()

                    # --- Unit 3: deterministic relay-task cancellation ---
                    # Spawn each half as a named task so we can:
                    #   (a) attach them to the session registry for
                    #       ``/debug/ws-sessions``,
                    #   (b) cancel the survivor explicitly when the
                    #       first one exits, and
                    #   (c) classify the termination cause for the
                    #       duration histogram.
                    client_task = asyncio.create_task(
                        _client_to_upstream(),
                        name=f"codex-ws-c2u-{session_id}",
                    )
                    upstream_task = asyncio.create_task(
                        _upstream_to_client(),
                        name=f"codex-ws-u2c-{session_id}",
                    )
                    relay_tasks = [client_task, upstream_task]
                    if ws_sessions is not None:
                        ws_sessions.attach_tasks(session_id, relay_tasks)
                        metrics_for_tasks = getattr(self, "metrics", None)
                        if metrics_for_tasks is not None and hasattr(
                            metrics_for_tasks, "inc_active_relay_tasks"
                        ):
                            try:
                                metrics_for_tasks.inc_active_relay_tasks(len(relay_tasks))
                            except Exception:  # pragma: no cover - defensive
                                pass

                    try:
                        done, pending = await asyncio.wait(
                            {client_task, upstream_task},
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        # Cancel the survivor so we don't leak the
                        # partner task. Suppress the CancelledError
                        # we just raised ourselves — any *other*
                        # exception from the cancelled task is
                        # already logged inside its own try/except.
                        for t in pending:
                            t.cancel()
                        if pending:
                            with contextlib.suppress(asyncio.CancelledError):
                                await asyncio.gather(*pending, return_exceptions=True)

                        # Classify termination cause from whichever
                        # task completed first. ``CancelledError``
                        # can show up on the "done" side if the
                        # handler itself was cancelled from outside
                        # (e.g. server shutdown).
                        for t in done:
                            exc = None
                            # Cancelled tasks raise CancelledError from
                            # .exception(); surface it explicitly so the
                            # downstream ``isinstance(exc, CancelledError)``
                            # branches actually run. For any other
                            # unexpected state (``InvalidStateError`` if
                            # the task somehow isn't done — shouldn't
                            # happen post-gather but defensive), we
                            # suppress and leave ``exc`` as ``None``.
                            if t.cancelled():
                                exc = asyncio.CancelledError()
                            else:
                                with contextlib.suppress(asyncio.InvalidStateError):
                                    exc = t.exception()
                            task_name = t.get_name() or ""
                            if t is client_task:
                                if client_relay_error is not None:
                                    termination_cause = "client_error"
                                elif exc is None:
                                    termination_cause = "client_disconnect"
                                elif isinstance(exc, asyncio.CancelledError):
                                    termination_cause = "client_disconnect"
                                else:
                                    # Distinguish legitimate client
                                    # disconnect exceptions from
                                    # real errors: WebSocketDisconnect
                                    # is a normal client exit.
                                    if "WebSocketDisconnect" in type(exc).__name__:
                                        termination_cause = "client_disconnect"
                                    else:
                                        termination_cause = "client_error"
                            elif t is upstream_task:
                                if upstream_relay_error is not None:
                                    termination_cause = "upstream_error"
                                    logger.debug(
                                        f"[{request_id}] WS relay {task_name} "
                                        f"raised: {upstream_relay_error!r}"
                                    )
                                elif exc is None:
                                    termination_cause = (
                                        "response_completed"
                                        if response_completed_seen
                                        else "upstream_disconnect"
                                    )
                                elif isinstance(exc, asyncio.CancelledError):
                                    termination_cause = "upstream_disconnect"
                                else:
                                    termination_cause = "upstream_error"
                                    logger.debug(
                                        f"[{request_id}] WS relay {task_name} raised: {exc!r}"
                                    )
                        if (
                            ws_cancel_frames > 0
                            and not response_completed_seen
                            and termination_cause
                            in {"upstream_disconnect", "client_disconnect", "unknown"}
                        ):
                            termination_cause = "client_cancel"
                    finally:
                        # In case anything above raised before the
                        # cancel-and-await loop ran.
                        for t in relay_tasks:
                            if not t.done():
                                t.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await asyncio.gather(*relay_tasks, return_exceptions=True)

                    logger.info(
                        "[%s] WS /v1/responses completed "
                        "(tokens_saved=%d, cause=%s, client_frames=%d, upstream_frames=%d, "
                        "cancel_frames=%d, client_disconnect=%s, last_client_type=%s, "
                        "last_upstream_type=%s)",
                        request_id,
                        tokens_saved,
                        termination_cause,
                        ws_client_frames_total,
                        ws_upstream_frames_total,
                        ws_cancel_frames,
                        ws_client_disconnect_seen,
                        ws_last_client_frame_type,
                        ws_last_upstream_frame_type,
                    )
                finally:
                    # Explicit cleanup for the upstream WS connection
                    # (replaces the async-with context manager that
                    # websockets 13.x no longer supports on an already-
                    # connected WebSocketClientProtocol).
                    with contextlib.suppress(Exception):
                        await upstream.close()
            else:
                # WS upgrade failed (HTTP 500 from OpenAI is common).
                # Fall back to HTTP POST streaming and relay SSE events
                # back over the client WebSocket transparently.
                ws_err = ws_last_err or RuntimeError("unknown websocket connect failure")
                _ws_detail = str(ws_err)
                if hasattr(ws_err, "response"):
                    resp_body = getattr(getattr(ws_err, "response", None), "body", b"")
                    if resp_body:
                        from cutctx.proxy.helpers import safe_decode_for_logging

                        _ws_detail += f" | {safe_decode_for_logging(resp_body, max_bytes=300)}"
                logger.warning(
                    f"[{request_id}] WS upstream failed ({_ws_detail}), "
                    f"falling back to HTTP POST streaming"
                )
                fallback_summary = await self._ws_http_fallback(
                    websocket,
                    body,
                    first_msg_raw,
                    upstream_headers,
                    request_id,
                    ws_tags=ws_tags,
                )
                ws_input_tokens_total += int(fallback_summary.get("input_tokens", 0) or 0)
                ws_output_tokens_total += int(fallback_summary.get("output_tokens", 0) or 0)
                ws_cache_read_tokens_total += int(fallback_summary.get("cache_read_tokens", 0) or 0)
                ws_cache_write_tokens_total += int(
                    fallback_summary.get("cache_write_tokens", 0) or 0
                )
                ws_uncached_input_tokens_total += int(
                    fallback_summary.get("uncached_input_tokens", 0) or 0
                )
                response_completed_seen = bool(fallback_summary.get("response_completed"))
                if fallback_summary.get("last_event_type"):
                    ws_last_upstream_frame_type = str(fallback_summary["last_event_type"])

            # ── WS session-end metric + RequestLog ──────────────────
            #
            # Unconditional (was previously gated on `tokens_saved>0`,
            # which made first-frame no-changes invisible). We record
            # one entry per WS session that aggregates `tokens_saved`
            # across every `response.create` frame compressed by the
            # first-frame block + `_maybe_compress_response_create_frame`.
            # The RequestLog entry mirrors the streaming.py /
            # anthropic.py shape so /transformations/feed surfaces
            # Codex WS turns.
            ws_session_duration_ms = (time.perf_counter() - session_started_at) * 1000.0
            ws_inner_for_telemetry: dict[str, Any] = (
                body.get("response", body) if isinstance(body, dict) else {}
            )
            if not isinstance(ws_inner_for_telemetry, dict):
                ws_inner_for_telemetry = {}
            model_name = (
                ws_inner_for_telemetry.get("model")
                or (body.get("model") if isinstance(body, dict) else None)
                or "unknown"
            )
            _final_auth_mode = classify_auth_mode(ws_headers)
            residual_input_tokens = max(0, ws_input_tokens_total - ws_recorded_input_tokens_total)
            residual_output_tokens = max(
                0, ws_output_tokens_total - ws_recorded_output_tokens_total
            )
            residual_cache_read_tokens = max(
                0, ws_cache_read_tokens_total - ws_recorded_cache_read_tokens_total
            )
            residual_cache_write_tokens = max(
                0, ws_cache_write_tokens_total - ws_recorded_cache_write_tokens_total
            )
            residual_uncached_input_tokens = max(
                0,
                ws_uncached_input_tokens_total - ws_recorded_uncached_input_tokens_total,
            )
            residual_tokens_saved = max(0, tokens_saved - ws_recorded_tokens_saved_total)
            residual_attempted_input_tokens = max(
                0,
                attempted_input_tokens_total - ws_recorded_attempted_input_tokens_total,
            )
            (
                final_overhead_delta_ms,
                final_ttfb_ms,
                final_pipeline_timing,
            ) = _prepare_ws_performance_metrics()
            ws_session_tags = {
                **(ws_tags or {}),
                "auth_mode": _final_auth_mode.value,
                "endpoint": "responses_ws",
                "compression_scope": "live_zone",
                "cache_policy": "prefix_safe",
                "transport": "websocket",
                "route": "chatgpt_subscription" if is_chatgpt_auth else "openai_api",
                "ws_response_create_frames": str(ws_response_create_frames),
                "ws_frames_compressed": str(ws_frames_compressed),
                "ws_client_frames_total": str(ws_client_frames_total),
                "ws_upstream_frames_total": str(ws_upstream_frames_total),
                "ws_cancel_frames": str(ws_cancel_frames),
                "ws_last_client_frame_type": ws_last_client_frame_type,
                "ws_last_upstream_frame_type": ws_last_upstream_frame_type,
                "ws_client_disconnect_seen": str(ws_client_disconnect_seen),
                "ws_termination_cause": termination_cause,
                "cache_read_tokens": str(ws_cache_read_tokens_total),
                "cache_write_tokens": str(ws_cache_write_tokens_total),
                "uncached_input_tokens": str(ws_uncached_input_tokens_total),
            }
            if (
                residual_input_tokens > 0
                or residual_output_tokens > 0
                or residual_tokens_saved > 0
                or residual_cache_read_tokens > 0
                or residual_cache_write_tokens > 0
                or residual_uncached_input_tokens > 0
                or residual_attempted_input_tokens > 0
                or final_overhead_delta_ms > 0
                or final_ttfb_ms > 0
            ):
                # Session-end residual: tokens not captured by any
                # per-turn record (e.g. signaling frames after the
                # last response.completed). The funnel emits the full
                # bookkeeping quartet for the residual; the explicit
                # session-summary RequestLog below remains a separate
                # entry (different semantics — cumulative session
                # totals vs delta residual).
                await self._record_request_outcome(
                    RequestOutcome(
                        request_id=request_id,
                        provider=_provider_for_client(client),
                        model=model_name,
                        original_tokens=residual_input_tokens + residual_tokens_saved,
                        optimized_tokens=residual_input_tokens,
                        output_tokens=residual_output_tokens,
                        tokens_saved=residual_tokens_saved,
                        attempted_input_tokens=residual_attempted_input_tokens,
                        cache_read_tokens=residual_cache_read_tokens,
                        cache_write_tokens=residual_cache_write_tokens,
                        uncached_input_tokens=residual_uncached_input_tokens,
                        total_latency_ms=ws_session_duration_ms,
                        overhead_ms=final_overhead_delta_ms,
                        ttfb_ms=final_ttfb_ms,
                        pipeline_timing=final_pipeline_timing,
                        transforms_applied=tuple(transforms_applied),
                        tags=ws_session_tags,
                        client=client,
                        savings_metadata=ws_savings_metadata,
                    )
                )
                ws_recorded_overhead_ms_total = _current_ws_overhead_ms()
                if final_ttfb_ms > 0:
                    ws_recorded_ttfb_ms = True
            if getattr(self, "logger", None) is not None:
                from cutctx.proxy.helpers import compute_turn_id
                from cutctx.proxy.models import RequestLog

                ws_messages_for_log: list[dict[str, Any]] = []
                ws_input_for_log = ws_inner_for_telemetry.get("input")
                ws_instructions_for_log = ws_inner_for_telemetry.get("instructions")
                if isinstance(ws_instructions_for_log, str) and ws_instructions_for_log:
                    ws_messages_for_log.append(
                        {"role": "system", "content": ws_instructions_for_log}
                    )
                if isinstance(ws_input_for_log, str) and ws_input_for_log:
                    ws_messages_for_log.append({"role": "user", "content": ws_input_for_log})
                self.logger.log(
                    RequestLog(
                        request_id=request_id,
                        timestamp=datetime.now().isoformat(),
                        provider="openai",
                        model=model_name,
                        input_tokens_original=ws_input_tokens_total + tokens_saved,
                        input_tokens_optimized=ws_input_tokens_total,
                        output_tokens=ws_output_tokens_total,
                        tokens_saved=tokens_saved,
                        savings_percent=(
                            tokens_saved / (ws_input_tokens_total + tokens_saved) * 100
                        )
                        if ws_input_tokens_total + tokens_saved > 0
                        else 0.0,
                        optimization_latency_ms=_current_ws_overhead_ms(),
                        total_latency_ms=ws_session_duration_ms,
                        tags=ws_session_tags,
                        cache_hit=False,
                        transforms_applied=transforms_applied,
                        request_messages=ws_messages_for_log
                        if getattr(self.config, "log_full_messages", False)
                        else None,
                        turn_id=compute_turn_id(
                            model_name,
                            ws_instructions_for_log,
                            ws_messages_for_log,
                        ),
                    )
                )

        except Exception as e:
            if "WebSocketDisconnect" in type(e).__name__:
                # Unit 3: client dropped the socket before or during
                # relay. The registry classifier may already have set
                # ``client_disconnect`` via the relay task exit path;
                # preserve that, otherwise set it here.
                if termination_cause == "unknown":
                    termination_cause = "client_disconnect"
            else:
                # Extract response body from websockets InvalidStatus for better debugging
                error_detail = str(e)
                if hasattr(e, "response"):
                    try:
                        resp = e.response
                        body_bytes = getattr(resp, "body", None) or b""
                        if body_bytes:
                            from cutctx.proxy.helpers import safe_decode_for_logging

                            error_detail += (
                                f" | body: {safe_decode_for_logging(body_bytes, max_bytes=500)}"
                            )
                    except Exception:
                        pass
                logger.error(f"[{request_id}] WS proxy error: {error_detail}")
                if termination_cause == "unknown":
                    termination_cause = "client_error"
            with contextlib.suppress(Exception):
                await websocket.close(code=1011, reason="Internal server error")
        finally:
            # Unit 2: emit structured per-session stage timings.
            stage_timer.record(
                "total_session",
                (time.perf_counter() - session_started_at) * 1000.0,
            )
            # Close the upstream WS on early-return paths (e.g. first-frame
            # timeout after we connected). The relay path closes it via
            # `async with upstream`; this idempotent backstop covers the rest.
            with contextlib.suppress(Exception):
                if upstream is not None:
                    await upstream.close()
            # Unit 3: deregister the session before (or independently
            # of) the stage-timings log so a failure there cannot leak
            # the registry entry. ``deregister`` is idempotent, so a
            # session that never registered is a no-op.
            if ws_sessions is not None and session_handle is not None:
                # Use deregister_and_count so the handle pop and the
                # relay-task count are read atomically inside the
                # registry. Capturing ``len(session_handle.relay_tasks)``
                # separately before ``deregister`` would risk drift if
                # the registry's bookkeeping ever changes.
                _deregistered, released_tasks = ws_sessions.deregister_and_count(
                    session_id, cause=termination_cause
                )
                session_duration_ms = (time.perf_counter() - session_started_at) * 1000.0
                metrics_for_close = getattr(self, "metrics", None)
                if metrics_for_close is not None:
                    with contextlib.suppress(Exception):
                        if hasattr(metrics_for_close, "dec_active_ws_sessions"):
                            metrics_for_close.dec_active_ws_sessions()
                        if released_tasks and hasattr(metrics_for_close, "dec_active_relay_tasks"):
                            metrics_for_close.dec_active_relay_tasks(released_tasks)
                        if hasattr(metrics_for_close, "record_ws_session_duration"):
                            metrics_for_close.record_ws_session_duration(
                                session_duration_ms, termination_cause
                            )
            metrics_for_ws_inbound_close = getattr(self, "metrics", None)
            if metrics_for_ws_inbound_close is not None and hasattr(
                metrics_for_ws_inbound_close, "record_inbound_response"
            ):
                with contextlib.suppress(Exception):
                    metrics_for_ws_inbound_close.record_inbound_response(
                        status_code=f"ws:{termination_cause}"
                    )
            logger.info(
                "event=proxy_inbound_websocket_closed request_id=%s session_id=%s "
                "path=%s cause=%s duration_ms=%.2f",
                request_id,
                session_id,
                _ws_path,
                termination_cause,
                (time.perf_counter() - session_started_at) * 1000.0,
            )
            await emit_stage_timings_log(
                path="openai_responses_ws",
                request_id=request_id,
                session_id=conversation_session_id,
                stage_timer=stage_timer,
                expected_stages=(
                    "accept",
                    "first_client_frame",
                    "upstream_connect",
                    "upstream_first_event",
                    "memory_context",
                    "compression",
                    "total_session",
                ),
                metrics=getattr(self, "metrics", None),
            )

    async def _ws_http_fallback(
        self,
        websocket: WebSocket,
        body: dict[str, Any],
        first_msg_raw: str,
        upstream_headers: dict[str, str],
        request_id: str,
        *,
        ws_tags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Fall back to HTTP POST streaming when upstream WS fails.

        Converts the WS ``response.create`` message to an HTTP POST to
        ``/v1/responses?stream=true``, reads SSE events, and relays each
        ``data:`` line as a WS text message to the client.  This makes
        Codex work immediately instead of exhausting its WS retry budget.
        """
        fallback_summary: dict[str, Any] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "uncached_input_tokens": 0,
            "response_completed": False,
            "last_event_type": "",
        }

        try:
            parsed = json.loads(first_msg_raw) if isinstance(first_msg_raw, str) else body
        except (json.JSONDecodeError, TypeError):
            parsed = body

        fallback_provider = getattr(self.config, "fallback_provider", None)
        fallback_backend = getattr(self, "fallback_backend", None) or getattr(
            self, "openai_fallback_backend", None
        )
        use_configured_backend = bool(
            getattr(self.config, "fallback_enabled", False)
            and fallback_provider
            and fallback_provider != "openai"
            and fallback_backend is not None
        )

        if ws_tags is not None and use_configured_backend:
            ws_tags["fallback_provider"] = str(fallback_provider)
            ws_tags["fallback_attempted"] = "true"
            ws_tags["fallback_reason"] = "connect_error"
            ws_tags["fallback_source_provider"] = "openai"
            ws_tags["upstream_provider"] = str(fallback_provider)

        # Normalize WebSocket response.create payload into the HTTP request body.
        http_body, _ = _normalize_ws_http_fallback_body(parsed, body)

        if use_configured_backend:
            response_id = f"resp_{uuid.uuid4().hex[:24]}"
            item_id = f"msg_{uuid.uuid4().hex[:24]}"
            output_index = 0
            content_index = 0
            accumulated_text: list[str] = []
            created_sent = False
            item_added_sent = False

            async def _send_event(event: dict[str, Any]) -> bool:
                fallback_summary["last_event_type"] = str(event.get("type") or "")
                try:
                    await websocket.send_text(json.dumps(event))
                    return True
                except Exception:
                    return False

            async def _ensure_response_created() -> bool:
                nonlocal created_sent
                if created_sent:
                    return True
                created_sent = await _send_event(
                    {
                        "type": "response.created",
                        "response": {
                            "id": response_id,
                            "object": "response",
                            "model": http_body.get("model"),
                            "status": "in_progress",
                        },
                    }
                )
                return created_sent

            async def _ensure_output_item_added() -> bool:
                nonlocal item_added_sent
                if item_added_sent:
                    return True
                if not await _ensure_response_created():
                    return False
                item_added_sent = await _send_event(
                    {
                        "type": "response.output_item.added",
                        "output_index": output_index,
                        "item": {
                            "id": item_id,
                            "type": "message",
                            "status": "in_progress",
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "",
                                    "annotations": [],
                                }
                            ],
                        },
                    }
                )
                return item_added_sent

            chat_body = _responses_payload_to_chat_completions_body(http_body)
            chat_body["stream"] = True
            stream_options = chat_body.get("stream_options")
            if not isinstance(stream_options, dict):
                stream_options = {}
            stream_options["include_usage"] = True
            chat_body["stream_options"] = stream_options

            logger.info(
                "[%s] WS fallback routing Responses transport through %s backend",
                request_id,
                fallback_provider,
            )

            try:
                async for sse_chunk in fallback_backend.stream_openai_message(
                    chat_body,
                    dict(upstream_headers),
                ):
                    if not isinstance(sse_chunk, str):
                        continue
                    for line in sse_chunk.splitlines():
                        line = line.strip()
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data == "[DONE]":
                            continue
                        try:
                            chunk_event = json.loads(data)
                        except (json.JSONDecodeError, TypeError, ValueError):
                            continue
                        if not isinstance(chunk_event, dict):
                            continue

                        usage_payload = chunk_event.get("usage")
                        if isinstance(usage_payload, dict):
                            usage = _openai_chat_usage_to_responses_usage(usage_payload)
                            fallback_summary["input_tokens"] = _usage_int(usage.get("input_tokens"))
                            fallback_summary["output_tokens"] = _usage_int(
                                usage.get("output_tokens")
                            )
                            details = usage.get("input_tokens_details")
                            if isinstance(details, dict):
                                fallback_summary["cache_read_tokens"] = _usage_int(
                                    details.get("cached_tokens")
                                )
                            fallback_summary["cache_write_tokens"] = (
                                _infer_openai_cache_write_tokens(
                                    fallback_summary["input_tokens"],
                                    fallback_summary["cache_read_tokens"],
                                )
                            )
                            fallback_summary["uncached_input_tokens"] = max(
                                0,
                                fallback_summary["input_tokens"]
                                - fallback_summary["cache_read_tokens"],
                            )

                        choices = chunk_event.get("choices")
                        if not isinstance(choices, list) or not choices:
                            continue
                        choice0 = choices[0]
                        if not isinstance(choice0, dict):
                            continue
                        delta = choice0.get("delta")
                        if isinstance(delta, dict):
                            content = delta.get("content")
                            if isinstance(content, str) and content:
                                accumulated_text.append(content)
                                if not await _ensure_output_item_added():
                                    return fallback_summary
                                if not await _send_event(
                                    {
                                        "type": "response.output_text.delta",
                                        "item_id": item_id,
                                        "output_index": output_index,
                                        "content_index": content_index,
                                        "delta": content,
                                    }
                                ):
                                    return fallback_summary

                        finish_reason = choice0.get("finish_reason")
                        if finish_reason and finish_reason != "null":
                            if not await _ensure_response_created():
                                return fallback_summary
                            response_payload = {
                                "id": response_id,
                                "object": "response",
                                "model": http_body.get("model"),
                                "status": "completed",
                                "output": [
                                    {
                                        "type": "message",
                                        "id": item_id,
                                        "status": "completed",
                                        "role": "assistant",
                                        "content": [
                                            {
                                                "type": "output_text",
                                                "text": "".join(accumulated_text),
                                                "annotations": [],
                                            }
                                        ],
                                    }
                                ],
                            }
                            response_payload["usage"] = {
                                "input_tokens": fallback_summary["input_tokens"],
                                "input_tokens_details": {
                                    "cached_tokens": fallback_summary["cache_read_tokens"]
                                },
                                "output_tokens": fallback_summary["output_tokens"],
                                "total_tokens": (
                                    fallback_summary["input_tokens"]
                                    + fallback_summary["output_tokens"]
                                ),
                            }
                            fallback_summary["response_completed"] = True
                            await _send_event(
                                {"type": "response.completed", "response": response_payload}
                            )
                            return fallback_summary
            except Exception as backend_err:
                logger.error(
                    "[%s] WS fallback via %s backend failed: %s",
                    request_id,
                    fallback_provider,
                    backend_err,
                )
                error_event = {
                    "type": "error",
                    "error": {
                        "type": "server_error",
                        "message": f"Fallback backend failed: {backend_err!s}"[:200],
                    },
                }
                with contextlib.suppress(Exception):
                    await websocket.send_text(json.dumps(error_event))
                return fallback_summary
            finally:
                with contextlib.suppress(Exception):
                    await websocket.close()

            return fallback_summary

        # Route to correct endpoint based on auth mode
        _lower = {k.lower() for k in upstream_headers}
        if "chatgpt-account-id" in _lower:
            http_url = "https://chatgpt.com/backend-api/codex/responses"
        else:
            http_url = build_copilot_upstream_url(self.OPENAI_API_URL, "/v1/responses")

        # For chatgpt.com, strip unsupported fields (stream, client_metadata, etc.)
        # and apply emergency truncation if the body exceeds the size limit.
        # For api.openai.com, enable streaming as normal.
        _is_chatgpt_fallback = "chatgpt.com" in http_url
        if _is_chatgpt_fallback:
            http_body, _stripped = _sanitize_chatgpt_subscription_responses_body(http_body)
            if _stripped:
                logger.info(
                    "[%s] WS→HTTP fallback stripped chatgpt subscription fields: %s",
                    request_id,
                    ", ".join(_stripped),
                )
            _fb_body_bytes = len(json.dumps(http_body).encode("utf-8", errors="replace"))
            _CHATGPT_FALLBACK_MAX = 900 * 1024
            if _fb_body_bytes > _CHATGPT_FALLBACK_MAX:
                logger.warning(
                    "[%s] WS→HTTP fallback body too large for chatgpt.com (%d bytes) — truncating",
                    request_id,
                    _fb_body_bytes,
                )
                http_body = _truncate_body_for_chatgpt(http_body, _CHATGPT_FALLBACK_MAX, request_id)
        else:
            # Ensure streaming is enabled for api.openai.com
            http_body["stream"] = True

        # Build HTTP headers from the upstream headers (already stripped of WS
        # hop-by-hop headers by the caller).
        http_headers = dict(upstream_headers)
        http_headers["content-type"] = "application/json"

        # Byte-faithful re-serialization (PR-A3, fixes P0-2). The WS payload
        # is always synthesized from the WebSocket frame so the body is
        # treated as mutated; we still go through the canonical path so
        # numeric precision and UTF-8 are preserved.
        from cutctx.proxy.helpers import (
            log_outbound_request,
            prepare_outbound_body_bytes,
        )

        outbound_bytes, outbound_source = prepare_outbound_body_bytes(
            body=http_body,
            original_body_bytes=None,
            body_mutated=True,
        )
        log_outbound_request(
            forwarder="openai_ws",
            method="POST",
            path=http_url,
            body_bytes_count=len(outbound_bytes),
            body_mutated=True,
            mutation_reasons=["ws_http_fallback_resynthesized"],
            request_id=request_id,
            source=outbound_source,
        )

        logger.debug(f"[{request_id}] WS→HTTP fallback POST to {http_url}")

        try:
            retry_attempts = max(1, getattr(self.config, "retry_max_attempts", 3))
            for http_attempt in range(retry_attempts):
                try:
                    async with self.http_client.stream(
                        "POST",
                        http_url,
                        headers=http_headers,
                        content=outbound_bytes,
                        timeout=120.0,
                    ) as response:
                        if response.status_code != 200:
                            error_body = b""
                            async for chunk in response.aiter_bytes():
                                error_body += chunk
                                if len(error_body) > 2000:
                                    break
                            from cutctx.proxy.helpers import safe_decode_for_logging

                            error_text = safe_decode_for_logging(error_body)
                            logger.error(
                                f"[{request_id}] WS→HTTP fallback got {response.status_code}: "
                                f"{error_text[:500]}"
                            )
                            # Send error as WS message so client sees it
                            error_event = {
                                "type": "error",
                                "error": {
                                    "type": "server_error",
                                    "message": f"Upstream returned {response.status_code}",
                                },
                            }
                            await websocket.send_text(json.dumps(error_event))
                            return

                        # Refresh Codex /stats from the fallback response
                        # headers. We can't forward them onto the client 101
                        # (already accepted headerless on this arm), but /stats
                        # parity is still worth keeping on a WS->HTTP fallback.
                        with contextlib.suppress(Exception):
                            from cutctx.subscription.codex_rate_limits import (
                                get_codex_rate_limit_state,
                            )

                            get_codex_rate_limit_state().update_from_headers(dict(response.headers))

                        # Relay SSE events as WS text messages
                        buffer = ""
                        async for chunk in response.aiter_text():
                            buffer += chunk
                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                line = line.strip()
                                if not line:
                                    continue
                                if line.startswith("data: "):
                                    data = line[6:]
                                    if data == "[DONE]":
                                        continue
                                    try:
                                        await websocket.send_text(data)
                                    except Exception:
                                        return fallback_summary
                                    try:
                                        parsed_event = json.loads(data)
                                    except (json.JSONDecodeError, TypeError, ValueError):
                                        parsed_event = None
                                    if isinstance(parsed_event, dict):
                                        fallback_summary["last_event_type"] = str(
                                            parsed_event.get("type") or ""
                                        )
                                        if parsed_event.get("type") == "response.completed":
                                            fallback_summary["response_completed"] = True
                                        (
                                            fallback_summary["input_tokens"],
                                            fallback_summary["output_tokens"],
                                            fallback_summary["cache_read_tokens"],
                                            fallback_summary["cache_write_tokens"],
                                            fallback_summary["uncached_input_tokens"],
                                        ) = _extract_responses_usage(parsed_event)
                                elif line.startswith("event: "):
                                    # SSE event type — skip, the data line contains the type
                                    continue

                        # Flush any remaining data in buffer
                        for line in buffer.strip().splitlines():
                            line = line.strip()
                            if line.startswith("data: ") and line[6:] != "[DONE]":
                                with contextlib.suppress(Exception):
                                    await websocket.send_text(line[6:])
                                try:
                                    parsed_event = json.loads(line[6:])
                                except (json.JSONDecodeError, TypeError, ValueError):
                                    parsed_event = None
                                if isinstance(parsed_event, dict):
                                    fallback_summary["last_event_type"] = str(
                                        parsed_event.get("type") or ""
                                    )
                                    if parsed_event.get("type") == "response.completed":
                                        fallback_summary["response_completed"] = True
                                    (
                                        fallback_summary["input_tokens"],
                                        fallback_summary["output_tokens"],
                                        fallback_summary["cache_read_tokens"],
                                        fallback_summary["cache_write_tokens"],
                                        fallback_summary["uncached_input_tokens"],
                                    ) = _extract_responses_usage(parsed_event)
                        return fallback_summary
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as http_err:
                    if http_attempt >= retry_attempts - 1:
                        raise

                    delay_with_jitter = jitter_delay_ms(
                        self.config.retry_base_delay_ms,
                        self.config.retry_max_delay_ms,
                        http_attempt,
                    )
                    logger.warning(
                        f"[{request_id}] WS→HTTP fallback connect failed "
                        f"(attempt {http_attempt + 1}/{retry_attempts}): {http_err}; "
                        f"retrying in {delay_with_jitter:.0f}ms"
                    )
                    await asyncio.sleep(delay_with_jitter / 1000)

        except Exception as http_err:
            logger.error(f"[{request_id}] WS→HTTP fallback failed: {http_err}")
            error_event = {
                "type": "error",
                "error": {
                    "type": "server_error",
                    "message": f"HTTP fallback failed: {http_err!s}"[:200],
                },
            }
            with contextlib.suppress(Exception):
                await websocket.send_text(json.dumps(error_event))
        finally:
            with contextlib.suppress(Exception):
                await websocket.close()
        return fallback_summary
