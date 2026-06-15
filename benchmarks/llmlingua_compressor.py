"""LLMLingua-2 adapter for benchmark comparison."""

from __future__ import annotations

import time


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
        result = self._compressor.compress_prompt([text], rate=0.5)
        elapsed = (time.perf_counter() - t0) * 1000
        return result["compressed_prompt"], elapsed
