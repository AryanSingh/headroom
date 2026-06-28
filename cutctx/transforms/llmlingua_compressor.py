"""LLMLingua-2 prompt compressor — optional ML algorithm.

Wraps Microsoft's LLMLingua-2 (token classification via BERT-level encoder)
for task-agnostic prompt compression. Requires ``pip install cutctx-ai[llmlingua]``.

Falls back gracefully when llmlingua is not installed — callers should check
``LLMLinguaCompressor.available()`` before use.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..config import TransformResult
from ..tokenizer import Tokenizer
from .base import Transform

logger = logging.getLogger(__name__)

_LLMLINGUA_AVAILABLE: bool | None = None  # lazy sentinel


def _check_available() -> bool:
    global _LLMLINGUA_AVAILABLE
    if _LLMLINGUA_AVAILABLE is None:
        try:
            import llmlingua  # noqa: F401

            _LLMLINGUA_AVAILABLE = True
        except ImportError:
            _LLMLINGUA_AVAILABLE = False
    return _LLMLINGUA_AVAILABLE


@dataclass
class LLMLinguaConfig:
    # Keep the integrated router path aligned with the benchmark adapter so
    # we evaluate and ship the same LLMLingua-2 variant.
    model_name: str = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
    rate: float = 0.5  # target keep-rate (0.5 = 50% of tokens kept)
    force_tokens: list[str] = field(default_factory=list)  # tokens always kept
    device: str = "cpu"  # "cpu" or "cuda"
    use_llmlingua2: bool = True  # use LLMLingua-2 (faster, task-agnostic)


@dataclass
class LLMLinguaResult:
    """Result of LLMLingua-2 compression."""

    compressed: str
    original: str
    original_tokens: int
    compressed_tokens: int

    @property
    def compression_ratio(self) -> float:
        if self.original_tokens == 0:
            return 1.0
        return self.compressed_tokens / self.original_tokens

    @property
    def tokens_saved(self) -> int:
        return max(0, self.original_tokens - self.compressed_tokens)

    @property
    def savings_percentage(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return (self.tokens_saved / self.original_tokens) * 100


class LLMLinguaCompressor(Transform):
    """Wraps LLMLingua-2 for ML-based prompt compression."""

    name: str = "llmlingua_compressor"

    def __init__(self, config: LLMLinguaConfig | None = None) -> None:
        self.config = config or LLMLinguaConfig()
        self._compressor: Any = None

    @staticmethod
    def available() -> bool:
        return _check_available()

    def _get_compressor(self) -> Any:
        if self._compressor is None:
            from llmlingua import PromptCompressor

            self._compressor = PromptCompressor(
                model_name=self.config.model_name,
                use_llmlingua2=self.config.use_llmlingua2,
                device_map=self.config.device,
            )
        return self._compressor

    def compress(
        self,
        content: str,
        context: str = "",
        question: str | None = None,
        target_ratio: float | None = None,
    ) -> LLMLinguaResult:
        """Compress content using LLMLingua-2.

        Args:
            content: Text to compress.
            context: Optional context string (unused by LLMLingua-2 directly).
            question: Optional question for QA-aware token preservation (unused).
            target_ratio: Override the configured keep-rate (fraction of tokens kept).

        Returns:
            LLMLinguaResult with compressed text and token counts.
        """
        n_words = len(content.split())

        if not self.available():
            logger.debug("LLMLingua not installed; returning original content")
            return LLMLinguaResult(
                compressed=content,
                original=content,
                original_tokens=n_words,
                compressed_tokens=n_words,
            )

        rate = target_ratio if target_ratio is not None else self.config.rate

        try:
            compressor = self._get_compressor()
            result = compressor.compress_prompt(
                [content],
                rate=rate,
                force_tokens=self.config.force_tokens,
            )
            compressed = result.get("compressed_prompt", content)
            compressed_tokens = len(compressed.split())
            return LLMLinguaResult(
                compressed=compressed,
                original=content,
                original_tokens=n_words,
                compressed_tokens=compressed_tokens,
            )
        except Exception as exc:
            logger.warning("LLMLingua-2 compression failed: %s", exc)
            return LLMLinguaResult(
                compressed=content,
                original=content,
                original_tokens=n_words,
                compressed_tokens=n_words,
            )

    def apply(
        self,
        messages: list[dict[str, Any]],
        tokenizer: Tokenizer,
        **kwargs: Any,
    ) -> TransformResult:
        """Apply LLMLingua-2 compression to messages (Transform interface)."""
        tokens_before = sum(tokenizer.count_text(str(m.get("content", ""))) for m in messages)
        transformed = []
        transforms_applied = []

        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")

            if not isinstance(content, str) or len(content.split()) < 10:
                transformed.append(message)
                continue

            if role in ("tool", "assistant"):
                result = self.compress(content)
                if result.compression_ratio < 0.9:
                    transformed.append({**message, "content": result.compressed})
                    transforms_applied.append(
                        f"llmlingua:{role}:{result.compression_ratio:.2f}"
                    )
                else:
                    transformed.append(message)
            else:
                transformed.append(message)

        tokens_after = sum(
            tokenizer.count_text(str(m.get("content", ""))) for m in transformed
        )

        return TransformResult(
            messages=transformed,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            transforms_applied=transforms_applied or ["llmlingua:noop"],
        )
