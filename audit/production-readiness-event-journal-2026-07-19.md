# Persistent Replay Journal Production Readiness — 2026-07-19

## Scope and verdict

This assessment covers the opt-in SQLite-backed session replay journal introduced on `codex/event-journal-foundation`. It does not replace the repository-wide assessment in `audit/production-readiness.md`.

**Score: 86/100.** The feature is ready for an opt-in local or single-node proxy release. It is not a high-availability event store and must not be marketed as one until the distributed-store phase exists.

## Evidence

| Area | Result | Evidence |
|---|---|---|
| Enablement and rollback | Pass | `CUTCTX_REPLAY` remains disabled by default. Setting it false removes journal work from the request path. |
| Privacy boundary | Pass | The journal allowlists structural fields by event type; it excludes message text, model output, tool payloads, headers, and keys. `tests/test_session_replay.py` covers dropped unrecognized fields. |
| Access control | Pass | The existing replay route retains local-admin authentication, with regression coverage in `tests/test_context_policy_proxy_integration.py`. |
| Durability and recovery | Pass | SQLite persistence survives store recreation; rows return in database append order. |
| Concurrency | Pass with limit | WAL mode and a short busy timeout support independent local proxy workers. A locked or failed journal write logs a structured event and does not fail the proxied request. |
| Data lifecycle | Pass | Seven-day retention is the default, a positive setting deletes expired rows, and a non-positive setting disables time-based deletion. Existing event/session bounds remain in force. |
| Corruption handling | Pass | Malformed persisted rows are skipped rather than turning a replay read into an API error. |
| Monitoring and alerts | Partial | Structured logs report initialization, write, read, and malformed-row failures. No Prometheus counter or alert policy exists for journal failures. |
| Backup and restore | Partial | SQLite is local durable storage. Operators who require recovery after host loss must back up the configured journal path; the feature does not ship backup automation. |
| Deployment and rollback runbook | Pass | Set `CUTCTX_REPLAY=1`, optionally configure `CUTCTX_REPLAY_DB_PATH` and `CUTCTX_REPLAY_RETENTION_DAYS`, and protect the existing local-admin endpoint. Disable the flag to stop new writes; retain or delete the SQLite file under the operator's retention policy. |

## Validation run

The branch ran:

```text
pytest tests/test_session_replay.py tests/test_context_policy_proxy_integration.py tests/test_docs_proxy.py -v
15 passed, 1 skipped

ruff check cutctx/proxy/session_replay.py cutctx/providers/proxy_routes.py tests/test_session_replay.py tests/test_context_policy_proxy_integration.py
0 findings
```

The final affected-surface run expanded this to `46 passed, 1 skipped` across replay, context-policy, pipeline lifecycle, assurance, provider-route, and proxy documentation tests. The repository-wide MyPy invocation still reports 266 existing errors across 55 files. It reports none in `cutctx/proxy/session_replay.py`; the existing repository-wide MyPy debt remains a broader release gate.

## Release conditions

Ship the feature behind `CUTCTX_REPLAY=1` for local and single-node deployments. For multi-node or compliance retention use cases, require a configured backup policy and journal-failure log collection. Do not claim cross-node consistency, remote durability, audit-grade immutability, or processor execution support; those belong to later phases of the event-sourced harness design.
