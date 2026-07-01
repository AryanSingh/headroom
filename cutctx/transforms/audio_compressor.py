from __future__ import annotations

import base64
import binascii
import io
import logging
import math
import sys
import wave
from array import array
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AudioCompressionStats:
    original_bytes: int
    compressed_bytes: int
    original_duration_ms: int
    compressed_duration_ms: int
    downmixed_to_mono: bool
    downsampled: bool
    trimmed_silence: bool

    @property
    def saved_bytes(self) -> int:
        return max(0, self.original_bytes - self.compressed_bytes)


class AudioCompressor:
    """Lossy speech-oriented compressor for base64-encoded WAV audio.

    This class intentionally does not mutate live proxy `/v1/audio/*` routes.
    It provides a concrete transform primitive for offline preprocessing and
    future explicit audio-compression flows.
    """

    def __init__(
        self,
        mode: str = "token",
        threshold_bytes: int = 100_000,
        target_sample_rate: int = 16_000,
        silence_threshold_rms: int = 300,
        silence_window_ms: int = 30,
        keep_silence_ms: int = 60,
        minimum_savings_bytes: int = 512,
    ) -> None:
        self.mode = mode
        self.threshold_bytes = threshold_bytes
        self.target_sample_rate = target_sample_rate
        self.silence_threshold_rms = silence_threshold_rms
        self.silence_window_ms = silence_window_ms
        self.keep_silence_ms = keep_silence_ms
        self.minimum_savings_bytes = minimum_savings_bytes
        self.total_saved_bytes = 0
        self.last_stats: AudioCompressionStats | None = None

    def compress_audio(self, b64_audio: str) -> str:
        """Compress base64 WAV audio when the result is meaningfully smaller."""
        try:
            audio_bytes = base64.b64decode(b64_audio, validate=True)
        except (ValueError, binascii.Error) as exc:
            logger.warning("Audio compression failed to decode base64: %s", exc)
            self.last_stats = None
            return b64_audio

        if len(audio_bytes) < self.threshold_bytes:
            self.last_stats = AudioCompressionStats(
                original_bytes=len(audio_bytes),
                compressed_bytes=len(audio_bytes),
                original_duration_ms=0,
                compressed_duration_ms=0,
                downmixed_to_mono=False,
                downsampled=False,
                trimmed_silence=False,
            )
            return b64_audio

        try:
            compressed_bytes, stats = self._compress_wav_bytes(audio_bytes)
        except wave.Error as exc:
            logger.info("Audio compression skipped for unsupported WAV payload: %s", exc)
            self.last_stats = None
            return b64_audio
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Audio compression failed: %s", exc)
            self.last_stats = None
            return b64_audio

        if stats.saved_bytes < self.minimum_savings_bytes:
            self.last_stats = stats
            return b64_audio

        self.total_saved_bytes += stats.saved_bytes
        self.last_stats = stats
        return base64.b64encode(compressed_bytes).decode("ascii")

    def _compress_wav_bytes(
        self,
        audio_bytes: bytes,
    ) -> tuple[bytes, AudioCompressionStats]:
        with wave.open(io.BytesIO(audio_bytes), "rb") as reader:
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            sample_rate = reader.getframerate()
            frame_count = reader.getnframes()
            compression_type = reader.getcomptype()
            frames = reader.readframes(frame_count)

        if compression_type != "NONE":
            raise wave.Error(f"unsupported WAV compression type {compression_type}")
        if sample_width not in (1, 2, 4):
            raise wave.Error(f"unsupported sample width {sample_width}")
        if channels < 1:
            raise wave.Error("audio must contain at least one channel")
        if channels > 2:
            raise wave.Error(f"unsupported channel count {channels}")

        original_duration_ms = self._duration_ms(frame_count, sample_rate)
        original_bytes = len(audio_bytes)

        mono_samples = self._decode_pcm(frames=frames, sample_width=sample_width, channels=channels)
        downmixed_to_mono = channels > 1

        trimmed_samples = self._trim_silence(
            samples=mono_samples,
            sample_rate=sample_rate,
        )
        trimmed_silence = trimmed_samples != mono_samples
        mono_samples = trimmed_samples

        downsampled = sample_rate > self.target_sample_rate
        if downsampled:
            mono_samples = self._downsample(
                samples=mono_samples,
                source_rate=sample_rate,
                target_rate=self.target_sample_rate,
            )
            sample_rate = self.target_sample_rate

        compressed_duration_ms = self._duration_ms(
            len(mono_samples),
            sample_rate,
        )
        frames = self._encode_pcm16(mono_samples)
        compressed_bytes = self._encode_wav(
            frames=frames,
            channels=1,
            sample_width=2,
            sample_rate=sample_rate,
        )
        stats = AudioCompressionStats(
            original_bytes=original_bytes,
            compressed_bytes=len(compressed_bytes),
            original_duration_ms=original_duration_ms,
            compressed_duration_ms=compressed_duration_ms,
            downmixed_to_mono=downmixed_to_mono,
            downsampled=downsampled,
            trimmed_silence=trimmed_silence,
        )
        return compressed_bytes, stats

    def _trim_silence(
        self,
        *,
        samples: list[int],
        sample_rate: int,
    ) -> list[int]:
        if not samples:
            return samples

        window_frames = max(1, int(sample_rate * self.silence_window_ms / 1000))
        keep_frames = max(0, int(sample_rate * self.keep_silence_ms / 1000))

        windows: list[list[int]] = [
            samples[idx : idx + window_frames]
            for idx in range(0, len(samples), window_frames)
            if samples[idx : idx + window_frames]
        ]
        if not windows:
            return samples

        def _is_audible(chunk: list[int]) -> bool:
            energy = sum(sample * sample for sample in chunk)
            rms = math.sqrt(energy / max(1, len(chunk)))
            return rms > self.silence_threshold_rms

        first_audible = next((idx for idx, chunk in enumerate(windows) if _is_audible(chunk)), None)
        last_audible = next(
            (idx for idx in range(len(windows) - 1, -1, -1) if _is_audible(windows[idx])),
            None,
        )
        if first_audible is None or last_audible is None:
            return samples

        start_frame = max(0, first_audible * window_frames - keep_frames)
        end_frame = min(len(samples), (last_audible + 1) * window_frames + keep_frames)
        trimmed = samples[start_frame:end_frame]
        return trimmed or samples

    @staticmethod
    def _decode_pcm(*, frames: bytes, sample_width: int, channels: int) -> list[int]:
        if sample_width == 1:
            raw = [sample - 128 for sample in frames]
        elif sample_width == 2:
            values = array("h")
            values.frombytes(frames)
            if sys.byteorder != "little":
                values.byteswap()
            raw = list(values)
        elif sample_width == 4:
            values = array("i")
            values.frombytes(frames)
            if sys.byteorder != "little":
                values.byteswap()
            raw = [max(-32768, min(32767, sample // 65536)) for sample in values]
        else:
            raise wave.Error(f"unsupported sample width {sample_width}")

        if channels == 1:
            return raw

        mono: list[int] = []
        for idx in range(0, len(raw), channels):
            frame = raw[idx : idx + channels]
            mono.append(int(round(sum(frame) / len(frame))))
        return mono

    @staticmethod
    def _downsample(
        *,
        samples: list[int],
        source_rate: int,
        target_rate: int,
    ) -> list[int]:
        if target_rate <= 0 or source_rate <= 0 or target_rate >= source_rate or len(samples) < 2:
            return samples

        target_length = max(1, int(round(len(samples) * target_rate / source_rate)))
        if target_length >= len(samples):
            return samples

        ratio = (len(samples) - 1) / max(1, target_length - 1)
        result: list[int] = []
        for idx in range(target_length):
            position = idx * ratio
            left = int(position)
            right = min(left + 1, len(samples) - 1)
            frac = position - left
            interpolated = samples[left] * (1.0 - frac) + samples[right] * frac
            result.append(int(round(interpolated)))
        return result

    @staticmethod
    def _encode_pcm16(samples: list[int]) -> bytes:
        pcm = array("h", [max(-32768, min(32767, sample)) for sample in samples])
        if sys.byteorder != "little":
            pcm.byteswap()
        return pcm.tobytes()

    @staticmethod
    def _encode_wav(
        *,
        frames: bytes,
        channels: int,
        sample_width: int,
        sample_rate: int,
    ) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as writer:
            writer.setnchannels(channels)
            writer.setsampwidth(sample_width)
            writer.setframerate(sample_rate)
            writer.writeframes(frames)
        return buffer.getvalue()

    @staticmethod
    def _duration_ms(frame_count: int, sample_rate: int) -> int:
        if sample_rate <= 0:
            return 0
        return int(round(frame_count * 1000 / sample_rate))
