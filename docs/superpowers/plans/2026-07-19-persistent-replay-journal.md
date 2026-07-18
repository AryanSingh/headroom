# Persistent Replay Journal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` to implement each task through a failing test, minimal implementation, and focused verification.

**Goal:** Make the opt-in proxy session replay journal durable across restarts while preserving the existing replay API and preventing prompt or tool payload retention.

**Architecture:** `cutctx.proxy.session_replay` remains the sole record/read seam. A SQLite-backed store replaces process-local state only when `CUTCTX_REPLAY` enables it; all writers retain their existing helper calls. The journal uses an append-only event table, per-session read order, retention cleanup, and a fail-open recording boundary.

**Tech Stack:** Python 3.10+, standard-library `sqlite3`, FastAPI, pytest, existing CutCtx proxy pipeline.

## Global Constraints

- `CUTCTX_REPLAY` remains default-off and recording performs no database work when disabled.
- The journal stores structural metadata only. It excludes messages, response text, tool arguments/results, headers, keys, and arbitrary error text.
- Journal failures must not affect a proxied request.
- The replay endpoint keeps local-admin authentication and its existing disabled and missing-session responses.
- New behavior follows test-driven development: each test must fail for the missing behavior before the implementation change.

---

### Task 1: Durable, ordered SQLite event store

**Files:**

- Modify: `cutctx/proxy/session_replay.py`
- Create: `tests/test_session_replay.py`

**Interfaces:**

- Produces `ReplayEventStore(db_path: Path | str | None = None, ...)` with `record(...)`, `get(session_id)`, and `close()`.
- Produces `ReplayEvent.to_dict()` with `event_id`, `timestamp`, `session_id`, `event_type`, `surface`, `request_id`, and `detail`.

- [ ] **Step 1: Write a failing persistence-and-order test**

```python
def test_store_persists_events_in_append_order(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite3"
    store = ReplayEventStore(db_path=path)
    store.record(session_id="s1", event_type="first", surface="test")
    store.record(session_id="s1", event_type="second", surface="test")
    store.close()

    payload = ReplayEventStore(db_path=path).get("s1")

    assert [event["event_type"] for event in payload["events"]] == ["first", "second"]
    assert [event["event_id"] for event in payload["events"]] == [1, 2]
```

- [ ] **Step 2: Run the test and verify it fails because `db_path` and `close` do not exist**

Run: `pytest tests/test_session_replay.py::test_store_persists_events_in_append_order -v`

- [ ] **Step 3: Implement the minimal SQLite schema and store methods**

```python
CREATE TABLE IF NOT EXISTS replay_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_ms INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    surface TEXT NOT NULL,
    request_id TEXT,
    detail_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_replay_events_session_order
    ON replay_events(session_id, event_id);
```

- [ ] **Step 4: Re-run the test and verify it passes**

Run: `pytest tests/test_session_replay.py::test_store_persists_events_in_append_order -v`

### Task 2: Configuration, disabled behavior, and retention

**Files:**

- Modify: `cutctx/proxy/session_replay.py`
- Modify: `tests/test_session_replay.py`

**Interfaces:**

- `get_replay_store()` reads `CUTCTX_REPLAY_DB_PATH` and `CUTCTX_REPLAY_RETENTION_DAYS` only after `CUTCTX_REPLAY` enables replay.
- `ReplayEventStore(..., retention_days: int = 7)` preserves recent rows and removes expired rows at initialization and bounded append cadence.

- [ ] **Step 1: Write failing tests for a disabled no-op and retention**

```python
def test_disabled_replay_does_not_create_a_database(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_REPLAY", raising=False)
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))
    reset_replay_store()
    record_replay_event(session_id="s1", event_type="request", surface="test")
    assert not (tmp_path / "replay.sqlite3").exists()

def test_retention_removes_expired_events(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite3"
    store = ReplayEventStore(db_path=path, retention_days=7)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO replay_events (timestamp_ms, session_id, event_type, surface, request_id, detail_json) VALUES (?, ?, ?, ?, ?, ?)",
            (0, "old", "request", "test", None, "{}"),
        )
    store.record(session_id="new", event_type="request", surface="test")
    assert store.get("old")["event_count"] == 0
    assert store.get("new")["event_count"] == 1
```

- [ ] **Step 2: Run tests and verify the required behavior is absent**

Run: `pytest tests/test_session_replay.py -v`

- [ ] **Step 3: Implement environment-backed configuration and retention without test-only production methods**

Use a controlled SQLite fixture setup to seed old events. The store runs cleanup on initialization and every fixed number of successful appends. A non-positive retention setting disables cleanup.

- [ ] **Step 4: Re-run the test module and verify it passes**

Run: `pytest tests/test_session_replay.py -v`

