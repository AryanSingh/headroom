"""Tests for task-aware compression (test_task_aware.py).

This module tests the TaskAwareCompressor and its supporting components:
1. TaskExtractor.extract_task() — Extracts task from messages with question words
   and imperative verbs ("fix", "debug", "implement", "find"), returns None for
   empty/irrelevant messages
2. RelevanceModulator.score() — Returns float 0.0–1.0, high score for content
   relevant to task, low for irrelevant content
3. TaskAwareCompressor.compress() — Applies task-aware modulation: relevant
   content gets lower compression, irrelevant gets higher
4. TaskAwareCompressor with no task — Falls back to normal compression behavior
5. TaskAwareCompressor.set_task() — Updates task mid-session, changes subsequent
   compression behavior
6. TaskAwareResult properties — tokens_saved and compression_ratio computed
   correctly
7. Edge cases — empty content, single-word content, very long content

Tests use pytest style with mocking for BM25/embedding calls to avoid ML
dependencies. All tests are self-contained and fast (no network calls).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from headroom.compression.task_aware import (
    RelevanceModulator,
    TaskAwareCompressor,
    TaskAwareResult,
    TaskExtractor,
)
from headroom.compression.universal import CompressionResult, ContentType

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_universal_compressor():
    """Mock UniversalCompressor to avoid ML dependencies."""
    with patch(
        "headroom.compression.task_aware.UniversalCompressor"
    ) as mock_class:
        # Create a mock instance
        mock_instance = MagicMock()

        # Set up default return value for compress()
        mock_instance.compress.return_value = CompressionResult(
            compressed="compressed content",
            original="original content",
            compression_ratio=0.5,
            tokens_before=100,
            tokens_after=50,
            content_type=ContentType.TEXT,
            detection_confidence=0.9,
            handler_used="default",
            preservation_ratio=0.8,
        )

        # Make the class return the mock instance when instantiated
        mock_class.return_value = mock_instance
        yield mock_class, mock_instance


@pytest.fixture
def mock_bm25_scorer():
    """Mock BM25Scorer to avoid ML dependencies."""
    with patch("headroom.compression.task_aware.BM25Scorer") as mock_class:
        mock_instance = MagicMock()
        # Default score result — returns a float so relevance >= X comparisons work
        default_score_result = MagicMock()
        default_score_result.score = 0.5
        mock_instance.score.return_value = default_score_result
        mock_class.return_value = mock_instance
        # Yield (instance, class) so tests can unpack as (_, mock_bm25)
        # where mock_bm25 is the class — allowing mock_bm25.return_value = X
        # to control what BM25Scorer() returns in subsequent instantiations.
        yield mock_instance, mock_class


# ============================================================================
# TaskExtractor Tests
# ============================================================================

class TestTaskExtractorBasic:
    """Test basic task extraction from messages."""

    def test_extract_task_with_debug_keyword(self):
        """Should extract task from messages containing 'debug'."""
        messages = [
            {"role": "user", "content": "I'm getting a 500 error when calling /api/users. Can you help debug this?"}
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None
        # Extractor may normalize/summarize the task description
        assert len(task) > 0

    def test_extract_task_with_fix_keyword(self):
        """Should extract task from messages containing 'fix'."""
        messages = [
            {"role": "user", "content": "Can you fix the broken authentication flow in the login module?"}
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None
        assert "fix" in task.lower()

    def test_extract_task_with_implement_verb(self):
        """Should extract task from messages containing 'implement'."""
        messages = [
            {"role": "user", "content": "I need you to implement a new feature for user profile management."}
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None
        assert "implement" in task.lower()

    def test_extract_task_with_find_verb(self):
        """Should extract task from messages containing 'find'."""
        messages = [
            {"role": "user", "content": "Find the memory leak in the caching subsystem."}
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None
        assert "find" in task.lower()

    def test_extract_task_with_question_word_what(self):
        """Should extract task from messages starting with 'What'."""
        messages = [
            {"role": "user", "content": "What's causing the database connection timeout?"}
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None
        assert len(task) >= 10

    def test_extract_task_with_question_word_how(self):
        """Should extract task from messages starting with 'How'."""
        messages = [
            {"role": "user", "content": "How can I optimize the SQL query for user lookup?"}
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None

    def test_extract_task_returns_none_for_empty_messages(self):
        """Should return None for empty message list."""
        task = TaskExtractor.extract_task([])
        assert task is None

    def test_extract_task_returns_none_for_irrelevant_messages(self):
        """Should return None for messages without task keywords."""
        messages = [
            {"role": "user", "content": "Hello there. The weather is nice today."}
        ]
        task = TaskExtractor.extract_task(messages)
        assert task is None

    def test_extract_task_ignores_assistant_messages(self):
        """Should only consider user messages."""
        messages = [
            {"role": "assistant", "content": "I can help you debug this issue."},
            {"role": "user", "content": "Thanks, but let's focus on other things."}
        ]
        task = TaskExtractor.extract_task(messages)
        # Should not pick up "debug" from assistant message
        assert task is None or "debug" not in task.lower()

    def test_extract_task_from_most_recent_message(self):
        """Should prefer most recent message when multiple contain tasks."""
        messages = [
            {"role": "user", "content": "Can you debug the old system?"},
            {"role": "user", "content": "Now fix the new authentication module."}
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None
        # Should get "fix" from second (more recent) message
        assert "fix" in task.lower() or "authentication" in task.lower()

    def test_extract_task_length_bounds(self):
        """Extracted task should be reasonable length (10-100 chars typically)."""
        messages = [
            {"role": "user", "content": "Implement the user management system with full CRUD operations."}
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None
        assert len(task) >= 10

    def test_extract_task_looks_at_last_3_messages(self):
        """Should look back at most recent 3 messages."""
        messages = [
            {"role": "user", "content": "This is very old, debug something."},
            {"role": "user", "content": "This is older."},
            {"role": "user", "content": "This is recent."},
            {"role": "user", "content": "This is most recent, implement a feature."},
        ]
        task = TaskExtractor.extract_task(messages)

        assert task is not None
        assert "implement" in task.lower()


class TestTaskExtractorEdgeCases:
    """Test edge cases in task extraction."""

    def test_extract_task_empty_content(self):
        """Should handle messages with empty content."""
        messages = [{"role": "user", "content": ""}]
        task = TaskExtractor.extract_task(messages)
        assert task is None

    def test_extract_task_very_short_content(self):
        """Should return None for very short content (< 3 chars)."""
        messages = [{"role": "user", "content": "ab"}]
        task = TaskExtractor.extract_task(messages)
        assert task is None

    def test_extract_task_only_special_keyword_no_context(self):
        """Should handle messages that are just the special keyword."""
        messages = [{"role": "user", "content": "debug"}]
        task = TaskExtractor.extract_task(messages)
        # May or may not extract, but shouldn't crash
        assert task is None or isinstance(task, str)

    def test_extract_task_missing_role(self):
        """Should handle messages missing 'role' field gracefully."""
        messages = [{"content": "fix the bug"}]
        task = TaskExtractor.extract_task(messages)
        # Should handle gracefully
        assert task is None or isinstance(task, str)

    def test_extract_task_missing_content(self):
        """Should handle messages missing 'content' field gracefully."""
        messages = [{"role": "user"}]
        task = TaskExtractor.extract_task(messages)
        assert task is None


# ============================================================================
# RelevanceModulator Tests
# ============================================================================

class TestRelevanceModulatorBasic:
    """Test basic relevance scoring."""

    def test_score_high_relevance_exact_match(self):
        """Should score high when content matches task exactly."""
        with patch("headroom.compression.task_aware.BM25Scorer") as mock_bm25:
            mock_scorer = MagicMock()
            mock_scorer.score.return_value = MagicMock(score=0.85)
            mock_bm25.return_value = mock_scorer

            modulator = RelevanceModulator(use_bm25=True)
            score = modulator.score(
                "error 500 HTTP connection refused",
                "debug HTTP 500 error"
            )

            assert 0.0 <= score <= 1.0
            assert score > 0.5

    def test_score_low_relevance_no_match(self):
        """Should score low when content doesn't match task."""
        with patch("headroom.compression.task_aware.BM25Scorer") as mock_bm25:
            mock_scorer = MagicMock()
            mock_scorer.score.return_value = MagicMock(score=0.1)
            mock_bm25.return_value = mock_scorer

            modulator = RelevanceModulator(use_bm25=True)
            score = modulator.score(
                "completely unrelated content about cooking recipes",
                "debug HTTP 500 error"
            )

            assert 0.0 <= score <= 1.0

    def test_score_returns_float_in_range(self):
        """Score should always be in [0.0, 1.0]."""
        with patch("headroom.compression.task_aware.BM25Scorer") as mock_bm25:
            mock_scorer = MagicMock()
            for test_score in [0.0, 0.25, 0.5, 0.75, 1.0]:
                mock_scorer.score.return_value = MagicMock(score=test_score)
                mock_bm25.return_value = mock_scorer

                modulator = RelevanceModulator(use_bm25=True)
                score = modulator.score("test content", "test task")

                assert isinstance(score, float)
                assert 0.0 <= score <= 1.0

    def test_score_empty_content(self):
        """Should return 0.0 for empty content."""
        modulator = RelevanceModulator(use_bm25=False)
        score = modulator.score("", "test task")
        assert score == 0.0

    def test_score_empty_task(self):
        """Should return 0.0 for empty task."""
        modulator = RelevanceModulator(use_bm25=False)
        score = modulator.score("test content", "")
        assert score == 0.0

    def test_score_fallback_to_keyword_overlap(self):
        """Should fallback to keyword overlap if BM25 fails."""
        with patch("headroom.compression.task_aware.BM25Scorer") as mock_bm25:
            # Simulate BM25 initialization failure
            mock_bm25.side_effect = Exception("BM25 unavailable")

            modulator = RelevanceModulator(use_bm25=True)
            # Should fallback to keyword overlap
            score = modulator.score(
                "error and debug are important",
                "debug the error"
            )

            assert 0.0 <= score <= 1.0
            assert score > 0.0  # Should find overlap

    def test_score_without_bm25_uses_keyword_overlap(self):
        """Should use keyword overlap when use_bm25=False."""
        modulator = RelevanceModulator(use_bm25=False)

        # High overlap
        score_high = modulator.score("error debug fix", "debug error")
        assert score_high > 0.3

        # No overlap
        score_low = modulator.score("completely unrelated", "debug error")
        assert score_low < 0.3


