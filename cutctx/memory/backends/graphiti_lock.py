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
        try:
            await asyncio.to_thread(self._lock.acquire)
        except Timeout as exc:
            raise GraphitiOperationLockTimeout(
                "timed out acquiring Graphiti partition lock"
            ) from exc
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await asyncio.to_thread(self._lock.release)
