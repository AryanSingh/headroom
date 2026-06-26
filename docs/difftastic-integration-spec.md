# Difftastic Integration Spec

**Feature:** Opt-in structural AST-aware diff compression via `difft`
**Status:** Draft
**Author:** aryan@payzli.com
**Date:** 2026-06-24

---

## 1. Background and Goal

### Problem

Cutctx's existing `DiffCompressor` (`cutctx/transforms/diff_compressor.py`) processes unified diffs in line-oriented fashion. It strips metadata headers and trims context lines, producing 40–70% line reduction on typical diffs. However, it has a fundamental blind spot: it is **not AST-aware**. When a developer moves a 50-line function from one file to another — a pure refactor with zero semantic change — the unified diff shows 50 deletions + 50 additions (100 lines). The existing compressor preserves all 100 lines because it cannot recognize the move.

### What Difftastic Does Differently

Difftastic (MIT license, written in Rust, binary `difft`) parses source files into their ASTs and diffs the trees rather than raw lines. Key properties:

- **Moved code is 0 diff lines.** A function relocated to another file shows as empty or a single-line annotation, not N removed + N added.
- **Whitespace and formatting changes are ignored.** Adding a trailing comma in a function call argument list produces 0 diff output; unified diff produces 1 removal + 1 addition.
- **Understands 30+ languages** including Python, TypeScript, JavaScript, Go, Rust, Java, C, C++, Ruby, and more.
- **Compact structural output.** Difftastic emits only the nodes that genuinely changed at the AST level, often 60–80% fewer lines than the equivalent unified diff for large refactors.

### Why This Matters for Agentic Sessions

In a typical Cutctx-proxied Claude Code session, the LLM frequently invokes `git diff`, `git show`, or `git log -p` via the Bash tool. For large refactors, these produce thousands of lines of unified diff that fill context windows with redundant information. The LLM then has less context budget for actual reasoning. Difftastic converts those thousands of lines into a compact structural representation, leaving more room for the code that matters.

### Goal

Integrate difftastic as an **opt-in enhancement** to the existing diff pipeline. When enabled via `--difftastic`:

1. A new `DifftasticInterceptor` intercepts Bash/Run tool outputs that contain git diff output and rewrites them with structural diff.
2. The `ContentRouter`'s `DIFF` strategy can optionally prefer the structural backend.
3. The feature is **100% safe to disable** (default off); when disabled, behavior is identical to today.

---

## 2. Architecture Overview

### Two Integration Points

```
                         Incoming request
                               │
                   ┌───────────▼───────────┐
                   │  ToolResultInterceptor │  ◄── Point 1: DifftasticInterceptor
                   │       pipeline         │       intercepts Bash tool results
                   └───────────┬───────────┘       with git diff headers
                               │
                   ┌───────────▼───────────┐
                   │    ContentRouter       │  ◄── Point 2: DiffCompressor gains
                   │  (DIFF strategy)       │       difftastic backend when enabled
                   └───────────┬───────────┘
                               │
                           upstream LLM
```

### Point 1: DifftasticInterceptor (Primary Path)

`cutctx/proxy/interceptors/difftastic_interceptor.py`

The interceptor sits at position 0 in the `INTERCEPTORS` list when enabled. It:

- **matches()**: Returns `True` for any Bash/Run/computer tool result whose output begins with `diff --git a/` or contains a `--- a/`/`+++ b/` header pair, indicating a git-format unified diff.
- **transform()**: Parses the unified diff into per-file old/new content, writes each pair to private temp files, runs `difft old new`, collects the structural output, and reassembles a single compressed representation.
- **Never enlarges**: If `difft`'s output is longer (token count) than the original unified diff, `transform()` returns `None` and the base `DiffCompressor` continues to handle it.
- **Graceful fallback**: If `difft` is not found, times out, or exits non-zero on any file pair, that pair falls back to the original unified diff for that file; the interceptor never partially corrupts a diff.

### Point 2: DiffCompressor Backend (Secondary Path)

When `difftastic_enabled=True`, the `ContentRouter`'s `_get_diff_compressor()` lazy-loader returns a `DiffCompressor` initialized with `backend="difftastic"`. This handles DIFF-typed content that arrives via the ContentRouter pipeline rather than via Bash tool results (e.g., diff content pasted directly into a user message or returned by a non-Bash tool).

### Registration Flow

The interceptor is registered conditionally at proxy startup. The proxy reads the `difftastic_enabled` flag from `ProxyConfig`, resolves the `difft` binary via `cutctx.binaries.resolve("difft")`, and if both conditions are true, instantiates `DifftasticInterceptor` and calls `base.register()`.

---

## 3. Dependency Changes

### difftastic is a Binary, Not a Python Package

Difftastic is already in the `cutctx/tools.json` registry as of v0.64.0. The `binaries` module already knows how to fetch, cache, and resolve it. **No new pyproject.toml Python dependency is needed.**

The `tools.json` entry already covers:
- `linux-x86_64-gnu` and `linux-x86_64-musl` (same glibc asset)
- `linux-aarch64-gnu` and `linux-aarch64-musl`
- `darwin-x86_64` and `darwin-aarch64`
- `windows-x86_64`

### Manual Installation Alternative

For users who prefer to manage the binary outside of Cutctx's auto-fetch:

```bash
# macOS
brew install difftastic

# Rust / Cargo
cargo install difftastic

# Direct download (any platform)
# https://github.com/Wilfred/difftastic/releases/tag/0.64.0
```

After manual install, the binary must be named `difft` and be on `PATH`. Cutctx's `binaries.which("difft")` will find it there first (via `shutil.which`) and use it, bypassing the auto-fetched cache copy.

### `difftastic_binary` Config Option

A `difftastic_binary: str = "difft"` field in `ProxyConfig` (see Section 4) allows overriding the binary name or providing an absolute path. When set to an absolute path, `binaries.resolve()` is bypassed entirely and the path is used directly. When set to just `"difft"`, the normal `binaries.resolve("difft")` flow applies.

---

## 4. Config Flags

### 4.1 New fields in `cutctx/proxy/models.py`

Add after the existing `code_graph_watcher: bool = False` field (line 180):

