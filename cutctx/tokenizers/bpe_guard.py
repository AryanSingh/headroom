"""Bound the quadratic blow-up in byte-pair-encoding tokenizers.

H16: tiktoken's pre-tokenizer regex splits text on word boundaries, then runs
the BPE merge loop on each pre-token. The merge loop is quadratic in the
length of a single pre-token, so one unbroken run of non-whitespace characters
turns token counting into a CPU bomb:

    100 KB of "A"   -> cl100k_base encode: 2.41 s   (one 100 KB pre-token)
    same 100 KB, whitespace every 100 chars -> 0.004 s   (550x faster)

Measured scaling on a single run (cl100k_base): 12.5 KB 0.04 s, 25 KB 0.14 s,
50 KB 0.56 s, 100 KB 2.41 s — a clean 4x per doubling.

The quadratic lives inside tiktoken's Rust core, not in cutctx, so it cannot
be fixed here. What *can* be fixed is never handing it a pathological
pre-token: splitting an over-long run into bounded slices makes the total cost
linear in the text length (O(n * MAX_BPE_RUN_CHARS) instead of O(n^2)) at the
cost of a handful of boundary tokens in the count — token counts in cutctx are
advisory (used for compression decisions and telemetry), never billed.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

# Longest contiguous non-whitespace run handed to a BPE encoder in one piece.
# 1 KB keeps the per-slice merge cost near zero while still being an order of
# magnitude longer than any real word, URL, hash, identifier or base64 line,
# so ordinary prose, code and JSON are never sliced at all. (Measured: 4096
# left a 100 KB single-run body at ~0.5 s per pass; 1024 brings it to ~0.1 s.)
MAX_BPE_RUN_CHARS = 1024

_LONG_RUN_RE = re.compile(rf"\S{{{MAX_BPE_RUN_CHARS + 1},}}")


def has_pathological_run(text: str, *, limit: int = MAX_BPE_RUN_CHARS) -> bool:
    """True if ``text`` contains a non-whitespace run longer than ``limit``.

    Linear, C-speed scan — cheap enough to run on every count.
    """
    if len(text) <= limit:
        return False
    if limit == MAX_BPE_RUN_CHARS:
        return _LONG_RUN_RE.search(text) is not None
    return re.search(rf"\S{{{limit + 1},}}", text) is not None


def iter_bpe_safe_chunks(text: str, *, limit: int = MAX_BPE_RUN_CHARS) -> Iterator[str]:
    """Yield slices of ``text`` containing no non-whitespace run over ``limit``.

    Text without a pathological run is yielded unchanged in a single piece, so
    the common path costs one regex scan and nothing else.
    """
    if not has_pathological_run(text, limit=limit):
        yield text
        return

    pattern = _LONG_RUN_RE if limit == MAX_BPE_RUN_CHARS else re.compile(rf"\S{{{limit + 1},}}")
    cursor = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > cursor:
            yield text[cursor:start]
        for offset in range(start, end, limit):
            yield text[offset : min(offset + limit, end)]
        cursor = end
    if cursor < len(text):
        yield text[cursor:]
