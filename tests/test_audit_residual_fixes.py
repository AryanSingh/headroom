"""Regressions for the two residuals left by earlier audit-fix agents.

1. ``cutctx/transforms/content_router.py:token_len`` had its own local
   ``_bpe_encoder`` and never applied ``iter_bpe_safe_chunks``, so a
   whitespace-free message cost ~2.9 s per 100 KB (H16 quadratic BPE).
2. ``cutctx/transforms/code_compressor.py`` emitted a CCR handle that no
   marker pattern in ``cutctx/ccr/markers.py`` could match (C2 hash drift).
"""

from __future__ import annotations

import time

import pytest

from cutctx.ccr.markers import (
    CCR_HASH_LENGTH,
    GENERIC_COMPRESSED_HASH_RE,
    MARKER_PATTERNS,
)
from cutctx.transforms.content_router import token_len


# --------------------------------------------------------------------------
# Residual 1 — BPE guard in content_router.token_len
# --------------------------------------------------------------------------


def test_token_len_uses_bpe_guard_for_pathological_run(monkeypatch):
    """A whitespace-free block must be sliced before it reaches the encoder."""
    from cutctx.transforms import content_router

    enc = content_router._bpe_encoder()
    if enc is None:
        pytest.skip("tiktoken unavailable")

    seen: list[int] = []
    real_encode = enc.encode

    def spy_encode(text, *args, **kwargs):
        seen.append(len(text))
        return real_encode(text, *args, **kwargs)

    monkeypatch.setattr(enc, "encode", spy_encode)

    # 40 KB with no whitespace at all — one giant pre-token before the fix.
    payload = "A" * 40_000
    token_len(payload)

    assert seen, "encoder was never called"
    # Before the fix this was a single 40 000-char call.
    assert max(seen) <= 1024, f"encoder saw a {max(seen)}-char run; BPE guard not applied"


def test_token_len_pathological_input_is_fast():
    """Wall-clock guard: 100 KB whitespace-free used to cost ~2.9 s."""
    from cutctx.transforms import content_router

    if content_router._bpe_encoder() is None:
        pytest.skip("tiktoken unavailable")

    payload = "A" * 100_000
    content_router._TOKEN_LEN_MEMO.clear()
    start = time.perf_counter()
    count = token_len(payload)
    elapsed = time.perf_counter() - start

    assert count > 0
    assert elapsed < 1.0, f"token_len took {elapsed:.2f}s on 100 KB — BPE guard not applied"


def test_token_len_still_correct_for_ordinary_text():
    """The guard must not change counts for text without a long run."""
    from cutctx.transforms import content_router

    enc = content_router._bpe_encoder()
    if enc is None:
        pytest.skip("tiktoken unavailable")

    text = "def hello(name):\n    return f'hi {name}'\n" * 20
    content_router._TOKEN_LEN_MEMO.clear()
    assert token_len(text) == len(enc.encode(text))


# --------------------------------------------------------------------------
# Residual 2 — CCR marker emitted by code_compressor must be parseable
# --------------------------------------------------------------------------


CCR_CODE_SAMPLE = (
    '''"""Module docstring that is long enough to be worth compressing."""


'''
    + "\n\n".join(
        f'''def function_number_{index}(alpha, beta, gamma):
    """Docstring for function {index} with enough prose to matter."""
    accumulator = 0
    for step in range(alpha):
        accumulator += step * beta
        if accumulator > gamma:
            accumulator -= gamma
    result = {{"index": {index}, "value": accumulator}}
    return result
'''
        for index in range(30)
    )
)


def _emit_real_marker(monkeypatch, cache_key: str) -> str:
    """Run the real CodeCompressor and return its emitted output.

    Stubs only the CCR store call so the test does not depend on a live
    compression store — everything else is production code, including the
    marker f-string under test.
    """
    from cutctx.transforms.code_compressor import CodeAwareCompressor, CodeCompressorConfig

    compressor = CodeAwareCompressor(CodeCompressorConfig(enable_ccr=True))
    monkeypatch.setattr(
        CodeAwareCompressor, "_store_in_ccr", lambda self, *a, **k: cache_key, raising=True
    )
    result = compressor.compress(CCR_CODE_SAMPLE, language="python")
    return result.compressed


def test_code_compressor_emits_a_parseable_ccr_marker(monkeypatch):
    """The real emitted handle must match a shared marker pattern."""
    cache_key = "a1b2c3d4e5f60718"  # 16 hex — the compression_store default
    output = _emit_real_marker(monkeypatch, cache_key)

    assert "hash=" in output, f"compressor emitted no CCR handle: {output[-300:]!r}"
    assert any(pattern.search(output) for pattern in MARKER_PATTERNS), (
        f"no shared CCR pattern matches the emitted marker: {output[-300:]!r}"
    )
    match = GENERIC_COMPRESSED_HASH_RE.search(output)
    assert match is not None
    assert match.group(1) == cache_key


def test_code_compressor_truncates_long_hash_to_shared_length(monkeypatch):
    """A 64-char sha256 must be truncated with the shared constant."""
    cache_key = "0123456789abcdef" * 4  # 64 hex chars
    output = _emit_real_marker(monkeypatch, cache_key)

    match = GENERIC_COMPRESSED_HASH_RE.search(output)
    assert match is not None, f"long hash produced an unmatchable marker: {output[-300:]!r}"
    assert len(match.group(1)) == CCR_HASH_LENGTH


def test_old_marker_ordering_was_unmatchable():
    """Pins the root cause: ``hash=`` mid-string could never match.

    This is the shape the code emitted before the fix; it documents why the
    ordering in the f-string is load-bearing.
    """
    broken = (
        "\n# [120 tokens compressed. 3 functions."
        " Retrieve more: hash=a1b2c3d4e5f60718."
        " Expires in 60m.]"
    )
    assert not any(pattern.search(broken) for pattern in MARKER_PATTERNS)
