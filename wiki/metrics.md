# Metrics & Monitoring

Cutctx provides comprehensive metrics for monitoring compression performance, cost savings, and system health.

## Proxy Metrics

### Stats Endpoint

```bash
curl http://localhost:8787/stats
```

```json
{
  "persistent_savings": {
    "lifetime": {
      "tokens_saved": 12500,
      "compression_savings_usd": 0.04
    },
    "recent_history": [
      {
        "timestamp": "2026-03-27T09:00:00Z",
        "total_tokens_saved": 12500,
        "compression_savings_usd": 0.04
      }
    ]
  },
  "requests": {
    "total": 42,
    "cached": 5,
    "rate_limited": 0,
    "failed": 0
  },
  "tokens": {
    "input": 50000,
    "output": 8000,
    "saved": 12500,
    "savings_percent": 25.0
  },
  "cost": {
    "total_cost_usd": 0.15,
    "total_savings_usd": 0.04
  },
  "cache": {
    "entries": 10,
    "total_hits": 5
  }
}
```

`/stats` keeps the existing live/session fields, including `savings_history`,
for backward compatibility. The new `persistent_savings` block is durable local
proxy compression history stored by default at
`${CUTCTX_WORKSPACE_DIR}/proxy_savings.json` (i.e.
`~/.cutctx/proxy_savings.json` when `CUTCTX_WORKSPACE_DIR` is unset).
Use `CUTCTX_SAVINGS_PATH` to override the file location directly, or
set `CUTCTX_WORKSPACE_DIR` to relocate the entire state root. See the
[Filesystem Contract](filesystem-contract.md) for details.

For Anthropic-style providers that return cache-write TTL buckets, `/stats`
also surfaces observed cache TTL usage under `prefix_cache`:

```json
{
  "prefix_cache": {
    "by_provider": {
      "anthropic": {
        "observed_ttl_buckets": {
          "5m": {"tokens": 20000, "requests": 8},
          "1h": {"tokens": 50000, "requests": 12}
        },
        "observed_ttl_mix": {
          "5m_pct": 28.6,
          "1h_pct": 71.4,
          "active_buckets": ["5m", "1h"]
        }
      }
    },
    "totals": {
      "observed_ttl_buckets": {
        "5m": {"tokens": 20000, "requests": 8},
        "1h": {"tokens": 50000, "requests": 12}
      }
    }
  }
}
```

These fields are observational only:

- they reflect provider-reported cache write buckets
- they do not configure TTL
- they do not represent remaining expiration time

### Historical Savings Endpoint

```bash
curl http://localhost:8787/stats-history
```

```json
{
  "schema_version": 2,
  "generated_at": "2026-03-27T09:10:00Z",
  "lifetime": {
    "tokens_saved": 12500,
    "compression_savings_usd": 0.04
  },
  "history": [
    {
      "timestamp": "2026-03-27T09:00:00Z",
      "total_tokens_saved": 12000,
      "compression_savings_usd": 0.038
    }
  ],
  "series": {
    "hourly": [],
    "daily": [],
    "weekly": [],
    "monthly": []
  },
  "exports": {
    "default_format": "json",
    "available_formats": ["json", "csv"],
    "available_series": ["history", "hourly", "daily", "weekly", "monthly"]
  },
  "history_summary": {
    "mode": "compact",
    "stored_points": 2048,
    "returned_points": 500,
    "compacted": true
  }
}
```

`/stats-history` is the stable frontend-facing API for durable proxy
compression history. It survives proxy restarts, tolerates missing or malformed
state files, and powers the historical view in `/dashboard`. It now includes
hourly, daily, weekly, and monthly chart-ready rollups.

By default, the `history` array is compacted for transport efficiency. Use
`history_mode=full` when you explicitly need the full retained checkpoint list,
or `history_mode=none` when you only need the aggregate rollups and lifetime
totals.

For export-friendly downloads:

```bash
curl "http://localhost:8787/stats-history?format=csv&series=daily"
curl "http://localhost:8787/stats-history?format=csv&series=monthly"
curl "http://localhost:8787/stats-history?history_mode=full"
```

CSV exports are available for `history`, `hourly`, `daily`, `weekly`, and
`monthly`. Plain JSON remains the default response format.

### Prometheus Metrics

```bash
curl http://localhost:8787/metrics
```

```prometheus
# HELP cutctx_requests_total Total number of requests
cutctx_requests_total 1234

# HELP cutctx_latency_ms_count Count of observed request latencies
cutctx_latency_ms_count 1234

# HELP cutctx_tokens_saved_total Tokens saved by optimization
cutctx_tokens_saved_total 5678900

# HELP cutctx_requests_by_provider Requests by provider
cutctx_requests_by_provider{provider="anthropic"} 800
cutctx_requests_by_provider{provider="openai"} 434

# HELP cutctx_requests_by_stack Requests by Cutctx integration stack
cutctx_requests_by_stack{stack="wrap_claude"} 612
cutctx_requests_by_stack{stack="adapter_ts_openai"} 48

# HELP cutctx_transform_timing_ms_sum Sum of transform timing in milliseconds
cutctx_transform_timing_ms_sum{transform="router"} 5123.7

# HELP cutctx_cache_write_ttl_tokens_total Provider cache write tokens by observed TTL bucket
cutctx_cache_write_ttl_tokens_total{provider="anthropic",ttl="5m"} 20000
cutctx_cache_write_ttl_tokens_total{provider="anthropic",ttl="1h"} 50000
```