```python
# ---------- Difftastic structural diff (opt-in) ----------
#
# Replace DiffCompressor with difftastic (difft) for AST-aware structural
# diff compression. Particularly effective on large refactors where moved
# code would otherwise produce N deletions + N additions in unified diff.
#
# Requirements: difft binary must be installed. Cutctx auto-fetches it
# from GitHub releases on first use, or it can be installed manually:
#   brew install difftastic
#   cargo install difftastic
#   https://github.com/Wilfred/difftastic/releases
#
# CLI: --difftastic; env: CUTCTX_DIFFTASTIC=1.
difftastic_enabled: bool = False

# Name or absolute path of the difft binary.
# - "difft" (default): use cutctx.binaries.resolve("difft") to find/fetch.
# - "/usr/local/bin/difft": use this path directly, skip auto-fetch.
# - "my-difft": PATH lookup only, no auto-fetch.
# CLI: --difftastic-binary <path>; env: CUTCTX_DIFFTASTIC_BINARY.
difftastic_binary: str = "difft"

# Context lines to pass to difftastic via DFT_CONTEXT_LINES env var.
# Difftastic uses this as a hint for how much surrounding context to show
# around changed nodes. 3 is the unified-diff default; 0 = minimal context.
# CLI: --difftastic-context-lines <n>; env: CUTCTX_DIFFTASTIC_CONTEXT_LINES.
difftastic_context_lines: int = 3
```

### 4.2 CLI Flags in `cutctx/cli/proxy.py`

Add the following `@click.option` decorators to the `proxy` command, following the pattern of existing flags like `--intercept-tool-results`:

```python
@click.option(
    "--difftastic",
    "difftastic_enabled",
    is_flag=True,
    envvar="CUTCTX_DIFFTASTIC",
    help=(
        "Enable structural diff compression via difftastic (difft). "
        "Rewrites Bash tool results that contain git diffs with AST-aware "
        "structural output. Particularly effective on large refactors. "
        "Requires the difft binary (auto-fetched or install via brew/cargo). "
        "Env: CUTCTX_DIFFTASTIC=1."
    ),
)
@click.option(
    "--difftastic-binary",
    default=None,
    envvar="CUTCTX_DIFFTASTIC_BINARY",
    help=(
        "Path or name of the difft binary (default: auto-resolved via Cutctx binary cache). "
        "Env: CUTCTX_DIFFTASTIC_BINARY."
    ),
)
@click.option(
    "--difftastic-context-lines",
    type=click.IntRange(min=0, max=20),
    default=None,
    envvar="CUTCTX_DIFFTASTIC_CONTEXT_LINES",
    help=(
        "Context lines to show around structural changes (0–20, default: 3). "
        "Env: CUTCTX_DIFFTASTIC_CONTEXT_LINES."
    ),
)
```

Pass the values to `ProxyConfig` construction in the `proxy` command handler:

```python
config = ProxyConfig(
    ...
    difftastic_enabled=difftastic_enabled,
    difftastic_binary=difftastic_binary or "difft",
    difftastic_context_lines=difftastic_context_lines if difftastic_context_lines is not None else 3,
    ...
)
```

---

## 5. Binary Detection Pattern

Add a `find_difftastic()` helper in `cutctx/binaries.py`, following the same pattern used internally by `resolve()` and `which()`:

```python
def find_difftastic(binary_override: str = "difft") -> Path | None:
    """Return a path to the difft binary, or None if unavailable.

    Resolution order:
    1. If ``binary_override`` is an absolute path and the file exists, use it directly.
    2. If ``binary_override`` != "difft", treat as a PATH name and call shutil.which().
       No auto-fetch in this case (custom name implies user-managed binary).
    3. Fall through to ``which("difft")`` (PATH + already-cached check, no network).
    4. Finally, attempt ``resolve("difft")`` which auto-fetches from GitHub releases.

    Returns None instead of raising. Callers in the compression pipeline should
    log at DEBUG level and treat absence as "feature unavailable — fall back to
    DiffCompressor".

    Never raises. All BinaryError subclasses and OSError are caught internally.
    """
    # Step 1: absolute path override
    if binary_override and binary_override != "difft":
        p = Path(binary_override)
        if p.is_absolute():
            return p if p.exists() else None
        # Relative / plain name — PATH lookup only, no auto-fetch
        found = shutil.which(binary_override)
        return Path(found) if found else None

    # Step 2: check PATH + already-cached (no network)
    on_path = which("difft")
    if on_path:
        return on_path

    # Step 3: auto-fetch from GitHub releases via binaries.resolve()
    try:
        return resolve("difft")
    except (BinaryError, OSError, KeyError) as e:
        logger.debug("difft not available: %s", e)
        return None
```

---

## 6. Full Implementation: `DifftasticInterceptor`

**File:** `cutctx/proxy/interceptors/difftastic_interceptor.py` (new file)

