"""LLMLingua-2 adapter for benchmark comparison."""

from __future__ import annotations

import time

# This model uses subword tokens, so a 350-word chunk can still exceed its
# 512-token window on JSON/source-heavy fixtures.  160 words leaves room for
# punctuation-heavy tokenization while retaining a deterministic boundary.
_MAX_WORDS_PER_CHUNK = 160


def _chunks(text: str) -> list[str]:
    """Split a long artifact below LLMLingua-2's 512-token model window.

    The comparison harness must score every fixture for every comparator. This
    deliberately uses fixed word chunks (rather than silently dropping long
    inputs) and joins results in order, preserving an auditable whole-artifact
    output. The benchmark metadata records the harness version/configuration.
    """
    words = text.split()
    return [
        " ".join(words[index : index + _MAX_WORDS_PER_CHUNK])
        for index in range(0, len(words), _MAX_WORDS_PER_CHUNK)
    ] or [""]


class LLMLinguaCompressor:
    """Wraps Microsoft LLMLingua-2 for head-to-head benchmarking."""

    name = "llmlingua-2"

    def __init__(self) -> None:
        from llmlingua import PromptCompressor

        self._compressor = PromptCompressor(
            model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
            use_llmlingua2=True,
            device_map="cpu",
        )

    def compress(self, text: str) -> tuple[str, float]:
        t0 = time.perf_counter()
        compressed: list[str] = []
        for chunk in _chunks(text):
            result = self._compressor.compress_prompt([chunk], rate=0.5)
            compressed.append(result["compressed_prompt"])
        elapsed = (time.perf_counter() - t0) * 1000
        return "\n".join(compressed), elapsed
