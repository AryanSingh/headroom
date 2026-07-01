from __future__ import annotations

import pytest

from cutctx.memory.config import MemoryConfig
from cutctx.memory.core import HierarchicalMemory


class _AsyncClosable:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _SyncClosable:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_hierarchical_memory_close_supports_sync_vector_index_close() -> None:
    store = _AsyncClosable()
    vector_index = _SyncClosable()
    text_index = _AsyncClosable()
    embedder = _AsyncClosable()

    memory = HierarchicalMemory(
        store=store,
        vector_index=vector_index,
        text_index=text_index,
        embedder=embedder,
        cache=None,
        config=MemoryConfig(),
    )

    await memory.close()

    assert store.closed is True
    assert vector_index.closed is True
    assert text_index.closed is True
    assert embedder.closed is True
