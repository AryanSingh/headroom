"""Inline audio message optimization for multimodal payloads."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from cutctx.transforms.audio_compressor import AudioCompressor

_WAV_FORMATS = {
    "wav",
    "wave",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
}


@dataclass(slots=True)
class InlineAudioMetrics:
    audio_blocks_seen: int = 0
    audio_blocks_optimized: int = 0
    bytes_before: int = 0
    bytes_after: int = 0

    @property
    def bytes_saved(self) -> int:
        return max(0, self.bytes_before - self.bytes_after)


def compress_inline_audio_messages(
    messages: list[dict[str, Any]],
    *,
    provider: str,
    compressor: AudioCompressor | None = None,
) -> tuple[list[dict[str, Any]], InlineAudioMetrics]:
    """Compress inline WAV audio blocks embedded inside chat messages.

    This helper intentionally does not touch dedicated `/v1/audio/*` routes.
    It only rewrites multimodal message blocks where the audio is already
    embedded inline as base64 payload data.
    """

    optimized = copy.deepcopy(messages)
    metrics = InlineAudioMetrics()
    local_compressor = compressor or AudioCompressor()

    for message in optimized:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if provider == "openai":
                _compress_openai_block(block, local_compressor, metrics)
            elif provider == "anthropic":
                _compress_anthropic_block(block, local_compressor, metrics)

    return optimized, metrics


def _compress_openai_block(
    block: dict[str, Any],
    compressor: AudioCompressor,
    metrics: InlineAudioMetrics,
) -> None:
    if block.get("type") != "input_audio":
        return
    payload = block.get("input_audio")
    if not isinstance(payload, dict):
        return
    fmt = str(payload.get("format") or "").strip().lower()
    if fmt not in _WAV_FORMATS:
        return
    data = payload.get("data")
    if not isinstance(data, str) or not data:
        return
    metrics.audio_blocks_seen += 1
    compressed = compressor.compress_audio(data)
    stats = compressor.last_stats
    if stats is None:
        return
    metrics.bytes_before += stats.original_bytes
    metrics.bytes_after += stats.compressed_bytes
    if compressed == data or stats.saved_bytes <= 0:
        return
    payload["data"] = compressed
    metrics.audio_blocks_optimized += 1


def _compress_anthropic_block(
    block: dict[str, Any],
    compressor: AudioCompressor,
    metrics: InlineAudioMetrics,
) -> None:
    if block.get("type") != "audio":
        return
    source = block.get("source")
    if not isinstance(source, dict):
        return
    if str(source.get("type") or "").strip().lower() not in {"base64", ""}:
        return
    media_type = str(source.get("media_type") or "").strip().lower()
    if media_type not in _WAV_FORMATS:
        return
    data = source.get("data")
    if not isinstance(data, str) or not data:
        return
    metrics.audio_blocks_seen += 1
    compressed = compressor.compress_audio(data)
    stats = compressor.last_stats
    if stats is None:
        return
    metrics.bytes_before += stats.original_bytes
    metrics.bytes_after += stats.compressed_bytes
    if compressed == data or stats.saved_bytes <= 0:
        return
    source["data"] = compressed
    metrics.audio_blocks_optimized += 1
