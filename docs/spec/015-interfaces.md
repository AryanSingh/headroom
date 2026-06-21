# 015. Interfaces

**Status:** done

## CLI Surface

### `cutctx proxy`

Start the Cutctx proxy server.

```bash
cutctx proxy [OPTIONS]
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Bind host |
| `--port` | `8787` | Bind port |
| `--mode` | `token` | Optimization mode: `token` or `cache` |
| `--workers` | `1` | Uvicorn worker processes |
| `--limit-concurrency` | `1000` | Maximum concurrent connections before 503 |
| `--no-optimize` | `false` | Passthrough mode |
| `--no-cache` | `false` | Disable semantic cache |
| `--no-rate-limit` | `false` | Disable rate limiting |
| `--memory` | `false` | Enable persistent memory |
| `--learn` | `false` | Enable live traffic learning |
| `--backend` | `anthropic` | Backend: anthropic, bedrock, openrouter, anyllm, or litellm-* |
| `--no-telemetry` | `false` | Disable anonymous telemetry |
| `--stateless` | `false` | Disable filesystem writes |

---

### `cutctx evals`

Run evaluation suite.

```bash
cutctx evals [OPTIONS]
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--suite` | `all` | Evaluation suite to run |
| `--output` | - | Output file for results |

---

### `cutctx install`

Install agent integrations.

```bash
cutctx install [OPTIONS]
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--agent` | - | Agent type (claude/copilot/codex/aider/cursor/openclaw) |

---

### `cutctx mcp`

Manage the Cutctx MCP server.

```bash
cutctx mcp [OPTIONS] COMMAND [ARGS]...
```

**Commands:**
- `install` — Install the MCP server into detected coding agents
- `serve` — Start the stdio MCP server
- `status` — Check configuration status
- `uninstall` — Remove Cutctx MCP config

---

### `cutctx perf`

Run performance tests.

```bash
cutctx perf [OPTIONS]
```

---

### `cutctx wrap`

Wrap a command with Cutctx proxy.

```bash
cutctx wrap [OPTIONS] -- <command> [args...]
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `8787` | Proxy port |
| `--no-context-tool` / `--no-rtk` | `false` | Skip CLI context-tool setup |

**Supported Commands:**
- `claude` — Wrap Claude Code
- `copilot` — Wrap GitHub Copilot
- `codex` — Wrap OpenAI Codex
- `aider` — Wrap Aider
- `cursor` — Wrap Cursor
- `openclaw` — Wrap OpenClaw

---

### `cutctx memory`

Memory system management (requires numpy/hnswlib).

```bash
cutctx memory [OPTIONS]
```

**Commands:**
- `list` — List stored memories
- `stats` — Show memory statistics
- `search QUERY` — Search memories

---

### `cutctx learn`

Run learn mode analysis.

```bash
cutctx learn [OPTIONS]
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--project` | current directory | Project directory to analyze |
| `--all` | `false` | Analyze all discovered projects |
| `--apply` | `false` | Write recommendations instead of dry-run |
| `--agent` | `auto` | Agent to analyze: auto, claude, codex, gemini, or plugin |
| `--model` | auto | LLM model for analysis |
| `--workers` | auto | Parallel workers for session scanning |

---

### `cutctx stats`

Show savings statistics.

```bash
cutctx stats [OPTIONS]
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--period` | `24h` | Time period |
| `--format` | `table` | Output format (table, json, csv) |

---

### `cutctx config`

Manage configuration.

```bash
cutctx config [COMMAND] [OPTIONS]
```

**Commands:**
- `get KEY` — Get config value
- `set KEY VALUE` — Set config value
- `list` — List all config
- `export` — Export config to file

---

## HTTP API

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/livez` | Liveness check |
| `GET` | `/readyz` | Readiness check |
| `POST` | `/v1/messages` | Proxy chat completions |
| `POST` | `/v1/embeddings` | Proxy embeddings |
| `POST` | `/v1/compress` | Direct compression |
| `POST` | `/v1/retrieve` | CCR retrieval |
| `GET` | `/stats` | Compression statistics |
| `GET` | `/metrics` | Prometheus metrics |

### Request/Response Examples

**POST /v1/messages:**
```bash
curl -X POST http://localhost:8787/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-..." \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**Response headers:**
```
X-Cutctx-Savings: 0.35
X-Cutctx-Original-Tokens: 8192
X-Cutctx-Compressed-Tokens: 5325
```

