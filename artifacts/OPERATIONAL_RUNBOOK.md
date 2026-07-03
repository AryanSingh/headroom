# Cutctx Operational Runbook

## 1. Deployment Checklist

### Prerequisites
- [ ] Docker image built: `docker build -t cutctx-proxy .`
- [ ] License key obtained through the current commercial licensing workflow
- [ ] Upstream API key (Anthropic/OpenAI) configured
- [ ] Admin API key generated (for dashboard/stats access)

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_PROXY_COMPRESSION` | `false` | Enable compression (set to `1`) |
| `CUTCTX_PROXY_COMPRESSION_MODE` | `off` | `live-zone` for production |
| `CUTCTX_LICENSE_KEY` | — | Commercial license key for the deployment |
| `CUTCTX_ADMIN_API_KEY` | — | Admin auth for /dashboard, /stats |
| `CUTCTX_CORS_ORIGINS` | `""` (closed) | Comma-separated origins, or `*` |
| `CUTCTX_MAX_BODY_MB` | `50` | Max request body size in MB |
| `CUTCTX_TELEMETRY_ENABLED` | `false` | Opt-in usage telemetry |
| `CUTCTX_EPISODIC_MEMORY_ENABLED` | `false` | Cross-session memory |
| `CUTCTX_UPSTREAM_URL` | provider default | Custom LLM endpoint |
| `RUST_LOG` | `info` | Rust proxy log level |
| `CUTCTX_LOG_LEVEL` | `info` | Python log level |

### First-Run Verification

```bash
# Start proxy
cutctx-proxy --upstream-url https://api.anthropic.com --compression

# Verify health
curl http://localhost:8080/healthz
# Expected: {"service":"cutctx-proxy","status":"healthy","alive":true}

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
rate(cutctx_tokens_saved_total[5m]) / rate(cutctx_tokens_requested_total[5m])

# Error rate
rate(cutctx_request_errors_total[5m]) / rate(cutctx_request_total[5m])

# Latency (p99)
histogram_quantile(0.99, rate(cutctx_request_duration_seconds_bucket[5m]))

# CCR cache hit rate
rate(cutctx_ccr_hits_total[5m]) / (rate(cutctx_ccr_hits_total[5m]) + rate(cutctx_ccr_misses_total[5m]))

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
| License expired | Grace period ending | Renew through the current commercial licensing workflow |

## 3. Common Operations

### Rotating the Admin API Key

```bash
# Update secret
kubectl create secret generic cutctx-proxy-secret \
  --from-literal=CUTCTX_ADMIN_API_KEY=new-key-123 \
  -n cutctx --dry-run=client -o yaml | kubectl apply -f -

# Restart to pick up new key
kubectl rollout restart deployment/cutctx-proxy -n cutctx
```

### Updating the License Key (Zero-Downtime)

```bash
# Update secret
kubectl create secret generic cutctx-proxy-secret \
  --from-literal=CUTCTX_LICENSE_KEY=new-license-key \
  -n cutctx --dry-run=client -o yaml | kubectl apply -f -

# Graceful restart
kubectl rollout restart deployment/cutctx-proxy -n cutctx
# Rolling update with maxUnavailable=0 ensures zero downtime
```

### Scaling

```bash
# Manual scale
kubectl scale deployment cutctx-proxy --replicas=5 -n cutctx

# Check HPA status
kubectl get hpa -n cutctx
```

### Clearing Stats

```bash
# Requires admin key + loopback access (or port-forward)
kubectl port-forward svc/cutctx-proxy 8080:80 -n cutctx
curl -X POST -H "X-Cutctx-Admin-Key: YOUR_KEY" http://localhost:8080/stats/reset
```

## 4. Troubleshooting

### High Latency

**Symptoms:** p99 latency > 30s, requests timing out

**Check:**
```bash
# 1. Upstream latency
curl -w "@curl-format.txt" -o /dev/null -s https://api.anthropic.com/v1/messages

# 2. Compression mode
kubectl exec -it deployment/cutctx-proxy -n cutctx -- env | grep COMPRESSION_MODE

# 3. Body size
kubectl logs deployment/cutctx-proxy -n cutctx | grep "body_too_large"
```

**Fixes:**
- Reduce `upstream_timeout` from 600s to 120s for non-streaming
- Switch compression mode from `off` to `live-zone`
- Increase `max_body_bytes` if legitimate large requests are failing

### Memory Pressure

**Symptoms:** OOMKilled, high RSS

