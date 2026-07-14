# Savings persistence hot-path design

## Goal

Remove synchronous JSON serialization and `fsync` from proxy request completion
while retaining atomic, observable, bounded-delay durability for the savings
ledger.

## Chosen design

`SavingsTracker` continues to update its in-memory state synchronously under
its existing lock. In asynchronous mode, a successful mutation adds a compact
state patch to an append journal and signals one dedicated writer thread. The
writer waits up to 250 ms to coalesce patches, appends the batch, and fsyncs
the small journal file outside the request path. Full JSON snapshots are
atomically compacted on graceful shutdown and explicit history/export reads.
Startup loads the last snapshot and replays the journal before accepting
traffic. Direct tracker construction remains synchronous by default for CLI
and library compatibility; production `PrometheusMetrics` explicitly
constructs its tracker in asynchronous mode.

`flush()` waits for the pending snapshot to be durable and reports any writer
failure. Proxy shutdown calls `flush()` before the process exits. A synchronous
mode remains available for deployments that explicitly require per-request
durability; it uses the existing atomic persistence behavior.

## Invariants

- Proxy request outcome handling never performs disk I/O in its explicitly
  configured asynchronous mode.
- Journal batches are append-only and fsynced; compacted snapshots remain
  complete, atomically replaced JSON documents.
- `flush()` and graceful shutdown make all accepted updates durable.
- Writer errors are retained and surfaced by `flush()` instead of being lost.
- Existing direct `SavingsTracker` callers remain synchronous by default for
  compatibility and strict-durability deployments.

## Tests

1. An asynchronous tracker returns from `record_request()` without invoking the disk
   writer inline, then makes its patch durable after `flush()`.
2. Multiple writes before a flush coalesce to one durable journal batch whose
   replay contains the latest state.
3. Synchronous mode persists before `record_request()` returns.
4. A write error is raised by `flush()` and never leaves a waiter blocked.
5. Proxy shutdown flushes and compacts dirty savings state; startup replays an
   un-compacted journal after an abrupt stop.
