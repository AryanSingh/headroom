# CLI Reference

This page is the authoritative reference for the **Python Cutctx CLI** exposed by the `cutctx` console script.

## Global behavior

### Entry points

- Console script: `cutctx`
- Python module entrypoint: `python -m cutctx.cli`

### Global options

| Option | Scope | Meaning |
|---|---|---|
| `--help`, `-?` | root, groups, commands | Show help and exit |
| `--version`, `-v` | root only | Show the Cutctx version and exit |

> `-v` is a **root-level version alias**. Inside subcommands such as `cutctx wrap claude -v`, `-v` keeps its subcommand meaning (`--verbose`), not version.

## Command index

| Command | Purpose | Docker-native parity |
|---|---|---|
| `cutctx install ...` | Install and manage persistent deployments | **python-native; Docker-native wrapper supports `persistent-docker` lifecycle subset** |
| `cutctx proxy` | Run the Cutctx proxy server | **native in container** |
| `cutctx learn` | Learn from past tool-call failures | **native in container** |
| `cutctx perf` | Summarize recent proxy performance | **native in container** |
| `cutctx evals ...` | Run memory evaluation workflows | **native in container** |
| `cutctx memory ...` | Inspect and manage stored memories | **native in container** |
| `cutctx mcp ...` | Install, inspect, remove, or serve MCP integration | **native in container** |
| `cutctx wrap claude` | Start proxy and launch Claude Code | **host-bridged** |
| `cutctx wrap cline` | Start proxy and configure Cline (VS Code) | **host-bridged** |
| `cutctx wrap codex` | Start proxy and launch Codex CLI | **host-bridged** |
| `cutctx wrap continue` | Start proxy and configure Continue (VS Code/JetBrains) | **host-bridged** |
| `cutctx wrap copilot` | Start proxy and launch GitHub Copilot CLI | **python-native only** |
| `cutctx wrap cursor` | Start proxy and print Cursor config guidance | **host-bridged** |
| `cutctx wrap aider` | Start proxy and launch Aider | **host-bridged** |
| `cutctx wrap gemini` | Start proxy and launch Gemini CLI | **host-bridged** |
| `cutctx wrap goose` | Start proxy and launch Goose CLI | **host-bridged** |
| `cutctx wrap openclaw` | Install and configure the OpenClaw plugin | **host-bridged** |
| `cutctx wrap openhands` | Start proxy and launch OpenHands CLI | **host-bridged** |
| `cutctx wrap opencode` | Start proxy and launch opencode CLI | **host-bridged** |
| `cutctx wrap windsurf` | Start proxy and print Windsurf config guidance | **host-bridged** |
| `cutctx wrap zed` | Start proxy and print Zed `settings.json` snippet | **host-bridged** |
| `cutctx unwrap openclaw` | Disable the Cutctx OpenClaw plugin | **host-bridged** |

## Captured `--help` output

The sections below capture the current top-level help output from the live CLI.

### `cutctx --help`

```text
Usage: cutctx [OPTIONS] COMMAND [ARGS]...

  Cutctx - The Context Optimization Layer for LLM Applications.

  Manage memories, run the optimization proxy, and analyze metrics.

  Examples:
      cutctx proxy              Start the optimization proxy
      cutctx memory list        List stored memories
      cutctx memory stats       Show memory statistics

Options:
  -v, --version  Show the version and exit.
  -?, --help     Show this message and exit.

Commands:
  evals   Memory evaluation commands.
  install Install and manage persistent Cutctx deployments.
  learn   Learn from past tool call failures to prevent future ones.
  mcp     MCP server for Claude Code integration.
  memory  Manage memories stored in Cutctx.
  perf    Analyze proxy performance from logs.
  proxy   Start the optimization proxy server.
  unwrap  Undo durable Cutctx wrapping for supported tools.
  wrap    Wrap CLI tools to run through Cutctx.
```

### Top-level command help snapshots

<details>
<summary><code>cutctx proxy --help</code></summary>

```text
Usage: cutctx proxy [OPTIONS]

  Start the optimization proxy server.

  Examples:
      cutctx proxy                    Start proxy on port 8787
      cutctx proxy --port 8080        Start proxy on port 8080
      cutctx proxy --no-optimize      Passthrough mode (no optimization)

  Usage with Claude Code:
      ANTHROPIC_BASE_URL=http://localhost:8787 claude

  Usage with OpenAI-compatible clients:
      OPENAI_BASE_URL=http://localhost:8787/v1 your-app
```

