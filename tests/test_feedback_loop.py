"""Tests for the intelligence feedback loop — connecting CCR retrievals,
profile recommendations, and content router overrides.

Initiative 1: Close the intelligence loop.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from cutctx.transforms.content_router import (
    CompressionStrategy,
    ContentRouter,
    ContentRouterConfig,
)

# =============================================================================
# Test 1: TOIN record_retrieval is called on CCR retrieval (full + search)
# =============================================================================


class TestTOINRecordedOnRetrieval:
    """Verify that CCRResponseHandler._execute_retrieval() records feedback."""

    def _make_mock_entry(self, **kwargs: Any) -> MagicMock:
        """Create a mock CompressionEntry with controllable attributes."""
        entry = MagicMock()
        entry.tool_signature_hash = kwargs.get("tool_signature_hash", "sig_hash_abc")
        entry.compression_strategy = kwargs.get("compression_strategy", "smart_crusher")
        entry.original_content = kwargs.get("original_content", '{"key": "value"}')
        entry.original_item_count = kwargs.get("original_item_count", 42)
        entry.hash = kwargs.get("hash_key", "test_hash_123")
        return entry

    def _make_mock_store(self, entry: MagicMock | None = None) -> MagicMock:
        """Create a mock compression store."""
        store = MagicMock()
        store.retrieve.return_value = entry
        store.search.return_value = [{"id": 1, "text": "result"}]
        store.get_entry_status.return_value = {"status": "available", "default_ttl_seconds": 3600}
        return store

    def test_toin_recorded_on_full_retrieval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Full retrieval path should call TOIN.record_retrieval with correct params."""
        from cutctx.ccr.response_handler import (
            CCRResponseHandler,
            CCRToolCall,
            ResponseHandlerConfig,
        )

        # Mock TOIN at its source module (get_toin is imported locally inside _execute_retrieval)
        mock_toin = MagicMock()
        monkeypatch.setattr("cutctx.telemetry.toin.get_toin", lambda: mock_toin)

        # Mock ProfileManager
        mock_profile = MagicMock()
        monkeypatch.setattr("cutctx.profiles.ProfileManager.get_profile", lambda: mock_profile)

        # Mock compression store
        entry = self._make_mock_entry(
            tool_signature_hash="test_sig_hash",
            compression_strategy="code_aware",
        )
        mock_store = self._make_mock_store(entry)
        monkeypatch.setattr("cutctx.ccr.response_handler.get_compression_store", lambda: mock_store)

        handler = CCRResponseHandler(ResponseHandlerConfig(enabled=True))
        ccr_call = CCRToolCall(tool_call_id="call_1", hash_key="test_hash_123")

        result = handler._execute_retrieval(ccr_call)

        assert result.success is True
        assert result.was_search is False

        # Verify TOIN.record_retrieval was called with correct params
        mock_toin.record_retrieval.assert_called_once()
        call_kwargs = mock_toin.record_retrieval.call_args[1]
        assert call_kwargs["tool_signature_hash"] == "test_sig_hash"
        assert call_kwargs["retrieval_type"] == "full"
        assert call_kwargs["strategy"] == "code_aware"

        # Verify profile was updated
        mock_profile.update_from_ccr_retrieval.assert_called_once()

    def test_toin_recorded_on_search_retrieval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Search path should call TOIN.record_retrieval with correct params."""
        from cutctx.ccr.response_handler import (
            CCRResponseHandler,
            CCRToolCall,
            ResponseHandlerConfig,
        )

        # Mock TOIN at its source module
        mock_toin = MagicMock()
        monkeypatch.setattr("cutctx.telemetry.toin.get_toin", lambda: mock_toin)

        # Mock compression store (entry status is available so we reach search)
        store = MagicMock()
        store.get_entry_status.return_value = {"status": "available", "default_ttl_seconds": 3600}
        store.search.return_value = [{"id": 1, "text": "match"}]
        monkeypatch.setattr("cutctx.ccr.response_handler.get_compression_store", lambda: store)

        handler = CCRResponseHandler(ResponseHandlerConfig(enabled=True))
        ccr_call = CCRToolCall(
            tool_call_id="call_1",
            hash_key="test_hash_123",
            query="search term",
        )

        result = handler._execute_retrieval(ccr_call)

        assert result.success is True
        assert result.was_search is True

        # Verify TOIN.record_retrieval was called with correct params
        mock_toin.record_retrieval.assert_called_once()
        call_kwargs = mock_toin.record_retrieval.call_args[1]
        assert call_kwargs["retrieval_type"] == "search"
        assert call_kwargs["query"] == "search term"


# =============================================================================
# Test 2: per_type_overrides affect bias
# =============================================================================


class TestPerTypeOverridesAffectBias:
    """Verify that ContentRouter applies per-type override bias adjustments."""

    def test_smart_crusher_bias_adjusted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting per_type_overrides for smart_crusher should adjust bias."""
        # Create a config with per_type_overrides
        config = ContentRouterConfig(
            enable_code_aware=False,
            enable_search_compressor=False,
            enable_log_compressor=False,
            enable_html_extractor=False,
            enable_image_optimizer=False,
            per_type_overrides={
                "smart_crusher": {"recommended_ratio": 0.5},
            },
        )
        router = ContentRouter(config)

        # Mock SmartCrusher to capture the bias
        captured_bias: list[float] = []

        class MockCrusher:
            def crush(self, content: str, **kwargs: Any) -> MagicMock:
                captured_bias.append(kwargs.get("bias", 1.0))
                result = MagicMock()
                result.compressed = '{"compressed": "data"}'
                result.strategy = "lossy"
                return result

        mock_crusher = MockCrusher()
        monkeypatch.setattr(router, "_get_smart_crusher", lambda: mock_crusher)

        # Create JSON array content that routes to SMART_CRUSHER
        json_content = json.dumps([{"id": i, "name": f"item_{i}"} for i in range(20)])

        result = router.compress(json_content, bias=1.0)

        assert result.strategy_used is not None

        # The bias should have been adjusted: 1.0 * (1.0 / max(0.5, 0.1)) = 2.0
        assert len(captured_bias) > 0
        # recommended_ratio=0.5 → bias_multiplier = 1.0/0.5 = 2.0
        # original bias = 1.0 → adjusted bias ≈ 2.0
        assert abs(captured_bias[0] - 2.0) < 0.01, (
            f"Expected bias ~2.0 for recommended_ratio=0.5, got {captured_bias[0]}"
        )

    def test_bias_unaffected_when_no_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without per_type_overrides, bias should remain unchanged."""
        config = ContentRouterConfig(
            enable_code_aware=False,
            enable_search_compressor=False,
            enable_log_compressor=False,
            enable_html_extractor=False,
            enable_image_optimizer=False,
            enable_kompress=False,
            # No per_type_overrides
        )
        router = ContentRouter(config)

        captured_bias: list[float] = []

        class MockCrusher:
            def crush(self, content: str, **kwargs: Any) -> MagicMock:
                captured_bias.append(kwargs.get("bias", 1.0))
                result = MagicMock()
                result.compressed = '{"compressed": "data"}'
                result.strategy = "lossy"
                return result

        mock_crusher = MockCrusher()
        monkeypatch.setattr(router, "_get_smart_crusher", lambda: mock_crusher)

        json_content = json.dumps([{"id": 1, "name": "test"}])
        result = router.compress(json_content, bias=1.5)

        assert result.strategy_used is not None
        assert len(captured_bias) > 0
        assert abs(captured_bias[0] - 1.5) < 0.01, (
            f"Expected bias unchanged at 1.5, got {captured_bias[0]}"
        )


# =============================================================================
# Test 3: Profile updates on retrieval
# =============================================================================


class TestProfileUpdatesOnRetrieval:
    """Verify that _execute_retrieval updates the per-workspace profile."""

    def test_profile_update_on_full_retrieval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Full retrieval should update profile with correct content_type."""
        from cutctx.ccr.response_handler import (
            CCRResponseHandler,
            CCRToolCall,
            ResponseHandlerConfig,
        )

        # Mock ProfileManager at its source module
        mock_profile = MagicMock()
        monkeypatch.setattr("cutctx.profiles.ProfileManager.get_profile", lambda: mock_profile)

        # Mock TOIN (required to prevent actual TOIN interactions)
        mock_toin = MagicMock()
        monkeypatch.setattr("cutctx.telemetry.toin.get_toin", lambda: mock_toin)

        # Mock store with a code-aware compression entry
        class MockEntry:
            tool_signature_hash = "sig_abc"
            compression_strategy = "code_aware"
            original_content = "def foo(): pass"
            original_item_count = 5
            hash = "test_hash"

        store = MagicMock()
        store.retrieve.return_value = MockEntry()
        store.get_entry_status.return_value = {"status": "available", "default_ttl_seconds": 3600}
        monkeypatch.setattr("cutctx.ccr.response_handler.get_compression_store", lambda: store)

        handler = CCRResponseHandler(ResponseHandlerConfig(enabled=True))
        ccr_call = CCRToolCall(tool_call_id="call_1", hash_key="test_hash")

        result = handler._execute_retrieval(ccr_call)

        assert result.success is True

        # Verify profile.update_from_ccr_retrieval was called with "source_code"
        mock_profile.update_from_ccr_retrieval.assert_called_once_with("source_code")

    def test_profile_updated_for_unknown_strategy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Full retrieval with unknown strategy should pass 'unknown' to profile."""
        from cutctx.ccr.response_handler import (
            CCRResponseHandler,
            CCRToolCall,
            ResponseHandlerConfig,
        )

        mock_profile = MagicMock()
        monkeypatch.setattr("cutctx.profiles.ProfileManager.get_profile", lambda: mock_profile)
        mock_toin = MagicMock()
        monkeypatch.setattr("cutctx.telemetry.toin.get_toin", lambda: mock_toin)

        class MockEntry:
            tool_signature_hash = None
            compression_strategy = None
            original_content = "some content"
            original_item_count = 3
            hash = "test_hash"

        store = MagicMock()
        store.retrieve.return_value = MockEntry()
        store.get_entry_status.return_value = {"status": "available", "default_ttl_seconds": 3600}
        monkeypatch.setattr("cutctx.ccr.response_handler.get_compression_store", lambda: store)

        handler = CCRResponseHandler(ResponseHandlerConfig(enabled=True))
        ccr_call = CCRToolCall(tool_call_id="call_1", hash_key="test_hash")

        result = handler._execute_retrieval(ccr_call)
        assert result.success is True

        mock_profile.update_from_ccr_retrieval.assert_called_once_with("unknown")


# =============================================================================
# Test 4: Empty overrides no-op
# =============================================================================


class TestEmptyOverridesNoop:
    """Verify that empty per_type_overrides causes no change to behavior."""

    def test_empty_overrides_no_crash(self) -> None:
        """Empty per_type_overrides dict should not affect normal compression."""
        config = ContentRouterConfig(
            per_type_overrides={},  # explicitly empty
            fallback_strategy=CompressionStrategy.PASSTHROUGH,
            enable_kompress=False,
            enable_smart_crusher=False,
            enable_code_aware=False,
            enable_search_compressor=False,
            enable_log_compressor=False,
            enable_html_extractor=False,
            enable_image_optimizer=False,
        )
        router = ContentRouter(config)

        # Simple text content — should not crash and preserve content
        text = "Hello, this is a test message that should remain unchanged."
        result = router.compress(text)

        assert result is not None
        # Content should be preserved (no compression applied)
        assert result.compressed == text
        # Strategy will be TEXT or PASSTHROUGH depending on routing — both valid

    def test_empty_overrides_with_override_recommended_ratio(self) -> None:
        """Only matching overrides should affect bias; non-matching should not."""
        config = ContentRouterConfig(
            per_type_overrides={
                "code_aware": {"recommended_ratio": 0.8},
                # smart_crusher intentionally absent
            },
            fallback_strategy=CompressionStrategy.PASSTHROUGH,
            enable_kompress=False,
            enable_smart_crusher=False,
            enable_code_aware=False,
            enable_search_compressor=False,
            enable_log_compressor=False,
            enable_html_extractor=False,
            enable_image_optimizer=False,
        )
        router = ContentRouter(config)

        # Simple text — should go to text/passthrough, not affected by code_aware override
        text = "Just some plain text content."
        result = router.compress(text)

        assert result is not None
        assert result.compressed is not None
        assert result.strategy_used is not None


# =============================================================================
# Test 5: ContentRouterConfig per_type_overrides field
# =============================================================================


def test_per_type_overrides_default_empty() -> None:
    """Default ContentRouterConfig should have empty per_type_overrides."""
    config = ContentRouterConfig()
    assert config.per_type_overrides == {}


def test_per_type_overrides_accepts_values() -> None:
    """per_type_overrides should accept and store values."""
    overrides = {
        "code_aware": {"recommended_ratio": 0.7},
        "smart_crusher": {"recommended_ratio": 0.5},
    }
    config = ContentRouterConfig(per_type_overrides=overrides)
    assert config.per_type_overrides == overrides
    assert config.per_type_overrides["code_aware"]["recommended_ratio"] == 0.7
    assert config.per_type_overrides["smart_crusher"]["recommended_ratio"] == 0.5


# =============================================================================
# Test 6: _strategy_to_content_type helper
# =============================================================================


def test_strategy_to_content_type() -> None:
    """Verify strategy-to-content-type mapping."""
    from cutctx.ccr.response_handler import _strategy_to_content_type

    assert _strategy_to_content_type("smart_crusher") == "json_array"
    assert _strategy_to_content_type("code_aware") == "source_code"
    assert _strategy_to_content_type("log") == "build_output"
    assert _strategy_to_content_type("search") == "search_results"
    assert _strategy_to_content_type("diff") == "git_diff"
    assert _strategy_to_content_type("kompress") == "plain_text"
    assert _strategy_to_content_type("llmlingua") == "plain_text"
    assert _strategy_to_content_type("") == "unknown"
    assert _strategy_to_content_type(None) == "unknown"
    assert _strategy_to_content_type("unknown_strategy") == "unknown"
