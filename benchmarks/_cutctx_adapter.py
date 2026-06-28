"""Shared Cutctx adapter helpers for benchmark scripts."""

from __future__ import annotations

import json
import time
from typing import Any


def extract_message_text(message: dict[str, Any], fallback: str) -> str:
    """Extract benchmarkable text from a Cutctx message payload."""
    content = message.get("content", fallback)

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                    continue
                nested = item.get("content")
                if isinstance(nested, str):
                    parts.append(nested)
                    continue
                parts.append(json.dumps(item, ensure_ascii=False))
                continue
            parts.append(str(item))
        extracted = "\n".join(part for part in parts if part)
        return extracted or fallback

    if isinstance(content, (dict, tuple)):
        return json.dumps(content, ensure_ascii=False)

    if content is None:
        return fallback

    return str(content)


def compress_text_with_cutctx(
    text: str,
    *,
    model: str = "gpt-4o",
) -> tuple[str, float]:
    """Compress a standalone artifact through Cutctx's raw-artifact engine.

    Benchmarks in this directory compare raw files and tool outputs, not
    multi-turn chat transcripts. For that workload, `ContentRouter` is the
    product surface that exercises Cutctx's per-content-type compressors
    directly. When the optional LLMLingua extra is installed, we enable it
    here so benchmark runs measure Cutctx's strongest supported text path.
    """
    from cutctx.transforms import ContentRouter
    from cutctx.transforms.content_router import ContentRouterConfig

    start = time.perf_counter()
    router = ContentRouter(ContentRouterConfig(use_llmlingua=True))
    result = router.compress(text)
    latency_ms = (time.perf_counter() - start) * 1000
    return result.compressed, latency_ms
