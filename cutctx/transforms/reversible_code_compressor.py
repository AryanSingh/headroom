# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""Reversible code compression: elide function bodies, keep them retrievable.

Source code is the largest incompressible surface the proxy sees. On this
install, Codex traffic is 4.16B input tokens at 0.33% saved, and its one
compressible category — tool outputs — is dominated by code and patches.
Measured alternatives that do not work:

* lossless whitespace/blank-line normalisation: **0.03%** across 142 files,
  and not even reliably AST-preserving;
* the existing ``code_aware`` path: silently drops ~a quarter of function-body
  statements while keeping signatures, and emits invalid Python on half the
  files tested. For a *coding* agent that is the worst possible failure — it
  reads a file to edit it and cannot see what it is editing.

So the only honest way to compress code is to remove it **visibly and
reversibly**. This module elides large function bodies, replaces each with an
explicit marker naming its retrieval hash, and guarantees:

1. **Output parses.** The result is re-parsed before it is returned; if it
   does not compile the original is returned unchanged.
2. **Every elided span is retrievable.** Bodies go into the CCR store under
   the hash embedded in the marker. Nothing is removed that cannot be fetched.
3. **The skeleton survives.** Imports, class and function signatures, decorators,
   type annotations, docstrings and module-level code are never touched, so
   the agent keeps the structure it needs to navigate and to decide what to
   retrieve.
4. **Never inflates.** If the rewrite is not smaller it is discarded.

Anything that cannot satisfy (1)–(4) returns the input unchanged. A compressor
for code that an agent is about to edit has to fail closed.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass
from typing import Any

from cutctx.utils import compute_short_hash

logger = logging.getLogger(__name__)

#: Bodies below this many source lines are left alone — the marker costs a
#: line or two itself, and small functions are usually the ones being read.
DEFAULT_MIN_BODY_LINES = 8

#: Marker written in place of an elided body. Deliberately a comment plus a
#: `pass`: it survives re-parsing, it is obvious to a human reading the
#: transcript, and it names the exact retrieval key.
_MARKER = "    # <cutctx:code_elided sha256={hash} lines={lines}> retrieve to view"


@dataclass
class ReversibleCodeResult:
    """Outcome of one compression attempt."""

    compressed: str
    original: str
    elided_spans: int
    stored_hashes: list[str]
    reason: str | None = None

    @property
    def changed(self) -> bool:
        return self.compressed != self.original


class ReversibleCodeCompressor:
    """Elide large function bodies, keeping every one retrievable."""

    def __init__(
        self,
        *,
        min_body_lines: int = DEFAULT_MIN_BODY_LINES,
        ccr_store: Any | None = None,
    ) -> None:
        self.min_body_lines = min_body_lines
        self._ccr_store = ccr_store

    # -- storage ---------------------------------------------------------

    def _store(self, body_text: str) -> str | None:
        """Persist an elided body and return its retrieval hash.

        Returns None when storage is unavailable — the caller then leaves the
        body in place, because eliding something unretrievable is data loss.
        """
        digest = compute_short_hash(body_text)
        store = self._ccr_store
        if store is None:
            try:
                from cutctx.cache.compression_store import get_compression_store

                store = get_compression_store()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("CCR store unavailable, not eliding: %s", exc)
                return None
        if store is None:
            return None
        try:
            store.store(
                body_text,
                body_text,
                compression_strategy="reversible_code",
                explicit_hash=digest,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not store elided body, leaving it inline: %s", exc)
            return None
        return digest

    # -- compression -----------------------------------------------------

    def compress(self, code: str) -> ReversibleCodeResult:
        """Return *code* with large function bodies elided and retrievable."""
        unchanged = ReversibleCodeResult(
            compressed=code, original=code, elided_spans=0, stored_hashes=[]
        )
        if not code or not code.strip():
            return unchanged

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Not parseable Python. Say so rather than guessing with regex.
            unchanged.reason = "not_python"
            return unchanged

        lines = code.split("\n")
        # (start_index, end_index_exclusive, indent) for each elidable body.
        spans: list[tuple[int, int, str]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            body = [s for s in node.body if not _is_docstring(s)]
            if not body:
                continue
            start = body[0].lineno - 1
            end = max(_end_line(s) for s in body)
            if end - start < self.min_body_lines:
                continue
            indent = " " * (len(lines[start]) - len(lines[start].lstrip()))
            spans.append((start, end, indent))

        if not spans:
            unchanged.reason = "no_elidable_bodies"
            return unchanged

        # Innermost-last so replacements do not disturb earlier line numbers,
        # and drop spans nested inside one already being elided.
        spans.sort(key=lambda s: s[0])
        merged: list[tuple[int, int, str]] = []
        for span in spans:
            if merged and span[0] < merged[-1][1]:
                continue
            merged.append(span)

        out = list(lines)
        stored: list[str] = []
        for start, end, indent in reversed(merged):
            body_text = "\n".join(lines[start:end])
            digest = self._store(body_text)
            if digest is None:
                continue  # unretrievable -> leave the body inline
            marker = _MARKER.format(hash=digest, lines=end - start)
            out[start:end] = [indent + marker.strip(), indent + "pass"]
            stored.append(digest)

        if not stored:
            unchanged.reason = "storage_unavailable"
            return unchanged

        candidate = "\n".join(out)

        # Contract 1: the result must parse. Fail closed.
        try:
            ast.parse(candidate)
        except SyntaxError:
            logger.warning("Reversible code compression produced invalid syntax; discarding")
            unchanged.reason = "invalid_syntax_discarded"
            return unchanged

        # Contract 4: never hand back something larger.
        if len(candidate) >= len(code):
            unchanged.reason = "would_not_shrink"
            return unchanged

        return ReversibleCodeResult(
            compressed=candidate,
            original=code,
            elided_spans=len(stored),
            stored_hashes=stored,
            reason="elided",
        )


def _is_docstring(stmt: ast.stmt) -> bool:
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _end_line(stmt: ast.stmt) -> int:
    end = getattr(stmt, "end_lineno", None)
    return int(end) if end is not None else int(stmt.lineno)