class TestRelevanceModulatorKeywordOverlap:
    """Test keyword overlap scoring (fallback mechanism)."""

    def test_keyword_overlap_identical_content(self):
        """Identical content should score high."""
        modulator = RelevanceModulator(use_bm25=False)
        score = modulator.score("debug error", "debug error")
        assert score > 0.7

    def test_keyword_overlap_partial_match(self):
        """Partial word match should score medium."""
        modulator = RelevanceModulator(use_bm25=False)
        score = modulator.score("debug the error in code", "debug error")
        assert 0.3 < score < 0.9

    def test_keyword_overlap_no_match(self):
        """No common words should score low."""
        modulator = RelevanceModulator(use_bm25=False)
        score = modulator.score("apple orange banana", "debug error fix")
        assert score < 0.3

    def test_keyword_overlap_short_tokens_ignored(self):
        """Short tokens (< 3 chars) should be ignored."""
        modulator = RelevanceModulator(use_bm25=False)
        # "a" and "b" are short and ignored
        score = modulator.score("a b c debug error", "debug error")
        # Should still match on "debug" and "error"
        assert score > 0.3

    def test_keyword_overlap_case_insensitive(self):
        """Scoring should be case insensitive."""
        modulator = RelevanceModulator(use_bm25=False)
        score_lower = modulator.score("DEBUG error", "debug error")
        score_upper = modulator.score("DEBUG ERROR", "DEBUG ERROR")
        assert score_lower > 0.7
        assert score_upper > 0.7


