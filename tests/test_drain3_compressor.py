"""Tests for the Drain3 ML log template mining compressor.

All 12 tests from the spec. Tests that require ``drain3`` are guarded
with ``@pytest.mark.skipif(not drain3_available(), ...)`` so the suite
passes whether or not the optional dependency is installed.
"""

from __future__ import annotations

import pytest

from cutctx.transforms.drain3_compressor import (
    Drain3CompressionResult,
    Drain3CompressorConfig,
    Drain3LogCompressor,
    drain3_available,
)

# =========================================================================
# Test 1: drain3_available() returns bool without crashing
# =========================================================================


class TestDrain3Available:
    """Verify the availability probe behaves correctly."""

    def test_returns_bool(self) -> None:
        """drain3_available() must return a bool."""
        result = drain3_available()
        assert isinstance(result, bool)

    def test_no_crash(self) -> None:
        """drain3_available() must never raise."""
        for _ in range(5):
            drain3_available()  # Should not raise


# =========================================================================
# Test 2: Drain3CompressionResult has all expected fields + properties
# =========================================================================


class TestDrain3CompressionResult:
    """Verify the result dataclass shape."""

    def test_fields_exist(self) -> None:
        """All required fields must be present with correct defaults."""
        result = Drain3CompressionResult(
            compressed="foo",
            original="bar\nbaz\nqux",
            original_line_count=3,
            compressed_line_count=1,
        )
        assert result.compressed == "foo"
        assert result.original == "bar\nbaz\nqux"
        assert result.original_line_count == 3
        assert result.compressed_line_count == 1
        assert result.clusters_found == 0  # default
        assert result.compression_ratio == 1.0  # default
        assert result.drain3_used is False  # default
        assert result.stats == {}  # default

    def test_tokens_saved_estimate(self) -> None:
        """tokens_saved_estimate should be (original - compressed) // 4."""
        original = "a much longer original string here for testing"
        compressed = "short"
        result = Drain3CompressionResult(
            compressed=compressed,
            original=original,
            original_line_count=1,
            compressed_line_count=1,
        )
        expected = (len(original) - len(compressed)) // 4
        assert result.tokens_saved_estimate == expected

    def test_tokens_saved_estimate_zero_when_compressed_larger(self) -> None:
        """When compressed is longer than original, estimate must be 0."""
        result = Drain3CompressionResult(
            compressed="this is a much longer compressed output than original",
            original="short",
            original_line_count=1,
            compressed_line_count=1,
        )
        assert result.tokens_saved_estimate == 0

    def test_lines_omitted(self) -> None:
        """lines_omitted = original_line_count - compressed_line_count."""
        result = Drain3CompressionResult(
            compressed="foo",
            original="a\nb\nc\nd\ne",
            original_line_count=5,
            compressed_line_count=2,
        )
        assert result.lines_omitted == 3


# =========================================================================
# Test 3: Drain3CompressorConfig has correct defaults
# =========================================================================


class TestDrain3CompressorConfig:
    """Verify configuration defaults and overrides."""

    def test_defaults(self) -> None:
        config = Drain3CompressorConfig()
        assert config.max_clusters == 1000
        assert config.sim_threshold == 0.4
        assert config.depth == 4
        assert config.max_children == 100
        assert config.fallback_on_error is True

    def test_custom_values(self) -> None:
        config = Drain3CompressorConfig(
            max_clusters=500,
            sim_threshold=0.3,
            depth=3,
            max_children=50,
            fallback_on_error=False,
        )
        assert config.max_clusters == 500
        assert config.sim_threshold == 0.3
        assert config.depth == 3
        assert config.max_children == 50
        assert config.fallback_on_error is False


# =========================================================================
# Test 4: Drain3LogCompressor initializes without error
# =========================================================================


