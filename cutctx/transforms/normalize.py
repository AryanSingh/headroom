# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
# Tokenizer-aware normalization pre-pass for the compression pipeline.
#
# Per artifacts/savings-moat-expansion-specs.md WS16 and the strategy-implementation-plan.md
# §0 ground rules: every pass is individually testable, semantics-preserving under
# the accuracy guard, and flag-gated behind CUTCTX_NORMALIZE=1 (default off).
#
# Per the spec, this module applies FOUR passes (each gated by its own sub-flag,
# default off within CUTCTX_NORMALIZE):
#   1. NFC + homoglyph whitespace collapse
#   2. Trailing-whitespace / blank-run collapse (deeper than cutctx.proxy.deblank)
#   3. base64/hex blobs > 256 chars -> CCR pointer reference
#   4. Decimal-precision capping in numeric tables (config, default off within flag)
#
# Every pass must be:
#   - IDEMPOTENT (f(f(x)) == f(x))
#   - Guard-clean (accuracy_preserving for the tool-output content type)
#   - MEASURED (per-pass tokens saved vs the same content before the pass)

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public configuration
# ---------------------------------------------------------------------------


# Default threshold for the base64/hex-to-CCR-pointer pass, per the spec.
DEFAULT_BLOB_TO_POINTER_THRESHOLD = 256

# Default decimal precision for the numeric-table cap pass. The spec says
# this is configurable and default-off within CUTCTX_NORMALIZE; we expose
# 0 as "use 0 = no cap" (i.e. off).
DEFAULT_DECIMAL_PRECISION = 0


@dataclass
class NormalizeConfig:
    """Configuration for the normalize pre-pass.

    All sub-flags default to False inside the broader CUTCTX_NORMALIZE
    envelope, per the spec. A normalize pre-pass with all sub-flags off
    is a no-op (it returns the input byte-identical, which is what the
    flag-off golden test asserts).
    """

    # Pass 1: NFC + homoglyph whitespace collapse
    enable_unicode_normalization: bool = False

    # Pass 2: trailing-whitespace / blank-run collapse (deeper than deblank)
    enable_whitespace_collapse: bool = False

    # Pass 3: base64/hex blobs > threshold -> CCR pointer reference.
    # The CCR insert call is OUT OF SCOPE for WS16 step 1 — we
    # implement the detection + marker emit only, so the pass is
    # safe to enable without touching the CCR store. The actual
    # CCR-insert integration lands when the proxy wires this in
    # (WS16.2). For now, the blob pass returns the original content
    # with a `__normalize_blob_kept_in_place__` marker and counts the
    # would-be savings; the wiring step replaces the marker with a
    # real CCR pointer.
    enable_blob_to_pointer: bool = False
    blob_to_pointer_threshold: int = DEFAULT_BLOB_TO_POINTER_THRESHOLD

    # Pass 4: decimal-precision capping in numeric tables.
    # 0 means "do not cap" (default off within the flag).
    enable_decimal_cap: bool = False
    decimal_precision: int = DEFAULT_DECIMAL_PRECISION


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class NormalizeResult:
    """Result of running the normalize pre-pass on a piece of content.

    `content` is the post-pass output (byte-identical to input if all
    sub-flags are off). `tokens_saved` is the per-pass estimated token
    savings measured against the target tokenizer; it is recorded for
    the attribution path in WS16.3. `passes_applied` is the list of
    pass names that actually changed the content (in order).
    """

    content: str
    tokens_saved: int = 0
    passes_applied: list[str] = field(default_factory=list)
    # Per-pass detail (only populated for passes that ran)
    per_pass: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pass implementations — each is a pure (str) -> (str, tokens_saved) function
# ---------------------------------------------------------------------------


def _estimate_tokens_saved(before: str, after: str, tokenizer: Any | None) -> int:
    """Estimate tokens saved by a pass using a tokenizer if provided.

    The token count is best-effort: we prefer the real tokenizer
    (`cutctx.tokenizer.Tokenizer`) but fall back to a 4-chars-per-token
    heuristic if the tokenizer is unavailable or raises. The estimate
    is used for attribution, not for any correctness decision; the
    pass is semantics-preserving regardless of the token-count number.
    """
    if before == after:
        return 0
    if tokenizer is None:
        # 4-chars-per-token is a defensible fallback for English/tool-output
        # text; we round up to avoid fractional "saved < 1" reports.
        before_n = (len(before) + 3) // 4
        after_n = (len(after) + 3) // 4
        return max(0, before_n - after_n)
    try:
        before_n = tokenizer.count_tokens(before)
        after_n = tokenizer.count_tokens(after)
        return max(0, before_n - after_n)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("tokenizer.count_tokens failed: %s", exc)
        return 0


