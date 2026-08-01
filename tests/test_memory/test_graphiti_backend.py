"""TDD tests for Graphiti OSS memory backend adapter.

Unit tests mock graphiti_core — no Neo4j required in CI.
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cutctx.memory.models import Memory


def test_scope_partition_is_stable_opaque_and_graphiti_safe() -> None:
    from cutctx.memory.backends.graphiti import _scope_partition

    first = _scope_partition("alice@example.com", "session/one")
    assert first == _scope_partition("alice@example.com", "session/one")
    assert first != _scope_partition("alice@example.com", "session/two")
    assert "alice" not in first and "session" not in first
    assert re.fullmatch(r"cutctx_[a-f0-9]{32}", first)


@pytest.mark.parametrize("version", ["0.21.0", "0.22.9"])
def test_graphiti_version_accepts_supported_releases(version: str) -> None:
    from cutctx.memory.backends.graphiti import _validate_graphiti_version

    _validate_graphiti_version(version)


@pytest.mark.parametrize("version", ["0.20.9", "0.23.0", "0.29.3", "garbage"])
def test_graphiti_version_rejects_unsupported_releases(version: str) -> None:
    from cutctx.memory.backends.graphiti import _validate_graphiti_version

    with pytest.raises(RuntimeError, match=r"graphiti-core>=0\.21,<0\.23"):
        _validate_graphiti_version(version)


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    return tmp_path / "graphiti_ledger.json"


def _cfg(ledger_path: Path, **kwargs: Any) -> Any:
    from cutctx.memory.backends.graphiti import GraphitiConfig

    kwargs.setdefault("neo4j_password", "secret")
    kwargs.setdefault("ledger_path", ledger_path)
    return GraphitiConfig(**kwargs)


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.add_episode = AsyncMock(return_value=SimpleNamespace(episode=SimpleNamespace(uuid="ep")))
    client.search = AsyncMock(return_value=[])
    client.close = AsyncMock()
    client.remove_episode = AsyncMock()
    client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
    return client


@pytest.fixture(autouse=True)
def _in_process_partition_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep backend tests independent of Graphiti's optional filelock extra."""

    class Lock:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        async def __aenter__(self) -> Lock:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

    monkeypatch.setitem(
        sys.modules,
        "cutctx.memory.backends.graphiti_lock",
        SimpleNamespace(PartitionOperationLock=Lock),
    )


class TestGraphitiImportGuard:
    def test_missing_graphiti_core_raises_clear_importerror(self) -> None:
        from cutctx.memory.backends import graphiti as graphiti_mod

        with patch.dict("sys.modules", {"graphiti_core": None, "graphiti_core.nodes": None}):
            with pytest.raises(ImportError, match="cutctx-ai\\[graphiti\\]"):
                graphiti_mod._import_graphiti()


