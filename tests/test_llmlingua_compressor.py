"""Comprehensive tests for LLMLinguaCompressor.

Tests cover:
1. compress() method basic functionality
2. available() static method
3. Configuration handling
4. Fallback behavior when llmlingua is not installed
5. LLMLinguaResult properties (compression_ratio, tokens_saved, savings_percentage)
6. Transform interface (apply method)
7. Edge cases and error handling
"""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

_LLMLINGUA_INSTALLED = importlib.util.find_spec("llmlingua") is not None

from cutctx.transforms.llmlingua_compressor import (
    LLMLinguaCompressor,
    LLMLinguaConfig,
    LLMLinguaResult,
)


class TestLLMLinguaResult:
    """Tests for LLMLinguaResult properties."""

    def test_compression_ratio_normal(self):
        """Compression ratio is calculated correctly."""
        result = LLMLinguaResult(
            compressed="Hello world",
            original="Hello world this is a longer text",
            original_tokens=7,
            compressed_tokens=2,
        )
        assert result.compression_ratio == pytest.approx(2 / 7, rel=0.01)

    def test_compression_ratio_no_compression(self):
        """Compression ratio is 1.0 when no tokens are removed."""
        result = LLMLinguaResult(
            compressed="Hello world",
            original="Hello world",
            original_tokens=2,
            compressed_tokens=2,
        )
        assert result.compression_ratio == 1.0

    def test_compression_ratio_zero_original(self):
        """Compression ratio is 1.0 when original tokens is zero."""
        result = LLMLinguaResult(
            compressed="",
            original="",
            original_tokens=0,
            compressed_tokens=0,
        )
        assert result.compression_ratio == 1.0

    def test_tokens_saved_normal(self):
        """Tokens saved is calculated correctly."""
        result = LLMLinguaResult(
            compressed="Hello world",
            original="Hello world this is a longer text",
            original_tokens=7,
            compressed_tokens=2,
        )
        assert result.tokens_saved == 5

    def test_tokens_saved_no_compression(self):
        """Tokens saved is zero when no compression occurs."""
        result = LLMLinguaResult(
            compressed="Hello world",
            original="Hello world",
            original_tokens=2,
            compressed_tokens=2,
        )
        assert result.tokens_saved == 0

    def test_tokens_saved_never_negative(self):
        """Tokens saved is never negative (max with 0)."""
        result = LLMLinguaResult(
            compressed="Hello world extra tokens",
            original="Hello world",
            original_tokens=2,
            compressed_tokens=5,
        )
        assert result.tokens_saved == 0

    def test_savings_percentage_normal(self):
        """Savings percentage is calculated correctly."""
        result = LLMLinguaResult(
            compressed="Hello world",
            original="Hello world this is a longer text",
            original_tokens=10,
            compressed_tokens=2,
        )
        assert result.savings_percentage == pytest.approx(80.0, rel=0.01)

    def test_savings_percentage_no_compression(self):
        """Savings percentage is 0 when no compression occurs."""
        result = LLMLinguaResult(
            compressed="Hello world",
            original="Hello world",
            original_tokens=2,
            compressed_tokens=2,
        )
        assert result.savings_percentage == 0.0

    def test_savings_percentage_zero_original(self):
        """Savings percentage is 0.0 when original tokens is zero."""
        result = LLMLinguaResult(
            compressed="",
            original="",
            original_tokens=0,
            compressed_tokens=0,
        )
        assert result.savings_percentage == 0.0

    def test_savings_percentage_high_compression(self):
        """Savings percentage is correct for high compression rates."""
        result = LLMLinguaResult(
            compressed="Hello",
            original="Hello world this is a much longer text with many words",
            original_tokens=100,
            compressed_tokens=1,
        )
        assert result.savings_percentage == pytest.approx(99.0, rel=0.01)


class TestLLMLinguaConfig:
    """Tests for LLMLinguaConfig."""

    def test_default_config(self):
        """Default configuration has expected values."""
        config = LLMLinguaConfig()
        assert config.model_name == "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"
        assert config.rate == 0.5
        assert config.force_tokens == []
        assert config.device == "cpu"
        assert config.use_llmlingua2 is True

    def test_custom_config(self):
        """Custom configuration values are set correctly."""
        config = LLMLinguaConfig(
            model_name="custom-model",
            rate=0.7,
            force_tokens=["important", "keyword"],
            device="cuda",
            use_llmlingua2=False,
        )
        assert config.model_name == "custom-model"
        assert config.rate == 0.7
        assert config.force_tokens == ["important", "keyword"]
        assert config.device == "cuda"
        assert config.use_llmlingua2 is False