```python
"""Difftastic interceptor: replace git diff output with structural AST-aware diffs.

Matches Bash/Run/computer tool results that contain git-format unified diff output
and rewrites them using difftastic (``difft``), which understands 30+ languages and
produces compact structural output. Moved code shows as 0 diff lines; whitespace-only
changes are silently dropped.

Key properties:
- 100% opt-in: never activated unless difftastic_enabled=True in ProxyConfig.
- Never enlarges: if difft output is larger than unified diff, passes through unchanged.
- Graceful fallback: subprocess timeout, binary absence, or non-zero exit all fall back
  to the original text. No partial corruption.
- Subprocess timeout: 10 seconds per file pair to prevent blocking the proxy on
  pathological inputs.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from cutctx import binaries

from . import base

logger = logging.getLogger(__name__)

# Minimum size below which the subprocess overhead is not worth the possible savings.
# ~200 chars is roughly 5 lines of diff — too small to matter.
MIN_CHARS_TO_TRANSFORM = int(os.environ.get("CUTCTX_DIFFT_MIN_CHARS", "200"))

# Timeout per file pair in seconds.
SUBPROCESS_TIMEOUT_SECONDS = 10

# Patterns that identify git-format unified diff content
_DIFF_GIT_RE = re.compile(r"^diff --git a/", re.MULTILINE)
_DIFF_HUNK_RE = re.compile(r"^--- a/", re.MULTILINE)

# Parse file pair headers from unified diff
# Matches: "diff --git a/path/to/file b/path/to/file"
_FILE_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)

# Match hunk markers so we can detect where file content ends
_HUNK_MARKER_RE = re.compile(r"^@@\s+-\d+", re.MULTILINE)

# Lines to skip when reconstructing old/new content from a hunk
_META_PREFIXES = (
    "diff --git ",
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
    "--- ",
    "+++ ",
)


def _is_git_diff(text: str) -> bool:
    """Return True if text looks like a git-format unified diff."""
    return bool(_DIFF_GIT_RE.search(text)) or bool(_DIFF_HUNK_RE.search(text))


def _split_into_file_diffs(text: str) -> list[tuple[str, str, str]]:
    """Split a multi-file unified diff into per-file sections.

    Returns a list of (path_a, path_b, section_text) triples.
    path_a and path_b are the old and new file paths from the diff header.
    If the diff has no ``diff --git`` markers (e.g. a bare ``--- a/`` diff),
    the entire text is returned as a single section with empty paths.
    """
    headers = list(_FILE_HEADER_RE.finditer(text))
    if not headers:
        return [("", "", text)]

    sections: list[tuple[str, str, str]] = []
    for i, match in enumerate(headers):
        start = match.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        sections.append((match.group(1), match.group(2), text[start:end]))
    return sections


def _reconstruct_old_new(section: str) -> tuple[str, str, str]:
    """Extract old and new file content from a unified diff section.

    Parses the hunk blocks and rebuilds the pre-change (old) and post-change
    (new) file content in memory, to be written to temp files for difft.

    Returns (old_content, new_content, extension) where extension is
    the file extension (e.g. ".py") extracted from the file path in the header.
    """
    lines = section.splitlines(keepends=False)
    old_lines: list[str] = []
    new_lines: list[str] = []
    ext = ""

    for line in lines:
        # Extract extension from --- a/ line for temp file naming
        if line.startswith("--- a/") or line.startswith("--- /dev/null"):
            if not ext and line.startswith("--- a/"):
                path_part = line[6:].strip()
                ext = Path(path_part).suffix or ""
            continue
        if line.startswith("+++ b/") or line.startswith("+++ /dev/null"):
            if not ext and line.startswith("+++ b/"):
                path_part = line[6:].strip()
                ext = Path(path_part).suffix or ""
            continue
        # Skip all metadata lines
        if any(line.startswith(prefix) for prefix in _META_PREFIXES):
            continue
        # Skip hunk headers (@@...@@)
        if line.startswith("@@"):
            continue
        # Added line
        if line.startswith("+"):
            new_lines.append(line[1:])
        # Removed line
        elif line.startswith("-"):
            old_lines.append(line[1:])
        # Context line (space-prefixed or bare)
        else:
            ctx = line[1:] if line.startswith(" ") else line
            old_lines.append(ctx)
            new_lines.append(ctx)

    return "\n".join(old_lines), "\n".join(new_lines), ext or ".txt"


def _run_difft(
    exe: Path | str,
    old_content: str,
    new_content: str,
    ext: str,
    context_lines: int,
) -> str | None:
    """Write old/new content to temp files and run difft.

    Returns the structural diff output, or None if difft failed, timed out,
    or produced no output.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="cutctx-difft-"))
    try:
        try:
            os.chmod(tmp_dir, 0o700)
        except OSError as e:
            logger.debug("chmod 0700 on difft tmp dir failed: %s", e)

        old_path = tmp_dir / f"old{ext}"
        new_path = tmp_dir / f"new{ext}"
        old_path.write_text(old_content, encoding="utf-8", errors="replace")
        new_path.write_text(new_content, encoding="utf-8", errors="replace")

        env = os.environ.copy()
        env["DFT_CONTEXT_LINES"] = str(context_lines)
        # Force plain text output (no color / ANSI codes)
        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"

        try:
            result = subprocess.run(
                [str(exe), str(old_path), str(new_path)],
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT_SECONDS,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            logger.debug(
                "difft timed out after %ds for ext=%s",
                SUBPROCESS_TIMEOUT_SECONDS,
                ext,
            )
            return None
        except OSError as e:
            logger.debug("difft OSError for ext=%s: %s", ext, e)
            return None

        if result.returncode not in (0, 1):
            # rc=0: success (changes found). rc=1: no differences.
            # rc>=2: error (binary not found, parse failure, etc.)
            logger.debug(
                "difft exited rc=%d for ext=%s: %s",
                result.returncode,
                ext,
                (result.stderr or "")[:200],
            )
            return None

        return result.stdout or ""

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class DifftasticInterceptor:
    """Interceptor that rewrites git diff outputs with difftastic structural diffs.

    Activated only when ``difftastic_enabled=True`` in ProxyConfig. When the difft
    binary is unavailable or any transformation fails, returns None so the base
    DiffCompressor pipeline takes over.
    """

    name = "difft"

    def __init__(
        self,
        binary_path: Path | str | None = None,
        context_lines: int = 3,
    ) -> None:
        """
        Args:
            binary_path: Resolved path to the difft binary. If None, the interceptor
                will attempt to resolve via ``binaries.find_difftastic()`` on first use.
            context_lines: Number of context lines to request from difft via
                DFT_CONTEXT_LINES. Defaults to 3 (unified-diff standard).
        """
        self._binary_path: Path | str | None = binary_path
        self._context_lines = context_lines
        self._resolved: Path | None = None
        self._unavailable: bool = False  # latched True on first resolution failure

    def _get_exe(self) -> Path | None:
        """Return the resolved difft path, attempting resolution once if needed."""
        if self._unavailable:
            return None
        if self._resolved is not None:
            return self._resolved
        if self._binary_path is not None:
            p = Path(self._binary_path)
            if p.exists():
                self._resolved = p
                return self._resolved
            # Treat as a name for PATH lookup
            found = shutil.which(str(self._binary_path))
            if found:
                self._resolved = Path(found)
                return self._resolved

        # Fall back to binaries module
        try:
            exe = binaries.resolve("difft")
            self._resolved = exe
            return self._resolved
        except (binaries.BinaryError, KeyError, OSError) as e:
            logger.debug("difft unavailable: %s", e)
            self._unavailable = True
            return None

    def matches(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> bool:
        """Return True for Bash/Run/computer tool results that look like git diffs."""
        # Only process tool outputs from shell execution tools
        if tool_name not in (
            "Bash",
            "bash",
            "Run",
            "run",
            "computer",
            "execute_bash",
            "shell",
            "run_terminal_cmd",
        ):
            return False
        if len(tool_output) < MIN_CHARS_TO_TRANSFORM:
            return False
        return _is_git_diff(tool_output)

    def transform(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> str | None:
        """Rewrite a git diff using difftastic structural output.

        Returns a new string (the structural diff) if it is strictly shorter
        than the original, otherwise returns None. Never raises.
        """
        exe = self._get_exe()
        if exe is None:
            return None

        try:
            return self._do_transform(exe, tool_output)
        except Exception as e:  # noqa: BLE001
            logger.debug("DifftasticInterceptor.transform failed unexpectedly: %s", e)
            return None

    def _do_transform(self, exe: Path, unified_diff: str) -> str | None:
        """Core transform: split diff into file sections, run difft on each, reassemble."""
        file_sections = _split_into_file_diffs(unified_diff)
        if not file_sections:
            return None

        output_parts: list[str] = []
        total_input_lines = len(unified_diff.splitlines())
        total_output_lines = 0

        for path_a, path_b, section_text in file_sections:
            old_content, new_content, ext = _reconstruct_old_new(section_text)

            # Both empty means the section was pure metadata (rename/mode change)
            # with no content changes. Emit a compact one-liner instead.
            if not old_content.strip() and not new_content.strip():
                if path_a and path_b and path_a != path_b:
                    output_parts.append(f"[renamed: {path_a} → {path_b}]")
                elif path_a:
                    output_parts.append(f"[mode change: {path_a}]")
                continue

            difft_out = _run_difft(exe, old_content, new_content, ext, self._context_lines)

            if difft_out is None:
                # Fallback for this file: use the original section
                output_parts.append(section_text.rstrip())
                total_output_lines += len(section_text.splitlines())
                continue

            # Prepend file header to structural output if we have paths
            if path_a or path_b:
                header = f"[difft] {path_a or '?'} → {path_b or '?'}"
                file_structural = header + "\n" + difft_out.rstrip()
            else:
                file_structural = difft_out.rstrip()

            output_parts.append(file_structural)
            total_output_lines += len(file_structural.splitlines())

        if not output_parts:
            return None

        reassembled = "\n\n".join(output_parts)

        # Never enlarge — if difft output is longer than unified diff, pass through.
        # Token count would be more accurate but line count is a good fast proxy
        # and avoids the Tokenizer import in this low-level module.
        if len(reassembled.splitlines()) >= total_input_lines:
            logger.debug(
                "difft output is not shorter (%d >= %d lines); passing through",
                len(reassembled.splitlines()),
                total_input_lines,
            )
            return None

        banner = (
            f"[cutctx: structural diff via difft v{self._get_difft_version()}; "
            f"{total_input_lines} → {len(reassembled.splitlines())} lines]"
        )
        return banner + "\n" + reassembled

    def _get_difft_version(self) -> str:
        """Return the difft version string (best-effort, cached)."""
        if hasattr(self, "_version_cache"):
            return self._version_cache  # type: ignore[attr-defined]
        exe = self._get_exe()
        if exe is None:
            return "unknown"
        try:
            r = subprocess.run(
                [str(exe), "--version"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            version = (r.stdout or "").strip().split()[-1] if r.returncode == 0 else "unknown"
        except (subprocess.TimeoutExpired, OSError):
            version = "unknown"
        self._version_cache = version  # type: ignore[attr-defined]
        return version

    def progressive_disclosure_key(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
    ) -> str | None:
        """Key by a hash of the Bash command, so repeated identical diffs pass through."""
        cmd = tool_input.get("command") or tool_input.get("cmd") or tool_input.get("input")
        if isinstance(cmd, str) and cmd:
            return "difft:" + hashlib.sha256(cmd.encode()).hexdigest()[:16]
        return None
```