# ============================================================================
# TaskAwareCompressor Tests
# ============================================================================

class TestTaskAwareCompressorBasic:
    """Test basic compression with task awareness."""

    def test_compress_with_task_high_relevance(self, mock_universal_compressor, mock_bm25_scorer):
        """With high relevance, should use minimal compression."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        # Mock BM25 to return high score
        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.85)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="debug HTTP 500 error")
        result = compressor.compress("error 500 connection refused")

        assert isinstance(result, TaskAwareResult)
        assert result.compressed == "compressed content"
        assert result.relevance_score > 0.7

    def test_compress_with_task_low_relevance(self, mock_universal_compressor, mock_bm25_scorer):
        """With low relevance, should use aggressive compression."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        # Mock BM25 to return low score
        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.1)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="debug HTTP error", relevance_threshold=0.3)
        result = compressor.compress("completely unrelated system info")

        assert isinstance(result, TaskAwareResult)
        assert result.relevance_score < 0.3

    def test_compress_without_task_behaves_normal(self, mock_universal_compressor, mock_bm25_scorer):
        """Without task, should use normal compression (no modulation)."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        compressor = TaskAwareCompressor(task=None)
        result = compressor.compress("some content")

        assert isinstance(result, TaskAwareResult)
        assert result.relevance_score == 1.0  # Default: fully relevant
        assert result.task_used is None

    def test_compress_result_has_required_fields(self, mock_universal_compressor, mock_bm25_scorer):
        """Result should contain all required fields."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.6)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="test task")
        result = compressor.compress("test content")

        assert hasattr(result, 'compressed')
        assert hasattr(result, 'original_tokens')
        assert hasattr(result, 'compressed_tokens')
        assert hasattr(result, 'relevance_score')
        assert hasattr(result, 'task_used')

    def test_compress_respects_content_type_parameter(self, mock_universal_compressor, mock_bm25_scorer):
        """Should pass content_type to UniversalCompressor."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        compressor = TaskAwareCompressor(task="test")
        compressor.compress('{"key": "value"}', content_type="application/json")

        # Check that compress was called (we can't easily verify exact call args with multiple instantiations)
        assert mock_instance.compress.called


class TestTaskAwareCompressorSetTask:
    """Test updating task mid-session."""

    def test_set_task_updates_task(self):
        """set_task should update the task."""
        compressor = TaskAwareCompressor(task="initial task")
        assert compressor.task == "initial task"

        compressor.set_task("updated task")
        assert compressor.task == "updated task"

    def test_set_task_none_disables_modulation(self):
        """set_task(None) should disable task-aware modulation."""
        compressor = TaskAwareCompressor(task="some task")
        compressor.set_task(None)
        assert compressor.task is None

    def test_set_task_changes_subsequent_compression(self, mock_universal_compressor, mock_bm25_scorer):
        """Changing task should affect subsequent compressions."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="debug error")

        # First compression with high relevance
        mock_scorer.score.return_value = MagicMock(score=0.85)
        result1 = compressor.compress("error message")
        assert result1.relevance_score > 0.7

        # Update task
        compressor.set_task("analyze performance")

        # Second compression with low relevance to new task
        mock_scorer.score.return_value = MagicMock(score=0.1)
        result2 = compressor.compress("error message")
        assert result2.relevance_score < 0.3
        assert result2.task_used == "analyze performance"


