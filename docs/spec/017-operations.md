# 017. Operations

**Status:** done

## Health Endpoints

### `GET /health`

Aggregate public health check. Returns 200 when the proxy is ready and 503
when a required subsystem or upstream check is unhealthy. Public health
responses deliberately omit provider URLs and raw transport errors.

```bash
curl http://localhost:8787/health
```

**Response:**
```json
{
  "service": "cutctx-proxy",
  "status": "healthy",
  "ready": true,
  "alive": true,
  "version": "0.31.0"
}
```

Use authenticated `GET /health/config` for operator-only configuration and
upstream diagnostics. Do not expose that route through an unauthenticated
ingress.

---

### `GET /livez`

Liveness check. Returns 200 if process is alive.

```bash
curl http://localhost:8787/livez
```

---

### `GET /readyz`

Readiness check. Returns 200 if ready to serve traffic.

```bash
curl http://localhost:8787/readyz
```

**Response:**
```json
{
  "ready": true,
  "checks": {
    "database": true,
    "cache": true,
    "provider": true
  }
}
```

---

## Logs

### Log Locations

| Installation | Location |
|-------------|----------|
| Docker | `docker logs cutctx` |
| Native | `~/.cutctx/logs/` |
| Systemd | `journalctl -u cutctx` |

### Log Levels

Set via CLI flag or `RUST_LOG` env var for the Rust proxy:
```bash
# Python proxy
cutctx proxy --log-level debug

# Rust proxy
RUST_LOG=debug cutctx-proxy --upstream http://...
```

---

## Metrics

### Prometheus

**Scrape Config:**
```yaml
scrape_configs:
  - job_name: 'cutctx'
    static_configs:
      - targets: ['localhost:8787']
    metrics_path: '/metrics'
```

---

## Upgrade Procedure

Never upgrade from a floating image without first recording the running
version and taking a restorable copy of the Cutctx state directory or mounted
volume. Set explicit versions from the release page:

```bash
export PREVIOUS_VERSION="0.31.0"
export TARGET_VERSION="0.32.0"
cp -a ~/.cutctx "${HOME}/.cutctx.pre-${TARGET_VERSION}"
```

Keep the backup until the upgraded service has passed the readiness and a
representative provider request. Database formats are not guaranteed to be
backward-compatible after a newer process has written them.

### Docker

```bash
docker pull "ghcr.io/cutctx/cutctx:${TARGET_VERSION}"
# Change the deployment image to the exact TARGET_VERSION tag.
docker-compose down
docker-compose up -d
curl --fail --show-error http://localhost:8787/readyz
```

### Native

```bash
pip install --upgrade "cutctx-ai[proxy]==${TARGET_VERSION}"
# Restart cutctx service
curl --fail --show-error http://localhost:8787/readyz
```

### Embedded

```bash
pip install --upgrade "cutctx-ai[proxy]==${TARGET_VERSION}"
# Restart application
```

---

## Rollback

Stop writes before rollback. If the upgraded process wrote persistent state,
stop it and restore the pre-upgrade state copy before starting the older
version. Do not delete the pre-upgrade backup until the rollback and a
representative provider request have both succeeded.

### Docker

```bash
docker-compose down
# Restore the pre-upgrade state volume/directory when required.
docker pull "ghcr.io/cutctx/cutctx:${PREVIOUS_VERSION}"
# Change the deployment image to the exact PREVIOUS_VERSION tag.
docker-compose up -d
curl --fail --show-error http://localhost:8787/readyz
```

Never create a rollback tag from `latest`: after a pull, that tag points to the
new image rather than the known-good image. Pin the previous release tag (or,
for stricter immutability, the recorded `sha256:` digest) in the deployment.

### Native / Embedded

```bash
# Stop the service/application first and restore ~/.cutctx from the backup
# when the newer version may have changed persistent state.
pip install --force-reinstall "cutctx-ai[proxy]==${PREVIOUS_VERSION}"
# Restart the service/application, then verify it.
curl --fail --show-error http://localhost:8787/readyz
```

---

## Monitoring

### Key Metrics to Watch

1. **Request rate** — requests per second
2. **Error rate** — 4xx + 5xx / total
3. **Savings rate** — average savings percentage
4. **Latency** — p50, p95, p99
5. **Cache hit rate** — hits / total

**Prometheus queries:**
```promql
# Request rate
rate(cutctx_requests_total[5m])

# Error rate
rate(cutctx_errors_total[5m]) / rate(cutctx_requests_total[5m])

# Average savings
rate(cutctx_tokens_original[5m] - cutctx_tokens_compressed[5m]) / rate(cutctx_tokens_original[5m])

# Cache hit rate
rate(cutctx_cache_hits_total[5m]) / (rate(cutctx_cache_hits_total[5m]) + rate(cutctx_cache_misses_total[5m]))
```

---

## Runbook

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Connection refused" | Proxy not running | Start it with `cutctx proxy` |
| "Cache miss on every request" | Cache disabled | Start without `--no-cache` |
| "No savings shown" | Database locked | Check file permissions |
| "Provider timeout" | Network issue | Check firewall/proxy |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0-draft | 2026-04-16 | Initial operations document |
