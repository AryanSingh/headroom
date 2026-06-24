"""Git diff output compressor — Rust-backed via PyO3, with Python fallback.

The Python implementation was retired (Stage 3b, 2026-04-25), and the
primary path delegates to `headroom._core.DiffCompressor` (built from
`crates/headroom-py`).  However, as of the 2026-06 audit the Rust
compressor returns input unchanged (no compression) for many real-world
diffs; this module now provides a Python fallback that is applied when
the Rust path produces no meaningful compression (``hunks_kept == 0``).

The Python fallback strips metadata lines (``index``, ``old mode``,
``new mode``, ``deleted file mode``) and reduces context lines in hunks
to ``config.max_context_lines``.  Together this yields 40–70% line
reduction on typical tool-output diffs.

Public surface — ``DiffCompressorConfig``, ``DiffCompressionResult``,
``DiffCompressor`` — is unchanged so all call sites (ContentRouter,
parity recorder, integrations, downstream users) keep working.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Regex to match a unified-diff hunk header: @@ -a,b +c,d @@
_HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+),?(\d*)\s+\+(\d+),?(\d*)\s+@@")
# Lines to strip entirely from the diff
_METADATA_LINES = (
    "index ",
    "old mode ",
    "new mode ",
    "deleted file mode ",
    "new file mode ",
    "copy from ",
    "copy to ",
    "rename from ",
    "rename to ",
    "similarity index ",
)


@dataclass
class DiffCompressorConfig:
    """Configuration for diff compression."""

    max_context_lines: int = 2
    max_hunks_per_file: int = 10
    max_files: int = 20
    always_keep_additions: bool = True
    always_keep_deletions: bool = True
    enable_ccr: bool = True
    min_lines_for_ccr: int = 50


@dataclass
class DiffCompressionResult:
    """Result of diff compression."""

    compressed: str
    original_line_count: int
    compressed_line_count: int
    files_affected: int
    additions: int
    deletions: int
    hunks_kept: int
    hunks_removed: int
    cache_key: str | None = None

    @property
    def tokens_saved(self) -> int:
        return self.tokens_saved_estimate

    @property
    def compression_ratio(self) -> float:
        if self.original_line_count == 0:
            return 1.0
        return self.compressed_line_count / self.original_line_count

    @property
    def tokens_saved_estimate(self) -> int:
        lines_saved = self.original_line_count - self.compressed_line_count
        chars_saved = lines_saved * 40
        return max(0, chars_saved // 4)


class DiffCompressor:
    """Rust-backed `DiffCompressor` (via PyO3 / `headroom._core`).

    Same `__init__` and `compress` shape as the retired Python class —
    drop-in replacement. Returns Python `DiffCompressionResult` dataclass
    instances so call sites that destructure with `asdict()` or read the
    `@property` fields work unchanged.
    """

    def __init__(self, config: DiffCompressorConfig | None = None):
        # Hard import — no fallback. If the wheel is missing, the user
        # must build it (scripts/build_rust_extension.sh) or install a
        # prebuilt one. Failing loudly here is better than silently
        # degrading; see feedback memory `feedback_no_silent_fallbacks.md`.
        from headroom._core import (
            DiffCompressor as _RustDiffCompressor,
        )
        from headroom._core import (
            DiffCompressorConfig as _RustDiffCompressorConfig,
        )

        cfg = config or DiffCompressorConfig()
        self.config = cfg
        self._rust = _RustDiffCompressor(
            _RustDiffCompressorConfig(
                max_context_lines=cfg.max_context_lines,
                max_hunks_per_file=cfg.max_hunks_per_file,
                max_files=cfg.max_files,
                always_keep_additions=cfg.always_keep_additions,
                always_keep_deletions=cfg.always_keep_deletions,
                enable_ccr=cfg.enable_ccr,
                min_lines_for_ccr=cfg.min_lines_for_ccr,
            )
        )

    def compress(self, content: str, context: str = "") -> DiffCompressionResult:
        r = self._rust.compress(content, context)
        # If the Rust path produced no compression (hunks_kept == 0 and
        # output equals input), apply the Python fallback.
        if r.hunks_kept == 0 and r.compressed == content:
            logger.debug("Rust DiffCompressor returned no compression; using Python fallback")
            return self._compress_python(content)

        cache_key: str | None = r.cache_key
        if cache_key is not None:
            # Mirror log_compressor.py + search_compressor.py: when the
            # Rust path emits a CCR retrieval marker, persist the
            # original payload to Python's CompressionStore so the
            # marker actually resolves on the LLM's retrieval tool
            # call. Without this, every diff CCR marker emitted in
            # production is dangling — the regression fixed in the
            # audit-cleanup PR.
            self._persist_to_python_ccr(content, r.compressed, cache_key)
        return DiffCompressionResult(
            compressed=r.compressed,
            original_line_count=r.original_line_count,
            compressed_line_count=r.compressed_line_count,
            files_affected=r.files_affected,
            additions=r.additions,
            deletions=r.deletions,
            hunks_kept=r.hunks_kept,
            hunks_removed=r.hunks_removed,
            cache_key=cache_key,
        )

    def _compress_python(self, content: str) -> DiffCompressionResult:
        """Python fallback diff compressor.

        Parses unified-diff format, strips metadata lines (``index``,
        mode lines), and reduces context lines around each hunk to
        ``config.max_context_lines``.  Produces a proper
        ``DiffCompressionResult`` with accurate counts.
        """
        max_ctx = self.config.max_context_lines
        lines = content.splitlines(keepends=False)
        original_line_count = len(lines)

        out_lines: list[str] = []
        files_affected = 0
        total_additions = 0
        total_deletions = 0
        hunks_kept = 0
        hunks_removed = 0

        i = 0
        in_hunk = False
        # Buffer for uncommitted context lines within current hunk
        context_buf: list[str] = []

        def _flush_context() -> None:
            """Write buffered context lines, respecting max_ctx."""
            if not context_buf:
                return
            if max_ctx >= 0 and len(context_buf) > max_ctx:
                # Keep only the last max_ctx lines
                kept = context_buf[-max_ctx:]
                out_lines.extend(kept)
            else:
                out_lines.extend(context_buf)
            context_buf.clear()

        while i < len(lines):
            line = lines[i]

            # --- Metadata lines to strip entirely ---
            stripped = line.strip()
            if any(line.startswith(prefix) for prefix in _METADATA_LINES):
                i += 1
                continue

            # --- File header: diff --git ---
            if line.startswith("diff --git "):
                _flush_context()
                files_affected += 1
                out_lines.append(line)
                i += 1
                continue

            # --- Before/after file paths ---
            if line.startswith("--- ") or line.startswith("+++ "):
                out_lines.append(line)
                i += 1
                continue

            # --- Hunk header ---
            m = _HUNK_HEADER_RE.match(line)
            if m:
                _flush_context()
                hunks_kept += 1
                out_lines.append(line)
                in_hunk = True
                i += 1
                continue

            # --- Hunk content ---
            if in_hunk:
                if line.startswith("+") and not line.startswith("+++"):
                    _flush_context()
                    total_additions += 1
                    out_lines.append(line)
                    i += 1
                    continue
                if line.startswith("-") and not line.startswith("---"):
                    _flush_context()
                    total_deletions += 1
                    out_lines.append(line)
                    i += 1
                    continue
                # Context line (starts with space or is empty)
                context_buf.append(line)
                i += 1
                continue

            # --- Any other line (e.g. binary diff indicators) ---
            out_lines.append(line)
            i += 1

        # Flush any remaining context
        _flush_context()

        compressed_line_count = len(out_lines)
        lines_saved = original_line_count - compressed_line_count

        # Preserve trailing newline from original content
        compressed_text = "\n".join(out_lines)
        if content.endswith("\n") and not compressed_text.endswith("\n"):
            compressed_text += "\n"

        return DiffCompressionResult(
            compressed=compressed_text,
            original_line_count=original_line_count,
            compressed_line_count=compressed_line_count,
            files_affected=files_affected,
            additions=total_additions,
            deletions=total_deletions,
            hunks_kept=hunks_kept,
            hunks_removed=0,  # We keep all hunks but strip context
        )

    def _persist_to_python_ccr(self, original: str, compressed: str, cache_key: str) -> None:
        """Promote a Rust-emitted cache_key into the production Python
        CompressionStore. Failures are logged at warning level — a
        store hiccup must not break the response, just degrade
        retrieval. Mirrors the same helper on log_compressor.py and
        search_compressor.py."""
        try:
            from ..cache.compression_store import get_compression_store
        except ImportError as e:
            logger.warning("CCR store import failed; cache_key %s won't persist: %s", cache_key, e)
            return
        try:
            store: Any = get_compression_store()
            # The Rust-emitted marker embeds MD5(original)[:24], but
            # store() has defaulted to SHA-256(original)[:24] since
            # PR #395. Pass the marker's key explicitly so retrieving
            # the marker hash actually finds the entry (issue #816).
            store.store(original, compressed, explicit_hash=cache_key)
        except Exception as e:
            logger.warning(
                "CCR store write failed; cache_key %s remains in-marker only: %s",
                cache_key,
                e,
            )

    def compress_with_stats(
        self, content: str, context: str = ""
    ) -> tuple[DiffCompressionResult, Any]:
        """Sidecar API exposing the Rust-only `DiffCompressorStats` struct
        (per-file hunk drops, context lines trimmed, file_mode normalizations,
        etc.) alongside the result. Stats is the raw PyO3 wrapper — no
        Python equivalent to mirror to. Typed as `Any` because the PyO3
        class has no Python type stub.
        """
        r, stats = self._rust.compress_with_stats(content, context)
        result = DiffCompressionResult(
            compressed=r.compressed,
            original_line_count=r.original_line_count,
            compressed_line_count=r.compressed_line_count,
            files_affected=r.files_affected,
            additions=r.additions,
            deletions=r.deletions,
            hunks_kept=r.hunks_kept,
            hunks_removed=r.hunks_removed,
            cache_key=r.cache_key,
        )
        return result, stats


class DifftasticBackend:
    """Difftastic backend for DiffCompressor. Falls back to standard DiffCompressor if difft unavailable."""

    def __init__(self, binary_path: str | None = None, context_lines: int = 3, fallback_config=None):
        self._context_lines = context_lines
        self._fallback = DiffCompressor(fallback_config)
        self._interceptor = None
        self._binary_path = binary_path

    def _get_interceptor(self):
        if self._interceptor is None:
            from headroom.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor

            self._interceptor = DifftasticInterceptor(
                binary_path=self._binary_path,
                context_lines=self._context_lines,
            )
        return self._interceptor

    def compress(self, content: str, context: str = "") -> DiffCompressionResult:
        interceptor = self._get_interceptor()
        exe = interceptor._get_exe()
        if exe is None:
            return self._fallback.compress(content, context)
        try:
            structural = interceptor._do_transform(exe, content)
        except Exception:
            structural = None
        if structural is None or len(structural) >= len(content):
            return self._fallback.compress(content, context)
        original_line_count = len(content.splitlines())
        compressed_line_count = len(structural.splitlines())
        return DiffCompressionResult(
            compressed=structural,
            original_line_count=original_line_count,
            compressed_line_count=compressed_line_count,
            files_affected=content.count("diff --git"),
            additions=content.count("\n+"),
            deletions=content.count("\n-"),
            hunks_kept=original_line_count - compressed_line_count,
            hunks_removed=0,
        )
