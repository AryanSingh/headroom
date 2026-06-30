from __future__ import annotations

from unittest.mock import patch

import pytest

from cutctx.transforms.kompress_compressor import KompressCompressor


def test_compress_passthrough_when_input_exceeds_max_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUTCTX_KOMPRESS_MAX_WORDS", "10")
    compressor = KompressCompressor()
    long_text = " ".join(f"word{i}" for i in range(11))

    with patch(
        "cutctx.transforms.kompress_compressor._load_kompress",
        side_effect=AssertionError("model should not load for oversized input"),
    ):
        result = compressor.compress(long_text)

    assert result.compressed == long_text
    assert result.compression_ratio == 1.0
    assert result.original_tokens == 11
    assert result.compressed_tokens == 11


def test_compress_batch_passthrough_when_input_exceeds_max_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUTCTX_KOMPRESS_MAX_WORDS", "10")
    compressor = KompressCompressor()
    contents = [" ".join(f"word{i}" for i in range(11)), "hello world"]

    with patch(
        "cutctx.transforms.kompress_compressor._load_kompress",
        side_effect=AssertionError("model should not load for oversized batch input"),
    ):
        results = compressor.compress_batch(contents)

    assert [result.compressed for result in results] == contents
    assert all(result.compression_ratio == 1.0 for result in results)
