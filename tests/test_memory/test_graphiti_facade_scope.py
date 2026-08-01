"""Ungarded public Graphiti facade scope and recovery tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cutctx.memory.easy import Memory as EasyMemory


def _client() -> MagicMock:
    client = MagicMock()
    client.add_episode = AsyncMock(return_value=SimpleNamespace())
    client.search = AsyncMock(return_value=[])
    return client


@pytest.mark.asyncio
async def test_facade_forwards_save_and_search_scope(tmp_path: Path) -> None:
    memory = EasyMemory(backend="graphiti", db_path=tmp_path / "memory.db")
    backend = MagicMock()
    backend.save_memory = AsyncMock(return_value=SimpleNamespace(id="episode"))
    backend.search_memories = AsyncMock(return_value=[])
    memory._backend, memory._initialized = backend, True

    assert (
        await memory.save("fact", user_id="alice", session_id="s1", idempotency_key="k")
        == "episode"
    )
    assert await memory.search("fact", user_id="alice", session_id="s1") == []
    assert backend.save_memory.await_args.kwargs["session_id"] == "s1"
    assert backend.save_memory.await_args.kwargs["idempotency_key"] == "k"
    assert backend.search_memories.await_args.kwargs["session_id"] == "s1"


@pytest.mark.asyncio
async def test_public_retry_reuses_pending_provider_payload_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cutctx.memory.backends.graphiti import (
        GraphitiBackend,
        GraphitiConfig,
        GraphitiWriteRecoveryRequired,
    )

    backend = GraphitiBackend(
        GraphitiConfig(neo4j_password="pw", ledger_path=tmp_path / "ledger.db"), client=_client()
    )
    memory = EasyMemory(backend="graphiti", db_path=tmp_path / "memory.db")
    memory._backend, memory._initialized = backend, True
    monkeypatch.setattr(
        backend._ledger, "activate", lambda _: (_ for _ in ()).throw(ValueError("activation"))
    )
    with pytest.raises(GraphitiWriteRecoveryRequired):
        await memory.save("fact", user_id="alice", session_id="s1", idempotency_key="retry")
    monkeypatch.undo()

    assert await memory.save("fact", user_id="alice", session_id="s1", idempotency_key="retry")