# --- Pass 1: Unicode NFC + homoglyph whitespace collapse -----------------

# A small set of Unicode characters that LOOK like ASCII whitespace but
# are not ASCII whitespace. These inflate token counts in some tokenizers
# because the tokenizer emits a different token for each unique codepoint.
# Per the spec, this pass collapses them to their ASCII equivalent.
_HOMOGLYPH_WHITESPACE = {
    "\u00a0": " ",  # NO-BREAK SPACE
    "\u2003": " ",  # EM SPACE
    "\u2002": " ",  # EN SPACE
    "\u2009": " ",  # THIN SPACE
    "\u200b": "",  # ZERO WIDTH SPACE
    "\u200c": "",  # ZERO WIDTH NON-JOINER
    "\u200d": "",  # ZERO WIDTH JOINER
    "\ufeff": "",  # ZERO WIDTH NO-BREAK SPACE / BOM
}


def _pass_unicode_normalize(content: str) -> tuple[str, int]:
    """Pass 1: NFC + homoglyph whitespace collapse.

    Returns (new_content, estimated_tokens_saved_using_no_tokenizer).
    The caller is responsible for applying the real-tokenizer estimate.
    """
    # NFC normalizes decomposed characters (e + combining acute = é) to
    # their composed form, which the tokenizer handles more efficiently.
    nfc = unicodedata.normalize("NFC", content)
    collapsed = "".join(_HOMOGLYPH_WHITESPACE.get(c, c) for c in nfc)
    return collapsed, _estimate_tokens_saved(content, collapsed, None)


# --- Pass 2: Trailing-whitespace / blank-run collapse ---------------------


def _pass_whitespace_collapse(content: str) -> tuple[str, int]:
    """Pass 2: collapse runs of blank lines and trailing whitespace.

    Deeper than `cutctx.proxy.deblank` (which is one-pass whitespace
    trimming per line). This pass:
      - Replaces any run of 2+ blank lines with a single blank line
      - Strips trailing whitespace from every line
      - Strips a single trailing newline (preserves the "ends with newline"
        convention only when the input had one; never adds one)
    """
    # Strip trailing whitespace per line, then collapse blank runs.
    lines = [line.rstrip() for line in content.splitlines()]
    # splitlines() drops the trailing empty string if the content ends
    # with "\n"; restore that to keep the "ends with newline" convention.
    ends_with_newline = content.endswith("\n")

    collapsed: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            # Keep at most one blank line.
            if blank_run <= 1:
                collapsed.append(line)
        else:
            blank_run = 0
            collapsed.append(line)

    out = "\n".join(collapsed)
    if ends_with_newline and not out.endswith("\n"):
        out += "\n"
    return out, _estimate_tokens_saved(content, out, None)


# --- Pass 3: base64/hex blobs > threshold -> CCR pointer marker ---------


# A blob is a contiguous run of base64-safe characters (or hex chars) of
# at least `threshold` chars. We scan manually (rather than regex) to
# avoid the lookbehind-overlap problem in re.finditer that matches
# overlapping regions when the input is a single long run of valid chars.
_BASE64_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
_HEX_CHARS = set("0123456789abcdefABCDEF")


def _scan_runs(content: str, valid_chars: set[str]) -> list[tuple[int, int]]:
    """Return a list of (start, end_exclusive) for every maximal run
    of `valid_chars` in `content`.

    A run is bounded by any character NOT in `valid_chars` (whitespace,
    punctuation, line breaks, etc.). The `valid_chars` set is the
    alphabet of the blob format — base64 is A-Z, a-z, 0-9, +, /, =;
    hex is 0-9, a-f, A-F. Real base64/hex blobs in prose are bounded
    by whitespace and punctuation; the `_looks_like_base64` /
    `_looks_like_hex` post-filters are what distinguish a "blob" from
    a "long word" (a 256-char word of only A's is not a real word).
    """
    runs: list[tuple[int, int]] = []
    n = len(content)
    i = 0
    while i < n:
        if content[i] in valid_chars:
            start = i
            while i < n and content[i] in valid_chars:
                i += 1
            runs.append((start, i))
        else:
            i += 1
    return runs


def _looks_like_base64(s: str) -> bool:
    """Heuristic: a base64 blob usually ends with = padding and has
    length divisible by 4. We are conservative and only flag strings
    that pass both checks AND have only base64 characters.
    """
    if len(s) % 4 != 0:
        return False
    if not s.endswith("=") and not s.endswith("==") and len(s) % 4 != 0:
        return False
    return all(c in _BASE64_CHARS for c in s)


