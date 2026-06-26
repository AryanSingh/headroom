# Cutctx Plugin for Codex

Context compression for OpenAI Codex — compress tool outputs, retrieve originals on demand, and track token savings.

## What It Does

- **Routes Codex traffic through Cutctx proxy** for automatic compression
- **Provides MCP tools** for on-demand compress/retrieve/status
- **Tracks token savings** across your session
- **Works with any OpenAI-compatible model** via the proxy

## Installation

### Quick Install (recommended)

```bash
cutctx install codex
```

Or via pip:

```bash
pip install cutctx-ai
cutctx install codex
```

### Manual Install

1. Run the install script:

```bash
bash plugins/codex/install.sh
```

Or add the provider manually to `~/.codex/config.toml`:

```toml
model_provider = "cutctx"
openai_base_url = "http://127.0.0.1:8787/v1"

[model_providers.cutctx]
name = "Cutctx persistent proxy"
base_url = "http://127.0.0.1:8787/v1"
supports_websockets = true
```

2. Install the MCP server:

```bash
cutctx mcp install --agent codex
```

3. Ensure the runtime is up:

```bash
cutctx init hook ensure --profile init-user
```

## How It Works

```
Codex CLI → Cutctx Proxy (port 8787) → OpenAI API
               ↓
         MCP Server (stdio)
         ├── cutctx_retrieve
         ├── cutctx_compress
         └── cutctx_status
```

1. **Traffic Routing**: Codex sends requests to the local proxy instead of OpenAI directly
2. **Compression**: The proxy compresses large tool outputs (file listings, search results)
3. **Retrieval**: When Codex needs full content, it calls `cutctx_retrieve` via MCP
4. **Status**: View compression ratios and token savings via `cutctx_status`

## Verification

After install, verify the local proxy is reachable:

```bash
curl http://127.0.0.1:8787/health
```

If that endpoint is down, Codex is configured but Cutctx is not yet active, so no token savings will occur until the local runtime starts.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CUTCTX_PROXY_URL` | `http://127.0.0.1:8787` | Proxy URL |
| `OPENAI_BASE_URL` | `http://127.0.0.1:8787/v1` | OpenAI-compatible base URL |
| `CUTCTX_ADMIN_API_KEY` | auto-generated | Admin API key for dashboard |

## Uninstall

```bash
cutctx uninstall codex
```

Or manually:

1. Remove the Cutctx block from `~/.codex/config.toml`
2. Remove MCP config: `cutctx mcp uninstall`