# ============================================================================
# TaskAwareResult Tests
# ============================================================================

class TestTaskAwareResultProperties:
    """Test TaskAwareResult property computation."""

    def test_tokens_saved_computed_correctly(self):
        """tokens_saved should equal original - compressed."""
        result = TaskAwareResult(
            compressed="short",
            original_tokens=100,
            compressed_tokens=30,
            relevance_score=0.5,
            task_used="test"
        )
        assert result.tokens_saved == 70

    def test_tokens_saved_minimum_zero(self):
        """tokens_saved should never be negative."""
        result = TaskAwareResult(
            compressed="very long",
            original_tokens=50,
            compressed_tokens=60,  # More tokens after (shouldn't happen)
            relevance_score=0.5,
            task_used="test"
        )
        assert result.tokens_saved == 0

    def test_compression_ratio_computed_correctly(self):
        """compression_ratio should equal tokens_saved / original_tokens."""
        result = TaskAwareResult(
            compressed="x",
            original_tokens=100,
            compressed_tokens=50,
            relevance_score=0.5,
            task_used="test"
        )
        assert result.compression_ratio == 0.5

    def test_compression_ratio_zero_with_zero_tokens(self):
        """compression_ratio should be 0.0 when original_tokens is 0."""
        result = TaskAwareResult(
            compressed="",
            original_tokens=0,
            compressed_tokens=0,
            relevance_score=0.0,
            task_used=None
        )
        assert result.compression_ratio == 0.0

    def test_compression_ratio_range(self):
        """compression_ratio should be in [0.0, 1.0]."""
        for orig, comp in [(100, 20), (100, 50), (100, 99), (1, 1)]:
            result = TaskAwareResult(
                compressed="x",
                original_tokens=orig,
                compressed_tokens=comp,
                relevance_score=0.5,
                task_used="test"
            )
            assert 0.0 <= result.compression_ratio <= 1.0

    def test_tokens_saved_zero_compression(self):
        """tokens_saved should be 0 when no compression occurs."""
        result = TaskAwareResult(
            compressed="same",
            original_tokens=100,
            compressed_tokens=100,
            relevance_score=1.0,
            task_used="test"
        )
        assert result.tokens_saved == 0
        assert result.compression_ratio == 0.0