</details>

<details>
<summary><code>cutctx learn --help</code></summary>

```text
Usage: cutctx learn [OPTIONS]

  Learn from past tool call failures to prevent future ones.
```

</details>

<details>
<summary><code>cutctx perf --help</code></summary>

```text
Usage: cutctx perf [OPTIONS]

  Analyze proxy performance from logs.
```

</details>

<details>
<summary><code>cutctx evals --help</code></summary>

```text
Usage: cutctx evals [OPTIONS] COMMAND [ARGS]...

  Memory evaluation commands.

Commands:
  memory     Run LoCoMo memory evaluation benchmark.
  memory-v2  Run LoCoMo V2 evaluation with LLM-controlled memory tools.
```

</details>

<details>
<summary><code>cutctx memory --help</code></summary>

```text
Usage: cutctx memory [OPTIONS] COMMAND [ARGS]...

  Manage memories stored in Cutctx.

Commands:
  delete  Delete one or more memories by ID.
  edit    Edit a memory's content or importance.
  export  Export all memories to JSON.
  import  Import memories from a JSON file.
  list    List stored memories with optional filters.
  prune   Prune memories matching specified criteria.
  purge   Delete ALL memories from the database.
  show    Show full details of a single memory.
  stats   Show memory store statistics.
```

</details>

<details>
<summary><code>cutctx mcp --help</code></summary>

```text
Usage: cutctx mcp [OPTIONS] COMMAND [ARGS]...

  MCP server for Claude Code integration.

Commands:
  install    Install Cutctx MCP server into Claude Code config.
  serve      Start the MCP server (called by Claude Code).
  status     Check Cutctx MCP configuration status.
  uninstall  Remove Cutctx MCP server from Claude Code config.
```

</details>

<details>
<summary><code>cutctx install --help</code></summary>

```text
Usage: cutctx install [OPTIONS] COMMAND [ARGS]...

  Install and manage persistent Cutctx deployments.

Options:
  -?, --help  Show this message and exit.

Commands:
  apply    Install a persistent Cutctx deployment.
  remove   Remove a persistent deployment and undo managed config.
  restart  Restart a persistent deployment.
  start    Start a persistent deployment.
  status   Show persistent deployment status.
  stop     Stop a persistent deployment.
```

</details>

<details>
<summary><code>cutctx wrap --help</code></summary>

```text
Usage: cutctx wrap [OPTIONS] COMMAND [ARGS]...

  Wrap CLI tools to run through Cutctx.

Commands:
  aider      Launch aider through Cutctx proxy.
  claude     Launch Claude Code through Cutctx proxy.
  cline      Start Cutctx proxy for use with Cline (VS Code extension).
  codex      Launch OpenAI Codex CLI through Cutctx proxy.
  continue   Start Cutctx proxy for use with Continue (VS Code / JetBrains).
  copilot    Launch GitHub Copilot CLI through Cutctx proxy.
  cursor     Start Cutctx proxy for use with Cursor.
  gemini     Launch Gemini CLI through Cutctx proxy.
  goose      Launch Goose (Block) CLI through Cutctx proxy.
  openclaw   Install and configure the Cutctx OpenClaw plugin in one...
  opencode   Launch opencode through Cutctx proxy.
  openhands  Launch OpenHands CLI through Cutctx proxy.
  windsurf   Start Cutctx proxy for use with Windsurf.
  zed        Start Cutctx proxy for use with Zed editor.
```

</details>

<details>
<summary><code>cutctx unwrap --help</code></summary>

```text
Usage: cutctx unwrap [OPTIONS] COMMAND [ARGS]...

  Undo durable Cutctx wrapping for supported tools.

Commands:
  openclaw  Disable the Cutctx OpenClaw plugin and restore the legacy engine slot.
```

</details>

## `cutctx proxy`

Start the optimization proxy server.

```bash
cutctx proxy
cutctx proxy --port 8787
cutctx proxy --mode cache
```