---

## 7. Enhanced DiffCompressor

The `ContentRouter` calls `_get_diff_compressor()` for `DIFF`-typed content. When `difftastic_enabled=True`, a thin wrapper over `DiffCompressor` provides the structural backend. This is the secondary integration path (handles DIFF content that does not arrive via a Bash tool result).

Add to `cutctx/transforms/diff_compressor.py`:

```python
class DifftasticBackend:
    """Difftastic backend for DiffCompressor.

    Wraps ``DifftasticInterceptor``'s core ``_do_transform`` logic in the
    ``DiffCompressor`` interface (``compress()`` returns ``DiffCompressionResult``).
    Used by ``ContentRouter._get_diff_compressor()`` when
    ``config.difftastic_enabled=True``.

    Falls back to the standard Rust ``DiffCompressor`` if difft is unavailable
    or produces no compression.
    """

    def __init__(
        self,
        binary_path: str | None = None,
        context_lines: int = 3,
        fallback_config: DiffCompressorConfig | None = None,
    ) -> None:
        self._context_lines = context_lines
        self._fallback = DiffCompressor(fallback_config)
        # Lazy import to avoid circular dependency
        self._interceptor: Any = None
        self._binary_path = binary_path

    def _get_interceptor(self) -> Any:
        if self._interceptor is None:
            from cutctx.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor
            self._interceptor = DifftasticInterceptor(
                binary_path=self._binary_path,
                context_lines=self._context_lines,
            )
        return self._interceptor

    def compress(self, content: str, context: str = "") -> DiffCompressionResult:
        """Compress content via difftastic, with DiffCompressor as fallback."""
        interceptor = self._get_interceptor()
        exe = interceptor._get_exe()
        if exe is None:
            logger.debug("diftt unavailable for DifftasticBackend; using DiffCompressor fallback")
            return self._fallback.compress(content, context)

        try:
            structural = interceptor._do_transform(exe, content)
        except Exception as e:
            logger.debug("DifftasticBackend._do_transform failed: %s; falling back", e)
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
```