The built-in Prometheus endpoint exposes the proxy's in-memory operational state, including:

- request counters
- token totals and savings
- latency / overhead / TTFB summaries
- per-provider and per-model request counts
- per-stage pipeline timing
- waste signal token totals
- provider cache read/write and TTL-bucket counters
- cache bust counters

### OTEL Metrics

Cutctx now emits the same operational events through a shared OTEL metrics facade.

There are two integration modes:

1. **Ambient OTEL app setup** - if your application already configures a global OTEL meter provider, Cutctx records into that provider automatically.
2. **Cutctx-managed export** - if you want the proxy to configure its own OTEL metrics exporter, install:

```bash
pip install "cutctx-ai[proxy,otel]"
```

Then set:

```bash
CUTCTX_OTEL_METRICS_ENABLED=1
CUTCTX_OTEL_METRICS_EXPORTER=otlp_http
CUTCTX_OTEL_METRICS_ENDPOINT=http://127.0.0.1:4318/v1/metrics
CUTCTX_OTEL_SERVICE_NAME=cutctx-proxy
CUTCTX_OTEL_RESOURCE_ATTRIBUTES=deployment.environment=dev,service.namespace=cutctx
```

For local validation without a collector:

```bash
CUTCTX_OTEL_METRICS_ENABLED=1
CUTCTX_OTEL_METRICS_EXPORTER=console
cutctx proxy
```

The proxy's `/stats` response now includes an `otel` block that reports whether Cutctx is managing an OTEL exporter for the current process.

Cutctx's managed OTEL exporters are intentionally scoped to Cutctx's own instrumentation. If you already manage global OTEL providers in your app, keep using those and let Cutctx record into the ambient providers instead of enabling `CUTCTX_OTEL_*`.

### OTEL Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_OTEL_METRICS_ENABLED` | `0` | Enables Cutctx-managed OTEL metric export |
| `CUTCTX_OTEL_METRICS_EXPORTER` | `otlp_http` | Exporter type: `otlp_http` or `console` |
| `CUTCTX_OTEL_METRICS_ENDPOINT` | unset | OTLP HTTP metrics endpoint |
| `CUTCTX_OTEL_METRICS_HEADERS` | unset | Comma-separated `key=value` headers for OTLP export |
| `CUTCTX_OTEL_METRICS_EXPORT_INTERVAL_MS` | `10000` | Periodic export interval in milliseconds |
| `CUTCTX_OTEL_SERVICE_NAME` | `cutctx-proxy` in proxy mode | OTEL `service.name` |
| `CUTCTX_OTEL_RESOURCE_ATTRIBUTES` | unset | Comma-separated resource attributes |

### Anonymous Telemetry vs OTEL

Cutctx has two separate systems:

- `CUTCTX_TELEMETRY` / `--no-telemetry` controls the privacy-preserving anonymous data-flywheel beacon and TOIN-related aggregate reporting.
- `CUTCTX_OTEL_*` controls operational OTEL metric export.

They are independent by design so you can disable the anonymous beacon while keeping OTEL metrics enabled, or vice versa.

#### Beacon identity fields

When the anonymous beacon is enabled, each report includes two identity fields
so usage can be segmented by integration surface and deployment shape:

- `cutctx_stack` — how Cutctx is invoked in this process. Values:
  `proxy`, `wrap_<agent>` (e.g. `wrap_claude`, `wrap_codex`),
  `adapter_<lang>_<provider>` (e.g. `adapter_ts_openai`), `mixed`
  (multi-stack proxy with no dominant caller), or `unknown`. Overridable via
  `CUTCTX_STACK`; `cutctx wrap <tool>` sets it automatically.
- `install_mode` — how the proxy is deployed. Values: `wrapped` (spawned by
  `cutctx wrap`), `persistent` (long-lived service on a fixed port),
  `on_demand` (short-lived direct invocation), or `unknown`.
- `requests_by_stack` — for proxies serving multiple integrations (e.g. a
  persistent proxy hit by both `wrap_claude` and a TS adapter), a per-stack
  request count dict mirroring the `cutctx_requests_by_stack` counter.

Clients tag requests with an `X-Cutctx-Stack` header; the proxy's FastAPI
middleware buckets these on `/v1/*`. Detection is best-effort — any failure
falls back to `"unknown"` and never breaks the proxy.

### Langfuse

Langfuse fits next to this implementation as a **trace backend**, not as a metrics backend.

