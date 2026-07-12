"""OpenAI handler mixin for CutctxProxy.

Contains all OpenAI Chat Completions, Responses API, and passthrough handlers.
"""

from __future__ import annotations

import contextlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from cutctx.proxy.handlers.openai.utils import (
    _passthrough_model_from_path,
    _passthrough_usage_from_json,
)
from cutctx.proxy.helpers import (
    extract_tags,
)

if TYPE_CHECKING:
    from fastapi import Request
    from fastapi.responses import Response

import httpx

from cutctx.copilot_auth import apply_copilot_api_auth, build_copilot_upstream_url
from cutctx.proxy.auth_mode import classify_client
from cutctx.proxy.outcome import RequestOutcome
from cutctx.proxy.savings_metadata import extract_savings_metadata, merge_savings_metadata

logger = logging.getLogger("cutctx.proxy")

_OPENAI_RESPONSES_UNIT_CACHE_MAX_ENTRIES = 10_000
_OPENAI_RESPONSES_UNIT_CACHE_VERSION = "openai_responses_unit_v1"
_OPENAI_RESPONSES_UNIT_PARALLELISM_ENV = "CUTCTX_TOOL_OUTPUT_COMPRESSION_PARALLELISM"
_OPENAI_RESPONSES_UNIT_PARALLELISM_DEFAULT = 4
_OPENAI_RESPONSES_UNIT_PARALLELISM_MAX = 16
_OPENAI_RESPONSES_UNIT_CACHE_INIT_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR_LOCK = threading.RLock()
_OPENAI_RESPONSES_UNIT_EXECUTOR: ThreadPoolExecutor | None = None

from cutctx.proxy.handlers.openai.utils import *  # noqa: E402, F403