**Check:**
```bash
kubectl top pods -n cutctx
curl -H "X-Cutctx-Admin-Key: YOUR_KEY" http://localhost:8080/stats | jq .ccr_store_size
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
kubectl exec -it deployment/cutctx-proxy -n cutctx -- env | grep COMPRESSION
# Should show: CUTCTX_PROXY_COMPRESSION=1

# Check compression ratio
curl -H "X-Cutctx-Admin-Key: YOUR_KEY" http://localhost:8080/stats | jq .compression_ratio

# Check for errors
kubectl logs deployment/cutctx-proxy -n cutctx | grep -i "compress"
```

**Fixes:**
- Ensure `CUTCTX_PROXY_COMPRESSION=1` is set
- Ensure `CUTCTX_PROXY_COMPRESSION_MODE=live-zone`
- Check that upstream URL is correct
- Verify API key is valid

### Auth Errors

**Check:**
```bash
# Check auth mode
kubectl logs deployment/cutctx-proxy -n cutctx | grep "auth_mode"

# Check policy enforcement
kubectl exec -it deployment/cutctx-proxy -n cutctx -- env | grep AUTH_MODE_POLICY
```

**Fixes:**
- Verify API key format (sk-ant-api for PAYG, Bearer for OAuth)
- Check `auth-mode-policy-enforcement` setting
- Ensure subscription UA prefixes are recognized

### CCR Misses

**Check:**
```bash
# CCR hit/miss rate
curl -H "X-Cutctx-Admin-Key: YOUR_KEY" http://localhost:8080/stats | jq .ccr_hits, .ccr_misses

# CCR store backend
kubectl exec -it deployment/cutctx-proxy -n cutctx -- env | grep CCR
```

**Fixes:**
- In-memory CCR loses data on restart — expected behavior
- Switch to Redis for persistent CCR
- Check hash format compatibility (BLAKE3 24-char)

## 5. Incident Response

### Proxy Crash (OOMKilled)

```bash
# 1. Check crash reason
kubectl describe pod <pod-name> -n cutctx | grep -A5 "Last State"

# 2. Check resource usage
kubectl top pods -n cutctx

# 3. Immediate fix: increase memory limit
kubectl patch deployment cutctx-proxy -n cutctx \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"cutctx-proxy","resources":{"limits":{"memory":"1Gi"}}}]}}}}'

# 4. Long-term: reduce max_body_mb, switch to Redis CCR
```

### Upstream Unreachable

```bash
# 1. Check upstream connectivity
kubectl exec -it deployment/cutctx-proxy -n cutctx -- \
  curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages

# 2. Check DNS
kubectl exec -it deployment/cutctx-proxy -n cutctx -- nslookup api.anthropic.com

# 3. Check network policies
kubectl get networkpolicy -n cutctx

# 4. Fallback: proxy passes through to upstream unchanged (no compression)
```

### License Expired

```bash
# Check license status
curl -H "X-Cutctx-Admin-Key: YOUR_KEY" http://localhost:8080/stats | jq .license_status

# Grace period: 7 days after expiry, features still work
# After grace period: compression degrades, telemetry stops
# Fix: renew the commercial license and update the CUTCTX_LICENSE_KEY secret
```

## 6. Backup & Recovery

### CCR Store (SQLite)

```bash
# If using SQLite CCR backend
kubectl exec -it deployment/cutctx-proxy -n cutctx -- ls -la /data/ccr.db

# Backup
kubectl exec -it deployment/cutctx-proxy -n cutctx -- tar czf /tmp/ccr-backup.tar.gz /data/ccr.db
kubectl cp cutctx/<pod>:/tmp/ccr-backup.tar.gz ./ccr-backup.tar.gz

# Restore
kubectl cp ./ccr-backup.tar.gz cutctx/<pod>:/tmp/
kubectl exec -it deployment/cutctx-proxy -n cutctx -- tar xzf /tmp/ccr-backup.tar.gz -C /
```

### Config Backup

```bash
# Export current config
kubectl get configmap cutctx-proxy-config -n cutctx -o yaml > configmap-backup.yaml
kubectl get secret cutctx-proxy-secret -n cutctx -o yaml > secret-backup.yaml
```

### Dashboard/Stats Data

Stats are in-memory and non-persistent. They reset on restart. Export before restart if needed:

```bash
curl -H "X-Cutctx-Admin-Key: YOUR_KEY" http://localhost:8080/stats > stats-backup.json
curl -H "X-Cutctx-Admin-Key: YOUR_KEY" http://localhost:8080/stats-history > stats-history-backup.json
```
