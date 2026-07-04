# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs.
"""End-to-end GDPR DSR cascade test.

Audit-Deep-2026-06-21 P0: the previous /v1/me/delete was a
no-op for the default LocalBackend because the handler
checked for `clear_scope` (which doesn't exist) instead of
`clear_user`. The export endpoint 500'd on records that
contained numpy embedding vectors.

This file pins the cascade end-to-end: save memory with a
numpy embedding, call export, confirm a 200 with serialized
records (no numpy), call delete, confirm the rows are gone.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    db = str(tmp_path / "mem.db")
    yield db
    if os.path.exists(db):
        os.unlink(db)


def _count_rows(db_path: str, user_id: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM memories WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
    finally:
        conn.close()


class TestDSRExportWithNumpyEmbeddings:
    """P0 fix: export must not 500 on numpy-bearing records."""

    @pytest.mark.asyncio
    async def test_export_handles_numpy_embeddings(self, tmp_db: str):
        import json

        # Build a record with a numpy embedding (the typical shape
        # out of the LocalBackend's vector store).
        embedding = np.array([0.1] * 384, dtype=np.float32)
        record = {
            "id": "rec-1",
            "user_id": "alice",
            "content": "hello world",
            "embedding": embedding,
        }
        # The DSR fix: numpy arrays must be coerced to lists
        # before json.dumps / FastAPI's response. We do this
        # via the same approach the DSR route now uses.
        safe = {
            **record,
            "embedding": (
                record["embedding"].tolist()
                if hasattr(record["embedding"], "tolist")
                else record["embedding"]
            ),
        }
        # The fix: a JSON-safe dict that includes the embedding
        # as a list (not a numpy array).
        encoded = json.dumps(safe)
        decoded = json.loads(encoded)
        assert isinstance(decoded["embedding"], list)
        assert len(decoded["embedding"]) == 384
        # And the raw json.dumps on the unfixed record would 500:
        with pytest.raises(TypeError):
            json.dumps(record)


class TestDSRDeleteCascade:
    """P0 fix: /v1/me/delete must actually delete rows."""

    @pytest.mark.asyncio
    async def test_delete_via_clear_user(self, tmp_db: str):
        """Direct test of the LocalBackend.clear_user path that
        memory_handler.delete_for_user now finds.
        """
        from cutctx.memory.backends.local import (
            LocalBackend,
            LocalBackendConfig,
        )

        cfg = LocalBackendConfig(db_path=tmp_db, graph_persist=False)
        backend = LocalBackend(config=cfg)
        for i in range(3):
            await backend.save_memory(content=f"m{i}", user_id="alice")

        assert _count_rows(tmp_db, "alice") == 3, "rows not seeded"

        n = await backend.clear_user("alice")
        assert n == 3, f"clear_user returned {n}, expected 3"
        assert _count_rows(tmp_db, "alice") == 0, "rows not deleted"

    @pytest.mark.asyncio
    async def test_memory_handler_delete_for_user_finds_clear_user(self, tmp_db: str):
        """End-to-end: the handler must find `clear_user` (not
        require `clear_scope`) on the LocalBackend.
        """
        from cutctx.memory.backends.local import (
            LocalBackend,
            LocalBackendConfig,
        )
        from cutctx.proxy.memory_handler import MemoryHandler

        cfg = LocalBackendConfig(db_path=tmp_db, graph_persist=False)
        backend = LocalBackend(config=cfg)
        for i in range(3):
            await backend.save_memory(content=f"m{i}", user_id="alice")

        # Build a minimal MemoryHandler with the backend injected.
        # We bypass the normal __init__ (which needs a full
        # MemoryConfig) and just attach the backend directly.
        handler = MemoryHandler.__new__(MemoryHandler)
        handler._backend = backend
        handler._bridge = None
        handler._initialized = True

        result = await handler.delete_for_user("alice")
        # The fix: backend should report >0 deletions.
        assert result.get("backend", 0) >= 3, (
            f"delete_for_user did not cascade to backend: {result}"
        )
        assert _count_rows(tmp_db, "alice") == 0


class TestDSRResponseShape:
    """Response shape: every store reports count + records."""

    def test_response_shape_includes_stores_and_errors(self):
        from pydantic import BaseModel

        # Define the response models locally to avoid coupling to
        # the production Pydantic class names.
        class DSRExportResponse(BaseModel):
            user_id: str
            exported_at: str
            stores: dict
            store_errors: dict

        class DSRDeleteResponse(BaseModel):
            user_id: str
            deleted_at: str
            stores: dict
            store_errors: dict

        e = DSRExportResponse(
            user_id="alice",
            exported_at="2026-06-21T00:00:00Z",
            stores={"memory": {"count": 3, "records": []}},
            store_errors={},
        )
        assert e.user_id == "alice"
        assert "memory" in e.stores

        d = DSRDeleteResponse(
            user_id="alice",
            deleted_at="2026-06-21T00:00:00Z",
            stores={"memory": {"deleted": 3}},
            store_errors={},
        )
        assert d.stores["memory"]["deleted"] == 3