class TestGraphitiSaveMapping:
    @pytest.mark.asyncio
    async def test_save_recovery_reuses_only_the_matching_pending_write(
        self, ledger_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cutctx.memory.backends.graphiti import (
            GraphitiBackend,
            GraphitiIdempotencyConflict,
            GraphitiWriteRecoveryRequired,
        )

        mock_client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        memory = Memory(id="recover-me", content="durable", user_id="alice", session_id="s1")
        original_activate = backend._ledger.activate
        monkeypatch.setattr(
            backend._ledger, "activate", lambda _: (_ for _ in ()).throw(ValueError())
        )

        with pytest.raises(GraphitiWriteRecoveryRequired) as exc:
            await backend.save(memory, idempotency_key="retry-1")
        assert backend._ledger.get("recover-me").state == "write_pending"  # type: ignore[union-attr]

        monkeypatch.setattr(backend._ledger, "activate", original_activate)
        assert (
            await backend.save(memory, idempotency_key=exc.value.idempotency_key)
        ).id == "recover-me"
        assert backend._ledger.get("recover-me").state == "active"  # type: ignore[union-attr]
        with pytest.raises(GraphitiIdempotencyConflict):
            await backend.save(
                Memory(id="wrong-scope", content="durable", user_id="alice", session_id="s2"),
                idempotency_key="retry-1",
            )
        with pytest.raises(GraphitiIdempotencyConflict):
            await backend.save(
                Memory(id="wrong-payload", content="changed", user_id="alice", session_id="s1"),
                idempotency_key="retry-1",
            )

    @pytest.mark.asyncio
    async def test_independent_identical_saves_get_distinct_episode_ids(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        backend = GraphitiBackend(_cfg(ledger_path), client=_mock_client())
        first = await backend.save_memory(content="same", user_id="alice", session_id="s1")
        second = await backend.save_memory(content="same", user_id="alice", session_id="s1")
        assert first.id != second.id

    @pytest.mark.asyncio
    async def test_save_maps_memory_to_add_episode(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, _scope_partition

        mock_client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)

        now = datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc)
        memory = Memory(
            id="mem-1",
            content="Alice works on backend",
            user_id="alice",
            valid_from=now,
            metadata={"source_description": "chat"},
        )

        result = await backend.save(memory)

        mock_client.add_episode.assert_awaited_once()
        kwargs = mock_client.add_episode.await_args.kwargs
        assert kwargs["episode_body"] == "Alice works on backend"
        assert kwargs["group_id"] == _scope_partition("alice", None)
        assert kwargs["uuid"] == "mem-1"
        assert kwargs["reference_time"] == now
        assert result.id == "mem-1"

    @pytest.mark.asyncio
    async def test_save_memory_stores_all_facts(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        mock_client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        saved = await backend.save_memory(
            content="ignored when facts present",
            user_id="bob",
            importance=0.8,
            facts=["fact one", "fact two"],
        )
        assert mock_client.add_episode.await_count == 2
        bodies = [c.kwargs["episode_body"] for c in mock_client.add_episode.await_args_list]
        assert bodies == ["fact one", "fact two"]
        assert saved.content == "fact one"


class TestGraphitiSearchMapping:
    @pytest.mark.asyncio
    async def test_failed_delete_stays_search_visible(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiDeletionError

        client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="retryable", content="fact", user_id="alice"))
        client.remove_episode.side_effect = RuntimeError("remote down")
        with pytest.raises(GraphitiDeletionError):
            await backend.delete_memory("retryable")
        client.search = AsyncMock(
            return_value=[SimpleNamespace(uuid="edge", fact="fact", episodes=["retryable"])]
        )
        assert [item.memory.content for item in await backend.search_memories("fact", "alice")] == [
            "fact"
        ]

    @pytest.mark.asyncio
    async def test_historical_and_include_superseded_search_admit_superseded_provenance(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        client = _mock_client()
        edge = SimpleNamespace(uuid="edge", fact="old", episodes=["old"], valid_at=None)
        client.search = AsyncMock(return_value=[edge])
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(
            Memory(
                id="old",
                content="old",
                user_id="alice",
                valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
        )
        await backend.supersede("old", Memory(id="new", content="new", user_id="alice"))
        assert await backend.search_memories("old", "alice") == []
        assert len(await backend.search_memories("old", "alice", include_superseded=True)) == 1
        assert (
            len(
                await backend.search_memories(
                    "old", "alice", valid_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
                )
            )
            == 1
        )

    @pytest.mark.asyncio
    async def test_historical_search_selects_old_parent_from_mixed_current_edge(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        client = _mock_client()
        client.search = AsyncMock(
            return_value=[SimpleNamespace(uuid="edge", fact="fact", episodes=["old", "new"])]
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(
            Memory(
                id="old",
                content="old",
                user_id="alice",
                valid_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
        )
        await backend.supersede(
            "old",
            Memory(
                id="new",
                content="new",
                user_id="alice",
                valid_from=datetime(2022, 1, 1, tzinfo=timezone.utc),
            ),
            supersede_time=datetime(2022, 1, 1, tzinfo=timezone.utc),
        )

        results = await backend.search_memories(
            "fact", "alice", valid_at=datetime(2021, 1, 1, tzinfo=timezone.utc)
        )

        assert results[0].memory.metadata["graphiti_episode_uuids"] == ["old"]

    @pytest.mark.asyncio
    async def test_include_superseded_preserves_upstream_mixed_parent_order(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        client = _mock_client()
        client.search = AsyncMock(
            return_value=[SimpleNamespace(uuid="edge", fact="fact", episodes=["old", "new"])]
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="old", content="old", user_id="alice"))
        await backend.supersede("old", Memory(id="new", content="new", user_id="alice"))

        result = (await backend.search_memories("fact", "alice", include_superseded=True))[0].memory

        assert result.id == "old"
        assert result.metadata["graphiti_episode_uuids"] == ["old", "new"]

    @pytest.mark.asyncio
    async def test_search_enforces_session_partition(self, ledger_path: Path) -> None:
        """Search admits only episodes owned by the requested session."""
        from cutctx.memory.backends.graphiti import (
            GraphitiBackend,
            _scope_partition,
        )
        from cutctx.memory.backends.graphiti_ledger import SQLiteEpisodeLedger

        ledger = SQLiteEpisodeLedger(ledger_path)
        s1_partition = _scope_partition("alice", "s1")
        s2_partition = _scope_partition("alice", "s2")
        for episode_id, session_id, partition in (
            ("ep-s1", "s1", s1_partition),
            ("ep-s2", "s2", s2_partition),
        ):
            ledger.reserve_write(
                episode_id=episode_id,
                user_key="alice",
                session_key=session_id,
                partition_id=partition,
                idempotency_key=episode_id,
                payload=episode_id,
            )
            ledger.activate(episode_id)

        edges = [
            SimpleNamespace(uuid="edge-s1", fact="s1 fact", episodes=["ep-s1"], score=0.9),
            SimpleNamespace(uuid="edge-s2", fact="s2 fact", episodes=["ep-s2"], score=0.8),
        ]
        mock_client = _mock_client()
        mock_client.search = AsyncMock(return_value=edges)
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)

        results = await backend.search_memories(query="fact", user_id="alice", session_id="s1")

        assert [result.memory.content for result in results] == ["s1 fact"]
        assert mock_client.search.await_args.kwargs["group_ids"] == [s1_partition]

    @pytest.mark.asyncio
    async def test_search_maps_entity_edges_to_memories(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, _scope_partition
        from cutctx.memory.backends.graphiti_ledger import SQLiteEpisodeLedger

        ledger = SQLiteEpisodeLedger(ledger_path)
        for episode_id in ("ep-1", "ep-2"):
            ledger.reserve_write(
                episode_id=episode_id,
                user_key="alice",
                session_key=None,
                partition_id=_scope_partition("alice", None),
                idempotency_key=episode_id,
                payload=episode_id,
            )
            ledger.activate(episode_id)

        edge = SimpleNamespace(
            uuid="edge-1",
            fact="Alice works on backend",
            episodes=["ep-1", "ep-2"],
            valid_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            invalid_at=None,
            score=0.91,
        )
        mock_client = _mock_client()
        mock_client.search = AsyncMock(return_value=[edge])
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        results = await backend.search_memories(query="Where does Alice work?", user_id="alice")

        assert len(results) == 1
        mem = results[0].memory
        assert mem.content == "Alice works on backend"
        assert mem.metadata["graphiti_edge_uuid"] == "edge-1"
        assert results[0].score == pytest.approx(0.91)

    @pytest.mark.asyncio
    async def test_search_user_wide_uses_only_recorded_user_partitions(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, _scope_partition
        from cutctx.memory.backends.graphiti_ledger import SQLiteEpisodeLedger

        ledger = SQLiteEpisodeLedger(ledger_path)
        for episode_id, user_id, session_id in (
            ("s1", "alice", "s1"),
            ("s2", "alice", "s2"),
            ("bob", "bob", "s1"),
        ):
            ledger.reserve_write(
                episode_id=episode_id,
                user_key=user_id,
                session_key=session_id,
                partition_id=_scope_partition(user_id, session_id),
                idempotency_key=episode_id,
                payload=episode_id,
            )
            ledger.activate(episode_id)
        mock_client = _mock_client()
        mock_client.search = AsyncMock(
            return_value=[
                SimpleNamespace(uuid="e1", fact="one", episodes=["s1"]),
                SimpleNamespace(uuid="e2", fact="two", episodes=["s2"]),
                SimpleNamespace(uuid="e3", fact="three", episodes=["bob"]),
            ]
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)

        results = await backend.search_memories(query="q", user_id="alice")

        assert [result.memory.content for result in results] == ["one", "two"]
        assert set(mock_client.search.await_args.kwargs["group_ids"]) == {
            _scope_partition("alice", "s1"),
            _scope_partition("alice", "s2"),
        }

    @pytest.mark.asyncio
    async def test_unknown_session_avoids_graphiti_search(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        mock_client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        assert await backend.search_memories(query="q", user_id="alice", session_id="missing") == []
        mock_client.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_search_retains_only_active_parent_provenance(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, _scope_partition
        from cutctx.memory.backends.graphiti_ledger import SQLiteEpisodeLedger

        ledger = SQLiteEpisodeLedger(ledger_path)
        partition = _scope_partition("alice", "s1")
        for episode_id in ("closed", "active", "replacement"):
            ledger.reserve_write(
                episode_id=episode_id,
                user_key="alice",
                session_key="s1",
                partition_id=partition,
                idempotency_key=episode_id,
                payload=episode_id,
            )
        ledger.activate("closed")
        ledger.activate("active")
        ledger.record_replacement("closed", "replacement")
        mock_client = _mock_client()
        mock_client.search = AsyncMock(
            return_value=[
                SimpleNamespace(
                    uuid="edge", fact="shared", episodes=["closed", "active"], score=1.0
                )
            ]
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)

        results = await backend.search_memories(query="shared", user_id="alice", session_id="s1")

        assert results[0].memory.metadata["graphiti_episode_uuids"] == ["active"]

    @pytest.mark.asyncio
    async def test_rank_fallback_score_when_edge_has_no_score(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, _scope_partition
        from cutctx.memory.backends.graphiti_ledger import SQLiteEpisodeLedger

        ledger = SQLiteEpisodeLedger(ledger_path)
        for episode_id in ("a", "b"):
            ledger.reserve_write(
                episode_id=episode_id,
                user_key="u",
                session_key=None,
                partition_id=_scope_partition("u", None),
                idempotency_key=episode_id,
                payload=episode_id,
            )
            ledger.activate(episode_id)

        edges = [
            SimpleNamespace(
                uuid="e0",
                fact="first",
                episodes=["a"],
                valid_at=None,
                invalid_at=None,
            ),
            SimpleNamespace(
                uuid="e1",
                fact="second",
                episodes=["b"],
                valid_at=None,
                invalid_at=None,
            ),
        ]
        mock_client = _mock_client()
        mock_client.search = AsyncMock(return_value=edges)
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        results = await backend.search_memories(query="q", user_id="u")
        assert results[0].score > results[1].score


class TestGraphitiSupersedeAndLedger:
    @pytest.mark.asyncio
    async def test_supersede_retry_reuses_reservation_after_finalization_failure(
        self, ledger_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiWriteRecoveryRequired

        client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="old", content="old", user_id="alice"))
        original = backend._ledger.record_replacement
        calls = 0

        def fail_once(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("finalize")
            return original(*args, **kwargs)

        monkeypatch.setattr(backend._ledger, "record_replacement", fail_once)
        replacement = Memory(id="new", content="new", user_id="alice")
        with pytest.raises(GraphitiWriteRecoveryRequired) as exc:
            await backend.supersede("old", replacement)
        assert exc.value.idempotency_key != "supersede"
        assert backend._ledger.get("new").state == "write_pending"  # type: ignore[union-attr]
        await backend.supersede("old", replacement)
        assert backend._ledger.get("old").state == "superseded"  # type: ignore[union-attr]
        assert backend._ledger.get("new").state == "active"  # type: ignore[union-attr]
        assert client.add_episode.await_args_list[-1].kwargs["uuid"] == "new"

    @pytest.mark.asyncio
    async def test_failed_replacement_keeps_old_episode_active(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="old", content="old", user_id="alice"))
        client.add_episode.side_effect = RuntimeError("graph down")

        with pytest.raises(RuntimeError, match="graph down"):
            await backend.supersede("old", Memory(id="new", content="new", user_id="alice"))

        assert backend._ledger.get("old").state == "active"  # type: ignore[union-attr]
        assert backend._ledger.get("new").state == "write_pending"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_supersede_persists_across_backend_recreate(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        edge = SimpleNamespace(
            uuid="edge-old",
            fact="Alice works on frontend",
            episodes=["ep-old"],
            valid_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            invalid_at=None,
            score=0.9,
        )
        mock_client = _mock_client()
        mock_client.search = AsyncMock(return_value=[edge])

        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        await backend.save(Memory(id="ep-old", content="old", user_id="alice"))
        await backend.supersede(
            "ep-old",
            Memory(id="ep-new", content="Alice works on backend", user_id="alice"),
        )
        assert ledger_path.exists()

        # New process / backend instance sharing ledger path
        backend2 = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        hidden = await backend2.search_memories(
            query="Alice", user_id="alice", include_superseded=False
        )
        assert hidden == []

    @pytest.mark.asyncio
    async def test_multi_parent_edge_survives_partial_supersede(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        edge = SimpleNamespace(
            uuid="edge-1",
            fact="Alice has penicillin allergy",
            episodes=["ehr", "chat"],
            valid_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            invalid_at=None,
            score=0.9,
        )
        mock_client = _mock_client()
        mock_client.search = AsyncMock(return_value=[edge])
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        await backend.save(Memory(id="chat", content="chat", user_id="alice"))
        await backend.save(Memory(id="ehr", content="ehr", user_id="alice"))
        await backend.supersede(
            "chat",
            Memory(id="ep-new", content="updated", user_id="alice"),
        )
        # Still supported by ehr → remains visible
        results = await backend.search_memories(query="allergy", user_id="alice")
        assert len(results) == 1
        assert results[0].memory.valid_until is None

        await backend.supersede(
            "ehr",
            Memory(id="ep-new2", content="updated2", user_id="alice"),
        )
        hidden = await backend.search_memories(query="allergy", user_id="alice")
        assert hidden == []

    @pytest.mark.asyncio
    async def test_delete_memory_hides_from_search(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        edge = SimpleNamespace(
            uuid="edge-1",
            fact="secret fact",
            episodes=["ep-del"],
            valid_at=None,
            invalid_at=None,
            score=1.0,
        )
        mock_client = _mock_client()
        mock_client.search = AsyncMock(return_value=[edge])
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        await backend.save(Memory(id="ep-del", content="secret", user_id="u"))
        assert await backend.delete_memory("ep-del") is True
        assert await backend.search_memories(query="secret", user_id="u") == []

    @pytest.mark.asyncio
    async def test_clear_user_removes_tracked_episodes(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        mock_client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=mock_client)
        await backend.save_memory(content="a", user_id="alice")
        await backend.save_memory(content="b", user_id="alice")
        n = await backend.clear_user("alice")
        assert n == 2


class TestGraphitiTruthfulDeletion:
    @staticmethod
    async def _save(backend: Any, *episodes: str, user: str = "alice") -> None:
        for episode_id in episodes:
            await backend.save(Memory(id=episode_id, content=episode_id, user_id=user))

    @pytest.mark.asyncio
    async def test_delete_refuses_origin_with_active_external_supporter(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiUnsafeDeletionError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=(
                [],
                [
                    SimpleNamespace(episodes=["origin", "supporter"]),
                ],
            )
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "origin", "supporter")

        with pytest.raises(GraphitiUnsafeDeletionError):
            await backend.delete_memory("origin")
        client.remove_episode.assert_not_awaited()
        assert backend._ledger.get("origin").state == "active"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_delete_confirmed_remote_failure_is_retained_for_retry(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiDeletionError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
        client.remove_episode.side_effect = RuntimeError("remote down")
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "episode")

        with pytest.raises(GraphitiDeletionError, match="remote down"):
            await backend.delete_memory("episode")
        record = backend._ledger.get("episode")
        assert record is not None and record.state == "delete_pending"
        assert record.last_error == "remote down"

    @pytest.mark.asyncio
    async def test_delete_finalization_failure_retries_not_found_as_confirmed(
        self, ledger_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiDeletionError

        class NodeNotFoundError(Exception):
            pass

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
        client.remove_episode.side_effect = [None, NodeNotFoundError("gone")]
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "episode")
        original = backend._ledger.mark_deleted
        monkeypatch.setattr(
            backend._ledger,
            "mark_deleted",
            lambda _: (_ for _ in ()).throw(RuntimeError("disk full")),
        )

        with pytest.raises(GraphitiDeletionError, match="disk full"):
            await backend.delete_memory("episode")
        monkeypatch.setattr(backend._ledger, "mark_deleted", original)

        assert await backend.delete_memory("episode") is True
        assert backend._ledger.get("episode").state == "deleted"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_clear_deletes_supporter_before_shared_origin(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=(
                [],
                [
                    SimpleNamespace(episodes=["origin", "supporter"]),
                ],
            )
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "origin", "supporter")

        assert await backend.clear_user("alice") == 2
        assert [call.args[0] for call in client.remove_episode.await_args_list] == [
            "supporter",
            "origin",
        ]

    @pytest.mark.asyncio
    async def test_delete_unknown_or_already_deleted_returns_false(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        assert await backend.delete_memory("unknown") is False
        await self._save(backend, "episode")
        assert await backend.delete_memory("episode") is True
        assert await backend.delete_memory("episode") is False

    @pytest.mark.asyncio
    async def test_clear_user_reports_partial_failures_after_safe_deletions(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiClearError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
        client.remove_episode.side_effect = lambda episode: (
            (_ for _ in ()).throw(RuntimeError("independent failed"))
            if episode == "independent"
            else None
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "safe", "independent")

        with pytest.raises(GraphitiClearError) as exc:
            await backend.clear_user("alice")
        assert exc.value.confirmed == 1
        assert exc.value.failed == 1
        assert backend._ledger.get("safe").state == "deleted"  # type: ignore[union-attr]
        assert backend._ledger.get("independent").state == "delete_pending"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_clear_defers_origin_after_its_supporter_remote_failure(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiClearError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=(
                [],
                [
                    SimpleNamespace(episodes=["origin", "supporter"]),
                ],
            )
        )
        client.remove_episode.side_effect = lambda episode: (
            (_ for _ in ()).throw(RuntimeError("supporter failed"))
            if episode == "supporter"
            else None
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "origin", "supporter")

        with pytest.raises(GraphitiClearError) as exc:
            await backend.clear_user("alice")

        assert exc.value.confirmed == 0
        assert exc.value.failed == 2
        assert [call.args[0] for call in client.remove_episode.await_args_list] == ["supporter"]
        assert backend._ledger.get("origin").state == "active"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_clear_continues_independent_episode_after_unsafe_origin(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiClearError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=(
                [],
                [
                    SimpleNamespace(episodes=["origin", "foreign-supporter"]),
                ],
            )
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "origin", "independent")
        await self._save(backend, "foreign-supporter", user="bob")

        with pytest.raises(GraphitiClearError) as exc:
            await backend.clear_user("alice")

        assert exc.value.confirmed == 1
        assert exc.value.failed == 1
        client.remove_episode.assert_awaited_once_with("independent")
        assert backend._ledger.get("origin").state == "active"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("state", ["write_pending", "delete_pending"])
    async def test_delete_refuses_unresolved_external_supporter(
        self, ledger_path: Path, state: str
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiUnsafeDeletionError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=([], [SimpleNamespace(episodes=["origin", "supporter"])])
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "origin", "supporter")
        if state == "write_pending":
            backend._ledger.reserve_write(
                episode_id="pending",
                user_key="alice",
                session_key=None,
                partition_id=backend._ledger.get("supporter").partition_id,
                idempotency_key="pending",
                payload="pending",
            )
            backend._ledger._transaction(
                lambda connection: connection.execute(
                    "UPDATE episodes SET state = 'write_pending' WHERE episode_id = 'supporter'"
                )
            )
        else:
            backend._ledger.mark_delete_pending("supporter")
        with pytest.raises(GraphitiUnsafeDeletionError):
            await backend.delete_memory("origin")
        client.remove_episode.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("state", ["deleted", "superseded"])
    async def test_delete_disregards_conclusively_closed_supporter(
        self, ledger_path: Path, state: str
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=([], [SimpleNamespace(episodes=["origin", "supporter"])])
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "origin", "supporter")
        backend._ledger.mark_delete_pending("supporter")
        backend._ledger.mark_deleted("supporter")
        if state == "superseded":
            backend._ledger._transaction(
                lambda connection: connection.execute(
                    "UPDATE episodes SET state = 'superseded' WHERE episode_id = 'supporter'"
                )
            )
        assert await backend.delete_memory("origin") is True

    @pytest.mark.asyncio
    async def test_delete_missing_remove_episode_is_truthful_failure(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiDeletionError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
        del client.remove_episode
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "episode")
        with pytest.raises(GraphitiDeletionError):
            await backend.delete_memory("episode")
        assert backend._ledger.get("episode").state == "delete_pending"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_delete_retries_ordinary_remote_failure(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiDeletionError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
        client.remove_episode.side_effect = [RuntimeError("temporary"), None]
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await self._save(backend, "episode")
        with pytest.raises(GraphitiDeletionError, match="temporary"):
            await backend.delete_memory("episode")
        assert await backend.delete_memory("episode") is True


class TestGraphitiLifecycleRaces:
    @staticmethod
    def _blocking_lock(monkeypatch: pytest.MonkeyPatch) -> tuple[asyncio.Event, asyncio.Event]:
        entered, release = asyncio.Event(), asyncio.Event()
        locks: dict[str, asyncio.Lock] = {}

        class Lock:
            def __init__(self, _: Path, partition_id: str, timeout: float) -> None:
                self.lock = locks.setdefault(partition_id, asyncio.Lock())

            async def __aenter__(self) -> Lock:
                await self.lock.acquire()
                entered.set()
                return self

            async def __aexit__(self, *_: Any) -> None:
                self.lock.release()

        monkeypatch.setitem(
            sys.modules,
            "cutctx.memory.backends.graphiti_lock",
            SimpleNamespace(PartitionOperationLock=Lock),
        )
        return entered, release

    @pytest.mark.asyncio
    async def test_deletion_first_blocks_supporter_add_until_release(
        self, ledger_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        entered, release = self._blocking_lock(monkeypatch)
        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="origin", content="origin", user_id="alice"))
        entered.clear()

        async def hold_removal(_: str) -> None:
            await release.wait()

        client.remove_episode.side_effect = hold_removal
        deleting = asyncio.create_task(backend.delete_memory("origin"))
        await entered.wait()
        adding = asyncio.create_task(
            backend.save(Memory(id="supporter", content="supporter", user_id="alice"))
        )
        await asyncio.sleep(0)
        assert not adding.done()
        release.set()
        assert await deleting is True
        assert (await adding).id == "supporter"

    @pytest.mark.asyncio
    async def test_add_first_makes_fresh_origin_preflight_refuse(
        self, ledger_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiUnsafeDeletionError

        self._blocking_lock(monkeypatch)
        client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="origin", content="origin", user_id="alice"))
        await backend.save(Memory(id="supporter", content="supporter", user_id="alice"))
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=([], [SimpleNamespace(episodes=["origin", "supporter"])])
        )
        with pytest.raises(GraphitiUnsafeDeletionError):
            await backend.delete_memory("origin")
        client.remove_episode.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clear_cannot_interleave_supersede_remote_write_and_ledger_transition(
        self, ledger_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The replacement's partition lock covers its remote write and ledger transition."""
        from cutctx.memory.backends.graphiti import GraphitiBackend

        entered, release = self._blocking_lock(monkeypatch)
        client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="old", content="old", user_id="alice"))
        entered.clear()
        replacement_write_started, allow_replacement_write = asyncio.Event(), asyncio.Event()

        async def add_episode(**kwargs: Any) -> Any:
            if kwargs["uuid"] == "new":
                replacement_write_started.set()
                await allow_replacement_write.wait()
            return SimpleNamespace(episode=SimpleNamespace(uuid=kwargs["uuid"]))

        client.add_episode.side_effect = add_episode
        client.get_nodes_and_edges_by_episode = AsyncMock(return_value=([], []))
        superseding = asyncio.create_task(
            backend.supersede("old", Memory(id="new", content="new", user_id="alice"))
        )
        await replacement_write_started.wait()
        clearing = asyncio.create_task(backend.clear_user("alice"))
        await asyncio.sleep(0)
        assert not clearing.done()
        # While Graphiti has accepted no transition yet, the old fact stays visible.
        assert backend._ledger.get("old").state == "active"  # type: ignore[union-attr]
        assert backend._ledger.get("new").state == "write_pending"  # type: ignore[union-attr]

        allow_replacement_write.set()
        assert (await superseding).id == "new"
        assert await clearing == 1
        assert backend._ledger.get("old").state == "deleted"  # type: ignore[union-attr]
        assert backend._ledger.get("new").state == "active"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_delete_refuses_unknown_external_supporter(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiUnsafeDeletionError

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=(
                [],
                [
                    SimpleNamespace(episodes=["origin", "untracked-supporter"]),
                ],
            )
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="origin", content="origin", user_id="alice"))

        with pytest.raises(GraphitiUnsafeDeletionError, match="unknown or foreign"):
            await backend.delete_memory("origin")
        client.remove_episode.assert_not_awaited()
        assert backend._ledger.get("origin").state == "active"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_delete_non_origin_supporter_succeeds(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

        client = _mock_client()
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=(
                [],
                [
                    SimpleNamespace(episodes=["origin", "supporter"]),
                ],
            )
        )
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="origin", content="origin", user_id="alice"))
        await backend.save(Memory(id="supporter", content="supporter", user_id="alice"))

        assert await backend.delete_memory("supporter") is True
        client.remove_episode.assert_awaited_once_with("supporter")
        assert backend._ledger.get("supporter").state == "deleted"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_concurrent_add_first_rechecks_origin_under_partition_lock(
        self, ledger_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An origin deletion waits for the supporter write, then refuses on fresh provenance."""
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiUnsafeDeletionError

        entered, _ = self._blocking_lock(monkeypatch)
        client = _mock_client()
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="origin", content="origin", user_id="alice"))
        entered.clear()
        supporter_write_started, allow_supporter_write = asyncio.Event(), asyncio.Event()

        async def add_episode(**kwargs: Any) -> Any:
            if kwargs["uuid"] == "supporter":
                supporter_write_started.set()
                await allow_supporter_write.wait()
            return SimpleNamespace(episode=SimpleNamespace(uuid=kwargs["uuid"]))

        client.add_episode.side_effect = add_episode
        client.get_nodes_and_edges_by_episode = AsyncMock(
            return_value=(
                [],
                [
                    SimpleNamespace(episodes=["origin", "supporter"]),
                ],
            )
        )
        adding = asyncio.create_task(
            backend.save(Memory(id="supporter", content="supporter", user_id="alice"))
        )
        await supporter_write_started.wait()
        deleting = asyncio.create_task(backend.delete_memory("origin"))
        await asyncio.sleep(0)
        assert not deleting.done()

        allow_supporter_write.set()
        assert (await adding).id == "supporter"
        with pytest.raises(GraphitiUnsafeDeletionError):
            await deleting
        client.remove_episode.assert_not_awaited()


class TestGraphitiClearProviderFailures:
    @pytest.mark.asyncio
    async def test_clear_aggregates_one_partition_preflight_failure_and_deletes_another(
        self, ledger_path: Path
    ) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiClearError

        client = _mock_client()

        async def provenance(episode_ids: list[str]) -> tuple[list[object], list[object]]:
            if "broken" in episode_ids:
                raise RuntimeError("provider unavailable")
            return ([], [])

        client.get_nodes_and_edges_by_episode.side_effect = provenance
        backend = GraphitiBackend(_cfg(ledger_path), client=client)
        await backend.save(Memory(id="broken", content="broken", user_id="alice", session_id="s1"))
        await backend.save(
            Memory(id="healthy", content="healthy", user_id="alice", session_id="s2")
        )

        with pytest.raises(GraphitiClearError) as exc:
            await backend.clear_user("alice")

        assert exc.value.confirmed == 1
        assert exc.value.failed == 1
        assert set(exc.value.failures) == {"broken"}
        client.remove_episode.assert_awaited_once_with("healthy")


class TestGraphitiEasyWiring:
    @pytest.mark.asyncio
    async def test_easy_graphiti_preserves_neo4j_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("NEO4J_URI", "bolt://db:7687")
        monkeypatch.setenv("NEO4J_USER", "graph")
        monkeypatch.setenv("NEO4J_PASSWORD", "env-secret")
        monkeypatch.setenv("CUTCTX_GRAPHITI_LEDGER", str(tmp_path / "ledger.json"))

        mock_client = _mock_client()
        captured: dict[str, Any] = {}

        def fake_graphiti(uri: str, user: str, password: str) -> Any:
            captured["uri"] = uri
            captured["user"] = user
            captured["password"] = password
            return mock_client

        with patch("cutctx.memory.backends.graphiti._import_graphiti") as import_g:
            import_g.return_value = (
                fake_graphiti,
                SimpleNamespace(text="text", message="message", json="json"),
            )
            with patch(
                "cutctx.memory.backends.graphiti.importlib.metadata.version",
                return_value="0.21.0",
            ):
                from cutctx.memory.easy import Memory as EasyMemory

                memory = EasyMemory(backend="graphiti")
                await memory._ensure_initialized()
                await memory.save("prefers vim", user_id="carol")
                assert await memory.delete("some-id") is False

        assert captured["uri"] == "bolt://db:7687"
        assert captured["user"] == "graph"
        assert captured["password"] == "env-secret"

    def test_config_reads_neo4j_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from cutctx.memory.backends.graphiti import GraphitiConfig

        monkeypatch.setenv("NEO4J_URI", "bolt://db:7687")
        monkeypatch.setenv("NEO4J_USER", "graph")
        monkeypatch.setenv("NEO4J_PASSWORD", "pw")

        cfg = GraphitiConfig.from_env()
        assert cfg.neo4j_uri == "bolt://db:7687"
        assert cfg.neo4j_user == "graph"
        assert cfg.neo4j_password == "pw"