| Option | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Host interface to bind |
| `--port`, `-p` | `8787` | Port to bind |
| `--mode` | runtime default | Optimization mode: `token`, `cache` |
| `--no-optimize` | off | Disable optimization and operate in passthrough mode |
| `--no-cache` | off | Disable semantic caching |
| `--no-rate-limit` | off | Disable rate limiting |
| `--retry-max-attempts` | runtime default `3` | Maximum upstream retry attempts |
| `--connect-timeout-seconds` | runtime default `10` | Upstream connection timeout |
| `--anthropic-pre-upstream-concurrency` | auto `max(2, min(8, cpu_count))` | Cap simultaneous pre-upstream work on `/v1/messages` (body read, deep copy, first compression stage, memory-context lookup, upstream connect). `0` or negative disables (unbounded); any positive integer is honoured verbatim. Prevents cold-start replay storms from starving `/livez`, `/readyz`, and new Codex WS opens. |
| `--anthropic-pre-upstream-acquire-timeout-seconds` | `15.0` | Fail fast when the Anthropic pre-upstream queue is saturated. Requests that wait longer return `503` with `Retry-After` instead of parking indefinitely. |
| `--anthropic-pre-upstream-memory-context-timeout-seconds` | `2.0` | Fail-open timeout for Anthropic memory-context lookup while the request still holds a pre-upstream slot. |
| `--log-file` | unset | JSONL log output path |
| `--budget` | unset | Daily USD budget limit |
| `--no-code-aware` | off | Disable AST-aware code compression |
| `--code-aware` | off | Enable code-aware compression in the proxy (env: CUTCTX_CODE_AWARE_ENABLED) |
| `--no-read-lifecycle` | off | Disable stale/superseded read compression |

| `--memory` | off | Enable persistent user memory |
| `--memory-db-path` | `""` | Override memory DB path (help text: `{cwd}/.cutctx/memory.db`) |
| `--no-memory-tools` | off | Disable automatic memory tool injection |
| `--no-memory-context` | off | Disable automatic memory context injection |
| `--memory-top-k` | `10` | Number of memories to inject |
| `--learn` | off | Enable live traffic learning |
| `--no-learn` | off | Explicitly disable traffic learning |
| `--backend` | `anthropic` | Backend: `anthropic`, `bedrock`, `openrouter`, `anyllm`, or `litellm-*` |
| `--anyllm-provider` | `openai` | Provider name for `anyllm` |
| `--anthropic-api-url` | unset | Custom Anthropic passthrough API URL |
| `--openai-api-url` | unset | Custom OpenAI passthrough API URL |
| `--gemini-api-url` | unset | Custom Gemini passthrough API URL |
| `--region` | `us-west-2` | Cloud region for Bedrock / Vertex / related backends |
| `--bedrock-region` | unset | Deprecated Bedrock region override |
| `--bedrock-profile` | unset | AWS profile name for Bedrock |
| `--no-telemetry` | off | Disable anonymous usage telemetry |

Notes:

- `--learn` implies memory unless `--no-learn` is also set.
- Proxy startup can also read environment variables such as `CUTCTX_HOST`, `CUTCTX_PORT`, `CUTCTX_BUDGET`, `CUTCTX_MODE`, `CUTCTX_ANYLLM_PROVIDER`, `CUTCTX_ANTHROPIC_PRE_UPSTREAM_CONCURRENCY`, `CUTCTX_ANTHROPIC_PRE_UPSTREAM_ACQUIRE_TIMEOUT_SECONDS`, `CUTCTX_ANTHROPIC_PRE_UPSTREAM_MEMORY_CONTEXT_TIMEOUT_SECONDS`, `ANTHROPIC_TARGET_API_URL`, `OPENAI_TARGET_API_URL`, and `GEMINI_TARGET_API_URL`. CLI flags take precedence over environment variables.
- The default Anthropic pre-upstream cap is intentionally conservative for CPU/ONNX-heavy work. Larger containers may want to raise it after checking the resolved runtime values on `/readyz` or `/debug/warmup`.

See also: [Proxy Server](proxy.md), [Configuration](configuration.md)

## `cutctx learn`

Learn from past tool-call failures and produce agent guidance.

```bash
cutctx learn
cutctx learn --apply
cutctx learn --agent codex --all
```

| Option | Default | Meaning |
|---|---|---|
| `--project` | current project resolution | Target project path |
| `--all` | off | Analyze all discovered projects |
| `--apply` | off | Write recommendations instead of dry-run output |
| `--agent` | `auto` | Agent source: `auto`, built-ins (`claude`, `codex`, `gemini`), or plugin-provided names |
| `--model` | auto-detect | LLM model used for analysis |

Notes:

- `--agent auto` scans all detected agent data sources.
- If `--project` is omitted, Cutctx resolves from the current directory upward.
- External agent integrations register through the `cutctx.learn_plugin` entry point.

