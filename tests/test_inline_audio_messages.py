from __future__ import annotations

import base64
import io
import math
import struct
import wave

from cutctx.transforms.audio_messages import compress_inline_audio_messages


def _make_wav_base64(
    *,
    sample_rate: int = 44_100,
    duration_seconds: float = 1.0,
    leading_silence_seconds: float = 0.25,
    trailing_silence_seconds: float = 0.25,
    channels: int = 2,
    frequency_hz: float = 440.0,
    amplitude: int = 12_000,
) -> str:
    total_frames = int(sample_rate * duration_seconds)
    lead_frames = int(sample_rate * leading_silence_seconds)
    trail_frames = int(sample_rate * trailing_silence_seconds)
    signal_start = lead_frames
    signal_end = max(signal_start, total_frames - trail_frames)

    frames = bytearray()
    for idx in range(total_frames):
        if signal_start <= idx < signal_end:
            value = int(amplitude * math.sin(2 * math.pi * frequency_hz * idx / sample_rate))
        else:
            value = 0
        packed = struct.pack("<h", value)
        for _ in range(channels):
            frames.extend(packed)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(bytes(frames))
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_openai_inline_audio_blocks_are_optimized() -> None:
    audio = _make_wav_base64()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Summarize this note."},
                {"type": "input_audio", "input_audio": {"format": "wav", "data": audio}},
            ],
        }
    ]

    optimized, metrics = compress_inline_audio_messages(messages, provider="openai")

    assert optimized != messages
    assert optimized[0]["content"][1]["input_audio"]["data"] != audio
    assert metrics.audio_blocks_seen == 1
    assert metrics.audio_blocks_optimized == 1
    assert metrics.bytes_saved > 0


def test_anthropic_inline_audio_blocks_are_optimized() -> None:
    audio = _make_wav_base64()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Summarize this note."},
                {
                    "type": "audio",
                    "source": {"type": "base64", "media_type": "audio/wav", "data": audio},
                },
            ],
        }
    ]

    optimized, metrics = compress_inline_audio_messages(messages, provider="anthropic")

    assert optimized != messages
    assert optimized[0]["content"][1]["source"]["data"] != audio
    assert metrics.audio_blocks_seen == 1
    assert metrics.audio_blocks_optimized == 1
    assert metrics.bytes_saved > 0


def test_non_wav_audio_is_left_unchanged() -> None:
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {"format": "mp3", "data": "ZmFrZQ=="},
                }
            ],
        }
    ]

    optimized, metrics = compress_inline_audio_messages(messages, provider="openai")

    assert optimized == messages
    assert metrics.audio_blocks_seen == 0
    assert metrics.audio_blocks_optimized == 0