- Cutctx metrics continue to go to `/metrics` and/or your OTEL metrics exporter.
- Langfuse receives OTLP traces for Cutctx's compression pipeline.
- Cutctx's `/stats` response includes a `langfuse` block when Cutctx is managing Langfuse trace export for the process.

Enable it with:

```bash
CUTCTX_LANGFUSE_ENABLED=1
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

For self-hosted Langfuse, set `LANGFUSE_BASE_URL` to your instance URL.

### Health Check

```bash
curl http://localhost:8787/health
```

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600
}
```

## SDK Metrics

### Session Stats

Quick stats for the current session (no database query):

```python
stats = client.get_stats()
print(stats)
```

```python
{
    "session": {
        "requests_total": 10,
        "tokens_input_before": 50000,
        "tokens_input_after": 35000,
        "tokens_saved_total": 15000,
        "tokens_output_total": 8000,
        "cache_hits": 3,
        "compression_ratio_avg": 0.70
    },
    "config": {
        "mode": "optimize",
        "provider": "openai",
        "cache_optimizer_enabled": True,
        "semantic_cache_enabled": False
    },
    "transforms": {
        "smart_crusher_enabled": True,
        "cache_aligner_enabled": True,
        "rolling_window_enabled": True
    }
}
```

### Historical Metrics

Query stored metrics from the database:

```python
from datetime import datetime, timedelta

# Get recent metrics
metrics = client.get_metrics(
    start_time=datetime.utcnow() - timedelta(hours=1),
    limit=100,
)

for m in metrics:
    print(f"{m.timestamp}: {m.tokens_input_before} -> {m.tokens_input_after}")
```

### Summary Statistics

Aggregate statistics across all stored metrics:

```python
summary = client.get_summary()
print(f"Total requests: {summary['total_requests']}")
print(f"Total tokens saved: {summary['total_tokens_saved']}")
print(f"Average compression: {summary['avg_compression_ratio']:.1%}")
print(f"Total cost savings: ${summary['total_cost_saved_usd']:.2f}")
```

## Logging

### Enable Logging

```python
import logging

# INFO level shows compression summaries
logging.basicConfig(level=logging.INFO)

# DEBUG level shows detailed transform decisions
logging.basicConfig(level=logging.DEBUG)
```

### Log Output Examples

```
INFO:cutctx.transforms.pipeline:Pipeline complete: 45000 -> 4500 tokens (saved 40500, 90.0% reduction)
INFO:cutctx.transforms.smart_crusher:SmartCrusher applied top_n strategy: kept 15 of 1000 items
INFO:cutctx.cache.compression_store:CCR cache hit: hash=abc123, retrieved 1000 items
DEBUG:cutctx.transforms.smart_crusher:Kept items: [0,1,2,42,77,97,98,99] (errors at 42, warnings at 77)
```

### Proxy Logging

```bash
# Log to file
cutctx proxy --log-file cutctx.jsonl

# Increase verbosity
cutctx proxy --log-level debug
```

## Grafana Dashboard

Example Grafana dashboard configuration for Prometheus metrics:

```json
{
  "panels": [
    {
      "title": "Tokens Saved",
      "type": "stat",
      "targets": [{"expr": "cutctx_tokens_saved_total"}]
    },
    {
      "title": "Average Request Latency (ms)",
      "type": "gauge",
      "targets": [{"expr": "cutctx_latency_ms_sum / clamp_min(cutctx_latency_ms_count, 1)"}]
    },
    {
      "title": "Max Request Latency (ms)",
      "type": "graph",
      "targets": [{"expr": "cutctx_latency_ms_max"}]
    },
    {
      "title": "Provider Cache Hit Rate",
      "type": "gauge",
      "targets": [{"expr": "cutctx_provider_cache_hit_requests_total / clamp_min(cutctx_provider_cache_requests_total, 1)"}]
    }
  ]
}
```

## Cost Tracking

### Per-Request Cost

Each request includes cost metadata in the response:

```python
response = client.chat.completions.create(...)

# Access via response metadata (if available)
# Cost is calculated based on model pricing and token counts
```

### Budget Alerts

Set a budget limit in the proxy:

```bash
cutctx proxy --budget 10.00
```

When the budget is exceeded:
- Requests return a budget exceeded error
- The `/stats` endpoint shows budget status
- Logs indicate budget state

## Validation

Validate your setup is correct:

```python
result = client.validate_setup()

if result["valid"]:
    print("Setup is correct!")
else:
    print("Issues found:")
    for issue in result["issues"]:
        print(f"  - {issue}")
```

## Key Metrics to Monitor

| Metric | What It Tells You | Target |
|--------|------------------|--------|
| `tokens_saved_total` | Total cost savings | Higher is better |
| `compression_ratio_avg` | Efficiency | 0.7-0.9 typical |
| `cache_hit_rate` | Cache effectiveness | >20% is good |
| `latency_p99` | Performance impact | <10ms |
| `failed_requests` | Reliability | 0 |
