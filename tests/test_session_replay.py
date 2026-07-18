import sqlite3
from pathlib import Path

from cutctx.pipeline import PipelineEvent, PipelineStage
from cutctx.proxy.session_replay import (
    ReplayEventStore,
    ReplayPipelineExtension,
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
        "prompt_count": 0,
        "input_message_count": 0,
        "input_token_count": 0,
        "llm_request_count": 0,
        "tool_call_count": 0,
        "tool_call_counts": {},
        "response_count": 1,
        "error_count": 0,
        "error_code_counts": {},
        "stream_completion_count": 0,
        "stream_truncation_count": 0,
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


def test_store_recovers_recent_session_states(tmp_path: Path) -> None:
    store = ReplayEventStore(db_path=tmp_path / "replay.sqlite3")
    store.record(
        session_id="sess-1",
        event_type="compression",
        surface="test",
        detail={"tokens_before": 10, "tokens_after": 4, "savings": 6, "stage": "input_compressed"},
    )

    recovered = store.recover_recent_session_states(limit=1)

    assert recovered == {
        "session_count": 1,
        "sessions": [
            {
                "session_id": "sess-1",
                "event_count": 1,
                "first_event_id": 1,
                "last_event_id": 1,
                "compression": {"tokens_before": 10, "tokens_after": 4, "tokens_saved": 6},
                "prompt_count": 0,
                "input_message_count": 0,
                "input_token_count": 0,
                "llm_request_count": 0,
                "tool_call_count": 0,
                "tool_call_counts": {},
                "response_count": 0,
                "error_count": 0,
                "error_code_counts": {},
                "stream_completion_count": 0,
                "stream_truncation_count": 0,
            }
        ],
    }


def test_pipeline_extension_records_llm_request_sent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))
    reset_replay_store()

    ReplayPipelineExtension().on_pipeline_event(
        PipelineEvent(
            stage=PipelineStage.PRE_SEND,
            operation="proxy.request",
            request_id="req-1",
            provider="openai",
            model="gpt-test",
            metadata={"session_id": "sess-1"},
        )
    )

    events = ReplayEventStore(db_path=tmp_path / "replay.sqlite3").get("sess-1")["events"]

    assert len(events) == 1
    assert events[0] | {"timestamp": None} == {
        "event_id": 1,
        "timestamp": None,
        "session_id": "sess-1",
        "event_type": "llm_request_sent",
        "surface": "pipeline",
        "request_id": "req-1",
        "detail": {"model": "gpt-test", "provider": "openai", "stage": "pre_send"},
    }


def test_reduce_replay_events_counts_sent_requests_without_a_response() -> None:
    state = reduce_replay_events(
        [
            {
                "event_id": 1,
                "timestamp": 1.0,
                "event_type": "llm_request_sent",
                "detail": {"model": "gpt-test", "provider": "openai", "stage": "pre_send"},
            }
        ]
    )

    assert state["llm_request_count"] == 1
    assert state["latest_model"] == "gpt-test"
    assert state["response_count"] == 0


def test_reduce_replay_events_derives_prompt_usage_without_content() -> None:
    state = reduce_replay_events(
        [
            {
                "event_id": 1,
                "timestamp": 1.0,
                "event_type": "prompt_received",
                "detail": {
                    "message_count": 3,
                    "token_count": 42,
                    "model": "gpt-test",
                    "provider": "openai",
                },
            }
        ]
    )

    assert state["prompt_count"] == 1
    assert state["input_message_count"] == 3
    assert state["input_token_count"] == 42
    assert state["latest_model"] == "gpt-test"


def test_store_persists_only_prompt_metadata(tmp_path: Path) -> None:
    store = ReplayEventStore(db_path=tmp_path / "replay.sqlite3")

    store.record(
        session_id="sess-1",
        event_type="prompt_received",
        surface="openai",
        detail={
            "message_count": 3,
            "token_count": 42,
            "model": "gpt-test",
            "provider": "openai",
            "messages": [{"role": "user", "content": "must-not-persist"}],
            "api_key": "must-not-persist",
        },
    )

    assert store.get("sess-1")["events"][0]["detail"] == {
        "message_count": 3,
        "token_count": 42,
        "model": "gpt-test",
        "provider": "openai",
    }


def test_pipeline_extension_records_tool_call_names_without_arguments(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))
    reset_replay_store()

    ReplayPipelineExtension().on_pipeline_event(
        PipelineEvent(
            stage=PipelineStage.RESPONSE_RECEIVED,
            operation="proxy.request",
            request_id="req-1",
            provider="openai",
            response={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {"function": {"name": "search", "arguments": "must-not-persist"}}
                            ]
                        }
                    }
                ]
            },
            metadata={"session_id": "sess-1"},
        )
    )

    events = ReplayEventStore(db_path=tmp_path / "replay.sqlite3").get("sess-1")["events"]

    assert [event["event_type"] for event in events] == ["tool_call_detected", "response_received"]
    assert events[0]["detail"] == {"tool_name": "search"}
    assert events[1]["detail"] == {"model": "", "stage": "response_received"}


def test_reduce_replay_events_counts_detected_tool_calls() -> None:
    state = reduce_replay_events(
        [
            {"event_type": "tool_call_detected", "detail": {"tool_name": "search"}},
            {"event_type": "tool_call_detected", "detail": {"tool_name": "search"}},
            {"event_type": "tool_call_detected", "detail": {"tool_name": "read_file"}},
        ]
    )

    assert state["tool_call_count"] == 3
    assert state["tool_call_counts"] == {"search": 2, "read_file": 1}


def test_pipeline_extension_records_failed_response_without_error_payload(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))
    reset_replay_store()

    ReplayPipelineExtension().on_pipeline_event(
        PipelineEvent(
            stage=PipelineStage.RESPONSE_RECEIVED,
            operation="proxy.request",
            request_id="req-1",
            provider="openai",
            response={"error": {"message": "must-not-persist"}},
            metadata={"session_id": "sess-1", "status_code": 429},
        )
    )

    events = ReplayEventStore(db_path=tmp_path / "replay.sqlite3").get("sess-1")["events"]

    assert [event["event_type"] for event in events] == ["error", "response_received"]
    assert events[0]["detail"] == {"code": "http_429"}


def test_reduce_replay_events_derives_error_code_counts() -> None:
    state = reduce_replay_events(
        [
            {"event_type": "error", "detail": {"code": "http_429"}},
            {"event_type": "error", "detail": {"code": "http_429"}},
            {"event_type": "error", "detail": {"code": "http_500"}},
        ]
    )

    assert state["error_count"] == 3
    assert state["error_code_counts"] == {"http_429": 2, "http_500": 1}
