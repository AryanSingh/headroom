"""Cross-process Graphiti partition lock tests."""

import asyncio
import time
from multiprocessing import Event, Process
from pathlib import Path

import pytest

from cutctx.memory.backends.graphiti_lock import (
    GraphitiOperationLockTimeout,
    PartitionOperationLock,
)


def _holder(root: str, partition: str, entered: Event, release: Event) -> None:
    async def run() -> None:
        async with PartitionOperationLock(Path(root), partition, timeout=2):
            entered.set()
            await asyncio.to_thread(release.wait, 10)

    asyncio.run(run())


def test_second_worker_times_out_without_entering_while_holder_lives(tmp_path: Path) -> None:
    entered, release = Event(), Event()
    process = Process(target=_holder, args=(str(tmp_path), "cutctx_opaque", entered, release))
    process.start()
    try:
        assert entered.wait(5)
        did_work = False

        async def contender() -> None:
            nonlocal did_work
            with pytest.raises(GraphitiOperationLockTimeout):
                async with PartitionOperationLock(tmp_path, "cutctx_opaque", timeout=0.05):
                    did_work = True

        asyncio.run(contender())
        assert not did_work
    finally:
        release.set()
        process.join(5)


def test_normal_release_wakes_waiter(tmp_path: Path) -> None:
    async def run() -> None:
        async with PartitionOperationLock(tmp_path, "cutctx_opaque", timeout=1):
            waiter = asyncio.create_task(_acquire(tmp_path))
            await asyncio.sleep(0.05)
            assert not waiter.done()
        assert await waiter

    asyncio.run(run())


async def _acquire(root: Path) -> bool:
    async with PartitionOperationLock(root, "cutctx_opaque", timeout=2):
        return True


def test_terminating_holder_releases_os_lock(tmp_path: Path) -> None:
    entered, release = Event(), Event()
    process = Process(target=_holder, args=(str(tmp_path), "cutctx_opaque", entered, release))
    process.start()
    assert entered.wait(5)
    process.terminate()
    process.join(5)
    assert process.exitcode is not None
    assert asyncio.run(_acquire(tmp_path))