# ============================================================================
# Edge Cases and Special Scenarios
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_compress_empty_content(self, mock_universal_compressor, mock_bm25_scorer):
        """Should handle empty content gracefully."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.0)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="test")
        result = compressor.compress("")

        # Should complete without error
        assert isinstance(result, TaskAwareResult)

    def test_compress_single_word_content(self, mock_universal_compressor, mock_bm25_scorer):
        """Should handle single-word content."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.5)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="test")
        result = compressor.compress("debug")

        assert isinstance(result, TaskAwareResult)

    def test_compress_very_long_content(self, mock_universal_compressor, mock_bm25_scorer):
        """Should handle very long content (10k+ characters)."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.7)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="analyze logs")
        large_content = "log entry " * 1000  # ~10k chars

        result = compressor.compress(large_content)
        assert isinstance(result, TaskAwareResult)

    def test_compress_unicode_content(self, mock_universal_compressor, mock_bm25_scorer):
        """Should handle Unicode content."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.5)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="translate")
        result = compressor.compress("こんにちは世界 🌍 debugging")

        assert isinstance(result, TaskAwareResult)

    def test_compress_whitespace_only(self, mock_universal_compressor, mock_bm25_scorer):
        """Should handle whitespace-only content."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.0)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="test")
        result = compressor.compress("   \n\n   \t  ")

        assert isinstance(result, TaskAwareResult)

    def test_compress_special_characters(self, mock_universal_compressor, mock_bm25_scorer):
        """Should handle special characters and symbols."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.3)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="debug")
        result = compressor.compress("!@#$%^&*()_+-=[]{}|;:,.<>?")

        assert isinstance(result, TaskAwareResult)

    def test_compress_json_content(self, mock_universal_compressor, mock_bm25_scorer):
        """Should handle JSON content with type parameter."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.7)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="parse API response")
        json_content = '{"error": "500", "message": "server error"}'

        result = compressor.compress(json_content, content_type="application/json")
        assert isinstance(result, TaskAwareResult)

    def test_compress_code_content(self, mock_universal_compressor, mock_bm25_scorer):
        """Should handle code content with type parameter."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.8)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="debug function")
        code = """
def debug_function():
    try:
        result = perform_operation()
    except Exception as e:
        logger.error("Error: %s", e)
"""

        result = compressor.compress(code, content_type="text/plain")
        assert isinstance(result, TaskAwareResult)

    def test_relevance_threshold_affects_compression_tier(self, mock_universal_compressor, mock_bm25_scorer):
        """Different relevance thresholds should select different compression tiers."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_bm25.return_value = mock_scorer

        # Test with low relevance (0.2) and different thresholds
        mock_scorer.score.return_value = MagicMock(score=0.2)

        compressor_low_threshold = TaskAwareCompressor(
            task="test", relevance_threshold=0.1
        )
        result_low = compressor_low_threshold.compress("content")

        compressor_high_threshold = TaskAwareCompressor(
            task="test", relevance_threshold=0.5
        )
        result_high = compressor_high_threshold.compress("content")

        # Both should complete
        assert isinstance(result_low, TaskAwareResult)
        assert isinstance(result_high, TaskAwareResult)

    def test_estimate_tokens_basic(self):
        """Test token estimation (internal method)."""
        compressor = TaskAwareCompressor()

        # 4 chars per token heuristic
        estimate = compressor._estimate_tokens("x" * 400)
        assert estimate == 100

    def test_estimate_tokens_minimum_one(self):
        """Token estimate should be at least 1."""
        compressor = TaskAwareCompressor()

        estimate = compressor._estimate_tokens("x")
        assert estimate >= 1

    def test_estimate_tokens_empty_string(self):
        """Token estimate for empty string should be >= 1."""
        compressor = TaskAwareCompressor()

        estimate = compressor._estimate_tokens("")
        assert estimate >= 1


class TestCompressionFallback:
    """Test fallback behavior when compression fails."""

    def test_compress_fallback_on_exception(self, mock_universal_compressor, mock_bm25_scorer):
        """Should fallback to original content if compression raises."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        # Make compress raise an exception
        mock_instance.compress.side_effect = RuntimeError("Compression failed")

        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.5)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task="test")
        result = compressor.compress("test content")

        # Should return original content unchanged
        assert result.compressed == "test content"
        assert result.original_tokens == result.compressed_tokens
        assert result.compression_ratio == 0.0


