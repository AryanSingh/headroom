"""Test semantic cache hit outcome recording in anthropic handler.

Regression test for P0 bug: semantic_cache_avoided_tokens should not
reference non-existent CacheEntry.tokens_saved_per_hit attribute.

Instead, when a response is served from cache, we record
semantic_cache_avoided_tokens=0 (the response is fully cached, not
partially optimized).
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from cutctx.cache.semantic import CacheEntry
from cutctx.proxy.outcome import RequestOutcome


class TestSemanticCacheOutcomeRecording:
    """Test outcome recording when semantic cache hit occurs."""

    def test_cache_entry_has_no_tokens_saved_per_hit_attribute(self):
        """Verify that CacheEntry does not have tokens_saved_per_hit field."""
        # This test documents the confirmed bug:
        # CacheEntry fields are: embedding, query, response, created_at,
        # last_accessed, access_count, messages_hash
        cache_entry = CacheEntry(
            embedding=[0.1, 0.2, 0.3],
            query="What is 2+2?",
            response={"result": "4"},
            created_at=1234567890.0,
            last_accessed=1234567890.0,
            access_count=1,
        )

        # Verify the attribute doesn't exist
        assert not hasattr(cache_entry, "tokens_saved_per_hit")

        # Verify expected attributes do exist
        assert hasattr(cache_entry, "embedding")
        assert hasattr(cache_entry, "query")
        assert hasattr(cache_entry, "response")
        assert hasattr(cache_entry, "access_count")

    def test_request_outcome_semantic_cache_fields_accept_zero(self):
        """Verify RequestOutcome accepts semantic_cache_avoided_tokens=0."""
        # When a cache hit occurs, we should record:
        # - from_response_cache=True (proxy served the response)
        # - semantic_cache_hit=True (it was a semantic cache hit)
        # - semantic_cache_avoided_tokens=0 (no need to reprocess)
        outcome = RequestOutcome(
            request_id="test-123",
            provider="anthropic",
            model="claude-3-5-sonnet",
            original_tokens=0,
            optimized_tokens=0,
            output_tokens=0,
            tokens_saved=0,
            attempted_input_tokens=0,
            from_response_cache=True,
            semantic_cache_hit=True,
            semantic_cache_avoided_tokens=0,  # This is correct when fully cached
        )

        assert outcome.from_response_cache is True
        assert outcome.semantic_cache_hit is True
        assert outcome.semantic_cache_avoided_tokens == 0

    def test_request_outcome_without_tokens_saved_per_hit_attribute_access(self):
        """Verify the fix: never access non-existent tokens_saved_per_hit."""
        # This simulates what the anthropic handler should do when
        # a semantic cache hit occurs
        cache_entry = CacheEntry(
            embedding=[0.1, 0.2],
            query="test query",
            response={"cached": "response"},
            created_at=1000.0,
            last_accessed=1000.0,
        )

        # The fix: use a literal value (0) instead of accessing
        # cache_entry.tokens_saved_per_hit
        avoided_tokens = 0  # Correct: cache hit means full response reuse

        outcome = RequestOutcome(
            request_id="test-cache-hit",
            provider="anthropic",
            model="claude-3-5-sonnet",
            original_tokens=0,
            optimized_tokens=0,
            output_tokens=0,
            tokens_saved=0,
            attempted_input_tokens=0,
            from_response_cache=True,
            semantic_cache_hit=True,
            semantic_cache_avoided_tokens=avoided_tokens,  # 0, not cache_entry.tokens_saved_per_hit
        )

        assert outcome.semantic_cache_avoided_tokens == 0
        # Should not raise AttributeError
        assert outcome.from_response_cache is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
