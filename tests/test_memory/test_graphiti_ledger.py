"""Durable ownership and lifecycle tests for the Graphiti episode ledger."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Barrier, Process, Queue
from pathlib import Path

import pytest

from cutctx.memory.backends.graphiti import _scope_partition
from cutctx.memory.backends.graphiti_ledger import SQLiteEpisodeLedger


def _reserve(ledger: SQLiteEpisodeLedger, episode: str, user: str, session: str) -> None:
    ledger.reserve_write(
        episode_id=episode,
        user_key=user,
        session_key=session,
        partition_id=_scope_partition(user, session),
        idempotency_key=f"key-{episode}",
        payload=f"payload-{episode}",
    )


def _construct_ledger(path: str, barrier: Barrier, errors: Queue) -> None:
    barrier.wait()
    try:
        SQLiteEpisodeLedger(Path(path), busy_timeout=0.001)
    except sqlite3.OperationalError as exc:
        errors.put(str(exc))


def test_persistence_reopens_exact_ownership_partition_and_state(tmp_path: Path) -> None:
    path = tmp_path / "episodes.sqlite3"
    first = SQLiteEpisodeLedger(path)
    _reserve(first, "episode-1", "alice", "s1")
    first.activate("episode-1")

    record = SQLiteEpisodeLedger(path).get("episode-1")

    assert record is not None
    assert record.episode_id == "episode-1"
    assert record.user_key != "alice"
    assert record.session_key != "s1"
    assert record.partition_id == _scope_partition("alice", "s1")
    assert record.state == "active"


def test_scope_lookup_does_not_leak_another_session(tmp_path: Path) -> None:
    ledger = SQLiteEpisodeLedger(tmp_path / "episodes.sqlite3")
    for episode, session in (("one", "s1"), ("two", "s2")):
        _reserve(ledger, episode, "alice", session)
        ledger.activate(episode)

    assert ledger.partitions_for_scope("alice", "s1") == [_scope_partition("alice", "s1")]
    assert {record.episode_id for record in ledger.records_for_user("alice")} == {"one", "two"}


def test_concurrent_independent_connections_preserve_all_records(tmp_path: Path) -> None:
    path = tmp_path / "episodes.sqlite3"
    barrier = threading.Barrier(2)
    ledgers = {prefix: SQLiteEpisodeLedger(path) for prefix in ("alice", "bob")}

    def writer(prefix: str) -> None:
        ledger = ledgers[prefix]
        barrier.wait()
        for index in range(50):
            episode = f"{prefix}-{index}"
            _reserve(ledger, episode, prefix, "s1")
            ledger.activate(episode)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer, prefix) for prefix in ("alice", "bob")]
        for future in futures:
            future.result()

    records = SQLiteEpisodeLedger(path).records_for_user("alice") + SQLiteEpisodeLedger(
        path
    ).records_for_user("bob")
    assert len(records) == 100
    assert all(record.state == "active" for record in records)


def test_lifecycle_transitions_and_visibility(tmp_path: Path) -> None:
    ledger = SQLiteEpisodeLedger(tmp_path / "episodes.sqlite3")
    _reserve(ledger, "old", "alice", "s1")
    _reserve(ledger, "new", "alice", "s1")
    ledger.activate("old")
    ledger.record_replacement("old", "new")

    assert ledger.get("old").state == "superseded"  # type: ignore[union-attr]
    assert ledger.get("old").replacement_id == "new"  # type: ignore[union-attr]
    assert ledger.get("new").state == "active"  # type: ignore[union-attr]
    ledger.mark_delete_pending("new")
    assert ledger.get("new").state == "delete_pending"  # type: ignore[union-attr]
    ledger.mark_delete_failed("new", "remote unavailable")
    assert ledger.get("new").last_error == "remote unavailable"  # type: ignore[union-attr]
    ledger.mark_deleted("new")
    assert ledger.get("new").state == "deleted"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("old_user", "old_session", "new_user", "new_session"),
    [("alice", "s1", "bob", "s1"), ("alice", "s1", "alice", "s2")],
)
def test_replacement_rejects_cross_scope_pairs_without_mutating_rows(
    tmp_path: Path,
    old_user: str,
    old_session: str,
    new_user: str,
    new_session: str,
) -> None:
    ledger = SQLiteEpisodeLedger(tmp_path / "episodes.sqlite3")
    _reserve(ledger, "old", old_user, old_session)
    _reserve(ledger, "new", new_user, new_session)
    ledger.activate("old")
    old_before, new_before = ledger.get("old"), ledger.get("new")

    with pytest.raises(ValueError, match="scope"):
        ledger.record_replacement("old", "new")

    assert ledger.get("old") == old_before
    assert ledger.get("new") == new_before


def test_concurrent_first_time_construction_retries_wal_busy_errors(tmp_path: Path) -> None:
    path = tmp_path / "episodes.sqlite3"
    barrier, errors = Barrier(2), Queue()
    workers = [
        Process(target=_construct_ledger, args=(str(path), barrier, errors)) for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(5)

    assert all(worker.exitcode == 0 for worker in workers)
    assert errors.empty()


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("activate", ("missing",)),
        ("mark_deleted", ("missing",)),
        ("record_replacement", ("missing", "also-missing")),
    ],
)
def test_unknown_ids_and_invalid_transitions_are_rejected(
    tmp_path: Path, method: str, args: tuple[str, ...]
) -> None:
    ledger = SQLiteEpisodeLedger(tmp_path / "episodes.sqlite3")
    with pytest.raises(ValueError):
        getattr(ledger, method)(*args)


def test_invalid_at_waits_for_every_parent_to_close(tmp_path: Path) -> None:
    ledger = SQLiteEpisodeLedger(tmp_path / "episodes.sqlite3")
    for episode in ("first", "second"):
        _reserve(ledger, episode, "alice", "s1")
        ledger.activate(episode)
    ledger.mark_delete_pending("first")
    ledger.mark_deleted("first")
    assert ledger.invalid_at_for(["first", "second"]) is None
    ledger.mark_delete_pending("second")
    ledger.mark_deleted("second")
    assert ledger.invalid_at_for(["first", "second"]) is not None


def test_legacy_json_is_rejected_without_mutating_bytes(tmp_path: Path) -> None:
    from cutctx.memory.backends.graphiti_ledger import GraphitiLegacyMigrationRequired

    path = tmp_path / "graphiti_ledger.json"
    legacy = b'{"superseded":{"old":"2026-01-01T00:00:00+00:00"},"deleted":["gone"],"user_episodes":{"alice":["old","gone"]}}'
    path.write_bytes(legacy)
    with pytest.raises(GraphitiLegacyMigrationRequired, match="session.*partition") as exc:
        SQLiteEpisodeLedger(path)
    assert str(path) in str(exc.value)
    assert path.read_bytes() == legacy


def test_malformed_legacy_file_fails_closed(tmp_path: Path) -> None:
    from cutctx.memory.backends.graphiti_ledger import GraphitiLegacyMigrationRequired

    path = tmp_path / "graphiti_ledger.json"
    path.write_bytes(b"{not json")
    with pytest.raises(GraphitiLegacyMigrationRequired):
        SQLiteEpisodeLedger(path)
    assert path.read_bytes() == b"{not json"


def test_non_lock_operational_error_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = SQLiteEpisodeLedger(tmp_path / "episodes.sqlite3")
    monkeypatch.setattr(
        ledger,
        "_connect",
        lambda: (_ for _ in ()).throw(sqlite3.OperationalError("no such table: nope")),
    )
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        ledger.get("anything")


def test_busy_write_is_retried_until_a_real_sqlite_lock_releases(tmp_path: Path) -> None:
    path = tmp_path / "episodes.sqlite3"
    ledger = SQLiteEpisodeLedger(path, busy_timeout=0.001)
    locked, release = threading.Event(), threading.Event()

    def hold_write_lock() -> None:
        connection = sqlite3.connect(path)
        try:
            connection.execute("BEGIN EXCLUSIVE")
            locked.set()
            assert release.wait(1)
            connection.commit()
        finally:
            connection.close()

    thread = threading.Thread(target=hold_write_lock)
    thread.start()
    assert locked.wait(1)
    releaser = threading.Timer(0.05, release.set)
    releaser.start()
    try:
        _reserve(ledger, "after-lock", "alice", "s1")
    finally:
        release.set()
        releaser.cancel()
        thread.join(1)
    assert ledger.get("after-lock") is not None
