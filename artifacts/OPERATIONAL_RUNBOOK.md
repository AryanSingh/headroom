# Headroom Operational Runbook

## 1. Deployment Checklist

### Prerequisites
- [ ] Docker image built: `docker build -t headroom-proxy .`
- [ ] License key obtained from hello@headroomlabs.ai
- [ ] Upstream API key (Anthropic/OpenAI) configured
- [ ] Admin API key generated (for dashboard/stats access)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HEADROOM_PROXY_COMPRESSION` | `false` | Enable compression (set to `1`) |
| `HEADROOM_PROXY_COMPRESSION_MODE` | `off` | `live-zone` for production |
| `HEADROOM_LICENSE_KEY` | — | License key (required for commercial use) |
| `HEADROOM_ADMIN_API_KEY` | — | Admin auth for /dashboard, /stats |
| `HEADROOM_CORS_ORIGINS` | `""` (closed) | Comma-separated origins, or `*` |
| `HEADROOM_MAX_BODY_MB` | `50` | Max request body size in MB |
| `HEADROOM_TELEMETRY_ENABLED` | `false` | Opt-in usage telemetry |
| `HEADROOM_EPISODIC_MEMORY_ENABLED` | `false` | Cross-session memory |
| `HEADROOM_UPSTREAM_URL` | provider default | Custom LLM endpoint |
| `RUST_LOG` | `info` | Rust proxy log level |
| `HEADROOM_LOG_LEVEL` | `info` | Python log level |

### First-Run Verification

```bash
# Start proxy
headroom-proxy --upstream-url https://api.anthropic.com --compression

# Verify health
curl http://localhost:8080/healthz
# Expected: {"service":"headroom-proxy","status":"healthy","alive":true}

# Verify compression is on
curl http://localhost:8080/stats | jq .compression_enabled
# Expected: true

# Test a request
curl -X POST http://localhost:8080/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -d '{"model":"claude-3-haiku-20240307","max_tokens":10,"messages":[{"role":"user","content":"Hello"}]}'
```

## 2. Health Monitoring

### Health Endpoints

| Endpoint | Purpose | Expected Response |
|----------|---------|-------------------|
| `/healthz` | Liveness + startup | 200 OK |
| `/readyz` | Readiness (all systems go) | 200 OK |
| `/livez` | Liveness (process alive) | 200 OK |

### Key Metrics to Monitor

```promql
# Compression effectiveness
rate(headroom_tokens_saved_total[5m]) / rate(headroom_tokens_requested_total[5m])

# Error rate
rate(headroom_request_errors_total[5m]) / rate(headroom_request_total[5m])

# Latency (p99)
histogram_quantile(0.99, rate(headroom_request_duration_seconds_bucket[5m]))

# CCR cache hit rate
rate(headroom_ccr_hits_total[5m]) / (rate(headroom_ccr_hits_total[5m]) + rate(headroom_ccr_misses_total[5m]))

# Memory usage
process_resident_memory_bytes / 1024 / 1024
```

### Recommended Alerting

| Alert | Threshold | Action |
|-------|-----------|--------|
| High error rate | > 5% for 5 min | Check upstream connectivity |
| High latency | p99 > 30s for 5 min | Check upstream_timeout, compression_mode |
| Memory pressure | > 80% of limit for 10 min | Scale up or reduce max_body_bytes |
| CCR store full | > 10K entries | Consider Redis backend |
| License expired | Grace period ending | Contact hello@headroomlabs.ai |

## 3. Common Operations

### Rotating the Admin API Key

```bash
# Update secret
kubectl create secret generic headroom-proxy-secret \
  --from-literal=HEADROOM_ADMIN_API_KEY=new-key-123 \
  -n headroom --dry-run=client -o yaml | kubectl apply -f -

# Restart to pick up new key
kubectl rollout restart deployment/headroom-proxy -n headroom
```

### Updating the License Key (Zero-Downtime)

```bash
# Update secret
kubectl create secret generic headroom-proxy-secret \
  --from-literal=HEADROOM_LICENSE_KEY=new-license-key \
  -n headroom --dry-run=client -o yaml | kubectl apply -f -

# Graceful restart
kubectl rollout restart deployment/headroom-proxy -n headroom
# Rolling update with maxUnavailable=0 ensures zero downtime
```

### Scaling

```bash
# Manual scale
kubectl scale deployment headroom-proxy --replicas=5 -n headroom

# Check HPA status
kubectl get hpa -n headroom
```

### Clearing Stats

```bash
# Requires admin key + loopback access (or port-forward)
kubectl port-forward svc/headroom-proxy 8080:80 -n headroom
curl -X POST -H "X-Headroom-Admin-Key: YOUR_KEY" http://localhost:8080/stats/reset
```

## 4. Troubleshooting

### High Latency

**Symptoms:** p99 latency > 30s, requests timing out

**Check:**
```bash
# 1. Upstream latency
curl -w "@curl-format.txt" -o /dev/null -s https://api.anthropic.com/v1/messages

# 2. Compression mode
kubectl exec -it deployment/headroom-proxy -n headroom -- env | grep COMPRESSION_MODE