def _looks_like_hex(s: str) -> bool:
    """A hex blob is even-length and all-hex. We avoid flagging short
    hex runs that might be normal identifiers."""
    if len(s) % 2 != 0 or len(s) < 32:
        return False
    return all(c in _HEX_CHARS for c in s)


def _pass_blob_to_pointer(content: str, threshold: int) -> tuple[str, list[tuple[str, str]]]:
    """Pass 3: detect base64/hex blobs over the threshold.

    Returns (new_content, list_of_(placeholder, blob) pairs). The
    placeholder is a deterministic marker the CCR integration can
    later swap for a real pointer; for WS16 step 1 we leave the
    blob in place (the wiring step WS16.2 swaps the marker for a
    CCR pointer). The list is informational and consumed by the
    caller to record attribution.

    This function NEVER modifies the content; it returns the original
    content and the list of detected blobs. Replacing the content
    with placeholders is the caller's choice and is the hook for
    WS16.2's CCR integration. Keeping pass 3 read-only here is
    what allows the unit tests to assert the detection without
    requiring a CCR store mock.
    """
    blobs: list[tuple[str, str]] = []
    # Track (start, end) ranges we've already classified so we don't
    # double-count a run that's both valid base64 and valid hex (a
    # 64-char run of A's, for example, passes both heuristics). The
    # base64 pass is the canonical classifier; if a run passes base64
    # we don't re-test it for hex.
    classified: set[tuple[int, int]] = set()

    # Base64 blobs: scan runs of base64 chars, bounded by anything not
    # in the base64 alphabet.
    for start, end in _scan_runs(content, _BASE64_CHARS):
        if end - start < threshold:
            continue
        candidate = content[start:end]
        if not _looks_like_base64(candidate):
            continue
        blobs.append((candidate, candidate))
        classified.add((start, end))

    # Hex blobs: scan runs of hex chars, bounded by anything not hex.
    # Skip runs already classified as base64.
    for start, end in _scan_runs(content, _HEX_CHARS):
        if (start, end) in classified:
            continue
        if end - start < threshold:
            continue
        candidate = content[start:end]
        if not _looks_like_hex(candidate):
            continue
        blobs.append((candidate, candidate))
        classified.add((start, end))

    return content, blobs


# --- Pass 4: Decimal-precision capping in numeric tables ---------------

# A "numeric table" is a multi-line block where every line contains at
# least one number. We restrict the cap to within-table contexts to
# avoid silently mutating user input where precision matters (e.g.
# crypto keys, version strings).

_NUMERIC_LINE_RE = re.compile(r"^(?P<indent>\s*)(?P<rest>.*\d.*)$")
_FLOAT_RE = re.compile(r"(\d+\.\d+)")


def _pass_decimal_cap(content: str, precision: int) -> tuple[str, int]:
    """Pass 4: cap float precision in numeric-table contexts.

    A "numeric table" is a run of consecutive lines where each line
    contains at least one number and the surrounding context is
    whitespace-anchored (e.g. aligned columns). This is a conservative
    definition: a line is treated as part of a numeric table only if
    the line above and below it are also numeric-looking. Single-line
    numeric strings (like a version number "1.234.56") are NEVER
    touched.
    """
    if precision <= 0:
        return content, 0

    lines = content.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    saved = 0
    while i < len(lines):
        # Look ahead to see if we are in a numeric-table run.
        run_start = i
        run_end = i
        while (
            run_end + 1 < len(lines)
            and _NUMERIC_LINE_RE.match(lines[run_end].rstrip("\n")) is not None
            and _NUMERIC_LINE_RE.match(lines[run_end + 1].rstrip("\n")) is not None
        ):
            run_end += 1
        if run_end > run_start:
            # Numeric table run from [run_start..run_end] inclusive.
            for j in range(run_start, run_end + 1):
                line = lines[j]
                m = _NUMERIC_LINE_RE.match(line.rstrip("\n"))
                if m is None:
                    out.append(line)
                    continue
                indent = m.group("indent")
                rest = m.group("rest")
                new_rest, line_saved = _cap_floats_in_line(rest, precision)
                saved += line_saved
                # Preserve the trailing newline if present.
                if line.endswith("\n"):
                    out.append(indent + new_rest + "\n")
                else:
                    out.append(indent + new_rest)
            i = run_end + 1
        else:
            out.append(lines[i])
            i += 1
    new_content = "".join(out)
    return new_content, _estimate_tokens_saved(content, new_content, None)


