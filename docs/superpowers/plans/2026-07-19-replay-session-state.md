# Replay Session State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` for each behavior change.

**Goal:** Expose deterministic per-session operational state derived from persisted replay events.

**Architecture:** A pure reducer in `cutctx/proxy/session_replay.py` folds the sanitized event dictionaries returned by `ReplayEventStore.get`. The existing FastAPI server calls that reducer behind its local-admin guard and returns its result through a new state route.

**Tech Stack:** Python 3.10+, FastAPI, pytest, SQLite-backed replay store.

## Global Constraints

- The reducer performs no I/O and depends only on event order and sanitized event data.
- Unknown event types count toward the timeline without changing specialized state.
- Disabled and missing-session responses retain the replay API's current 404 contracts.
- No raw prompt, response, tool, header, or key material enters reducer state.

---

### Task 1: Pure replay reducer

**Files:**

- Modify: `cutctx/proxy/session_replay.py`
- Modify: `tests/test_session_replay.py`

**Interfaces:**

- Produces `reduce_replay_events(events: Iterable[Mapping[str, Any]]) -> dict[str, Any]`.

- [ ] **Step 1: Write a failing mixed-event reducer test**

```python
events = [
    {"event_id": 1, "timestamp": 1.0, "request_id": "r1", "event_type": "compression", "detail": {"tokens_before": 10, "tokens_after": 4, "savings": 6, "stage": "input_compressed"}},
    {"event_id": 2, "timestamp": 2.0, "event_type": "response_received", "detail": {"model": "gpt-test"}},
    {"event_id": 3, "timestamp": 3.0, "event_type": "policy_blocked", "detail": {}},
]
assert reduce_replay_events(events)["compression"]["tokens_saved"] == 6
```

- [ ] **Step 2: Run the focused test and verify that importing the reducer fails**

Run: `pytest tests/test_session_replay.py::test_reduce_replay_events_derives_session_state -v`

- [ ] **Step 3: Implement the minimal reducer**

It returns `event_count`, event bounds, latest request/model/stage, event-type counts, compression totals, response count, and policy counts. It ignores malformed details and unknown event types apart from their count.

- [ ] **Step 4: Re-run the reducer tests**

Run: `pytest tests/test_session_replay.py -v`

### Task 2: Guarded state endpoint

**Files:**

- Modify: `cutctx/proxy/server.py`
- Modify: `tests/test_context_policy_proxy_integration.py`

**Interfaces:**

- Produces `GET /v1/sessions/{session_id}/state` under `_require_local_admin_auth`.

- [ ] **Step 1: Write a failing state-route persistence test**

```python
response = client.get("/v1/sessions/sess-1/state", headers={"x-cutctx-admin-key": "admin-secret"})
assert response.status_code == 200
assert response.json()["compression"]["tokens_saved"] == 6
```

- [ ] **Step 2: Run the focused test and verify it receives 404 because the route is absent**

Run: `pytest tests/test_context_policy_proxy_integration.py::test_session_state_api_reads_persisted_events -v`

- [ ] **Step 3: Add the route using the existing disabled and missing-session responses**

- [ ] **Step 4: Re-run endpoint and replay tests**

Run: `pytest tests/test_session_replay.py tests/test_context_policy_proxy_integration.py -v`

### Task 3: Documentation and validation

**Files:**

- Modify: `docs/content/docs/architecture.mdx`

- [ ] **Step 1: Document the local-admin state endpoint and its derived-data boundary**

- [ ] **Step 2: Run affected validation**

Run: `pytest tests/test_session_replay.py tests/test_context_policy_proxy_integration.py tests/test_proxy_pipeline_lifecycle.py tests/test_docs_proxy.py -v && ruff check cutctx/proxy/session_replay.py cutctx/proxy/server.py tests/test_session_replay.py tests/test_context_policy_proxy_integration.py`
