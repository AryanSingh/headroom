import sqlite3
from pathlib import Path

from cutctx.proxy.session_replay import (
    ReplayEventStore,
    record_replay_event,
    reduce_replay_events,
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


def test_reduce_replay_events_derives_session_state() -> None:
    events = [
        {
            "event_id": 1,
            "timestamp": 1.0,
            "request_id": "req-1",
            "event_type": "compression",
            "detail": {
                "tokens_before": 10,
                "tokens_after": 4,
                "savings": 6,
                "stage": "input_compressed",
            },
        },
        {
            "event_id": 2,
            "timestamp": 2.0,
            "event_type": "response_received",
            "detail": {"model": "gpt-test", "stage": "response_received"},
        },
        {"event_id": 3, "timestamp": 3.0, "event_type": "policy_blocked", "detail": {}},
        {"event_id": 4, "timestamp": 4.0, "event_type": "future_event", "detail": None},
    ]

    state = reduce_replay_events(events)

    assert state == {
        "event_count": 4,
        "first_event_id": 1,
        "last_event_id": 4,
        "first_event_timestamp": 1.0,
        "last_event_timestamp": 4.0,
        "latest_request_id": "req-1",
        "latest_model": "gpt-test",
        "latest_stage": "response_received",
        "event_type_counts": {
            "compression": 1,
            "response_received": 1,
            "policy_blocked": 1,
            "future_event": 1,
        },
        "compression": {"tokens_before": 10, "tokens_after": 4, "tokens_saved": 6},
        "response_count": 1,
        "policy_block_count": 1,
        "policy_redaction_count": 0,
    }


def test_store_lists_recent_sessions_by_latest_event(tmp_path: Path) -> None:
    store = ReplayEventStore(db_path=tmp_path / "replay.sqlite3")
    store.record(session_id="older", event_type="request", surface="test")
    store.record(session_id="newer", event_type="request", surface="test")
    store.record(session_id="older", event_type="response_received", surface="test")

    payload = store.list_recent_sessions(limit=1)

    assert payload == {
        "session_count": 1,
        "sessions": [{"session_id": "older", "event_count": 2, "last_event_id": 3}],
    }
