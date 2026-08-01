"""TDD tests for Graphiti OSS memory backend adapter.

Unit tests mock graphiti_core — no Neo4j required in CI.
"""

from __future__ import annotations

import re
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
    return client


class TestGraphitiImportGuard:
    def test_missing_graphiti_core_raises_clear_importerror(self) -> None:
        from cutctx.memory.backends import graphiti as graphiti_mod

        with patch.dict("sys.modules", {"graphiti_core": None, "graphiti_core.nodes": None}):
            with pytest.raises(ImportError, match="cutctx-ai\\[graphiti\\]"):
                graphiti_mod._import_graphiti()


class TestGraphitiSaveMapping:
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
    async def test_search_maps_entity_edges_to_memories(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

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
    async def test_rank_fallback_score_when_edge_has_no_score(self, ledger_path: Path) -> None:
        from cutctx.memory.backends.graphiti import GraphitiBackend

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
                assert await memory.delete("some-id") is True

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
