# Backup and Restore

Back up the persistent Cutctx state before an upgrade and after onboarding.
Keep encryption and orchestration keys outside the data archive.

## SQLite backup

Stop or drain proxy writes. For each required database, use SQLite's backup
command rather than copying a live WAL database:

```bash
sqlite3 /data/cutctx.db ".backup '/backup/cutctx.db'"
sqlite3 /data/cutctx_memory.db ".backup '/backup/cutctx_memory.db'"
sqlite3 /data/licenses.db ".backup '/backup/licenses.db'"
```

Archive configuration without secret values. Record the Cutctx version, image
digest, schema version, file checksum, owner, and UTC timestamp.

## Restore

1. Stop the proxy and preserve the failed state for investigation.
2. Restore the matching secret-manager entries and orchestration master key.
3. Restore database files to the documented persistent path and file owner.
4. Run an integrity check before startup:

```bash
sqlite3 /data/cutctx.db "PRAGMA integrity_check;"
sqlite3 /data/cutctx_memory.db "PRAGMA integrity_check;"
sqlite3 /data/licenses.db "PRAGMA integrity_check;"
```

5. Start the pinned release and verify `/readyz`, license status, one OpenAI
   request, and one Anthropic request.

## Docker and Kubernetes

For Docker, back up the named volume through a one-shot container that mounts
the volume read-only after the proxy stops. For Kubernetes, snapshot the PVC or
run a one-shot backup pod after scaling the deployment to zero. Restore the
Secret first, restore the PVC, then scale the deployment up.

A backup is accepted only after a restore drill succeeds and the operator
records its evidence path.

