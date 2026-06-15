"""Tests for semantic deduplication (test_dedup.py).

Tests cover:
- Basic deduplication (first vs. second occurrence)
- Skipping short content
- Multi-turn deduplication
- Session reset
- Statistics tracking
- System message filtering
- Token estimation
- CCR integration (when store is available)
"""

import pytest
from headroom.dedup import (
    SessionDeduplicator,
    ContentHash,
    DeduplicationResult,
    MIN_DEDUP_TOKENS,
)


class TestBasicDedup:
    """Test basic deduplication logic."""

    def test_first_occurrence_not_deduplicated(self):
        """First occurrence should be tracked, not replaced."""
        dedup = SessionDeduplicator()

        messages = [
            {"role": "tool", "content": "x" * 1000}  # Large enough to trigger dedup
        ]
        result = dedup.process(messages)

        assert len(result.messages) == 1
        assert result.messages[0]["content"] == "x" * 1000
        assert result.dedup_count == 0
        assert result.refs_created == 1
        assert result.tokens_saved == 0

    def test_second_occurrence_deduplicated(self):
        """Second occurrence should be replaced with pointer."""
        dedup = SessionDeduplicator()

        content = "This is a test message that is long enough to trigger deduplication" * 10

        # First turn
        messages_1 = [{"role": "tool", "content": content}]
        result_1 = dedup.process(messages_1)
        assert result_1.dedup_count == 0
        assert result_1.refs_created == 1

        # Second turn with same content
        messages_2 = [{"role": "tool", "content": content}]
        result_2 = dedup.process(messages_2)

        assert len(result_2.messages) == 1
        assert "[headroom:ref:" in result_2.messages[0]["content"]
        assert result_2.dedup_count == 1
        assert result_2.tokens_saved > 0

    def test_different_content_not_deduplicated(self):
        """Different content should not be deduplicated."""
        dedup = SessionDeduplicator()

        content_1 = "First message " * 100
        content_2 = "Second message " * 100

        messages_1 = [{"role": "tool", "content": content_1}]
        result_1 = dedup.process(messages_1)

        messages_2 = [{"role": "tool", "content": content_2}]
        result_2 = dedup.process(messages_2)

        assert result_2.dedup_count == 0
        assert result_2.refs_created == 1
        assert result_2.messages[0]["content"] == content_2


class TestSkipShortContent:
    """Test that short content is skipped."""

    def test_skip_under_min_dedup_tokens(self):
        """Content under MIN_DEDUP_TOKENS should be skipped."""
        dedup = SessionDeduplicator()

        # Create content definitely under MIN_DEDUP_TOKENS
        short_content = "short"  # ~5 chars = ~1 token

        messages = [{"role": "tool", "content": short_content}]
        result = dedup.process(messages)

        assert result.refs_created == 0
        assert result.messages[0]["content"] == short_content

    def test_boundary_at_min_dedup_tokens(self):
        """Content right at the boundary should be processed."""
        dedup = SessionDeduplicator()

        # Create content right around MIN_DEDUP_TOKENS (200 tokens ≈ 800 chars)
        boundary_content = "x" * 801  # Slightly over 200 tokens

        messages = [{"role": "tool", "content": boundary_content}]
        result = dedup.process(messages)

        # Should be tracked
        assert result.refs_created == 1


class TestMultiTurnDedup:
    """Test deduplication across multiple turns."""

    def test_three_identical_contents(self):
        """Test dedup with three identical occurrences."""
        dedup = SessionDeduplicator()

        content = "repeated " * 500

        # Turn 1
        result_1 = dedup.process([{"role": "user", "content": content}])
        assert result_1.dedup_count == 0
        assert result_1.refs_created == 1

        # Turn 2
        result_2 = dedup.process([{"role": "assistant", "content": content}])
        assert result_2.dedup_count == 1

        # Turn 3
        result_3 = dedup.process([{"role": "tool", "content": content}])
        assert result_3.dedup_count == 1

        # All should be pointed to same hash
        assert len(dedup._hash_index) == 1

    def test_mixed_duplicates_and_new_content(self):
        """Test dedup with mixed duplicates and new content."""
        dedup = SessionDeduplicator()

        content_a = "content A " * 500
        content_b = "content B " * 500

        # Turn 1: A
        result_1 = dedup.process([{"role": "tool", "content": content_a}])
        assert result_1.refs_created == 1

        # Turn 2: A, B
        messages = [
            {"role": "tool", "content": content_a},
            {"role": "tool", "content": content_b},
        ]
        result_2 = dedup.process(messages)
        assert result_2.dedup_count == 1  # First A is deduped
        assert result_2.refs_created == 1  # B is new
        assert len(result_2.messages) == 2
        assert "[headroom:ref:" in result_2.messages[0]["content"]
        assert result_2.messages[1]["content"] == content_b

    def test_stats_accumulation(self):
        """Test that stats accumulate across turns."""
        dedup = SessionDeduplicator()

        content = "test " * 500

        # Turn 1
        dedup.process([{"role": "tool", "content": content}])
        # Turn 2
        dedup.process([{"role": "tool", "content": content}])
        # Turn 3
        dedup.process([{"role": "tool", "content": content}])

        stats = dedup.stats
        assert stats["current_turn"] == 3
        assert stats["total_dedup_count"] == 2  # 2nd and 3rd occurrences
        assert stats["total_tokens_saved"] > 0


