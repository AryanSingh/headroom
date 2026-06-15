---
name: cutctx
description: Context compression for AI agents — compress tool outputs, logs, RAG results, and conversation history to save 60-95% tokens. Use when working with large codebases, long tool outputs, or when you need to fit more context into a conversation.
---

# CutCtx — Context Compression

CutCtx compresses everything you read — tool outputs, logs, RAG chunks, files, and conversation history — before it reaches the LLM. Same answers, fraction of the tokens.

## When to Use

- Large tool outputs (file listings, search results, git diffs)
- Long conversation histories eating into context windows
- RAG results with redundant content
- Log analysis and debugging
- Multi-file code reviews

## Quick Start

```bash
# Install
pip install headroom-ai

# One command to compress any text
headroom compress < large_file.txt

# Start a proxy (zero code changes for any app)
headroom proxy --port 8787

# Wrap a coding agent
headroom wrap claude
```

## How It Works

CutCtx uses 6 compression algorithms:

| Algorithm | Best For | Savings |
|-----------|----------|---------|
| **SmartCrusher** | JSON, structured data | 60-90% |
| **CodeCompressor** | Source code (Python, JS, Go, Rust) | 40-70% |
| **DiffCompressor** | Git diffs, patches | 70-95% |
| **LogCompressor** | Log files, stack traces | 80-95% |
| **SearchCompressor** | Search results, documentation | 50-80% |
| **CacheAligner** | Prefix stabilization for KV cache | 0% (cache hit optimization) |

All compression is **reversible** — originals are stored locally and can be retrieved on demand.

## Proxy Mode

The easiest way to use CutCtx is as a proxy. All traffic is compressed automatically:

```bash
# Start the proxy
headroom proxy --port 8787

# Point your app at it
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
claude  # or any other tool
```

## MCP Tools

When running as an MCP server, CutCtx provides these tools:

- **headroom_retrieve** — Retrieve original content from a compression marker
- **headroom_compress** — Compress content on demand
- **headroom_stats** — View session compression statistics

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HEADROOM_PROXY_URL` | `http://127.0.0.1:8787` | Proxy URL |
| `HEADROOM_LICENSE_KEY` | (none) | License key for pro features |

## Learn More

- **Docs**: https://cutctx.dev/docs
- **GitHub**: https://github.com/AryanSingh/cutcxt
- **PyPI**: `pip install headroom-ai[all]`