---

## Environment Variables

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_MODE` | `token` | Proxy optimization mode (`token` or `cache`) |
| `CUTCTX_PORT` | `8787` | Proxy port |
| `CUTCTX_HOST` | `127.0.0.1` | Proxy host |
| `CUTCTX_WORKERS` | `1` | Uvicorn worker count |
| `CUTCTX_LIMIT_CONCURRENCY` | `1000` | Maximum concurrent connections before 503 |
| `CUTCTX_MAX_CONNECTIONS` | `500` | Maximum upstream HTTP connections |
| `CUTCTX_MAX_KEEPALIVE` | `100` | Maximum upstream keep-alive connections |
| `CUTCTX_BUDGET` | - | Daily budget limit in USD |
| `CUTCTX_TELEMETRY` | enabled | Set to `off` to disable anonymous telemetry |
| `CUTCTX_STATELESS` | `false` | Disable filesystem writes |

### Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | - | Anthropic API key |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `GOOGLE_API_KEY` | - | Google AI API key |
| `COHERE_API_KEY` | - | Cohere API key |

### Features

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_TELEMETRY` | enabled | Set to `off` to disable telemetry |
| `CUTCTX_MIN_EVIDENCE` | `5` | Minimum observations before live learning persists a pattern |
| `CUTCTX_PROXY_EXTENSIONS` | - | Comma-separated proxy extensions to enable |
| `CUTCTX_STATELESS` | `false` | Disable filesystem writes |
| `CUTCTX_MODEL_LIMITS` | - | Model limits override as JSON or file path |

### Compression

| Variable | Default | Description |
|----------|---------|-------------|
| `CUTCTX_MAX_TOKENS` | `4096` | Max tokens per request |
| `CUTCTX_TARGET_TOKENS` | - | Target tokens after compression |
| `CUTCTX_OVERLAP_TOKENS` | `512` | Overlap tokens for chunking |
| `CUTCTX_CONTENT_SENSITIVITY` | `0.5` | Content sensitivity (0-1) |
| `CUTCTX_PRESERVE_SYSTEM` | `true` | Preserve system messages |

---

## Plugin ABI

### Plugin Interface

```python
from abc import ABC, abstractmethod
from cutctx.learn.base import ConversationScanner, ContextWriter
from cutctx.learn.models import ProjectInfo, SessionData

class LearnPlugin(ConversationScanner):
    """A self-contained learn plugin for a single coding agent."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short lowercase identifier (e.g., 'claude', 'cursor')."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name (e.g., 'Claude Code', 'Cursor')."""
        ...

    @abstractmethod
    def detect(self) -> bool:
        """Return True if this agent has data on the current machine."""
        ...

    @abstractmethod
    def discover_projects(self) -> list[ProjectInfo]:
        """Discover all projects with conversation data."""
        ...

    @abstractmethod
    def scan_project(self, project: ProjectInfo, max_workers: int = 1) -> list[SessionData]:
        """Scan all sessions for a project."""
        ...

    @abstractmethod
    def create_writer(self) -> ContextWriter:
        """Return the appropriate ContextWriter for this agent."""
        ...
```

### Plugin Registration

Plugins are auto-discovered from `cutctx/learn/plugins/` directory.

**Manual registration:**
```python
from cutctx.learn import plugin_registry

plugin_registry.register(MyPlugin())
```

### Plugin Config

```yaml
# ~/.cutctx/config.yaml
learn:
  enabled: true
  plugins:
    - name: claude
      enabled: true
      config:
        session_modes:
          - auto
          - learn
          - disabled
    - name: my_plugin
      enabled: true
      config:
        custom_option: value
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0-draft | 2026-04-16 | Initial interfaces document |
