"""Compatibility contracts for the supported Graphiti upstream releases."""

from __future__ import annotations

import asyncio
import inspect
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

graphiti_core = pytest.importorskip("graphiti_core")


def test_installed_graphiti_distribution_is_supported() -> None:
    from importlib.metadata import version

    from cutctx.memory.backends.graphiti import _validate_graphiti_version

    _validate_graphiti_version(version("graphiti-core"))


def test_graphiti_public_method_signatures_are_compatible() -> None:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodeType

    assert EpisodeType is not None
    required = {
        "add_episode": {
            "name",
            "episode_body",
            "source_description",
            "reference_time",
            "source",
            "group_id",
            "uuid",
            "previous_episode_uuids",
        },
        "search": {"query", "group_ids", "num_results"},
        "remove_episode": {"episode_uuid"},
        "get_nodes_and_edges_by_episode": {"episode_uuids"},
    }
    for method, parameters in required.items():
        assert parameters <= set(inspect.signature(getattr(Graphiti, method)).parameters)


def test_adapter_uses_supported_awaited_call_shapes(tmp_path) -> None:
    from cutctx.memory.backends.graphiti import GraphitiBackend, GraphitiConfig, _scope_partition
    from cutctx.memory.models import Memory

    client = SimpleNamespace(
        add_episode=AsyncMock(),
        search=AsyncMock(return_value=[]),
        remove_episode=AsyncMock(),
    )
    backend = GraphitiBackend(
        GraphitiConfig(neo4j_password="test", ledger_path=tmp_path / "ledger.json"),
        client=client,
    )
    asyncio.run(
        backend.save(Memory(id="episode", content="fact", user_id="alice", session_id="session"))
    )
    asyncio.run(backend.search_memories("fact", user_id="alice", session_id="session"))
    asyncio.run(backend.delete_memory("episode"))

    add_kwargs = client.add_episode.await_args.kwargs
    assert {
        "name",
        "episode_body",
        "source_description",
        "reference_time",
        "source",
        "group_id",
        "uuid",
    } <= set(add_kwargs)
    assert add_kwargs["group_id"] == _scope_partition("alice", "session")
    assert client.search.await_args.kwargs == {
        "query": "fact",
        "group_ids": [_scope_partition("alice", "session")],
        "num_results": 30,
    }
    client.remove_episode.assert_awaited_once_with("episode")


@pytest.mark.graphiti_live_contract
def test_graphiti_live_contract_preserves_ordered_provenance() -> None:
    asyncio.run(_run_graphiti_live_contract())


async def _run_graphiti_live_contract() -> None:
    """Prove Graphiti's origin-first deletion behavior against CI Neo4j."""
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "AZURE_OPENAI_API_KEY",
    ):
        assert not os.environ.get(key), f"{key} must be unset for this contract"

    from graphiti_core import Graphiti
    from graphiti_core.driver.neo4j_driver import Neo4jDriver
    from graphiti_core.edges import EntityEdge, EpisodicEdge
    from graphiti_core.nodes import EntityNode, EpisodeType, EpisodicNode

    driver = Neo4jDriver(
        os.environ["NEO4J_URI"],
        os.environ["NEO4J_USER"],
        os.environ["NEO4J_PASSWORD"],
    )
    graphiti = object.__new__(Graphiti)
    graphiti.driver = driver
    graphiti.max_coroutines = None
    group_id = f"contract-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    origin_uuid, supporter_uuid = str(uuid.uuid4()), str(uuid.uuid4())
    edge_uuid = str(uuid.uuid4())
    try:
        origin = EpisodicNode(
            uuid=origin_uuid,
            name="origin",
            group_id=group_id,
            source=EpisodeType.message,
            source_description="contract",
            content="origin",
            valid_at=now,
            entity_edges=[edge_uuid],
        )
        supporter = EpisodicNode(
            uuid=supporter_uuid,
            name="supporter",
            group_id=group_id,
            source=EpisodeType.message,
            source_description="contract",
            content="supporter",
            valid_at=now,
            entity_edges=[edge_uuid],
        )
        source = EntityNode(name="source", group_id=group_id, name_embedding=[0.0])
        target = EntityNode(name="target", group_id=group_id, name_embedding=[0.0])
        edge = EntityEdge(
            uuid=edge_uuid,
            group_id=group_id,
            source_node_uuid=source.uuid,
            target_node_uuid=target.uuid,
            created_at=now,
            name="SUPPORTS",
            fact="source supports target",
            fact_embedding=[0.0],
            episodes=[origin_uuid, supporter_uuid],
            valid_at=now,
        )
        for item in (origin, supporter, source, target, edge):
            await item.save(driver)
        for episode in (origin, supporter):
            await EpisodicEdge(
                group_id=group_id,
                source_node_uuid=episode.uuid,
                target_node_uuid=source.uuid,
                created_at=now,
            ).save(driver)

        result = await graphiti.get_nodes_and_edges_by_episode([origin_uuid, supporter_uuid])
        matching_edges = [item for item in result.edges if str(item.uuid) == edge_uuid]
        assert matching_edges
        assert matching_edges[0].episodes == [origin_uuid, supporter_uuid]

        await graphiti.remove_episode(supporter_uuid)
        retained = await graphiti.get_nodes_and_edges_by_episode([origin_uuid])
        assert edge_uuid in [str(item.uuid) for item in retained.edges]

        await graphiti.remove_episode(origin_uuid)
        assert await EntityEdge.get_by_uuids(driver, [edge_uuid]) == []
    finally:
        await driver.close()
