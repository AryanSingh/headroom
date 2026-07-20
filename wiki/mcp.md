# MCP Server — Context Engineering Toolkit

Cutctx's MCP server exposes **compression, retrieval, and observability** as tools that any MCP-compatible AI coding tool can use — Claude Code, Cursor, Codex, and more.

## Quick Start

```bash
# Install (MCP is included with proxy, or standalone)
pip install "cutctx-ai[proxy]"    # Proxy + MCP tools
pip install "cutctx-ai[mcp]"      # MCP tools only (lightweight)

# Register with every detected agent (one-time):
# Claude Code, Claude Desktop app, Codex
cutctx mcp install

# Start Claude Code — it now has cutctx tools!
claude
```

That's it. Claude Code can now compress content on demand, retrieve originals, and check session stats — **no proxy required**.

## Claude Desktop app

`cutctx mcp install` also detects the Claude Desktop app and writes the server
into `claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`,
Windows: `%APPDATA%\Claude\`, Linux: `~/.config/Claude/`). Restrict to Desktop
only with:

```bash
cutctx mcp install --agent claude-desktop
```

Two Desktop-specific notes:

- **Absolute command path.** Desktop launches MCP servers with a minimal GUI
  PATH, so the installer resolves `cutctx` to its absolute path (Homebrew,
  pipx, venv) at registration time. If you edit the config by hand, use the
  full path from `which cutctx`.
- **Restart to load.** Desktop reads the config only at launch — restart the
  app after installing.

In Desktop, the cutctx server itself provides **on-demand tools**
(`cutctx_compress`, `cutctx_retrieve`, `cutctx_stats`). The transparent proxy
pipeline doesn't apply because the app's model endpoint isn't repointable —
for automatic compression, use the gateway below.

### Automatic compression via the MCP gateway

Desktop's model traffic can't be proxied, but its MCP servers are launched
from config entries cutctx controls. `cutctx mcp gateway` is a transparent
stdio proxy that interposes at the **MCP layer**: it spawns the real server,
relays JSON-RPC verbatim, and compresses large `tools/call` results before
they reach model context — which is where most agent tokens go.

```bash
# Wrap every stdio server in claude_desktop_config.json (idempotent, reversible):
cutctx mcp install --gateway

# Or wrap one server manually:
cutctx mcp gateway --name slack -- npx -y slack-mcp-server
```

Wrapping rewrites entries like:

```json
"slack": { "command": "npx", "args": ["-y", "slack-mcp-server"] }
```

to:

```json
"slack": {
  "command": "/opt/homebrew/bin/cutctx",
  "args": ["mcp", "gateway", "--name", "slack", "--", "npx", "-y", "slack-mcp-server"]
}
```

The original invocation is preserved after `--`, so `cutctx mcp uninstall`
restores every entry exactly. Compressed results carry a
`cutctx_retrieve hash=...` marker; with the cutctx MCP server installed
alongside, the model can recover any original in full. Results below the
size threshold (default 2000 chars, `--min-chars`) and non-text content pass
through untouched, and any compression failure forwards the original — the
gateway never breaks a session it can't improve.

### Privacy

Compression runs fully on-machine by default (local Rust transforms, no external model call). The only exception is setting `CUTCTX_ENABLE_KOMPRESS=1`, which downloads an ML model from HuggingFace on first use.

### Known limitations

- Only wraps stdio MCP servers — remote/URL servers pass through uncompressed
- JSON-RPC batch-array frames pass through uncompressed
- Retrieval requires the cutctx MCP server installed alongside, the default on-disk SQLite store (not `CUTCTX_STATELESS`/memory), and the ~1h TTL not yet expired
- Config wrap edits `claude_desktop_config.json` in place but writes a timestamped `.bak-<timestamp>` backup first and is fully reversible via `cutctx mcp uninstall`

For automatic compression of ALL traffic, also run the proxy:

```bash
# Terminal 1
cutctx proxy

# Terminal 2
ANTHROPIC_BASE_URL=http://127.0.0.1:8787 claude
```

## Tools

The MCP server provides three tools:

### cutctx_compress

Compress content on demand. The LLM calls this when it wants to shrink large content before reasoning over it.

```
Tool: cutctx_compress

Parameters:
  - content (required): Text to compress (files, JSON, logs, search results, etc.)

Returns:
  - compressed: Compressed text
  - hash: Key for retrieving the original later
  - original_tokens / compressed_tokens / savings_percent
  - transforms: Which compression algorithms were applied
```

Example — Claude reads a large file, then compresses it:

```
Claude: Let me compress this large output to save context space.

→ cutctx_compress(content="[5000 lines of grep results...]")

← {
    "compressed": "[key matches with context...]",
    "hash": "a1b2c3d4e5f6...",
    "original_tokens": 12000,
    "compressed_tokens": 3200,
    "savings_percent": 73.3,
    "transforms": ["router:search:0.27"]
  }
