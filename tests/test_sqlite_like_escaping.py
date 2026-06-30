from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from cutctx.memory.adapters.sqlite import SQLiteMemoryStore, _escape_like
from cutctx.memory.models import Memory
from cutctx.memory.ports import MemoryFilter


def test_escape_like_escapes_percent_and_underscore() -> None:
    assert _escape_like("test%value_under") == r"test\%value\_under"


@pytest.mark.asyncio
async def test_entity_ref_filter_treats_percent_as_literal() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        store = SQLiteMemoryStore(db_path)
        literal = Memory(
            id="literal-entity",
            content="literal percent entity ref",
            user_id="alice",
            entity_refs=["test%injection"],
        )
        wildcard_neighbor = Memory(
            id="wildcard-neighbor",
            content="neighbor entity ref",
            user_id="alice",
            entity_refs=["testAinjection"],
        )
        await store.save(literal)
        await store.save(wildcard_neighbor)

        results = await store.query(
            MemoryFilter(user_id="alice", entity_refs=["test%injection"])
        )
        assert [memory.id for memory in results] == ["literal-entity"]
    finally:
        db_path.unlink(missing_ok=True)
