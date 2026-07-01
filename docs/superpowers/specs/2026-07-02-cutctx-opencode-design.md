# CutCtx opencode integration — design

**Date:** 2026-07-02
**Status:** Approved (pending user review)
**Scope:** New files only. No edits to existing `cutctx/`, `crates/`, `dashboard/`, `plugins/cutctx-plugin/`, or any other project source.

## 1. Goals & non-goals

### Goal

Make CutCtx the always-on context-compression layer for the user's opencode
install. Every opencode session — in this repo and any other — auto-compresses
tool outputs, log streams, and conversation history before they hit the LLM,
and exposes `cutctx_compress` / `cutctx_retrieve` / `cutctx_stats` MCP tools
so the model can ask for originals back (CCR — Compress-Cache-Retrieve).

### Non-goals

- Not building a public npm package (`@cutctx/opencode`). Local install only.
- Not rewriting the proxy. We either call `compress()` in-process or
  lazy-spawn the existing `cutctx proxy` for streaming. Both reuse existing
  code.
- Not adding new compression algorithms. Uses `cutctx-ai`'s existing
  `compress()` / `retrieve()` / `stats()`.
- Not changing the dashboard, enterprise control plane, or any existing
  project source.
- Not editing `opencode.json` inside the project repo. The user's
  `~/.config/opencode/opencode.json` is the only config touched.

## 2. Architecture & component layout

```
+--------------------------------------------------------------+
|                  opencode session (TUI)                      |
|                                                              |
|  user  -->  LLM  <-->  tool calls  <-->  bash / read / write |
|                   ^                                         |
|                   |   chat.messages / chat.params            |
|                   v                                         |
|        +--------------------------------------+             |
|        |   cutctx.ts (opencode plugin)        |             |
|        |                                      |             |
|        |   tool.execute.after   -> compress    |             |
|        |   chat.messages.transform -> rollup   |             |
|        |   session.compacting  -> compress     |             |
|        +-------------+------------------+-----+             |
|                      |                  |                   |
|                      v                  v                   |
|             +----------------+   +-----------------+         |
|             | cutctx-ai (TS) |   | cutctx proxy    |         |
|             | compress()     |   | (lazy spawn)    |         |
|             | (in-process)   |   | for SSE streams |         |
|             +-------+--------+   +--------+--------+         |
|                     |                     |                  |
|                     v                     v                  |
|             +----------------+   +-----------------+         |
|             | CCR cache      |   | provider HTTP   |         |
|             | (~/.cutctx/)   |   | (Anthropic/etc) |         |
|             +----------------+   +-----------------+         |
|                                                              |
|        +--------------------------------------+             |
|        |   MCP server (cutctx mcp serve)       |             |
|        |   cutctx_compress / _retrieve / _stats| <-- LLM     |
|        +--------------------------------------+             |
+--------------------------------------------------------------+
```

### Component responsibilities

1. **`cutctx.ts` — the opencode plugin** (single file, ~250 LOC).
   - Implements opencode's `Plugin` interface from `@opencode-ai/plugin`.
   - Imports `compress`, `retrieve`, `stats` from `cutctx-ai` (the official
     TypeScript SDK; same `compress()` API as the Python package).
   - Owns three handlers:
     - **`tool.execute.after`** — receives the tool's output text, runs
       `compress()` if the output exceeds a threshold (default 4 KB /
       ~1k tokens), replaces the output with the compressed version,
       records a CCR handle in the local cache.
     - **`experimental.chat.messages.transform`** — on every LLM-bound
       message list, runs `compress(messages, model)` if the conversation
       is over the model's context window minus a reserve, so opencode's
       own compaction never has to fire.
     - **`experimental.session.compacting`** — when opencode's own
       compactor runs, hand the messages to `compress()` and return the
       result so the session compactor benefits from cutctx's pipeline.
   - **Lazy proxy spawn**: if a streaming response is detected, the
     plugin spawns `cutctx proxy --port 8787` once and caches the port.
     Subsequent streaming calls reuse it. If the proxy crashes, the plugin
     catches the error, logs a single warning, and continues without
     proxy-based compression for that session.

