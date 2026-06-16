"""Filesystem watcher for CutCtx learn auto-mode.

Watches agent log directories for new JSONL files.
When a new session file is detected (>30s old, fully written),
triggers the learn pipeline in the background.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Grace period after file creation before we consider it "closed"
_SETTLE_SECS = 30.0
# Polling interval when watchdog is not available
_POLL_INTERVAL_SECS = 10.0


class SessionWatcher:
    """Watches agent session directories and fires a callback on new sessions."""

    def __init__(
        self,
        directories: list[Path],
        on_new_session: Callable[[Path], Awaitable[None]],
    ) -> None:
        self._dirs = directories
        self._callback = on_new_session
        self._seen: set[Path] = set()
        self._running = False

    async def run(self) -> None:
        """Poll loop -- gracefully degrades if watchdog is not installed."""
        self._running = True
        logger.info("cutctx learn --watch: monitoring %s", self._dirs)
        while self._running:
            await self._scan()
            await asyncio.sleep(_POLL_INTERVAL_SECS)

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False

    async def _scan(self) -> None:
        now = time.time()
        for directory in self._dirs:
            if not directory.exists():
                continue
            for path in directory.rglob("*.jsonl"):
                if path in self._seen:
                    continue
                try:
                    age = now - path.stat().st_mtime
                except OSError:
                    continue
                if age < _SETTLE_SECS:
                    continue  # File still being written
                self._seen.add(path)
                logger.info("New session detected: %s", path)
                try:
                    await self._callback(path)
                except Exception as exc:
                    logger.warning("learn callback error: %s", exc)

    @property
    def seen_count(self) -> int:
        """Number of session files seen so far."""
        return len(self._seen)
