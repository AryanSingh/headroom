# Persistent Replay Journal Design

## Purpose

CutCtx will persist a compact, ordered record of proxy request lifecycle events so an operator can inspect a session after the proxy restarts. The initial release extends the existing opt-in session replay feature. It does not run LLM requests during replay, execute user-supplied code, or provide a dashboard.

## Scope

The release includes:

- an opt-in SQLite journal behind the existing session replay seam;
- metadata-only event payloads for request, pipeline, compression, upstream-result, and error lifecycle points;
- per-session ordered reads through the existing local-admin-authenticated replay endpoint;
- SQLite schema initialization, bounded retention, and safe shutdown;
- compatibility with `CUTCTX_REPLAY=1` and no new work on the normal request path while replay is disabled.

The release excludes raw request messages, tool arguments and results, response content, processor deployment, reducer snapshots, distributed storage, and dashboard UI.

## Architecture

`cutctx.proxy.session_replay` remains the public integration point. Its in-memory `ReplayEventStore` becomes a narrow storage interface with a SQLite implementation selected when replay is enabled. Existing pipeline extensions and handler call sites keep using `record_replay_event`; they do not receive direct database access.

The SQLite table stores a monotonic event identifier, timestamp, session identifier, event type, and JSON payload. An index on `(session_id, event_id)` makes the existing replay route return one session in append order. A time index supports retention cleanup. Database writes run behind the store boundary so a journal failure is logged and does not fail the proxied request.

```text
provider handler / pipeline extension
              |
              v
     record_replay_event(...)
              |
              v
      ReplayEventStore interface
              |
              v
        SQLite event journal
              |
              v
GET /v1/sessions/{id}/replay (local admin auth)
```

## Event Contract

Each event contains:

- `event_id`: database-assigned append order;
- `timestamp`: UTC Unix milliseconds;
- `session_id`: the existing replay session identifier;
- `event_type`: a stable, documented lifecycle label;
- `payload`: a JSON object containing structural metadata only.

Payload values may include provider, model, token counts, compression strategy, cache or routing outcome, status code, error class, and bounded error code. Payloads must not include message text, image data, authorization headers, API keys, tool arguments, tool results, or model output. The event constructor performs the allowlist and rejects unsupported values before persistence.

## Configuration and Retention

`CUTCTX_REPLAY=1` keeps replay disabled by default and enables journal construction. A journal-path setting chooses a local SQLite file; a retention-days setting controls expiration. The default path lives under CutCtx's local data directory, and the default retention is seven days. A non-positive retention value disables deletion.

On initialization, the store creates its schema and indexes. On append, the store deletes expired rows at a bounded cadence rather than once per request. The store opens a fresh SQLite connection for each synchronous storage operation with a short busy timeout, which avoids sharing one connection across proxy threads. A write failure logs a structured error and returns control to the proxy.

## API Compatibility

`GET /v1/sessions/{session_id}/replay` retains its current local-admin-auth requirement and response shape: `session_id`, `event_count`, and `events`. A disabled journal returns the current `replay_disabled` 404 response. An empty session returns the current `replay_not_found` 404 response. Existing callers continue using the replay environment flag without code changes.

## Testing

Tests will drive the implementation in this order:

1. SQLite persistence survives a store re-creation and returns events in append order.
2. The disabled flag performs no database work and preserves the no-op recording contract.
3. The event allowlist rejects sensitive and non-JSON-safe payload fields before they reach SQLite.
4. Retention deletes expired rows without deleting recent events.
5. A storage failure does not change the proxied request outcome.
6. The authenticated replay route returns persisted events and preserves the disabled and missing-session responses.

Each test must fail before production code is written. Unit tests use temporary SQLite files and real store instances rather than mocks. Route coverage uses the existing FastAPI proxy test patterns.

## Migration

The initial change keeps `ReplayEventStore` as the compatibility name where feasible. The in-memory implementation can remain as a test utility, but the enabled runtime path uses SQLite. No existing data migration is needed because the current replay store is process-local and ephemeral.

## Risks and Controls

The journal could retain sensitive data or add latency. The payload allowlist, default-off switch, local-admin route guard, and fail-open storage boundary limit those risks. SQLite contention remains local to the journal and cannot block upstream provider traffic beyond the journal's short write attempt.
