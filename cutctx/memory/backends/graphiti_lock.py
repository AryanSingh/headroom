"""Cross-process partition locks for Graphiti remote mutations."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from filelock import FileLock, Timeout


class GraphitiOperationLockTimeout(TimeoutError):
    """A partition lock could not be acquired before remote work may begin."""


class PartitionOperationLock:
    """Async wrapper around a process-safe file lock for one opaque partition."""

    def __init__(self, root: Path, partition_id: str, timeout: float) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", partition_id):
            raise ValueError("partition_id must be opaque and path-safe")
        self._directory = Path(root).parent / "graphiti-locks"
        self._directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self._directory, 0o700)
        except OSError:
            pass
        # ``to_thread`` may choose a different worker for release, so lock
        # bookkeeping cannot be thread-local even though the OS lock is process-wide.
        self._lock = FileLock(
            str(self._directory / f"{partition_id}.lock"), timeout=timeout, thread_local=False
        )

    async def __aenter__(self) -> PartitionOperationLock:
        acquire = asyncio.create_task(asyncio.to_thread(self._lock.acquire))
        try:
            await asyncio.shield(acquire)
        except asyncio.CancelledError:
            # A caller can cancel repeatedly, so compensation cannot live in
            # this cancelling task.  This detached cleanup survives until the
            # worker either times out or acquires and releases the file lock.
            asyncio.create_task(self._release_if_late_acquire(acquire))
            raise
        except Timeout as exc:
            raise GraphitiOperationLockTimeout(
                "timed out acquiring Graphiti partition lock"
            ) from exc
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await asyncio.shield(asyncio.to_thread(self._lock.release))

    async def _release_if_late_acquire(self, acquire: asyncio.Task[object]) -> None:
        try:
            await asyncio.shield(acquire)
        except Timeout:
            return
        await asyncio.shield(asyncio.to_thread(self._lock.release))