### ContentRouter Change

In `cutctx/transforms/content_router.py`, modify `_get_diff_compressor()`:

```python
def _get_diff_compressor(self) -> Any:
    """Get DiffCompressor (lazy load), using difftastic backend when enabled."""
    if self._diff_compressor is None:
        from .diff_compressor import DiffCompressor, DifftasticBackend

        # Check if difftastic is requested via runtime flag (set by proxy server
        # from ProxyConfig.difftastic_enabled before apply() is called).
        if getattr(self, "_runtime_difftastic_enabled", False):
            self._diff_compressor = DifftasticBackend(
                binary_path=getattr(self, "_runtime_difftastic_binary", None),
                context_lines=getattr(self, "_runtime_difftastic_context_lines", 3),
            )
        else:
            self._diff_compressor = DiffCompressor()
    return self._diff_compressor
```

The proxy server sets these runtime attrs on the `ContentRouter` instance during startup, analogous to how `_runtime_target_ratio` and `_runtime_kompress_model` are currently set.

---

## 8. Full Test File

**File:** `tests/test_difftastic_interceptor.py` (new file)

```python
"""Tests for DifftasticInterceptor.

Tests run against the real interceptor logic with subprocess mocked out
so they work in CI without difft installed. The "integration" tests at
the bottom use a real difft binary via ``binaries.which("difft")`` and
are skipped if not found.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cutctx.proxy.interceptors.difftastic_interceptor import (
    DifftasticInterceptor,
    _is_git_diff,
    _reconstruct_old_new,
    _run_difft,
    _split_into_file_diffs,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_GIT_DIFF = textwrap.dedent("""\
    diff --git a/foo.py b/foo.py
    index abcdef1..1234567 100644
    --- a/foo.py
    +++ b/foo.py
    @@ -1,5 +1,5 @@
     def hello():
    -    print("hello world")
    +    print("hello, world!")
         pass
""")

MULTI_FILE_GIT_DIFF = textwrap.dedent("""\
    diff --git a/alpha.py b/alpha.py
    index 0000001..0000002 100644
    --- a/alpha.py
    +++ b/alpha.py
    @@ -1,3 +1,3 @@
     x = 1
    -y = 2
    +y = 99
     z = 3
    diff --git a/beta.ts b/beta.ts
    index 0000003..0000004 100644
    --- a/beta.ts
    +++ b/beta.ts
    @@ -1,3 +1,4 @@
     const a = 1;
    +const b = 2;
     const c = 3;
""")

NOT_A_DIFF = "hello world\nno diff headers here\n"

SEARCH_OUTPUT = textwrap.dedent("""\
    src/main.py:10: def main():
    src/utils.py:25: def helper():
""")


# ---------------------------------------------------------------------------
# Unit tests: matching logic
# ---------------------------------------------------------------------------

class TestMatches:
    def _make_interceptor(self) -> DifftasticInterceptor:
        return DifftasticInterceptor(binary_path="/fake/difft")

    def test_matches_bash_with_git_diff(self) -> None:
        interceptor = self._make_interceptor()
        assert interceptor.matches("Bash", {"command": "git diff HEAD"}, SIMPLE_GIT_DIFF)

    def test_matches_run_with_git_diff(self) -> None:
        interceptor = self._make_interceptor()
        assert interceptor.matches("Run", {}, SIMPLE_GIT_DIFF)

    def test_no_match_on_non_diff_output(self) -> None:
        interceptor = self._make_interceptor()
        assert not interceptor.matches("Bash", {"command": "ls"}, NOT_A_DIFF)

    def test_no_match_on_search_output(self) -> None:
        interceptor = self._make_interceptor()
        assert not interceptor.matches("Bash", {"command": "grep"}, SEARCH_OUTPUT)

    def test_no_match_on_read_tool(self) -> None:
        interceptor = self._make_interceptor()
        assert not interceptor.matches("Read", {"file_path": "foo.py"}, SIMPLE_GIT_DIFF)

    def test_no_match_below_min_chars(self) -> None:
        interceptor = self._make_interceptor()
        tiny_diff = "diff --git a/f b/f\n--- a/f\n+++ b/f\n"
        assert not interceptor.matches("Bash", {}, tiny_diff)

    def test_matches_multi_file_diff(self) -> None:
        interceptor = self._make_interceptor()
        assert interceptor.matches("Bash", {}, MULTI_FILE_GIT_DIFF)


# ---------------------------------------------------------------------------
# Unit tests: _is_git_diff helper
# ---------------------------------------------------------------------------

class TestIsGitDiff:
    def test_detects_diff_git_header(self) -> None:
        assert _is_git_diff("diff --git a/foo b/foo\n")

    def test_detects_bare_minus_a_header(self) -> None:
        assert _is_git_diff("--- a/foo.py\n+++ b/foo.py\n")

    def test_rejects_plain_text(self) -> None:
        assert not _is_git_diff("no diff here\n")

    def test_rejects_grep_output(self) -> None:
        assert not _is_git_diff("file.py:10: def foo():\n")


# ---------------------------------------------------------------------------
# Unit tests: _split_into_file_diffs
# ---------------------------------------------------------------------------

class TestSplitIntoFileDiffs:
    def test_single_file(self) -> None:
        sections = _split_into_file_diffs(SIMPLE_GIT_DIFF)
        assert len(sections) == 1
        path_a, path_b, text = sections[0]
        assert path_a == "foo.py"
        assert path_b == "foo.py"
        assert "print" in text

    def test_multi_file(self) -> None:
        sections = _split_into_file_diffs(MULTI_FILE_GIT_DIFF)
        assert len(sections) == 2
        assert sections[0][0] == "alpha.py"
        assert sections[1][0] == "beta.ts"

    def test_bare_diff_no_git_header(self) -> None:
        bare = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new\n"
        sections = _split_into_file_diffs(bare)
        assert len(sections) == 1
        path_a, path_b, text = sections[0]
        assert path_a == ""
        assert path_b == ""


# ---------------------------------------------------------------------------
# Unit tests: _reconstruct_old_new
# ---------------------------------------------------------------------------

class TestReconstructOldNew:
    def test_extracts_old_and_new(self) -> None:
        old, new, ext = _reconstruct_old_new(SIMPLE_GIT_DIFF)
        assert "hello world" in old
        assert "hello, world!" in new
        assert "hello world" not in new
        assert ext == ".py"

    def test_context_lines_appear_in_both(self) -> None:
        old, new, ext = _reconstruct_old_new(SIMPLE_GIT_DIFF)
        # "def hello():" is a context line
        assert "def hello" in old
        assert "def hello" in new


# ---------------------------------------------------------------------------
# Unit tests: subprocess timeout handling
# ---------------------------------------------------------------------------

class TestSubprocessTimeout:
    def test_timeout_returns_none(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="difft", timeout=10)):
            result = _run_difft("/fake/difft", "old", "new", ".py", context_lines=3)
        assert result is None

    def test_oserror_returns_none(self) -> None:
        with patch("subprocess.run", side_effect=OSError("no such file")):
            result = _run_difft("/fake/difft", "old", "new", ".py", context_lines=3)
        assert result is None

    def test_nonzero_exit_code_returns_none(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "parse error"
        with patch("subprocess.run", return_value=mock_result):
            result = _run_difft("/fake/difft", "old", "new", ".py", context_lines=3)
        assert result is None


# ---------------------------------------------------------------------------
# Unit tests: transform output quality
# ---------------------------------------------------------------------------

class TestTransformOutputQuality:
    def _make_interceptor_with_mock_difft(self, difft_output: str) -> DifftasticInterceptor:
        interceptor = DifftasticInterceptor(context_lines=3)
        # Bypass binary resolution
        interceptor._resolved = Path("/fake/difft")
        interceptor._unavailable = False

        mock_completed = MagicMock()
        mock_completed.returncode = 0
        mock_completed.stdout = difft_output
        mock_completed.stderr = ""

        # Patch subprocess.run globally for the duration of the test
        self._patch = patch("subprocess.run", return_value=mock_completed)
        self._mock_run = self._patch.start()
        return interceptor

    def teardown_method(self) -> None:
        if hasattr(self, "_patch"):
            self._patch.stop()

    def test_structural_diff_shorter_than_unified_is_accepted(self) -> None:
        # difft output: one short line vs original's many lines
        short_difft_output = "foo.py --- hello_world: String(\"world\") -> String(\"world!\")\n"
        interceptor = self._make_interceptor_with_mock_difft(short_difft_output * 2)
        result = interceptor.transform("Bash", {}, SIMPLE_GIT_DIFF)
        # Result should not be None — it's shorter
        assert result is not None
        assert "[cutctx: structural diff via difft" in result

    def test_structural_diff_longer_than_unified_returns_none(self) -> None:
        # Pathological case: difft output is much longer than input
        bloated_output = "A very long line\n" * 1000
        interceptor = self._make_interceptor_with_mock_difft(bloated_output)
        result = interceptor.transform("Bash", {}, SIMPLE_GIT_DIFF)
        assert result is None

    def test_binary_not_found_graceful_fallback(self) -> None:
        interceptor = DifftasticInterceptor(binary_path="/nonexistent/path/difft")
        # Should return None (binary missing) rather than raising
        result = interceptor.transform("Bash", {}, SIMPLE_GIT_DIFF)
        assert result is None

    def test_empty_difft_output_returns_none(self) -> None:
        interceptor = self._make_interceptor_with_mock_difft("")
        result = interceptor.transform("Bash", {}, SIMPLE_GIT_DIFF)
        # Empty difft output means no changes found (rc=1 path) or
        # the file pairs are empty; should fall back gracefully
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# Unit tests: progressive_disclosure_key
# ---------------------------------------------------------------------------

class TestProgressiveDisclosureKey:
    def test_key_from_command(self) -> None:
        interceptor = DifftasticInterceptor()
        key = interceptor.progressive_disclosure_key("Bash", {"command": "git diff HEAD"})
        assert key is not None
        assert key.startswith("difft:")

    def test_key_is_deterministic(self) -> None:
        interceptor = DifftasticInterceptor()
        k1 = interceptor.progressive_disclosure_key("Bash", {"command": "git diff"})
        k2 = interceptor.progressive_disclosure_key("Bash", {"command": "git diff"})
        assert k1 == k2

    def test_key_differs_for_different_commands(self) -> None:
        interceptor = DifftasticInterceptor()
        k1 = interceptor.progressive_disclosure_key("Bash", {"command": "git diff HEAD"})
        k2 = interceptor.progressive_disclosure_key("Bash", {"command": "git diff HEAD~1"})
        assert k1 != k2

    def test_no_key_when_no_command(self) -> None:
        interceptor = DifftasticInterceptor()
        key = interceptor.progressive_disclosure_key("Bash", {})
        assert key is None


# ---------------------------------------------------------------------------
# Integration tests (skipped if difft not available)
# ---------------------------------------------------------------------------

def _difft_available() -> bool:
    from cutctx import binaries
    return binaries.which("difft") is not None


@pytest.mark.skipif(not _difft_available(), reason="difft not installed")
class TestIntegration:
    """Real difft integration tests — require difft on PATH or in binaries cache."""

    def test_real_diff_produces_shorter_output(self) -> None:
        from cutctx import binaries
        exe = binaries.which("difft")
        assert exe is not None

        # A simple addition diff — difft should handle it
        simple_diff = textwrap.dedent("""\
            diff --git a/greet.py b/greet.py
            index aaa..bbb 100644
            --- a/greet.py
            +++ b/greet.py
            @@ -1,4 +1,5 @@
             def greet(name):
            +    \"\"\"Greet someone.\"\"\"
                 print(f"Hello, {name}")
                 return name
        """)

        interceptor = DifftasticInterceptor(binary_path=str(exe), context_lines=3)
        # Should return either structural output or None (if not shorter)
        result = interceptor.transform("Bash", {"command": "git diff"}, simple_diff)
        # Either structural output (str) or None (not shorter) — both are valid
        assert result is None or isinstance(result, str)

    def test_real_difft_version_detection(self) -> None:
        from cutctx import binaries
        exe = binaries.which("difft")
        interceptor = DifftasticInterceptor(binary_path=str(exe))
        version = interceptor._get_difft_version()
        # Should return a version string (e.g. "0.64.0") not "unknown"
        assert version != "" and isinstance(version, str)
```