class TestDrain3LogCompressorInit:
    """Compressor initialization must never raise."""

    def test_init_default(self) -> None:
        compressor = Drain3LogCompressor()
        assert compressor.config is not None

    def test_init_with_config(self) -> None:
        config = Drain3CompressorConfig(max_clusters=50)
        compressor = Drain3LogCompressor(config=config)
        assert compressor.config.max_clusters == 50

    def test_init_with_none(self) -> None:
        compressor = Drain3LogCompressor(config=None)
        assert compressor.config is not None


# =========================================================================
# Test 5: compress() returns Drain3CompressionResult even when drain3 absent
# =========================================================================


class TestCompressReturnsResult:
    """compress() must always return a Drain3CompressionResult, never crash."""

    def test_returns_result_type(self) -> None:
        compressor = Drain3LogCompressor()
        result = compressor.compress("hello\nworld")
        assert isinstance(result, Drain3CompressionResult)
        assert result.compressed is not None

    def test_empty_content(self) -> None:
        compressor = Drain3LogCompressor()
        result = compressor.compress("")
        assert isinstance(result, Drain3CompressionResult)

    def test_single_line(self) -> None:
        compressor = Drain3LogCompressor()
        result = compressor.compress("just one line")
        assert isinstance(result, Drain3CompressionResult)


# =========================================================================
# Test 6: compress() with repetitive lines produces fewer output lines
# =========================================================================


class TestCompressRepetitive:
    """Repetitive log lines should be deduplicated into clusters."""

    @pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
    def test_repetitive_lines_deduped(self) -> None:
        """Identical lines should cluster into a single output line + summary."""
        content = "\n".join(["INFO: processing item 1"] * 5)
        compressor = Drain3LogCompressor()
        result = compressor.compress(content)
        # Even without drain3, the LogCompressor fallback keeps lines; with drain3,
        # all identical lines cluster to 1 rep + 1 summary = 2 lines.
        # For the test to be meaningful, we accept either behavior.
        # With drain3: compressed_line_count == 2 (1 rep + 1 summary)
        assert result.original_line_count == 5
        # drain3 clusters identical lines → expect fewer output lines
        if drain3_available():
            assert result.compressed_line_count == 2  # 1 rep + 1 "[N more]"
            assert result.clusters_found == 1
            assert "[4 more similar lines omitted" in result.compressed


# =========================================================================
# Test 7: compress() with unique lines preserves them
# =========================================================================


class TestCompressUnique:
    """Unique log lines may still be reduced but representative ones survive."""

    @pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
    def test_unique_lines_preserved(self) -> None:
        content = "\n".join(
            [
                "ERROR: connection timeout on host alpha",
                "INFO: task completed successfully",
                "WARN: disk space low on /dev/sda1",
            ]
        )
        compressor = Drain3LogCompressor()
        result = compressor.compress(content)
        # With drain3, all 3 are different templates → 3 clusters expected
        assert result.clusters_found == 3
        # Each line is unique, so no "[N more]" lines
        assert "[ more similar lines omitted" not in result.compressed
        assert "[0 more similar lines omitted" not in result.compressed


# =========================================================================
# Test 8: tokens_saved_estimate works on a real compression result
# =========================================================================


class TestTokensSavedEstimate:
    """tokens_saved_estimate on real output."""

    def test_non_negative(self) -> None:
        compressor = Drain3LogCompressor()
        content = "\n".join(["WARN: something happened"] * 10)
        result = compressor.compress(content)
        assert result.tokens_saved_estimate >= 0

    @pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
    def test_saves_tokens_on_repetitive(self) -> None:
        content = "\n".join(
            ["2024-01-01 10:00:00 INFO: Request processed in 42ms"] * 20
        )
        compressor = Drain3LogCompressor()
        result = compressor.compress(content)
        assert result.tokens_saved_estimate > 0
        # With drain3 we should have fewer lines
        assert result.compressed_line_count < result.original_line_count


# =========================================================================
# Test 9: lines_omitted reports correct count
# =========================================================================


