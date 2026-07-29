# Migration and Scaling Verification — Task 9 Assessment

- **Date (UTC):** 2026-07-29
- **Worktree:** `verified-production-remediation`
- **SHA at assessment:** `ef541733bb4ac9af7fd36d217d48ca64d869e55e`
- **Plan reference:** `docs/superpowers/plans/2026-07-29-verified-production-remediation-backlog.md` (Task 9)
- **Policy:** Evidence only — nothing in this document claims staging restore, Postgres upgrade, or multi-replica load tests were run unless explicitly marked **RUN**.

---

## Executive summary

| Acceptance criterion | Status | Notes |
|---|---|---|
| Oldest supported schema → current upgrade tested | **NOT RUN** | Tooling and unit tests exist; no live Postgres or legacy SQLite snapshot exercise in this session |
| Backup/restore demonstrated in staging | **NOT RUN** | Backup CronJob and verify script exist; no restore drill recorded |
| Rollback decision documented | **UNKNOWN** | Requires operations/product owner |
| `maxReplicas: 1` constraint preserved and explained | **CONFIRMED** | Comment present in `k8s/hpa.yaml`; architecture unchanged |

---

## 1. Upgrade / migration path (what exists today)

Cutctx has **two independent migration systems**. They must not be conflated.

### 1a. Hosted Postgres (Supabase telemetry / dashboard)

**Runner:** `scripts/migrate.py`

**Mechanism:**

- Ordered manifest (`MIGRATIONS` tuple) — not alphabetical discovery.
- Bookkeeping table `schema_migrations` (filename, checksum, applied_at).
- Checksum drift detection via `verify`.
- `--baseline` for databases already migrated manually through the Supabase SQL editor.
- One transaction per migration; failure rolls back the current step and leaves earlier steps applied (resumable).

**Registered migrations (dependency order):**

| # | File | Purpose |
|---|---|---|
| 1 | `create_proxy_telemetry_v2.sql` | Base telemetry table |
| 2 | `create_dashboard_summary.sql` | Dashboard summary + hourly refresh (requires `pg_cron`) |
| 3 | `upgrade_dashboard_v2.sql` | Dashboard v2 patches |
| 4 | `upgrade_telemetry_cache_bust.sql` | Telemetry cache-bust columns |
| 5 | `upgrade_telemetry_stack_context.sql` | `cutctx_stack`, `install_mode`, `requests_by_stack` columns |

**Prerequisites (from runner docstring):** Supabase provides `anon` role and `pg_cron`. On vanilla `postgres:16`, create `anon` and preload `pg_cron`, or edit `create_dashboard_summary.sql` to drop cron scheduling.

**Unit-test coverage (this session — RUN):**

```bash
pytest -q tests/test_sql_migrations.py tests/test_sqlite_schema_migrations.py tests/test_sqlite_schema_versions.py
```

Result: **35 passed** (manifest guards, idempotency checks, dry `plan`/`verify`, SQLite schema migration framework tests).

**Manifest dry-run (this session — RUN):**

```bash
python3 scripts/migrate.py plan
```

Output (abridged):

```
Migration order:
  1. create_proxy_telemetry_v2.sql  sha256:fc62b9b05615
  2. create_dashboard_summary.sql  sha256:6fcf6f0b4553
  3. upgrade_dashboard_v2.sql  sha256:6de3501536e2
  4. upgrade_telemetry_cache_bust.sql  sha256:d0ae628d909d
  5. upgrade_telemetry_stack_context.sql  sha256:e6216ef24913

No DATABASE_URL / SUPABASE_DB_URL set — this is a dry plan only.
```

**Oldest → current upgrade test (this session — NOT RUN):**

The runner docstring states all five migrations were previously verified against stock `postgres:16`, but **this session did not reproduce that end-to-end test**. No `DATABASE_URL` was set; no Docker Postgres container was started; no legacy schema snapshot with production-like rows was migrated and queried for data preservation.

**Exact command to satisfy Task 9 Step 1 acceptance:**

