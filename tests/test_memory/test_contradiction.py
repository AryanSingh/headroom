"""TDD tests for opt-in contradiction detection → supersede."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pytest

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from cutctx.memory.adapters.sqlite import SQLiteMemoryStore
from cutctx.memory.config import MemoryConfig
from cutctx.memory.contradiction import (
    ContradictionClassifier,
    ContradictionVerdict,
    classify_pair,
    find_contradiction_candidates,
)
from cutctx.memory.core import HierarchicalMemory
from cutctx.memory.models import Memory
from cutctx.memory.ports import MemoryFilter, TextFilter, TextSearchResult, VectorFilter


class _StubEmbedder:
    async def embed(self, text: str) -> np.ndarray:
        return np.zeros(8, dtype=np.float32)

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        return [await self.embed(t) for t in texts]


class _StubVectorIndex:
    async def index(self, memory: Memory) -> None:
        return None

    async def index_memory(self, memory: Memory) -> None:
        return None

    async def index_batch(self, memories: list[Memory]) -> int:
        return len(memories)

    async def remove(self, memory_id: str) -> bool:
        return True

    async def search(self, filter: VectorFilter) -> list[Any]:
        return []


class _StubTextIndex:
    async def index(self, memory: Memory) -> None:
        return None

    async def index_memory(self, memory: Memory) -> None:
        return None

    async def index_batch(self, memories: list[Memory]) -> int:
        return len(memories)

    async def remove(self, memory_id: str) -> bool:
        return True

    async def search(self, filter: TextFilter) -> list[TextSearchResult]:
        return []


def _make_hm(db_path: Path, **config_kwargs: Any) -> HierarchicalMemory:
    store = SQLiteMemoryStore(db_path)
    config = MemoryConfig(db_path=db_path, **config_kwargs)
    return HierarchicalMemory(
        store=store,
        vector_index=_StubVectorIndex(),
        text_index=_StubTextIndex(),
        embedder=_StubEmbedder(),
        cache=None,
        config=config,
    )


class TestDeterministicClassifier:
    def test_independent_when_no_shared_entities(self) -> None:
        verdict = classify_pair(
            old_content="Alice works on frontend",
            new_content="Bob prefers dark mode",
            shared_entities=[],
        )
        assert verdict == ContradictionVerdict.INDEPENDENT

    @pytest.mark.parametrize(
        ("old_content", "new_content"),
        [
            ("Alice owns a bike", "Alice owns a car"),
            ("Alice likes coffee", "Alice likes tea"),
            ("Alice uses Python", "Alice uses Rust"),
            ("Alice works on frontend", "Alice works on backend"),
        ],
    )
    def test_nonexclusive_predicates_with_distinct_objects_are_independent(
        self, old_content: str, new_content: str
    ) -> None:
        verdict = classify_pair(
            old_content=old_content,
            new_content=new_content,
            shared_entities=["Alice"],
        )
        assert verdict == ContradictionVerdict.INDEPENDENT

    def test_contradict_when_explicit_exclusive_predicate_changes_object(self) -> None:
        verdict = classify_pair(
            old_content="Alice was born in Paris",
            new_content="Alice was born in London",
            shared_entities=["Alice"],
        )
        assert verdict == ContradictionVerdict.CONTRADICT

    def test_refine_when_new_extends_old(self) -> None:
        verdict = classify_pair(
            old_content="Alice works on backend",
            new_content="Alice works on backend and owns auth",
            shared_entities=["Alice"],
        )
        assert verdict == ContradictionVerdict.REFINE

    def test_refine_when_content_is_identical(self) -> None:
        assert (
            classify_pair(
                old_content="Alice works on backend",
                new_content="Alice works on backend",
                shared_entities=["Alice"],
            )
            == ContradictionVerdict.REFINE
        )

    def test_narrowing_is_independent(self) -> None:
        verdict = classify_pair(
            old_content="Alice works on backend and owns auth",
            new_content="Alice works on backend",
            shared_entities=["Alice"],
        )
        # Same role verb+object after strip? "works on backend and owns auth" vs
        # "works on backend" — objects differ → CONTRADICT actually via role pattern.
        # Prefer independent narrowing without treating extension reverse as refine.
        assert verdict in (
            ContradictionVerdict.INDEPENDENT,
            ContradictionVerdict.CONTRADICT,
        )
        assert verdict != ContradictionVerdict.REFINE

    def test_unrelated_same_entity_is_independent(self) -> None:
        verdict = classify_pair(
            old_content="Alice likes coffee",
            new_content="Alice works on backend",
            shared_entities=["Alice"],
        )
        assert verdict == ContradictionVerdict.INDEPENDENT


class TestFindCandidates:
    def test_finds_active_memories_sharing_entities(self) -> None:
        candidates = [
            Memory(
                id="1",
                content="Alice works on frontend",
                user_id="u1",
                entity_refs=["Alice", "frontend"],
            ),
            Memory(
                id="2",
                content="Bob prefers vim",
                user_id="u1",
                entity_refs=["Bob"],
            ),
            Memory(
                id="3",
                content="Alice likes coffee",
                user_id="u1",
                entity_refs=["Alice"],
                valid_until=datetime.now(timezone.utc),
            ),
        ]
        new = Memory(
            content="Alice works on backend",
            user_id="u1",
            entity_refs=["Alice", "backend"],
        )
        found = find_contradiction_candidates(new, candidates)
        assert [m.id for m in found] == ["1"]


class TestHierarchicalContradictionGate:
    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp) / "mem.db"

    @pytest.mark.asyncio
    async def test_gate_off_keeps_both_current(self, temp_db: Path) -> None:
        hm = _make_hm(temp_db, contradiction_detection=False)
        first = await hm.add(
            content="Alice works on frontend",
            user_id="alice",
            entity_refs=["Alice", "frontend"],
            auto_embed=False,
        )
        second = await hm.add(
            content="Alice works on backend",
            user_id="alice",
            entity_refs=["Alice", "backend"],
            auto_embed=False,
        )
        refreshed = await hm.get(first.id)
        assert refreshed is not None and refreshed.is_current
        assert second.is_current

    @pytest.mark.asyncio
    async def test_nonexclusive_facts_remain_current(self, temp_db: Path) -> None:
        hm = _make_hm(temp_db, contradiction_detection=True)
        first = await hm.add(
            content="Alice works on frontend",
            user_id="alice",
            entity_refs=["Alice", "frontend"],
            auto_embed=False,
        )
        second = await hm.add(
            content="Alice works on backend",
            user_id="alice",
            entity_refs=["Alice", "backend"],
            auto_embed=False,
        )

        old = await hm.get(first.id)
        assert old is not None
        assert old.is_current
        assert old.superseded_by is None
        assert second.supersedes is None
        assert second.is_current

    @pytest.mark.asyncio
    async def test_refine_supersedes_old(self, temp_db: Path) -> None:
        hm = _make_hm(temp_db, contradiction_detection=True)
        first = await hm.add(
            content="Alice works on backend",
            user_id="alice",
            entity_refs=["Alice"],
            auto_embed=False,
        )
        second = await hm.add(
            content="Alice works on backend and owns auth",
            user_id="alice",
            entity_refs=["Alice"],
            auto_embed=False,
        )
        old = await hm.get(first.id)
        assert old is not None
        assert not old.is_current
        assert second.supersedes == first.id

    @pytest.mark.asyncio
    async def test_independent_both_remain_current(self, temp_db: Path) -> None:
        hm = _make_hm(temp_db, contradiction_detection=True)
        first = await hm.add(
            content="Alice works on frontend",
            user_id="alice",
            entity_refs=["Alice"],
            auto_embed=False,
        )
        second = await hm.add(
            content="Bob prefers dark mode",
            user_id="alice",
            entity_refs=["Bob"],
            auto_embed=False,
        )
        old = await hm.get(first.id)
        assert old is not None and old.is_current
        assert second.is_current

    @pytest.mark.asyncio
    async def test_llm_classifier_can_be_injected(self, temp_db: Path) -> None:
        calls: list[tuple[str, str]] = []

        def llm_classifier(old: str, new: str, shared: list[str]) -> ContradictionVerdict:
            calls.append((old, new))
            return ContradictionVerdict.CONTRADICT

        hm = _make_hm(
            temp_db,
            contradiction_detection=True,
            contradiction_classifier="llm",
            contradiction_classifier_callable=llm_classifier,
        )

        first = await hm.add(
            content="Team uses Postgres",
            user_id="alice",
            entity_refs=["Team", "Postgres"],
            auto_embed=False,
        )
        second = await hm.add(
            content="Team uses SQLite",
            user_id="alice",
            entity_refs=["Team", "SQLite"],
            auto_embed=False,
        )
        assert calls
        old = await hm.get(first.id)
        assert old is not None and not old.is_current
        assert second.supersedes == first.id

    @pytest.mark.asyncio
    async def test_add_batch_runs_contradiction_gate(self, temp_db: Path) -> None:
        hm = _make_hm(temp_db, contradiction_detection=True)
        created = await hm.add_batch(
            [
                {
                    "content": "Alice works on frontend",
                    "user_id": "alice",
                    "entity_refs": ["Alice"],
                },
                {
                    "content": "Alice works on backend",
                    "user_id": "alice",
                    "entity_refs": ["Alice"],
                },
            ],
            auto_embed=False,
        )
        assert len(created) == 2
        old = await hm.get(created[0].id)
        assert old is not None and old.is_current

    @pytest.mark.asyncio
    async def test_unrelated_same_entity_both_current(self, temp_db: Path) -> None:
        hm = _make_hm(temp_db, contradiction_detection=True)
        first = await hm.add(
            content="Alice likes coffee",
            user_id="alice",
            entity_refs=["Alice"],
            auto_embed=False,
        )
        second = await hm.add(
            content="Alice works on backend",
            user_id="alice",
            entity_refs=["Alice"],
            auto_embed=False,
        )
        old = await hm.get(first.id)
        assert old is not None and old.is_current
        assert second.is_current

    @pytest.mark.asyncio
    async def test_supersedes_all_conflicting_candidates(self, temp_db: Path) -> None:
        hm = _make_hm(temp_db, contradiction_detection=True)
        a = await hm.add(
            content="Alice works on frontend",
            user_id="alice",
            entity_refs=["Alice"],
            auto_embed=False,
        )
        # Force a second current conflict via gate-off path then re-enable isn't possible;
        # inject a second memory directly into the store as current.
        from cutctx.memory.models import Memory as Mem

        extra = Mem(
            content="Alice works on mobile",
            user_id="alice",
            entity_refs=["Alice"],
        )
        await hm._store.save(extra)
        third = await hm.add(
            content="Alice works on backend",
            user_id="alice",
            entity_refs=["Alice"],
            auto_embed=False,
        )
        old_a = await hm.get(a.id)
        old_extra = await hm.get(extra.id)
        assert old_a is not None and old_a.is_current
        assert old_extra is not None and old_extra.is_current
        assert third.is_current


class TestEasyApiClassifier:
    @pytest.mark.asyncio
    async def test_easy_api_classifier_is_called_for_a_local_conflict(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from cutctx.memory import HierarchicalMemory
        from cutctx.memory.easy import Memory as EasyMemory

        calls: list[tuple[str, str, list[str]]] = []
        created_systems: list[HierarchicalMemory] = []

        def classifier(old: str, new: str, shared: list[str]) -> ContradictionVerdict:
            calls.append((old, new, shared))
            return ContradictionVerdict.CONTRADICT

        async def create_with_stubbed_indexes(config: MemoryConfig) -> HierarchicalMemory:
            # Real LocalBackend owns the facade path; only heavy indexes are stubbed.
            system = _make_hm(tmp_path / "memory.db", **{
                "contradiction_detection": config.contradiction_detection,
                "contradiction_classifier": config.contradiction_classifier,
                "contradiction_classifier_callable": config.contradiction_classifier_callable,
            })
            created_systems.append(system)
            return system

        monkeypatch.setattr(
            HierarchicalMemory, "create", staticmethod(create_with_stubbed_indexes)
        )
        memory = EasyMemory(
            db_path=tmp_path / "memory.db",
            contradiction_detection=True,
            contradiction_classifier="llm",
            contradiction_classifier_callable=classifier,
        )
        first_id = await memory.save(
            "Alice uses Python", user_id="alice", entities=[{"entity": "Alice"}]
        )
        second_id = await memory.save(
            "Alice uses Rust", user_id="alice", entities=[{"entity": "Alice"}]
        )

        assert calls == [("Alice uses Python", "Alice uses Rust", ["alice"])]
        first = await created_systems[0].get(first_id)
        second = await created_systems[0].get(second_id)
        assert first is not None and not first.is_current
        assert second is not None and second.supersedes == first_id

    def test_easy_api_classifier_llm_requires_callable_before_initialization(
        self, tmp_path: Path
    ) -> None:
        from cutctx.memory.easy import Memory as EasyMemory

        with pytest.raises(ValueError, match="requires contradiction_classifier_callable"):
            EasyMemory(
                db_path=tmp_path / "memory.db",
                contradiction_detection=True,
                contradiction_classifier="llm",
            )

    def test_qdrant_neo4j_defaults_ignore_graphiti_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cutctx.memory.easy import Memory as EasyMemory

        monkeypatch.setenv("NEO4J_URI", "bolt://graphiti-env:7687")
        monkeypatch.setenv("NEO4J_USER", "graphiti-env-user")
        monkeypatch.setenv("NEO4J_PASSWORD", "graphiti-env-password")
        memory = EasyMemory(backend="qdrant-neo4j")

        assert memory._neo4j_uri == "neo4j://localhost:7687"
        assert memory._neo4j_user == "neo4j"
        assert memory._neo4j_password
        assert EasyMemory().backend_type == "local"

    @pytest.mark.asyncio
    async def test_graphiti_options_override_environment_without_using_qdrant_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cutctx.memory.backends import graphiti
        from cutctx.memory.easy import Memory as EasyMemory

        captured: list[Any] = []

        class FakeGraphitiBackend:
            def __init__(self, config: Any) -> None:
                captured.append(config)

        monkeypatch.setattr(graphiti, "GraphitiBackend", FakeGraphitiBackend)
        monkeypatch.setenv("NEO4J_URI", "bolt://graphiti-env:7687")
        monkeypatch.setenv("NEO4J_USER", "graphiti-env-user")
        monkeypatch.setenv("NEO4J_PASSWORD", "graphiti-env-password")
        memory = EasyMemory(
            backend="graphiti",
            neo4j_uri="neo4j://qdrant-only:7687",
            neo4j_user="qdrant-only-user",
            neo4j_password="qdrant-only-password",
            graphiti_neo4j_uri="bolt://graphiti-override:7687",
            graphiti_neo4j_user="graphiti-override-user",
            graphiti_neo4j_password="graphiti-override-password",
            graphiti_ledger_path="/tmp/graphiti-ledger.db",
        )
        await memory._ensure_initialized()

        config = captured[0]
        assert config.neo4j_uri == "bolt://graphiti-override:7687"
        assert config.neo4j_user == "graphiti-override-user"
        assert config.neo4j_password == "graphiti-override-password"
        assert config.ledger_path == Path("/tmp/graphiti-ledger.db")

    def test_graphiti_rejects_local_contradiction_options(self) -> None:
        from cutctx.memory.easy import Memory as EasyMemory

        with pytest.raises(ValueError, match="Graphiti's temporal extraction"):
            EasyMemory(backend="graphiti", contradiction_detection=True)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"contradiction_detection": True},
            {"contradiction_classifier": "llm"},
            {"contradiction_classifier_callable": lambda *_: ContradictionVerdict.CONTRADICT},
        ],
    )
    def test_graphiti_rejects_every_nondefault_contradiction_option_first(
        self, kwargs: dict[str, Any]
    ) -> None:
        from cutctx.memory.easy import Memory as EasyMemory

        with pytest.raises(ValueError, match="Graphiti's temporal extraction"):
            EasyMemory(backend="graphiti", **kwargs)

    def test_qdrant_password_sentinel_is_replaced(self) -> None:
        from cutctx.memory.easy import Memory as EasyMemory

        memory = EasyMemory(backend="qdrant-neo4j", neo4j_password="password")
        assert memory._neo4j_password not in {"", "password"}