See also: [Failure Learning](learn.md)

## `cutctx perf`

Summarize recent proxy performance from the local proxy log.

```bash
cutctx perf
cutctx perf --hours 24
cutctx perf --raw
```

| Option | Default | Meaning |
|---|---|---|
| `--hours` | `168.0` | Time window in hours |
| `--raw` | off | Print raw PERF records instead of the summarized report |

The command reads `${CUTCTX_WORKSPACE_DIR}/logs/proxy.log` (defaults
to `~/.cutctx/logs/proxy.log` — see the
[Filesystem Contract](filesystem-contract.md)).

## `cutctx evals`

Memory evaluation command group.

### `cutctx evals memory`

Run the LoCoMo memory evaluation benchmark.

```bash
cutctx evals memory -n 3
cutctx evals memory --answer-model gpt-4o --llm-judge
```

| Option | Default | Meaning |
|---|---|---|
| `--n-conversations`, `-n` | all available | Number of conversations to evaluate |
| `--categories` | benchmark default | Comma-separated categories |
| `--include-adversarial` | off | Include category 5 / unanswerable questions |
| `--top-k` | `10` | Memories retrieved per question |
| `--f1-threshold` | `0.5` | Threshold for correctness |
| `--answer-model` | unset | Model for answer generation |
| `--llm-judge` | off | Use LLM-as-judge scoring |
| `--judge-provider` | `litellm` | Judge provider: `openai`, `anthropic`, `litellm`, `simple` |
| `--judge-model` | `gpt-4o` | Judge model |
| `--output`, `-o` | unset | Save JSON results to a path |
| `--no-extract` | off | Disable LLM memory extraction |
| `--extraction-model` | `gpt-4o-mini` | Memory extraction model |
| `--pass-all` | off | Require all checks to pass |
| `--parallel` | `10` | Parallel worker count |
| `--debug` | off | Enable debug output |

### `cutctx evals memory-v2`

Run the V2 memory evaluation flow with LLM-controlled tools.

```bash
cutctx evals memory-v2
cutctx evals memory-v2 --save-model gpt-4o-mini --llm-judge
```

| Option | Default | Meaning |
|---|---|---|
| `--n-conversations`, `-n` | all available | Number of conversations to evaluate |
| `--categories` | benchmark default | Comma-separated categories |
| `--include-adversarial` | off | Include adversarial questions |
| `--f1-threshold` | `0.5` | Threshold for correctness |
| `--save-model` | `gpt-4o-mini` | Model used when persisting memories |
| `--answer-model` | `gpt-4o` | Answer model |
| `--max-results` | `10` | Maximum tool results |
| `--no-graph` | off | Disable graph usage |
| `--llm-judge` | off | Use LLM-as-judge scoring |
| `--judge-model` | `gpt-4o` | Judge model |
| `--output`, `-o` | unset | Save JSON results |
| `--parallel` | `5` | Parallel worker count |
| `--debug` | off | Enable debug output |

Hidden compatibility shims exist for older command paths:

- `cutctx memory-eval`
- `cutctx memory-eval-v2`

These are intentionally omitted from normal usage docs.

## `cutctx memory`

Memory management command group. This group is only registered when the optional memory dependencies import successfully.

### `cutctx memory list`

```bash
cutctx memory list
cutctx memory list --scope USER --since 7d
cutctx memory list -q "budget"
```

| Option | Default | Meaning |
|---|---|---|
| `--db-path` | `cutctx_memory.db` | Memory database path |
| `--limit`, `-n` | `50` | Maximum memories to show |
| `--session`, `-s` | unset | Filter by session ID |
| `--scope` | unset | `USER`, `SESSION`, `AGENT`, or `TURN` |
| `--since` | unset | Age filter using duration syntax such as `7d`, `2w`, `1m` |
| `--search`, `-q` | unset | Content search query |

### `cutctx memory show <memory_id>`

```bash
cutctx memory show 1234abcd
cutctx memory show 1234abcd --json
```

| Argument / option | Default | Meaning |
|---|---|---|
| `memory_id` | required | Full or partial memory ID |
| `--db-path` | `cutctx_memory.db` | Memory database path |
| `--json` | off | Emit raw JSON |

### `cutctx memory stats`

```bash
cutctx memory stats
```

| Option | Default | Meaning |
|---|---|---|
| `--db-path` | `cutctx_memory.db` | Memory database path |

### `cutctx memory edit <memory_id>`