# 3. Body size
kubectl logs deployment/headroom-proxy -n headroom | grep "body_too_large"
```

**Fixes:**
- Reduce `upstream_timeout` from 600s to 120s for non-streaming
- Switch compression mode from `off` to `live-zone`
- Increase `max_body_bytes` if legitimate large requests are failing

### Memory Pressure

**Symptoms:** OOMKilled, high RSS

**Check:**
```bash
kubectl top pods -n headroom
curl -H "X-Headroom-Admin-Key: YOUR_KEY" http://localhost:8080/stats | jq .ccr_store_size
```

**Fixes:**
- Reduce `max_body_mb` from 50 to 25
- Switch CCR backend from in-memory to Redis
- Increase memory limit
- Reduce HPA max replicas

### Compression Not Working

**Check:**
```bash
# Verify compression is enabled
kubectl exec -it deployment/headroom-proxy -n headroom -- env | grep COMPRESSION
# Should show: HEADROOM_PROXY_COMPRESSION=1

# Check compression ratio
curl -H "X-Headroom-Admin-Key: YOUR_KEY" http://localhost:8080/stats | jq .compression_ratio

# Check for errors
kubectl logs deployment/headroom-proxy -n headroom | grep -i "compress"
```

**Fixes:**
- Ensure `HEADROOM_PROXY_COMPRESSION=1` is set
- Ensure `HEADROOM_PROXY_COMPRESSION_MODE=live-zone`
- Check that upstream URL is correct
- Verify API key is valid

### Auth Errors

**Check:**
```bash
# Check auth mode
kubectl logs deployment/headroom-proxy -n headroom | grep "auth_mode"

# Check policy enforcement
kubectl exec -it deployment/headroom-proxy -n headroom -- env | grep AUTH_MODE_POLICY
```

**Fixes:**
- Verify API key format (sk-ant-api for PAYG, Bearer for OAuth)
- Check `auth-mode-policy-enforcement` setting
- Ensure subscription UA prefixes are recognized

### CCR Misses

**Check:**
```bash
# CCR hit/miss rate
curl -H "X-Headroom-Admin-Key: YOUR_KEY" http://localhost:8080/stats | jq .ccr_hits, .ccr_misses

# CCR store backend
kubectl exec -it deployment/headroom-proxy -n headroom -- env | grep CCR
```

**Fixes:**
- In-memory CCR loses data on restart — expected behavior
- Switch to Redis for persistent CCR
- Check hash format compatibility (BLAKE3 24-char)

## 5. Incident Response

### Proxy Crash (OOMKilled)

```bash
# 1. Check crash reason
kubectl describe pod <pod-name> -n headroom | grep -A5 "Last State"

# 2. Check resource usage
kubectl top pods -n headroom

# 3. Immediate fix: increase memory limit
kubectl patch deployment headroom-proxy -n headroom \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"headroom-proxy","resources":{"limits":{"memory":"1Gi"}}}]}}}}'

# 4. Long-term: reduce max_body_mb, switch to Redis CCR
```

### Upstream Unreachable

```bash
# 1. Check upstream connectivity
kubectl exec -it deployment/headroom-proxy -n headroom -- \
  curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages

# 2. Check DNS
kubectl exec -it deployment/headroom-proxy -n headroom -- nslookup api.anthropic.com

# 3. Check network policies
kubectl get networkpolicy -n headroom

# 4. Fallback: proxy passes through to upstream unchanged (no compression)
```

### License Expired

```bash
# Check license status
curl -H "X-Headroom-Admin-Key: YOUR_KEY" http://localhost:8080/stats | jq .license_status

# Grace period: 7 days after expiry, features still work
# After grace period: compression degrades, telemetry stops
# Fix: renew license, update HEADROOM_LICENSE_KEY secret
```

## 6. Backup & Recovery

### CCR Store (SQLite)

```bash
# If using SQLite CCR backend
kubectl exec -it deployment/headroom-proxy -n headroom -- ls -la /data/ccr.db

# Backup
kubectl exec -it deployment/headroom-proxy -n headroom -- tar czf /tmp/ccr-backup.tar.gz /data/ccr.db
kubectl cp headroom/<pod>:/tmp/ccr-backup.tar.gz ./ccr-backup.tar.gz

# Restore
kubectl cp ./ccr-backup.tar.gz headroom/<pod>:/tmp/
kubectl exec -it deployment/headroom-proxy -n headroom -- tar xzf /tmp/ccr-backup.tar.gz -C /
```

### Config Backup

```bash
# Export current config
kubectl get configmap headroom-proxy-config -n headroom -o yaml > configmap-backup.yaml
kubectl get secret headroom-proxy-secret -n headroom -o yaml > secret-backup.yaml
```

### Dashboard/Stats Data

Stats are in-memory and non-persistent. They reset on restart. Export before restart if needed:

```bash
curl -H "X-Headroom-Admin-Key: YOUR_KEY" http://localhost:8080/stats > stats-backup.json
curl -H "X-Headroom-Admin-Key: YOUR_KEY" http://localhost:8080/stats-history > stats-history-backup.json
```