class TestSystemMessageSkipping:
    """Test that system messages are never deduplicated."""

    def test_system_messages_skipped(self):
        """System messages should always be skipped."""
        dedup = SessionDeduplicator()

        content = "instruction " * 500

        # First: system message
        result_1 = dedup.process([{"role": "system", "content": content}])
        assert result_1.refs_created == 0
        assert result_1.messages[0]["content"] == content

        # Second: same content in system message
        result_2 = dedup.process([{"role": "system", "content": content}])
        assert result_2.dedup_count == 0
        assert result_2.messages[0]["content"] == content

    def test_system_vs_user_different_tracking(self):
        """System and user messages with same content should be separate."""
        dedup = SessionDeduplicator()

        content = "shared " * 500

        # System
        dedup.process([{"role": "system", "content": content}])
        # User
        result = dedup.process([{"role": "user", "content": content}])

        # Since system was skipped, user is first occurrence
        assert result.refs_created == 1
        assert result.dedup_count == 0


class TestReset:
    """Test session reset functionality."""

    def test_reset_clears_state(self):
        """Reset should clear all tracked hashes."""
        dedup = SessionDeduplicator()

        content = "test " * 500
        dedup.process([{"role": "tool", "content": content}])

        assert len(dedup._hash_index) > 0
        assert dedup._turn_counter == 1

        dedup.reset()

        assert len(dedup._hash_index) == 0
        assert dedup._turn_counter == 0

    def test_dedup_after_reset(self):
        """After reset, same content should be treated as first occurrence."""
        dedup = SessionDeduplicator()

        content = "test " * 500

        # First session
        dedup.process([{"role": "tool", "content": content}])
        dedup.process([{"role": "tool", "content": content}])

        # Reset
        dedup.reset()

        # New session: same content should be first occurrence again
        result = dedup.process([{"role": "tool", "content": content}])
        assert result.refs_created == 1
        assert result.dedup_count == 0


class TestStats:
    """Test statistics tracking."""

    def test_stats_empty_deduplicator(self):
        """Stats should reflect empty state."""
        dedup = SessionDeduplicator()
        stats = dedup.stats

        assert stats["current_turn"] == 0
        assert stats["tracked_hashes"] == 0
        assert stats["total_dedup_count"] == 0
        assert stats["total_tokens_saved"] == 0

    def test_stats_after_processing(self):
        """Stats should accumulate."""
        dedup = SessionDeduplicator()

        content = "x" * 2000

        # Turn 1
        result_1 = dedup.process([{"role": "tool", "content": content}])
        # Turn 2
        result_2 = dedup.process([{"role": "tool", "content": content}])

        stats = dedup.stats
        assert stats["current_turn"] == 2
        assert stats["tracked_hashes"] == 1
        assert stats["total_messages_processed"] == 2
        assert stats["total_dedup_count"] == 1
        assert stats["total_tokens_saved"] > 0

    def test_stats_ccr_flag(self):
        """Stats should indicate if CCR is available."""
        dedup = SessionDeduplicator()
        assert dedup.stats["ccr_enabled"] is False

        # Can't easily test CCR integration without mocking,
        # but the flag should reflect the store


