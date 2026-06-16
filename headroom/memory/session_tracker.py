"""Episodic memory session tracker for the proxy.

Tracks active sessions by project hash, detects idle sessions
(5-minute timeout), and triggers asynchronous memory extraction.

Usage:
    tracker = EpisodicSessionTracker(store, extractor)
    tracker.on_request(project_path="...", messages=[...])
    # After 5 min idle, extraction runs automatically
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from headroom.memory.extractor import extract_session_insights, format_memory_block
from headroom.memory.store import EpisodicMemoryStore, compute_project_hash

logger = logging.getLogger(__name__)

# Default idle timeout before triggering extraction (5 minutes)
DEFAULT_IDLE_TIMEOUT_SECONDS = 300

# Maximum transcript size to send for extraction (20KB)
MAX_TRANSCRIPT_CHARS = 20000


class EpisodicSessionTracker:
    """Tracks active sessions and triggers memory extraction on idle.

    The tracker maintains a dict of project_hash → {messages, last_active}.
    When a project hasn't seen a request for ``idle_timeout_seconds``,
    the tracker fires an async extraction task and clears the buffer.

    Thread safety: This class is designed to run on a single asyncio
    event loop (FastAPI). No locking needed.
    """

    def __init__(
        self,
        store: EpisodicMemoryStore,
        idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT_SECONDS,
        *,
        enabled: bool = True,
        extraction_model: str = "claude-3-haiku-20240307",
    ) -> None:
        self._store = store
        self._idle_timeout = idle_timeout_seconds
        self._enabled = enabled
        self._extraction_model = extraction_model
        # project_hash → {messages: list, last_active: float, task: asyncio.Task | None}
        self._sessions: dict[str, dict[str, Any]] = {}
        # Background task that checks for idle sessions
        self._sweep_task: asyncio.Task | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start_sweeper(self) -> None:
        """Start the background idle-session sweep loop."""
        if not self._enabled:
            return
        if self._sweep_task is not None and not self._sweep_task.done():
            return
        self._sweep_task = asyncio.create_task(self._sweep_loop())

    def stop_sweeper(self) -> None:
        """Stop the background sweep loop."""
        if self._sweep_task is not None:
            self._sweep_task.cancel()
            self._sweep_task = None

    async def _sweep_loop(self) -> None:
        """Periodically check for idle sessions and trigger extraction."""
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute
                await self._check_idle_sessions()
        except asyncio.CancelledError:
            pass

    async def _check_idle_sessions(self) -> None:
        """Check all tracked sessions for idle timeout."""
        now = time.time()
        idle_hashes = [
            h
            for h, session in self._sessions.items()
            if now - session["last_active"] > self._idle_timeout
            and session["messages"]
            and not session.get("extracting")
        ]

        for project_hash in idle_hashes:
            session = self._sessions[project_hash]
            messages = session["messages"]
            session["messages"] = []
            session["extracting"] = True

            logger.info(
                "EpisodicTracker: session idle for %s, extracting insights (%d messages)",
                project_hash[:8],
                len(messages),
            )

            # Fire extraction in background
            asyncio.create_task(self._extract_and_store(project_hash, messages))

    async def _extract_and_store(self, project_hash: str, messages: list[dict[str, Any]]) -> None:
        """Extract insights and store them."""
        try:
            insights = await extract_session_insights(messages, model=self._extraction_model)
            if insights:
                self._store.save_memory(project_hash, insights)
                logger.info(
                    "EpisodicTracker: stored insights for %s (%d chars)",
                    project_hash[:8],
                    len(insights),
                )
        except Exception as e:
            logger.warning(
                "EpisodicTracker: extraction failed for %s: %s",
                project_hash[:8],
                e,
            )
        finally:
            session = self._sessions.get(project_hash)
            if session:
                session["extracting"] = False

    def on_request(
        self,
        project_path: str,
        messages: list[dict[str, Any]],
    ) -> str:
        """Record a request for a project and return the project hash.

        Appends messages to the session buffer for later extraction.

        Args:
            project_path: Path to the project root.
            messages: The messages array from the request.

        Returns:
            The computed project hash.
        """
        if not self._enabled:
            return compute_project_hash(project_path)

        project_hash = compute_project_hash(project_path)

        if project_hash not in self._sessions:
            self._sessions[project_hash] = {
                "messages": [],
                "last_active": time.time(),
                "extracting": False,
            }

        session = self._sessions[project_hash]
        session["last_active"] = time.time()

        # Append messages (bounded to prevent memory growth)
        existing_chars = sum(len(str(m.get("content", ""))) for m in session["messages"])
        for msg in messages:
            content = str(msg.get("content", ""))
            if existing_chars + len(content) > MAX_TRANSCRIPT_CHARS:
                break
            session["messages"].append(msg)
            existing_chars += len(content)

        return project_hash

    def load_episodic_memories(self, project_path: str) -> str:
        """Load stored episodic memories for a project.

        Returns a formatted memory block ready for injection, or empty
        string if no memories exist.
        """
        if not self._enabled:
            return ""

        project_hash = compute_project_hash(project_path)
        memories = self._store.load_memories(project_hash)
        if not memories:
            return ""

        return format_memory_block(memories, project_path=project_path)

    def get_stats(self) -> dict[str, Any]:
        """Get tracker stats for the dashboard."""
        return {
            "active_sessions": len([s for s in self._sessions.values() if s["messages"]]),
            "total_tracked": len(self._sessions),
            "enabled": self._enabled,
        }
