"""Difftastic structural diff interceptor.

Replaces verbose unified-diff output (``git diff``, ``diff``) with
AST-aware structural diffs produced by ``difft`` (difftastic).  This gives
the LLM a much more compact view of what *semantically* changed — function
bodies rewritten, signatures altered — rather than hundreds of +/- lines
of generic context.

Interceptor protocol
--------------------
Implements ``ToolResultInterceptor`` (see ``base.py``)::

    name = "difft"

    def matches(tool_name, tool_input, tool_output) -> bool
    def transform(tool_name, tool_input, tool_output) -> str | None
    def progressive_disclosure_key(tool_name, tool_input) -> str | None

Env knobs
---------
CUTCTX_DIFFTASTIC_MIN_CHARS  minimum diff size (chars) before we bother;
                               default 200.
CUTCTX_DIFFTASTIC_TIMEOUT    per-file subprocess timeout in seconds;
                               default 10.
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

import cutctx.binaries as binaries_module

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def _parse_int_env(name: str, default: int) -> int:
    """Parse an integer env var, returning *default* on invalid or missing."""
    val = os.environ.get(name)
    if val is not None:
        try:
            result = int(val)
            if result >= 0:
                return result
        except (ValueError, TypeError):
            logger.warning("Invalid %s=%r, using default %d", name, val, default)
    return default


MIN_CHARS_TO_TRANSFORM = _parse_int_env("CUTCTX_DIFFTASTIC_MIN_CHARS", 200)
SUBPROCESS_TIMEOUT_SECONDS = _parse_int_env("CUTCTX_DIFFTASTIC_TIMEOUT", 10)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_DIFF_GIT_RE = re.compile(r"^diff --git a/(.*) b/(.*)$")
_DIFF_HUNK_RE = re.compile(r"^@@\s+-(\d+),?(\d*)\s+\+(\d+),?(\d*)\s+@@")
_FILE_HEADER_RE = re.compile(r"^(?:---|\+\+\+)\s+(?:a/|b/)?(.+)$")
_HUNK_MARKER_RE = re.compile(r"^@{2,3}\s+")

# Lines that can be stripped entirely (metadata)
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_git_diff(text: str) -> bool:
    """Return True if *text* looks like a git/unified diff."""
    return bool(
        text.startswith("diff --git ")
        or text.startswith("diff --cc ")
        or "--- a/" in text.splitlines()[0]
        if text.splitlines()
        else False
    )


def _split_into_file_diffs(text: str) -> list[tuple[str, str, str]]:
    """Split a multi-file diff into per-file sections.

    Returns a list of ``(path_a, path_b, section_text)`` triples, where
    *path_a* and *path_b* are normalised file paths and *section_text* is
    the contiguous diff block beginning with ``diff --git`` and ending
    before the next such header.
    """
    sections: list[tuple[str, str, str]] = []
    lines = text.splitlines(keepends=True)

    # Locate diff --git headers
    header_indices: list[int] = []
    for i, line in enumerate(lines):
        m = _DIFF_GIT_RE.match(line.strip())
        if m:
            header_indices.append(i)

    if not header_indices:
        # Bare diff (no ``diff --git`` header) — treat as single file.
        # Use ``--- a/`` and ``+++ b/`` to extract paths if present.
        path_a, path_b = _guess_bare_paths(text)
        sections.append((path_a, path_b, text))
        return sections

    for idx in range(len(header_indices)):
        start = header_indices[idx]
        end = header_indices[idx + 1] if idx + 1 < len(header_indices) else len(lines)
        section_text = "".join(lines[start:end])
        m = _DIFF_GIT_RE.match(lines[start].strip())
        if m:
            path_a, path_b = m.group(1), m.group(2)
            sections.append((path_a, path_b, section_text))
        else:
            # Should not happen given our search, but be defensive.
            sections.append(("unknown", "unknown", section_text))

    return sections


def _guess_bare_paths(section_text: str) -> tuple[str, str]:
    """Extract ``--- a/path`` / ``+++ b/path`` from a bare diff."""
    path_a, path_b = "old", "new"
    for line in section_text.splitlines():
        m = re.match(r"^---\s+(?:a/)?(.+)$", line)
        if m:
            path_a = m.group(1).strip()
    for line in section_text.splitlines():
        m = re.match(r"^\+\+\+\s+(?:b/)?(.+)$", line)
        if m:
            path_b = m.group(1).strip()
    return path_a, path_b


def _reconstruct_old_new(section: str) -> tuple[str, str, str]:
    """Rebuild old and new content from a unified or combined diff section.

    Returns ``(old_content, new_content, extension)``.
    Extension is inferred from the file path headers, preferring ``+++ b/``
    (correct for new files where ``--- /dev/null`` has no useful suffix).
    """
    lines = section.splitlines(keepends=True)
    old_lines: list[str] = []
    new_lines: list[str] = []
    old_ext = ""
    new_ext = ""

    # Capture extension from path headers, preferring +++ b/ for new files.
    for line in lines:
        m = re.match(r"^---\s+(?:a/)?(.+)$", line)
        if m:
            p = m.group(1).strip()
            if p != "/dev/null":
                old_ext = Path(p).suffix or ""
        m = re.match(r"^\+\+\+\s+(?:b/)?(.+)$", line)
        if m:
            p = m.group(1).strip()
            if p != "/dev/null":
                new_ext = Path(p).suffix or ""
    ext = new_ext or old_ext or ".txt"

    in_hunk = False
    is_combined = False
    for line in lines:
        stripped = line.rstrip("\n\r")
        if _HUNK_MARKER_RE.match(stripped):
            in_hunk = True
            is_combined = stripped.startswith("@@@")
            continue
        if not in_hunk:
            continue

        if is_combined:
            # Combined diff prefixes (merge-commit format)
            #   "  content"  — context (2-space prefix)
            #   "--content"  — deleted from both parents
            #   "++content"  — added by both parents
            #   "-content"   — deleted from first parent only
            #   "+content"   — added by first parent only
            if stripped.startswith("--"):
                old_lines.append(stripped[2:] + "\n")
            elif stripped.startswith("++"):
                new_lines.append(stripped[2:] + "\n")
            elif stripped.startswith("  "):
                ctx = stripped[2:] + "\n"
                old_lines.append(ctx)
                new_lines.append(ctx)
            elif stripped.startswith("-"):
                old_lines.append(stripped[1:] + "\n")
                if len(new_lines) < len(old_lines):
                    new_lines.append("\n")
            elif stripped.startswith("+"):
                new_lines.append(stripped[1:] + "\n")
                if len(old_lines) < len(new_lines):
                    old_lines.append("\n")
            else:
                # Fallback: treat as context for both
                old_lines.append(stripped + "\n")
                new_lines.append(stripped + "\n")
        else:
            # Unified diff prefixes
            if stripped.startswith("-") and not stripped.startswith("---"):
                old_lines.append(stripped[1:] + "\n")
                if len(new_lines) < len(old_lines):
                    new_lines.append("\n")
            elif stripped.startswith("+") and not stripped.startswith("+++"):
                new_lines.append(stripped[1:] + "\n")
                if len(old_lines) < len(new_lines):
                    old_lines.append("\n")
            elif stripped.startswith(" ") or stripped == "":
                ctx = stripped[1:] + "\n" if stripped.startswith(" ") else "\n"
                old_lines.append(ctx)
                new_lines.append(ctx)
            # else: hunk-marker or metadata — skip

    return "".join(old_lines), "".join(new_lines), ext


def _run_difft(
    exe: str,
    old_content: str,
    new_content: str,
    ext: str,
    context_lines: int = 3,
) -> str | None:
    """Run ``difft`` on two temp files and return its stdout, or None on error.

    Enforces *SUBPROCESS_TIMEOUT_SECONDS* per-file and sets
    ``NO_COLOR=1``, ``TERM=dumb``, ``DFT_CONTEXT_LINES=<context_lines>``
    in the subprocess environment.
    """
    tmp_dir = tempfile.mkdtemp(prefix="cutctx-difft-")
    try:
        old_path = Path(tmp_dir) / f"old{ext}"
        new_path = Path(tmp_dir) / f"new{ext}"
        old_path.write_text(old_content, encoding="utf-8")
        new_path.write_text(new_content, encoding="utf-8")

        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        env["TERM"] = "dumb"
        env["DFT_CONTEXT_LINES"] = str(context_lines)

        completed = subprocess.run(
            [exe, str(old_path), str(new_path)],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
        if completed.returncode not in (0, 1):
            logger.debug(
                "difft returned rc=%d for %s; stderr=%s",
                completed.returncode,
                old_path,
                (completed.stderr or "")[:300],
            )
            return None
        return completed.stdout
    except subprocess.TimeoutExpired:
        logger.debug("difft timed out after %ss for %s", SUBPROCESS_TIMEOUT_SECONDS, ext)
        return None
    except OSError as e:
        logger.debug("difft OSError: %s", e)
        return None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Interceptor class
# ---------------------------------------------------------------------------


class DifftasticInterceptor:
    """ToolResultInterceptor that rewrites git diff output with difftastic.

    Splits unified-diff content into old/new file content, runs ``difft``
    per file, and reassembles the structural output.  Never enlarges the
    content — if difft output is not strictly shorter, the original is kept.
    """

    name = "difft"

    def __init__(
        self,
        binary_path: str | None = None,
        context_lines: int = 3,
    ):
        self._binary_path = binary_path
        self._context_lines = context_lines
        self._exe_resolved: str | None = None
        self._exe_failed: bool = False
        self._version: str | None = None
        self._version_lock: bool = False

    def _get_exe(self) -> str | None:
        """Resolve the ``difft`` binary path, caching result.

        Resolution order:
        1. Explicit *binary_path* passed to ``__init__``.
        2. ``shutil.which("difft")``.
        3. ``cutctx.binaries.resolve("difft")``.
        """
        if self._exe_resolved is not None:
            return self._exe_resolved
        if self._exe_failed:
            return None

        # 1. Explicit path
        if self._binary_path:
            p = Path(self._binary_path)
            if p.is_absolute() and p.exists():
                self._exe_resolved = str(p)
                return self._exe_resolved
            # Treat as a name on PATH
            found = shutil.which(self._binary_path)
            if found:
                self._exe_resolved = found
                return self._exe_resolved

        # 2. PATH
        found = shutil.which("difft")
        if found:
            self._exe_resolved = found
            return self._exe_resolved

        # 3. Binary cache (auto-fetch)
        try:
            resolved = binaries_module.resolve("difft")
            self._exe_resolved = str(resolved)
            return self._exe_resolved
        except (binaries_module.BinaryError, KeyError, OSError) as e:
            logger.debug("difft binary not available: %s", e)
            self._exe_failed = True
            return None

    def matches(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> bool:
        if tool_name not in ("Bash", "Run", "Terminal", "execute_command"):
            return False
        if not tool_output or len(tool_output) < MIN_CHARS_TO_TRANSFORM:
            return False
        return _is_git_diff(tool_output)

    def transform(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
        tool_output: str,
    ) -> str | None:
        exe = self._get_exe()
        if exe is None:
            return None
        result = self.do_transform(exe, tool_output)
        if result is None:
            return None
        # Never enlarge
        if len(result) >= len(tool_output):
            return None
        return result

    def do_transform(self, exe: str, unified_diff: str) -> str | None:
        """Core transform logic: split diff, run difft per file, reassemble."""
        file_diffs = _split_into_file_diffs(unified_diff)
        if not file_diffs:
            return None

        out_parts: list[str] = []
        for path_a, path_b, section in file_diffs:
            old_content, new_content, ext = _reconstruct_old_new(section)
            difft_out = _run_difft(
                exe,
                old_content,
                new_content,
                ext,
                context_lines=self._context_lines,
            )
            if difft_out is None:
                # Fall back to the original section for this file.
                out_parts.append(section)
            else:
                # Tag each file's output so the LLM knows what changed.
                header = f"[cutctx: structural diff via difft for {path_a} -> {path_b}]\n"
                out_parts.append(header + difft_out.strip() + "\n")

        if not out_parts:
            return None
        return "".join(out_parts)

    def _get_difft_version(self) -> str:
        """Return the cached ``difft --version`` string."""
        if self._version_lock:
            return self._version or "unknown"
        self._version_lock = True
        exe = self._get_exe()
        if exe is None:
            self._version = None
            return "unknown"
        try:
            r = subprocess.run(
                [exe, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self._version = (r.stdout or r.stderr or "").strip() or "unknown"
        except (OSError, subprocess.TimeoutExpired):
            self._version = None
        return self._version or "unknown"

    def progressive_disclosure_key(
        self,
        tool_name: str | None,
        tool_input: dict[str, Any],
    ) -> str | None:
        """Return a stable key based on the command hash for dedup."""
        # Check for explicit command key first; empty string is valid.
        command = tool_input.get("command")
        if command is None:
            command = tool_input.get("cmd")
        if command is None:
            return None
        return hashlib.sha256(command.encode()).hexdigest()