### Task 3: Metadata allowlist and fail-open writes

**Files:**

- Modify: `cutctx/proxy/session_replay.py`
- Modify: `cutctx/providers/proxy_routes.py`
- Modify: `tests/test_session_replay.py`
- Modify: `tests/test_context_policy_proxy_integration.py`

**Interfaces:**

- `record_replay_event(..., detail)` persists only JSON-safe keys in the event-specific allowlist.
- `ReplayEventStore.record(...)` catches database errors, logs them, and returns `None`.

- [ ] **Step 1: Write failing payload-boundary and storage-failure tests**

```python
def test_record_drops_sensitive_and_unrecognized_detail_fields(tmp_path: Path) -> None:
    store = ReplayEventStore(db_path=tmp_path / "replay.sqlite3")
    store.record(
        session_id="s1", event_type="policy_blocked", surface="openai",
        detail={"matched_rules": ["deny"], "message": "secret prompt", "headers": {"x-api-key": "x"}},
    )
    assert store.get("s1")["events"][0]["detail"] == {"matched_rules": ["deny"]}

def test_record_returns_after_sqlite_failure(tmp_path: Path, monkeypatch) -> None:
    store = ReplayEventStore(db_path=tmp_path / "replay.sqlite3")
    monkeypatch.setattr(store, "_append", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")))
    store.record(session_id="s1", event_type="request", surface="test")
```

- [ ] **Step 2: Run tests and verify they fail on unfiltered or propagated data**

Run: `pytest tests/test_session_replay.py::test_record_drops_sensitive_and_unrecognized_detail_fields tests/test_session_replay.py::test_record_returns_after_sqlite_failure -v`

- [ ] **Step 3: Implement per-event structural allowlists and remove policy text at the writer**

Allow `matched_rules` for policy events; allow numeric token metrics and string model/strategy/stage identifiers for pipeline events. Drop all unknown keys, non-finite numbers, oversized strings, and nested values except a bounded list of rule identifiers.

- [ ] **Step 4: Re-run the focused tests and policy integration test**

Run: `pytest tests/test_session_replay.py tests/test_context_policy_proxy_integration.py -v`

### Task 4: Endpoint regression coverage and documentation

**Files:**

- Modify: `tests/test_context_policy_proxy_integration.py`
- Modify: `docs/content/docs/architecture.mdx`

**Interfaces:**

- Existing `GET /v1/sessions/{session_id}/replay` returns persisted events through its current local-admin-auth guard.

- [ ] **Step 1: Write a failing endpoint persistence test**

```python
def test_session_replay_api_reads_persisted_events(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_REPLAY", "1")
    monkeypatch.setenv("CUTCTX_REPLAY_DB_PATH", str(tmp_path / "replay.sqlite3"))
    reset_replay_store()
    record_replay_event(session_id="sess-1", event_type="request", surface="openai")
    reset_replay_store()
    app = create_app(ProxyConfig(admin_api_key="admin-secret"))
    with TestClient(app) as client:
        response = client.get("/v1/sessions/sess-1/replay", headers={"x-cutctx-admin-key": "admin-secret"})
    assert response.status_code == 200
    assert response.json()["events"][0]["event_type"] == "request"
```

- [ ] **Step 2: Run the test and verify that process-local storage cannot satisfy it**

Run: `pytest tests/test_context_policy_proxy_integration.py::test_session_replay_api_reads_persisted_events -v`

- [ ] **Step 3: Document the opt-in and privacy contract**

Add a short architecture note for `CUTCTX_REPLAY`, `CUTCTX_REPLAY_DB_PATH`, `CUTCTX_REPLAY_RETENTION_DAYS`, local-admin access, seven-day retention, and metadata-only storage.

- [ ] **Step 4: Run endpoint and documentation tests**

Run: `pytest tests/test_context_policy_proxy_integration.py tests/test_docs_proxy.py -v`

### Task 5: Release validation

**Files:**

- Verify: `cutctx/proxy/session_replay.py`
- Verify: `tests/test_session_replay.py`
- Verify: `tests/test_context_policy_proxy_integration.py`

- [ ] **Step 1: Run focused replay and policy coverage**

Run: `pytest tests/test_session_replay.py tests/test_context_policy_proxy_integration.py -v`

- [ ] **Step 2: Run static checks on changed Python files**

Run: `ruff check cutctx/proxy/session_replay.py cutctx/providers/proxy_routes.py tests/test_session_replay.py tests/test_context_policy_proxy_integration.py`

- [ ] **Step 3: Review the diff and verify the existing route response behavior**

Run: `git diff --check && git diff -- cutctx/proxy/session_replay.py cutctx/providers/proxy_routes.py tests/test_session_replay.py tests/test_context_policy_proxy_integration.py docs/content/docs/architecture.mdx`
