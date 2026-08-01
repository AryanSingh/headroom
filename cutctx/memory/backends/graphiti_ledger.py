"""Transactional, scope-owned lifecycle records for Graphiti episodes."""

from __future__ import annotations

import hashlib
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar


class GraphitiLegacyMigrationRequired(RuntimeError):
    """A pre-release JSON ledger cannot safely be assigned to new scopes."""


@dataclass(frozen=True)
class EpisodeRecord:
    episode_id: str
    user_key: str
    session_key: str | None
    partition_id: str
    idempotency_key_hash: str
    payload_digest: str
    provider_reference_time: datetime | None
    state: str
    superseded_at: datetime | None
    deleted_at: datetime | None
    replacement_id: str | None
    last_error: str | None


_T = TypeVar("_T")
_SQLITE_HEADER = b"SQLite format 3\x00"
_RETRIES = (0.01, 0.02, 0.04, 0.08)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest(payload: str | bytes) -> str:
    value = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(value).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteEpisodeLedger:
    """SQLite-backed Graphiti episode ownership with enforced state changes."""

    def __init__(self, path: Path, *, busy_timeout: float = 30) -> None:
        self.path = Path(path)
        self._busy_timeout = busy_timeout
        self._check_legacy_file()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _check_legacy_file(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("rb") as source:
            header = source.read(len(_SQLITE_HEADER))
        if header != _SQLITE_HEADER:
            raise GraphitiLegacyMigrationRequired(
                f"Graphiti ledger at {self.path} is not SQLite. Its legacy state "
                "cannot be migrated automatically because session and opaque partition "
                "ownership cannot be reconstructed."
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self._busy_timeout)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout * 1000)}")
        return connection

    def _initialize(self) -> None:
        # WAL mode must be selected before a transaction begins; setting it on
        # every short-lived operation races concurrent writers needlessly.
        for attempt in range(len(_RETRIES) + 1):
            connection = self._connect()
            try:
                connection.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as exc:
                if attempt >= len(_RETRIES) or not self._is_lock_error(exc):
                    raise
                time.sleep(_RETRIES[attempt])
            finally:
                connection.close()
        else:
            raise AssertionError("unreachable")

        def create(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    user_key TEXT NOT NULL,
                    session_key TEXT,
                    partition_id TEXT NOT NULL,
                    idempotency_key_hash TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    provider_reference_time TEXT,
                    state TEXT NOT NULL,
                    superseded_at TEXT,
                    deleted_at TEXT,
                    replacement_id TEXT,
                    last_error TEXT
                )
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(episodes)")}
            if "provider_reference_time" not in columns:
                connection.execute("ALTER TABLE episodes ADD COLUMN provider_reference_time TEXT")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS episodes_scope_state "
                "ON episodes(user_key, session_key, state)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS episodes_partition ON episodes(partition_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS episodes_idempotency ON episodes(idempotency_key_hash)"
            )

        self._transaction(create)

    def _transaction(self, operation: Callable[[sqlite3.Connection], _T]) -> _T:
        for attempt in range(len(_RETRIES) + 1):
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                result = operation(connection)
                connection.commit()
                return result
            except sqlite3.OperationalError as exc:
                connection.rollback()
                if attempt >= len(_RETRIES) or not self._is_lock_error(exc):
                    raise
                time.sleep(_RETRIES[attempt])
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        raise AssertionError("unreachable")

    @staticmethod
    def _is_lock_error(error: sqlite3.OperationalError) -> bool:
        text = str(error).lower()
        return "database is locked" in text or "database is busy" in text

    @staticmethod
    def _record(row: sqlite3.Row | None) -> EpisodeRecord | None:
        if row is None:
            return None
        return EpisodeRecord(
            episode_id=row["episode_id"],
            user_key=row["user_key"],
            session_key=row["session_key"],
            partition_id=row["partition_id"],
            idempotency_key_hash=row["idempotency_key_hash"],
            payload_digest=row["payload_digest"],
            provider_reference_time=_parse(row["provider_reference_time"]),
            state=row["state"],
            superseded_at=_parse(row["superseded_at"]),
            deleted_at=_parse(row["deleted_at"]),
            replacement_id=row["replacement_id"],
            last_error=row["last_error"],
        )

    def reserve_write(
        self,
        *,
        episode_id: str,
        user_key: str,
        session_key: str | None,
        partition_id: str,
        idempotency_key: str,
        payload: str | bytes,
        provider_reference_time: datetime | None = None,
    ) -> EpisodeRecord:
        user_hash, session_hash = (
            _hash(user_key),
            _hash(session_key) if session_key is not None else None,
        )
        idem_hash, payload_hash = _hash(idempotency_key), _digest(payload)

        def reserve(connection: sqlite3.Connection) -> EpisodeRecord:
            existing = connection.execute(
                "SELECT * FROM episodes WHERE idempotency_key_hash = ?", (idem_hash,)
            ).fetchone()
            if existing is not None:
                record = self._record(existing)
                assert record is not None
                if (
                    record.user_key,
                    record.session_key,
                    record.partition_id,
                    record.payload_digest,
                ) != (user_hash, session_hash, partition_id, payload_hash):
                    raise ValueError("idempotency key was reused with different scope or payload")
                return record
            try:
                connection.execute(
                    "INSERT INTO episodes (episode_id, user_key, session_key, partition_id, idempotency_key_hash, payload_digest, provider_reference_time, state) VALUES (?, ?, ?, ?, ?, ?, ?, 'write_pending')",
                    (
                        episode_id,
                        user_hash,
                        session_hash,
                        partition_id,
                        idem_hash,
                        payload_hash,
                        provider_reference_time.isoformat() if provider_reference_time else None,
                    ),
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"episode already reserved: {episode_id}") from None
            record = self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
                ).fetchone()
            )
            assert record is not None
            return record

        return self._transaction(reserve)

    def _require_update(
        self, connection: sqlite3.Connection, sql: str, params: tuple[object, ...], message: str
    ) -> None:
        if connection.execute(sql, params).rowcount != 1:
            raise ValueError(message)

    def activate(self, episode_id: str) -> EpisodeRecord:
        def activate(connection: sqlite3.Connection) -> EpisodeRecord:
            self._require_update(
                connection,
                "UPDATE episodes SET state = 'active' WHERE episode_id = ? AND state = 'write_pending'",
                (episode_id,),
                "episode is not write_pending",
            )
            record = self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
                ).fetchone()
            )
            assert record is not None
            return record

        return self._transaction(activate)

    def record_replacement(
        self, old_episode_id: str, replacement_id: str, when: datetime | None = None
    ) -> EpisodeRecord:
        stamp = (when or _now()).isoformat()

        def replace(connection: sqlite3.Connection) -> EpisodeRecord:
            old = self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (old_episode_id,)
                ).fetchone()
            )
            replacement = self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (replacement_id,)
                ).fetchone()
            )
            if old is None or replacement is None:
                raise ValueError("episode does not exist")
            if (old.user_key, old.session_key, old.partition_id) != (
                replacement.user_key,
                replacement.session_key,
                replacement.partition_id,
            ):
                raise ValueError("replacement episodes must share the same scope")
            # The commit may have succeeded before a caller received its
            # response.  Retrying that exact pair is therefore safe and must
            # not turn a completed supersession into an error.
            if (
                old.state == "superseded"
                and old.replacement_id == replacement_id
                and replacement.state == "active"
            ):
                return old
            self._require_update(
                connection,
                "UPDATE episodes SET state = 'active' WHERE episode_id = ? AND state = 'write_pending'",
                (replacement_id,),
                "replacement is not write_pending",
            )
            self._require_update(
                connection,
                "UPDATE episodes SET state = 'superseded', superseded_at = ?, replacement_id = ? WHERE episode_id = ? AND state = 'active'",
                (stamp, replacement_id, old_episode_id),
                "episode is not active",
            )
            record = self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (old_episode_id,)
                ).fetchone()
            )
            assert record is not None
            return record

        return self._transaction(replace)

    def mark_delete_pending(self, episode_id: str) -> EpisodeRecord:
        def pending(connection: sqlite3.Connection) -> EpisodeRecord:
            row = connection.execute(
                "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
            ).fetchone()
            record = self._record(row)
            if record is None or record.state not in {"active", "superseded", "delete_pending"}:
                raise ValueError("episode cannot be marked delete_pending")
            if record.state != "delete_pending":
                self._require_update(
                    connection,
                    "UPDATE episodes SET state = 'delete_pending' WHERE episode_id = ? AND state IN ('active', 'superseded')",
                    (episode_id,),
                    "episode cannot be marked delete_pending",
                )
            result = self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
                ).fetchone()
            )
            assert result is not None
            return result

        return self._transaction(pending)

    def mark_deleted(self, episode_id: str, when: datetime | None = None) -> EpisodeRecord:
        stamp = (when or _now()).isoformat()

        def deleted(connection: sqlite3.Connection) -> EpisodeRecord:
            self._require_update(
                connection,
                "UPDATE episodes SET state = 'deleted', deleted_at = ? WHERE episode_id = ? AND state = 'delete_pending'",
                (stamp, episode_id),
                "episode is not delete_pending",
            )
            record = self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
                ).fetchone()
            )
            assert record is not None
            return record

        return self._transaction(deleted)

    def mark_delete_failed(self, episode_id: str, error: str) -> EpisodeRecord:
        def failed(connection: sqlite3.Connection) -> EpisodeRecord:
            self._require_update(
                connection,
                "UPDATE episodes SET last_error = ? WHERE episode_id = ? AND state = 'delete_pending'",
                (error, episode_id),
                "episode is not delete_pending",
            )
            record = self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
                ).fetchone()
            )
            assert record is not None
            return record

        return self._transaction(failed)

    def get(self, episode_id: str) -> EpisodeRecord | None:
        return self._transaction(
            lambda connection: self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE episode_id = ?", (episode_id,)
                ).fetchone()
            )
        )

    def find_by_idempotency_key(self, idempotency_key: str) -> EpisodeRecord | None:
        key_hash = _hash(idempotency_key)
        return self._transaction(
            lambda connection: self._record(
                connection.execute(
                    "SELECT * FROM episodes WHERE idempotency_key_hash = ?", (key_hash,)
                ).fetchone()
            )
        )

    def partitions_for_scope(self, user_key: str, session_key: str | None) -> list[str]:
        user_hash = _hash(user_key)
        session_hash = _hash(session_key) if session_key is not None else None

        def partitions(connection: sqlite3.Connection) -> list[str]:
            if session_key is None:
                rows = connection.execute(
                    "SELECT DISTINCT partition_id FROM episodes WHERE user_key = ?", (user_hash,)
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT DISTINCT partition_id FROM episodes WHERE user_key = ? AND session_key = ?",
                    (user_hash, session_hash),
                ).fetchall()
            return [row[0] for row in rows]

        return self._transaction(partitions)

    def records_for_user(self, user_key: str) -> list[EpisodeRecord]:
        def records(connection: sqlite3.Connection) -> list[EpisodeRecord]:
            result: list[EpisodeRecord] = []
            for row in connection.execute(
                "SELECT * FROM episodes WHERE user_key = ?", (_hash(user_key),)
            ).fetchall():
                record = self._record(row)
                assert record is not None
                result.append(record)
            return result

        return self._transaction(records)

    def invalid_at_for(self, episode_ids: list[str]) -> datetime | None:
        if not episode_ids:
            return None

        def invalid(connection: sqlite3.Connection) -> datetime | None:
            placeholders = ", ".join("?" for _ in episode_ids)
            rows = connection.execute(
                f"SELECT * FROM episodes WHERE episode_id IN ({placeholders})", episode_ids
            ).fetchall()
            if len(rows) != len(set(episode_ids)):
                return None
            records = [self._record(row) for row in rows]
            if any(
                record is None or record.state not in {"superseded", "deleted"}
                for record in records
            ):
                return None
            stamps = [
                record.superseded_at or record.deleted_at
                for record in records
                if record is not None
            ]
            return max(stamp for stamp in stamps if stamp is not None)

        return self._transaction(invalid)