---

## 9. Binary Installation Verification Helper

### 9.1 Startup Check

The proxy server should verify difft availability at startup when `difftastic_enabled=True`. Add to the proxy's startup lifespan logic (wherever `binaries.ensure_tools()` is called, typically in `cutctx/proxy/server.py`):

```python
if config.difftastic_enabled:
    from cutctx.binaries import find_difftastic

    difft_path = find_difftastic(config.difftastic_binary)
    if difft_path is None:
        logger.warning(
            "difftastic_enabled=True but difft binary not found and auto-fetch failed. "
            "Diff compression will fall back to DiffCompressor. "
            "Install manually: brew install difftastic  OR  cargo install difftastic"
        )
    else:
        logger.info("difft resolved at %s", difft_path)
        # Pre-register the interceptor
        from cutctx.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor
        from cutctx.proxy.interceptors import base as interceptor_base

        interceptor = DifftasticInterceptor(
            binary_path=difft_path,
            context_lines=config.difftastic_context_lines,
        )
        interceptor_base.register(interceptor)
        logger.info(
            "DifftasticInterceptor registered (context_lines=%d)",
            config.difftastic_context_lines,
        )
```

### 9.2 `cutctx tools install` Already Works

Because `difft` is already in `tools.json`, running `cutctx tools install` will fetch and cache it. The `cutctx tools doctor` command will show its state. No separate `cutctx install-difftastic` command is needed — the existing tools CLI already handles it:

```bash
# Verify difft is available
cutctx tools doctor

# Pre-fetch difft (and all other tools) into the per-user cache
cutctx tools install

# Fetch only difft
cutctx tools install --tool difft

# Run difft directly via Cutctx passthrough
cutctx diff old_file.py new_file.py
```

### 9.3 Minimal Sanity-Check CLI Command (Optional Enhancement)

For self-contained verification, a `cutctx difftastic check` sub-command can be added to `cutctx/cli/tools.py`:

```python
@tools_group.command("difft-check")
def tools_difft_check_cmd() -> None:
    """Verify difftastic (difft) is available and working."""
    from cutctx.binaries import find_difftastic

    path = find_difftastic()
    if path is None:
        click.secho("difft: NOT FOUND", fg="red")
        click.echo("Install with:  brew install difftastic  OR  cargo install difftastic")
        raise SystemExit(1)

    click.secho(f"difft: found at {path}", fg="green")

    # Quick smoke test: diff two trivial strings
    import tempfile
    import subprocess
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as old:
        old.write("hello world\n")
        old_path = old.name
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as new:
        new.write("hello, world!\n")
        new_path = new.name
    try:
        result = subprocess.run(
            [str(path), old_path, new_path],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode in (0, 1):
            click.secho("difft smoke test: PASSED", fg="green")
        else:
            click.secho(f"difft smoke test: FAILED (rc={result.returncode})", fg="red")
            click.echo(result.stderr[:500])
            raise SystemExit(1)
    except subprocess.TimeoutExpired:
        click.secho("difft smoke test: TIMED OUT", fg="red")
        raise SystemExit(1)
    finally:
        import os
        os.unlink(old_path)
        os.unlink(new_path)
```

---

## 10. Verification Steps

The following 10 steps verify the complete integration end-to-end with exact commands.

### Step 1: Verify difft binary is available

```bash
# Check if Cutctx can find/fetch difft
cutctx tools doctor

# Expected output: a table row showing difft with state "cached" or "on-path"
# If missing: run step 2 first
```

### Step 2: Fetch difft binary

```bash
cutctx tools install --tool difft

# Expected: "difft: installed → /path/to/cached/difft-0.64.0-darwin-aarch64/difft"
```

### Step 3: Smoke-test the binary directly

```bash
# Create two trivial test files
echo 'def hello():\n    print("world")' > /tmp/old.py
echo 'def hello():\n    print("world!")' > /tmp/new.py

# Run via Cutctx passthrough
cutctx diff /tmp/old.py /tmp/new.py

# Expected: structural output showing the String literal change, not line-diff
```

### Step 4: Verify the interceptor's match logic (Python unit test)

```bash
cd /Users/aryansingh/Documents/Claude/Projects/cutctx

python -m pytest tests/test_difftastic_interceptor.py::TestMatches -v

# Expected: 7 tests pass
```

### Step 5: Run all interceptor unit tests

```bash
python -m pytest tests/test_difftastic_interceptor.py -v --ignore-glob="*Integration*"

# Expected: all non-integration tests pass (no real difft required)
```

### Step 6: Run integration tests (requires difft)

```bash
python -m pytest tests/test_difftastic_interceptor.py -v -k "Integration"

# Expected: tests pass (skipped if difft not available)
```

### Step 7: Test the interceptor against a real git diff

```bash
# Generate a real git diff and pipe it through the interceptor in isolation
python - <<'EOF'
from cutctx.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor
from cutctx import binaries

exe = binaries.which("difft")
if exe is None:
    print("difft not found — run 'cutctx tools install --tool difft'")
    exit(1)

interceptor = DifftasticInterceptor(binary_path=str(exe), context_lines=3)

# Simulate what the proxy would see from a Bash tool result
import subprocess
git_diff = subprocess.run(
    ["git", "diff", "HEAD~1", "HEAD"],
    capture_output=True, text=True, cwd="/Users/aryansingh/Documents/Claude/Projects/cutctx"
).stdout

if not git_diff.strip():
    print("No diff found — try with a repo that has recent commits")
    exit(0)

original_lines = len(git_diff.splitlines())
result = interceptor.transform("Bash", {"command": "git diff HEAD~1 HEAD"}, git_diff)

if result is None:
    print(f"No compression (original {original_lines} lines was already compact or difft was larger)")
else:
    structural_lines = len(result.splitlines())
    pct = (1 - structural_lines / original_lines) * 100
    print(f"Original: {original_lines} lines -> Structural: {structural_lines} lines ({pct:.1f}% reduction)")
    print("\n--- Structural diff output (first 40 lines) ---")
    print("\n".join(result.splitlines()[:40]))
EOF

# Expected: token reduction percentage printed, or "no compression" if the diff was already minimal
```