2. **`cutctx` MCP server** (separate process, registered in `opencode.json`).
   - Spawned by opencode at session start (not by the plugin) via the
     standard `mcp` block: `{"type":"local","command":["cutctx","mcp","serve"]}`.
   - Exposes `cutctx_compress(text)`, `cutctx_retrieve(handle)`,
     `cutctx_stats()`.
   - Why a separate process: opencode's MCP loader has its own lifecycle.
     Co-locating this in the plugin would require reinventing MCP transport.
     The `cutctx mcp serve` binary already exists.

3. **`~/.config/opencode/opencode.json` edits** (global config only).
   - Add `~/.config/opencode/.opencode/plugin/cutctx.ts` to the `plugin`
     array.
   - Add `cutctx` to the `mcp` block.
   - Add a `cutctx-stats` command under `command` for a slash command.
   - Optional `permission` rules to allow the plugin to invoke `cutctx` and
     `cutctx proxy` via bash.

4. **Local symlink** for edit-in-repo visibility.
   - The plugin lives at `plugins/cutctx-opencode/cutctx.ts` in this repo.
     After `npm install` in that directory (it has a `package.json`
     declaring `@opencode-ai/plugin` and `cutctx-ai`), `node_modules` is
     built. A symlink
     `~/.config/opencode/.opencode/plugin/cutctx.ts ->
     /Users/aryansingh/Documents/Claude/Projects/headroom/plugins/cutctx-opencode/cutctx.ts`
     lets the user edit in-repo and have opencode see the change after
     restart.

### Boundaries

- The plugin owns *transformation* (what reaches the LLM). The MCP server
  owns *retrieval* (what the LLM asks for back). They share the same CCR
  cache via the `cutctx-ai` SDK, so a `cutctx_compress()` MCP call writes
  the same cache entry the plugin's `tool.execute.after` hook would.
- The proxy is *only* for SSE streaming (which can't be done in a hook
  callback mid-stream). For batch, the plugin uses the in-process SDK.

## 3. Data flow

### A. Tool-output compression (the most common case)

1. opencode runs a tool (e.g. `bash`, `read`, `grep`).
2. `tool.execute.after` fires in `cutctx.ts` with `{ tool, output }`.
3. Plugin checks: `output.length > COMPRESS_THRESHOLD_BYTES` (default
   4096). If not, return unchanged.
4. Plugin calls `compress({ role: "user", content: output }, { model:
   currentModel, targetRatio: 0.3 })` from `cutctx-ai`.
5. `compress()` returns `{ content, originalHandle, savings: {
   tokensBefore, tokensAfter, ratio } }`.
6. Plugin **rewrites the tool's output** in opencode's `output` object to
   the compressed `content`, prefixed with a single header line:

   ```
   [cutctx: compressed 12,400 → 3,720 tokens (handle: ccr_8f2c1a)]
   …compressed text…
   ```

   The handle is what the LLM uses with `cutctx_retrieve` to ask for the
   original.
7. Plugin calls `cutctxStats().recordCompression({ tool, ratio, latencyMs
   })` so the user can run `/cutctx-stats` and see total savings.
8. opencode sends the message to the LLM with the compressed output. Net
   effect: 60-90% fewer tokens for that tool result hit the model.

### B. Conversation-history compression (long sessions)

1. opencode is about to send `messages[]` to the LLM.
2. `experimental.chat.messages.transform` fires with `{ messages }`.
3. Plugin calls `countTokens(messages, model)`. If `tokens < modelLimit *
   0.85`, return unchanged.
4. Otherwise call `compress(messages, { model, protectRecent: 4,
   targetRatio: 0.5 })`. The `protectRecent: 4` keeps the last 4 turns
   verbatim so the agent's current reasoning is never compressed.