```bash
cutctx memory edit 1234abcd --content "Updated note"
cutctx memory edit 1234abcd --importance 0.9
```

| Argument / option | Default | Meaning |
|---|---|---|
| `memory_id` | required | Full or partial memory ID |
| `--db-path` | `cutctx_memory.db` | Memory database path |
| `--content`, `-c` | unset | New memory content |
| `--importance`, `-i` | unset | New importance score (`0.0` to `1.0`) |

At least one of `--content` or `--importance` is required.

### `cutctx memory delete <memory_ids...>`

```bash
cutctx memory delete 1234abcd 5678efgh
cutctx memory delete 1234abcd --force
```

| Argument / option | Default | Meaning |
|---|---|---|
| `memory_ids...` | required | One or more memory IDs |
| `--db-path` | `cutctx_memory.db` | Memory database path |
| `--force`, `-f` | off | Skip confirmation |

### `cutctx memory prune`

```bash
cutctx memory prune --older-than 30d --dry-run
cutctx memory prune --scope SESSION --force
```

| Option | Default | Meaning |
|---|---|---|
| `--db-path` | `cutctx_memory.db` | Memory database path |
| `--older-than` | unset | Age threshold |
| `--scope` | unset | Scope filter: `USER`, `SESSION`, `AGENT`, `TURN` |
| `--low-importance` | unset | Importance cutoff |
| `--session`, `-s` | unset | Session ID filter |
| `--dry-run` | off | Show what would be removed |
| `--force`, `-f` | off | Skip confirmation |

At least one filter is required. Filters combine with **AND** semantics.

### `cutctx memory purge`

```bash
cutctx memory purge --confirm
```

| Option | Default | Meaning |
|---|---|---|
| `--db-path` | `cutctx_memory.db` | Memory database path |
| `--confirm` | off | Required confirmation flag |

### `cutctx memory export`

```bash
cutctx memory export
cutctx memory export --output export.json
```

| Option | Default | Meaning |
|---|---|---|
| `--db-path` | `cutctx_memory.db` | Memory database path |
| `--output`, `-o` | stdout | Output path |

### `cutctx memory import <file>`

```bash
cutctx memory import export.json
cutctx memory import export.json --force
```

| Argument / option | Default | Meaning |
|---|---|---|
| `file` | required | JSON file containing exported memories |
| `--db-path` | `cutctx_memory.db` | Memory database path |
| `--force`, `-f` | off | Skip confirmation |

The import expects a JSON array. Malformed entries are skipped.

## `cutctx mcp`

Manage the Cutctx MCP server integration.

### `cutctx mcp install`

```bash
cutctx mcp install
cutctx mcp install --proxy-url http://127.0.0.1:9000
```

| Option | Default | Meaning |
|---|---|---|
| `--proxy-url` | `http://127.0.0.1:8787` | Proxy URL written into MCP config |
| `--force` | off | Overwrite an existing Cutctx MCP config |

### `cutctx mcp uninstall`

```bash
cutctx mcp uninstall
```

This removes the Cutctx MCP server entry from the Claude configuration.

### `cutctx mcp status`

```bash
cutctx mcp status
```

This inspects MCP SDK availability, Claude config state, and proxy reachability.

### `cutctx mcp serve`

```bash
cutctx mcp serve
cutctx mcp serve --proxy-url http://127.0.0.1:9000 --debug
```

| Option | Default | Meaning |
|---|---|---|
| `--proxy-url` | `http://127.0.0.1:8787` | Proxy URL (also reads `CUTCTX_PROXY_URL`) |
| `--direct` | off | Disable stdio transport wrapping |
| `--debug` | off | Enable debug logging |

`serve` is part of the public CLI, but it is usually consumed by MCP host tooling rather than by humans directly.

See also: [MCP Tools](mcp.md)

## `cutctx install`

Install and manage persistent local Cutctx deployments.

### `cutctx install apply --help`

