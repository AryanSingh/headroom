from __future__ import annotations

import base64
import io
import math
import struct
import wave

from cutctx.transforms.audio_compressor import AudioCompressor


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


def _decode_wav(b64_audio: str) -> tuple[wave._wave_params, bytes]:
    raw = base64.b64decode(b64_audio)
    with wave.open(io.BytesIO(raw), "rb") as reader:
        return reader.getparams(), reader.readframes(reader.getnframes())


def test_audio_compressor_returns_original_below_threshold() -> None:
    b64_audio = _make_wav_base64(duration_seconds=0.15, channels=1)
    compressor = AudioCompressor(threshold_bytes=1_000_000)

    result = compressor.compress_audio(b64_audio)

    assert result == b64_audio


def test_audio_compressor_trims_silence_downmixes_and_downsamples() -> None:
    b64_audio = _make_wav_base64(duration_seconds=1.2, channels=2)
    original_params, original_frames = _decode_wav(b64_audio)
    compressor = AudioCompressor(
        threshold_bytes=256,
        target_sample_rate=16_000,
        silence_threshold_rms=150,
        silence_window_ms=20,
        keep_silence_ms=20,
        minimum_savings_bytes=64,
    )

    result = compressor.compress_audio(b64_audio)
    compressed_params, compressed_frames = _decode_wav(result)

    assert len(base64.b64decode(result)) < len(base64.b64decode(b64_audio))
    assert compressed_params.nchannels == 1
    assert compressed_params.framerate == 16_000
    assert compressed_params.nframes < original_params.nframes
    assert len(compressed_frames) < len(original_frames)
    assert compressor.last_stats is not None
    assert compressor.last_stats.downmixed_to_mono is True
    assert compressor.last_stats.downsampled is True
    assert compressor.last_stats.trimmed_silence is True
    assert compressor.total_saved_bytes > 0


def test_audio_compressor_returns_original_for_invalid_base64() -> None:
    compressor = AudioCompressor(threshold_bytes=1)

    result = compressor.compress_audio("not-base64!!")

    assert result == "not-base64!!"
    assert compressor.last_stats is None
