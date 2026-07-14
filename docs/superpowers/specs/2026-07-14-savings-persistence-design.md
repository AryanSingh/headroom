# Savings persistence hot-path design

## Goal

Remove synchronous JSON serialization and `fsync` from proxy request completion
while retaining atomic, observable, bounded-delay durability for the savings
ledger.

## Chosen design

`SavingsTracker` continues to update its in-memory state synchronously under
its existing lock. A successful mutation marks the state dirty and signals one
dedicated writer thread. The writer waits up to 250 ms to coalesce further
updates, snapshots the state under the lock, and performs the existing atomic
temporary-file, `fsync`, and rename sequence outside the request path.

`flush()` waits for the pending snapshot to be durable and reports any writer
failure. Proxy shutdown calls `flush()` before the process exits. A synchronous
mode remains available for deployments that explicitly require per-request
durability; it uses the existing atomic persistence behavior.

## Invariants

- Request outcome handling never performs disk I/O in the default mode.
- Persisted snapshots remain complete, atomically replaced JSON documents.
- `flush()` and graceful shutdown make all accepted updates durable.
- Writer errors are retained and surfaced by `flush()` instead of being lost.
- Existing direct `SavingsTracker` callers retain a synchronous mode for
  compatibility and strict-durability deployments.

## Tests

1. A default tracker returns from `record_request()` without invoking the disk
   writer inline, then persists after `flush()`.
2. Multiple writes before a flush coalesce to one durable snapshot containing
   the latest state.
3. Synchronous mode persists before `record_request()` returns.
4. A write error is raised by `flush()` and never leaves a waiter blocked.
5. Proxy shutdown flushes dirty savings state.
