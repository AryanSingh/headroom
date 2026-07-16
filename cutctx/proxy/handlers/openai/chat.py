"""OpenAI handler mixin for CutctxProxy.

Contains all OpenAI Chat Completions, Responses API, and passthrough handlers.
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import TYPE_CHECKING, Any

from cutctx.proxy.helpers import (
    COMPRESSION_TIMEOUT_SECONDS,
    extract_tags,
)

if TYPE_CHECKING:
    from fastapi import Request
    from fastapi.responses import Response, StreamingResponse


import httpx

from cutctx.ccr.response_handler import CCRException
from cutctx.copilot_auth import apply_copilot_api_auth, build_copilot_upstream_url
from cutctx.pipeline import PipelineStage, summarize_routing_markers
from cutctx.proxy.auth_mode import classify_auth_mode, classify_client
from cutctx.proxy.compression_decision import CompressionDecision
from cutctx.proxy.cost import header_safe_transforms
from cutctx.proxy.outcome import RequestOutcome
from cutctx.proxy.savings_metadata import extract_savings_metadata, merge_savings_metadata

logger = logging.getLogger("cutctx.proxy")

_CLIENT_PROVIDER_MAP: dict[str, str] = {
    "claude-code": "claude",
    "claude-vscode": "claude",
    "claude-cli": "claude",
}


def _provider_for_client(client: str | None) -> str:
    """Map a detected client identifier to its provider label for metrics."""
    return _CLIENT_PROVIDER_MAP.get(client or "", "openai")


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
    _infer_openai_cache_write_tokens,
    _resolve_codex_routing_headers,
)


class OpenAIChatMixin:
    @staticmethod
    def _model_routing_chat_response_text(payload: dict[str, Any] | None) -> str:
        if not isinstance(payload, dict):
            return ""
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return ""
        message = choices[0].get("message", {})
        if not isinstance(message, dict):
            return ""
        content = message.get("content", "")
        return content if isinstance(content, str) else ""

    async def _maybe_model_routing_chat_shadow(
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
        client: str | None = None,
        telemetry_tags: dict[str, Any] | None = None,
    ) -> None:
        """Replay a sampled Chat Completions request on its requested model."""

        if (
            not routing_metadata
            or source_model == candidate_model
            or routing_metadata.get("target_model") != candidate_model
        ):
            return
        from cutctx.proxy.model_routing_evals import maybe_run_model_routing_shadow
        from cutctx.proxy.savings_tracker import estimate_request_cost_usd

        candidate_usage = candidate_json.get("usage", {}) if candidate_json else {}
        candidate_total = int(candidate_usage.get("prompt_tokens", 0) or 0)
        candidate_details = candidate_usage.get("prompt_tokens_details") or {}
        candidate_cached = int(candidate_details.get("cached_tokens", 0) or 0)
        candidate_uncached = max(0, candidate_total - candidate_cached)
        candidate_cost = estimate_request_cost_usd(
            candidate_model,
            input_tokens=candidate_total,
            cache_read_tokens=candidate_cached,
            uncached_input_tokens=candidate_uncached,
        )

        async def baseline_call() -> tuple[str, float]:
            baseline_body = copy.deepcopy(candidate_body)
            baseline_body["model"] = source_model
            response = await self._retry_request(
                "POST",
                url,
                headers,
                baseline_body,
                telemetry_tags=telemetry_tags,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"model-routing shadow returned HTTP {response.status_code}")
            payload = response.json()
            usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
            total = int(usage.get("prompt_tokens", 0) or 0)
            details = usage.get("prompt_tokens_details") or {}
            cached = int(details.get("cached_tokens", 0) or 0)
            cost = estimate_request_cost_usd(
                source_model,
                input_tokens=total,
                cache_read_tokens=cached,
                uncached_input_tokens=max(0, total - cached),
            )
            return self._model_routing_chat_response_text(payload), cost

        await maybe_run_model_routing_shadow(
            request_id=request_id,
            messages=messages,
            source_model=source_model,
            candidate_model=candidate_model,
            scorer=str(routing_metadata.get("scorer", "heuristic")),
            confidence=float(routing_metadata.get("confidence", 0.0) or 0.0),
            candidate_response=self._model_routing_chat_response_text(candidate_json),
            candidate_cost_usd=candidate_cost,
            baseline_call=baseline_call,
            category="openai_chat_completions",
            segments={
                "client": client or "openai",
                "task_type": "openai_chat_completions",
            },
        )

    async def handle_openai_chat(
        self,
        request: Request,
    ) -> Response | StreamingResponse:
        """Handle OpenAI /v1/chat/completions endpoint."""
        if not hasattr(self, "pipeline_extensions"):
            from cutctx.pipeline import PipelineExtensionManager

            self.pipeline_extensions = PipelineExtensionManager(discover=False)

        from fastapi import HTTPException
        from fastapi.responses import JSONResponse, Response

        from cutctx.ccr import CCRToolInjector
        from cutctx.proxy.helpers import (
            MAX_MESSAGE_ARRAY_LENGTH,
            MAX_REQUEST_BODY_SIZE,
            _read_request_json,
        )
        from cutctx.proxy.modes import is_cache_mode, is_token_mode
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
        # WS13 Batch Routing
        batch_router = getattr(self, "batch_router", None)
        if batch_router:
            batch_decision = batch_router.route(
                request_body=body,
                headers=request.headers,
                origin=request.headers.get("x-cutctx-origin"),
            )
            if batch_decision.action == "enqueued":
                return JSONResponse(
                    status_code=202,
                    content={
                        "id": batch_decision.queue_id,
                        "status": "in_progress",
                        "metadata": batch_decision.metadata,
                    },
                )

        model = body.get("model", "unknown")
        requested_model = model
        messages = body.get("messages", [])
        request_savings_metadata = extract_savings_metadata(
            request_headers=request.headers,
            body=body,
        )
        schema_savings_metadata = None
        from cutctx.proxy.canary_identity import resolve_canary_identity
        from cutctx.proxy.model_router import infer_request_capabilities, prepare_model_routing
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
        from cutctx.proxy.handlers.openai.responses import _sanitize_codex_responses_lite_body
        from cutctx.proxy.handlers.openai.utils import _has_codex_responses_lite_hint

        codex_responses_lite = _has_codex_responses_lite_hint(raw_request_headers)

        model, request_savings_metadata = prepare_model_routing(
            self,
            model,
            request_savings_metadata=request_savings_metadata,
            tool_calls=len(body.get("tools") or []),
            num_messages=len(messages),
            messages=messages,
            request_id=_canary_identity.value,
            client=classify_client(dict(request.headers.items())),
            assignment_identity_source=_canary_identity.source,
            assignment_sticky=_canary_identity.sticky,
            transport_provider="openai",
            implicit_downgrade_allowed=not (is_chatgpt_subscription or codex_responses_lite),
            required_capabilities=infer_request_capabilities(body),
        )
        body["model"] = model
        if codex_responses_lite:
            body, lite_stripped_fields = _sanitize_codex_responses_lite_body(body)
            if lite_stripped_fields:
                logger.info(
                    "[%s] /v1/chat/completions normalized Codex Responses Lite model: %s",
                    request_id,
                    ", ".join(lite_stripped_fields),
                )
        # Chat-completions upstreams reject the Responses-only reasoning
        # request override, so we intentionally do not forward it here.
        # The routing decision still applies; only the transport-incompatible
        # hint is dropped.
        original_client_messages = copy.deepcopy(messages)
        input_event = self.pipeline_extensions.emit(
            PipelineStage.INPUT_RECEIVED,
            operation="proxy.request",
            request_id=request_id,
            provider="openai",
            model=model,
            messages=messages,
            tools=body.get("tools"),
            metadata={"path": "/v1/chat/completions", "stream": body.get("stream", False)},
        )
        if input_event.messages is not None:
            messages = input_event.messages
            original_client_messages = copy.deepcopy(messages)
        if input_event.tools is not None:
            body["tools"] = input_event.tools

        # Validate message array size
        if len(messages) > MAX_MESSAGE_ARRAY_LENGTH:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": f"Message array too large ({len(messages)} messages). "
                        f"Maximum is {MAX_MESSAGE_ARRAY_LENGTH}.",
                        "type": "invalid_request_error",
                        "code": "invalid_request",
                    }
                },
            )

        stream = body.get("stream", False)

        # Bypass: skip ALL compression for explicit opt-out
        _bypass = self._cutctx_bypass_enabled(request.headers)
        if _bypass:
            logger.info(f"[{request_id}] Bypass: skipping compression (header)")

        if self.config.audio_optimize:
            from cutctx.transforms.audio_messages import compress_inline_audio_messages

            messages, inline_audio_metrics = compress_inline_audio_messages(
                messages,
                provider="openai",
            )
            if inline_audio_metrics.bytes_saved > 0:
                logger.info(
                    f"[{request_id}] Inline audio optimized "
                    f"({inline_audio_metrics.bytes_before} -> "
                    f"{inline_audio_metrics.bytes_after} bytes)"
                )

        # Image compression: tile alignment + ML-based technique routing.
        # Gated on ImageCompressionDecision — same value-type pattern
        # as CompressionDecision + MemoryDecision; locks bypass-respect
        # in tests so a future site can't drift.
        from cutctx.proxy.image_compression_decision import ImageCompressionDecision

        _image_decision = ImageCompressionDecision.decide(
            headers=request.headers, config=self.config, messages=messages
        )
        # tags is populated downstream at L1229 — defer apply_to_tags
        # to where the tags dict exists. The decision is captured here
        # so the conditional is uniform with the other gates.
        if _image_decision.should_compress:
            from cutctx.proxy.helpers import _get_image_compressor

            compressor = None
            try:
                compressor = _get_image_compressor()
                if compressor and compressor.has_images(messages):
                    messages = compressor.compress(messages, provider="openai")
                    if compressor.last_result:
                        logger.info(
                            f"[{request_id}] Image: {compressor.last_result.technique.value} "
                            f"({compressor.last_result.savings_percent:.0f}% saved, "
                            f"{compressor.last_result.original_tokens} → "
                            f"{compressor.last_result.compressed_tokens} tokens)"
                        )
            finally:
                if compressor and hasattr(compressor, "close"):
                    compressor.close()

        headers = dict(request.headers.items())
        headers.pop("host", None)
        headers.pop("content-length", None)
        # Strip accept-encoding so httpx negotiates its own encoding.
        # Cloudflare Workers forward "br, zstd" which OpenAI may honor;
        # if httpx lacks brotli support the response body is undecipherable → 502.
        headers.pop("accept-encoding", None)
        tags = extract_tags(headers)
        client = classify_client(headers)
        # Surface the image-compression decision (computed earlier) into
        # tags now that the tags dict exists. Same observability pattern
        # the funnel uses for passthrough_reason + memory_skip_reason.
        _image_decision.apply_to_tags(tags)
        # PR-A5 (P5-49): strip internal x-cutctx-* from upstream-bound
        # headers AFTER `_extract_tags` reads them. Inbound bypass gating
        # uses `request.headers.get(...)` above; memory user-id reads
        # `request.headers` below. From this point on, `headers` is the
        # upstream-bound copy.
        from cutctx.proxy.handlers.openai.utils import _strip_openai_internal_headers
        from cutctx.proxy.helpers import _strip_internal_headers, log_outbound_headers

        _pre_strip_count_chat = sum(1 for k in headers if k.lower().startswith("x-cutctx-"))
        headers = _strip_internal_headers(headers)
        headers = _strip_openai_internal_headers(headers)
        from cutctx.proxy.auth_keyring import inject_provider_authorization

        if inject_provider_authorization(headers, "openai"):
            logger.debug(
                "[%s] injected OpenAI Authorization from configured credentials", request_id
            )
        log_outbound_headers(
            forwarder="openai_chat_completions",
            stripped_count=_pre_strip_count_chat,
            request_id=request_id,
        )

        # Memory: Get user ID when memory is enabled. Reads `request.headers`
        # directly because `headers` was stripped of `x-cutctx-*` for the
        # upstream-bound copy (PR-A5).
        memory_user_id: str | None = None
        memory_request_ctx = None
        if self.memory_handler:
            memory_user_id = request.headers.get(
                "x-cutctx-user-id",
                os.environ.get("USER", os.environ.get("USERNAME", "default")),
            )
            # Per-project memory routing (GH #462). Built once per request
            # so every save/search/inject resolves to the same workspace.
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

        # Canonical memory-injection gate (parallels Anthropic). Pre-
        # PR-this the inline conjunction at the memory site silently
        # ignored `x-cutctx-bypass: true`, mutating request bytes
        # under the user's "don't touch my bytes" signal.
        from cutctx.proxy.helpers import get_memory_injection_mode
        from cutctx.proxy.memory_decision import MemoryDecision
        from cutctx.proxy.memory_query import MemoryQuery

        memory_decision = MemoryDecision.decide(
            headers=request.headers,
            memory_handler=self.memory_handler,
            memory_user_id=memory_user_id,
            mode_name=get_memory_injection_mode(),
            messages=messages,
        )
        memory_decision.apply_to_tags(tags)

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

        # Check cache
        if self.cache:
            cached = await self.cache.get(messages, model)
            if cached:
                self.pipeline_extensions.emit(
                    PipelineStage.INPUT_CACHED,
                    operation="proxy.request",
                    request_id=request_id,
                    provider="openai",
                    model=model,
                    messages=messages,
                    metadata={"cache_hit": True, "path": "/v1/chat/completions"},
                )
                # Response-cache hit: same pattern as the anthropic
                # cache-hit site. ``from_response_cache=True`` is the
                # distinct signal that the proxy served from its own
                # semantic cache (not upstream prompt cache).
                _cache_hit_latency = (time.time() - start_time) * 1000
                await self._record_request_outcome(
                    RequestOutcome(
                        request_id=request_id,
                        provider=_provider_for_client(client),
                        model=model,
                        original_tokens=0,
                        optimized_tokens=0,
                        output_tokens=0,
                        tokens_saved=0,
                        attempted_input_tokens=0,
                        from_response_cache=True,
                        semantic_cache_hit=True,
                        semantic_cache_avoided_tokens=cached.tokens_saved_per_hit,
                        # Self-hosted prefix cache and model routing do
                        # not apply to a response-cache hit: the proxy
                        # never reached the upstream. Set the fields
                        # explicitly so the funnel's per-source merge
                        # sees them rather than skipping the source.
                        self_hosted_prefix_cache_hits=0,
                        model_routing_tokens_saved=0,
                        model_routing_usd_saved=0.0,
                        memoization_hits=0,
                        memoization_tokens_saved=0,
                        output_optimization_tokens_saved=0,
                        total_latency_ms=_cache_hit_latency,
                        num_messages=len(messages),
                        tags=tags,
                        client=client,
                        savings_metadata=request_savings_metadata,
                    )
                )

                # Remove compression headers from cached response
                response_headers = dict(cached.response_headers)
                response_headers.pop("content-encoding", None)
                response_headers.pop("content-length", None)
                response_headers["x-cutctx-response-cache"] = "hit"
                response_headers["x-cutctx-cache-kind"] = "exact-match"

                if stream:
                    from fastapi.responses import StreamingResponse

                    async def generate():
                        if cached.is_streaming:
                            for chunk in cached.response_body.split(b"\n\n"):
                                if chunk.strip():
                                    yield chunk + b"\n\n"
                        else:
                            cached_dict = json.loads(cached.response_body)
                            chunks = self._response_to_sse(cached_dict, provider="openai")
                            for chunk in chunks:
                                yield chunk

                    return StreamingResponse(
                        generate(),
                        media_type="text/event-stream",
                        headers=response_headers,
                    )
                else:
                    return Response(content=cached.response_body, headers=response_headers)

        # Token counting
        tokenizer = get_tokenizer(model)
        original_tokens = tokenizer.count_messages(messages)

        # Hook: pre_compress
        _hook_biases = None
        if self.config.hooks:
            from cutctx.hooks import CompressContext

            _hook_ctx = CompressContext(model=model, provider="openai")
            try:
                messages = self.config.hooks.pre_compress(messages, _hook_ctx)
                _hook_biases = self.config.hooks.compute_biases(messages, _hook_ctx)
            except Exception as e:
                logger.debug(f"[{request_id}] Hook error: {e}")

        # Optimization
        transforms_applied = []
        pipeline_timing: dict[str, float] = {}
        waste_signals_dict: dict[str, int] | None = None
        optimized_messages = messages
        optimized_tokens = original_tokens

        # Intelligence pipeline: pre-compression (task extraction, profile, shared context)
        _intel_ctx = None
        try:
            from cutctx.proxy.intelligence_pipeline import IntelligencePipeline

            _intel_pipeline = getattr(self, "intelligence_pipeline", None)
            if _intel_pipeline is None:
                _intel_pipeline = IntelligencePipeline.from_config(self.config)
            else:
                _intel_pipeline.sync_from_config(self.config)
            if _intel_pipeline.any_enabled():
                _intel_ctx = _intel_pipeline.pre_compression(
                    messages,
                    model,
                    request_id,
                )
                _hook_biases = _intel_pipeline.merge_biases(
                    _hook_biases,
                    _intel_ctx.autopilot_biases,
                )
        except Exception as e:
            logger.debug(f"[{request_id}] Intelligence pre-compression failed: {e}")

        # Phase 3.3: provider-aware policy resolver (observation only
        # for now — the existing prefix tracker already protects the
        # cache-friendly prefix; the decision is recorded in /stats).
        try:
            from cutctx.savings import StrategyResolver, WorkloadClass

            _resolver = StrategyResolver(
                user_overrides=getattr(self.config, "policy_overrides", None) or None,
            )
            _policy_decision = _resolver.resolve(
                provider="openai",
                model=model,
                workload=(
                    WorkloadClass.CODING_AGENT
                    if getattr(self.config, "workload_class", "coding_agent") == "coding_agent"
                    else WorkloadClass.UNKNOWN
                ),
                request_shape={
                    "tool_result_count": sum(
                        1
                        for m in messages
                        if isinstance(m, dict)
                        and (m.get("role") == "tool" or m.get("role") == "function")
                    ),
                    "user_turn_count": sum(1 for m in messages if m.get("role") == "user"),
                },
            )
        except Exception as e:
            logger.debug(f"[{request_id}] Policy resolver failed: {e}")

        # Get prefix cache tracker for this session
        openai_session_id = self.session_tracker_store.compute_session_id(request, model, messages)

        # WS11 Tool Memoization Recording. ``memoization_hits`` /
        # ``memoization_tokens_saved`` are threaded into whichever
        # RequestOutcome construction site(s) exist below. Initialize
        # here so the funnel's WS11 attribution actually sees them
        # instead of staying permanently 0.
        memoization_hits = 0
        memoization_tokens_saved = 0
        if getattr(self, "memoizer", None):
            from cutctx.proxy.memoizer import record_tool_results_from_messages

            memoization_hits, memoization_tokens_saved = record_tool_results_from_messages(
                self.memoizer, messages, openai_session_id
            )

        openai_prefix_tracker = self.session_tracker_store.get_or_create(
            openai_session_id, "openai"
        )

        # PR-A6 (P5-50, preps P0-6): session-sticky `OpenAI-Beta` merge.
        # Same pattern as anthropic.py — read client value, union with
        # session-seen tokens, update tracker. WS auto-injection of
        # `responses_websockets=2026-02-06` lives on the WS handler;
        # chat-completions has no Cutctx-required tokens today, so the
        # merge effectively just makes the client value byte-stable
        # across turns.
        from cutctx.proxy.helpers import (
            get_session_beta_tracker as _get_session_beta_tracker_chat,
        )
        from cutctx.proxy.helpers import (
            log_beta_header_merge as _log_beta_header_merge_chat,
        )

        _client_openai_beta = headers.get("openai-beta")
        _client_openai_beta_count = (
            len([t for t in (_client_openai_beta or "").split(",") if t.strip()])
            if _client_openai_beta
            else 0
        )
        _sticky_openai_beta = _get_session_beta_tracker_chat().record_and_get_sticky_betas(
            provider="openai",
            session_id=openai_session_id,
            client_value=_client_openai_beta,
        )
        _sticky_openai_beta_count = (
            len([t for t in _sticky_openai_beta.split(",") if t.strip()])
            if _sticky_openai_beta
            else 0
        )
        if _sticky_openai_beta and _sticky_openai_beta != (_client_openai_beta or ""):
            headers["openai-beta"] = _sticky_openai_beta
        _log_beta_header_merge_chat(
            provider="openai",
            session_id=openai_session_id,
            client_betas_count=_client_openai_beta_count,
            sticky_betas_count=_sticky_openai_beta_count,
            cutctx_added=[],
            request_id=request_id,
        )

        openai_frozen_count = openai_prefix_tracker.get_frozen_message_count()
        if is_cache_mode(self.config.mode):
            openai_frozen_count = self._strict_previous_turn_frozen_count(
                original_client_messages,
                openai_frozen_count,
            )

        _compression_failed = False
        original_messages = messages  # Preserve for 400-retry fallback
        _decision = CompressionDecision.decide(
            headers=request.headers,
            config=self.config,
            usage_reporter=self.usage_reporter,
            messages=messages,
        )
        _decision.apply_to_tags(tags)
        if not _decision.should_compress:
            logger.info(f"[{request_id}] Compression skipped: reason={_decision.decline_reason}")
            self.metrics.record_compression_declined(_decision.decline_reason or "unknown")
        if _decision.should_compress:
            try:
                context_limit = self.openai_provider.get_context_limit(model)
                # Keep automatic chat compression aligned with the effective
                # proxy/profile target advertised by /health and /stats.
                # ContentRouter uses this to tune strategy aggressiveness.
                from cutctx.agent_savings import proxy_pipeline_kwargs

                pipeline_kwargs = proxy_pipeline_kwargs(self.config)
                target_ratio = pipeline_kwargs.get("target_ratio")

                # F2.1 c5/5: per-request CompressionPolicy. Hoisted out of
                # the is_token_mode branch so the else (non-token) branch
                # below can pass it through too. See the equivalent block
                # in handlers/anthropic.py.
                from cutctx.transforms.compression_policy import resolve_policy

                compression_policy = resolve_policy(getattr(request.state, "auth_mode", None))

                if is_token_mode(self.config.mode):
                    comp_cache = self._get_compression_cache(openai_session_id)

                    # Zone 1: Swap cached compressed versions
                    working_messages = comp_cache.apply_cached(messages)

                    # Re-freeze boundary
                    openai_frozen_count = comp_cache.compute_frozen_count(messages)

                    result = await self._run_compression_in_executor(
                        lambda: self.openai_pipeline.apply(
                            messages=working_messages,
                            model=model,
                            model_limit=context_limit,
                            context=extract_user_query(working_messages),
                            frozen_message_count=openai_frozen_count,
                            biases=_hook_biases,
                            compression_policy=compression_policy,
                            target_ratio=target_ratio,
                        ),
                        timeout=COMPRESSION_TIMEOUT_SECONDS,
                    )

                    if result.messages != working_messages:
                        comp_cache.update_from_result(messages, result.messages)

                    # Always use pipeline result in token mode
                    optimized_messages = result.messages
                    transforms_applied = result.transforms_applied
                    pipeline_timing = result.timing
                    # Keep original_tokens as the REAL original (pre-Zone-1-swap)
                    # so tokens_saved captures both Zone 1 + Zone 2 savings.
                    optimized_tokens = result.tokens_after
                else:
                    result = await self._run_compression_in_executor(
                        lambda: self.openai_pipeline.apply(
                            messages=messages,
                            model=model,
                            model_limit=context_limit,
                            context=extract_user_query(messages),
                            frozen_message_count=openai_frozen_count,
                            biases=_hook_biases,
                            compression_policy=compression_policy,
                            target_ratio=target_ratio,
                        ),
                        timeout=COMPRESSION_TIMEOUT_SECONDS,
                    )

                    if result.messages != messages:
                        optimized_messages = result.messages
                        transforms_applied = result.transforms_applied
                        pipeline_timing = result.timing
                        original_tokens = result.tokens_before
                        optimized_tokens = result.tokens_after

                if result.waste_signals:
                    waste_signals_dict = result.waste_signals.to_dict()
            except Exception as e:
                logger.warning(f"Optimization failed: {e}")
                # Flag compression failure for observability
                _compression_failed = True

        # Guard: if "optimization" inflated tokens, revert to originals
        if optimized_tokens > original_tokens:
            logger.warning(
                f"[{request_id}] Optimization inflated tokens "
                f"({original_tokens} -> {optimized_tokens}), reverting to original messages"
            )
            optimized_messages = original_messages
            optimized_tokens = original_tokens
            transforms_applied = []

        tokens_saved = original_tokens - optimized_tokens
        optimization_latency = (time.time() - start_time) * 1000

        routing_markers = summarize_routing_markers(transforms_applied)
        if routing_markers:
            routed_event = self.pipeline_extensions.emit(
                PipelineStage.INPUT_ROUTED,
                operation="proxy.request",
                request_id=request_id,
                provider="openai",
                model=model,
                messages=optimized_messages,
                metadata={
                    "routing_markers": routing_markers,
                    "transforms_applied": transforms_applied,
                },
            )
            if routed_event.messages is not None:
                optimized_messages = routed_event.messages
                optimized_tokens = tokenizer.count_messages(optimized_messages)
                tokens_saved = original_tokens - optimized_tokens

        compressed_event = self.pipeline_extensions.emit(
            PipelineStage.INPUT_COMPRESSED,
            operation="proxy.request",
            request_id=request_id,
            provider="openai",
            model=model,
            messages=optimized_messages,
            metadata={
                "tokens_before": original_tokens,
                "tokens_after": optimized_tokens,
                "transforms_applied": transforms_applied,
                # Read-only reference for recording extensions (probe
                # recorder); extensions must not mutate it.
                "original_messages": original_messages,
            },
        )
        if compressed_event.messages is not None:
            optimized_messages = compressed_event.messages
            optimized_tokens = tokenizer.count_messages(optimized_messages)
            tokens_saved = original_tokens - optimized_tokens

        # Hook: post_compress
        if self.config.hooks and tokens_saved > 0:
            from cutctx.hooks import CompressEvent

            try:
                self.config.hooks.post_compress(
                    CompressEvent(
                        tokens_before=original_tokens,
                        tokens_after=optimized_tokens,
                        tokens_saved=tokens_saved,
                        compression_ratio=tokens_saved / original_tokens
                        if original_tokens > 0
                        else 0,
                        transforms_applied=transforms_applied,
                        model=model,
                        provider="openai",
                    )
                )
            except Exception as e:
                logger.debug(f"[{request_id}] post_compress hook error: {e}")

        # CCR Tool Injection: Inject retrieval tool if compression occurred
        # OR if this session has previously done CCR (PR-B7 sticky-on).
        # See `cutctx/proxy/handlers/anthropic.py` and PR-B7 plan
        # `REALIGNMENT/04-phase-B-live-zone.md` for the rationale: once a
        # session has done CCR, the `cutctx_retrieve` tool stays
        # registered for every subsequent turn so the prompt cache
        # anchored on the previous turn's tool list never busts.
        tools = body.get("tools")
        _original_tools = tools  # Preserve for diagnostic / future retry
        if (
            self.config.ccr_inject_tool or self.config.ccr_inject_system_instructions
        ) and not _bypass:
            injector = CCRToolInjector(
                provider="openai",
                inject_tool=False,  # routed through sticky helper below
                inject_system_instructions=self.config.ccr_inject_system_instructions,
            )
            injector.scan_for_markers(optimized_messages)
            if self.config.ccr_inject_system_instructions and injector.has_compressed_content:
                optimized_messages = injector.inject_into_system_message(optimized_messages)

            if self.config.ccr_inject_tool:
                from cutctx.proxy.helpers import apply_session_sticky_ccr_tool

                tools, ccr_tool_injected = apply_session_sticky_ccr_tool(
                    provider="openai",
                    session_id=openai_session_id,
                    request_id=request_id,
                    existing_tools=tools,
                    has_compressed_content_this_turn=injector.has_compressed_content,
                )
                if ccr_tool_injected:
                    logger.debug(
                        f"[{request_id}] CCR: tool registered (session={openai_session_id}, "
                        f"compressed_this_turn={injector.has_compressed_content}, "
                        f"hashes_seen={len(injector.detected_hashes)})"
                    )

        if is_cache_mode(self.config.mode):
            optimized_messages, restored_count = self._restore_frozen_prefix(
                original_client_messages,
                optimized_messages,
                frozen_message_count=openai_frozen_count,
            )
            if restored_count > 0:
                logger.warning(
                    f"[{request_id}] Restored {restored_count} frozen prefix message(s) "
                    "to preserve cache stability (openai)"
                )

        # Memory: inject context and tools for OpenAI requests.
        #
        # PR-A3 follow-up to A2: memory context now routes exclusively to
        # the live-zone tail (latest user message), never via a system-level
        # prepend. The cache hot zone (system messages) is sacrosanct —
        # invariant I2. See REALIGNMENT/03-phase-A-lockdown.md PR-A3.
        memory_context_injected = False
        memory_tools_injected = False
        if memory_decision.inject:
            # Memory-handler is guaranteed present when inject=True.
            # Timeout-wrap (matches Anthropic /v1/messages and
            # /v1/responses) — pre-PR-this site was the only chat
            # path without one.
            try:
                if self.memory_handler.config.inject_context:
                    memory_context = await asyncio.wait_for(
                        self.memory_handler.search_and_format_context(
                            memory_user_id,
                            optimized_messages,
                            request_context=memory_request_ctx,
                            query=MemoryQuery.from_messages(optimized_messages),
                        ),
                        timeout=(self.config.anthropic_pre_upstream_memory_context_timeout_seconds),
                    )
                    if memory_context:
                        from cutctx.proxy.helpers import (
                            append_text_to_latest_user_chat_message,
                            get_memory_injection_mode,
                            log_memory_injection,
                        )

                        injection_mode = get_memory_injection_mode()
                        if injection_mode == "disabled":
                            log_memory_injection(
                                request_id=request_id,
                                session_id=None,
                                decision="skipped_disabled",
                                bytes_injected=0,
                                query=None,
                            )
                        else:
                            new_messages, bytes_appended = append_text_to_latest_user_chat_message(
                                optimized_messages, memory_context
                            )
                            if bytes_appended > 0:
                                optimized_messages = new_messages
                                memory_context_injected = True
                                log_memory_injection(
                                    request_id=request_id,
                                    session_id=None,
                                    decision="injected_live_zone_tail_chat",
                                    bytes_injected=bytes_appended,
                                    query=None,
                                )
                                logger.info(
                                    f"[{request_id}] Memory: Injected {bytes_appended} chars "
                                    f"into latest user message tail for user {memory_user_id}"
                                )
                            else:
                                log_memory_injection(
                                    request_id=request_id,
                                    session_id=None,
                                    decision="no_eligible_user_message",
                                    bytes_injected=0,
                                    query=None,
                                )

                # Inject memory tools — PR-A7 (P0-6) routes through
                # `apply_session_sticky_memory_tools` so byte-stable across turns.
                from cutctx.proxy.helpers import (
                    apply_session_sticky_memory_tools as _apply_sticky_mem_tools,
                )

                memory_tool_defs = (
                    self.memory_handler.compute_memory_tool_definitions("openai")
                    if self.memory_handler.config.inject_tools
                    else []
                )
                tools, mem_tools_injected = _apply_sticky_mem_tools(
                    provider="openai",
                    session_id=openai_session_id,
                    request_id=request_id,
                    existing_tools=tools,
                    memory_tools_to_inject=memory_tool_defs,
                    inject_this_turn=bool(self.memory_handler.config.inject_tools),
                )
                if mem_tools_injected:
                    memory_tools_injected = True
                    logger.info(f"[{request_id}] Memory: Injected memory tools (openai)")
            except Exception as e:
                logger.warning(f"[{request_id}] Memory injection failed: {e}")

        remembered_event = self.pipeline_extensions.emit(
            PipelineStage.INPUT_REMEMBERED,
            operation="proxy.request",
            request_id=request_id,
            provider="openai",
            model=model,
            messages=optimized_messages,
            tools=tools,
            metadata={
                "memory_context_injected": memory_context_injected,
                "memory_tools_injected": memory_tools_injected,
                "memory_skip_reason": memory_decision.skip_reason,
            },
        )
        if remembered_event.messages is not None:
            optimized_messages = remembered_event.messages
        if remembered_event.tools is not None:
            tools = remembered_event.tools

        # Intelligence pipeline: post-compression (dedup, context budget, profiles, cost)
        if _intel_ctx is not None:
            try:
                optimized_messages = _intel_pipeline.post_compression(
                    optimized_messages,
                    original_messages,
                    _intel_ctx,
                    request_id,
                    input_tokens=original_tokens,
                    output_tokens=0,
                )
            except Exception as e:
                logger.debug(f"[{request_id}] Intelligence post-compression failed: {e}")

        body["messages"] = optimized_messages
        if tools or _original_tools is not None:
            body["tools"] = tools

        try:
            from cutctx.proxy.schema_compress import (
                compress_tool_results,
                compress_tool_schemas,
            )
            from cutctx.proxy.tool_surface import (
                estimate_tool_scaffolding_tokens,
                slim_tool_surface,
            )

            _canary_arm = str(
                ((request_savings_metadata or {}).get("savings_canary") or {}).get("arm", "control")
            )

            tool_scaffolding_tokens = estimate_tool_scaffolding_tokens(
                body.get("tools"),
                tokenizer,
            )
            tool_surface_query = extract_user_query(optimized_messages) or extract_user_query(
                messages
            )
            tool_surface_result = slim_tool_surface(
                body.get("tools"),
                query=tool_surface_query,
                tokenizer=tokenizer,
                tool_choice=body.get("tool_choice"),
                messages=body.get("messages"),
            )
            if tool_surface_result.modified:
                body["tools"] = tool_surface_result.tools
                tools = tool_surface_result.tools
                tokens_saved += tool_surface_result.tokens_saved
                optimized_tokens = max(0, optimized_tokens - tool_surface_result.tokens_saved)
                schema_savings_metadata = merge_savings_metadata(
                    schema_savings_metadata,
                    {"api_surface_slimming": {"tokens": tool_surface_result.tokens_saved}},
                )
                transforms_applied = list(transforms_applied) + [
                    "openai:chat:tool_surface_slimming"
                ]

            schema_tokens_saved = 0
            if body.get("tools"):
                original_tools_payload = body["tools"]
                compacted_tools, tools_were_modified, tb, ta = compress_tool_schemas(
                    original_tools_payload,
                    max_description_length=120 if _canary_arm == "tool_api_slimming" else 200,
                    aggressive=_canary_arm == "tool_api_slimming",
                )
                if tools_were_modified:
                    body["tools"] = compacted_tools
                    tools = compacted_tools
                    transforms_applied = list(transforms_applied) + [
                        "openai:chat:tool_schema_compaction"
                    ]
                    try:
                        schema_tokens_saved = max(
                            0,
                            tokenizer.count_text(
                                json.dumps(original_tools_payload, ensure_ascii=False)
                            )
                            - tokenizer.count_text(json.dumps(compacted_tools, ensure_ascii=False)),
                        )
                    except Exception:
                        schema_tokens_saved = max(0, (tb - ta) // 4)
            if body.get("messages"):
                body["messages"] = compress_tool_results(
                    body["messages"],
                    max_array_items_for_positional=25 if _canary_arm == "mutable_tail" else 10,
                    min_fields_for_positional=2 if _canary_arm == "mutable_tail" else 3,
                )
                optimized_messages = body["messages"]
            if schema_tokens_saved > 0:
                tokens_saved += schema_tokens_saved
                optimized_tokens = max(0, optimized_tokens - schema_tokens_saved)
                schema_savings_metadata = merge_savings_metadata(
                    schema_savings_metadata,
                    {"tool_schema_compaction": {"tokens": schema_tokens_saved}},
                )
            residual_ghost_tokens = max(
                0,
                tool_scaffolding_tokens - tool_surface_result.tokens_saved - schema_tokens_saved,
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
        except Exception as e:
            logger.debug(f"[{request_id}] Schema compression failed: {e}")

        # WS10 Output Optimization
        output_optimization_tokens_saved = 0
        output_optimizer = getattr(self, "output_optimizer", None)
        if output_optimizer and output_optimizer.config.enabled:
            opt_decision = output_optimizer.optimize(
                request_body=body,
                session_id=openai_session_id,
            )
            if opt_decision.actions_applied:
                # Only apply if a lever actually fired (safety rails
                # already accounted for inside optimize()).
                body = opt_decision.request_body
                optimized_messages = body.get("messages", optimized_messages)
                transforms_applied = list(transforms_applied) + [
                    f"output_optimization:{lever}" for lever in opt_decision.actions_applied
                ]
                output_optimization_tokens_saved = opt_decision.estimated_tokens_saved
                logger.info(
                    f"[{request_id}] WS10 output optimization applied: "
                    f"{opt_decision.actions_applied}"
                )

        presend_event = self.pipeline_extensions.emit(
            PipelineStage.PRE_SEND,
            operation="proxy.request",
            request_id=request_id,
            provider="openai",
            model=model,
            messages=optimized_messages,
            tools=tools,
            headers=headers,
            metadata={"path": "/v1/chat/completions", "stream": stream},
        )
        if presend_event.messages is not None:
            optimized_messages = presend_event.messages
            body["messages"] = optimized_messages
        if presend_event.tools is not None:
            tools = presend_event.tools
            body["tools"] = tools
        if presend_event.headers is not None:
            headers = presend_event.headers
        optimized_tokens = tokenizer.count_messages(body["messages"])
        tokens_saved = original_tokens - optimized_tokens

        # Route through LiteLLM/any-llm backend if configured
        if self.anthropic_backend is not None:
            try:
                if stream:
                    self.pipeline_extensions.emit(
                        PipelineStage.POST_SEND,
                        operation="proxy.request",
                        request_id=request_id,
                        provider="openai",
                        model=model,
                        messages=body["messages"],
                        tools=tools,
                        metadata={"path": "/v1/chat/completions", "stream": True},
                    )
                    # Streaming: use stream_openai_message() → SSE events
                    return await self._stream_openai_via_backend(
                        body,
                        headers,
                        model,
                        request_id,
                        start_time,
                        original_tokens,
                        optimized_tokens,
                        tokens_saved,
                        transforms_applied,
                        tags,
                        optimization_latency,
                        pipeline_timing=pipeline_timing,
                        waste_signals=waste_signals_dict,
                        prefix_tracker=openai_prefix_tracker,
                        optimized_messages=optimized_messages,
                        savings_metadata=merge_savings_metadata(
                            request_savings_metadata,
                            schema_savings_metadata,
                        ),
                    )
                else:
                    # Non-streaming: use send_openai_message() → JSON
                    backend_response = await self.anthropic_backend.send_openai_message(
                        body, headers
                    )
                    self.pipeline_extensions.emit(
                        PipelineStage.POST_SEND,
                        operation="proxy.request",
                        request_id=request_id,
                        provider="openai",
                        model=model,
                        messages=body["messages"],
                        tools=tools,
                        response=backend_response.body,
                        metadata={
                            "path": "/v1/chat/completions",
                            "stream": False,
                            "status_code": backend_response.status_code,
                        },
                    )
                    self.pipeline_extensions.emit(
                        PipelineStage.RESPONSE_RECEIVED,
                        operation="proxy.request",
                        request_id=request_id,
                        provider="openai",
                        model=model,
                        response=backend_response.body,
                        metadata={
                            "path": "/v1/chat/completions",
                            "stream": False,
                            "status_code": backend_response.status_code,
                        },
                    )

                    if backend_response.error:
                        return JSONResponse(
                            status_code=backend_response.status_code,
                            content=backend_response.body,
                        )

                    # CCR Response Handling: intercept cutctx_retrieve
                    # tool calls server-side so a Bedrock/LiteLLM
                    # OpenAI-shape response doesn't propagate a tool_call
                    # the downstream caller (e.g. Strands) can't resolve.
                    # Mirrors the Anthropic handler block (anthropic.py
                    # ~1893-2034) but on the OpenAI provider shape.
                    #
                    # NO SILENT FALLBACK: per feedback_no_silent_fallbacks
                    # we re-raise on CCR errors instead of swallowing
                    # them. The Anthropic version still swallows for
                    # legacy reasons; align it in a follow-up.
                    # TODO(#realignment): align anthropic.py CCR block to
                    # re-raise on exception so both providers fail loud.
                    if (
                        self.ccr_response_handler
                        and backend_response.body
                        and backend_response.status_code == 200
                        and self.ccr_response_handler.has_ccr_tool_calls(
                            backend_response.body, "openai", session_id=openai_session_id
                        )
                    ):
                        logger.info(
                            f"[{request_id}] CCR: Detected retrieval tool call "
                            f"on backend path, handling via {self.anthropic_backend.name}"
                        )

                        # Continuation closure — delegates transport to
                        # the backend abstraction. We strip encoding
                        # headers for safety even though the backend
                        # owns transport (mirrors the Anthropic block).
                        async def api_call_fn(
                            msgs: list[dict[str, Any]],
                            tls: list[dict[str, Any]] | None,
                        ) -> dict[str, Any]:
                            continuation_body = {**body, "messages": msgs}
                            if tls is not None:
                                continuation_body["tools"] = tls

                            continuation_headers = {
                                k: v
                                for k, v in headers.items()
                                if k.lower()
                                not in (
                                    "content-encoding",
                                    "transfer-encoding",
                                    "accept-encoding",
                                    "content-length",
                                )
                            }

                            assert self.anthropic_backend is not None
                            logger.info(
                                f"[{request_id}] CCR: Issuing continuation via "
                                f"{self.anthropic_backend.name} backend "
                                f"({len(msgs)} messages)"
                            )
                            cont_resp = await self.anthropic_backend.send_openai_message(
                                continuation_body, continuation_headers
                            )
                            return cont_resp.body

                        try:
                            final_resp_json = await self.ccr_response_handler.handle_response(
                                backend_response.body,
                                optimized_messages,
                                tools,
                                api_call_fn,
                                provider="openai",
                                session_id=openai_session_id,
                            )
                            backend_response.body = final_resp_json
                            logger.info(
                                f"[{request_id}] CCR: Retrieval handled "
                                "successfully on backend path"
                            )
                        except Exception as e:
                            import traceback

                            logger.error(
                                f"[{request_id}] CCR: Response handling failed on "
                                f"backend path: {e}\n"
                                f"Traceback: {traceback.format_exc()}"
                            )
                            # No silent fallback — fail loud per
                            # feedback_no_silent_fallbacks.md.
                            raise CCRException(f"CCR handling failed: {e}") from e

                    # Extract usage from the FINAL backend body (after
                    # any CCR resolution) so the prefix tracker counts
                    # cache stats from the LAST upstream call.
                    total_latency = (time.time() - start_time) * 1000
                    usage = backend_response.body.get("usage", {})
                    output_tokens = usage.get("completion_tokens", 0)
                    total_input_tokens = usage.get("prompt_tokens", optimized_tokens)

                    # Cache stats: prefer the Anthropic/Bedrock top-level
                    # keys when present (authoritative). Fall back to
                    # OpenAI's `prompt_tokens_details.cached_tokens` only
                    # if the top-level keys are absent/zero.
                    cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
                    cache_creation_input_tokens = usage.get("cache_creation_input_tokens", 0) or 0
                    if cache_read_tokens == 0:
                        prompt_details = usage.get("prompt_tokens_details") or {}
                        cache_read_tokens = prompt_details.get("cached_tokens", 0) or 0

                    # Bedrock reports cache creation directly. Only infer
                    # when no explicit count is available.
                    if cache_creation_input_tokens > 0:
                        cache_write_tokens = cache_creation_input_tokens
                    else:
                        cache_write_tokens = _infer_openai_cache_write_tokens(
                            total_input_tokens,
                            cache_read_tokens,
                        )

                    openai_prefix_tracker.update_from_response(
                        cache_read_tokens=cache_read_tokens,
                        cache_write_tokens=cache_write_tokens,
                        messages=optimized_messages,
                    )

                    outcome_savings_metadata = extract_savings_metadata(
                        request_headers=request.headers,
                        response_headers=backend_response.headers,
                        body=body,
                    )
                    await self._record_request_outcome(
                        RequestOutcome(
                            request_id=request_id,
                            provider=self.anthropic_backend.name,
                            model=model,
                            original_tokens=original_tokens,
                            optimized_tokens=total_input_tokens,
                            output_tokens=output_tokens,
                            tokens_saved=tokens_saved,
                            attempted_input_tokens=total_input_tokens + tokens_saved,
                            self_hosted_prefix_cache_hits=int(
                                (outcome_savings_metadata or {})
                                .get("prefix_cache_self_hosted", {})
                                .get("tokens", 0)
                                or (outcome_savings_metadata or {})
                                .get("vllm_apc", {})
                                .get("tokens", 0)
                                or 0
                            ),
                            model_routing_tokens_saved=int(
                                (outcome_savings_metadata or {})
                                .get("model_routing", {})
                                .get("tokens", 0)
                                or 0
                            ),
                            model_routing_usd_saved=float(
                                (outcome_savings_metadata or {})
                                .get("model_routing", {})
                                .get("usd", 0.0)
                                or 0.0
                            ),
                            memoization_hits=memoization_hits,
                            memoization_tokens_saved=memoization_tokens_saved,
                            output_optimization_tokens_saved=output_optimization_tokens_saved,
                            total_latency_ms=total_latency,
                            overhead_ms=optimization_latency,
                            pipeline_timing=pipeline_timing,
                            waste_signals=waste_signals_dict,
                            transforms_applied=tuple(transforms_applied),
                            num_messages=len(body.get("messages", [])),
                            tags=tags or {},
                            request_messages=body.get("messages")
                            if getattr(self.config, "log_full_messages", False)
                            else None,
                            client=client,
                            savings_metadata=outcome_savings_metadata,
                        )
                    )

                    if tokens_saved > 0:
                        logger.info(
                            f"[{request_id}] {model}: {original_tokens:,} → {optimized_tokens:,} "
                            f"(saved {tokens_saved:,} tokens) via {self.anthropic_backend.name}"
                        )

                    return JSONResponse(
                        status_code=backend_response.status_code,
                        content=backend_response.body,
                    )
            except CCRException as e:
                import traceback

                traceback.print_exc()
                logger.error(f"[{request_id}] CCR error: {e}")
                # Preserve the original exception message to allow clients to debug
                # the specific CCR failure while signaling it's CCR-specific
                original_msg = str(e.__cause__) if e.__cause__ else str(e)
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "message": original_msg,
                            "type": "api_error",
                            "code": "ccr_error",
                        }
                    },
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                logger.error(f"[{request_id}] Backend error: {e}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "message": "Internal server error",
                            "type": "api_error",
                            "code": "backend_error",
                        }
                    },
                )

        # Direct OpenAI API (no backend configured)
        url = build_copilot_upstream_url(self.OPENAI_API_URL, "/v1/chat/completions")

        try:
            if stream:
                # Inject stream_options to get usage stats in streaming response
                # This allows accurate token counting instead of byte-based estimation
                if "stream_options" not in body:
                    body["stream_options"] = {"include_usage": True}
                elif isinstance(body.get("stream_options"), dict):
                    body["stream_options"]["include_usage"] = True

                self.pipeline_extensions.emit(
                    PipelineStage.POST_SEND,
                    operation="proxy.request",
                    request_id=request_id,
                    provider="openai",
                    model=model,
                    messages=body["messages"],
                    tools=tools,
                    metadata={"path": "/v1/chat/completions", "stream": True},
                )
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
                    pipeline_timing=pipeline_timing,
                    prefix_tracker=openai_prefix_tracker,
                    savings_metadata=request_savings_metadata,
                )
            else:
                headers = await apply_copilot_api_auth(headers, url=url)
                response = await self._retry_request(
                    "POST", url, headers, body, telemetry_tags=tags
                )
                self.pipeline_extensions.emit(
                    PipelineStage.POST_SEND,
                    operation="proxy.request",
                    request_id=request_id,
                    provider="openai",
                    model=model,
                    messages=body["messages"],
                    tools=tools,
                    response=response,
                    metadata={
                        "path": "/v1/chat/completions",
                        "stream": False,
                        "status_code": response.status_code,
                    },
                )
                self.pipeline_extensions.emit(
                    PipelineStage.RESPONSE_RECEIVED,
                    operation="proxy.request",
                    request_id=request_id,
                    provider="openai",
                    model=model,
                    response=response,
                    metadata={
                        "path": "/v1/chat/completions",
                        "stream": False,
                        "status_code": response.status_code,
                    },
                )

                # Full diagnostic dump on upstream errors (OpenAI handler)
                if response.status_code >= 400:
                    try:
                        err_body = response.json()
                        err_msg = err_body.get("error", {}).get("message", "")
                        err_type = err_body.get("error", {}).get("type", "")
                    except Exception:
                        err_body = {"raw": response.text[:2000]}
                        err_msg = str(response.text[:500])
                        err_type = "parse_error"

                    logger.warning(
                        f"[{request_id}] UPSTREAM_ERROR "
                        f"status={response.status_code} "
                        f"error_type={err_type} "
                        f"error_msg={err_msg!r} "
                        f"model={model} "
                        f"compressed={'yes' if transforms_applied else 'no'} "
                        f"transforms={transforms_applied} "
                        f"original_tokens={original_tokens} "
                        f"optimized_tokens={optimized_tokens} "
                        f"message_count={len(body.get('messages', []))} "
                        f"stream={stream}"
                    )

                    try:
                        from cutctx import paths as _hr_paths

                        debug_dir = _hr_paths.debug_400_dir()
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        debug_file = debug_dir / f"{ts}_{request_id}.json"

                        safe_headers = {}
                        for k, v in headers.items():
                            if k.lower() in ("x-api-key", "authorization"):
                                safe_headers[k] = v[:12] + "..." if v else ""
                            else:
                                safe_headers[k] = v

                        debug_payload = {
                            "request_id": request_id,
                            "timestamp": datetime.now().isoformat(),
                            "status_code": response.status_code,
                            "error_response": err_body,
                            "model": model,
                            "stream": stream,
                            "headers": safe_headers,
                            "compression": {
                                "was_compressed": bool(transforms_applied),
                                "transforms": transforms_applied,
                                "original_tokens": original_tokens,
                                "optimized_tokens": optimized_tokens,
                                "tokens_saved": tokens_saved,
                                "compression_failed": _compression_failed,
                            },
                            "tools_sent": body.get("tools"),
                            "tool_count": len(body.get("tools") or []),
                            "original_tool_count": len(_original_tools or []),
                            "messages_sent": body.get("messages"),
                            "message_count": len(body.get("messages", [])),
                            "original_messages": (
                                original_messages
                                if original_messages is not body.get("messages")
                                else "__same_as_sent__"
                            ),
                            "original_message_count": len(original_messages),
                            "system_prompt": body.get("system"),
                        }

                        with open(debug_file, "w") as f:
                            json.dump(debug_payload, f, indent=2, default=str)

                        logger.warning(f"[{request_id}] Full debug dump: {debug_file}")
                    except Exception as dump_err:
                        logger.error(f"[{request_id}] Failed to write debug dump: {dump_err}")

                total_latency = (time.time() - start_time) * 1000

                total_input_tokens = optimized_tokens  # fallback
                output_tokens = 0
                cache_read_tokens = 0
                resp_json = None
                try:
                    resp_json = response.json()
                    usage = resp_json.get("usage", {})
                    total_input_tokens = usage.get("prompt_tokens", optimized_tokens)
                    output_tokens = usage.get("completion_tokens", 0)
                    # OpenAI returns cached_tokens in prompt_tokens_details
                    # These are charged at 50% of the input price
                    prompt_details = usage.get("prompt_tokens_details") or {}
                    cache_read_tokens = prompt_details.get("cached_tokens", 0)
                except (KeyError, TypeError, AttributeError) as e:
                    logger.debug(
                        f"[{request_id}] Failed to extract cached tokens from OpenAI response: {e}"
                    )

                # Update prefix cache tracker for next turn
                cache_write_tokens = _infer_openai_cache_write_tokens(
                    total_input_tokens,
                    cache_read_tokens,
                )
                openai_prefix_tracker.update_from_response(
                    cache_read_tokens=cache_read_tokens,
                    cache_write_tokens=cache_write_tokens,
                    messages=optimized_messages,
                )

                # OpenAI has no write penalty — uncached = total - cached
                uncached_input_tokens = max(0, total_input_tokens - cache_read_tokens)

                if self.cost_tracker:
                    self.cost_tracker.record_tokens(
                        model,
                        tokens_saved,
                        optimized_tokens,
                        cache_read_tokens=cache_read_tokens,
                        cache_write_tokens=cache_write_tokens,
                        uncached_tokens=uncached_input_tokens,
                    )

                # Memory: handle memory tool calls in OpenAI Chat Completions response.
                # After executing tools, send a continuation request so the model
                # can produce a final user-facing response (not just tool_calls).
                if (
                    self.memory_handler
                    and memory_user_id
                    and resp_json
                    and response.status_code == 200
                    and self.memory_handler.has_memory_tool_calls(resp_json, "openai")
                ):
                    try:
                        tool_results = await self.memory_handler.handle_memory_tool_calls(
                            resp_json,
                            memory_user_id,
                            "openai",
                            request_context=memory_request_ctx,
                        )
                        if tool_results:
                            # Build continuation: original messages + assistant tool_calls + tool results
                            assistant_msg = resp_json.get("choices", [{}])[0].get("message", {})
                            continuation_messages = list(optimized_messages)
                            continuation_messages.append(assistant_msg)
                            continuation_messages.extend(tool_results)

                            continuation_body = {
                                **body,
                                "messages": continuation_messages,
                            }

                            cont_response = await self._retry_request(
                                "POST",
                                url,
                                headers,
                                continuation_body,
                                telemetry_tags=tags,
                            )
                            if cont_response.status_code == 200:
                                resp_json = cont_response.json()
                                response = cont_response

                            logger.info(
                                f"[{request_id}] Memory: Handled {len(tool_results)} "
                                f"tool call(s) with continuation for user {memory_user_id}"
                            )
                    except Exception as e:
                        logger.warning(f"[{request_id}] Memory tool handling failed: {e}")

                routing_metadata = (
                    request_savings_metadata.get("model_routing")
                    if isinstance(request_savings_metadata, dict)
                    else None
                )
                from cutctx.proxy.model_routing_evals import schedule_model_routing_shadow

                schedule_model_routing_shadow(
                    self._maybe_model_routing_chat_shadow(
                        request_id=request_id,
                        source_model=requested_model,
                        candidate_model=model,
                        url=url,
                        headers=headers,
                        candidate_body=body,
                        routing_metadata=routing_metadata,
                        messages=original_client_messages,
                        candidate_json=resp_json,
                        telemetry_tags=tags,
                        client=client,
                    )
                )

                # Cache
                if self.cache and response.status_code == 200:
                    await self.cache.set(
                        messages,
                        model,
                        response.content,
                        dict(response.headers),
                        total_input_tokens,
                    )

                # Capture Codex rate-limit window data from response headers
                from cutctx.subscription.codex_rate_limits import (
                    get_codex_rate_limit_state,
                )

                get_codex_rate_limit_state().update_from_headers(dict(response.headers))

                # Tag the metric/log with auth_mode + endpoint so the
                # dashboard can break down by client class (PAYG vs
                # subscription vs OAuth) without re-classifying.
                _auth_mode_chat = getattr(request.state, "auth_mode", None)
                _chat_log_tags = {
                    **(tags or {}),
                    "auth_mode": _auth_mode_chat.value if _auth_mode_chat else "payg",
                    "endpoint": "chat_completions",
                }

                # OpenAI Chat direct (non-backend) non-streaming.
                # Fallback denominator: full pre-comp size — see
                # equivalent note at the backend-routed sibling.
                from cutctx.proxy.helpers import compute_turn_id

                outcome_savings_metadata = merge_savings_metadata(
                    request_savings_metadata,
                    extract_savings_metadata(
                        request_headers=request.headers,
                        response_headers=response.headers,
                        body=body,
                    ),
                    schema_savings_metadata,
                )
                await self._record_request_outcome(
                    RequestOutcome(
                        request_id=request_id,
                        provider=_provider_for_client(client),
                        model=model,
                        original_tokens=original_tokens,
                        optimized_tokens=total_input_tokens,
                        output_tokens=output_tokens,
                        tokens_saved=tokens_saved,
                        attempted_input_tokens=total_input_tokens + tokens_saved,
                        cache_read_tokens=cache_read_tokens,
                        cache_write_tokens=cache_write_tokens,
                        uncached_input_tokens=uncached_input_tokens,
                        self_hosted_prefix_cache_hits=int(
                            (outcome_savings_metadata or {})
                            .get("prefix_cache_self_hosted", {})
                            .get("tokens", 0)
                            or (outcome_savings_metadata or {}).get("vllm_apc", {}).get("tokens", 0)
                            or 0
                        ),
                        model_routing_tokens_saved=int(
                            (outcome_savings_metadata or {})
                            .get("model_routing", {})
                            .get("tokens", 0)
                            or 0
                        ),
                        model_routing_usd_saved=float(
                            (outcome_savings_metadata or {})
                            .get("model_routing", {})
                            .get("usd", 0.0)
                            or 0.0
                        ),
                        memoization_hits=memoization_hits,
                        memoization_tokens_saved=memoization_tokens_saved,
                        output_optimization_tokens_saved=output_optimization_tokens_saved,
                        total_latency_ms=total_latency,
                        overhead_ms=optimization_latency,
                        pipeline_timing=pipeline_timing,
                        waste_signals=waste_signals_dict,
                        transforms_applied=tuple(transforms_applied),
                        num_messages=len(body.get("messages", [])),
                        tags=_chat_log_tags,
                        turn_id=compute_turn_id(model, body.get("system"), body.get("messages")),
                        request_messages=body.get("messages")
                        if getattr(self.config, "log_full_messages", False)
                        else None,
                        client=client,
                        savings_metadata=outcome_savings_metadata,
                    )
                )

                if tokens_saved > 0:
                    logger.info(
                        f"[{request_id}] {model}: {original_tokens:,} → {optimized_tokens:,} "
                        f"(saved {tokens_saved:,} tokens)"
                    )

                # Remove compression headers since httpx already decompressed the response
                response_headers = dict(response.headers)
                response_headers.pop("content-encoding", None)
                response_headers.pop("content-length", None)  # Length changed after decompression

                # Inject Cutctx compression metrics (for SaaS metering)
                response_headers["x-cutctx-tokens-before"] = str(original_tokens)
                response_headers["x-cutctx-tokens-after"] = str(optimized_tokens)
                response_headers["x-cutctx-tokens-saved"] = str(tokens_saved)
                response_headers["x-cutctx-model"] = model
                if transforms_applied:
                    response_headers["x-cutctx-transforms"] = ",".join(
                        header_safe_transforms(transforms_applied)
                    )
                if cache_read_tokens > 0:
                    response_headers["x-cutctx-cached"] = "true"
                if _compression_failed:
                    response_headers["x-cutctx-compression-failed"] = "true"

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response_headers,
                )
        except Exception as e:
            import traceback

            traceback.print_exc()

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
                    "[%s] Attempting OpenAI chat fallback to %s",
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
                    backend_response = await fallback_backend.send_openai_message(
                        body,
                        dict(headers),
                    )
                except Exception as fallback_exc:
                    logger.error(
                        "[%s] OpenAI chat fallback to %s failed: %s: %s",
                        request_id,
                        fallback_provider,
                        type(fallback_exc).__name__,
                        fallback_exc,
                    )
                else:
                    if not backend_response.error and backend_response.status_code < 500:
                        total_latency = (time.time() - start_time) * 1000
                        usage = backend_response.body.get("usage", {})
                        total_input_tokens = usage.get("prompt_tokens", optimized_tokens)
                        output_tokens = usage.get("completion_tokens", 0)
                        cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
                        cache_creation_input_tokens = (
                            usage.get("cache_creation_input_tokens", 0) or 0
                        )
                        if cache_read_tokens == 0:
                            prompt_details = usage.get("prompt_tokens_details") or {}
                            cache_read_tokens = prompt_details.get("cached_tokens", 0) or 0

                        if cache_creation_input_tokens > 0:
                            cache_write_tokens = cache_creation_input_tokens
                        else:
                            cache_write_tokens = _infer_openai_cache_write_tokens(
                                total_input_tokens,
                                cache_read_tokens,
                            )

                        openai_prefix_tracker.update_from_response(
                            cache_read_tokens=cache_read_tokens,
                            cache_write_tokens=cache_write_tokens,
                            messages=optimized_messages,
                        )

                        uncached_input_tokens = max(0, total_input_tokens - cache_read_tokens)
                        if self.cost_tracker:
                            self.cost_tracker.record_tokens(
                                model,
                                tokens_saved,
                                optimized_tokens,
                                cache_read_tokens=cache_read_tokens,
                                cache_write_tokens=cache_write_tokens,
                                uncached_tokens=uncached_input_tokens,
                            )

                        outcome_savings_metadata = extract_savings_metadata(
                            request_headers=request.headers,
                            response_headers=backend_response.headers,
                            body=body,
                        )
                        await self._record_request_outcome(
                            RequestOutcome(
                                request_id=request_id,
                                provider=fallback_provider,
                                model=model,
                                original_tokens=original_tokens,
                                optimized_tokens=total_input_tokens,
                                output_tokens=output_tokens,
                                tokens_saved=tokens_saved,
                                attempted_input_tokens=total_input_tokens + tokens_saved,
                                cache_read_tokens=cache_read_tokens,
                                uncached_input_tokens=uncached_input_tokens,
                                self_hosted_prefix_cache_hits=int(
                                    (outcome_savings_metadata or {})
                                    .get("prefix_cache_self_hosted", {})
                                    .get("tokens", 0)
                                    or (outcome_savings_metadata or {})
                                    .get("vllm_apc", {})
                                    .get("tokens", 0)
                                    or 0
                                ),
                                model_routing_tokens_saved=int(
                                    (outcome_savings_metadata or {})
                                    .get("model_routing", {})
                                    .get("tokens", 0)
                                    or 0
                                ),
                                model_routing_usd_saved=float(
                                    (outcome_savings_metadata or {})
                                    .get("model_routing", {})
                                    .get("usd", 0.0)
                                    or 0.0
                                ),
                                memoization_hits=memoization_hits,
                                memoization_tokens_saved=memoization_tokens_saved,
                                output_optimization_tokens_saved=output_optimization_tokens_saved,
                                total_latency_ms=total_latency,
                                overhead_ms=optimization_latency,
                                pipeline_timing=pipeline_timing,
                                waste_signals=waste_signals_dict,
                                transforms_applied=tuple(transforms_applied),
                                num_messages=len(body.get("messages", [])),
                                tags=tags,
                                client=client,
                                savings_metadata=outcome_savings_metadata,
                                request_messages=original_messages
                                if self.config.log_full_messages
                                else None,
                                compressed_messages=optimized_messages
                                if self.config.log_full_messages
                                else None,
                            )
                        )

                        response_headers = dict(backend_response.headers)
                        response_headers.pop("content-encoding", None)
                        response_headers.pop("content-length", None)
                        response_headers["x-cutctx-tokens-before"] = str(original_tokens)
                        response_headers["x-cutctx-tokens-after"] = str(total_input_tokens)
                        response_headers["x-cutctx-tokens-saved"] = str(tokens_saved)
                        response_headers["x-cutctx-model"] = model
                        if transforms_applied:
                            response_headers["x-cutctx-transforms"] = ",".join(
                                header_safe_transforms(transforms_applied)
                            )
                        if cache_read_tokens > 0:
                            response_headers["x-cutctx-cached"] = "true"
                        if _compression_failed:
                            response_headers["x-cutctx-compression-failed"] = "true"

                        return Response(
                            content=json.dumps(backend_response.body).encode("utf-8"),
                            status_code=backend_response.status_code,
                            headers=response_headers,
                            media_type="application/json",
                        )

            await self.metrics.record_failed(provider="openai")
            # Log full error details internally for debugging
            logger.error(f"[{request_id}] OpenAI request failed: {type(e).__name__}: {e}")
            # Return sanitized error message to client (don't expose internal details)
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
