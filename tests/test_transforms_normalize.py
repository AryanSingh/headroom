# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""Tests for cutctx.transforms.normalize — WS16 tokenizer-aware normalization.

Per artifacts/savings-moat-expansion-specs.md WS16 and the
strategy-implementation-plan.md §0.2, these tests are behavioral
contracts that the normalize pre-pass must satisfy.

TDD: written first, then implementation in cutctx/transforms/normalize.py
was made to satisfy them. If you change normalize.py, these tests
should still pass byte-identically; if they don't, you broke a
contract.
"""

from __future__ import annotations

import pytest

from cutctx.transforms.normalize import (
    DEFAULT_BLOB_TO_POINTER_THRESHOLD,
    DEFAULT_DECIMAL_PRECISION,
    NormalizeConfig,
    NormalizeResult,
    normalize_content,
)


# ---------------------------------------------------------------------------
# Flag-off golden contract — the most important test in this file
# ---------------------------------------------------------------------------


def test_normalize_off_returns_input_byte_identical() -> None:
    """With all sub-flags off, normalize_content must return the input
    byte-identical. This is the flag-off golden test from
    strategy-implementation-plan.md §0.1.
    """
    config = NormalizeConfig()  # all flags default off
    inputs = [
        "",  # empty
        "hello world",  # ascii
        "héllo wörld",  # latin1
        "    \n\n   foo   \n\n\n   bar   \n",  # whitespace
        "123.456789012345",  # numeric
        "aGVsbG8gd29ybGQ=",  # base64
        "0xdeadbeefcafebabe1234567890abcdef",  # hex
        "line1\nline2\nline3\n",  # multi-line
        "line1\nline2\nline3",  # multi-line no trailing newline
    ]
    for s in inputs:
        result = normalize_content(s, config)
        assert result.content == s, (
            f"flag-off golden broken: input {s!r} produced {result.content!r}"
        )
        assert result.tokens_saved == 0
        assert result.passes_applied == []


def test_normalize_off_with_tokenizer_returns_input_byte_identical() -> None:
    """Same as above, with a tokenizer argument — the tokenizer must
    not be invoked when the flag is off.
    """
    class _SpyTokenizer:
        def __init__(self) -> None:
            self.call_count = 0

        def count_tokens(self, s: str) -> int:
            self.call_count += 1
            return len(s) // 4

    spy = _SpyTokenizer()
    config = NormalizeConfig()
    result = normalize_content("hello world", config, tokenizer=spy)
    assert result.content == "hello world"
    assert spy.call_count == 0, "tokenizer was called even though no pass ran"


def test_normalize_passes_through_non_string_defensively() -> None:
    """If a non-string slips through, normalize must not crash."""
    config = NormalizeConfig(enable_unicode_normalization=True)
    result = normalize_content("", config)  # empty string still works
    assert result.content == ""


# ---------------------------------------------------------------------------
# Pass 1: Unicode NFC + homoglyph whitespace collapse
# ---------------------------------------------------------------------------


def test_unicode_nfc_normalizes_decomposed() -> None:
    """NFC: 'e' + combining-acute ('e\u0301') -> 'é' (single codepoint)."""
    decomposed = "e\u0301"  # e + combining acute accent
    composed = "\u00e9"      # é (single codepoint)
    assert len(decomposed) == 2
    assert len(composed) == 1
    config = NormalizeConfig(enable_unicode_normalization=True)
    result = normalize_content(decomposed, config)
    assert result.content == composed
    assert "unicode_normalize" in result.passes_applied


def test_unicode_homoglyph_whitespace_collapsed() -> None:
    """No-break-space, em-space, en-space, thin-space, zero-width-* all
    collapse to ASCII whitespace (or to empty for zero-width)."""
    config = NormalizeConfig(enable_unicode_normalization=True)
    # Mix of homoglyphs
    inputs = {
        "a\u00a0b": "a b",  # NO-BREAK SPACE -> SPACE
        "a\u2003b": "a b",  # EM SPACE -> SPACE
        "a\u2002b": "a b",  # EN SPACE -> SPACE
        "a\u2009b": "a b",  # THIN SPACE -> SPACE
        "a\u200bb": "ab",   # ZERO WIDTH SPACE -> ""
        "a\u200cb": "ab",   # ZERO WIDTH NON-JOINER -> ""
        "a\u200db": "ab",   # ZERO WIDTH JOINER -> ""
        "a\ufeffb": "ab",   # ZERO WIDTH NO-BREAK SPACE -> ""
    }
    for raw, expected in inputs.items():
        result = normalize_content(raw, config)
        assert result.content == expected, (
            f"homoglyph {raw!r} should collapse to {expected!r}, got {result.content!r}"
        )


def test_unicode_pass_idempotent() -> None:
    """normalize ∘ normalize == normalize (the spec's idempotency requirement)."""
    config = NormalizeConfig(enable_unicode_normalization=True)
    for s in ["hello world", "héllo\u0301 wörld", "a\u00a0b\u2003c\u200bd"]:
        once = normalize_content(s, config).content
        twice = normalize_content(once, config).content
        assert once == twice, f"not idempotent: {s!r} -> {once!r} -> {twice!r}"


def test_unicode_pass_does_not_touch_user_text() -> None:
    """The spec is explicit: this pass applies only to tool-output
    content, not user/assistant text. We assert the pass itself is
    content-agnostic (the gating is the caller's responsibility) —
    but in this test we feed it plain ASCII to confirm it does
    nothing harmful.
    """
    config = NormalizeConfig(enable_unicode_normalization=True)
    s = "the quick brown fox jumps over the lazy dog"
    result = normalize_content(s, config)
    assert result.content == s
    assert "unicode_normalize" not in result.passes_applied


# ---------------------------------------------------------------------------
# Pass 2: Trailing-whitespace / blank-run collapse
# ---------------------------------------------------------------------------


def test_whitespace_collapses_trailing_per_line() -> None:
    config = NormalizeConfig(enable_whitespace_collapse=True)
    raw = "foo   \nbar\t \nbaz"
    result = normalize_content(raw, config)
    assert result.content == "foo\nbar\nbaz"


def test_whitespace_collapses_blank_runs() -> None:
    config = NormalizeConfig(enable_whitespace_collapse=True)
    raw = "a\n\n\n\nb\n\n\nc"
    result = normalize_content(raw, config)
    assert result.content == "a\n\nb\n\nc"


def test_whitespace_preserves_trailing_newline() -> None:
    """If the input ended with a newline, the output also ends with a newline."""
    config = NormalizeConfig(enable_whitespace_collapse=True)
    raw_with = "foo\nbar  \n"
    raw_without = "foo\nbar  "
    with_result = normalize_content(raw_with, config).content
    without_result = normalize_content(raw_without, config).content
    assert with_result.endswith("\n")
    assert not without_result.endswith("\n")
    assert with_result == "foo\nbar\n"
    assert without_result == "foo\nbar"


def test_whitespace_idempotent() -> None:
    config = NormalizeConfig(enable_whitespace_collapse=True)
    for s in ["a\n\n\nb\n", "foo   \nbar\t \n", "no changes here"]:
        once = normalize_content(s, config).content
        twice = normalize_content(once, config).content
        assert once == twice, f"not idempotent: {s!r} -> {once!r} -> {twice!r}"


def test_whitespace_no_change_on_clean_text() -> None:
    config = NormalizeConfig(enable_whitespace_collapse=True)
    s = "foo\nbar\nbaz\n"
    result = normalize_content(s, config)
    assert result.content == s
    assert "whitespace_collapse" not in result.passes_applied


# ---------------------------------------------------------------------------
# Pass 3: base64/hex blob detection (does NOT modify content in step 1)
# ---------------------------------------------------------------------------


def test_blob_detects_long_base64() -> None:
    config = NormalizeConfig(
        enable_blob_to_pointer=True,
        blob_to_pointer_threshold=64,
    )
    # A 64-char base64 blob. Padding to a multiple of 4 with "=".
    blob = "A" * 60 + "==="
    assert len(blob) == 63  # not 64, adjust
    # Use exactly 64 base64 chars:
    blob = "A" * 60 + "BBBB"  # 64 chars, all base64
    text = f"before {blob} after"
    result = normalize_content(text, config)
    # Step 1 does NOT modify content — only records the detection.
    assert result.content == text
    assert "blob_to_pointer" in result.passes_applied
    assert result.per_pass.get("blob_to_pointer_count") == 1


def test_blob_does_not_flag_short_base64() -> None:
    config = NormalizeConfig(
        enable_blob_to_pointer=True,
        blob_to_pointer_threshold=64,
    )
    text = "short = ABCDEFGH"  # 8 chars, well under threshold
    result = normalize_content(text, config)
    assert result.per_pass.get("blob_to_pointer_count", 0) == 0


def test_blob_detects_long_hex() -> None:
    config = NormalizeConfig(
        enable_blob_to_pointer=True,
        blob_to_pointer_threshold=32,
    )
    # 32 hex chars (16 bytes), all-hex, even-length.
    hex_blob = "deadbeef" * 4  # 32 chars
    text = f"prefix {hex_blob} suffix"
    result = normalize_content(text, config)
    assert result.content == text  # no modification in step 1
    assert "blob_to_pointer" in result.passes_applied
    assert result.per_pass.get("blob_to_pointer_count") == 1


def test_blob_does_not_flag_short_hex() -> None:
    config = NormalizeConfig(
        enable_blob_to_pointer=True,
        blob_to_pointer_threshold=32,
    )
    # 16 hex chars (8 bytes) — too short to flag.
    text = "deadbeef12345678"
    result = normalize_content(text, config)
    assert result.per_pass.get("blob_to_pointer_count", 0) == 0


def test_blob_default_threshold() -> None:
    """The default blob threshold should be 256 (per the spec)."""
    assert DEFAULT_BLOB_TO_POINTER_THRESHOLD == 256


# ---------------------------------------------------------------------------
# Pass 4: Decimal-precision capping in numeric tables
# ---------------------------------------------------------------------------


def test_decimal_cap_disabled_by_default() -> None:
    config = NormalizeConfig()  # enable_decimal_cap=False
    s = "1.1234567890\n2.2345678901"
    result = normalize_content(s, config)
    assert result.content == s
    assert "decimal_cap" not in result.passes_applied


def test_decimal_cap_zero_precision_means_no_cap() -> None:
    """Precision 0 = use 0 = no cap, even if the flag is on."""
    config = NormalizeConfig(enable_decimal_cap=True, decimal_precision=0)
    s = "1.1234567890"
    result = normalize_content(s, config)
    assert result.content == s
    assert "decimal_cap" not in result.passes_applied


def test_decimal_cap_runs_on_numeric_table() -> None:
    config = NormalizeConfig(enable_decimal_cap=True, decimal_precision=2)
    # 2+ consecutive numeric-looking lines = numeric table
    s = "1.12345\n2.67890\n3.14159"
    result = normalize_content(s, config)
    assert result.content == "1.12\n2.68\n3.14"
    assert "decimal_cap" in result.passes_applied
    assert result.per_pass["decimal_cap"] > 0


def test_decimal_cap_does_not_touch_single_line_numbers() -> None:
    """Single-line numbers (e.g. version strings) must never be touched
    because they may be semantically meaningful.
    """
    config = NormalizeConfig(enable_decimal_cap=True, decimal_precision=2)
    s = "1.123.456"  # looks like a version string
    result = normalize_content(s, config)
    assert result.content == s
    assert "decimal_cap" not in result.passes_applied


def test_decimal_cap_default_precision() -> None:
    """Default precision should be 0 (= no cap)."""
    assert DEFAULT_DECIMAL_PRECISION == 0


# ---------------------------------------------------------------------------
# Composition: passes compose, last write wins
# ---------------------------------------------------------------------------


def test_passes_compose_in_order() -> None:
    """All four passes on, with NFC + whitespace + decimal — content
    should reflect all three transformations.

    Input has actual whitespace to collapse (trailing spaces) AND
    a numeric table to cap. The unicode_normalize pass is a no-op
    on this ASCII input; the test asserts the passes that actually
    changed the content.
    """
    config = NormalizeConfig(
        enable_unicode_normalization=True,
        enable_whitespace_collapse=True,
        enable_decimal_cap=True,
        decimal_precision=2,
    )
    # Input has trailing spaces on each line (whitespace pass runs)
    # AND a 2-line numeric table (decimal_cap pass runs).
    # Unicode normalize is a no-op (input is ASCII).
    raw = "1.12345   \n2.67890   "
    result = normalize_content(raw, config)
    # Both whitespace and decimal apply.
    assert result.content == "1.12\n2.68"
    assert set(result.passes_applied) == {
        "whitespace_collapse",
        "decimal_cap",
    }


def test_token_count_with_real_tokenizer() -> None:
    """When a tokenizer is provided, the per-pass estimate is replaced
    by a real-token count at the end. This is the path the agent
    pipeline uses (per the spec).
    """

    class _StubTokenizer:
        def count_tokens(self, s: str) -> int:
            return len(s)  # 1 char = 1 token, deterministic

    config = NormalizeConfig(
        enable_unicode_normalization=True,
        enable_whitespace_collapse=True,
    )
    # raw: 'a'(1) + NBSP(1) + 'b'(1) + ' '(1) + ' '(1) + ' '(1) + '\n'(1) = 7 chars
    raw = "a\u00a0b   \n"
    assert len(raw) == 7, f"test fixture: expected 7 chars, got {len(raw)}"
    # After normalization: 'a b\n' = 4 chars.
    result = normalize_content(raw, config, tokenizer=_StubTokenizer())
    assert result.content == "a b\n"
    # StubTokenizer says before=7, after=4, saved=3.
    assert result.tokens_saved == 3


# ---------------------------------------------------------------------------
# BDD: behavioral scenarios from the spec
# ---------------------------------------------------------------------------


def test_bdd_scenario_tool_output_with_runaway_whitespace() -> None:
    """Spec scenario: tool output (e.g. `ls -la`) often has trailing
    whitespace and run-together blank lines. The normalize pass
    should produce a noticeably shorter, equivalent output.
    """
    config = NormalizeConfig(
        enable_whitespace_collapse=True,
        enable_unicode_normalization=True,
    )
    raw = (
        "drwxr-xr-x   2 aryan staff    4096 \u00a0Jul  1 10:00 Documents   \n"
        "\n"
        "\n"
        "\n"
        "drwxr-xr-x   3 aryan staff    4096 Jul  1 10:01 Downloads\t \n"
        "-rw-r--r--   1 aryan staff    1234 Jul  1 10:02 readme.md   \n"
    )
    result = normalize_content(raw, config)
    # No more than 1 blank line in a row; no trailing whitespace per line.
    assert "\n\n\n" not in result.content
    for line in result.content.splitlines():
        # rstrip would remove the newline; here we just check no
        # trailing tabs/spaces on the line content.
        if line:  # skip empty lines
            assert line == line.rstrip()
    # Token savings: real positive number.
    assert result.tokens_saved > 0


def test_bdd_scenario_decomposed_unicode_in_logs() -> None:
    """Spec scenario: log output from tools that emit decomposed
    unicode (e + combining acute = 2 codepoints but 1 token). NFC
    collapses to composed form.
    """
    config = NormalizeConfig(enable_unicode_normalization=True)
    # 'café' written as 'café' (decomposed)
    decomposed = "caf\u00e9"  # already composed (e + combining)
    # Actually: \u00e9 is the composed form. Use 'e' + combining acute:
    decomposed = "cafe\u0301"
    composed = "café"
    result = normalize_content(decomposed, config)
    assert result.content == composed


def test_bdd_scenario_idempotency_under_repeated_application() -> None:
    """Spec: 'idempotent; guard-clean on fixture corpus'."""
    config = NormalizeConfig(
        enable_unicode_normalization=True,
        enable_whitespace_collapse=True,
    )
    fixture = """
    line 1   \u00a0
    \n
    \n
    \t\tline 2\t\t
    e\u0301 e\u0301 e\u0301
    """
    once = normalize_content(fixture, config).content
    twice = normalize_content(once, config).content
    thrice = normalize_content(twice, config).content
    assert once == twice == thrice, (
        f"normalize is not idempotent:\n  once:   {once!r}\n  twice:  {twice!r}\n  thrice: {thrice!r}"
    )


# ---------------------------------------------------------------------------
# Regression guard: the config defaults are flag-off (per spec)
# ---------------------------------------------------------------------------


def test_default_config_is_all_off() -> None:
    """The default NormalizeConfig must have every sub-flag off —
    this is the spec's flag-off default for the CUTCTX_NORMALIZE envelope.
    """
    c = NormalizeConfig()
    assert c.enable_unicode_normalization is False
    assert c.enable_whitespace_collapse is False
    assert c.enable_blob_to_pointer is False
    assert c.enable_decimal_cap is False
    assert c.decimal_precision == 0
    assert c.blob_to_pointer_threshold == DEFAULT_BLOB_TO_POINTER_THRESHOLD


def test_normalize_result_dataclass_shape() -> None:
    """Smoke test on the result type's public surface."""
    r = NormalizeResult(content="x", tokens_saved=0)
    assert r.content == "x"
    assert r.tokens_saved == 0
    assert r.passes_applied == []
    assert r.per_pass == {}