5. Return the compressed `messages[]` to opencode. CCR handles for the
   dropped pieces are in the cache; the LLM can ask for any of them via
   `cutctx_retrieve`.

### C. Session-compaction (opencode's own compactor)

1. opencode decides to compact the session (its own heuristic).
2. `experimental.session.compacting` fires.
3. Plugin hands `messages` to `compress()` with `targetRatio: 0.4` and
   returns the result. opencode persists the compacted session. Net
   effect: cutctx is the compactor.

### D. Streaming / SSE (lazy proxy)

1. opencode begins a streaming response (the `chat.headers` carry a
   streaming flag or the response is a `text/event-stream`).
2. Plugin checks `proxyState.port` — if unset, spawns `cutctx proxy
   --port 8787` once, waits for `127.0.0.1:8787/health` to return 200,
   caches the port. 3-second timeout; on failure, fall back to no
   streaming compression for the session.
3. Plugin rewrites the `baseURL` for this one request to
   `http://127.0.0.1:8787` so the proxy intercepts the SSE stream and
   applies incremental compression between chunks.
4. On session end, plugin sends SIGTERM to the proxy child.

### E. CCR retrieve (MCP tool path)

1. LLM decides the original tool output matters and calls
   `cutctx_retrieve("ccr_8f2c1a")` via the MCP server.
2. `cutctx mcp serve` reads from `~/.cutctx/ccr/<handle>.json` (the
   on-disk cache the in-process `compress()` wrote) and returns the
   original text.
3. The MCP server and the plugin share the same `~/.cutctx/` directory —
   no shared in-process state, just a filesystem cache. This means the
   plugin can crash and the MCP server still retrieves; the MCP server
   can crash and the plugin still compresses.

## 4. Error handling & safety

| Failure | Behavior | Logged? |
| --- | --- | --- |
| `compress()` throws (e.g. malformed content) | Plugin catches, returns the **uncompressed** tool output. The session continues. | Yes — `logger.warn("cutctx: compress failed for tool=read, falling back to original", err)` |
| Proxy fails to spawn / unhealthy after 3s | Plugin logs once per session, sets `proxyState.disabled = true`. All subsequent streaming calls bypass the proxy. | Yes — single warning, no spam. |
| Proxy crashes mid-stream | Plugin catches the EPIPE on the response stream, closes the opencode stream, returns an error to the LLM (which will retry without compression). | Yes — `logger.error("cutctx proxy crashed mid-stream", err)`. |
| MCP server unreachable | opencode's MCP loader handles this; `cutctx_compress` tool will be missing from the model's tool list. The plugin still works for in-process compression. | Yes — opencode logs it. |
| CCR handle miss on retrieve | `cutctx_retrieve` returns `{ error: "handle not found" }` to the LLM, which the model handles gracefully. | No. |
| Cache directory not writable | Plugin calls `compress()` with `cache: false` for that call. | Yes — one warning per session. |
| User runs `/cutctx-stats` mid-compression | Stats are read from `~/.cutctx/stats.json` (atomic append), so concurrent reads are safe. | n/a |
| Plugin load itself fails (e.g. `cutctx-ai` not installed) | opencode shows the plugin load error in the TUI. Session still works without compression. | Yes — opencode logs it. |

### Safety invariants

- Compression is **never lossy from the LLM's perspective** without a way
  back: every compressed output is paired with a CCR handle in the
  response, and the `cutctx_retrieve` tool is always available.
- `protectRecent: 4` keeps the last 4 conversation turns verbatim. The
  agent's current task description and recent tool calls are never
  touched.
- Originals are kept on disk (not in-memory) so a plugin restart doesn't
  lose retrievable content.

## 5. Testing strategy

### Unit tests (Vitest, in `plugins/cutctx-opencode/test/`)

- `compress.test.ts` — mocked `cutctx-ai`, asserts that `tool.execute.after`
  rewrites output only when above threshold, prepends the
  `[cutctx: compressed …]` header, and passes the CCR handle through.