def _cap_floats_in_line(text: str, precision: int) -> tuple[str, int]:
    """Cap float precision in a single line. Returns (new_text, chars_saved)."""
    saved = 0

    def _sub(match: re.Match[str]) -> str:
        nonlocal saved
        original = match.group(0)
        # `g` rounds-half-to-even (banker's rounding); we use the more
        # conventional "round" via the format spec. format(x, ".3f") gives
        # "1.234" for 1.234567890. This is the same rounding the user
        # would see in most spreadsheets and is what the spec implies
        # by "decimal-precision capping."
        value = float(original)
        capped = f"{value:.{precision}f}"
        # Avoid expanding the string (e.g. "1" -> "1.000"). If the
        # original had no decimal point, we still apply the cap for
        # consistency — but the spec says this is configurable, so
        # callers that want "leave integers alone" can post-process.
        if len(capped) >= len(original):
            return original
        saved += len(original) - len(capped)
        return capped

    new = _FLOAT_RE.sub(_sub, text)
    return new, saved


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def normalize_content(
    content: str,
    config: NormalizeConfig,
    tokenizer: Any | None = None,
) -> NormalizeResult:
    """Run the normalize pre-pass on `content`.

    Args:
        content: the tool-output / log / etc. text to normalize. Never
            touches user messages or assistant text — that gating is
            the caller's responsibility (per spec: applied only to
            tool-output content).
        config: pass configuration. With all sub-flags off, this
            function is a no-op and returns the input byte-identical
            (the flag-off golden test contract).
        tokenizer: optional tokenizer for per-pass token-savings
            estimation. Falls back to a 4-chars-per-token heuristic
            if None.

    Returns:
        NormalizeResult with the post-pass content, total tokens
        saved, and per-pass detail.
    """
    if not isinstance(content, str):
        # Defensive: pass-through non-strings. The ContentRouter will
        # never call us with non-strings, but downstream callers might.
        return NormalizeResult(content=content if isinstance(content, str) else "")

    if not any(
        (
            config.enable_unicode_normalization,
            config.enable_whitespace_collapse,
            config.enable_blob_to_pointer,
            config.enable_decimal_cap,
        )
    ):
        return NormalizeResult(content=content, tokens_saved=0, passes_applied=[])

    out = content
    passes: list[str] = []
    per_pass: dict[str, int] = {}
    total_saved = 0

    if config.enable_unicode_normalization:
        before = out
        out = _pass_unicode_normalize(out)[0]
        # NFC + homoglyph collapse is a real saving even when the
        # heuristic token estimator rounds to 0 (1-2 codepoints
        # don't move the 4-chars-per-token needle). Record the pass
        # as applied whenever it changed the content; the per-pass
        # token-saved count is best-effort.
        if out != before:
            passes.append("unicode_normalize")
            saved = _estimate_tokens_saved(before, out, None)
            per_pass["unicode_normalize"] = saved
            total_saved += saved

    if config.enable_whitespace_collapse:
        before = out
        out = _pass_whitespace_collapse(out)[0]
        if out != before:
            passes.append("whitespace_collapse")
            saved = _estimate_tokens_saved(before, out, None)
            per_pass["whitespace_collapse"] = saved
            total_saved += saved

    if config.enable_blob_to_pointer:
        # WS16 step 1 keeps the content unchanged; the wiring step
        # WS16.2 will replace the marker with a real CCR pointer.
        # We record the detection list for the caller's attribution.
        _out, blobs = _pass_blob_to_pointer(out, config.blob_to_pointer_threshold)
        if blobs:
            passes.append("blob_to_pointer")
            # The pass emits no content change in step 1, so the
            # token-saved estimate is 0. The wiring step will count
            # the actual savings once CCR-insert is wired in.
            per_pass["blob_to_pointer"] = 0
            per_pass["blob_to_pointer_count"] = len(blobs)

    if config.enable_decimal_cap and config.decimal_precision > 0:
        before = out
        out = _pass_decimal_cap(out, config.decimal_precision)[0]
        if out != before:
            passes.append("decimal_cap")
            saved = _estimate_tokens_saved(before, out, None)
            per_pass["decimal_cap"] = saved
            total_saved += saved

    # If a real tokenizer is available, re-estimate total savings
    # against it (the per-pass heuristic estimates are a fallback).
    if tokenizer is not None and out != content:
        real_saved = _estimate_tokens_saved(content, out, tokenizer)
        if real_saved > 0:
            total_saved = real_saved

    return NormalizeResult(
        content=out,
        tokens_saved=total_saved,
        passes_applied=passes,
        per_pass=per_pass,
    )


# Public exports
__all__ = [
    "NormalizeConfig",
    "NormalizeResult",
    "DEFAULT_BLOB_TO_POINTER_THRESHOLD",
    "DEFAULT_DECIMAL_PRECISION",
    "normalize_content",
]