```bash
# 1. Start a clean Postgres 16 instance with pg_cron preloaded (or use Supabase staging).
docker run --rm -d --name cutctx-migrate-test \
  -e POSTGRES_PASSWORD=postgres \
  -p 5433:5432 postgres:16

# 2. Create prerequisites on vanilla Postgres (skip on Supabase):
#    CREATE ROLE anon NOINHERIT;
#    (configure shared_preload_libraries = 'pg_cron' and restart if testing cron)

# 3. Apply from empty (simulates fresh deploy):
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5433/postgres
python3 scripts/migrate.py apply

# 4. Verify idempotency (must be no-op):
python3 scripts/migrate.py apply

# 5. Verify checksums:
python3 scripts/migrate.py verify

# 6. For hand-migrated DBs, test baseline adoption:
#    (reset DB or use a copy that already has objects but no schema_migrations row)
python3 scripts/migrate.py apply --baseline
python3 scripts/migrate.py verify

# 7. Teardown:
docker stop cutctx-migrate-test
```

**Failure recovery path (documented in runner, not exercised here):** A failed `apply` rolls back the failing migration's transaction; `schema_migrations` records only completed steps; re-run `apply` resumes from the first pending file.

### 1b. Local SQLite stores (proxy workspace / `~/.cutctx`)

**Framework:** `cutctx/storage/sqlite_schema.py`

- Uses `PRAGMA user_version` per store.
- `@register_migration(store_name, target_version)` registry.
- `upgrade_schema()` applies steps in order, commits after each step (resumable).
- Refuses to open databases newer than the runtime supports.
- Refuses version gaps without registered migrations (no silent stamp).

**Consumers include:** `cutctx/storage/sqlite.py` (metrics), and other SQLite-backed stores listed in `audit/database-analysis.md`.

**Unit-test coverage:** `tests/test_sqlite_schema_migrations.py`, `tests/test_sqlite_schema_versions.py` — included in the 35-test run above.

**Oldest → current SQLite upgrade (this session — NOT RUN):** No legacy on-disk snapshot (e.g. pre-migration `cutctx_memory.db` from an older release) was opened, upgraded, and validated for row preservation across all 17+ workspace databases.

**Exact command to satisfy acceptance (representative; repeat per store with registered migrations):**

```bash
# Copy a known-old database snapshot to a temp path, then open with current Cutctx:
pytest -q tests/test_sqlite_schema_migrations.py  # framework regression
# Plus a manual/integration step per store:
#   1. cp <legacy-snapshot>/<store>.db /tmp/upgrade-test.db
#   2. Open with the store's Python adapter (triggers stamp_schema_version / upgrade_schema)
#   3. Assert PRAGMA user_version matches current expected version
#   4. Assert row counts / spot-check critical tables unchanged
```

> **Note:** `audit/database-analysis.md` (2026-07-10) predates the `sqlite_schema.py` migration registry and still describes ad-hoc column adds. The registry exists now, but a full multi-store oldest→current drill has not been recorded.

---

## 2. Backup / restore story

### What exists

| Artifact | Role |
|---|---|
| `k8s/backup-cronjob.yaml` | Daily (`0 0 * * *` UTC) CronJob; `sqlite3 .backup` for 17 workspace SQLite files on the RWO PVC; uploads to `s3://cutctx-backups/`; 30-day S3 retention prune in the same job |
| `k8s/pvc.yaml` | `ReadWriteOnce`, 10 Gi — single-node attach only |
| `k8s/deployment.yaml` | Mounts PVC at `/home/nonroot/.cutctx`; `replicas: 1` |
| `scripts/verify-backup.sh` | Local or S3 integrity verification (`PRAGMA integrity_check`, size/table checks); `--s3-bucket`, `--strict`, `--dry-run` modes |

**Databases covered by backup CronJob and verify script (kept in sync):**

`cutctx.db`, `cutctx_memory.db`, `cutctx_memory_graph.db`, `cutctx_memory_vectors.db`, `spend_ledger.db`, `audit.db`, `rbac.db`, `org.db`, `fleet.db`, `scim.db`, `ccr.db`, `prefix_tracker.db`, `assurance.ledger.db`, `episodes.db`, `policies.db`, `secrets.db`, `webhooks.db`, `webhook_dlq.db`

**Postgres (Supabase):** No in-repo automated backup/restore procedure for the hosted schema. Supabase platform backups are out of scope for this repository audit.

### What was run this session

| Check | Status | Evidence |
|---|---|---|
| `./scripts/verify-backup.sh --dry-run` | **RUN** | Exit 0; integrity dry-checks against local `~/.cutctx` databases |
| S3 backup download + verify | **NOT RUN** | Requires `aws-cli` credentials and `cutctx-backups` bucket access |
| Restore from S3/local backup into a fresh PVC | **NOT RUN** | No restore runbook or script found in `k8s/`, `scripts/`, or `docs/` |
| Staging restore drill | **NOT RUN** | No staging cluster access in this session |