```text
Usage: cutctx install apply [OPTIONS]

  Install a persistent Cutctx deployment.

Options:
  --preset [persistent-service|persistent-task|persistent-docker]
                                  Persistent runtime preset to install.
                                  [default: persistent-service]
  --runtime [python|docker]       Runtime used to execute Cutctx for
                                  service/task modes.  [default: python]
  --scope [provider|user|system]  Where to apply persistent configuration.
                                  [default: user]
  --providers [auto|all|manual]   Target selection mode for direct tool
                                  configuration.  [default: auto]
  --target [claude|copilot|codex|aider|cursor|openclaw]
                                  Tool target to configure when --providers
                                  manual is used.
  --profile TEXT                  Deployment profile name.  [default: default]
  -p, --port INTEGER              Persistent proxy port.  [default: 8787]
  --backend TEXT                  Proxy backend for the persistent runtime.
                                  [default: anthropic]
  --anyllm-provider TEXT          Provider for any-llm backends when --backend
                                  anyllm is used.
  --region TEXT                   Cloud region for Bedrock / Vertex style
                                  backends.
  --mode TEXT                     Proxy optimization mode.  [default: token]
  --memory                        Enable persistent memory in the proxy runtime.
  --no-telemetry                  Disable anonymous telemetry in the runtime.
  --image TEXT                    Docker image to use when runtime=docker or
                                  preset=persistent-docker.  [default:
                                  ghcr.io/cutctx/cutctx:latest]
  -?, --help                      Show this message and exit.
```

### `cutctx install apply`

```bash
cutctx install apply --preset persistent-service --providers auto
cutctx install apply --preset persistent-task --providers manual --target claude --target codex
cutctx install apply --preset persistent-docker --scope user
```

| Option | Default | Meaning |
|---|---|---|
| `--preset` | `persistent-service` | Lifecycle preset: `persistent-service`, `persistent-task`, or `persistent-docker` |
| `--runtime` | `python` | Runtime used for service/task installs: `python` or `docker` |
| `--scope` | `user` | Config scope: `provider`, `user`, or `system` |
| `--providers` | `auto` | Target selection mode: `auto`, `all`, or `manual` |
| `--target` | repeatable | Tool target used with `--providers manual` |
| `--profile` | `default` | Deployment profile name |
| `--port`, `-p` | `8787` | Persistent proxy port |
| `--backend` | `anthropic` | Backend for the managed runtime |
| `--anyllm-provider` | unset | Provider name used with `--backend anyllm` |
| `--region` | unset | Cloud region override |
| `--mode` | `token` | Proxy optimization mode |
| `--memory` | off | Enable persistent memory in the managed runtime |
| `--no-telemetry` | off | Disable anonymous telemetry |
| `--image` | `ghcr.io/cutctx/cutctx:latest` | Docker image for Docker-backed installs |

`apply` stores a manifest under
`${CUTCTX_WORKSPACE_DIR}/deploy/<profile>/manifest.json` (default
`~/.cutctx/deploy/<profile>/manifest.json`), applies managed tool
configuration, starts the chosen runtime, and waits for `readyz`.

Docker-native host wrappers expose a narrower `cutctx install` subset for `persistent-docker` only: `apply`, `status`, `start`, `stop`, `restart`, and `remove`. Those wrapper flows preserve the same port and manifest behavior, but they intentionally reject `persistent-service`, `persistent-task`, and provider mutation flags like `--scope`, `--providers`, and `--target`.

### `cutctx install status`

```bash
cutctx install status
cutctx install status --profile default
```

Shows the stored profile, preset, runtime, supervisor kind, scope, port, runtime status, readiness, and backend from `/health`.

### `cutctx install start`

```bash
cutctx install start
cutctx install start --profile default
```

Starts a previously installed deployment profile without reapplying mutations.

### `cutctx install stop`

```bash
cutctx install stop
```

Stops the managed runtime for an installed deployment profile.

### `cutctx install restart`

```bash
cutctx install restart
```

Stops and starts the selected deployment profile.

### `cutctx install remove`

```bash
cutctx install remove
```

Stops the runtime, removes installed supervisor artifacts, reverts managed configuration changes, and deletes the stored manifest.

See also: [Persistent Installs](persistent-installs.md)

## `cutctx wrap`

Wrap external coding tools so their traffic flows through Cutctx.

### Shared semantics

- `--port`, when available, defaults to `8787`
- `--no-proxy` skips proxy startup and assumes an existing proxy
- `--learn` enables live traffic learning
- `-v`, `--verbose` means **verbose output**
- Hidden `--prepare-only` exists for internal Docker-native bridge flows and is intentionally omitted from normal usage

### `cutctx wrap claude`

```bash
cutctx wrap claude
cutctx wrap claude --resume <session-id>
cutctx wrap claude --port 9999
```

