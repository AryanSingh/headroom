# Savings Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove blocking per-request savings persistence without losing atomic snapshots or graceful-shutdown durability.

**Architecture:** `SavingsTracker` mutates in-memory state under its existing lock, then its asynchronous mode coalesces persistence in a single writer thread. The writer serializes a state snapshot and atomically fsyncs it outside proxy request completion; `flush()` provides a durability boundary and shutdown invokes it. Direct callers remain synchronous by default, while `PrometheusMetrics` explicitly selects asynchronous mode for the proxy hot path.

**Tech Stack:** Python 3.11+, `threading.Condition`, atomic temporary-file replacement, pytest.

## Global Constraints

- Default maximum flush interval: 250 ms.
- Proxy request completion must never call `_persist_snapshot` inline.
- Snapshots retain atomic temporary-file + `fsync` + replace semantics.
- `flush()` and proxy shutdown must make accepted updates durable or raise/log a persistence error.
- Synchronous mode preserves persistence-before-return semantics.

---

### Task 1: Tracker persistence contract

**Files:**
- Modify: `tests/test_savings_hot_path.py`
- Modify: `cutctx/proxy/savings_tracker.py`

**Interfaces:**
- Produces: `SavingsTracker.flush(timeout: float | None = None) -> bool`
- Produces: `SavingsTracker(..., persistence_mode="async" | "sync", flush_interval_seconds=0.25)`
- Produces: `_persist_snapshot(snapshot: dict[str, Any]) -> None`

- [ ] **Step 1: Write failing tests**

```python
def test_async_tracker_defers_disk_persistence_until_flush(tmp_path, monkeypatch):
    tracker = SavingsTracker(path=tmp_path / "savings.json", persistence_mode="async")
    persisted = []
    monkeypatch.setattr(tracker, "_persist_snapshot", lambda snapshot: persisted.append(snapshot))
    tracker.record_request(model="gpt-4o", input_tokens=10, tokens_saved=1)
    assert persisted == []
    assert tracker.flush(timeout=1)
    assert len(persisted) == 1

def test_sync_tracker_persists_before_record_request_returns(tmp_path, monkeypatch):
    tracker = SavingsTracker(path=tmp_path / "savings.json", persistence_mode="sync")
    persisted = []
    monkeypatch.setattr(tracker, "_persist_snapshot", lambda snapshot: persisted.append(snapshot))
    tracker.record_request(model="gpt-4o", input_tokens=10, tokens_saved=1)
    assert len(persisted) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_savings_hot_path.py -k 'defers_disk or sync_tracker' -q`

Expected: FAIL because `persistence_mode`, `flush`, or `_persist_snapshot` does not exist.

- [ ] **Step 3: Implement minimal coalescing writer and production selection**

```python
def _mark_dirty_locked(self) -> None:
    self._dirty_generation += 1
    if self._persistence_mode == "sync":
        self._persist_snapshot(self._snapshot_locked())
        self._persisted_generation = self._dirty_generation
    else:
        self._write_condition.notify()

def flush(self, timeout: float | None = None) -> bool:
    # Signal the writer and wait until persisted_generation reaches the
    # generation captured at entry, raising a retained writer error.
```