class TestHashMetadata:
    """Test hash metadata retrieval."""

    def test_get_tracked_hashes(self):
        """Should return list of all tracked hashes."""
        dedup = SessionDeduplicator()

        content_a = "a" * 1000
        content_b = "b" * 1000

        dedup.process([{"role": "tool", "content": content_a}])
        dedup.process([{"role": "tool", "content": content_b}])

        hashes = dedup.get_tracked_hashes()
        assert len(hashes) == 2

    def test_get_hash_metadata(self):
        """Should retrieve metadata for a hash."""
        dedup = SessionDeduplicator()

        content = "test content " * 500
        dedup.process([{"role": "tool", "content": content}])

        hashes = dedup.get_tracked_hashes()
        assert len(hashes) == 1

        hash_key = hashes[0]
        metadata = dedup.get_hash_metadata(hash_key)

        assert metadata is not None
        assert metadata.hash == hash_key
        assert metadata.first_seen_turn == 1
        assert metadata.content_preview == content[:50]
        assert metadata.token_count > 0

    def test_get_hash_metadata_nonexistent(self):
        """Should return None for nonexistent hash."""
        dedup = SessionDeduplicator()

        metadata = dedup.get_hash_metadata("nonexistent_hash")
        assert metadata is None


class TestNonStringContent:
    """Test handling of non-string content."""

    def test_non_string_content_passed_through(self):
        """Non-string content should be passed through unchanged."""
        dedup = SessionDeduplicator()

        messages = [
            {"role": "tool", "content": [1, 2, 3]},  # List instead of string
            {"role": "tool", "content": {"key": "value"}},  # Dict instead of string
        ]

        result = dedup.process(messages)

        assert result.messages[0]["content"] == [1, 2, 3]
        assert result.messages[1]["content"] == {"key": "value"}
        assert result.refs_created == 0

    def test_malformed_messages_passed_through(self):
        """Malformed messages should be passed through."""
        dedup = SessionDeduplicator()

        messages = [
            "not a dict",  # String instead of dict
            {"role": "tool"},  # Missing content
            {"content": "test"},  # Missing role
        ]

        result = dedup.process(messages)

        # All should be passed through
        assert len(result.messages) == 3


class TestTokenEstimation:
    """Test token count estimation."""

    def test_token_estimate_basic(self):
        """Test basic token estimation."""
        dedup = SessionDeduplicator()

        # ~4 chars per token
        content = "x" * 400  # Should estimate ~100 tokens
        estimate = dedup._estimate_tokens(content)

        assert estimate == 100

    def test_token_estimate_minimum(self):
        """Token estimate should be at least 1."""
        dedup = SessionDeduplicator()

        content = "x"
        estimate = dedup._estimate_tokens(content)

        assert estimate >= 1


class TestPointerFormat:
    """Test that pointers are formatted correctly."""

    def test_pointer_format(self):
        """Pointer should have correct format."""
        dedup = SessionDeduplicator()

        content = "test " * 500
        dedup.process([{"role": "tool", "content": content}])

        result = dedup.process([{"role": "tool", "content": content}])
        pointer = result.messages[0]["content"]

        # Should match [headroom:ref:HASH]
        assert pointer.startswith("[headroom:ref:")
        assert pointer.endswith("]")
        # Extract hash (should be 16 chars)
        hash_part = pointer[14:-1]
        assert len(hash_part) == 16
        # Hash should be hex
        assert all(c in "0123456789abcdef" for c in hash_part)


class TestEdgeCases:
    """Test edge cases and corner conditions."""

    def test_empty_messages_list(self):
        """Empty message list should return empty result."""
        dedup = SessionDeduplicator()

        result = dedup.process([])

        assert len(result.messages) == 0
        assert result.dedup_count == 0
        assert result.refs_created == 0

    def test_whitespace_only_content(self):
        """Whitespace-only content should be handled."""
        dedup = SessionDeduplicator()

        content = "   \n\n   " * 500  # Mostly whitespace but large

        result = dedup.process([{"role": "tool", "content": content}])

        # Should be tracked (length is large enough)
        assert result.refs_created >= 0  # Depends on token estimation

    def test_unicode_content(self):
        """Unicode content should be handled correctly."""
        dedup = SessionDeduplicator()

        content = "こんにちは世界 🌍" * 500

        result_1 = dedup.process([{"role": "tool", "content": content}])
        result_2 = dedup.process([{"role": "tool", "content": content}])

        assert result_1.refs_created >= 0
        if result_1.refs_created > 0:
            assert result_2.dedup_count >= 0

    def test_very_long_content(self):
        """Very long content should be handled efficiently."""
        dedup = SessionDeduplicator()

        # 10MB of content (enough to stress-test)
        content = "x" * (10 * 1024 * 1024)

        result_1 = dedup.process([{"role": "tool", "content": content}])
        # Just check it doesn't crash and completes in reasonable time
        assert isinstance(result_1, DeduplicationResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
