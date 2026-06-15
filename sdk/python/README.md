# cutctx-sdk

Python SDK for [CutCtx](https://cutctx.dev) — AI context compression proxy.

## Quickstart

```python
from cutctx_sdk import CutCtxClient

client = CutCtxClient(api_key="your-license-key")
compressed = client.compress([
    {"role": "user", "content": "Explain quantum computing"}
])
# Send compressed messages to your LLM — tokens reduced 60–95%
```

## Installation

```
pip install cutctx-sdk
```

## API

### `CutCtxClient(proxy_url, api_key, model)`

| Parameter | Default | Description |
|---|---|---|
| `proxy_url` | `http://localhost:8787` | CutCtx proxy base URL |
| `api_key` | `None` | License key for authentication |
| `model` | `claude-sonnet-4-5` | Target model for cost estimation |

### `compress(messages, model=None) → list[dict]`

Send messages through CutCtx compression and return compressed messages.

### `retrieve(ref) → str`

Fetch original content for a `[headroom:ref:HASH]` pointer.

### `stats() → dict`

Get proxy statistics (requires admin auth).

### `health() → dict`

Check proxy health status.

## Shared Context

```python
from cutctx_sdk import SharedContext

ctx = SharedContext()
ctx.put("project", "my-app")
value, found = ctx.get("project")  # ("my-app", True)
ctx.clear()
```
