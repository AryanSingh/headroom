import sqlite3
from pathlib import Path

from cutctx.proxy.session_replay import (
    ReplayEventStore,
    record_replay_event,
    reset_replay_store,
)


def test_store_persists_events_in_append_order(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite3"
    store = ReplayEventStore(db_path=path)
    store.record(session_id="s1", event_type="first", surface="test")
    store.record(session_id="s1", event_type="second", surface="test")
    store.close()

    payload = ReplayEventStore(db_path=path).get("s1")

    assert [event["event_type"] for event in payload["events"]] == ["first", "second"]
    assert [event["event_id"] for event in payload["events"]] == [1, 2]


def test_disabled_replay_does_not_create_a_database(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "replay.sqlite3"
    monkeypatch.delenv("CUTCTX_REPLAY", raising=False)
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(path))
    reset_replay_store()

    record_replay_event(session_id="s1", event_type="request", surface="test")

    assert not path.exists()


def test_store_removes_expired_events_when_opened(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite3"
    ReplayEventStore(db_path=path, retention_days=0).close()
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO replay_events (
                timestamp_ms, session_id, event_type, surface, request_id, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (0, "old", "request", "test", None, "{}"),
        )

    store = ReplayEventStore(db_path=path, retention_days=7)

    assert store.get("old")["event_count"] == 0


def test_store_drops_sensitive_and_unrecognized_detail_fields(tmp_path: Path) -> None:
    store = ReplayEventStore(db_path=tmp_path / "replay.sqlite3")

    store.record(
        session_id="s1",
        event_type="policy_blocked",
        surface="openai",
        detail={
            "matched_rules": ["deny"],
            "message": "secret prompt",
            "headers": {"x-api-key": "secret"},
        },
    )

    assert store.get("s1")["events"][0]["detail"] == {"matched_rules": ["deny"]}


def test_store_ignores_a_storage_failure(tmp_path: Path, monkeypatch) -> None:
    store = ReplayEventStore(db_path=tmp_path / "replay.sqlite3")

    def fail_append(*_args, **_kwargs) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(store, "_append", fail_append)

    store.record(session_id="s1", event_type="request", surface="test")


def test_store_keeps_only_the_configured_recent_events_per_session(tmp_path: Path) -> None:
    store = ReplayEventStore(db_path=tmp_path / "replay.sqlite3", max_events_per_session=2)
    store.record(session_id="s1", event_type="first", surface="test")
    store.record(session_id="s1", event_type="second", surface="test")
    store.record(session_id="s1", event_type="third", surface="test")

    payload = store.get("s1")

    assert [event["event_type"] for event in payload["events"]] == ["second", "third"]


def test_store_skips_a_malformed_persisted_event(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite3"
    ReplayEventStore(db_path=path).close()
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO replay_events (
                timestamp_ms, session_id, event_type, surface, request_id, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1, "s1", "request", "test", None, "not-json"),
        )

    payload = ReplayEventStore(db_path=path, retention_days=0).get("s1")

    assert payload["event_count"] == 0


def test_store_uses_write_ahead_logging_for_concurrent_proxy_workers(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite3"
    ReplayEventStore(db_path=path).close()

    with sqlite3.connect(path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert journal_mode == "wal"