```

The original is stored locally for the session (1-hour TTL). If Claude needs the full content later, it calls `cutctx_retrieve`.

### cutctx_retrieve

Retrieve original uncompressed content by hash.

```
Tool: cutctx_retrieve

Parameters:
  - hash (required): Hash key from compression
  - query (optional): Search within the original to return only matching items

Returns:
  - original_content (full retrieval) or results (search)
  - source: "local" or "proxy"
```

Retrieval checks the local store first (content compressed via `cutctx_compress`), then falls back to the proxy's store (content compressed automatically by the proxy). Hashes from either source work transparently.

### cutctx_stats

Session compression statistics — including sub-agent stats and proxy cache info.

```
Tool: cutctx_stats

Returns:
  - compressions, retrievals, tokens_saved, savings_percent
  - estimated_cost_saved_usd
  - recent_events (last 10 compression/retrieval events)
  - sub_agents (stats from sub-agent MCP instances, if any)
  - combined (main + sub-agent totals)
  - proxy (request count, cache hits, cost saved — if proxy is running)
```

Sub-agent stats are aggregated via a shared stats file at
`${CUTCTX_WORKSPACE_DIR}/session_stats.jsonl` (default
`~/.cutctx/session_stats.jsonl` — see the
[Filesystem Contract](filesystem-contract.md)). Each MCP server instance
(main session and sub-agents) writes events there, and `cutctx_stats`
reads across all of them.

## Architecture

### MCP Only (no proxy)

```
┌─────────────────────────────────────────────┐
│  Claude Code / Cursor / Codex               │
│                                              │
│  LLM calls cutctx_compress on demand       │
│  ↓                                           │
│  Compression happens locally in MCP process  │
│  Original stored in local CompressionStore   │
│  ↓                                           │
│  LLM calls cutctx_retrieve when needed     │
└─────────────────────────────────────────────┘
```

### MCP + Proxy (full setup)

```
┌─────────────────────────────────────────────┐
│  Claude Code                                 │
│                                              │
│  1. Sends request ──→ Proxy (auto-compress)  │
│  2. Gets response with compressed outputs    │
│  3. Can call cutctx_compress for more      │
│  4. cutctx_retrieve checks:                │
│     local store → proxy store                │
└──────────────────┬──────────────────────────┘
                   │ MCP (stdio)
                   ▼
┌─────────────────────────────────────────────┐
│  Cutctx MCP Server                         │
│  ├── cutctx_compress  (local compression)  │
│  ├── cutctx_retrieve  (local + proxy)      │
│  └── cutctx_stats     (aggregated stats)   │
└─────────────────────────────────────────────┘
```

No double-compression: the proxy compresses at the HTTP level (before the LLM sees content). MCP tools operate after the LLM receives content. They don't touch the same data.

## CLI Commands

### Install

```bash
cutctx mcp install                              # Default setup
cutctx mcp install --proxy-url http://host:9000  # Custom proxy URL
cutctx mcp install --force                       # Overwrite existing
```

### Status

```bash
cutctx mcp status
```

```
Cutctx MCP Status
========================================
MCP SDK:        ✓ Installed
Claude Config:  ✓ Configured
                /Users/you/.claude/mcp.json
Proxy URL:      http://127.0.0.1:8787
Proxy Status:   ✓ Running at http://127.0.0.1:8787
```

### Uninstall

```bash
cutctx mcp uninstall
```

### Debug

```bash
cutctx mcp serve --debug
```

## Cross-Tool Compatibility

The MCP server works with any MCP-compatible host:

| Tool | MCP Support | Setup |
|------|-------------|-------|
| Claude Code | Native | `cutctx mcp install` |
| Cursor | Supported | Add to Cursor MCP settings |
| Codex | If supported | Configure MCP server |
| Any MCP host | Yes | Point to `cutctx mcp serve` |

## Troubleshooting

### "MCP SDK not installed"

```bash
pip install "cutctx-ai[mcp]"
```

### "Proxy not running" (when using proxy features)

```bash
cutctx proxy  # In another terminal
```

### "Entry not found or expired"

- Content compressed via `cutctx_compress`: stored for 1 hour (session TTL)
- Content compressed by the proxy: stored for 5 minutes (proxy TTL)
- The proxy must be running for proxy-compressed content

### Claude doesn't see cutctx tools

1. Check: `cutctx mcp status`
2. Restart Claude Code after installing MCP
3. Verify with `/mcp` in Claude Code — should show 3 cutctx tools

### Sub-agent stats not showing

Sub-agent stats appear in `cutctx_stats` only after sub-agents have run compressions. The shared stats file is at `${CUTCTX_WORKSPACE_DIR}/session_stats.jsonl` (defaults to `~/.cutctx/session_stats.jsonl`).