| Option / arg | Default | Meaning |
|---|---|---|
| `--port`, `-p` | `8787` | Proxy port |
| `--no-context-tool`, `--no-rtk` | off | Skip CLI context-tool setup |
| `--no-mcp` | off | Skip Cutctx MCP server registration |
| `--no-serena` | off | Skip Serena MCP server registration |
| `--code-graph` | off | Enable code graph indexing |
| `--memory` | off | Enable persistent cross-session memory |
| `--no-proxy` | off | Reuse an existing proxy |
| `--learn` | off | Enable live traffic learning |
| `--tool-search` | `true` | Keep Claude Code's on-demand tool loading active through the proxy |
| `--verbose`, `-v` | off | Verbose output |
| `claude_args...` | passthrough | Additional Claude Code arguments |

Requires the `claude` binary on the host.

### `cutctx wrap codex`

```bash
cutctx wrap codex
cutctx wrap codex -- "fix the bug"
cutctx wrap codex --backend anyllm --anyllm-provider groq
```

| Option / arg | Default | Meaning |
|---|---|---|
| `--port`, `-p` | `8787` | Proxy port |
| `--no-context-tool`, `--no-rtk` | off | Skip CLI context-tool setup |
| `--no-mcp` | off | Skip Cutctx MCP server registration |
| `--no-serena` | off | Skip Serena MCP server registration |
| `--code-graph` | off | Enable code graph indexing |
| `--no-proxy` | off | Reuse an existing proxy |
| `--learn` | off | Enable live traffic learning |
| `--backend` | unset | Proxy backend override |
| `--anyllm-provider` | unset | `anyllm` provider override |
| `--region` | unset | Cloud region override |
| `--verbose`, `-v` | off | Verbose output |
| `codex_args...` | passthrough | Additional Codex CLI arguments |

Requires the `codex` binary on the host.

### `cutctx wrap copilot`

```bash
cutctx wrap copilot -- --model claude-sonnet-4-20250514
cutctx wrap copilot --backend anyllm --anyllm-provider groq -- --model gpt-4o
```

| Option / arg | Default | Meaning |
|---|---|---|
| `--port`, `-p` | `8787` | Proxy port |
| `--no-context-tool`, `--no-rtk` | off | Skip CLI context-tool setup |
| `--no-proxy` | off | Reuse an existing proxy |
| `--backend` | unset | Proxy backend override |
| `--anyllm-provider` | unset | `anyllm` provider override |
| `--region` | unset | Cloud region override |
| `--provider-type` | `auto` | Force Copilot BYOK provider type (`anthropic` or `openai`) |
| `--wire-api` | unset | OpenAI wire API override for OpenAI-style backends |
| `--subscription` | off | Route GitHub-authenticated traffic without requiring a provider API key |
| `--memory` | off | Enable persistent cross-session memory |
| `--verbose`, `-v` | off | Verbose output |
| `copilot_args...` | passthrough | Additional Copilot CLI arguments |

Requires the `copilot` binary on the host. When a matching persistent deployment exists on the requested port, `wrap copilot` reuses or recovers it before falling back to an ephemeral proxy.

### `cutctx wrap aider`

```bash
cutctx wrap aider
cutctx wrap aider -- --model gpt-4o
cutctx wrap aider --backend litellm-vertex --region us-central1
```

| Option / arg | Default | Meaning |
|---|---|---|
| `--port`, `-p` | `8787` | Proxy port |
| `--no-context-tool`, `--no-rtk` | off | Skip CLI context-tool setup |
| `--code-graph` | off | Enable code graph indexing |
| `--no-proxy` | off | Reuse an existing proxy |
| `--learn` | off | Enable live traffic learning |
| `--memory` | off | Enable persistent cross-session memory |
| `--backend` | unset | Proxy backend override |
| `--anyllm-provider` | unset | `anyllm` provider override |
| `--region` | unset | Cloud region override |
| `--verbose`, `-v` | off | Verbose output |
| `aider_args...` | passthrough | Additional Aider arguments |

Requires the `aider` binary on the host.

### `cutctx wrap cursor`

```bash
cutctx wrap cursor
cutctx wrap cursor --port 9999
cutctx wrap cursor --no-rtk
```

| Option | Default | Meaning |
|---|---|---|
| `--port`, `-p` | `8787` | Proxy port |
| `--no-context-tool`, `--no-rtk` | off | Skip CLI context-tool setup |
| `--no-proxy` | off | Reuse an existing proxy |
| `--learn` | off | Enable live traffic learning |
| `--memory` | off | Enable persistent cross-session memory |
| `--verbose`, `-v` | off | Verbose output |

