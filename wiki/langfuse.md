# Langfuse Integration

Cutctx emits OpenTelemetry traces to Langfuse for every compression decision,
CCR operation, and proxy request. Zero code changes required — enable with two
env vars.

## Quick start

```bash
pip install cutctx-ai[langfuse]

export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...

cutctx proxy --langfuse
```

## What gets traced

- Every compression pass: algorithm selected, tokens in/out, ratio, duration
- CCR store operations: put, get, miss, TTL expiry
- Proxy request lifecycle: provider, model, latency, cache hit/miss

## Self-hosted Langfuse

```bash
export LANGFUSE_BASE_URL=https://your-langfuse.company.com
cutctx proxy --langfuse
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `CUTCTX_LANGFUSE_ENABLED` | `0` | Set to `1` to enable |
| `LANGFUSE_PUBLIC_KEY` | — | Your Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | — | Your Langfuse project secret key |
| `LANGFUSE_BASE_URL` | `https://cloud.langfuse.com` | Override for self-hosted |
| `CUTCTX_LANGFUSE_SERVICE_NAME` | `cutctx` | Service name in Langfuse traces |

## Checking status

The `/stats` endpoint reports Langfuse status:
```bash
curl http://127.0.0.1:8787/stats | python3 -m json.tool | grep -A6 langfuse
```
