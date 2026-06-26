"""Task-aware compression module for Cutctx SDK.

This module provides task-aware compression that uses the current working task
(extracted from user messages) to modulate compression rate per content segment.

Key components:
1. TaskExtractor: Extracts working task from recent messages
2. RelevanceModulator: Scores content relevance to task
3. TaskAwareCompressor: Wraps UniversalCompressor with task-aware modulation

Example:
    compressor = TaskAwareCompressor(task="debug HTTP 500 error")
    result = compressor.compress(json_response, content_type="application/json")
    # HTTP response preserved (relevance ~0.8), minimal compression
    # System info crushed (relevance ~0.1), aggressive compression
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from cutctx.compression.universal import (
    UniversalCompressor,
    UniversalCompressorConfig,
)
from cutctx.relevance import BM25Scorer

logger = logging.getLogger(__name__)


class TaskExtractor:
    """Extract working task from recent user messages.

    Uses simple heuristics (pattern matching) to identify the current task:
    - Imperative verbs: debug, fix, implement, find, analyze, review, summarize, compare
    - Question words: what, how, where, why, which
    - Special keywords: fix, debug

    If no pattern matches, returns None (no task detected).
    """

    # Imperative verbs indicating a task
    IMPERATIVE_VERBS = {
        "debug", "fix", "implement", "find", "analyze", "review",
        "summarize", "compare", "generate", "create", "optimize",
        "test", "validate", "check", "identify", "locate", "refactor",
        "improve", "explain", "describe", "show", "list"
    }

    # Question words
    QUESTION_WORDS = {"what", "how", "where", "why", "which", "who", "when"}

    # Special keywords always indicating a task
    SPECIAL_KEYWORDS = {"fix", "debug", "error"}

    @staticmethod
    def extract_task(messages: list[dict]) -> str | None:
        """Extract working task from last 3 user messages.

        Looks at messages in reverse order (most recent first) and extracts
        the first detectable task.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                     Expected format: [{"role": "user", "content": "..."}, ...]

        Returns:
            Brief task string (40-100 chars) or None if not detectable.

        Example:
            >>> msgs = [
            ...     {"role": "user", "content": "I'm getting a 500 error when I call /api/users. Can you help debug this?"}
            ... ]
            >>> TaskExtractor.extract_task(msgs)
            'debug API 500 error'
        """
        if not messages:
            return None

        # Get last 3 user messages
        user_messages = [
            msg.get("content", "")
            for msg in messages[-3:]
            if msg.get("role") == "user"
        ]

        if not user_messages:
            return None

        # Process most recent first
        for content in reversed(user_messages):
            task = TaskExtractor._extract_from_content(content)
            if task:
                return task

        return None

    @staticmethod
    def _extract_from_content(content: str) -> str | None:
        """Extract task from a single message content string.

        Args:
            content: Message content

        Returns:
            Task string or None
        """
        if not content or len(content) < 3:
            return None

        content_lower = content.lower()

        # Check for special keywords first
        for keyword in TaskExtractor.SPECIAL_KEYWORDS:
            if keyword in content_lower:
                # Return first sentence containing the keyword
                sentences = content.split('.')
                for sent in sentences:
                    if keyword in sent.lower():
                        cleaned = sent.strip()
                        if 30 <= len(cleaned) <= 100:
                            return cleaned
                        # If too long, take first 100 chars
                        if len(cleaned) > 100:
                            return cleaned[:100].rsplit(' ', 1)[0]
                        return cleaned if len(cleaned) >= 10 else None

        # Check for question words
        for qword in TaskExtractor.QUESTION_WORDS:
            if content_lower.startswith(qword):
                # Extract first sentence (up to first period or 100 chars)
                first_sent = content.split('.')[0]
                if len(first_sent) > 100:
                    return first_sent[:100].rsplit(' ', 1)[0]
                return first_sent if len(first_sent) >= 10 else None

        # Check for imperative verbs
        words = content_lower.split()
        for verb in TaskExtractor.IMPERATIVE_VERBS:
            if verb in words:
                # Extract first sentence
                first_sent = content.split('.')[0]
                if len(first_sent) > 100:
                    return first_sent[:100].rsplit(' ', 1)[0]
                return first_sent if len(first_sent) >= 10 else None

        return None


class RelevanceModulator:
    """Score content relevance to a task.

    Uses BM25 (keyword-based) scoring for fast, deterministic relevance
    computation without requiring neural networks.

    Falls back to simple keyword overlap if BM25 unavailable.
    """

    def __init__(self, use_bm25: bool = True):
        """Initialize relevance modulator.

        Args:
            use_bm25: Whether to use BM25 scorer. If False, uses keyword overlap.
        """
        self.use_bm25 = use_bm25
        self._bm25_scorer = None

        if use_bm25:
            try:
                self._bm25_scorer = BM25Scorer()
            except Exception as e:
                logger.warning("BM25 scorer unavailable, falling back to keyword overlap: %s", e)
                self._bm25_scorer = None

    def score(self, content: str, task: str) -> float:
        """Score content relevance to task.

        Args:
            content: Content chunk to score
            task: Task string

        Returns:
            Relevance score [0.0, 1.0]

        Example:
            >>> modulator = RelevanceModulator()
            >>> score = modulator.score(
            ...     '{"error": "connection refused", "status": 500}',
            ...     "debug HTTP 500 error"
            ... )
            >>> score > 0.5  # "error", "500" match
            True
        """
        if not content or not task:
            return 0.0

        if self._bm25_scorer:
            try:
                result = self._bm25_scorer.score(content, task)
                return result.score
            except Exception as e:
                logger.warning("BM25 scoring failed, falling back: %s", e)

        # Fallback: simple keyword overlap
        return self._keyword_overlap_score(content, task)

    @staticmethod
    def _keyword_overlap_score(content: str, task: str) -> float:
        """Score using simple keyword overlap.

        Args:
            content: Content string
            task: Task string

        Returns:
            Score [0.0, 1.0]
        """
        # Tokenize both
        def tokenize(text: str) -> set[str]:
            # Extract words (alphanumeric sequences)
            tokens = re.findall(r'\b[a-zA-Z0-9_]+\b', text.lower())
            # Filter short tokens
            return {t for t in tokens if len(t) > 2}

        task_tokens = tokenize(task)
        content_tokens = tokenize(content)

        if not task_tokens or not content_tokens:
            return 0.0

        # Overlap / union
        overlap = len(task_tokens & content_tokens)
        union = len(task_tokens | content_tokens)

        return overlap / union if union > 0 else 0.0


@dataclass
class TaskAwareResult:
    """Result from task-aware compression.

    Attributes:
        compressed: The compressed content
        original_tokens: Token count before compression
        compressed_tokens: Token count after compression
        relevance_score: Relevance of content to task [0.0, 1.0]
        task_used: The task string used (or None if no task)
    """

    compressed: str
    original_tokens: int
    compressed_tokens: int
    relevance_score: float
    task_used: str | None

    @property
    def tokens_saved(self) -> int:
        """Tokens removed by compression."""
        return max(0, self.original_tokens - self.compressed_tokens)

    @property
    def compression_ratio(self) -> float:
        """Compression ratio (tokens_saved / original_tokens)."""
        if self.original_tokens == 0:
            return 0.0
        return self.tokens_saved / self.original_tokens


class TaskAwareCompressor:
    """Compress content with task-aware modulation.

    Wraps UniversalCompressor and adds task-aware relevance scoring.
    When a task is available, compresses high-relevance content minimally
    and irrelevant content aggressively.

    When no task is available (task=None), behaves identically to
    UniversalCompressor (no modulation).

    Example:
        compressor = TaskAwareCompressor(task="debug HTTP 500 error")
        result = compressor.compress(json_response)
        # HTTP error details: minimal compression
        # System info: aggressive compression
    """

    def __init__(
        self,
        task: str | None = None,
        relevance_threshold: float = 0.3,
    ):
        """Initialize task-aware compressor.

        Args:
            task: Current working task, or None. Can be updated later with set_task().
            relevance_threshold: Minimum relevance for "normal" compression tier.
                - relevance >= 0.7: minimal (CacheAligner only)
                - 0.3 <= relevance < 0.7: normal (type-based routing)
                - relevance < 0.3: aggressive (crush down to ~10%)
        """
        self.task = task
        self.relevance_threshold = relevance_threshold

        # Initialize components
        self._universal = UniversalCompressor()
        self._modulator = RelevanceModulator(use_bm25=True)

    def compress(
        self,
        content: str,
        content_type: str | None = None,
    ) -> TaskAwareResult:
        """Compress content with task-aware modulation.

        Args:
            content: Content to compress
            content_type: MIME type (e.g., "application/json", "text/plain")
                         Optional - UniversalCompressor will detect if not provided

        Returns:
            TaskAwareResult with compressed content and metrics

        Example:
            >>> compressor = TaskAwareCompressor(task="find database function")
            >>> result = compressor.compress(large_python_file)
            >>> print(f"Relevance: {result.relevance_score:.2f}")
            >>> print(f"Tokens saved: {result.tokens_saved}")
        """
        # Compute relevance if task available
        relevance = 1.0  # Default: fully relevant (no modulation)
        if self.task:
            relevance = self._modulator.score(content, self.task)

        # Select compression strategy based on relevance
        if relevance >= 0.7:
            # High relevance: minimal compression (preserve structure only)
            config = UniversalCompressorConfig(
                compression_ratio_target=0.95,  # Keep 95%
                use_kompress=False,  # Disable ML compression
                use_entropy_preservation=True,
            )
        elif relevance >= self.relevance_threshold:
            # Medium relevance: normal compression (type-based routing)
            config = UniversalCompressorConfig()
        else:
            # Low relevance: aggressive compression
            config = UniversalCompressorConfig(
                compression_ratio_target=0.1,  # Keep only 10%
                use_kompress=True,
            )

        # Compress with modulated config
        try:
            compressor = UniversalCompressor(config=config)
            result = compressor.compress(content, content_type)

            return TaskAwareResult(
                compressed=result.compressed,
                original_tokens=result.tokens_before,
                compressed_tokens=result.tokens_after,
                relevance_score=relevance,
                task_used=self.task,
            )
        except Exception as e:
            logger.warning(
                "Task-aware compression failed: %s. Returning original content.",
                e,
            )
            # Fallback: return original content
            original_tokens = self._estimate_tokens(content)
            return TaskAwareResult(
                compressed=content,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                relevance_score=relevance,
                task_used=self.task,
            )

    def set_task(self, task: str | None) -> None:
        """Update task mid-session.

        Allows updating the task after initialization, useful in long-running
        agent sessions where the task may evolve.

        Args:
            task: New task string, or None to disable task-aware modulation

        Example:
            compressor = TaskAwareCompressor()
            # ... first compression without task ...
            compressor.set_task("debug database connection")
            # ... subsequent compressions use the new task ...
        """
        self.task = task
        logger.debug("Task updated to: %s", task)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough estimate of token count (simple heuristic).

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Simple heuristic: ~4 characters per token (English average)
        return max(1, len(text) // 4)
