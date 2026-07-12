from __future__ import annotations

from cutctx.cache.backends.sqlite import SqliteBackend
from cutctx.memory.adapters.fts5 import FTS5TextIndex
from cutctx.memory.adapters.sqlite import SQLiteMemoryStore
from cutctx.memory.adapters.sqlite_graph import SQLiteGraphStore
from cutctx.storage.sqlite import SQLiteStorage


def test_sqlite_ccr_backend_enables_wal_and_normal_sync(tmp_path) -> None:
    backend = SqliteBackend(str(tmp_path / "ccr.db"))

    with backend._get_conn() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1


def test_memory_and_metrics_sqlite_stores_enable_wal(tmp_path) -> None:
    stores = [
        SQLiteMemoryStore(tmp_path / "memory.db"),
        SQLiteGraphStore(tmp_path / "graph.db"),
        FTS5TextIndex(tmp_path / "fts.db"),
        SQLiteStorage(str(tmp_path / "metrics.db")),
    ]

    for store in stores:
        with store._get_conn() as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