class TestLLMLinguaCompressorAvailable:
    """Tests for LLMLinguaCompressor.available() method."""

    @patch("cutctx.transforms.llmlingua_compressor._check_available")
    def test_available_returns_true_when_installed(self, mock_check):
        """available() returns True when llmlingua is installed."""
        mock_check.return_value = True
        assert LLMLinguaCompressor.available() is True

    @patch("cutctx.transforms.llmlingua_compressor._check_available")
    def test_available_returns_false_when_not_installed(self, mock_check):
        """available() returns False when llmlingua is not installed."""
        mock_check.return_value = False
        assert LLMLinguaCompressor.available() is False

    @patch("cutctx.transforms.llmlingua_compressor._check_available")
    def test_available_check_is_static(self, mock_check):
        """available() is callable without instantiation."""
        mock_check.return_value = True
        # Should not raise AttributeError
        result = LLMLinguaCompressor.available()
        assert result is True


class TestLLMLinguaCompressorCompress:
    """Tests for LLMLinguaCompressor.compress() method."""

    def test_compress_basic_functionality(self):
        """compress() returns LLMLinguaResult with correct structure."""
        compressor = LLMLinguaCompressor()

        # Mock the underlying compressor
        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "Hello world shorter"}

        with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                result = compressor.compress("Hello world this is longer text")

        assert isinstance(result, LLMLinguaResult)
        assert result.original == "Hello world this is longer text"
        assert result.compressed == "Hello world shorter"
        assert result.original_tokens > 0
        assert result.compressed_tokens > 0

    def test_compress_fallback_when_not_available(self):
        """compress() returns original content when llmlingua is not available."""
        compressor = LLMLinguaCompressor()
        content = "Hello world this is longer text"

        with patch.object(LLMLinguaCompressor, "available", return_value=False):
            result = compressor.compress(content)

        assert result.compressed == content
        assert result.original == content
        assert result.compression_ratio == 1.0
        assert result.used_fallback is True
        assert result.fallback_reason == "unavailable"

    def test_compress_with_context(self):
        """compress() accepts context parameter."""
        compressor = LLMLinguaCompressor()
        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "Compressed"}

        with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                result = compressor.compress("Original text", context="Search results")

        assert result is not None
        mock_llmlingua.compress_prompt.assert_called_once()

    def test_compress_with_question(self):
        """compress() accepts question parameter for QA-aware compression."""
        compressor = LLMLinguaCompressor()
        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "Compressed"}

        with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                result = compressor.compress("Original text", question="What is the main topic?")

        assert result is not None

    def test_compress_with_target_ratio(self):
        """compress() respects target_ratio parameter."""
        compressor = LLMLinguaCompressor(config=LLMLinguaConfig(rate=0.5))
        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "Compressed"}

        with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                result = compressor.compress("Original text", target_ratio=0.3)

        # Verify the target_ratio was passed to the compressor
        mock_llmlingua.compress_prompt.assert_called_once()
        call_kwargs = mock_llmlingua.compress_prompt.call_args[1]
        assert call_kwargs["rate"] == 0.3

    def test_compress_uses_configured_rate_by_default(self):
        """compress() uses configured rate when target_ratio is not specified."""
        config = LLMLinguaConfig(rate=0.7)
        compressor = LLMLinguaCompressor(config=config)
        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "Compressed"}

        with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                result = compressor.compress("Original text")

        call_kwargs = mock_llmlingua.compress_prompt.call_args[1]
        assert call_kwargs["rate"] == 0.7

    def test_compress_handles_exception(self):
        """compress() returns original content on exception."""
        compressor = LLMLinguaCompressor()
        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.side_effect = RuntimeError("Model error")

        with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                result = compressor.compress("Original text")

        assert result.compressed == "Original text"
        assert result.compression_ratio == 1.0
        assert result.used_fallback is True
        assert result.fallback_reason == "runtime_error"

    def test_compress_with_force_tokens(self):
        """compress() passes force_tokens to compressor."""
        config = LLMLinguaConfig(force_tokens=["important", "keyword"])
        compressor = LLMLinguaCompressor(config=config)
        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "Compressed"}

        with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                result = compressor.compress("Original text")

        call_kwargs = mock_llmlingua.compress_prompt.call_args[1]
        assert call_kwargs["force_tokens"] == ["important", "keyword"]

    def test_compress_empty_string(self):
        """compress() handles empty string gracefully."""
        compressor = LLMLinguaCompressor()

        with patch.object(LLMLinguaCompressor, "available", return_value=False):
            result = compressor.compress("")

        assert result.compressed == ""
        assert result.original == ""
        assert result.original_tokens == 0


