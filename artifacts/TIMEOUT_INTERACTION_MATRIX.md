# Timeout Interaction Matrix

## Timeout Configuration Table

| Component | Default | Env Var | CLI Flag | Scope | Interaction |
|-----------|---------|---------|----------|-------|-------------|
| `upstream_timeout` | 600s | `CUTCTX_PROXY_UPSTREAM_TIMEOUT` | `--upstream-timeout` | Per-request LLM stream | Max time to wait for upstream response |
| `upstream_connect_timeout` | 10s | `CUTCTX_PROXY_UPSTREAM_CONNECT_TIMEOUT` | `--upstream-connect-timeout` | TCP/TLS handshake | Must be < upstream_timeout |
| `graceful_shutdown_timeout` | 30s | `CUTCTX_PROXY_GRACEFUL_SHUTDOWN_TIMEOUT` | `--graceful-shutdown-timeout` | SIGTERM drain | Must be > sum of in-flight timeouts |
| `request_timeout` (Python) | 300s | `CUTCTX_REQUEST_TIMEOUT` | `--request-timeout` | Management API | Affects /dashboard, /stats only |
| `episodic_idle_timeout` | 300s | `CUTCTX_EPISODIC_IDLE_TIMEOUT` | N/A | Memory extraction | When idle session triggers extraction |
| K8s `terminationGracePeriodSeconds` | 60s | — | — | Pod shutdown | Must be > graceful_shutdown_timeout + 10s |
| K8s `livenessProbe.periodSeconds` | 10s | — | — | Health check | How often to check liveness |
| K8s `readinessProbe.periodSeconds` | 5s | — | — | Health check | How often to check readiness |
| K8s `startupProbe.failureThreshold` | 30 | — | — | Startup window | 30 × 2s = 60s startup window |

## Interaction Rules

### Rule 1: `upstream_connect_timeout` MUST be < `upstream_timeout`

```
upstream_connect_timeout (10s) < upstream_timeout (600s) ✅
```

The connect timeout governs TCP/TLS handshake only. If the upstream is unreachable, failing fast at 10s is correct. The 600s upstream_timeout governs the full request lifecycle (including streaming).

### Rule 2: `graceful_shutdown_timeout` MUST be > longest in-flight request

```
graceful_shutdown_timeout (30s) > upstream_timeout (600s)? NO ❌
```

**This is a known limitation.** With default settings, at most 0 in-flight streaming requests can complete during shutdown. The proxy will forcefully terminate long-running streams.

**Mitigation options:**
1. Reduce `upstream_timeout` to 25s (safe for non-streaming)
2. Increase `graceful_shutdown_timeout` to 610s (risky — delays pod removal)
3. Accept that streaming requests may be interrupted on restart

### Rule 3: K8s `terminationGracePeriodSeconds` > `graceful_shutdown_timeout`

```yaml
terminationGracePeriodSeconds: 60  # > 30s graceful_shutdown_timeout ✅
```

The K8s grace period must exceed Cutctx's graceful shutdown to allow:
1. SIGTERM received → graceful shutdown starts
2. Graceful shutdown drains in-flight requests (up to 30s)
3. Remaining 30s for OS-level cleanup

### Rule 4: Python `request_timeout` is independent of proxy path

The Python FastAPI management API (`/dashboard`, `/stats`) has its own timeout. The Rust proxy path (`/v1/*`) uses `upstream_timeout` directly. They do not interact.

### Rule 5: `episodic_idle_timeout` triggers async extraction

When a session is idle for 300s, the episodic memory extractor fires asynchronously. This does NOT block the proxy path. The extraction runs in a background task and writes to the file-based memory store.

## Tuning Guide

### High-Throughput (>500 req/s)

```bash
# Reduce upstream timeout for faster cycling
CUTCTX_PROXY_UPSTREAM_TIMEOUT=120s

# Reduce graceful shutdown for faster deploys
CUTCTX_PROXY_GRACEFUL_SHUTDOWN_TIMEOUT=15s

# K8s: match termination grace period
terminationGracePeriodSeconds: 30
```

### Long-Context (100K+ tokens)

```bash
# Increase upstream timeout for long generation
CUTCTX_PROXY_UPSTREAM_TIMEOUT=900s

# Increase graceful shutdown to drain long streams
CUTCTX_PROXY_GRACEFUL_SHUTDOWN_TIMEOUT=920s

# K8s: increase termination grace period
terminationGracePeriodSeconds: 960
```

### Development/Testing

```bash
# Short timeouts for fast feedback
CUTCTX_PROXY_UPSTREAM_TIMEOUT=30s
CUTCTX_PROXY_UPSTREAM_CONNECT_TIMEOUT=5s
CUTCTX_PROXY_GRACEFUL_SHUTDOWN_TIMEOUT=5s
```

### K8s Production (Conservative)

```yaml
# Deployment spec
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 65
      containers:
        - name: cutctx-proxy
          args:
            - "--upstream-timeout"
            - "600s"
            - "--graceful-shutdown-timeout"
            - "30s"
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /readyz
              port: http
            periodSeconds: 5
            failureThreshold: 3
          startupProbe:
            httpGet:
              path: /healthz
              port: http
            periodSeconds: 2
            failureThreshold: 30  # 60s startup window
```

## Timeout Interaction Diagram

```
Client Request
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Cutctx Proxy                                      │
│                                                      │
│  1. Connect to upstream (upstream_connect_timeout)   │
│     └── TCP/TLS handshake: 10s max                   │
│                                                      │
│  2. Forward request (upstream_timeout)               │
│     └── Full request lifecycle: 600s max             │
│         ├── Non-streaming: single response           │
│         └── Streaming: SSE/chunked transfer          │
│                                                      │
│  3. Shutdown (graceful_shutdown_timeout)             │
│     └── Drain in-flight: 30s max                     │
│         └── SIGTERM → stop accepting → drain → exit  │
└─────────────────────────────────────────────────────┘

K8s Layer:
  terminationGracePeriodSeconds: 60s
  └── Must be > graceful_shutdown_timeout + buffer
  └── If exceeded: SIGKILL (forceful termination)
```

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Request timeout during streaming | `upstream_timeout` too low | Increase to 600s+ |
| Pod killed during deploy | `terminationGracePeriodSeconds` too low | Increase to > graceful_shutdown_timeout + 10s |
| Health check failures during startup | Startup probe too aggressive | Increase `failureThreshold` to 30 |
| Connection refused errors | `upstream_connect_timeout` too low | Increase to 15-30s for remote upstreams |
| Memory spike during shutdown | Many in-flight requests | Reduce `upstream_timeout` or scale down before deploy |