### Restore procedure (inferred, not verified)

A plausible but **untested** operator sequence:

1. Scale `cutctx-proxy` deployment to 0 replicas.
2. Copy backup `.db` files from S3 (or local backup) onto the PVC mount path (`/home/nonroot/.cutctx` in the pod, `/data` in the backup CronJob).
3. Run `./scripts/verify-backup.sh` against restored files.
4. Scale deployment back to 1 replica.

**This sequence has not been demonstrated.** Do not treat it as validated.

### Rollback decision

| Question | Status |
|---|---|
| Is binary/schema **downgrade** supported? | **UNKNOWN** — needs team decision |
| Is **restore-from-backup** the required rollback path? | **LIKELY** for SQLite state (no downgrade tooling found), but **not formally adopted** |
| Postgres rollback on failed migration? | Forward-only; re-run `apply` after fix; no `down` migration; restore from Supabase backup if needed |

**Action required:** Operations owner must record whether release rollback means (a) redeploy previous image only, (b) restore PVC from S3, (c) Supabase point-in-time restore, or (d) combination — and which cases are acceptable data-loss windows.

---

## 3. Horizontal scaling constraint (`maxReplicas: 1`)

### Status: **CONFIRMED — unchanged, intentional**

`k8s/hpa.yaml` documents the constraint inline:

```yaml
  # Do not scale a ReadWriteOnce-backed deployment above one replica. Enable
  # this HPA only after migrating state to shared RWX/external storage.
  minReplicas: 1
  maxReplicas: 1
```

Supporting context (not modified):

- `k8s/pvc.yaml` — `accessModes: [ReadWriteOnce]`
- `k8s/deployment.yaml` — `# The bundled PVC is ReadWriteOnce. Deploy one replica by default; use a shared RWX volume/external state backend before enabling horizontal scale.` with `replicas: 1`

The remediation backlog explicitly rejects treating `maxReplicas: 1` as a bug: it is a storage-safety constraint until state moves off single-node RWO SQLite.

### Multi-replica path (not implemented — design required)

Enabling `maxReplicas > 1` requires a **separate design/implementation plan**, including at minimum:

1. **Shared state:** RWX volume and/or external stores (Redis, Postgres, S3) for all data currently in the 17 local SQLite files.
2. **Session ownership:** Sticky sessions or leader-elected writers so concurrent pods do not corrupt SQLite.
3. **Backup model:** Replace per-pod SQLite backup with shared-store backup semantics.
4. **Load/failure tests:** Multi-replica HPA scale-up/down, pod kill during write, and backup consistency under concurrent access.

**No architecture changes were made in this assessment.**

---

## 4. Session evidence log

| Command | When | Result |
|---|---|---|
| `python3 scripts/migrate.py plan` | This session | PASS (dry plan, 5 migrations listed) |
| `python3 scripts/migrate.py verify` (no `DATABASE_URL`) | This session | PASS (manifest only) |
| `pytest -q tests/test_sql_migrations.py tests/test_sqlite_schema_migrations.py tests/test_sqlite_schema_versions.py` | This session | **35 passed** |
| `./scripts/verify-backup.sh --dry-run` | This session | PASS (local integrity dry-check) |
| Postgres `apply` oldest→current with data check | This session | **NOT RUN** |
| Backup restore drill (local or staging) | This session | **NOT RUN** |
| Multi-replica / HPA scale test | This session | **NOT RUN** (and not desired without RWX plan) |

---

## 5. Open items for team ownership

1. **Run Postgres migration acceptance** using the exact commands in §1a; attach output to this file or a linked ops evidence doc.
2. **Run SQLite oldest-snapshot upgrade** per critical store; record which legacy versions are still supported.
3. **Author a restore runbook** (or extend `scripts/verify-backup.sh` with a documented restore companion) and execute one staging drill.
4. **Record rollback policy** — downgrade vs restore-from-backup — in an ops-owned document; update this file when decided.
5. **If horizontal scale is desired:** open a dedicated design issue for RWX/external state; do not raise `maxReplicas` until that plan ships.

---

## 6. Relation to other audit artifacts

- `audit/release-evidence-2668582c35da84acc38a7396eabc4eceb32eedd4.md` — Task 9 explicitly deferred at that SHA; this document is the Task 9 assessment for the current remediation worktree.
- `audit/database-analysis.md` (2026-07-10) — historical SQLite gap analysis; partially superseded by `cutctx/storage/sqlite_schema.py` but still relevant for WAL/consistency notes on individual stores.
