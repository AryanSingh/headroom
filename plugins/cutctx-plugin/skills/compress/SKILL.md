---
name: compress
description: |
  Compress context using Cutctx to save 60-95% tokens. Use when: working with large tool outputs (file listings, search results, git diffs), long conversation histories, RAG results, log analysis, multi-file code reviews, or any context that's eating into token limits. Trigger when context is large or when the user asks to compress, summarize, or save tokens.
---

# Cutctx Context Compression

You have access to Cutctx, a context compression tool that saves 60-95% tokens while preserving accuracy.

## Auto-Start (runs automatically on session start)

Cutctx proxy starts automatically when this plugin loads. If it's not running:

```bash
# Start the proxy in the background
cutctx proxy --port 8787 &

# Wait for it to be ready
until curl -sf http://127.0.0.1:8787/livez >/dev/null 2>&1; do
  sleep 0.5
done
```

The proxy runs on `http://127.0.0.1:8787` and compresses all requests automatically.

## Available Commands

### Compress text
```bash
echo "large text here" | cutctx compress
```

### Compress a file
```bash
cutctx compress < large_file.txt
```

### Check compression stats
```bash
cutctx stats
```

### Start the proxy (manual, if auto-start failed)
```bash
cutctx proxy --port 8787
```

### Retrieve original content from CCR
```bash
cutctx retrieve <hash>
```

## Compression Algorithms

| Algorithm | Best For | Savings |
|-----------|----------|---------|
| SmartCrusher | JSON, structured data | 60-90% |
| CodeCompressor | Source code (Python, JS, Go, Rust) | 40-70% |
| DiffCompressor | Git diffs, patches | 70-95% |
| LogCompressor | Log files, stack traces | 80-95% |
| SearchCompressor | Search results, documentation | 50-80% |

## When to Compress

1. **Large tool outputs** — File listings, search results, API responses
2. **Long histories** — Conversation histories exceeding context limits
3. **Code reviews** — Multi-file diffs and code analysis
4. **Log analysis** — Stack traces, error logs, debug output
5. **RAG results** — Retrieval results with redundant content

## Example Workflow

When you receive a large tool output:
1. Check if it's compressible (JSON, code, logs, diffs)
2. Run: `echo '<content>' | cutctx compress`
3. Use the compressed version in your response
4. If the user needs full details, run: `cutctx retrieve <hash>`

## Installation

If Cutctx is not installed:
```bash
pip install cutctx-ai
```

Or for all features:
```bash
pip install "cutctx-ai[all]"
```

The CLI binary is `cutctx` (installed via the `cutctx-ai` package).

## Learn More

- **Docs**: https://cutctx.dev/docs
- **GitHub**: https://github.com/cutctx/cutctx
- **Proxy mode**: `cutctx proxy --port 8787` (zero code changes, automatic compression)
