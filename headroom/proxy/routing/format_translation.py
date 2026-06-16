# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Headroom Labs.
"""Format translation between Anthropic and OpenAI message/response schemas.

Provides:
  - ``anthropic_to_openai``: convert a messages list from Anthropic → OpenAI format
  - ``openai_to_anthropic``: convert a messages list from OpenAI → Anthropic format
  - ``translate_response``: cross-translate a provider response dict
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("headroom.proxy.routing.format_translation")


# ---------------------------------------------------------------------------
# Message-list converters
# ---------------------------------------------------------------------------


def anthropic_to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert an Anthropic API ``messages`` list to the OpenAI format.

    Anthropic format (list content blocks)::

        [{"role": "user",
          "content": [{"type": "text", "text": "Hello"},
                      {"type": "image",
                       "source": {"type": "base64",
                                  "media_type": "image/png",
                                  "data": "<b64>"}}]}]

    OpenAI format (flat string or vision array)::

        [{"role": "user", "content": "Hello"}]
        # or for multimodal:
        [{"role": "user", "content": [{"type": "text", "text": "…"},
                                       {"type": "image_url",
                                        "image_url": {"url": "data:image/png;base64,…"}}]}]

    Tool-use and tool-result blocks are also translated:
      - Anthropic ``tool_use`` block  → OpenAI ``tool_calls`` on the assistant message
      - Anthropic ``tool_result``     → OpenAI ``tool`` role message
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # ── String shorthand (already flat) ───────────────────────────────
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        # ── List of content blocks ─────────────────────────────────────────
        if not isinstance(content, list):
            out.append({"role": role, "content": str(content)})
            continue

        text_parts: list[str] = []
        oai_parts: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        tool_results: list[dict[str, Any]] = []

        for block in content:
            btype = block.get("type", "")

            if btype == "text":
                text = block.get("text", "")
                text_parts.append(text)
                oai_parts.append({"type": "text", "text": text})

            elif btype == "image":
                source = block.get("source", {})
                stype = source.get("type", "")
                if stype == "base64":
                    media_type = source.get("media_type", "image/jpeg")
                    data = source.get("data", "")
                    url = f"data:{media_type};base64,{data}"
                elif stype == "url":
                    url = source.get("url", "")
                else:
                    logger.warning("event=unknown_image_source_type type=%s; skipping block", stype)
                    continue
                oai_parts.append({"type": "image_url", "image_url": {"url": url}})

            elif btype == "tool_use":
                import json as _json

                tool_calls.append(
                    {
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": _json.dumps(block.get("input", {})),
                        },
                    }
                )

            elif btype == "tool_result":
                import json as _json

                tr_content = block.get("content", "")
                if isinstance(tr_content, list):
                    tr_text = " ".join(
                        b.get("text", "") for b in tr_content if b.get("type") == "text"
                    )
                else:
                    tr_text = str(tr_content)
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": tr_text,
                    }
                )

            else:
                logger.debug("event=unknown_content_block type=%s; skipping", btype)

        # ── Emit tool-result messages first (they logically precede the assistant
        # response in the OpenAI history ordering)
        out.extend(tool_results)

        # ── Build the main message ─────────────────────────────────────────
        if tool_calls:
            msg_out: dict[str, Any] = {"role": role}
            # If there's also text, surface it as content; otherwise omit.
            if text_parts:
                msg_out["content"] = " ".join(text_parts) if len(text_parts) == 1 else oai_parts
            else:
                msg_out["content"] = None
            msg_out["tool_calls"] = tool_calls
            out.append(msg_out)
        elif len(oai_parts) == 1 and oai_parts[0].get("type") == "text":
            # Simplest case: single text block → flat string
            out.append({"role": role, "content": oai_parts[0]["text"]})
        elif oai_parts:
            out.append({"role": role, "content": oai_parts})
        else:
            # Empty content list → empty string for compatibility
            out.append({"role": role, "content": ""})

    return out


def openai_to_anthropic(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert an OpenAI API ``messages`` list to the Anthropic format.

    OpenAI format::

        [{"role": "user", "content": "Hello"},
         {"role": "assistant", "content": null,
          "tool_calls": [{"id": "c1", "type": "function",
                          "function": {"name": "…", "arguments": "{}"}}]},
         {"role": "tool", "tool_call_id": "c1", "content": "result"}]

    Anthropic format::

        [{"role": "user",
          "content": [{"type": "text", "text": "Hello"}]},
         {"role": "assistant",
          "content": [{"type": "tool_use", "id": "c1", "name": "…", "input": {}}]},
         {"role": "user",
          "content": [{"type": "tool_result", "tool_use_id": "c1",
                       "content": [{"type": "text", "text": "result"}]}]}]
    """
    import json as _json

    out: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []

        # ── ``tool`` role → Anthropic ``tool_result`` block in a ``user`` turn ──
        if role == "tool":
            tool_use_id = msg.get("tool_call_id", "")
            result_text = content if isinstance(content, str) else _json.dumps(content)
            # Anthropic expects tool_result inside a user message
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": [{"type": "text", "text": result_text}],
                        }
                    ],
                }
            )
            continue

        blocks: list[dict[str, Any]] = []

        # ── Text / multimodal content ──────────────────────────────────────
        if isinstance(content, str) and content:
            blocks.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for part in content:
                ptype = part.get("type", "")
                if ptype == "text":
                    blocks.append({"type": "text", "text": part.get("text", "")})
                elif ptype == "image_url":
                    image_url = part.get("image_url", {})
                    url = (
                        image_url.get("url", "") if isinstance(image_url, dict) else str(image_url)
                    )
                    if url.startswith("data:"):
                        # data:<media_type>;base64,<data>
                        try:
                            header, b64data = url.split(",", 1)
                            media_type = header.split(":")[1].split(";")[0]
                        except (ValueError, IndexError):
                            media_type = "image/jpeg"
                            b64data = ""
                        blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": b64data,
                                },
                            }
                        )
                    else:
                        blocks.append(
                            {
                                "type": "image",
                                "source": {"type": "url", "url": url},
                            }
                        )

        # ── tool_calls → tool_use blocks ──────────────────────────────────
        for tc in tool_calls:
            fn = tc.get("function", {})
            raw_args = fn.get("arguments", "{}")
            try:
                parsed_input = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except _json.JSONDecodeError:
                parsed_input = {"_raw": raw_args}
            blocks.append(
                {
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "input": parsed_input,
                }
            )

        # ── Emit ──────────────────────────────────────────────────────────
        if blocks:
            out.append({"role": role, "content": blocks})
        else:
            # system messages and empty turns: pass through as text block
            out.append({"role": role, "content": [{"type": "text", "text": ""}]})

    return out


