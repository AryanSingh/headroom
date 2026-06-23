import sqlite3
from typing import Any

from ..compression_store import CompressionEntry


class SqliteBackend:
    """SQLite backend for CompressionStore that interoperates with Rust's SqliteCcrStore.
    
    Reads from the exact same table:
    CREATE TABLE IF NOT EXISTS ccr_entries (
        hash         TEXT PRIMARY KEY,
        original     BLOB NOT NULL,
        created_at   INTEGER NOT NULL,
        ttl_seconds  INTEGER NOT NULL
    )
    """

    def __init__(self, db_path: str, default_ttl: int = 300, **kwargs: Any):
        self._db_path = db_path
        self._default_ttl = default_ttl
        # When using :memory:, keep a single shared connection so all
        # operations see the same database (each separate connect() call
        # creates an independent in-memory database).
        self._is_memory = db_path in (":memory:",) or db_path.startswith("file::memory:")
        self._memory_conn: sqlite3.Connection | None = None
        # Ensure table exists (in case Python initializes before Rust)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Return a connection, reusing the singleton for :memory: databases."""
        if self._is_memory:
            if self._memory_conn is None:
                if self._db_path.startswith("file::"):
                    self._memory_conn = sqlite3.connect(self._db_path, uri=True)
                else:
                    self._memory_conn = sqlite3.connect(self._db_path)
            return self._memory_conn
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ccr_entries (
                    hash         TEXT PRIMARY KEY,
                    original     BLOB NOT NULL,
                    created_at   INTEGER NOT NULL,
                    ttl_seconds  INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def get(self, hash_key: str) -> CompressionEntry | None:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT original, created_at, ttl_seconds FROM ccr_entries WHERE hash = ?",
                (hash_key,)
            ).fetchone()

            if not row:
                return None

            # The Rust store saves `original` as a BLOB, which might be JSON bytes
            # CompressionEntry expects original to be a string or JSON-compatible string
            original_bytes = row["original"]
            original_str = original_bytes.decode("utf-8") if isinstance(original_bytes, bytes) else original_bytes

            return CompressionEntry(
                hash=hash_key,
                original_content=original_str,
                compressed_content="",  # Rust doesn't store compressed payload
                original_tokens=0,
                compressed_tokens=0,
                original_item_count=0,
                compressed_item_count=0,
                tool_name="rust_smart_crusher",
                tool_call_id=None,
                query_context=None,
                created_at=row["created_at"],
                ttl=row["ttl_seconds"]
            )

    def set(self, hash_key: str, entry: CompressionEntry) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO ccr_entries (hash, original, created_at, ttl_seconds)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(hash) DO UPDATE SET
                    original=excluded.original,
                    created_at=excluded.created_at,
                    ttl_seconds=excluded.ttl_seconds
                """,
                (
                    hash_key,
                    entry.original_content.encode("utf-8"),
                    int(entry.created_at),
                    self._default_ttl,
                )
            )
            conn.commit()

    def delete(self, hash_key: str) -> bool:
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM ccr_entries WHERE hash = ?", (hash_key,))
            conn.commit()
            return cursor.rowcount > 0

    def exists(self, hash_key: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute("SELECT 1 FROM ccr_entries WHERE hash = ?", (hash_key,)).fetchone()
            return row is not None

    def clear(self) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM ccr_entries")
            conn.commit()

    def count(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM ccr_entries").fetchone()
            return row[0] if row else 0

    def keys(self) -> list[str]:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT hash FROM ccr_entries")
            return [row[0] for row in cursor.fetchall()]

    def __len__(self) -> int:
        return self.count()

    def items(self) -> list[tuple[str, CompressionEntry]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT hash, original, created_at, ttl_seconds FROM ccr_entries").fetchall()

            result = []
            for row in rows:
                original_bytes = row["original"]
                original_str = original_bytes.decode("utf-8") if isinstance(original_bytes, bytes) else original_bytes

                entry = CompressionEntry(
                    hash=row["hash"],
                    original_content=original_str,
                    compressed_content="",
                    original_tokens=0,
                    compressed_tokens=0,
                    original_item_count=0,
                    compressed_item_count=0,
                    tool_name="rust_smart_crusher",
                    tool_call_id=None,
                    query_context=None,
                    created_at=row["created_at"],
                    ttl=row["ttl_seconds"]
                )
                result.append((row["hash"], entry))
            return result

    def get_stats(self) -> dict[str, Any]:
        return {
            "entry_count": self.count(),
            "backend_type": "sqlite",
            "db_path": self._db_path,
        }