The writer waits up to `flush_interval_seconds`, captures a copy of the state
under the lock, then calls `_persist_snapshot` after releasing it.
`PrometheusMetrics.__init__` constructs `SavingsTracker(persistence_mode="async")`
when no tracker is injected; injected and direct trackers retain the default
strict behavior.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_savings_hot_path.py -k 'defers_disk or sync_tracker' -q`

Expected: PASS.

### Task 2: Coalescing, failure, and shutdown behavior

**Files:**
- Modify: `tests/test_savings_hot_path.py`
- Modify: `tests/test_proxy_pipeline_lifecycle.py`
- Modify: `cutctx/proxy/savings_tracker.py`
- Modify: `cutctx/proxy/server.py`

**Interfaces:**
- Consumes: `SavingsTracker.flush()` and `SavingsTracker.close()`.
- Produces: `CutctxProxy.shutdown()` flushing its `metrics.savings_tracker`.

- [ ] **Step 1: Write failing tests**

```python
def test_flush_coalesces_many_updates_into_latest_snapshot(tmp_path, monkeypatch):
    tracker = SavingsTracker(path=tmp_path / "savings.json", persistence_mode="async", flush_interval_seconds=60)
    calls = []
    monkeypatch.setattr(tracker, "_persist_snapshot", lambda snapshot: calls.append(snapshot))
    for _ in range(3):
        tracker.record_request(model="gpt-4o", input_tokens=10, tokens_saved=1)
    assert tracker.flush(timeout=1)
    assert len(calls) == 1
    assert calls[0]["lifetime"]["requests"] == 3

def test_flush_surfaces_writer_failure(tmp_path, monkeypatch):
    tracker = SavingsTracker(path=tmp_path / "savings.json", persistence_mode="async")
    monkeypatch.setattr(tracker, "_persist_snapshot", lambda snapshot: (_ for _ in ()).throw(OSError("disk full")))
    tracker.record_request(model="gpt-4o", input_tokens=10, tokens_saved=1)
    with pytest.raises(OSError, match="disk full"):
        tracker.flush(timeout=1)
```

Add a shutdown test that dirties the proxy tracker, calls `asyncio.run(proxy.shutdown())`, then reopens the savings file and observes the update.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_savings_hot_path.py -k 'coalesces or surfaces_writer_failure' tests/test_proxy_pipeline_lifecycle.py -q`

Expected: FAIL because writes are still inline and shutdown has no flush boundary.

- [ ] **Step 3: Implement lifecycle and error behavior**

```python
def close(self) -> None:
    self.flush()
    with self._write_condition:
        self._writer_stopping = True
        self._write_condition.notify_all()
    self._writer.join(timeout=5)

async def shutdown(self):
    self.metrics.savings_tracker.close()
    # Existing shutdown work follows.
```

Writer exceptions are retained, wake all waiters, and are re-raised by
`flush()`; the writer remains available for a later successful write.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_savings_hot_path.py -k 'coalesces or surfaces_writer_failure' tests/test_proxy_pipeline_lifecycle.py -q`

Expected: PASS.

### Task 3: Regression and throughput verification

**Files:**
- Modify: `benchmarks/README.md` only if behavior/configuration needs user-facing documentation.
- Test: `tests/test_proxy_savings_history.py`, `tests/test_savings_hot_path.py`, `tests/test_proxy_pipeline_lifecycle.py`, `tests/test_proxy_request_benchmark.py`

- [ ] **Step 1: Run focused regression suite**

Run: `pytest tests/test_savings_hot_path.py tests/test_proxy_savings_history.py tests/test_savings_corruption_recovery.py tests/test_savings_tracker_cross_process.py tests/test_proxy_pipeline_lifecycle.py tests/test_proxy_request_benchmark.py -q`

Expected: PASS.

- [ ] **Step 2: Run the request-path benchmark at two concurrencies**

Run: `.venv/bin/python benchmarks/proxy_request_benchmark.py --requests 50 --concurrency 1 --warmup 5` and `.venv/bin/python benchmarks/proxy_request_benchmark.py --requests 100 --concurrency 20 --warmup 10`

Expected: both runs have zero failures, and the higher-concurrency run no longer has the previous ~7–8 request/sec ceiling caused by per-request fsync.

- [ ] **Step 3: Commit**

```bash
git add cutctx/proxy/savings_tracker.py cutctx/proxy/server.py \
  tests/test_savings_hot_path.py tests/test_proxy_pipeline_lifecycle.py \
  benchmarks/README.md
git commit -m "fix: move savings persistence off request path"
```