# ---------------------------------------------------------------------------
# Response translators
# ---------------------------------------------------------------------------

_STOP_REASON_ANTHROPIC_TO_OAI: dict[str, str] = {
    "end_turn": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "stop_sequence": "stop",
}

_STOP_REASON_OAI_TO_ANTHROPIC: dict[str, str] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "function_call": "tool_use",
    "content_filter": "end_turn",
}


def translate_response(
    response: dict[str, Any],
    from_provider: str,
    to_provider: str,
) -> dict[str, Any]:
    """Translate a provider response dict from one format to another.

    Supported translations:
      - ``'anthropic'`` → ``'openai'``
      - ``'openai'`` → ``'anthropic'``

    Preserved fields: tool_calls/tool_use, stop_reason/finish_reason, usage.
    Unknown (from_provider, to_provider) pairs return the response unchanged
    with a warning.
    """
    key = (from_provider.lower(), to_provider.lower())
    if key == ("anthropic", "openai"):
        return _anthropic_response_to_openai(response)
    if key == ("openai", "anthropic"):
        return _openai_response_to_anthropic(response)
    if from_provider == to_provider:
        return response
    logger.warning(
        "event=unsupported_translation from=%s to=%s; returning original",
        from_provider,
        to_provider,
    )
    return response


def _anthropic_response_to_openai(resp: dict[str, Any]) -> dict[str, Any]:
    """Internal: Anthropic Messages API response → OpenAI Chat Completions shape."""
    import json as _json

    content_blocks: list[dict[str, Any]] = resp.get("content", [])
    stop_reason = resp.get("stop_reason", "end_turn")
    usage = resp.get("usage", {})

    # Build choices[0]
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for block in content_blocks:
        btype = block.get("type", "")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": _json.dumps(block.get("input", {})),
                    },
                }
            )

    message: dict[str, Any] = {"role": "assistant"}
    if text_parts:
        message["content"] = "".join(text_parts)
    else:
        message["content"] = None
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason = _STOP_REASON_ANTHROPIC_TO_OAI.get(stop_reason, "stop")

    oai_usage = {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
    }

    return {
        "id": resp.get("id", ""),
        "object": "chat.completion",
        "created": 0,
        "model": resp.get("model", ""),
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": oai_usage,
    }


def _openai_response_to_anthropic(resp: dict[str, Any]) -> dict[str, Any]:
    """Internal: OpenAI Chat Completions response → Anthropic Messages API shape."""
    import json as _json

    choices = resp.get("choices", [])
    first_choice = choices[0] if choices else {}
    message = first_choice.get("message", {})
    finish_reason = first_choice.get("finish_reason", "stop")
    usage = resp.get("usage", {})

    content_blocks: list[dict[str, Any]] = []

    # Text content
    text = message.get("content")
    if text:
        content_blocks.append({"type": "text", "text": text})

    # Tool calls
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function", {})
        raw_args = fn.get("arguments", "{}")
        try:
            parsed = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except _json.JSONDecodeError:
            parsed = {"_raw": raw_args}
        content_blocks.append(
            {
                "type": "tool_use",
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "input": parsed,
            }
        )

    stop_reason = _STOP_REASON_OAI_TO_ANTHROPIC.get(finish_reason or "stop", "end_turn")

    anthropic_usage = {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }

    return {
        "id": resp.get("id", ""),
        "type": "message",
        "role": "assistant",
        "model": resp.get("model", ""),
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": anthropic_usage,
    }