- `messages-transform.test.ts` — asserts
  `experimental.chat.messages.transform` returns unchanged when under
  threshold, compresses with `protectRecent: 4` when over.
- `proxy-lifecycle.test.ts` — spawns a fake `cutctx` binary (a shell
  script that prints a port and stays alive), asserts plugin caches the
  port and falls back on 3s timeout.
- `stats.test.ts` — asserts the `cutctx-stats` command reads from
  `~/.cutctx/stats.json` correctly.

### Integration tests (real cutctx-ai, real opencode)

- `e2e/install.test.ts` — uses opencode's headless TUI driver to launch a
  session in this repo, runs `cat .tmp-stats.json | wc -c` via the bash
  tool, asserts the output in the next LLM call is the
  `[cutctx: compressed …]` form.
- `e2e/mcp.test.ts` — drives the session to call `cutctx_compress` and
  `cutctx_retrieve`, asserts the handle round-trips.
- `e2e/streaming.test.ts` — uses a model that returns SSE, asserts the
  proxy is spawned and the compressed stream is delivered.

### Manual smoke (post-install)

1. `cd plugins/cutctx-opencode && npm install`
2. Symlink the plugin into `~/.config/opencode/.opencode/plugin/`
3. Add the `plugin`, `mcp`, and `command` entries to
   `~/.config/opencode/opencode.json`
4. Restart opencode
5. In a new session, run `cat /var/log/system.log | head -2000` (huge
   output)
6. Verify the next LLM call shows `[cutctx: compressed …]` in the tool
   result
7. Run `/cutctx-stats` and verify savings appear
8. Ask the model to retrieve the original via `cutctx_retrieve` and
   verify

## 6. Files to create (final list)

| Path | Purpose | Existing or new |
| --- | --- | --- |
| `plugins/cutctx-opencode/cutctx.ts` | The opencode plugin (TS, exports `Plugin`). | new |
| `plugins/cutctx-opencode/package.json` | Declares `@opencode-ai/plugin` and `cutctx-ai` deps. | new |
| `plugins/cutctx-opencode/tsconfig.json` | TS config for the plugin. | new |
| `plugins/cutctx-opencode/README.md` | Install/usage docs. | new |
| `plugins/cutctx-opencode/test/*.test.ts` | Vitest unit tests. | new |
| `plugins/cutctx-opencode/vitest.config.ts` | Vitest config. | new |
| `docs/superpowers/specs/2026-07-02-cutctx-opencode-design.md` | This file. | new |
| `~/.config/opencode/opencode.json` | Add plugin + mcp + command entries. | edit (global only, not in repo) |
| `~/.config/opencode/.opencode/plugin/cutctx.ts` | Symlink to repo file. | new (symlink) |

## 7. Configuration constants (defaults, all overridable via env)

| Env var | Default | Purpose |
| --- | --- | --- |
| `CUTCTX_COMPRESS_THRESHOLD_BYTES` | `4096` | Min tool output size to compress. |
| `CUTCTX_HISTORY_TARGET_RATIO` | `0.5` | Target ratio for `chat.messages.transform`. |
| `CUTCTX_PROTECT_RECENT_TURNS` | `4` | Last N turns kept verbatim. |
| `CUTCTX_PROXY_PORT` | `8787` | Lazy-spawned proxy port. |
| `CUTCTX_PROXY_SPAWN_TIMEOUT_MS` | `3000` | Health-check timeout for proxy. |
| `CUTCTX_DISABLED` | `0` | Set to `1` to disable the plugin entirely (escape hatch). |

## 8. Out of scope (deferred)

- Public npm package (`@cutctx/opencode`).
- A `cutctx wrap opencode` CLI subcommand (mirrors the existing
  `cutctx wrap claude`).
- Compression analytics in the cutctx dashboard (the plugin writes to
  `~/.cutctx/stats.json`, dashboard integration is a follow-up).
- Per-agent compression policies (different agents, different thresholds).
