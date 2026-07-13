"""OpenAI compression-only endpoint support."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from cutctx.proxy.handlers.openai.utils import *  # noqa: F403

if TYPE_CHECKING:
    from fastapi import Request
    from fastapi.responses import JSONResponse


logger = logging.getLogger("cutctx.proxy")


class OpenAICompressMixin:
    async def handle_compress(self, request: Request) -> JSONResponse:
        """Compress messages without making an upstream model call."""
        from fastapi.responses import JSONResponse

        from cutctx.proxy.helpers import _read_request_json

        # Bypass keeps the endpoint useful as a pure pass-through shaping surface.
        if request.headers.get("x-cutctx-bypass", "").lower() == "true":
            try:
                body = await _read_request_json(request)
            except (json.JSONDecodeError, ValueError) as exc:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Invalid request body: {exc!s}"},
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
                    "transforms_summary": {},
                    "ccr_hashes": [],
                    "image_metrics": {
                        "images_optimized": 0,
                        "tokens_before": 0,
                        "tokens_after": 0,
                        "tokens_saved": 0,
                    },
                    "audio_metrics": {
                        "audio_blocks_seen": 0,
                        "audio_blocks_optimized": 0,
                        "bytes_before": 0,
                        "bytes_after": 0,
                        "bytes_saved": 0,
                    },
                    "diagnostics": {
                        "profile": "bypass",
                        "warnings": [],
                        "timing_ms": {},
                        "content_router": {},
                    },
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
                    "transforms_summary": {},
                    "ccr_hashes": [],
                    "image_metrics": {
                        "images_optimized": 0,
                        "tokens_before": 0,
                        "tokens_after": 0,
                        "tokens_saved": 0,
                    },
                    "audio_metrics": {
                        "audio_blocks_seen": 0,
                        "audio_blocks_optimized": 0,
                        "bytes_before": 0,
                        "bytes_after": 0,
                        "bytes_saved": 0,
                    },
                    "diagnostics": {
                        "profile": "empty",
                        "warnings": [],
                        "timing_ms": {},
                        "content_router": {},
                    },
                }
            )

        try:
            image_metrics: dict[str, int | float | bool | str] = {
                "images_optimized": 0,
                "tokens_before": 0,
                "tokens_after": 0,
                "tokens_saved": 0,
            }

            audio_metrics: dict[str, int] = {
                "audio_blocks_seen": 0,
                "audio_blocks_optimized": 0,
                "bytes_before": 0,
                "bytes_after": 0,
                "bytes_saved": 0,
            }

            if self.config.audio_optimize:
                from cutctx.transforms.audio_messages import compress_inline_audio_messages

                messages, inline_audio = compress_inline_audio_messages(
                    messages,
                    provider="openai",
                )
                audio_metrics = {
                    "audio_blocks_seen": inline_audio.audio_blocks_seen,
                    "audio_blocks_optimized": inline_audio.audio_blocks_optimized,
                    "bytes_before": inline_audio.bytes_before,
                    "bytes_after": inline_audio.bytes_after,
                    "bytes_saved": inline_audio.bytes_saved,
                }

            # Keep /v1/compress aligned with the main OpenAI chat path:
            # multimodal payloads should run through image optimization first.
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

            token_budget = body.get("token_budget")
            context_limit = (
                token_budget
                if token_budget and isinstance(token_budget, int)
                else self.openai_provider.get_context_limit(model)
            )

            compress_config = body.get("config", {}) or {}
            compression_profile = (
                str(compress_config.get("profile", "max_savings") or "max_savings").strip().lower()
            )
            compress_user_messages = compress_config.get("compress_user_messages")
            compress_assistant_text_blocks = compress_config.get("compress_assistant_text_blocks")
            target_ratio = compress_config.get("target_ratio")
            protect_recent = compress_config.get("protect_recent")
            protect_analysis_context = compress_config.get("protect_analysis_context")
            min_ratio_override = compress_config.get("min_ratio_override")

            # /v1/compress is an explicit compaction surface, so default it to a
            # more aggressive acceptance policy than the live proxy path. Named
            # agent profiles are accepted here too so users can compare balanced
            # vs. high-savings behavior without starting a proxy subprocess.
            if compression_profile == "agent-90":
                from cutctx.agent_savings import get_agent_savings_profile

                profile = get_agent_savings_profile(compression_profile)
                if compress_user_messages is None:
                    compress_user_messages = profile.compress_user_messages
                if protect_recent is None:
                    protect_recent = profile.protect_recent
                if protect_analysis_context is None:
                    protect_analysis_context = profile.protect_analysis_context
                if target_ratio is None:
                    target_ratio = profile.target_ratio
                pipeline_kwargs_profile = {
                    "compress_system_messages": profile.compress_system_messages,
                    "min_tokens_to_compress": profile.min_tokens_to_compress,
                    "max_items_after_crush": profile.max_items_after_crush,
                    "smart_crusher_with_compaction": profile.smart_crusher_with_compaction,
                    "force_kompress": profile.force_kompress,
                }
            else:
                pipeline_kwargs_profile = {}

            if compression_profile in {"max_savings", "max-savings"}:
                if compress_user_messages is None:
                    compress_user_messages = True
                if compress_assistant_text_blocks is None:
                    compress_assistant_text_blocks = True
                if protect_recent is None:
                    protect_recent = 0
                if protect_analysis_context is None:
                    protect_analysis_context = False
                if min_ratio_override is None:
                    min_ratio_override = 0.99
                pipeline_kwargs_profile["compression_mode"] = "aggressive"
            else:
                if compress_user_messages is None:
                    compress_user_messages = False
                if compress_assistant_text_blocks is None:
                    compress_assistant_text_blocks = False

            pipeline_kwargs: dict[str, Any] = {"model_limit": context_limit}
            pipeline_kwargs.update(pipeline_kwargs_profile)
            if compress_user_messages:
                pipeline_kwargs["compress_user_messages"] = True
            if compress_assistant_text_blocks:
                pipeline_kwargs["compress_assistant_text_blocks"] = True
            if target_ratio is not None:
                pipeline_kwargs["target_ratio"] = float(target_ratio)
            if protect_recent is not None:
                pipeline_kwargs["protect_recent"] = int(protect_recent)
            if protect_analysis_context is not None:
                pipeline_kwargs["protect_analysis_context"] = bool(protect_analysis_context)
            if min_ratio_override is not None:
                pipeline_kwargs["min_ratio_override"] = float(min_ratio_override)

            result = self.openai_pipeline.apply(
                messages=messages,
                model=model,
                **pipeline_kwargs,
            )

            total_tokens_before = result.tokens_before + int(image_metrics.get("tokens_before", 0))
            total_tokens_after = result.tokens_after + int(image_metrics.get("tokens_after", 0))
            total_tokens_saved = max(0, total_tokens_before - total_tokens_after)
            pipeline_tokens_saved = max(0, result.tokens_before - result.tokens_after)
            image_tokens_saved = int(image_metrics.get("tokens_saved", 0) or 0)

            transforms_applied = list(result.transforms_applied)
            if audio_metrics.get("bytes_saved", 0) > 0:
                transforms_applied.append("audio:inline_wav")
            image_technique = image_metrics.get("technique")
            if image_technique and image_metrics.get("tokens_saved", 0):
                transforms_applied.append(f"image:{image_technique}")

            content_router_diag: dict[str, Any] = {}
            if isinstance(result.diagnostics, dict):
                content_router_diag = dict(result.diagnostics.get("content_router") or {})

            diagnostics = {
                "profile": compression_profile,
                "warnings": list(result.warnings),
                "timing_ms": dict(result.timing),
                "content_router": content_router_diag,
            }
            if total_tokens_saved <= 0:
                diagnostics["why_no_savings"] = (
                    content_router_diag.get("summary")
                    or "No transform met the current acceptance threshold."
                )

            response_payload = {
                "messages": result.messages,
                "tokens_before": total_tokens_before,
                "tokens_after": total_tokens_after,
                "tokens_saved": total_tokens_saved,
                "savings_by_source": {
                    "total_tokens": total_tokens_saved,
                    "tokens": {
                        "cutctx_compression": pipeline_tokens_saved,
                        "image_optimization": image_tokens_saved,
                    },
                    "usd": {},
                },
                "compression_ratio": (
                    total_tokens_after / total_tokens_before if total_tokens_before > 0 else 1.0
                ),
                "transforms_applied": transforms_applied,
                "transforms_summary": result.transforms_summary,
                "ccr_hashes": result.markers_inserted,
                "image_metrics": image_metrics,
                "audio_metrics": audio_metrics,
                "diagnostics": diagnostics,
            }

            from cutctx.proxy.auth_mode import classify_client
            from cutctx.proxy.outcome import RequestOutcome

            await self._record_request_outcome(
                RequestOutcome(
                    request_id=await self._next_request_id(),
                    provider="compress",
                    model=model,
                    original_tokens=total_tokens_before,
                    optimized_tokens=total_tokens_after,
                    output_tokens=0,
                    tokens_saved=total_tokens_saved,
                    attempted_input_tokens=total_tokens_before,
                    total_latency_ms=0.0,
                    overhead_ms=0.0,
                    transforms_applied=tuple(transforms_applied),
                    num_messages=len(messages),
                    request_messages=None,
                    compressed_messages=None,
                    client=classify_client(request.headers),
                    tags=self._extract_tags(request.headers),
                )
            )

            return JSONResponse(response_payload)
        except Exception as exc:
            logger.exception("Compression failed: %s", exc)
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "type": "compression_error",
                        "message": str(exc),
                    }
                },
            )
