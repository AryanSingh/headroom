"""Simple file-based episodic memory store.

Stores session insights as Markdown files in ``~/.headroom/memories/``.
Each project gets its own file keyed by a SHA-256 hash of the project path.

Design:
    - User-editable: plain Markdown, no binary formats
    - Append-only: new memories are appended to the file
    - Thread-safe: file operations use atomic writes
    - Zero dependencies: only stdlib (pathlib, hashlib, json)

Usage:
    from headroom.memory.store import EpisodicMemoryStore

    store = EpisodicMemoryStore()
    store.save_memory(project_hash="abc123", content="## Session 1\\n- User prefers Python")
    memories = store.load_memories(project_hash="abc123")
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default storage directory
_DEFAULT_MEMORY_DIR = "~/.headroom/memories"


class EpisodicMemoryStore:
    """File-based episodic memory store using Markdown files.

    Each project gets a file named ``{project_hash}.md`` under the
    memory directory. Memories are appended as Markdown sections with
    timestamps.

    The store is safe for concurrent reads but writes should be
    serialized per-file (FastAPI runs on a single event loop, so
    this is naturally satisfied).
    """

    def __init__(self, memory_dir: str | Path | None = None) -> None:
        if memory_dir is None:
            memory_dir = os.environ.get("HEADROOM_EPISODIC_MEMORY_DIR", _DEFAULT_MEMORY_DIR)
        self._dir = Path(memory_dir).expanduser()
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def memory_dir(self) -> Path:
        return self._dir

    def _file_for(self, project_hash: str) -> Path:
        """Return the Markdown file path for a project hash."""
        # Sanitize hash to prevent path traversal
        safe_hash = hashlib.sha256(project_hash.encode()).hexdigest()[:64]
        return self._dir / f"{safe_hash}.md"

    def save_memory(self, project_hash: str, content: str) -> Path:
        """Append a memory section to the project's Markdown file.

        Args:
            project_hash: Hash identifying the project/workspace.
            content: Markdown content to append. Should include its own
                heading (e.g. "## Session Insights").

        Returns:
            Path to the written file.
        """
        if not content or not content.strip():
            return self._file_for(project_hash)

        filepath = self._file_for(project_hash)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        # Build the entry block
        entry = f"\n\n---\n### {timestamp} (UTC)\n\n{content.strip()}\n"

        # Atomic append: write to temp file, then rename
        # For append-only, we read + write (simple, correct for small files)
        existing = ""
        if filepath.exists():
            existing = filepath.read_text(encoding="utf-8")

        new_content = existing + entry

        # Atomic write via temp file + rename
        # Use SHA-256 of the hash as prefix to avoid path traversal via raw input
        safe_prefix = hashlib.sha256(project_hash.encode()).hexdigest()[:8]
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._dir), suffix=".tmp", prefix=f".{safe_prefix}_"
        )
        try:
            os.write(fd, new_content.encode("utf-8"))
            os.close(fd)
            os.replace(tmp_path, str(filepath))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        logger.info(
            "EpisodicMemory: saved %d bytes to %s",
            len(entry),
            filepath.name,
        )
        return filepath

    def load_memories(self, project_hash: str) -> str:
        """Load all stored memories for a project.

        Args:
            project_hash: Hash identifying the project/workspace.

        Returns:
            Full Markdown content, or empty string if no memories exist.
        """
        filepath = self._file_for(project_hash)
        if not filepath.exists():
            return ""

        try:
            content = filepath.read_text(encoding="utf-8")
            return content.strip()
        except Exception as e:
            logger.warning(
                "EpisodicMemory: failed to read %s: %s",
                filepath.name,
                e,
            )
            return ""

    def has_memories(self, project_hash: str) -> bool:
        """Check if any memories exist for a project."""
        filepath = self._file_for(project_hash)
        return filepath.exists() and filepath.stat().st_size > 0

    def clear_memories(self, project_hash: str) -> bool:
        """Delete all memories for a project.

        Returns:
            True if memories were deleted, False if none existed.
        """
        filepath = self._file_for(project_hash)
        if filepath.exists():
            filepath.unlink()
            logger.info("EpisodicMemory: cleared %s", filepath.name)
            return True
        return False

    def list_projects(self) -> list[str]:
        """List all project hashes that have stored memories."""
        return [f.stem for f in self._dir.glob("*.md") if f.stat().st_size > 0]

    def get_memory_stats(self, project_hash: str) -> dict[str, Any]:
        """Get stats about stored memories for a project.

        Returns:
            Dict with keys: exists, size_bytes, section_count.
        """
        filepath = self._file_for(project_hash)
        if not filepath.exists():
            return {"exists": False, "size_bytes": 0, "section_count": 0}

        stat = filepath.stat()
        content = filepath.read_text(encoding="utf-8")
        # Count sections by "---" delimiters
        sections = content.count("\n---\n") + (1 if content.strip() else 0)

        return {
            "exists": True,
            "size_bytes": stat.st_size,
            "section_count": sections,
        }


def compute_project_hash(project_path: str) -> str:
    """Compute a stable hash for a project path.

    Uses SHA-256 truncated to 16 hex chars (64 bits) — enough for
    collision avoidance in a single-user context.

    Args:
        project_path: Absolute path to the project root.

    Returns:
        16-char hex string.
    """
    # Normalize: resolve symlinks, strip trailing slash
    normalized = os.path.normpath(os.path.abspath(project_path))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
