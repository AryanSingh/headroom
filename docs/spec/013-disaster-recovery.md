# 013. Disaster Recovery

**Status:** done

## Failure Modes

### Proxy Failures

| Failure | Impact | Recovery |
|---------|--------|----------|
| Proxy crash | Service unavailable | Restart or failover |
| OOM | Service unavailable | Restart with more memory |
| Network partition | Cannot reach providers | Retry with backoff |

### Compression Failures

| Failure | Impact | Recovery |
|---------|--------|----------|
| Compression timeout | Request delayed | Retry with passthrough |
| Transform error | Compression skipped | Log error, passthrough |
| Budget exceeded | Truncation | Notify via headers |

### Storage Failures

| Failure | Impact | Recovery |
|---------|--------|----------|
| SQLite corruption | Data loss | Restore from backup |
| Cache full | CCR disabled | Clear old entries |
| Disk full | Write failures | Expand storage |

---

## Backup Strategies

### Manual Backup

```bash
# Full backup
tar -czf cutctx-backup-$(date +%Y%m%d).tar.gz ~/.cutctx/

# Incremental (last 24h)
sqlite3 ~/.cutctx/cutctx_memory.db ".backup /tmp/cutctx_incremental.db"
```

### Automated Backup

```bash
# Cron job (daily at 2am)
0 2 * * * tar -czf /backup/cutctx-$(date +\%Y\%m\%d).tar.gz ~/.cutctx/
```

### External Storage

> **Note:** External PostgreSQL/Redis storage is not yet implemented. Cutctx uses SQLite at `~/.cutctx/` (configurable via `CUTCTX_WORKSPACE_DIR`). The `CUTCTX_DB_URL` and `CUTCTX_CACHE_BACKEND` vars do not exist.

---

## Recovery Procedures

### Proxy Recovery

1. **Restart proxy:**
```bash
# Docker
docker-compose restart cutctx

# Native
pkill cutctx && cutctx proxy &
```

2. **Check health:**
```bash
curl http://localhost:8787/health
curl http://localhost:8787/readyz
```

### Database Recovery

1. **Restore from backup:**
```bash
# Stop cutctx
pkill cutctx

# Restore SQLite
rm ~/.cutctx/cutctx_memory.db
tar -xzf cutctx-backup-20260416.tar.gz -C ~/

# Restart cutctx
cutctx proxy &
```

2. **Verify data:**
```bash
curl http://localhost:8787/stats
```

---

## Data Migration

### Schema Migration

```python
async def migrate_v1_to_v2():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            ALTER TABLE sessions
            ADD COLUMN agent_version TEXT
        """)
        await db.commit()
```

### Data Export/Import

```bash
# Export
curl http://localhost:8787/api/v1/export > backup.json

# Import
curl -X POST http://localhost:8787/api/v1/import \
  -H "Content-Type: application/json" \
  -d @backup.json
```

---

## High Availability

### Active-Active

```yaml
services:
  cutctx-1:
    image: cutctx-ai/cutctx:latest
    ports:
      - "8787:8787"

  cutctx-2:
    image: cutctx-ai/cutctx:latest
    ports:
      - "8788:8787"

  redis:
    image: redis:latest
```

### Health Check Failover

```bash
curl http://primary:8787/health || curl http://backup:8787/health
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0-draft | 2026-04-16 | Initial disaster recovery document |
