"""Local episode store for the data flywheel.

Records CompressionEpisodes and RetrievalLabels to a local SQLite database.
To satisfy privacy constraints, NO RAW TEXT payload is ever stored in this
database—only span offsets (start/end lines) and token reductions.
"""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

DEFAULT_DB_PATH = os.environ.get("CUTCTX_EPISODES_DB", os.path.expanduser("~/.cutctx/episodes.db"))


@dataclass
class CompressionEpisode:
    """Records a compression event (never text)."""

    episode_id: str
    tenant_id: str
    original_size: int
    compressed_size: int
    start_line: int
    end_line: int
    timestamp_ts: float


@dataclass
class RetrievalLabel:
    """Records a retrieval of a compressed memory."""

    episode_id: str
    tenant_id: str
    retrieved_span_start: int
    retrieved_span_end: int
    timestamp_ts: float


class EpisodeStore:
    """SQLite-backed store for episodes and labels."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compression_episodes (
                    episode_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    original_size INTEGER NOT NULL,
                    compressed_size INTEGER NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    timestamp_ts REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS retrieval_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    retrieved_span_start INTEGER NOT NULL,
                    retrieved_span_end INTEGER NOT NULL,
                    timestamp_ts REAL NOT NULL,
                    FOREIGN KEY(episode_id) REFERENCES compression_episodes(episode_id)
                )
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def record_compression(self, episode: CompressionEpisode) -> None:
        """Record a compression event."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO compression_episodes
                (episode_id, tenant_id, original_size, compressed_size, start_line, end_line, timestamp_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    episode.episode_id,
                    episode.tenant_id,
                    episode.original_size,
                    episode.compressed_size,
                    episode.start_line,
                    episode.end_line,
                    episode.timestamp_ts,
                ),
            )
            conn.commit()

    def record_retrieval(self, label: RetrievalLabel) -> None:
        """Record a retrieval event."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO retrieval_labels
                (episode_id, tenant_id, retrieved_span_start, retrieved_span_end, timestamp_ts)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    label.episode_id,
                    label.tenant_id,
                    label.retrieved_span_start,
                    label.retrieved_span_end,
                    label.timestamp_ts,
                ),
            )
            conn.commit()

    def get_episodes(self, limit: int = 100) -> list[CompressionEpisode]:
        """Get recent compression episodes."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT episode_id, tenant_id, original_size, compressed_size, start_line, end_line, timestamp_ts
                FROM compression_episodes
                ORDER BY timestamp_ts DESC
                LIMIT ?
            """,
                (limit,),
            )
            return [
                CompressionEpisode(
                    episode_id=row[0],
                    tenant_id=row[1],
                    original_size=row[2],
                    compressed_size=row[3],
                    start_line=row[4],
                    end_line=row[5],
                    timestamp_ts=row[6],
                )
                for row in cursor.fetchall()
            ]
