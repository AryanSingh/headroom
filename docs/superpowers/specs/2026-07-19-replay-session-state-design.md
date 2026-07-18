# Replay Session State Design

## Goal

Add a deterministic reducer that turns a persisted session replay timeline into a compact operational state document. The local-admin proxy API will expose the state without changing request processing, replay retention, or event storage.

## Reducer contract

`reduce_replay_events(events)` accepts the existing serialized replay events in event-ID order and returns one JSON-safe state object. The reducer performs no I/O, uses no wall-clock values, and never calls a model.

The state includes the session ID, event count, first and last event identifiers and timestamps, event-type counts, the latest request ID, the latest model and pipeline stage, compression totals (`tokens_before`, `tokens_after`, `tokens_saved`), response count, and policy block/redaction counts. Unknown event types contribute to event counts but do not alter specialized fields. Malformed or missing detail fields leave state unchanged.

## API

`GET /v1/sessions/{session_id}/state` shares the existing local-admin guard and replay-disabled response with the timeline endpoint. A session with no persisted events returns the existing `replay_not_found` 404 shape. A populated session returns the derived state directly.

## Boundary

The reducer uses only the sanitized fields already stored in the journal. It does not reintroduce prompt text, response content, tool payloads, arbitrary error messages, snapshots, processors, or background work. The endpoint offers a read model for operators and future dashboard work; it does not mutate the event journal.

## Tests

Test the pure reducer with a mixed event timeline, unknown event handling, and incomplete metadata. Test the endpoint for local-admin access, disabled behavior, missing sessions, and state persistence after store recreation. Each new behavior begins with a failing test.
