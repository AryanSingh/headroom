from __future__ import annotations

from cutctx.cache.backends.sqlite import SqliteBackend


def test_sqlite_ccr_backend_enables_wal_and_normal_sync(tmp_path) -> None:
    backend = SqliteBackend(str(tmp_path / "ccr.db"))

    with backend._get_conn() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
