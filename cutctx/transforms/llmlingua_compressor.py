"""LLMLingua prompt compression via Microsoft's LLMLingua-2 model.

Requires: pip install cutctx-ai[llmlingua]  (``llmlingua>=0.2.2``, ``torch``).

When llmlingua is not installed, compress() returns the original text unchanged
with compression_ratio=1.0 — no error is raised.
"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..config import TransformResult

logger = logging.getLogger(__name__)


def _check_available() -> bool:
    return importlib.util.find_spec("llmlingua") is not None


@dataclass
class LLMLinguaResult:
    """Result of LLMLingua compression.

    Attributes:
        compressed: Compressed prompt text.
        original: Original prompt text.
        original_tokens: Estimated token count of original.
        compressed_tokens: Estimated token count of compressed output.
    """

    compressed: str
    original: str
    original_tokens: int
    compressed_tokens: int

    @property
    def compression_ratio(self) -> float:
        """Ratio of compressed to original tokens (lower = better)."""
        if self.original_tokens == 0:
            return 1.0
        return self.compressed_tokens / self.original_tokens

    @property
    def tokens_saved(self) -> int:
        """Tokens removed (never negative)."""
        return max(0, self.original_tokens - self.compressed_tokens)

    @property
    def savings_percentage(self) -> float:
        """Percentage of tokens removed (0-100)."""
        if self.original_tokens == 0:
            return 0.0
        return max(0.0, (1.0 - self.compression_ratio) * 100.0)


@dataclass
class LLMLinguaConfig:
    """Configuration for LLMLingua compression.

    Attributes:
        model_name: HuggingFace model identifier.
        rate: Target compression rate 0.0-1.0 (default 0.5 = 50% reduction).
        force_tokens: Tokens that must be preserved verbatim.
        device: PyTorch device string (``"cpu"``, ``"cuda"``, ``"mps"``).
        use_llmlingua2: Whether to use LLMLingua-2 (recommended).
        min_length: Minimum content length in chars to attempt compression.
    """

    model_name: str = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
    rate: float = 0.5
    force_tokens: list[str] = field(default_factory=list)
    device: str = "cpu"
    use_llmlingua2: bool = True
    min_words: int = 10


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class LLMLinguaCompressor:
    """Prompt compressor backed by Microsoft LLMLingua-2.

    Usage::

        from cutctx.transforms.llmlingua_compressor import LLMLinguaCompressor
        c = LLMLinguaCompressor()
        result = c.compress(long_prompt)
        print(result.tokens_saved)
    """

    name = "llmlingua_compressor"

    def __init__(self, config: LLMLinguaConfig | None = None) -> None:
        self.config = config or LLMLinguaConfig()
        self._compressor: Any = None

    @staticmethod
    def available() -> bool:
        """Return True when the ``llmlingua`` package is importable."""
        return _check_available()

    def _get_compressor(self) -> Any:
        """Lazy-initialise the underlying PromptCompressor (heavy model load)."""
        if self._compressor is None:
            from llmlingua import PromptCompressor  # type: ignore[import]

            self._compressor = PromptCompressor(
                model_name=self.config.model_name,
                use_llmlingua2=self.config.use_llmlingua2,
                device_map=self.config.device,
            )
        return self._compressor

    def compress(
        self,
        content: str,
        context: str | None = None,
        question: str | None = None,
        target_ratio: float | None = None,
    ) -> LLMLinguaResult:
        """Compress *content* using LLMLingua-2.

        Falls back to returning the original unchanged if llmlingua is not
        installed or if an error occurs during compression.
        """
        if not self.available():
            tok = _estimate_tokens(content)
            return LLMLinguaResult(
                compressed=content,
                original=content,
                original_tokens=tok,
                compressed_tokens=tok,
            )

        rate = target_ratio if target_ratio is not None else self.config.rate
        original_tokens = _estimate_tokens(content)

        try:
            compressor = self._get_compressor()
            kwargs: dict[str, Any] = {
                "rate": rate,
                "force_tokens": self.config.force_tokens,
            }
            if context:
                kwargs["context"] = context
            if question:
                kwargs["question"] = question

            output = compressor.compress_prompt(content, **kwargs)
            compressed_text: str = output.get("compressed_prompt", content)
            compressed_tokens = _estimate_tokens(compressed_text)

        except Exception:
            logger.exception("LLMLingua compression failed; returning original")
            compressed_text = content
            compressed_tokens = original_tokens

        return LLMLinguaResult(
            compressed=compressed_text,
            original=content,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
        )

    def apply(self, messages: list[dict[str, Any]], tokenizer: Any = None) -> TransformResult:
        """Transform interface: compress system/assistant message content.

        Returns a ``TransformResult``. Short messages (below ``config.min_length``)
        are passed through unchanged. User-role messages are never compressed.
        """
        from ..config import TransformResult

        def _count(text: str) -> int:
            if tokenizer is not None and hasattr(tokenizer, "count_text"):
                return tokenizer.count_text(text)
            return _estimate_tokens(text)

        tokens_before = sum(
            _count(m.get("content", "")) for m in messages if isinstance(m.get("content"), str)
        )

        result_messages: list[dict[str, Any]] = []
        transforms_applied: list[str] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if (
                role == "user"
                or not isinstance(content, str)
                or len(content.split()) < self.config.min_words
            ):
                result_messages.append(msg)
                continue

            res = self.compress(content)
            if res.tokens_saved > 0:
                result_messages.append({**msg, "content": res.compressed})
                transforms_applied.append(f"llmlingua:{role}")
            else:
                result_messages.append(msg)

        tokens_after = sum(
            _count(m.get("content", ""))
            for m in result_messages
            if isinstance(m.get("content"), str)
        )

        return TransformResult(
            messages=result_messages,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            transforms_applied=transforms_applied,
        )
