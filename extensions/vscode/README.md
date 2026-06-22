# CutCtx — AI Context Compression

Automatically compress LLM context to save 60–90% of tokens. Works transparently with Cursor, Cline, Continue, and any OpenAI-compatible AI tool in VS Code.

## Requirements

```bash
pip install "cutctx-ai[proxy]"
```

## Features

- **Auto-start**: Starts the CutCtx proxy when VS Code launches
- **Status bar**: Shows tokens saved and cost reduction in real time  
- **One-click setup**: Configures Cline and Continue to route through the proxy

## Quick Start

1. Install: `pip install "cutctx-ai[proxy]"`
2. Open VS Code — the proxy starts automatically
3. Run **CutCtx: Configure Active AI Extension** to route Cline or Continue through the proxy

## Commands

| Command | Description |
|---------|-------------|
| `CutCtx: Start Proxy` | Start the compression proxy |
| `CutCtx: Stop Proxy` | Stop the proxy |
| `CutCtx: Show Compression Stats` | View tokens saved |
| `CutCtx: Configure Active AI Extension` | Auto-configure Cline or Continue |

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `cutctx.port` | `8787` | Proxy port |
| `cutctx.autoStart` | `true` | Auto-start proxy on launch |
| `cutctx.binaryPath` | `cutctx` | Path to the cutctx binary |

## Manual Configuration

Set your AI tool's API base URL to `http://127.0.0.1:8787/v1` (OpenAI-compatible) or `http://127.0.0.1:8787` (Anthropic).

## More Info

- Docs: https://cutctx.dev/docs
- GitHub: https://github.com/cutctx/cutctx