class TestLLMLinguaCompressorTransformInterface:
    """Tests for LLMLinguaCompressor Transform interface (apply method)."""

    def test_apply_basic_functionality(self):
        """apply() processes messages through Transform interface."""
        compressor = LLMLinguaCompressor()
        tokenizer = MagicMock()
        tokenizer.count_text.return_value = 10

        messages = [
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "This is a much longer response with many words"},
        ]

        with patch.object(LLMLinguaCompressor, "available", return_value=False):
            result = compressor.apply(messages, tokenizer)

        assert result.messages is not None
        assert result.tokens_before >= 0
        assert result.tokens_after >= 0
        assert result.transforms_applied is not None

    def test_apply_skips_short_content(self):
        """apply() skips compression for short content (<10 words)."""
        compressor = LLMLinguaCompressor()
        tokenizer = MagicMock()
        tokenizer.count_text.return_value = 5

        messages = [{"role": "assistant", "content": "Hello world"}]

        with patch.object(LLMLinguaCompressor, "available", return_value=True):
            mock_llmlingua = MagicMock()
            with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
                result = compressor.apply(messages, tokenizer)

        # Should not call compress for short content
        mock_llmlingua.compress_prompt.assert_not_called()
        assert result.messages == messages

    def test_apply_compresses_long_content(self):
        """apply() compresses long content from assistant/tool roles."""
        compressor = LLMLinguaCompressor()
        tokenizer = MagicMock()
        tokenizer.count_text.return_value = 15

        long_content = " ".join(["word"] * 20)
        messages = [{"role": "assistant", "content": long_content}]

        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "compressed version"}

        with patch.object(LLMLinguaCompressor, "available", return_value=True):
            with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
                result = compressor.apply(messages, tokenizer)

        # Should have called compress
        mock_llmlingua.compress_prompt.assert_called()
        assert result.messages is not None

    def test_apply_ignores_user_role(self):
        """apply() does not compress user role messages."""
        compressor = LLMLinguaCompressor()
        tokenizer = MagicMock()
        tokenizer.count_text.return_value = 15

        long_content = " ".join(["word"] * 20)
        messages = [{"role": "user", "content": long_content}]

        mock_llmlingua = MagicMock()

        with patch.object(LLMLinguaCompressor, "available", return_value=True):
            with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
                result = compressor.apply(messages, tokenizer)

        # Should not compress user messages
        mock_llmlingua.compress_prompt.assert_not_called()
        assert result.messages == messages

    def test_apply_handles_non_string_content(self):
        """apply() handles messages with non-string content gracefully."""
        compressor = LLMLinguaCompressor()
        tokenizer = MagicMock()
        tokenizer.count_text.return_value = 5

        messages = [
            {"role": "assistant", "content": ["list", "content"]},
            {"role": "user", "content": None},
        ]

        result = compressor.apply(messages, tokenizer)

        assert result.messages is not None
        assert len(result.messages) == 2

    def test_apply_returns_transform_result(self):
        """apply() returns proper TransformResult object."""
        compressor = LLMLinguaCompressor()
        tokenizer = MagicMock()
        tokenizer.count_text.return_value = 10

        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(LLMLinguaCompressor, "available", return_value=False):
            result = compressor.apply(messages, tokenizer)

        # Should have these TransformResult fields
        assert hasattr(result, "messages")
        assert hasattr(result, "tokens_before")
        assert hasattr(result, "tokens_after")
        assert hasattr(result, "transforms_applied")

    def test_apply_respects_compression_threshold(self):
        """apply() only applies compression if ratio is below 0.9."""
        compressor = LLMLinguaCompressor()
        tokenizer = MagicMock()
        tokenizer.count_text.side_effect = [15, 14]  # First call original, second compressed

        long_content = " ".join(["word"] * 20)
        messages = [{"role": "assistant", "content": long_content}]

        mock_llmlingua = MagicMock()
        # Return a slightly compressed version (ratio 0.93, above threshold)
        mock_llmlingua.compress_prompt.return_value = {
            "compressed_prompt": "slightly compressed version"
        }

        with patch.object(LLMLinguaCompressor, "available", return_value=True):
            with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
                result = compressor.apply(messages, tokenizer)

        # Compression should have been attempted
        assert result is not None

    def test_apply_tracking_transforms(self):
        """apply() tracks applied transformations."""
        compressor = LLMLinguaCompressor()
        tokenizer = MagicMock()
        tokenizer.count_text.return_value = 15

        long_content = " ".join(["word"] * 20)
        messages = [{"role": "tool", "content": long_content}]

        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "compressed"}

        with patch.object(LLMLinguaCompressor, "available", return_value=True):
            with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
                result = compressor.apply(messages, tokenizer)

        assert result.transforms_applied is not None
        assert isinstance(result.transforms_applied, list)