This command prints Cursor configuration instructions and waits while the proxy stays up. It does **not** launch Cursor directly.

### `cutctx wrap openclaw`

```bash
cutctx wrap openclaw
cutctx wrap openclaw --plugin-path ./plugins/openclaw
```

| Option | Default | Meaning |
|---|---|---|
| `--plugin-path` | unset | Local plugin source directory |
| `--plugin-spec` | `cutctx-ai/openclaw` | NPM plugin spec |
| `--skip-build` | off | Skip local `npm install` / build steps |
| `--copy` | off | Copy plugin instead of linked install |
| `--proxy-port` | `8787` | Cutctx proxy port |
| `--startup-timeout-ms` | `20000` | Proxy startup timeout |
| `--gateway-provider-id` | repeatable | OpenClaw provider IDs routed through Cutctx |
| `--python-path` | unset | Python launcher override |
| `--no-auto-start` | off | Disable plugin auto-start behavior |
| `--no-restart` | off | Do not restart the OpenClaw gateway |
| `--verbose`, `-v` | off | Verbose output |

Requires the `openclaw` binary on the host, and local-source mode may also require `npm`. In Docker-native mode, the installed host wrapper drives the host `openclaw` CLI while the plugin auto-starts the host `cutctx` wrapper from `PATH`.

## `cutctx unwrap`

Undo durable wrapping for supported tools.

### `cutctx unwrap openclaw`

```bash
cutctx unwrap openclaw
cutctx unwrap openclaw --no-restart
```

| Option | Default | Meaning |
|---|---|---|
| `--no-restart` | off | Do not restart the OpenClaw gateway |
| `--verbose`, `-v` | off | Verbose output |

This disables the Cutctx OpenClaw plugin and restores the legacy context engine slot.

## Docker-native parity matrix

This matrix compares the **Python CLI contract** to the Docker-native host wrapper added in this branch.

Legend:

- **native in container** — the command runs entirely inside the Cutctx container
- **host-bridged** — Cutctx runs in Docker, but the wrapped external tool still runs on the host

| Command path | Python CLI | Docker-native wrapper | Parity |
|---|---|---|---|
| `cutctx proxy` | native | native in container | full |
| `cutctx learn` | native | native in container | full |
| `cutctx perf` | native | native in container | full |
| `cutctx evals memory` | native | native in container | full |
| `cutctx evals memory-v2` | native | native in container | full |
| `cutctx memory ...` | native (when memory deps are available) | native in container | full |
| `cutctx mcp install` | native | native in container | full |
| `cutctx mcp uninstall` | native | native in container | full |
| `cutctx mcp status` | native | native in container | full |
| `cutctx mcp serve` | native | native in container | full |
| `cutctx install apply|status|start|stop|restart|remove` | native | Docker-native wrapper for `persistent-docker`; compose remains an alternative | partial |
| `cutctx wrap claude` | native | host-bridged | partial |
| `cutctx wrap cline` | native | host-bridged | partial |
| `cutctx wrap codex` | native | host-bridged | partial |
| `cutctx wrap continue` | native | host-bridged | partial |
| `cutctx wrap copilot` | native | not implemented in Docker-native wrapper | none |
| `cutctx wrap cursor` | native | host-bridged | partial |
| `cutctx wrap aider` | native | host-bridged | partial |
| `cutctx wrap gemini` | native | host-bridged | partial |
| `cutctx wrap goose` | native | host-bridged | partial |
| `cutctx wrap openclaw` | native | host-bridged | partial |
| `cutctx wrap openhands` | native | host-bridged | partial |
| `cutctx wrap opencode` | native | host-bridged | partial |
| `cutctx wrap windsurf` | native | host-bridged | partial |
| `cutctx wrap zed` | native | host-bridged | partial |
| `cutctx unwrap openclaw` | native | host-bridged | partial |

For the Docker-native execution model itself, see [Docker-Native Install](docker-install.md). For persistent service/task/docker lifecycle management, see [Persistent Installs](persistent-installs.md).

## Hidden and compatibility-only command paths

These exist in code but are intentionally excluded from normal user docs:

- `cutctx memory-eval`
- `cutctx memory-eval-v2`
- hidden internal `--prepare-only` flags on `wrap` subcommands

If you are documenting operational behavior or debugging internal wrapper flows, refer to the implementation in `cutctx/cli/wrap.py`.