class OpenAIPassthroughMixin:
    async def handle_passthrough(
        self,
        request: Request,
        base_url: str,
        endpoint_name: str | None = None,
        provider: str | None = None,
    ) -> Response:
        """Pass through request unchanged.

        Args:
            request: The incoming request
            base_url: The upstream API base URL
            endpoint_name: Optional name for stats tracking (e.g., "models", "embeddings")
            provider: Optional provider name for stats (e.g., "openai", "anthropic", "gemini")
        """
        from fastapi.responses import Response

        if endpoint_name in {"streamGenerateContent", "streamRawPredict"} and provider:
            return await self._handle_streaming_passthrough(
                request=request,
                base_url=base_url,
                endpoint_name=endpoint_name,
                provider=provider,
            )

        start_time = time.time()
        path = request.url.path
        url = build_copilot_upstream_url(base_url, path)

        # Preserve query string parameters
        if request.url.query:
            url = f"{url}?{request.url.query}"

        headers = dict(request.headers.items())
        headers.pop("host", None)
        headers.pop("accept-encoding", None)
        client = classify_client(headers)
        tags = extract_tags(headers)
        request_savings_metadata = extract_savings_metadata(request_headers=headers)
        # PR-A5 (P5-49): strip internal x-cutctx-* before forwarding upstream.
        from cutctx.proxy.handlers.openai.utils import _strip_openai_internal_headers
        from cutctx.proxy.helpers import _strip_internal_headers, log_outbound_headers

        _pre_strip_count_pt = sum(1 for k in headers if k.lower().startswith("x-cutctx-"))
        headers = _strip_internal_headers(headers)
        headers = _strip_openai_internal_headers(headers)
        log_outbound_headers(
            forwarder="openai_passthrough",
            stripped_count=_pre_strip_count_pt,
            request_id=None,
        )

        body = await request.body()

        headers = await apply_copilot_api_auth(headers, url=url)
        try:
            response = await self.http_client.request(  # type: ignore[union-attr]
                method=request.method,
                url=url,
                headers=headers,
                content=body,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(
                "Passthrough request failed before upstream response: %s %s -> %s: %s",
                request.method,
                path,
                url,
                e,
            )
            return Response(
                content=json.dumps(
                    {
                        "error": {
                            "type": "connection_error",
                            "message": f"Failed to connect to upstream API: {e}",
                        }
                    }
                ),
                status_code=502,
                media_type="application/json",
            )

        # Remove compression headers since httpx already decompressed the response
        response_headers = dict(response.headers)
        response_headers.pop("content-encoding", None)
        response_headers.pop("content-length", None)  # Length changed after decompression

        # Passthrough request: forwarded upstream with no transforms.
        # Still recorded so dashboards see traffic on the passthrough
        # endpoints. When the upstream exposes provider-native usage
        # fields, normalize them so dashboard totals do not collapse to
        # zero for Vertex/Gemini and other pass-through endpoints.
        if endpoint_name and provider:
            latency_ms = (time.time() - start_time) * 1000
            request_id = await self._next_request_id()
            usage: dict[str, int] = {}
            if response.headers.get("content-type", "").lower().startswith("application/json"):
                try:
                    usage = _passthrough_usage_from_json(response.json())
                except (json.JSONDecodeError, ValueError, TypeError):
                    usage = {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            cache_write_tokens = usage.get("cache_creation_input_tokens", 0)
            uncached_input_tokens = max(0, input_tokens - cache_read_tokens - cache_write_tokens)
            await self._record_request_outcome(
                RequestOutcome(
                    request_id=request_id,
                    provider=provider,
                    model=_passthrough_model_from_path(path, endpoint_name),
                    original_tokens=input_tokens,
                    optimized_tokens=input_tokens,
                    output_tokens=output_tokens,
                    tokens_saved=0,
                    attempted_input_tokens=input_tokens,
                    cache_read_tokens=cache_read_tokens,
                    cache_write_tokens=cache_write_tokens,
                    uncached_input_tokens=uncached_input_tokens,
                    total_latency_ms=latency_ms,
                    tags=tags,
                    client=client,
                    savings_metadata=merge_savings_metadata(
                        request_savings_metadata,
                        extract_savings_metadata(response_headers=response.headers),
                    ),
                )
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
        )

    async def _handle_streaming_passthrough(
        self,
        request: Request,
        base_url: str,
        endpoint_name: str,
        provider: str,
    ) -> Response:
        """Stream pass-through responses without buffering the upstream body."""
        from fastapi.responses import Response, StreamingResponse

        from cutctx.proxy.helpers import MAX_SSE_BUFFER_SIZE

        start_time = time.time()
        path = request.url.path
        url = build_copilot_upstream_url(base_url, path)
        if request.url.query:
            url = f"{url}?{request.url.query}"

        headers = dict(request.headers.items())
        headers.pop("host", None)
        headers.pop("accept-encoding", None)
        client = classify_client(headers)
        tags = extract_tags(headers)
        request_savings_metadata = extract_savings_metadata(request_headers=headers)

        from cutctx.proxy.helpers import _strip_internal_headers, log_outbound_headers

        _pre_strip_count_pt = sum(1 for k in headers if k.lower().startswith("x-cutctx-"))
        headers = _strip_internal_headers(headers)
        log_outbound_headers(
            forwarder="streaming_passthrough",
            stripped_count=_pre_strip_count_pt,
            request_id=None,
        )

        body = await request.body()
        headers = await apply_copilot_api_auth(headers, url=url)
        request_id = await self._next_request_id()
        stream_provider = "gemini" if provider == "vertex:google" else "anthropic"
        stream_state: dict[str, Any] = {
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_creation_ephemeral_5m_input_tokens": 0,
            "cache_creation_ephemeral_1h_input_tokens": 0,
            "total_bytes": 0,
            "sse_buffer": bytearray(),
            "ttfb_ms": None,
        }

        assert self.http_client is not None, "http_client must be initialized before streaming"
        try:
            upstream_request = self.http_client.build_request(
                request.method,
                url,
                headers=headers,
                content=body,
            )
            upstream_response = await self.http_client.send(upstream_request, stream=True)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(
                "Streaming passthrough failed before upstream response: %s %s -> %s: %s",
                request.method,
                path,
                url,
                e,
            )
            return Response(
                content=json.dumps(
                    {
                        "error": {
                            "type": "connection_error",
                            "message": f"Failed to connect to upstream API: {e}",
                        }
                    }
                ),
                status_code=502,
                media_type="application/json",
            )

        response_headers = dict(upstream_response.headers)
        response_headers.pop("content-length", None)
        response_headers.pop("transfer-encoding", None)
        response_headers.pop("connection", None)
        response_headers.pop("content-encoding", None)

        if upstream_response.status_code >= 400:
            try:
                error_content = await upstream_response.aread()
            finally:
                await upstream_response.aclose()
            return Response(
                content=error_content,
                status_code=upstream_response.status_code,
                headers=response_headers,
            )

        def _absorb_usage(usage: dict[str, int] | None) -> None:
            if not usage:
                return
            if "input_tokens" in usage:
                stream_state["input_tokens"] = usage["input_tokens"]
            if "output_tokens" in usage:
                stream_state["output_tokens"] = usage["output_tokens"]
            if "cache_read_input_tokens" in usage:
                stream_state["cache_read_input_tokens"] = usage["cache_read_input_tokens"]
            if "cache_creation_input_tokens" in usage:
                stream_state["cache_creation_input_tokens"] = usage["cache_creation_input_tokens"]
            if "cache_creation_ephemeral_5m_input_tokens" in usage:
                stream_state["cache_creation_ephemeral_5m_input_tokens"] = usage[
                    "cache_creation_ephemeral_5m_input_tokens"
                ]
            if "cache_creation_ephemeral_1h_input_tokens" in usage:
                stream_state["cache_creation_ephemeral_1h_input_tokens"] = usage[
                    "cache_creation_ephemeral_1h_input_tokens"
                ]

        async def generate():
            try:
                async with contextlib.aclosing(upstream_response) as response:
                    async for chunk in response.aiter_bytes():
                        if stream_state["ttfb_ms"] is None:
                            stream_state["ttfb_ms"] = (time.time() - start_time) * 1000
                        stream_state["total_bytes"] += len(chunk)
                        stream_state["sse_buffer"].extend(chunk)
                        if len(stream_state["sse_buffer"]) > MAX_SSE_BUFFER_SIZE:
                            tail = bytes(stream_state["sse_buffer"][-MAX_SSE_BUFFER_SIZE // 2 :])
                            stream_state["sse_buffer"] = bytearray(tail)

                        _absorb_usage(
                            self._parse_sse_usage_from_buffer(stream_state, stream_provider)
                        )
                        yield chunk
            finally:
                buf = stream_state["sse_buffer"]
                if len(buf) > 0:
                    buf.extend(b"\n\n")
                    _absorb_usage(self._parse_sse_usage_from_buffer(stream_state, stream_provider))

                input_tokens = stream_state["input_tokens"] or 0
                output_tokens = stream_state["output_tokens"] or 0
                cache_read_tokens = stream_state["cache_read_input_tokens"] or 0
                cache_write_tokens = stream_state["cache_creation_input_tokens"] or 0
                total_latency_ms = (time.time() - start_time) * 1000
                uncached_input_tokens = max(
                    0,
                    input_tokens - cache_read_tokens - cache_write_tokens,
                )
                await self._record_request_outcome(
                    RequestOutcome(
                        request_id=request_id,
                        provider=provider,
                        model=_passthrough_model_from_path(path, endpoint_name),
                        original_tokens=input_tokens,
                        optimized_tokens=input_tokens,
                        output_tokens=output_tokens,
                        tokens_saved=0,
                        attempted_input_tokens=input_tokens,
                        cache_read_tokens=cache_read_tokens,
                        cache_write_tokens=cache_write_tokens,
                        cache_write_5m_tokens=stream_state[
                            "cache_creation_ephemeral_5m_input_tokens"
                        ],
                        cache_write_1h_tokens=stream_state[
                            "cache_creation_ephemeral_1h_input_tokens"
                        ],
                        uncached_input_tokens=uncached_input_tokens,
                        total_latency_ms=total_latency_ms,
                        ttfb_ms=stream_state["ttfb_ms"] or total_latency_ms,
                        tags=tags,
                        client=client,
                        savings_metadata=request_savings_metadata,
                    )
                )

        media_type = upstream_response.headers.get("content-type") or "text/event-stream"
        return StreamingResponse(
            generate(),
            status_code=upstream_response.status_code,
            headers=response_headers,
            media_type=media_type,
        )