class TestLinesOmitted:
    """lines_omitted should reflect actual line reduction."""

    def test_omitted_count(self) -> None:
        compressor = Drain3LogCompressor()
        content = "\n".join(["test line"] * 10)
        result = compressor.compress(content)
        assert result.lines_omitted == result.original_line_count - result.compressed_line_count
        assert result.lines_omitted >= 0

    @pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
    def test_omitted_on_repetitive(self) -> None:
        content = "\n".join(["WARN: retrying connection"] * 15)
        compressor = Drain3LogCompressor()
        result = compressor.compress(content)
        assert result.lines_omitted > 0
        assert result.lines_omitted == 13  # 15 lines → 1 rep + 1 summary = 2 lines


# =========================================================================
# Test 10: drain3_used flag correctly indicates if drain3 was active
# =========================================================================


class TestDrain3UsedFlag:
    """drain3_used must reflect whether drain3 did the work."""

    def test_drain3_used_false_when_not_available(self) -> None:
        if not drain3_available():
            compressor = Drain3LogCompressor()
            result = compressor.compress("some log content")
            assert result.drain3_used is False
        else:
            pytest.skip("drain3 IS installed — can't test the unavailable path")

    @pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
    def test_drain3_used_true_when_available(self) -> None:
        compressor = Drain3LogCompressor()
        result = compressor.compress("just a line")
        assert result.drain3_used is True


# =========================================================================
# Test 11: fallback_on_error catches exceptions gracefully
# =========================================================================


class TestFallbackOnError:
    """When drain3 errors mid-compression, fallback should kick in."""

    @pytest.mark.skipif(not drain3_available(), reason="drain3 not installed")
    def test_fallback_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        compressor = Drain3LogCompressor()
        content = "line1\nline2\nline3"

        # Monkey-patch _drain3_compress to raise
        def _broken(*args: object, **kwargs: object) -> object:
            raise RuntimeError("simulated drain3 failure")

        monkeypatch.setattr(compressor, "_drain3_compress", _broken)
        result = compressor.compress(content)
        assert isinstance(result, Drain3CompressionResult)
        assert result.drain3_used is False  # fallback, not drain3

    def test_no_crash_without_drain3_and_broken_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even if both drain3 and fallback fail, compress returns a valid result."""
        # Force drain3_available to return False
        monkeypatch.setattr("cutctx.transforms.drain3_compressor.drain3_available", lambda: False)

        compressor = Drain3LogCompressor()

        # Make _get_fallback return None (no LogCompressor available)
        monkeypatch.setattr(compressor, "_get_fallback", lambda: None)
        # drain3 is already unavailable in this environment
        content = "surviving line"
        result = compressor.compress(content)
        assert isinstance(result, Drain3CompressionResult)
        # Should return content unchanged
        assert result.compressed == content
        assert result.drain3_used is False


# =========================================================================
# Test 12: Thread safety — concurrent calls do not corrupt state
# =========================================================================


class TestThreadSafety:
    """Concurrent compress calls must not deadlock or produce garbage."""

    def test_concurrent_calls_no_deadlock(self) -> None:
        """Call compress from multiple threads; must not deadlock."""
        import concurrent.futures

        compressor = Drain3LogCompressor()
        content = "\n".join(["test line"] * 20)

        def _call() -> Drain3CompressionResult:
            return compressor.compress(content)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(_call) for _ in range(20)]
            results: list[Drain3CompressionResult] = []
            for f in concurrent.futures.as_completed(futures, timeout=30):
                try:
                    results.append(f.result(timeout=5))
                except Exception as exc:
                    pytest.fail(f"Thread safety test failed with: {exc}")

        # All results must be valid
        for r in results:
            assert isinstance(r, Drain3CompressionResult)
            assert r.original_line_count == 20
            assert r.compressed_line_count <= 20

    def test_concurrent_calls_no_crash_empty_input(self) -> None:
        """Concurrent compress with empty input must not raise."""
        import concurrent.futures

        compressor = Drain3LogCompressor()

        def _call() -> Drain3CompressionResult:
            return compressor.compress("")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_call) for _ in range(10)]
            for f in concurrent.futures.as_completed(futures, timeout=15):
                r = f.result(timeout=5)
                assert isinstance(r, Drain3CompressionResult)