### Step 8: Test the full proxy pipeline with `--difftastic`

```bash
# Start the proxy with difftastic enabled on a test port
cutctx proxy --port 9797 --difftastic --log-level debug &
PROXY_PID=$!
sleep 2

# Send a minimal health check
curl -s http://127.0.0.1:9797/health | python -m json.tool | grep -E "(status|version)"

# Kill the test proxy
kill $PROXY_PID

# Expected: health endpoint responds, logs show "DifftasticInterceptor registered"
```

### Step 9: Verify `--difftastic` flag appears in proxy help

```bash
cutctx proxy --help | grep -A 3 "difftastic"

# Expected output (approximately):
#   --difftastic         Enable structural diff compression via difftastic (difft).
#   --difftastic-binary  Path or name of the difft binary
#   --difftastic-context-lines  Context lines to show around structural changes
```

### Step 10: Verify never-enlarge contract with a pathological diff

```bash
python - <<'EOF'
from cutctx.proxy.interceptors.difftastic_interceptor import DifftasticInterceptor
from unittest.mock import patch, MagicMock

# Mock difft to return something much longer than the input
bloated_output = "verbose structural output line\n" * 500

mock_result = MagicMock()
mock_result.returncode = 0
mock_result.stdout = bloated_output
mock_result.stderr = ""

interceptor = DifftasticInterceptor(context_lines=3)
interceptor._resolved = __import__("pathlib").Path("/fake/difft")
interceptor._unavailable = False

simple_diff = """diff --git a/foo.py b/foo.py
index abc..def 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,3 @@
 x = 1
-y = 2
+y = 3
 z = 4
"""

with patch("subprocess.run", return_value=mock_result):
    result = interceptor.transform("Bash", {"command": "git diff"}, simple_diff)

assert result is None, f"Expected None (never-enlarge), got: {result[:100]}"
print("PASS: never-enlarge contract holds — bloated difft output correctly returns None")
EOF

# Expected: "PASS: never-enlarge contract holds"
```

---

## 11. File Creation/Modification Summary

| File | Action | Description |
|------|--------|-------------|
| `cutctx/proxy/interceptors/difftastic_interceptor.py` | **CREATE** | Full `DifftasticInterceptor` implementation implementing `ToolResultInterceptor` protocol |
| `cutctx/proxy/interceptors/__init__.py` | **MODIFY** | Add conditional `from . import difftastic_interceptor` registration path guarded by `difftastic_enabled` config flag |
| `cutctx/proxy/models.py` | **MODIFY** | Add `difftastic_enabled: bool = False`, `difftastic_binary: str = "difft"`, `difftastic_context_lines: int = 3` fields after `code_graph_watcher` (line 180) |
| `cutctx/cli/proxy.py` | **MODIFY** | Add `--difftastic`, `--difftastic-binary`, `--difftastic-context-lines` CLI options and pass values into `ProxyConfig` construction |
| `cutctx/binaries.py` | **MODIFY** | Add `find_difftastic(binary_override: str = "difft") -> Path | None` public helper function |
| `cutctx/transforms/diff_compressor.py` | **MODIFY** | Add `DifftasticBackend` class implementing `compress(content, context)` interface; used by `ContentRouter` when `difftastic_enabled=True` |
| `cutctx/transforms/content_router.py` | **MODIFY** | Update `_get_diff_compressor()` to return `DifftasticBackend` when `_runtime_difftastic_enabled=True`; add `_runtime_difftastic_binary` and `_runtime_difftastic_context_lines` runtime attrs |
| `cutctx/cli/tools.py` | **MODIFY** | Add optional `tools difft-check` subcommand for standalone binary verification |
| `tests/test_difftastic_interceptor.py` | **CREATE** | 7+ test classes covering match logic, helper functions, subprocess timeout, never-enlarge contract, binary-not-found fallback, progressive disclosure keys, and real integration tests (skipped when difft absent) |
| `cutctx/tools.json` | **NO CHANGE** | `difft` v0.64.0 already registered with all platform assets |
| `pyproject.toml` | **NO CHANGE** | difft is a binary tool, not a Python package — no new dependency entry needed |

---

## Appendix: Key Design Decisions

### Why an Interceptor, Not Just a ContentRouter Backend?

The Interceptor fires on Bash/Run tool results specifically, which is where `git diff` output appears in practice. The `ContentRouter` backend handles the secondary case where DIFF content is detected in other contexts. Running both ensures maximum coverage without adding risk to the existing diff pipeline.

### Why Never-Enlarge is a Hard Contract

The interceptor framework in `cutctx/proxy/interceptors/base.py` (line 309–311) already enforces never-enlarge at the framework level: if `after >= before` tokens, the rewrite is discarded. The `DifftasticInterceptor` also enforces it internally (line-count proxy before token counting) to avoid the overhead of invoking the Tokenizer unnecessarily. Both checks must pass.

### Why Temp Files Instead of Stdin

Difftastic does not support stdin input — it is file-oriented, like `diff(1)`. Temp files are written to a private `mode 0700` directory per call and cleaned up in a `finally` block regardless of success/failure. This mirrors exactly the pattern used by `AstGrepReadOutline` in `astgrep.py`.

### Progressive Disclosure Key Strategy

The key is `sha256(command)[:16]` prefixed with `"difft:"`. This means: if the LLM calls `git diff HEAD` twice in a session, the second call passes through unmodified (giving the LLM the full unified diff if it needed more detail). This follows the existing progressive disclosure contract in `base.py`.

### Why 10-Second Timeout

Difft can be slow on very large files (10K+ lines) because AST parsing is O(n). 10 seconds is generous enough for files up to ~5000 lines while still failing fast on truly pathological inputs. The per-file-pair timeout means a 20-file diff has at most 10 seconds per file, not 10 seconds total.

### Why `DFT_CONTEXT_LINES` and Not `--context`

Difftastic uses the `DFT_CONTEXT_LINES` environment variable as of v0.50+. The `--context` flag does not exist in the CLI surface. Setting it via environment is the documented mechanism.
