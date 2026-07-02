# Cutctx Proxy — Kubernetes Deployment

## Quick Start

```bash
# 1. Create namespace and resources
kubectl apply -f k8s/

# 2. Edit secret with your keys
kubectl edit secret cutctx-proxy-secret -n cutctx

# 3. Verify deployment
kubectl get pods -n cutctx
kubectl logs -f deployment/cutctx-proxy -n cutctx
```

## Prerequisites

- Kubernetes 1.25+
- `kubectl` configured with cluster access
- Cutctx Docker image available (build with `docker build -t cutctx-proxy .`)
- (Optional) ingress-nginx controller for external access
- (Optional) cert-manager for TLS certificates

## Files

| File | Description |
|------|-------------|
| `namespace.yaml` | Cutctx namespace |
| `configmap.yaml` | Non-sensitive configuration |
| `secret.yaml` | Secrets template (edit before deploying) |
| `deployment.yaml` | 2-replica deployment with probes + resource limits |
| `service.yaml` | ClusterIP service (port 80 → 8080) |
| `hpa.yaml` | HorizontalPodAutoscaler (2-10 replicas) |
| `pdb.yaml` | PodDisruptionBudget (min 1 available) |
| `ingress.yaml` | Ingress with TLS placeholder |
| `rbac.yaml` | ServiceAccount |

## Configuration

### Required Secrets

Edit `secret.yaml` before deploying:

```yaml
stringData:
  CUTCTX_LICENSE_KEY: "your-license-key"
  CUTCTX_ADMIN_API_KEY: "your-admin-key"
  CUTCTX_UPSTREAM_API_KEY: "your-anthropic-or-openai-key"
```

### Optional: Upstream URL

If your LLM provider requires a custom base URL:

```yaml
# In configmap.yaml
CUTCTX_PROXY_UPSTREAM_URL: "https://your-proxy.example.com"
```

### Resource Sizing

| Load | CPU Request | Memory Request | CPU Limit | Memory Limit |
|------|-------------|----------------|-----------|--------------|
| Light (<100 req/s) | 100m | 128Mi | 500m | 256Mi |
| Medium (100-500 req/s) | 250m | 256Mi | 1000m | 512Mi |
| Heavy (500+ req/s) | 500m | 512Mi | 2000m | 1Gi |

## Health Endpoints

| Endpoint | Purpose | Probe Type |
|----------|---------|------------|
| `/healthz` | Liveness + startup | HTTP GET |
| `/readyz` | Readiness | HTTP GET |
| `/livez` | Liveness | HTTP GET |

## Scaling

```bash
# Manual scale
kubectl scale deployment cutctx-proxy --replicas=5 -n cutctx

# Check HMA status
kubectl get hpa -n cutctx
```

## Monitoring

Prometheus metrics available at `/metrics`:

```bash
# Port-forward to check metrics
kubectl port-forward svc/cutctx-proxy 8080:80 -n cutctx
curl http://localhost:8080/metrics
```

Key metrics:
- `cutctx_compression_ratio` — compression effectiveness
- `cutctx_request_duration_seconds` — latency histogram
- `cutctx_ccr_store_size` — CCR cache entries
- `cutctx_tokens_saved_total` — cumulative tokens saved

## Upgrading

```bash
# Update image tag
kubectl set image deployment/cutctx-proxy cutctx-proxy=ghcr.io/cutctx/cutctx:v0.29.0 -n cutctx

# Watch rollout
kubectl rollout status deployment/cutctx-proxy -n cutctx

# Rollback if needed
kubectl rollout undo deployment/cutctx-proxy -n cutctx
```

## Troubleshooting

### Pod stuck in CrashLoopBackOff
```bash
kubectl logs -p deployment/cutctx-proxy -n cutctx
# Check: OOM? (increase memory limit)
# Check: License key? (check secret)
# Check: Upstream unreachable? (check network policy)
```

### Compression not working
```bash
# Verify compression is enabled
kubectl exec -it deployment/cutctx-proxy -n cutctx -- env | grep COMPRESSION
# Should show: CUTCTX_PROXY_COMPRESSION=1
```

### High memory usage
```bash
# Check CCR store size
curl -H "X-Cutctx-Admin-Key: YOUR_KEY" http://localhost:8080/stats
# Consider reducing max_body_bytes or adding Redis CCR backend
```
