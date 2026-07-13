"""Streaming handler mixin for CutctxProxy.

Contains SSE parsing, streaming response generation, and related utilities.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any

from cutctx.proxy.auth_mode import classify_client
from cutctx.proxy.helpers import jitter_delay_ms

if TYPE_CHECKING:
    from fastapi.responses import Response, StreamingResponse


import httpx

from cutctx.copilot_auth import apply_copilot_api_auth

logger = logging.getLogger("cutctx.proxy")


def _parse_completion_tokens_from_sse_chunk(chunk_bytes: bytes) -> int | None:
    """Extract `usage.completion_tokens` from a single SSE chunk if present.

    Returns the integer count when the chunk carries a usage frame (LiteLLM
    emits this only when the request included
    ``stream_options.include_usage=true``), or None when no usage data is
    present (the typical content-only chunk path) or when the chunk fails
    to parse. Used by the OpenAI-via-backend stream path to track
    completion tokens online instead of buffering the entire response.
    """
    try:
        decoded = chunk_bytes.decode("utf-8", errors="replace")
    except (UnicodeDecodeError, AttributeError):
        return None
    for line in decoded.split("\n"):
        line = line.strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        try:
            data = json.loads(line[6:])
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        chunk_usage = data.get("usage")
        if isinstance(chunk_usage, dict):
            return int(chunk_usage.get("completion_tokens", 0) or 0)
    return None


def _iter_openai_sse_json_events(chunk_bytes: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        decoded = chunk_bytes.decode("utf-8", errors="replace")
    except (UnicodeDecodeError, AttributeError):
        return events
    for line in decoded.split("\n"):
        line = line.strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        try:
            parsed = json.loads(line[6:])
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


class StreamingMixin:
    """Mixin providing streaming response methods for CutctxProxy."""

    @staticmethod
    def _classify_streaming_fallback_reason(exc: Exception | None) -> str:
        if isinstance(exc, httpx.ConnectError):
            return "connect_error"
        if isinstance(exc, httpx.TimeoutException):
            return "timeout"
        if isinstance(exc, httpx.HTTPStatusError):
            return "upstream_5xx"
        if exc is None:
            return "unknown"
        return type(exc).__name__.lower()

    @staticmethod
    def _extract_anthropic_cache_ttl_metrics(usage: dict[str, Any] | None) -> tuple[int, int]:
        """Extract observed Anthropic cache-write TTL bucket usage."""
        if not isinstance(usage, dict):
            return (0, 0)
        cache_creation = usage.get("cache_creation")
        if not isinstance(cache_creation, dict):
            return (0, 0)
        return (
            int(cache_creation.get("ephemeral_5m_input_tokens", 0) or 0),
            int(cache_creation.get("ephemeral_1h_input_tokens", 0) or 0),
        )

    def _parse_sse_usage(self, chunk: bytes, provider: str) -> dict[str, int] | None:
        """Parse usage information from SSE chunk.

        For Anthropic: Looks for message_start (input tokens) and message_delta (output tokens)
        For OpenAI: Looks for final chunk with usage object (requires stream_options.include_usage=true)
        For Gemini: Looks for usageMetadata in each chunk

        Returns dict with keys: input_tokens, output_tokens, cache_read_input_tokens,
        cache_creation_input_tokens, cache_creation_ephemeral_5m_input_tokens,
        cache_creation_ephemeral_1h_input_tokens
        Returns None if no usage found in this chunk.

        PR-A8 / P1-8: Decoded via the bytes-buffer SSE splitter so multi-byte
        characters split across TCP reads do not corrupt downstream parsing.
        Only complete events (terminated by ``\\n\\n``) are decoded; partial
        bytes are dropped (this method is single-chunk only — the buffered
        path is in ``_parse_sse_usage_from_buffer``).
        """
        from cutctx.proxy.helpers import parse_sse_events_from_byte_buffer

        try:
            buf = bytearray(chunk)
            events = parse_sse_events_from_byte_buffer(buf)
            for _event_name, data_str in events:
                if not data_str or data_str == "[DONE]":
                    continue

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                usage = {}

                if provider == "anthropic":
                    # Anthropic sends message_start with input tokens
                    # and message_delta with output tokens
                    event_type = data.get("type", "")

                    if event_type == "message_start":
                        msg = data.get("message", {})
                        msg_usage = msg.get("usage", {})
                        if msg_usage:
                            usage["input_tokens"] = msg_usage.get("input_tokens", 0)
                            usage["cache_read_input_tokens"] = msg_usage.get(
                                "cache_read_input_tokens", 0
                            )
                            usage["cache_creation_input_tokens"] = msg_usage.get(
                                "cache_creation_input_tokens", 0
                            )
                            cache_write_5m, cache_write_1h = (
                                self._extract_anthropic_cache_ttl_metrics(msg_usage)
                            )
                            usage["cache_creation_ephemeral_5m_input_tokens"] = cache_write_5m
                            usage["cache_creation_ephemeral_1h_input_tokens"] = cache_write_1h

                    elif event_type == "message_delta":
                        delta_usage = data.get("usage", {})
                        if delta_usage:
                            usage["output_tokens"] = delta_usage.get("output_tokens", 0)

                elif provider == "openai":
                    # OpenAI sends usage in final chunk (when stream_options.include_usage=true)
                    chunk_usage = data.get("usage")
                    if chunk_usage:
                        usage["input_tokens"] = chunk_usage.get("prompt_tokens", 0)
                        usage["output_tokens"] = chunk_usage.get("completion_tokens", 0)
                        # OpenAI has cached tokens in prompt_tokens_details
                        details = chunk_usage.get("prompt_tokens_details") or {}
                        usage["cache_read_input_tokens"] = details.get("cached_tokens", 0)

                elif provider == "gemini":
                    # Gemini sends usageMetadata in each streaming chunk
                    # Format: {"usageMetadata": {"promptTokenCount": N, "candidatesTokenCount": M}}
                    usage_meta = data.get("usageMetadata")
                    if usage_meta:
                        usage["input_tokens"] = usage_meta.get("promptTokenCount", 0)
                        usage["output_tokens"] = usage_meta.get("candidatesTokenCount", 0)
                        # Gemini also has cachedContentTokenCount for context caching
                        usage["cache_read_input_tokens"] = usage_meta.get(
                            "cachedContentTokenCount", 0
                        )

                if usage:
                    return usage

        except (UnicodeDecodeError, KeyError, TypeError) as e:
            # Don't fail streaming on parse errors
            logger.debug(f"SSE usage parsing error for {provider}: {e}")

        return None

    def _parse_sse_usage_from_buffer(
        self, stream_state: dict[str, Any], provider: str
    ) -> dict[str, int] | None:
        """Parse usage from buffered SSE data, handling split chunks.

        Processes complete SSE events (terminated by ``\\n\\n``) from the
        bytes buffer and removes them from the buffer. Incomplete events
        are kept in the buffer for the next chunk.

        PR-A8 / P1-8: ``stream_state["sse_buffer"]`` is a ``bytearray``
        (not ``str``); event boundaries are found in bytes so a multi-byte
        UTF-8 character split across TCP reads is preserved intact. Each
        complete event is decoded as UTF-8 only AFTER the boundary is
        located. Invalid UTF-8 in a *complete* event raises (operator-
        visible diagnostic, not silent corruption).
        """
        from cutctx.proxy.helpers import parse_sse_events_from_byte_buffer

        buffer = stream_state["sse_buffer"]
        usage_found: dict[str, int] = {}

        # Process complete SSE events (separated by double newlines).
        # ``parse_sse_events_from_byte_buffer`` mutates ``buffer`` in
        # place, leaving partial-event tail bytes for the next chunk —
        # since ``buffer`` is the same ``bytearray`` object held by
        # ``stream_state``, no reassignment is needed.
        events = parse_sse_events_from_byte_buffer(buffer)
        for _event_name, data_str in events:
            if not data_str or data_str == "[DONE]":
                continue

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if provider == "anthropic":
                event_type = data.get("type", "")
                if event_type == "message_start":
                    msg = data.get("message", {})
                    msg_usage = msg.get("usage", {})
                    if msg_usage:
                        usage_found["input_tokens"] = msg_usage.get("input_tokens", 0)
                        usage_found["cache_read_input_tokens"] = msg_usage.get(
                            "cache_read_input_tokens", 0
                        )
                        usage_found["cache_creation_input_tokens"] = msg_usage.get(
                            "cache_creation_input_tokens", 0
                        )
                        cache_write_5m, cache_write_1h = self._extract_anthropic_cache_ttl_metrics(
                            msg_usage
                        )
                        usage_found["cache_creation_ephemeral_5m_input_tokens"] = cache_write_5m
                        usage_found["cache_creation_ephemeral_1h_input_tokens"] = cache_write_1h
                        logger.debug(
                            f"[CACHE] Anthropic usage: input={usage_found.get('input_tokens')}, "
                            f"cache_read={usage_found.get('cache_read_input_tokens')}, "
                            f"cache_write={usage_found.get('cache_creation_input_tokens')}"
                        )
                elif event_type == "message_delta":
                    delta_usage = data.get("usage", {})
                    if delta_usage:
                        usage_found["output_tokens"] = delta_usage.get("output_tokens", 0)

            elif provider == "openai":
                chunk_usage = data.get("usage")
                if not isinstance(chunk_usage, dict):
                    response = data.get("response")
                    if isinstance(response, dict):
                        chunk_usage = response.get("usage")
                if isinstance(chunk_usage, dict):

                    def _usage_int(value: Any) -> int:
                        try:
                            return max(int(value), 0)
                        except (TypeError, ValueError):
                            return 0

                    # Chat Completions streams report prompt/completion tokens.
                    # Responses streams report input/output tokens under
                    # response.usage on response.completed.
                    input_tokens = chunk_usage.get("prompt_tokens")
                    if input_tokens is None:
                        input_tokens = chunk_usage.get("input_tokens", 0)
                    output_tokens = chunk_usage.get("completion_tokens")
                    if output_tokens is None:
                        output_tokens = chunk_usage.get("output_tokens", 0)
                    usage_found["input_tokens"] = _usage_int(input_tokens)
                    usage_found["output_tokens"] = _usage_int(output_tokens)
                    details = (
                        chunk_usage.get("prompt_tokens_details")
                        or chunk_usage.get("input_tokens_details")
                        or {}
                    )
                    if isinstance(details, dict):
                        usage_found["cache_read_input_tokens"] = _usage_int(
                            details.get("cached_tokens")
                        )

            elif provider == "gemini":
                usage_meta = data.get("usageMetadata")
                if usage_meta:
                    usage_found["input_tokens"] = usage_meta.get("promptTokenCount", 0)
                    usage_found["output_tokens"] = usage_meta.get("candidatesTokenCount", 0)
                    usage_found["cache_read_input_tokens"] = usage_meta.get(
                        "cachedContentTokenCount", 0
                    )

        return usage_found if usage_found else None

    def _parse_sse_to_response(self, sse_data: str, provider: str) -> dict[str, Any] | None:
        """Parse SSE data to reconstruct the API response JSON.

        Args:
            sse_data: Raw SSE data string. Must already be UTF-8 decoded
                from a complete-events bytes buffer (see
                ``parse_sse_events_from_byte_buffer``).
            provider: Provider type for parsing.

        Returns:
            Reconstructed response dict or None if parsing fails.

        PR-A8 / P1-9: handles all Anthropic delta types per guide §5.1:
        ``text_delta``, ``input_json_delta``, ``thinking_delta``,
        ``signature_delta``, ``citations_delta``. Also preserves
        ``redacted_thinking.data`` and accumulates citations as a list.
        """
        if provider != "anthropic":
            return None  # Only implemented for Anthropic

        response: dict[str, Any] = {"content": [], "usage": {}}
        # Track blocks by their `index` field so out-of-order events
        # don't corrupt the reconstruction. The current block pointer
        # remains for backward-compat with code that walks this dict
        # sequentially, but the index map is the source of truth.
        blocks_by_index: dict[int, dict[str, Any]] = {}
        current_block: dict[str, Any] | None = None

        for line in sse_data.split("\n"):
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if not data_str or data_str == "[DONE]":
                continue

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = data.get("type", "")

            if event_type == "message_start":
                msg = data.get("message", {})
                response["id"] = msg.get("id")
                response["model"] = msg.get("model")
                response["role"] = msg.get("role", "assistant")
                response["stop_reason"] = msg.get("stop_reason")
                if msg.get("usage"):
                    response["usage"].update(msg["usage"])

            elif event_type == "content_block_start":
                block = data.get("content_block", {})
                block_index = data.get("index", len(response["content"]))
                btype = block.get("type")
                current_block = {
                    "type": btype,
                    "index": block_index,
                }
                if btype == "text":
                    current_block["text"] = block.get("text", "")
                elif btype == "tool_use":
                    current_block["id"] = block.get("id")
                    current_block["name"] = block.get("name")
                    current_block["input"] = {}
                elif btype == "thinking":
                    # Thinking block — accumulate text via
                    # `thinking_delta`; signature arrives via
                    # `signature_delta` (single value, not accumulated).
                    current_block["thinking_buffer"] = block.get("thinking", "")
                    if "signature" in block:
                        current_block["signature"] = block["signature"]
                elif btype == "redacted_thinking":
                    # Per Anthropic spec §2.7: opaque encrypted reasoning
                    # block. The `data` field is preserved as-is and
                    # MUST be replayed unchanged on the next turn for
                    # signature validation to pass.
                    if "data" in block:
                        current_block["data"] = block["data"]
                blocks_by_index[block_index] = current_block

            elif event_type == "content_block_delta":
                # Resolve the target block by index (preferred) or fall
                # back to current_block for legacy linear streams.
                idx = data.get("index")
                target = (blocks_by_index.get(idx) if idx is not None else None) or current_block
                if target is not None:
                    delta = data.get("delta", {})
                    dtype = delta.get("type")
                    if dtype == "text_delta":
                        target["text"] = target.get("text", "") + delta.get("text", "")
                    elif dtype == "input_json_delta":
                        # Accumulate partial JSON for tool input.
                        partial = delta.get("partial_json", "")
                        target["_partial_json"] = target.get("_partial_json", "") + partial
                    elif dtype == "thinking_delta":
                        # Accumulate thinking text into the dedicated
                        # buffer so it never collides with `text` on
                        # text blocks (separate field per guide §2.7).
                        target["thinking_buffer"] = target.get("thinking_buffer", "") + delta.get(
                            "thinking", ""
                        )
                    elif dtype == "signature_delta":
                        # Single value, not accumulated. Last-write
                        # wins per Anthropic spec.
                        if "signature" in delta:
                            target["signature"] = delta["signature"]
                    elif dtype == "citations_delta":
                        # Append the citation object to the citations
                        # list so multi-citation blocks reconstruct
                        # correctly. Per guide §2.5: each delta carries
                        # one full citation object under `citation`.
                        citations = target.setdefault("citations", [])
                        citation = delta.get("citation")
                        if citation is not None:
                            citations.append(citation)

            elif event_type == "content_block_stop":
                idx = data.get("index")
                target = (blocks_by_index.get(idx) if idx is not None else None) or current_block
                if target is not None:
                    # Parse accumulated JSON for tool_use blocks.
                    if target.get("type") == "tool_use" and "_partial_json" in target:
                        try:
                            target["input"] = json.loads(target["_partial_json"])
                        except json.JSONDecodeError as _je:
                            logger.warning(
                                "[streaming] tool_use input JSON parse failed for block %r: %s — using empty input",
                                target.get("id"),
                                _je,
                            )
                            target["input"] = {}
                        del target["_partial_json"]
                    # Materialize the thinking buffer into the
                    # canonical `thinking` field expected by the
                    # Anthropic API.
                    if target.get("type") == "thinking" and "thinking_buffer" in target:
                        target["thinking"] = target.pop("thinking_buffer")
                    # Append the block exactly once. `current_block`
                    # may not match the indexed target if the stream
                    # interleaved multiple blocks; index-keyed map is
                    # authoritative.
                    if target not in response["content"]:
                        response["content"].append(target)
                    current_block = None

            elif event_type == "message_delta":
                delta = data.get("delta", {})
                if delta.get("stop_reason"):
                    response["stop_reason"] = delta["stop_reason"]
                if data.get("usage"):
                    response["usage"].update(data["usage"])

        return response if response.get("content") else None

    def _response_to_sse(self, response: dict[str, Any], provider: str) -> list[bytes]:
        """Convert a response dict back to SSE format.

        Args:
            response: API response dict.
            provider: Provider type for formatting.

        Returns:
            List of SSE event bytes.
        """
        if provider != "anthropic":
            return []

        events: list[bytes] = []

        # message_start
        msg_start = {
            "type": "message_start",
            "message": {
                "id": response.get("id", "msg_generated"),
                "type": "message",
                "role": response.get("role", "assistant"),
                "model": response.get("model", "unknown"),
                "content": [],
                "stop_reason": None,
                "usage": response.get("usage", {}),
            },
        }
        events.append(f"event: message_start\ndata: {json.dumps(msg_start)}\n\n".encode())

        # Content blocks
        for idx, block in enumerate(response.get("content", [])):
            # content_block_start
            if block.get("type") == "text":
                block_start = {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": {"type": "text", "text": ""},
                }
            elif block.get("type") == "tool_use":
                block_start = {
                    "type": "content_block_start",
                    "index": idx,
                    "content_block": {
                        "type": "tool_use",
                        "id": block.get("id", f"toolu_{idx}"),
                        "name": block.get("name", ""),
                        "input": {},
                    },
                }
            else:
                continue

            events.append(
                f"event: content_block_start\ndata: {json.dumps(block_start)}\n\n".encode()
            )

            # content_block_delta(s)
            if block.get("type") == "text" and block.get("text"):
                delta = {
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {"type": "text_delta", "text": block["text"]},
                }
                events.append(f"event: content_block_delta\ndata: {json.dumps(delta)}\n\n".encode())
            elif block.get("type") == "tool_use" and block.get("input"):
                delta = {
                    "type": "content_block_delta",
                    "index": idx,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(block["input"]),
                    },
                }
                events.append(f"event: content_block_delta\ndata: {json.dumps(delta)}\n\n".encode())

            # content_block_stop
            block_stop = {"type": "content_block_stop", "index": idx}
            events.append(f"event: content_block_stop\ndata: {json.dumps(block_stop)}\n\n".encode())

        # message_delta
        has_tool_use = any(b.get("type") == "tool_use" for b in response.get("content", []))
        stop_reason = "tool_use" if has_tool_use else response.get("stop_reason", "end_turn")
        msg_delta = {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason},
            "usage": {"output_tokens": response.get("usage", {}).get("output_tokens", 0)},
        }
        events.append(f"event: message_delta\ndata: {json.dumps(msg_delta)}\n\n".encode())

        # message_stop
        events.append(b'event: message_stop\ndata: {"type": "message_stop"}\n\n')

        return events

    def _record_ccr_feedback_from_response(
        self, response: dict, provider: str, request_id: str
    ) -> None:
        """Extract cutctx_retrieve tool calls from a response and record feedback.

        This closes the TOIN feedback loop for streaming responses where
        the proxy can't intercept and handle retrieval calls inline.
        """
        from cutctx.cache.compression_store import get_compression_store

        content = response.get("content", [])
        if not isinstance(content, list):
            return

        store = get_compression_store()

        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            if block.get("name") != "cutctx_retrieve":
                continue

            input_data = block.get("input", {})
            hash_key = input_data.get("hash")
            query = input_data.get("query")

            if not hash_key:
                continue

            logger.info(
                f"[{request_id}] CCR Feedback: Recording retrieval "
                f"hash={hash_key[:8]}... query={query!r}"
            )

            # Call store.retrieve()/search() for the side effect of triggering
            # the feedback chain: _log_retrieval -> process_pending_feedback
            # -> toin.record_retrieval(). We discard the returned content.
            try:
                if query:
                    store.search(hash_key, query)
                else:
                    store.retrieve(hash_key, query=None)
            except Exception as e:
                logger.debug(f"[{request_id}] CCR Feedback recording failed: {e}")

    def _record_ccr_feedback_from_openai_sse(self, full_sse_data: str, request_id: str) -> None:
        """Record cutctx_retrieve feedback from OpenAI Chat Completions SSE.

        OpenAI streams tool_calls incrementally via
        ``choices[0].delta.tool_calls[*].function.arguments`` (chunked
        JSON string). We accumulate per-call-index and finalize on
        stream completion. The accumulator records each completed
        ``cutctx_retrieve`` invocation as a no-op store call for the
        TOIN feedback side effect (matches the Anthropic streaming
        feedback path).
        """
        from cutctx.cache.compression_store import get_compression_store

        # tool_call_index -> {"name": str, "args_buf": str}
        tool_calls: dict[int, dict[str, str]] = {}

        for raw_line in full_sse_data.split("\n"):
            line = raw_line.strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if not payload or payload == "[DONE]":
                continue
            try:
                data = json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue

            choices = data.get("choices") or []
            if not choices:
                continue
            delta = (choices[0] or {}).get("delta") or {}
            for tc in delta.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                idx = tc.get("index", 0)
                fn = tc.get("function") or {}
                slot = tool_calls.setdefault(idx, {"name": "", "args_buf": ""})
                fn_name = fn.get("name")
                if fn_name:
                    slot["name"] = fn_name
                fn_args = fn.get("arguments")
                if fn_args:
                    slot["args_buf"] = slot["args_buf"] + fn_args

        if not tool_calls:
            return

        store = get_compression_store()
        for slot in tool_calls.values():
            if slot["name"] != "cutctx_retrieve":
                continue
            try:
                input_data = json.loads(slot["args_buf"]) if slot["args_buf"] else {}
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(input_data, dict):
                continue
            hash_key = input_data.get("hash")
            query = input_data.get("query")
            if not hash_key:
                continue

            logger.info(
                f"[{request_id}] CCR Feedback (openai stream): Recording retrieval "
                f"hash={hash_key[:8]}... query={query!r}"
            )
            try:
                if query:
                    store.search(hash_key, query)
                else:
                    store.retrieve(hash_key, query=None)
            except Exception as e:
                logger.debug(f"[{request_id}] CCR Feedback (openai stream) failed: {e}")

    async def _finalize_stream_response(
        self,
        *,
        body: dict,
        provider: str,
        outcome_provider: str | None = None,
        model: str,
        request_id: str,
        original_tokens: int,
        optimized_tokens: int,
        tokens_saved: int,
        transforms_applied: list[str],
        optimization_latency: float,
        stream_state: dict[str, Any],
        start_time: float,
        tags: dict[str, str] | None = None,
        pipeline_timing: dict[str, float] | None = None,
        prefix_tracker: Any | None = None,
        original_messages: list[dict] | None = None,
        full_sse_data: str = "",
        parsed_response: dict[str, Any] | None = None,
        client: str | None = None,
        savings_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        from cutctx.proxy.outcome import RequestOutcome

        outcome_provider = outcome_provider or provider
        total_latency = (time.time() - start_time) * 1000

        # Per-chunk SSE parsing only flushes events terminated by ``\n\n``.
        # When upstream truncates mid-event (client disconnect, network
        # drop, connection reset), the message_start (cache_read /
        # cache_creation) or message_delta (output_tokens) usage events
        # can sit in the residual buffer and never be parsed — surfacing
        # as cache_read=cache_write=0 in PERF logs and poisoning the
        # downstream freeze heuristic for the next request. Append the
        # terminator so the buffer parser drains whatever's there. The
        # per-event try/except in the parser swallows incomplete JSON,
        # so this is safe even when the truncation cut mid-payload.
        sse_buffer = stream_state.get("sse_buffer")
        if isinstance(sse_buffer, bytearray) and len(sse_buffer) > 0:
            sse_buffer.extend(b"\n\n")
            late_usage = self._parse_sse_usage_from_buffer(stream_state, provider) or {}
            for key in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
                "cache_creation_ephemeral_5m_input_tokens",
                "cache_creation_ephemeral_1h_input_tokens",
            ):
                if key not in late_usage:
                    continue
                current = stream_state.get(key)
                # Only fill in unset (None) or default-zero slots so a
                # real cache_read=0 from earlier in the stream isn't
                # clobbered by a later partial event.
                if current is None or current == 0:
                    stream_state[key] = late_usage[key]

        output_tokens = stream_state["output_tokens"]
        if output_tokens is None:
            output_tokens = stream_state["total_bytes"] // 40
            logger.warning(
                f"[{request_id}] Could not parse output_tokens from SSE, "
                f"estimating {output_tokens} from {stream_state['total_bytes']} bytes"
            )

        provider_input_tokens = stream_state.get("input_tokens")
        effective_optimized_tokens = optimized_tokens
        effective_original_tokens = original_tokens
        if (
            provider in {"openai", "gemini"}
            and isinstance(provider_input_tokens, int)
            and provider_input_tokens > 0
        ):
            effective_optimized_tokens = provider_input_tokens
            effective_original_tokens = max(original_tokens, provider_input_tokens + tokens_saved)

        cache_read_tokens = stream_state["cache_read_input_tokens"] or 0
        cache_write_tokens = stream_state["cache_creation_input_tokens"] or 0
        cache_write_5m_tokens = stream_state["cache_creation_ephemeral_5m_input_tokens"] or 0
        cache_write_1h_tokens = stream_state["cache_creation_ephemeral_1h_input_tokens"] or 0
        uncached_input_tokens = max(
            effective_optimized_tokens - cache_read_tokens - cache_write_tokens, 0
        )

        # Prefix-tracker mutation is provider-specific state that lives
        # outside the metric funnel. Run it before the funnel so the next
        # request inherits correct prefix state regardless of metric path.
        if prefix_tracker is not None:
            import copy as _copy

            forwarded_messages = body.get("messages", [])
            next_forwarded = _copy.deepcopy(forwarded_messages)
            next_original = _copy.deepcopy(original_messages or forwarded_messages)

            if full_sse_data and provider == "anthropic":
                _parsed = (
                    parsed_response
                    if parsed_response is not None
                    else self._parse_sse_to_response(full_sse_data, provider)
                )
                if _parsed:
                    asst_msg = self._assistant_message_from_response_json(_parsed)
                    if asst_msg is not None:
                        next_forwarded.append(_copy.deepcopy(asst_msg))
                        next_original.append(_copy.deepcopy(asst_msg))

            prefix_tracker.update_from_response(
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
                messages=next_forwarded,
                original_messages=next_original,
            )

        # Active-compression denominator (``attempted_input_tokens``) is
        # derived inside ``RequestOutcome.from_stream`` as
        # ``optimized_tokens + tokens_saved``. No frozen_message_count
        # propagates to the streaming finalizer yet — per-message
        # live-zone tracking is a follow-up. Without this fallback the
        # dashboard headline collapses to 0% even when compression is
        # happening (issue #455).
        # Audit-Deep-2026-06-21: extract per-source savings from
        # the metadata dict so the typed per-source fields on
        # RequestOutcome are populated. The funnel (in
        # emit_request_outcome) merges typed + escape-hatch
        # values, so passing the typed values from here is
        # the safe move. If the field is not in metadata,
        # default to 0 (the funnel's escape-hatch path will
        # still pick it up from savings_metadata).
        _sc_avoided = 0
        _self_hosted_hits = 0
        _routing_tokens = 0
        _routing_usd = 0.0
        if savings_metadata:
            _sc_avoided = int((savings_metadata.get("semantic_cache") or {}).get("tokens", 0) or 0)
            _self_hosted_hits = int(
                (savings_metadata.get("prefix_cache_self_hosted") or {}).get("tokens", 0) or 0
            )
            _routing_meta = savings_metadata.get("model_routing") or {}
            _routing_tokens = int(_routing_meta.get("tokens_saved", 0) or 0)
            _routing_usd = float(_routing_meta.get("usd_saved", 0.0) or 0.0)

        outcome = RequestOutcome.from_stream(
            body=body,
            provider=outcome_provider,
            model=model,
            request_id=request_id,
            original_tokens=effective_original_tokens,
            optimized_tokens=effective_optimized_tokens,
            output_tokens=output_tokens,
            tokens_saved=tokens_saved,
            transforms_applied=transforms_applied,
            total_latency_ms=total_latency,
            overhead_ms=optimization_latency,
            tags=tags,
            client=client,
            log_full_messages=getattr(self.config, "log_full_messages", False),
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_write_5m_tokens=cache_write_5m_tokens,
            cache_write_1h_tokens=cache_write_1h_tokens,
            uncached_input_tokens=uncached_input_tokens,
            ttfb_ms=stream_state["ttfb_ms"] or total_latency,
            pipeline_timing=pipeline_timing,
            original_messages=original_messages,
            savings_metadata=savings_metadata,
            # Audit-Deep-2026-06-21: per-source fields (was: 0).
            semantic_cache_avoided_tokens=_sc_avoided,
            self_hosted_prefix_cache_hits=_self_hosted_hits,
            model_routing_tokens_saved=_routing_tokens,
            model_routing_usd_saved=_routing_usd,
        )
        cache = getattr(self, "cache", None)
        print(f"DEBUG: cache={cache is not None} original_messages={bool(original_messages)} full_sse_data={bool(full_sse_data)}")
        if cache and original_messages:
            if full_sse_data:
                await cache.set(
                    messages=original_messages,
                    model=model,
                    response_body=full_sse_data.encode("utf-8"),
                    response_headers={"content-type": "text/event-stream"},
                    tokens_saved=max(effective_optimized_tokens, cache_read_tokens),
                )
                print("DEBUG: cache.set called with full_sse_data")
            elif parsed_response:
                await cache.set(
                    messages=original_messages,
                    model=model,
                    response_body=json.dumps(parsed_response).encode("utf-8"),
                    response_headers={"content-type": "application/json"},
                    tokens_saved=max(effective_optimized_tokens, cache_read_tokens),
                )
                print("DEBUG: cache.set called with parsed_response")

        await self._record_request_outcome(outcome)

    async def _stream_response(
        self,
        url: str,
        headers: dict,
        body: dict,
        provider: str,
        model: str,
        request_id: str,
        original_tokens: int,
        optimized_tokens: int,
        tokens_saved: int,
        transforms_applied: list[str],
        tags: dict[str, str],
        optimization_latency: float,
        memory_user_id: str | None = None,
        pipeline_timing: dict[str, float] | None = None,
        prefix_tracker: Any | None = None,
        original_messages: list[dict] | None = None,
        *,
        original_body_bytes: bytes | None = None,
        body_mutated: bool = True,
        mutation_reasons: list[str] | None = None,
        memory_request_ctx: Any | None = None,
        outcome_provider: str | None = None,
        savings_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> Response | StreamingResponse:
        """Stream response with metrics tracking and memory tool handling.

        Parses SSE events to extract actual usage information from the API response
        for accurate token counting and cost calculation.

        When memory is enabled (memory_user_id provided), this method:
        1. Buffers the response to detect memory tool calls
        2. Executes memory tools if found
        3. Makes continuation requests until no memory tools remain
        4. Streams the final response to the client
        """
        from fastapi.responses import Response, StreamingResponse

        from cutctx.proxy.helpers import MAX_SSE_BUFFER_SIZE, MAX_SSE_MIRROR_SIZE

        # Identify the harness (codex / claude-code / aider / cursor /
        # ...) from the *client's* User-Agent before copilot-auth
        # potentially rewrites headers for upstream.
        client = classify_client(headers)
        headers = await apply_copilot_api_auth(headers, url=url)
        start_time = time.time()

        # Byte-faithful forwarding (PR-A3, fixes P0-2). Resolve outbound
        # bytes once before entering the connection-retry loop. When a
        # transform mutated the body we re-serialize canonically; otherwise
        # we forward the original client bytes verbatim.
        from cutctx.proxy.helpers import (
            capture_codex_wire_debug,
            codex_wire_debug_enabled,
            log_outbound_request,
            prepare_outbound_body_bytes,
        )

        outbound_bytes, outbound_source = prepare_outbound_body_bytes(
            body=body,
            original_body_bytes=original_body_bytes,
            body_mutated=body_mutated,
        )
        outbound_headers = {**headers, "content-type": "application/json"}

        # ── Ensemble interception ──
        # When ensemble is enabled AND the client sends X-Cutctx-Ensemble,
        # fan out to multiple models concurrently and return the best response.
        if headers.get("x-cutctx-ensemble", "").lower() in ("true", "1", "yes"):
            try:
                from cutctx.proxy.ensemble import EnsembleConfig, EnsembleCoordinator

                _ens_cfg = EnsembleConfig.from_env()
                if _ens_cfg.enabled:
                    messages = body.get("messages", [])
                    coordinator = EnsembleCoordinator(_ens_cfg)
                    ensemble_result = await coordinator.execute(
                        messages=messages,
                        client=self.http_client,
                        temperature=body.get("temperature", 0.7),
                        max_tokens=body.get("max_tokens", 4096),
                    )
                    # Return the winning response as a non-streaming JSON response
                    from fastapi.responses import JSONResponse

                    winning = {
                        "id": f"ensemble-{request_id}",
                        "model": ensemble_result.winning_model,
                        "content": ensemble_result.content,
                        "finish_reason": "ensemble_evaluated",
                        "_ensemble": {
                            "winning_model": ensemble_result.winning_model,
                            "evaluation_reasoning": ensemble_result.evaluation_reasoning,
                            "total_latency_ms": ensemble_result.total_latency_ms,
                            "models_evaluated": [
                                {"model": r.model, "latency_ms": r.latency_ms, "success": r.success}
                                for r in ensemble_result.all_results
                            ],
                        },
                    }
                    logger.info(
                        "[%s] Ensemble: winning model=%s, %d models evaluated in %.1fms",
                        request_id,
                        ensemble_result.winning_model,
                        len(ensemble_result.all_results),
                        ensemble_result.total_latency_ms,
                    )
                    return JSONResponse(content=winning)
            except Exception as ens_err:
                logger.warning(
                    "[%s] Ensemble failed, falling through to single model: %s", request_id, ens_err
                )
        log_outbound_request(
            forwarder="streaming",
            method="POST",
            path=url,
            body_bytes_count=len(outbound_bytes),
            body_mutated=body_mutated,
            mutation_reasons=list(mutation_reasons or []),
            request_id=request_id,
            source=outbound_source,
        )
        _codex_wire_debug = (
            codex_wire_debug_enabled() and provider == "openai" and "/responses" in url
        )
        if _codex_wire_debug:
            capture_codex_wire_debug(
                "http_stream_upstream_request",
                request_id=request_id,
                transport="http_sse",
                direction="cutctx_to_upstream",
                method="POST",
                url=url,
                headers=outbound_headers,
                body=body,
                metadata={
                    "body_bytes": len(outbound_bytes),
                    "body_mutated": body_mutated,
                    "mutation_reasons": list(mutation_reasons or []),
                    "tokens_saved": tokens_saved,
                    "transforms_applied": transforms_applied,
                },
            )

        # Mutable state for the generator to update
        stream_state: dict[str, Any] = {
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_creation_ephemeral_5m_input_tokens": 0,
            "cache_creation_ephemeral_1h_input_tokens": 0,
            "total_bytes": 0,
            # Buffer for incomplete SSE events (bytes, per PR-A8 / P1-8).
            # We split events on the ``\n\n`` byte sequence and decode
            # each complete event as UTF-8 only after the boundary is
            # found, so multi-byte characters split across TCP reads do
            # not corrupt downstream parsing.
            "sse_buffer": bytearray(),
            "ttfb_ms": None,  # Time to first byte from upstream
        }

        # Track if we need to handle memory tools
        memory_enabled = (
            memory_user_id is not None
            and self.memory_handler is not None
            and provider == "anthropic"
        )

        # Open connection before generator to capture upstream response headers
        # (needed to forward ratelimit headers to the client via StreamingResponse)
        assert self.http_client is not None, "http_client must be initialized before streaming"
        try:
            retry_attempts = max(1, getattr(self.config, "retry_max_attempts", 3))
            upstream_response = None
            last_connect_error = None

            for attempt in range(retry_attempts):
                try:
                    _upstream_req = self.http_client.build_request(
                        "POST", url, content=outbound_bytes, headers=outbound_headers
                    )
                    upstream_response = await self.http_client.send(_upstream_req, stream=True)
                    if _codex_wire_debug:
                        capture_codex_wire_debug(
                            "http_stream_upstream_response_headers",
                            request_id=request_id,
                            transport="http_sse",
                            direction="upstream_to_cutctx",
                            method="POST",
                            url=url,
                            headers=dict(upstream_response.headers),
                            status_code=upstream_response.status_code,
                        )
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as e:
                    last_connect_error = e
                    if attempt >= retry_attempts - 1:
                        raise

                    delay_with_jitter = jitter_delay_ms(
                        self.config.retry_base_delay_ms,
                        self.config.retry_max_delay_ms,
                        attempt,
                    )
                    logger.warning(
                        f"[{request_id}] Connection error to upstream API "
                        f"(attempt {attempt + 1}/{retry_attempts}): {e!r}; "
                        f"retrying in {delay_with_jitter:.0f}ms"
                    )
                    await asyncio.sleep(delay_with_jitter / 1000)

            if upstream_response is None:
                raise last_connect_error or RuntimeError("upstream connection did not start")
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as e:
            logger.error(f"[{request_id}] Connection error to upstream API: {e}")

            fallback_provider = getattr(self.config, "fallback_provider", None)
            fallback_backend = getattr(self, "fallback_backend", None) or getattr(
                self, "openai_fallback_backend", None
            )
            if (
                provider == "gemini"
                and getattr(self.config, "fallback_enabled", False)
                and fallback_provider
                and fallback_backend is not None
            ):
                logger.info(
                    "[%s] Attempting Gemini streaming fallback to %s",
                    request_id,
                    fallback_provider,
                )
                tags["fallback_provider"] = fallback_provider
                tags["fallback_attempted"] = "true"
                tags["fallback_reason"] = self._classify_streaming_fallback_reason(e)
                tags["fallback_source_provider"] = provider
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
                return await self._stream_gemini_via_backend(
                    body=body,
                    headers=dict(headers),
                    model=model,
                    request_id=request_id,
                    start_time=start_time,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    tags=tags,
                    optimization_latency=optimization_latency,
                    pipeline_timing=pipeline_timing,
                    savings_metadata=savings_metadata,
                    backend=fallback_backend,
                    outcome_provider=fallback_provider,
                )

            fallback_provider = getattr(self.config, "fallback_provider", None)
            fallback_backend = getattr(self, "fallback_backend", None) or getattr(
                self, "openai_fallback_backend", None
            )
            if (
                provider == "openai"
                and getattr(self.config, "fallback_enabled", False)
                and fallback_provider
                and fallback_backend is not None
            ):
                logger.info(
                    "[%s] Attempting OpenAI streaming fallback to %s",
                    request_id,
                    fallback_provider,
                )
                tags["fallback_provider"] = fallback_provider
                tags["fallback_attempted"] = "true"
                tags["fallback_reason"] = self._classify_streaming_fallback_reason(e)
                tags["fallback_source_provider"] = provider
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
                return await self._stream_openai_via_backend(
                    body=body,
                    headers=dict(headers),
                    model=model,
                    request_id=request_id,
                    start_time=start_time,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    tags=tags,
                    optimization_latency=optimization_latency,
                    pipeline_timing=pipeline_timing,
                    waste_signals=None,
                    prefix_tracker=prefix_tracker,
                    optimized_messages=body.get("messages", []),
                    savings_metadata=savings_metadata,
                    backend=fallback_backend,
                    outcome_provider=fallback_provider,
                )

            fallback_provider = getattr(self.config, "fallback_provider", None)
            fallback_backend = getattr(self, "fallback_backend", None) or getattr(
                self, "openai_fallback_backend", None
            )
            if (
                provider == "anthropic"
                and self.config.fallback_enabled
                and fallback_provider
                and fallback_backend is not None
            ):
                logger.info(
                    "[%s] Attempting streaming fallback to %s",
                    request_id,
                    fallback_provider,
                )
                tags["fallback_provider"] = fallback_provider
                tags["fallback_attempted"] = "true"
                tags["fallback_reason"] = self._classify_streaming_fallback_reason(e)
                tags["fallback_source_provider"] = provider
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
                return await self._stream_response_backend(
                    backend=fallback_backend,
                    body=body,
                    headers=dict(headers),
                    provider=provider,
                    model=model,
                    request_id=request_id,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    tags=tags,
                    optimization_latency=optimization_latency,
                    pipeline_timing=pipeline_timing,
                    original_messages=original_messages,
                    savings_metadata=savings_metadata,
                    outcome_provider=fallback_provider,
                )

            async def _error_gen():
                error_event = {
                    "type": "error",
                    "error": {
                        "type": "connection_error",
                        "message": "Failed to connect to upstream API",
                    },
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

            return StreamingResponse(_error_gen(), media_type="text/event-stream")

        # Capture Codex rate-limit window data from the upstream response
        # headers, for *every* status. Codex (gpt-5.x) almost always streams, so
        # without this the session/weekly windows surfaced in ``/stats`` and the
        # dashboard would only refresh on the rare non-streaming reply. We do this
        # *before* the error early-return below so a streaming 429/5xx — the moment
        # usage is most relevant — still refreshes the windows, matching the
        # non-streaming HTTP handlers which capture on all statuses.
        # ``update_from_headers`` is a no-op when the response carries no
        # ``x-codex-*`` headers (e.g. the Anthropic streaming path), so this is
        # safe to call unconditionally.
        from cutctx.subscription.codex_rate_limits import (
            get_codex_rate_limit_state,
        )

        get_codex_rate_limit_state().update_from_headers(dict(upstream_response.headers))

        if upstream_response.status_code >= 400:
            fallback_provider = getattr(self.config, "fallback_provider", None)
            fallback_backend = getattr(self, "fallback_backend", None) or getattr(
                self, "openai_fallback_backend", None
            )
            if (
                upstream_response.status_code >= 500
                and provider == "gemini"
                and getattr(self.config, "fallback_enabled", False)
                and fallback_provider
                and fallback_backend is not None
            ):
                logger.info(
                    "[%s] Attempting Gemini streaming fallback to %s after upstream status=%s",
                    request_id,
                    fallback_provider,
                    upstream_response.status_code,
                )
                tags["fallback_provider"] = fallback_provider
                tags["fallback_attempted"] = "true"
                tags["fallback_reason"] = "upstream_5xx"
                tags["fallback_source_provider"] = provider
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
                await upstream_response.aclose()
                return await self._stream_gemini_via_backend(
                    body=body,
                    headers=dict(headers),
                    model=model,
                    request_id=request_id,
                    start_time=start_time,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    tags=tags,
                    optimization_latency=optimization_latency,
                    pipeline_timing=pipeline_timing,
                    savings_metadata=savings_metadata,
                    backend=fallback_backend,
                    outcome_provider=fallback_provider,
                )

            fallback_provider = getattr(self.config, "fallback_provider", None)
            fallback_backend = getattr(self, "fallback_backend", None) or getattr(
                self, "openai_fallback_backend", None
            )
            if (
                upstream_response.status_code >= 500
                and provider == "openai"
                and getattr(self.config, "fallback_enabled", False)
                and fallback_provider
                and fallback_backend is not None
            ):
                logger.info(
                    "[%s] Attempting OpenAI streaming fallback to %s after upstream status=%s",
                    request_id,
                    fallback_provider,
                    upstream_response.status_code,
                )
                tags["fallback_provider"] = fallback_provider
                tags["fallback_attempted"] = "true"
                tags["fallback_reason"] = "upstream_5xx"
                tags["fallback_source_provider"] = provider
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
                await upstream_response.aclose()
                return await self._stream_openai_via_backend(
                    body=body,
                    headers=dict(headers),
                    model=model,
                    request_id=request_id,
                    start_time=start_time,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    tags=tags,
                    optimization_latency=optimization_latency,
                    pipeline_timing=pipeline_timing,
                    waste_signals=None,
                    prefix_tracker=prefix_tracker,
                    optimized_messages=body.get("messages", []),
                    savings_metadata=savings_metadata,
                    backend=fallback_backend,
                    outcome_provider=fallback_provider,
                )

            fallback_provider = getattr(self.config, "fallback_provider", None)
            fallback_backend = getattr(self, "fallback_backend", None) or getattr(
                self, "openai_fallback_backend", None
            )
            if (
                upstream_response.status_code >= 500
                and provider == "anthropic"
                and self.config.fallback_enabled
                and fallback_provider
                and fallback_backend is not None
            ):
                logger.info(
                    "[%s] Attempting streaming fallback to %s after upstream status=%s",
                    request_id,
                    fallback_provider,
                    upstream_response.status_code,
                )
                tags["fallback_provider"] = fallback_provider
                tags["fallback_attempted"] = "true"
                tags["fallback_reason"] = "upstream_5xx"
                tags["fallback_source_provider"] = provider
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
                await upstream_response.aclose()
                return await self._stream_response_backend(
                    backend=fallback_backend,
                    body=body,
                    headers=dict(headers),
                    provider=provider,
                    model=model,
                    request_id=request_id,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    tags=tags,
                    optimization_latency=optimization_latency,
                    pipeline_timing=pipeline_timing,
                    original_messages=original_messages,
                    savings_metadata=savings_metadata,
                    outcome_provider=fallback_provider,
                )

            logger.warning(
                "[%s] Forwarding upstream streaming error status=%s url=%s",
                request_id,
                upstream_response.status_code,
                url,
            )
            # Log body keys + small fields to aid diagnosis (drop large text fields)
            try:
                _body_keys = list(body.keys())
                _small_fields = {
                    k: v
                    for k, v in body.items()
                    if k not in ("input", "instructions", "tools") and not isinstance(v, str)
                }
                _sent_summary = f"keys={_body_keys} small_fields={json.dumps(_small_fields)[:300]}"
            except Exception:
                _sent_summary = "<unserializable>"
            logger.error(
                "[%s] upstream %d — url=%s body_debug=%s",
                request_id,
                upstream_response.status_code,
                url,
                _sent_summary,
            )
            response_headers = dict(upstream_response.headers)
            response_headers.pop("content-length", None)
            response_headers.pop("transfer-encoding", None)
            response_headers.pop("connection", None)
            response_headers.pop("content-encoding", None)

            try:
                error_content = await upstream_response.aread()
                logger.error(
                    "[%s] upstream %d response body: %s",
                    request_id,
                    upstream_response.status_code,
                    error_content[:2000].decode("utf-8", errors="replace"),
                )
            except Exception as read_error:
                logger.warning(
                    "[%s] Failed reading upstream error body status=%s url=%s error=%s",
                    request_id,
                    upstream_response.status_code,
                    url,
                    read_error,
                )
                error_content = json.dumps(
                    {
                        "error": {
                            "message": "Failed to read upstream error response body",
                            "details": str(read_error),
                        }
                    }
                ).encode("utf-8")
                response_headers["content-type"] = "application/json"
            finally:
                await upstream_response.aclose()

            if _codex_wire_debug:
                _error_text: str | None = None
                _error_body: Any = None
                try:
                    _error_text = error_content.decode("utf-8")
                    _error_body = json.loads(_error_text)
                    _error_text = None
                except Exception:
                    with contextlib.suppress(Exception):
                        _error_text = error_content.decode("utf-8", errors="replace")
                capture_codex_wire_debug(
                    "http_stream_upstream_error_response",
                    request_id=request_id,
                    transport="http_sse",
                    direction="upstream_to_cutctx",
                    method="POST",
                    url=url,
                    headers=response_headers,
                    body=_error_body,
                    raw_text=_error_text,
                    status_code=upstream_response.status_code,
                )

            stream_state["total_bytes"] = len(error_content)
            await self._finalize_stream_response(
                body=body,
                provider=provider,
                outcome_provider=outcome_provider,
                model=model,
                request_id=request_id,
                original_tokens=original_tokens,
                optimized_tokens=optimized_tokens,
                tokens_saved=tokens_saved,
                transforms_applied=transforms_applied,
                optimization_latency=optimization_latency,
                stream_state=stream_state,
                start_time=start_time,
                tags=tags,
                pipeline_timing=pipeline_timing,
                prefix_tracker=prefix_tracker,
                original_messages=original_messages,
                client=client,
                savings_metadata=savings_metadata,
            )
            return Response(
                content=error_content,
                status_code=upstream_response.status_code,
                headers=response_headers,
            )

        # Forward upstream rate-limit headers to the client. We pass both the
        # generic ``*ratelimit*`` headers (Anthropic) and Codex's ``x-codex-*``
        # window/credit headers — the latter do not contain the ``ratelimit``
        # substring, so without the second clause the Codex CLI's own
        # session/weekly display would stop updating on the streaming path.
        forwarded_headers = {
            k: v
            for k, v in upstream_response.headers.items()
            if "ratelimit" in k.lower() or k.lower().startswith("x-codex")
        }

        # Adjust token count header to reflect post-compression token budget.
        # After compression, the client consumed fewer tokens than the upstream
        # reported; credit the difference back so harnesses don't throttle early.
        _remaining_key = "x-ratelimit-remaining-tokens"
        if _remaining_key in forwarded_headers and tokens_saved > 0:
            try:
                _remaining = int(forwarded_headers[_remaining_key])
                forwarded_headers[_remaining_key] = str(_remaining + tokens_saved)
            except (ValueError, TypeError):
                pass

        async def generate():
            nonlocal body, memory_enabled  # May need to modify for continuation requests

            stream_complete = False

            # For memory mode, we buffer the response to check for tool calls
            buffered_chunks: list[bytes] = []
            # Bytes-level mirror of the SSE stream for memory/prefix
            # tracking. PR-A8 / P1-8: keep this as bytes too — we
            # decode only after a complete `\n\n`-terminated event has
            # been collected, so split UTF-8 bytes never produce
            # corrupted strings.
            full_sse_bytes = bytearray()
            full_sse_truncated = False
            parsed_response = None  # Set by memory block; used by CCR + prefix tracker

            # ── Budget tracker (per-request token budget enforcement) ──
            budget_tracker = None
            try:
                from cutctx.proxy.budget import BudgetConfig, BudgetTracker

                _budget_cfg = BudgetConfig.from_env()
                if _budget_cfg.enabled:
                    budget_tracker = BudgetTracker(
                        _budget_cfg,
                        user_budget_tokens=_budget_cfg.default_budget_tokens,
                        model=model,
                    )
            except Exception:
                pass

            try:
                async with contextlib.aclosing(upstream_response) as response:
                    sse_chunk_index = 0
                    # Blocker-10 (production-audit-progress-2026-06-20.md):
                    # wrap_stream on StreamingRedactor was defined but
                    # had no callsite; the streaming PII redactor was
                    # therefore dead code. The redactor is now invoked
                    # here (when the firewall middleware exposes one)
                    # to redact PII from SSE response chunks before
                    # they reach the client. Falls through to the
                    # original aiter_bytes() iterator when no
                    # redactor is configured.
                    chunk_iter = response.aiter_bytes()
                    _streaming_redactor = getattr(self, "_streaming_redactor", None)
                    if _streaming_redactor is not None and getattr(
                        _streaming_redactor, "enabled", False
                    ):
                        chunk_iter = _streaming_redactor.wrap_stream(chunk_iter)
                    async for chunk in chunk_iter:
                        sse_chunk_index += 1
                        # Record TTFB on first chunk
                        if stream_state["ttfb_ms"] is None:
                            stream_state["ttfb_ms"] = (time.time() - start_time) * 1000

                        stream_state["total_bytes"] += len(chunk)

                        # PR-A8 / P1-8: append bytes verbatim. The
                        # buffer is a ``bytearray`` and event boundaries
                        # are located in bytes; decoding happens per
                        # complete event in the SSE splitter helper.
                        stream_state["sse_buffer"].extend(chunk)

                        # Safety: prevent unbounded buffer growth.
                        if len(stream_state["sse_buffer"]) > MAX_SSE_BUFFER_SIZE:
                            logger.error(
                                "SSE buffer exceeded maximum size (%d bytes), "
                                "truncating to prevent memory exhaustion",
                                MAX_SSE_BUFFER_SIZE,
                            )
                            # Keep the most recent half so an in-flight
                            # event is more likely to survive.
                            tail = bytes(stream_state["sse_buffer"][-MAX_SSE_BUFFER_SIZE // 2 :])
                            stream_state["sse_buffer"] = bytearray(tail)

                        # Always stream immediately — buffering breaks
                        # real-time clients (LangGraph, LangChain, etc.)
                        yield chunk

                        if _codex_wire_debug:
                            capture_codex_wire_debug(
                                "http_stream_upstream_chunk",
                                request_id=request_id,
                                transport="http_sse",
                                direction="upstream_to_cutctx",
                                method="POST",
                                url=url,
                                raw_text=chunk.decode("utf-8", errors="replace"),
                                metadata={
                                    "chunk": sse_chunk_index,
                                    "byte_count": len(chunk),
                                },
                            )

                        # Buffer SSE data for memory processing and/or prefix tracker
                        _track_sse = (
                            _codex_wire_debug
                            or memory_enabled
                            or (prefix_tracker is not None and provider == "anthropic")
                        )
                        if _track_sse and not full_sse_truncated:
                            if memory_enabled:
                                buffered_chunks.append(chunk)
                            if len(full_sse_bytes) + len(chunk) <= MAX_SSE_MIRROR_SIZE:
                                full_sse_bytes.extend(chunk)
                            else:
                                logger.warning(
                                    "SSE post-stream mirror exceeded %d bytes; disabling optional "
                                    "post-stream processing for this request",
                                    MAX_SSE_MIRROR_SIZE,
                                )
                                memory_enabled = False
                                buffered_chunks.clear()
                                full_sse_bytes.clear()
                                full_sse_truncated = True

                        # Parse complete SSE events from buffer
                        # Check if we've received the terminal [DONE] sentinel
                        if b"[DONE]" in chunk:
                            stream_complete = True
                        usage = self._parse_sse_usage_from_buffer(stream_state, provider)
                        if usage:
                            if "input_tokens" in usage:
                                stream_state["input_tokens"] = usage["input_tokens"]
                            if "output_tokens" in usage:
                                stream_state["output_tokens"] = usage["output_tokens"]
                            if "cache_read_input_tokens" in usage:
                                stream_state["cache_read_input_tokens"] = usage[
                                    "cache_read_input_tokens"
                                ]
                            if "cache_creation_input_tokens" in usage:
                                stream_state["cache_creation_input_tokens"] = usage[
                                    "cache_creation_input_tokens"
                                ]
                            if "cache_creation_ephemeral_5m_input_tokens" in usage:
                                stream_state["cache_creation_ephemeral_5m_input_tokens"] = usage[
                                    "cache_creation_ephemeral_5m_input_tokens"
                                ]
                            if "cache_creation_ephemeral_1h_input_tokens" in usage:
                                stream_state["cache_creation_ephemeral_1h_input_tokens"] = usage[
                                    "cache_creation_ephemeral_1h_input_tokens"
                                ]

                        # ── Budget enforcement ──
                        if budget_tracker is not None and "output_tokens" in stream_state:
                            budget_tracker.add_tokens(
                                stream_state["output_tokens"] - budget_tracker.tokens_used
                            )
                            if budget_tracker.should_warn():
                                warning_chunk = budget_tracker.make_budget_warning_chunk()
                                yield warning_chunk.encode("utf-8")
                                logger.info(
                                    "[%s] Budget warning: %.0f%% used (%d/%d tokens)",
                                    request_id,
                                    budget_tracker.percent_used,
                                    budget_tracker.tokens_used,
                                    budget_tracker.budget_tokens,
                                )
                            if budget_tracker.is_exceeded():
                                exceeded_chunk = budget_tracker.make_budget_exceeded_chunk()
                                yield exceeded_chunk.encode("utf-8")
                                logger.warning(
                                    "[%s] Budget exceeded: %d/%d tokens — stream terminated",
                                    request_id,
                                    budget_tracker.tokens_used,
                                    budget_tracker.budget_tokens,
                                )
                                return  # Stop streaming

                # Memory tool handling after stream completes
                # Chunks were already yielded in real-time above, so we only
                # do silent background processing here — no yielding.
                #
                # PR-A8 / P1-8: full_sse_bytes accumulated as bytes; we
                # decode here in one shot now that the stream is
                # complete (the entire payload is a closed sequence of
                # complete events). Invalid UTF-8 at this point would
                # be an upstream protocol violation — surface loudly.
                full_sse_data: str = full_sse_bytes.decode("utf-8") if full_sse_bytes else ""

                if memory_enabled and full_sse_data:
                    # Check for Claude Code credential error
                    if "only authorized for use with Claude Code" in full_sse_data:
                        logger.warning(
                            f"[{request_id}] Memory: Claude Code subscription credentials "
                            "do not support custom tool injection. Set ANTHROPIC_API_KEY "
                            "environment variable or use --no-memory-tools flag."
                        )
                        return

                    # Parse SSE to get response JSON
                    parsed_response = self._parse_sse_to_response(full_sse_data, provider)

                    if parsed_response and self.memory_handler.has_memory_tool_calls(
                        parsed_response, provider
                    ):
                        logger.info(
                            f"[{request_id}] Memory: Detected tool calls in streaming response"
                        )

                        # Execute memory tool calls — response already streamed
                        # so results are saved but continuation is not possible
                        # in SSE streaming mode. The WS and non-streaming paths
                        # handle continuation properly.
                        tool_results = await self.memory_handler.handle_memory_tool_calls(
                            parsed_response,
                            memory_user_id,
                            provider,
                            request_context=memory_request_ctx,
                        )
                        if tool_results:
                            logger.info(
                                f"[{request_id}] Memory: Tool calls executed "
                                f"({len(tool_results)} results saved, SSE streaming — "
                                "continuation handled by client)"
                            )

                # CCR Feedback: Record cutctx_retrieve tool calls for TOIN learning.
                # In streaming mode, the client handles actual retrieval, but we
                # still need to record the event so TOIN learns which fields matter.
                if self.config.ccr_inject_tool and full_sse_data:
                    ccr_parsed = (
                        parsed_response
                        if parsed_response
                        else self._parse_sse_to_response(full_sse_data, provider)
                    )
                    if ccr_parsed:
                        self._record_ccr_feedback_from_response(ccr_parsed, provider, request_id)

                # ── Structured Output post-validation (streaming) ──
                # Validate the streamed response text against the request's
                # json_schema. We can't retry (already streamed) so we log.
                if full_sse_data:
                    try:
                        from cutctx.proxy.structured_output import (
                            StructuredOutputConfig,
                            StructuredOutputValidator,
                        )

                        _so_cfg = StructuredOutputConfig.from_env()
                        if _so_cfg.enabled:
                            _so_validator = StructuredOutputValidator(_so_cfg)
                            _schema = _so_validator.detect_schema(body)
                            if _schema is not None:
                                _so_parsed = (
                                    parsed_response
                                    if parsed_response
                                    else self._parse_sse_to_response(full_sse_data, provider)
                                )
                                if _so_parsed:
                                    _resp_text = ""
                                    if isinstance(_so_parsed, dict):
                                        _content_blocks = _so_parsed.get("content", [])
                                        if isinstance(_content_blocks, list):
                                            for _block in _content_blocks:
                                                if (
                                                    isinstance(_block, dict)
                                                    and _block.get("type") == "text"
                                                ):
                                                    _resp_text += _block.get("text", "")
                                    if _resp_text:
                                        _vresult = _so_validator.validate(_resp_text, _schema)
                                        if not _vresult.valid:
                                            logger.warning(
                                                f"[{request_id}] Structured output streaming validation FAILED: "
                                                f"errors={_vresult.errors} "
                                                f"validation_ms={_vresult.validation_time_ms:.1f}"
                                            )
                                        else:
                                            logger.debug(
                                                f"[{request_id}] Structured output streaming validation OK "
                                                f"({_vresult.validation_time_ms:.1f}ms)"
                                            )
                    except Exception as _so_err:
                        logger.debug(
                            f"[{request_id}] Structured output streaming validation error: {_so_err}"
                        )
                if _codex_wire_debug:
                    _debug_parsed_response = (
                        parsed_response
                        if parsed_response
                        else self._parse_sse_to_response(full_sse_data, provider)
                        if full_sse_data
                        else None
                    )
                    capture_codex_wire_debug(
                        "http_stream_upstream_complete",
                        request_id=request_id,
                        transport="http_sse",
                        direction="upstream_to_cutctx",
                        method="POST",
                        url=url,
                        headers=dict(upstream_response.headers),
                        body=_debug_parsed_response,
                        raw_text=full_sse_data,
                        status_code=upstream_response.status_code,
                        metadata={"total_bytes": stream_state["total_bytes"]},
                    )

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as e:
                logger.error(f"[{request_id}] Connection error to upstream API: {e}")
                error_event = {
                    "type": "error",
                    "error": {
                        "type": "connection_error",
                        "message": f"Failed to connect to upstream API: {e}",
                    },
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
            except httpx.HTTPStatusError as e:
                logger.error(f"[{request_id}] HTTP error from upstream API: {e}")
                # Forward the upstream error response
                yield e.response.content
            except Exception as e:
                logger.error(f"[{request_id}] Unexpected streaming error: {e}")
                error_event = {
                    "type": "error",
                    "error": {"type": "api_error", "message": "Internal streaming error"},
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()
            finally:
                try:
                    _final_full_sse_data: str = (
                        full_sse_bytes.decode("utf-8") if full_sse_bytes else ""
                    )
                except UnicodeDecodeError:
                    logger.warning(
                        f"[{request_id}] Final SSE buffer contained invalid UTF-8; "
                        "downstream finalization will see only the well-formed prefix."
                    )
                    # Find the longest valid UTF-8 prefix via the
                    # incremental decoder; the lossy decoder kwargs
                    # are forbidden in this module per PR-A8 / P1-8.
                    decoder = __import__("codecs").getincrementaldecoder("utf-8")()
                    _final_full_sse_data = decoder.decode(bytes(full_sse_bytes), final=False)
                if not stream_complete:
                    logger.warning(
                        "[%s] Stream ended without terminal event — upstream may have truncated",
                        request_id,
                    )
                await self._finalize_stream_response(
                    body=body,
                    provider=provider,
                    outcome_provider=outcome_provider,
                    model=model,
                    request_id=request_id,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    optimization_latency=optimization_latency,
                    stream_state=stream_state,
                    start_time=start_time,
                    tags=tags,
                    pipeline_timing=pipeline_timing,
                    prefix_tracker=prefix_tracker,
                    original_messages=original_messages,
                    full_sse_data=_final_full_sse_data,
                    parsed_response=parsed_response,
                    client=client,
                    savings_metadata=savings_metadata,
                )

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers=forwarded_headers,
        )

    async def _stream_response_backend(
        self,
        backend: Any,
        body: dict,
        headers: dict,
        provider: str,
        model: str,
        request_id: str,
        original_tokens: int,
        optimized_tokens: int,
        tokens_saved: int,
        transforms_applied: list[str],
        tags: dict[str, str],
        optimization_latency: float,
        pipeline_timing: dict[str, float] | None = None,
        original_messages: list[dict] | None = None,
        savings_metadata: dict[str, dict[str, Any]] | None = None,
        response_headers: dict[str, str] | None = None,
        outcome_provider: str | None = None,
    ) -> StreamingResponse:
        """Stream response from a backend that yields Anthropic-format SSE events."""
        from fastapi.responses import StreamingResponse

        from cutctx.proxy.outcome import RequestOutcome

        client = classify_client(headers)

        start_time = time.time()
        stream_state: dict[str, Any] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "ttfb_ms": None,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_creation_ephemeral_5m_input_tokens": 0,
            "cache_creation_ephemeral_1h_input_tokens": 0,
        }

        async def generate():
            try:
                async for event in backend.stream_message(body, headers):
                    if stream_state["ttfb_ms"] is None:
                        stream_state["ttfb_ms"] = (time.time() - start_time) * 1000

                    if event.raw_sse:
                        yield event.raw_sse.encode()
                    else:
                        sse_line = f"event: {event.event_type}\ndata: {json.dumps(event.data)}\n\n"
                        yield sse_line.encode()

                    if event.event_type == "message_start":
                        msg = event.data.get("message", {})
                        usage = msg.get("usage", {})
                        if "input_tokens" in usage:
                            stream_state["input_tokens"] = usage["input_tokens"]
                        stream_state["cache_read_input_tokens"] = usage.get(
                            "cache_read_input_tokens", 0
                        )
                        stream_state["cache_creation_input_tokens"] = usage.get(
                            "cache_creation_input_tokens", 0
                        )
                        cw_5m, cw_1h = self._extract_anthropic_cache_ttl_metrics(usage)
                        stream_state["cache_creation_ephemeral_5m_input_tokens"] = cw_5m
                        stream_state["cache_creation_ephemeral_1h_input_tokens"] = cw_1h

                    if event.event_type == "message_delta":
                        usage = event.data.get("usage", {})
                        if "output_tokens" in usage:
                            stream_state["output_tokens"] = usage["output_tokens"]

                    if event.event_type == "error":
                        logger.error(f"[{request_id}] Backend stream error: {event.data}")

            except Exception as e:
                logger.error(f"[{request_id}] Backend streaming error: {e}")
                error_event = {
                    "type": "error",
                    "error": {"type": "api_error", "message": "Internal streaming error"},
                }
                yield f"event: error\ndata: {json.dumps(error_event)}\n\n".encode()

            finally:
                total_latency = (time.time() - start_time) * 1000
                _backend_name = outcome_provider or getattr(backend, "name", provider)
                _sc_avoided = 0
                _self_hosted_hits = 0
                _routing_tokens = 0
                _routing_usd = 0.0
                if savings_metadata:
                    _sc_avoided = int(
                        (savings_metadata.get("semantic_cache") or {}).get("tokens", 0) or 0
                    )
                    _self_hosted_hits = int(
                        (savings_metadata.get("prefix_cache_self_hosted") or {}).get("tokens", 0)
                        or 0
                    )
                    _routing_meta = savings_metadata.get("model_routing") or {}
                    _routing_tokens = int(_routing_meta.get("tokens_saved", 0) or 0)
                    _routing_usd = float(_routing_meta.get("usd_saved", 0.0) or 0.0)

                outcome = RequestOutcome.from_stream(
                    body=body,
                    provider=_backend_name,
                    model=model,
                    request_id=request_id,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    output_tokens=stream_state["output_tokens"],
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    total_latency_ms=total_latency,
                    overhead_ms=optimization_latency,
                    tags=tags,
                    client=client,
                    log_full_messages=getattr(self.config, "log_full_messages", False),
                    cache_read_tokens=stream_state["cache_read_input_tokens"],
                    cache_write_tokens=stream_state["cache_creation_input_tokens"],
                    cache_write_5m_tokens=stream_state["cache_creation_ephemeral_5m_input_tokens"],
                    cache_write_1h_tokens=stream_state["cache_creation_ephemeral_1h_input_tokens"],
                    ttfb_ms=stream_state["ttfb_ms"] or total_latency,
                    pipeline_timing=pipeline_timing,
                    original_messages=original_messages,
                    savings_metadata=savings_metadata,
                    semantic_cache_avoided_tokens=_sc_avoided,
                    self_hosted_prefix_cache_hits=_self_hosted_hits,
                    model_routing_tokens_saved=_routing_tokens,
                    model_routing_usd_saved=_routing_usd,
                )
                await self._record_request_outcome(outcome)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers=response_headers or {},
        )

    async def _stream_response_bedrock(
        self,
        body: dict,
        headers: dict,
        provider: str,
        model: str,
        request_id: str,
        original_tokens: int,
        optimized_tokens: int,
        tokens_saved: int,
        transforms_applied: list[str],
        tags: dict[str, str],
        optimization_latency: float,
        pipeline_timing: dict[str, float] | None = None,
        original_messages: list[dict] | None = None,
        savings_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> StreamingResponse:
        """Stream response from Bedrock backend with metrics tracking.

        Translates Bedrock streaming events to Anthropic SSE format.
        """
        assert self.anthropic_backend is not None
        return await self._stream_response_backend(
            backend=self.anthropic_backend,
            body=body,
            headers=headers,
            provider=provider,
            model=model,
            request_id=request_id,
            original_tokens=original_tokens,
            optimized_tokens=optimized_tokens,
            tokens_saved=tokens_saved,
            transforms_applied=transforms_applied,
            tags=tags,
            optimization_latency=optimization_latency,
            pipeline_timing=pipeline_timing,
            original_messages=original_messages,
            savings_metadata=savings_metadata,
            outcome_provider=self.anthropic_backend.name,
        )

    async def _stream_openai_via_backend(
        self,
        body: dict,
        headers: dict,
        model: str,
        request_id: str,
        start_time: float,
        original_tokens: int,
        optimized_tokens: int,
        tokens_saved: int,
        transforms_applied: list[str],
        tags: dict[str, str],
        optimization_latency: float,
        pipeline_timing: dict[str, float] | None = None,
        waste_signals: dict[str, int] | None = None,
        prefix_tracker: Any | None = None,
        optimized_messages: list[dict] | None = None,
        savings_metadata: dict[str, dict[str, Any]] | None = None,
        backend: Any | None = None,
        outcome_provider: str | None = None,
    ) -> StreamingResponse:
        """Stream OpenAI chat completion response from backend.

        Routes stream:true requests through the backend's
        ``stream_openai_message()``, yielding SSE events to the client.
        Buffers chunk bytes into ``stream_state["sse_buffer"]`` and
        incrementally drains complete events via
        :meth:`_parse_sse_usage_from_buffer` so the final usage frame
        (LiteLLM/OpenAI emits this only when the request included
        ``stream_options.include_usage=true``) yields ``prompt_tokens``,
        ``completion_tokens``, and
        ``prompt_tokens_details.cached_tokens``. OpenAI exposes no
        separate cache-write counter, so the write portion is inferred
        via :func:`_infer_openai_cache_write_tokens`. Memory stays O(1)
        because the buffer-parser consumes whole events as they arrive.

        ``prefix_tracker``/``optimized_messages`` carry the
        :class:`PrefixCacheTracker` for the session so cache stats from
        the FINAL usage frame can update the tracker for the next turn
        — mirroring the direct streaming path
        (``_stream_response``/``_finalize_stream_response``).

        NOTE: CCR request-level intercept on the streaming path is
        intentionally OUT OF SCOPE. Mirrors the Anthropic streaming
        path, which also does not buffer-and-rewrite mid-stream — doing
        so would require buffering the full response and would kill the
        streaming benefit. We do still record CCR retrieval feedback
        (cheap) for TOIN learning.
        """
        from fastapi.responses import StreamingResponse

        from cutctx.proxy.handlers.openai import _infer_openai_cache_write_tokens
        from cutctx.proxy.helpers import MAX_SSE_MIRROR_SIZE
        from cutctx.proxy.outcome import RequestOutcome

        backend = backend or self.anthropic_backend
        assert backend is not None
        client = classify_client(headers)

        async def generate():
            stream_state: dict[str, Any] = {
                "sse_buffer": bytearray(),
                "ttfb_ms": None,
                "input_tokens": None,
                "output_tokens": None,
                "cache_read_input_tokens": None,
                "cache_creation_input_tokens": None,
            }
            # Bytes-level mirror of the SSE stream so we can parse the
            # final response shape for CCR feedback after the stream
            # closes (cheap, no buffering of in-flight chunks back to
            # the client).
            full_sse_bytes = bytearray()
            full_sse_truncated = False

            def _absorb(usage: dict[str, int] | None) -> None:
                if not usage:
                    return
                for key in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                ):
                    if key in usage and not stream_state.get(key):
                        stream_state[key] = usage[key]

            try:
                async for sse_chunk in backend.stream_openai_message(body, headers):
                    if stream_state["ttfb_ms"] is None:
                        stream_state["ttfb_ms"] = (time.time() - start_time) * 1000
                    chunk_bytes = sse_chunk.encode() if isinstance(sse_chunk, str) else sse_chunk
                    stream_state["sse_buffer"].extend(chunk_bytes)
                    if self.config.ccr_inject_tool and not full_sse_truncated:
                        if len(full_sse_bytes) + len(chunk_bytes) <= MAX_SSE_MIRROR_SIZE:
                            full_sse_bytes.extend(chunk_bytes)
                        else:
                            logger.warning(
                                "[%s] SSE post-stream mirror exceeded %d bytes; skipping CCR feedback",
                                request_id,
                                MAX_SSE_MIRROR_SIZE,
                            )
                            full_sse_bytes.clear()
                            full_sse_truncated = True
                    _absorb(self._parse_sse_usage_from_buffer(stream_state, "openai"))
                    # Per-chunk fallback for upstreams that emit only
                    # ``completion_tokens`` and not a full usage frame.
                    parsed = _parse_completion_tokens_from_sse_chunk(chunk_bytes)
                    if parsed is not None and not stream_state["output_tokens"]:
                        stream_state["output_tokens"] = parsed
                    yield chunk_bytes
            except Exception as e:
                logger.error(f"[{request_id}] Backend streaming error: {e}")
                error_data = {
                    "error": {
                        "message": "Internal server error",
                        "type": "api_error",
                        "code": "backend_error",
                    }
                }
                yield f"data: {json.dumps(error_data)}\n\n".encode()
                yield b"data: [DONE]\n\n"
            finally:
                # Late-flush: if upstream truncated the stream mid-event,
                # the buffer parser hasn't seen the closing ``\n\n`` yet.
                # Mirror _finalize_stream_response: append the terminator
                # and drain anything still parseable.
                buf = stream_state["sse_buffer"]
                if len(buf) > 0:
                    buf.extend(b"\n\n")
                    _absorb(self._parse_sse_usage_from_buffer(stream_state, "openai"))

                # Mirror the non-streaming sibling (``_extract_responses_usage``
                # in handlers/openai.py): only infer cache metrics when
                # upstream actually reported a usage frame. Otherwise the
                # proxy-side ``optimized_tokens`` would masquerade as a
                # cache write — wrong, and indistinguishable from a real
                # hit-rate-zero call in the dashboard.
                upstream_input = stream_state["input_tokens"]
                output_tokens = stream_state["output_tokens"] or 0
                cache_read_tokens = stream_state["cache_read_input_tokens"] or 0
                # Prefer authoritative cache_creation_input_tokens from
                # Bedrock/Anthropic shape when present. Fall back to
                # inferring write count from total - read for OpenAI
                # shape (which has no separate write counter).
                cache_creation_input_tokens = stream_state.get("cache_creation_input_tokens") or 0
                if upstream_input is None:
                    cache_write_tokens = 0
                    uncached_input_tokens = 0
                    cache_inferred = False
                elif cache_creation_input_tokens > 0:
                    cache_write_tokens = cache_creation_input_tokens
                    uncached_input_tokens = max(
                        upstream_input - cache_read_tokens - cache_write_tokens, 0
                    )
                    cache_inferred = False
                else:
                    cache_write_tokens = _infer_openai_cache_write_tokens(
                        upstream_input, cache_read_tokens
                    )
                    uncached_input_tokens = max(upstream_input - cache_read_tokens, 0)
                    cache_inferred = True

                # Update prefix cache tracker for the next turn — mirrors
                # the non-streaming sibling. Done before outcome funnel
                # so prefix state is consistent regardless of metric
                # path.
                if prefix_tracker is not None:
                    tracker_messages = (
                        optimized_messages
                        if optimized_messages is not None
                        else body.get("messages", [])
                    )
                    prefix_tracker.update_from_response(
                        cache_read_tokens=cache_read_tokens,
                        cache_write_tokens=cache_write_tokens,
                        messages=tracker_messages,
                    )

                # CCR Feedback: record cutctx_retrieve tool calls so
                # TOIN learns which fields matter. Streaming path can't
                # do request-level intercept (would require buffering
                # the full stream), so we just close the feedback loop.
                if self.config.ccr_inject_tool and len(full_sse_bytes) > 0:
                    try:
                        full_sse_data = full_sse_bytes.decode("utf-8", errors="replace")
                        self._record_ccr_feedback_from_openai_sse(full_sse_data, request_id)
                    except Exception as e:
                        logger.debug(
                            f"[{request_id}] CCR feedback recording (openai stream) failed: {e}"
                        )

                total_latency = (time.time() - start_time) * 1000
                # Active-compression denominator for backend-routed
                # streaming. No per-message live-zone tracking is wired
                # for this path yet (see the non-streaming sibling in
                # openai.py for the same caveat), so use the full pre-
                # comp request size. This keeps active_savings_percent
                # in sync with proxy_savings_percent for this provider
                # instead of collapsing the dashboard headline to 0%.
                # Audit-Deep-2026-06-21: extract per-source
                # fields from savings_metadata so the typed
                # RequestOutcome fields are populated, not 0.
                _sc_avoided = 0
                _self_hosted_hits = 0
                _routing_tokens = 0
                _routing_usd = 0.0
                if savings_metadata:
                    _sc_avoided = int(
                        (savings_metadata.get("semantic_cache") or {}).get("tokens", 0) or 0
                    )
                    _self_hosted_hits = int(
                        (savings_metadata.get("prefix_cache_self_hosted") or {}).get("tokens", 0)
                        or 0
                    )
                    _routing_meta = savings_metadata.get("model_routing") or {}
                    _routing_tokens = int(_routing_meta.get("tokens_saved", 0) or 0)
                    _routing_usd = float(_routing_meta.get("usd_saved", 0.0) or 0.0)

                outcome = RequestOutcome.from_stream(
                    body=body,
                    provider=outcome_provider or backend.name,
                    model=model,
                    request_id=request_id,
                    original_tokens=original_tokens,
                    optimized_tokens=optimized_tokens,
                    output_tokens=output_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    total_latency_ms=total_latency,
                    overhead_ms=optimization_latency,
                    tags=tags,
                    client=client,
                    log_full_messages=getattr(self.config, "log_full_messages", False),
                    cache_read_tokens=cache_read_tokens,
                    cache_write_tokens=cache_write_tokens,
                    uncached_input_tokens=uncached_input_tokens,
                    cache_inferred=cache_inferred,
                    ttfb_ms=stream_state["ttfb_ms"] or total_latency,
                    pipeline_timing=pipeline_timing,
                    waste_signals=waste_signals,
                    savings_metadata=savings_metadata,
                    # Audit-Deep-2026-06-21: per-source fields.
                    semantic_cache_avoided_tokens=_sc_avoided,
                    self_hosted_prefix_cache_hits=_self_hosted_hits,
                    model_routing_tokens_saved=_routing_tokens,
                    model_routing_usd_saved=_routing_usd,
                )
                await self._record_request_outcome(outcome)

                if tokens_saved > 0:
                    logger.info(
                        f"[{request_id}] {model}: {original_tokens:,} → {optimized_tokens:,} "
                        f"(saved {tokens_saved:,} tokens) via {self.anthropic_backend.name} [stream]"
                    )

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
        )

    async def _stream_gemini_via_backend(
        self,
        body: dict,
        headers: dict,
        model: str,
        request_id: str,
        start_time: float,
        original_tokens: int,
        optimized_tokens: int,
        tokens_saved: int,
        transforms_applied: list[str],
        tags: dict[str, str],
        optimization_latency: float,
        pipeline_timing: dict[str, float] | None = None,
        savings_metadata: dict[str, dict[str, Any]] | None = None,
        backend: Any | None = None,
        outcome_provider: str | None = None,
    ) -> StreamingResponse:
        from fastapi.responses import StreamingResponse

        from cutctx.proxy.outcome import RequestOutcome

        backend = backend or self.anthropic_backend
        assert backend is not None
        client = classify_client(headers)

        async def generate():
            stream_state: dict[str, Any] = {
                # Keep the fallback stream telemetry contract aligned with
                # `_stream_openai_via_backend`: a successful first chunk is
                # the authoritative time-to-first-byte.  Without this entry,
                # the final outcome recording raised KeyError after Gemini had
                # already yielded its fallback response to the caller.
                "ttfb_ms": None,
                "input_tokens": None,
                "output_tokens": None,
                "cache_read_input_tokens": None,
                "cache_creation_input_tokens": 0,
            }

            def _absorb_usage(parsed: dict[str, Any]) -> None:
                usage = parsed.get("usage")
                if not isinstance(usage, dict):
                    return
                if stream_state["input_tokens"] is None:
                    stream_state["input_tokens"] = int(usage.get("prompt_tokens", 0) or 0)
                if stream_state["output_tokens"] is None:
                    stream_state["output_tokens"] = int(
                        usage.get("completion_tokens", 0) or 0
                    )
                prompt_details = usage.get("prompt_tokens_details") or {}
                if isinstance(prompt_details, dict) and stream_state["cache_read_input_tokens"] is None:
                    stream_state["cache_read_input_tokens"] = int(
                        prompt_details.get("cached_tokens", 0) or 0
                    )

            try:
                async for sse_chunk in backend.stream_openai_message(body, headers):
                    if stream_state["ttfb_ms"] is None:
                        stream_state["ttfb_ms"] = (time.time() - start_time) * 1000
                    chunk_bytes = sse_chunk.encode() if isinstance(sse_chunk, str) else sse_chunk
                    parsed_events = _iter_openai_sse_json_events(chunk_bytes)
                    emitted = False
                    for parsed in parsed_events:
                        _absorb_usage(parsed)
                        choices = parsed.get("choices")
                        if isinstance(choices, list):
                            text_parts: list[str] = []
                            function_calls: list[dict[str, Any]] = []
                            for choice in choices:
                                if not isinstance(choice, dict):
                                    continue
                                delta = choice.get("delta") or {}
                                if not isinstance(delta, dict):
                                    continue
                                content = delta.get("content")
                                if isinstance(content, str) and content:
                                    text_parts.append(content)
                                tool_calls = delta.get("tool_calls")
                                if isinstance(tool_calls, list):
                                    function_calls.extend(tc for tc in tool_calls if isinstance(tc, dict))
                            parts: list[dict[str, Any]] = []
                            if text_parts:
                                parts.append({"text": "".join(text_parts)})
                            for tool_call in function_calls:
                                function = tool_call.get("function") or {}
                                if not isinstance(function, dict):
                                    function = {}
                                arguments = function.get("arguments", {})
                                if isinstance(arguments, str):
                                    try:
                                        arguments = json.loads(arguments)
                                    except Exception:
                                        arguments = {"raw": arguments}
                                parts.append(
                                    {
                                        "functionCall": {
                                            "name": function.get("name", "function"),
                                            "args": arguments
                                            if isinstance(arguments, dict)
                                            else {"value": arguments},
                                        }
                                    }
                                )
                            if parts:
                                emitted = True
                                yield (
                                    "data: "
                                    + json.dumps(
                                        {
                                            "candidates": [
                                                {
                                                    "content": {
                                                        "role": "model",
                                                        "parts": parts,
                                                    }
                                                }
                                            ]
                                        }
                                    )
                                    + "\n\n"
                                ).encode()
                    if stream_state["input_tokens"] is not None or stream_state["output_tokens"] is not None:
                        usage_payload = {
                            "usageMetadata": {
                                "promptTokenCount": int(stream_state["input_tokens"] or 0),
                                "candidatesTokenCount": int(stream_state["output_tokens"] or 0),
                                "cachedContentTokenCount": int(
                                    stream_state["cache_read_input_tokens"] or 0
                                ),
                            }
                        }
                        yield ("data: " + json.dumps(usage_payload) + "\n\n").encode()
                        stream_state["input_tokens"] = None
                        stream_state["output_tokens"] = None
                        stream_state["cache_read_input_tokens"] = None
                    if not emitted and chunk_bytes.strip() == b"data: [DONE]":
                        continue
            except Exception as e:
                logger.error(f"[{request_id}] Gemini backend streaming error: {e}")
                error_payload = {
                    "error": {
                        "message": "Internal server error",
                        "code": 500,
                    }
                }
                yield ("data: " + json.dumps(error_payload) + "\n\n").encode()
            finally:
                total_latency = (time.time() - start_time) * 1000
                input_tokens = int(stream_state.get("input_tokens") or optimized_tokens)
                output_tokens = int(stream_state.get("output_tokens") or 0)
                cache_read_tokens = int(stream_state.get("cache_read_input_tokens") or 0)
                uncached_input_tokens = max(0, input_tokens - cache_read_tokens)
                _sc_avoided = 0
                _self_hosted_hits = 0
                _routing_tokens = 0
                _routing_usd = 0.0
                if savings_metadata:
                    _sc_avoided = int(
                        (savings_metadata.get("semantic_cache") or {}).get("tokens", 0) or 0
                    )
                    _self_hosted_hits = int(
                        (savings_metadata.get("prefix_cache_self_hosted") or {}).get("tokens", 0)
                        or 0
                    )
                    _routing_meta = savings_metadata.get("model_routing") or {}
                    _routing_tokens = int(_routing_meta.get("tokens_saved", 0) or 0)
                    _routing_usd = float(_routing_meta.get("usd_saved", 0.0) or 0.0)

                outcome = RequestOutcome.from_stream(
                    body=body,
                    provider=outcome_provider or backend.name,
                    model=model,
                    request_id=request_id,
                    original_tokens=original_tokens,
                    optimized_tokens=input_tokens,
                    output_tokens=output_tokens,
                    tokens_saved=tokens_saved,
                    transforms_applied=transforms_applied,
                    total_latency_ms=total_latency,
                    overhead_ms=optimization_latency,
                    tags=tags,
                    client=client,
                    log_full_messages=getattr(self.config, "log_full_messages", False),
                    cache_read_tokens=cache_read_tokens,
                    uncached_input_tokens=uncached_input_tokens,
                    ttfb_ms=stream_state["ttfb_ms"] or total_latency,
                    pipeline_timing=pipeline_timing,
                    savings_metadata=savings_metadata,
                    semantic_cache_avoided_tokens=_sc_avoided,
                    self_hosted_prefix_cache_hits=_self_hosted_hits,
                    model_routing_tokens_saved=_routing_tokens,
                    model_routing_usd_saved=_routing_usd,
                )
                await self._record_request_outcome(outcome)

        return StreamingResponse(generate(), media_type="text/event-stream")