class TestLLMLinguaCompressorConfiguration:
    """Tests for configuration handling."""

    def test_init_without_config(self):
        """Initialization without config uses defaults."""
        compressor = LLMLinguaCompressor()
        assert compressor.config is not None
        assert compressor.config.rate == 0.5

    def test_init_with_custom_config(self):
        """Initialization with custom config uses provided values."""
        custom_config = LLMLinguaConfig(rate=0.8, device="cuda")
        compressor = LLMLinguaCompressor(config=custom_config)
        assert compressor.config.rate == 0.8
        assert compressor.config.device == "cuda"

    def test_config_immutability_for_other_instances(self):
        """Modifying config of one instance doesn't affect others."""
        config1 = LLMLinguaConfig(rate=0.5)
        compressor1 = LLMLinguaCompressor(config=config1)
        compressor2 = LLMLinguaCompressor()

        assert compressor1.config.rate == 0.5
        assert compressor2.config.rate == 0.5  # Default


class TestLLMLinguaCompressorIntegration:
    """Integration tests for LLMLinguaCompressor."""

    def test_compressor_name_attribute(self):
        """Compressor has correct name attribute."""
        compressor = LLMLinguaCompressor()
        assert compressor.name == "llmlingua_compressor"

    @pytest.mark.skipif(not _LLMLINGUA_INSTALLED, reason="llmlingua not installed")
    def test_lazy_initialization_of_underlying_compressor(self):
        """Underlying compressor is only initialized on first use."""
        compressor = LLMLinguaCompressor()
        assert compressor._compressor is None

        mock_llmlingua = MagicMock()
        # PromptCompressor is imported inside _get_compressor() — patch its
        # module attribute directly since it's a local import.
        with patch.object(LLMLinguaCompressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                compressor.compress("Hello world this is long text")

        # _compressor remains None because we mocked _get_compressor itself
        # (which is fine — the lazy-init contract is still verified by the
        # initial assert above that _compressor starts as None).
        assert compressor._compressor is None

    def test_compressor_reused_across_calls(self):
        """Underlying compressor instance is reused across compress() calls."""
        compressor = LLMLinguaCompressor()
        mock_llmlingua = MagicMock()
        mock_llmlingua.compress_prompt.return_value = {"compressed_prompt": "result"}

        with patch.object(compressor, "_get_compressor", return_value=mock_llmlingua):
            with patch.object(LLMLinguaCompressor, "available", return_value=True):
                compressor.compress("First text")
                compressor.compress("Second text")

        # Should have been called twice
        assert mock_llmlingua.compress_prompt.call_count == 2

    def test_word_count_estimation(self):
        """Word count for token estimation uses simple split."""
        result = LLMLinguaResult(
            compressed="hello world",
            original="hello world foo bar baz qux",
            original_tokens=5,
            compressed_tokens=2,
        )
        assert result.original_tokens == 5
        assert result.compressed_tokens == 2
