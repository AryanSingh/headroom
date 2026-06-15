# CutCtx Plugin for Claude Code

Context compression that runs inside Claude Code — compress tool outputs, retrieve originals on demand, and track token savings.

## What It Does

- **Auto-starts the CutCtx proxy** when Claude Code launches
- **Compresses tool outputs** (file listings, search results, logs) before they reach the LLM
- **Provides MCP tools** for on-demand compress/retrieve/stats
- **Tracks token savings** across your session

## Installation

### Quick Install (recommended)

```bash
cutctx install claude
```

Or via pip:

```bash
pip install cutctx-ai
cutctx install claude
```

### Manual Install

1. Copy this directory to `~/.claude/plugins/cutctx/`
2. Add to your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "plugins": {
    "cutctx": {
      "path": "~/.claude/plugins/cutctx",
      "enabled": true
    }
  }
}
```

3. Install the MCP server:

```bash
cutctx mcp install --agent claude
```

4. Start the proxy (or let the plugin auto-start it):

```bash
cutctx proxy
```

## How It Works

```
Claude Code → CutCtx Plugin → Proxy (port 8787) → LLM Provider
                  ↓
            MCP Server (stdio)
            ├── headroom_retrieve
            ├── headroom_compress
            └── headroom_stats
```

1. **Session Start**: Plugin hooks auto-start the CutCtx proxy if not running
2. **Tool Use**: Before tool results reach Claude, the proxy compresses large outputs
3. **Retrieval**: When Claude needs full content, it calls `headroom_retrieve` via MCP
4. **Stats**: View compression ratios and token savings via `headroom_stats`

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CUTCTX_PROXY_URL` | `http://127.0.0.1:8787` | Proxy URL |
| `CUTCTX_AUTO_START` | `1` | Auto-start proxy on session start |
| `HEADROOM_ADMIN_API_KEY` | auto-generated | Admin API key for dashboard |

## Uninstall

```bash
cutctx uninstall claude
```

Or manually:

1. Remove from `~/.claude/settings.json`
2. Remove `~/.claude/plugins/cutctx/`
3. Remove MCP config: `cutctx mcp uninstall`
