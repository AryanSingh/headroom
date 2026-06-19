# Deployment Architecture

## Deployment Options

| Option | Complexity | Best For |
|--------|-----------|----------|
| Local (pip) | Trivial | Individual engineers, prototyping |
| Docker | Simple | Small teams, CI/CD |
| docker-compose | Simple | Multi-service setups |
| Kubernetes | Moderate | Production, scaling |
| Air-gapped | Moderate | Regulated environments |

## Local (Fastest)

```bash
pip install "cutctx-ai[all]"
cutctx proxy --port 8787
```

**Requirements:** Python 3.10+, 2GB RAM

**What runs:**
- CutCtx proxy (FastAPI + Uvicorn)
- Python compression pipeline
- Rust core (via PyO3)
- SQLite for CCR and memory
- Local dashboard at `/dashboard`

## Docker

```bash
docker pull ghcr.io/chopratejas/headroom:latest
docker run -p 8787:8787 \
  -e ANTHROPIC_API_KEY=$KEY \
  ghcr.io/chopratejas/headroom:latest
```

**Image size:** ~50MB (minimal Python + Rust binary)

**Features:**
- Non-root user
- Health checks
- Resource limits
- No shell in production image

## docker-compose

```yaml
version: '3.8'
services:
  headroom:
    image: ghcr.io/chopratejas/headroom:latest
    ports:
      - "8787:8787"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - HEADROOM_CACHE_ENABLED=true
      - HEADROOM_LOG_REQUESTS=true
    volumes:
      - headroom-data:/root/.headroom
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8787/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  headroom-data:
```

**Features:**
- Persistent storage via volumes
- Health checks
- Automatic restarts
- Network isolation

## Kubernetes

### Production Manifests

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: headroom-proxy
  labels:
    app: headroom
spec:
  replicas: 2
  selector:
    matchLabels:
      app: headroom
  template:
    metadata:
      labels:
        app: headroom
    spec:
      containers:
      - name: headroom
        image: ghcr.io/chopratejas/headroom:latest
        ports:
        - containerPort: 8787
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: headroom-secrets
              key: anthropic-api-key
        - name: HEADROOM_LICENSE_KEY
          valueFrom:
            secretKeyRef:
              name: headroom-secrets
              key: license-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8787
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8787
          initialDelaySeconds: 5
          periodSeconds: 10
```

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: headroom-proxy
spec:
  selector:
    app: headroom
  ports:
  - port: 8787
    targetPort: 8787
  type: ClusterIP
```

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: headroom-proxy
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  rules:
  - host: headroom.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: headroom-proxy
            port:
              number: 8787
```

### Helm Chart (Coming Q4 2026)

```bash
helm repo add cutctx https://cutctx.dev/helm
helm install headroom headroom/headroom --set licenseKey=hlk_...
```

## Air-Gapped Deployment

### Pre-Download Dependencies

```bash
# Download ONNX Runtime
wget https://cdn.pyke.io/onnxruntime/linux-x64/onnxruntime-1.17.0.tgz

# Download Kompress Model
wget https://huggingface.co/pykeio/kompress-base/resolve/main/model.onnx

# Copy to air-gapped machine
scp onnxruntime-*.tgz model.onnx airgap-host:/opt/headroom/
```

### Run Offline

```bash
# Set offline flags
export HF_HUB_OFFLINE=1
export ORT_STRATEGY=system

# Run proxy
cutctx proxy --port 8787
```

**Requirements:**
- Python 3.10+
- 2GB RAM
- No external network access after setup

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Customer Infrastructure                    │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  AI Agent    │───▶│   CutCtx   │───▶│  LLM Provider│   │
│  │  (Claude,    │    │    Proxy     │    │  (Anthropic, │   │
│  │   Codex,     │    │  (port 8787) │    │   OpenAI,    │   │
│  │   Cursor)    │    │              │    │   Google)    │   │
│  └──────────────┘    └──────┬───────┘    └──────────────┘   │
│                              │                               │
│                     ┌────────┴────────┐                     │
│                     │   Local Storage  │                     │
│                     │  ┌────────────┐  │                     │
│                     │  │  CCR DB    │  │                     │
│                     │  │  (SQLite)  │  │                     │
│                     │  └────────────┘  │                     │
│                     │  ┌────────────┐  │                     │
│                     │  │  Memory    │  │                     │
│                     │  │  (SQLite)  │  │                     │
│                     │  └────────────┘  │                     │
│                     │  ┌────────────┐  │                     │
│                     │  │  Logs      │  │                     │
│                     │  │  (JSONL)   │  │                     │
│                     │  └────────────┘  │                     │
│                     └──────────────────┘                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Resource Requirements

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| CutCtx proxy | 0.25–1.0 cores | 256MB–1GB | 100MB |
| CCR database | Negligible | 50MB–500MB | 1GB–10GB |
| Memory store | Negligible | 50MB–500MB | 100MB–1GB |
| Request logs | Negligible | 10MB–100MB | 1GB–50GB |
| **Total** | **0.25–1.0 cores** | **500MB–2GB** | **2GB–60GB** |

## Scaling

### Horizontal Scaling
- Run multiple CutCtx proxy instances behind a load balancer
- Each instance has its own CCR and memory store (isolated)
- No shared state between instances

### Vertical Scaling
- Increase `--compression-max-workers` for higher throughput
- Increase `--max-connections` for more concurrent requests
- Increase `--cache-max-entries` for better hit rates

### Recommended Configuration

| Team Size | Instances | CPU | Memory |
|-----------|-----------|-----|--------|
| 1–5 engineers | 1 | 0.5 cores | 512MB |
| 5–20 engineers | 1–2 | 1 core | 1GB |
| 20–50 engineers | 2–4 | 2 cores | 2GB |
| 50+ engineers | 4+ | 4+ cores | 4+ GB |