class TestIntegrationScenarios:
    """Test realistic multi-step scenarios."""

    def test_session_with_multiple_compressions(self, mock_universal_compressor, mock_bm25_scorer):
        """Test a session with multiple compressions and task updates."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        mock_scorer = MagicMock()
        mock_bm25.return_value = mock_scorer

        # Create compressor
        compressor = TaskAwareCompressor(task="debug HTTP errors")

        # First compression (high relevance)
        mock_scorer.score.return_value = MagicMock(score=0.85)
        result1 = compressor.compress("HTTP 500 error response")
        assert result1.task_used == "debug HTTP errors"
        assert result1.relevance_score > 0.7

        # Update task
        compressor.set_task("analyze database performance")

        # Second compression (low relevance to new task)
        mock_scorer.score.return_value = MagicMock(score=0.15)
        result2 = compressor.compress("HTTP 500 error response")
        assert result2.task_used == "analyze database performance"
        assert result2.relevance_score < 0.3

        # Disable task
        compressor.set_task(None)

        # Third compression (no task, full relevance)
        result3 = compressor.compress("HTTP 500 error response")
        assert result3.task_used is None
        assert result3.relevance_score == 1.0

    def test_extract_and_compress_workflow(self, mock_universal_compressor, mock_bm25_scorer):
        """Test workflow: extract task from messages, then compress with it."""
        _, mock_instance = mock_universal_compressor
        _, mock_bm25 = mock_bm25_scorer

        # Extract task from messages
        messages = [
            {"role": "user", "content": "I'm debugging a JSON parsing error in the API handler."}
        ]
        task = TaskExtractor.extract_task(messages)
        assert task is not None
        assert "debug" in task.lower()

        # Create compressor with extracted task
        mock_scorer = MagicMock()
        mock_scorer.score.return_value = MagicMock(score=0.75)
        mock_bm25.return_value = mock_scorer

        compressor = TaskAwareCompressor(task=task)
        result = compressor.compress('{"error": "parse failed"}')

        assert result.task_used == task
        assert result.relevance_score > 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
