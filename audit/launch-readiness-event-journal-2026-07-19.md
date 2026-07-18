# Persistent Replay Journal Launch Readiness — 2026-07-19

## Decision

**Conditional go for opt-in local and single-node proxy deployments.**

The persistent replay journal ships behind `CUTCTX_REPLAY=1`. The existing proxy behavior remains unchanged when the flag is absent or false. This addendum supplements, rather than replaces, the product-wide launch report in `audit/launch-readiness-report.md`.

## Sign-off checklist

| Item | Status | Evidence or operator action |
|---|---|---|
| Feature implementation | Signed | Commit `6e291c9` persists replay events in SQLite and preserves the authenticated read route. |
| Privacy | Signed | Event detail allowlists exclude prompt text, model output, tool data, headers, and API keys. |
| Documentation | Signed | `docs/content/docs/architecture.mdx` documents enablement, path, retention, endpoint access, and data boundary. |
| Local restart verification | Signed | An isolated SQLite probe wrote a compression event, recreated the store, and read one sanitized event: `local_restart_probe=passed`. |
| Automated tests | Signed | Final affected suite: 46 passed, 1 skipped. |
| Rollback | Signed | Set `CUTCTX_REPLAY=0` or remove the variable, then restart the proxy. Existing journal files remain available for operator-controlled retention or deletion. |
| Monitoring | Conditional | Collect `replay_init_failed`, `replay_record_failed`, `replay_read_failed`, and `replay_row_skipped` structured logs. A journal-specific metric and alert are not included in this phase. |
| Backup | Conditional | Configure host-level backup for `CUTCTX_REPLAY_DB_PATH` when replay records must survive host loss. The default is `~/.cutctx/replay.sqlite3`. |
| Staging deployment | Pending external target | No staging proxy URL, deployment credential, or managed backup target is configured in this workspace. Run the restart probe against the target before enabling the flag for users. |
| Compliance and support | Conditional | The journal provides local operational replay, not audit-grade immutability or distributed retention. Support runbooks should state this boundary. |

## Rollout

Start with one local or single-node proxy:

```bash
CUTCTX_REPLAY=1
CUTCTX_REPLAY_DB_PATH=/var/lib/cutctx/replay.sqlite3
CUTCTX_REPLAY_RETENTION_DAYS=7
```

After traffic reaches the proxy, use a local-admin credential to request `GET /v1/sessions/<session-id>/replay`. Restart the proxy and verify that the same endpoint still returns the session events. Promote only after the configured backup path and failure-log collection work in the deployment environment.

## No-go conditions

Do not enable this phase for a multi-node or compliance-grade deployment that requires cross-node consistency, remote durability, tamper-evident records, or an alert-backed durability SLO. Those requirements need the distributed event-store phase from the event-sourced harness design.
