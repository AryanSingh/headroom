"""OpenAI handler mixin for CutctxProxy.

Contains all OpenAI Chat Completions, Responses API, and passthrough handlers.
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request
    from fastapi.responses import JSONResponse



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


class OpenAICompressMixin:
    async def handle_compress(self, request: Request) -> JSONResponse:
        """Compress messages without calling an LLM.

        POST /v1/compress
        Body: {"messages": [...], "model": "...", "config": {}}
        Returns compressed messages + metrics.
        """
        from fastapi.responses import JSONResponse

        from cutctx.proxy.helpers import _read_request_json

        # Check bypass header
        if request.headers.get("x-cutctx-bypass", "").lower() == "true":
            try:
                body = await _read_request_json(request)
            except (json.JSONDecodeError, ValueError) as e:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Invalid request body: {e!s}"},
                )
            messages = body.get("messages", [])
            return JSONResponse(
                {
                    "messages": messages,
                    "tokens_before": 0,
                    "tokens_after": 0,
                    "tokens_saved": 0,
                    "compression_ratio": 1.0,
                    "transforms_applied": [],
                    "ccr_hashes": [],
                }
            )

        try:
            body = await _read_request_json(request)
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "type": "invalid_request",
                        "message": "Invalid JSON in request body.",
                    }
                },
            )

        messages = body.get("messages")
        model = body.get("model")

        if messages is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "type": "invalid_request",
                        "message": "Missing required field: messages",
                    }
                },
            )

        if model is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "type": "invalid_request",
                        "message": "Missing required field: model",
                    }
                },
            )

        if not messages:
            return JSONResponse(
                {
                    "messages": [],
                    "tokens_before": 0,
                    "tokens_after": 0,
                    "tokens_saved": 0,
                    "compression_ratio": 1.0,
                    "transforms_applied": [],
                    "ccr_hashes": [],
                }
            )

        try:
            image_metrics: dict[str, int | float | bool | str] = {
                "images_optimized": 0,
                "tokens_before": 0,
                "tokens_after": 0,
                "tokens_saved": 0,
            }

            # Keep /v1/compress aligned with the main OpenAI chat path:
            # multimodal payloads should run through the image optimizer before
            # text compression, and the endpoint's token metrics should reflect
            # both layers rather than text-only router counts.
            if self.config.image_optimize:
                from cutctx.proxy.helpers import _get_image_compressor

                compressor = None
                try:
                    compressor = _get_image_compressor()
                    if compressor and compressor.has_images(messages):
                        messages = compressor.compress(messages, provider="openai")
                        if compressor.last_result:
                            image_metrics = {
                                "images_optimized": (
                                    compressor.last_result.compressed_tokens
                                    < compressor.last_result.original_tokens
                                ),
                                "tokens_before": compressor.last_result.original_tokens,
                                "tokens_after": compressor.last_result.compressed_tokens,
                                "tokens_saved": (
                                    compressor.last_result.original_tokens
                                    - compressor.last_result.compressed_tokens
                                ),
                                "technique": compressor.last_result.technique.value,
                                "confidence": compressor.last_result.confidence,
                            }
                finally:
                    if compressor and hasattr(compressor, "close"):
                        compressor.close()

            # Use OpenAI pipeline (messages are in OpenAI format from TS SDK)
            # Allow optional token_budget to override model's context limit
            # (used by OpenClaw compact() and other callers that need tighter budgets)
            token_budget = body.get("token_budget")
            context_limit = (
                token_budget
                if token_budget and isinstance(token_budget, int)
                else self.openai_provider.get_context_limit(model)
            )
            # Extract CompressConfig options from request body
            compress_config = body.get("config", {})
            compress_user_messages = compress_config.get("compress_user_messages", False)
            target_ratio = compress_config.get("target_ratio")
            protect_recent = compress_config.get("protect_recent")
            protect_analysis_context = compress_config.get("protect_analysis_context")

            pipeline_kwargs: dict = {"model_limit": context_limit}
            if compress_user_messages:
                pipeline_kwargs["compress_user_messages"] = True
            if target_ratio is not None:
                pipeline_kwargs["target_ratio"] = float(target_ratio)
            if protect_recent is not None:
                pipeline_kwargs["protect_recent"] = int(protect_recent)
            if protect_analysis_context is not None:
                pipeline_kwargs["protect_analysis_context"] = bool(protect_analysis_context)

            result = self.openai_pipeline.apply(
                messages=messages,
                model=model,
                **pipeline_kwargs,
            )

            total_tokens_before = result.tokens_before + int(image_metrics.get("tokens_before", 0))
            total_tokens_after = result.tokens_after + int(image_metrics.get("tokens_after", 0))
            total_tokens_saved = max(0, total_tokens_before - total_tokens_after)

            transforms_applied = list(result.transforms_applied)
            image_technique = image_metrics.get("technique")
            if image_technique and image_metrics.get("tokens_saved", 0):
                transforms_applied.append(f"image:{image_technique}")

            return JSONResponse(
                {
                    "messages": result.messages,
                    "tokens_before": total_tokens_before,
                    "tokens_after": total_tokens_after,
                    "tokens_saved": total_tokens_saved,
                    "compression_ratio": (
                        total_tokens_after / total_tokens_before
                        if total_tokens_before > 0
                        else 1.0
                    ),
                    "transforms_applied": transforms_applied,
                    "transforms_summary": result.transforms_summary,
                    "ccr_hashes": result.markers_inserted,
                    "image_metrics": image_metrics,
                }
            )
        except Exception as e:
            logger.exception("Compression failed: %s", e)
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "type": "compression_error",
                        "message": str(e),
                    }
                },
            )

