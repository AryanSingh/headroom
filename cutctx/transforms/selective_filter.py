"""SelectiveContextFilter — drop low-relevance message blocks before compression.

Sits in the pipeline BEFORE ContentRouter. Given the full message list and the
most recent user query, it scores each message block and drops those below
`min_score`. Always protects the last `protect_recent` turns (user + assistant
pairs) regardless of score.

This is NOT compression — it's selective deletion. A block is either kept
(intact) or dropped (entirely removed from the message list).

Use via ContentRouterConfig.selective_filter=True and
ContentRouterConfig.selective_filter_min_score=0.15.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SelectiveFilterConfig:
    """Configuration for SelectiveContextFilter."""

    # Minimum relevance score (0-1) for a message block to be retained.
    # 0.0 = keep everything (filter is a no-op).
    # 0.15 = drop clearly off-topic turns (recommended starting point).
    # 0.30 = aggressive — may drop mildly relevant turns.
    min_score: float = 0.15

    # Number of most-recent turns (user+assistant counted together) to always
    # keep, regardless of relevance score. Prevents stripping live context.
    protect_recent: int = 6

    # Minimum message character length to score — very short messages (acks,
    # "ok", "thanks") are always kept since they carry conversation structure.
    min_len_to_score: int = 80

    # Scoring backend: "bm25" (fast, no deps) or "hybrid" (needs [relevance]).
    scorer: str = "bm25"

    # When True, system messages are always preserved (never dropped).
    protect_system: bool = True


@dataclass
class FilterResult:
    """Result from a SelectiveContextFilter pass."""

    messages_in: int
    messages_out: int
    messages_dropped: int
    dropped_indices: list[int] = field(default_factory=list)
    scores: dict[int, float] = field(default_factory=dict)  # index -> score


class SelectiveContextFilter:
    """Filters a message list by relevance to the most recent user query.

    Thread-safe: scorer is lazy-loaded once and reused.
    """

    def __init__(self, config: SelectiveFilterConfig | None = None) -> None:
        self.config = config or SelectiveFilterConfig()
        self._scorer: Any = None

    def _get_scorer(self) -> Any:
        if self._scorer is None:
            if self.config.scorer == "hybrid":
                try:
                    from cutctx.relevance.hybrid import HybridScorer

                    self._scorer = HybridScorer()
                    return self._scorer
                except Exception:
                    logger.debug("HybridScorer unavailable, falling back to BM25")
            from cutctx.relevance.bm25 import BM25Scorer

            self._scorer = BM25Scorer()
        return self._scorer

    @staticmethod
    def _extract_text(message: dict[str, Any]) -> str:
        """Extract plain text from a message dict (Anthropic or OpenAI format)."""
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    t = block.get("type", "")
                    if t == "text":
                        parts.append(block.get("text", ""))
                    elif t == "tool_result":
                        inner = block.get("content", "")
                        if isinstance(inner, str):
                            parts.append(inner)
                        elif isinstance(inner, list):
                            for ib in inner:
                                if isinstance(ib, dict) and ib.get("type") == "text":
                                    parts.append(ib.get("text", ""))
                    elif t == "tool_use":
                        # Include tool name + input for scoring
                        name = block.get("name", "")
                        inp = block.get("input", {})
                        parts.append(f"{name} {json.dumps(inp)[:200]}")
            return " ".join(parts)
        return ""

    @staticmethod
    def _find_last_user_query(messages: list[dict[str, Any]]) -> str:
        """Return text of the most recent user message."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                text = SelectiveContextFilter._extract_text(msg)
                if text.strip():
                    return text.strip()
        return ""

    def filter(
        self,
        messages: list[dict[str, Any]],
        query: str | None = None,
    ) -> tuple[list[dict[str, Any]], FilterResult]:
        """Filter messages by relevance to query.

        Args:
            messages: Full message list (Anthropic or OpenAI format).
            query: Query to score against. If None, uses last user message.

        Returns:
            (filtered_messages, FilterResult)
        """
        if not messages or self.config.min_score <= 0.0:
            return messages, FilterResult(
                messages_in=len(messages),
                messages_out=len(messages),
                messages_dropped=0,
            )

        effective_query = query or self._find_last_user_query(messages)
        if not effective_query:
            # No query to score against — keep everything
            return messages, FilterResult(
                messages_in=len(messages),
                messages_out=len(messages),
                messages_dropped=0,
            )

        n = len(messages)
        # Indices of the last `protect_recent` messages are always kept
        protected_start = max(0, n - self.config.protect_recent)
        protected_indices = set(range(protected_start, n))

        scorer = self._get_scorer()
        keep: list[bool] = []
        scores: dict[int, float] = {}

        for i, msg in enumerate(messages):
            # Always keep protected (recent) messages
            if i in protected_indices:
                keep.append(True)
                continue

            # Always keep system messages if configured
            if self.config.protect_system and msg.get("role") == "system":
                keep.append(True)
                continue

            text = self._extract_text(msg)

            # Too short to score — keep
            if len(text) < self.config.min_len_to_score:
                keep.append(True)
                continue

            try:
                result = scorer.score(text, effective_query)
                score_val = (
                    getattr(result, "score", result) if not isinstance(result, float) else result
                )
                scores[i] = float(score_val)
                keep.append(float(score_val) >= self.config.min_score)
            except Exception as exc:
                logger.debug("Scoring failed for message %d (keeping): %s", i, exc)
                keep.append(True)

        filtered = [msg for msg, k in zip(messages, keep) if k]
        dropped_indices = [i for i, k in enumerate(keep) if not k]

        result = FilterResult(
            messages_in=n,
            messages_out=len(filtered),
            messages_dropped=n - len(filtered),
            dropped_indices=dropped_indices,
            scores=scores,
        )

        if result.messages_dropped > 0:
            logger.debug(
                "SelectiveContextFilter: dropped %d/%d messages (min_score=%.2f)",
                result.messages_dropped,
                n,
                self.config.min_score,
            )

        return filtered, result
