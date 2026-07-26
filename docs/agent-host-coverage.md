# Agent host coverage

Which Cutctx features reach which AI coding host, and why the answer differs.

Cutctx has two delivery paths, and a host supports one, both, or neither:

- **Proxy path** — the host is pointed at the local proxy via a base URL, so
  every model request flows through Cutctx. This is the only path that
  delivers the **compressor, model routing, and orchestrator**.
- **MCP path** — Cutctx registers an MCP server the host loads. This delivers
  on-demand tools (`cutctx_compress`, `cutctx_retrieve`, `cutctx_scan`,
  `cutctx_stats`, `cutctx_audit`) and, via `cutctx mcp gateway`, automatic
  compression of *other* MCP servers' tool output before it reaches context.

A host qualifies for the proxy path only if it lets you repoint its model
endpoint at an OpenAI- or Anthropic-compatible URL. Several popular hosts do
not, and no amount of configuration changes that.

## Matrix

| Host | Proxy path (compressor / routing / orchestrator) | MCP path | Command |
| --- | --- | --- | --- |
| Claude Code CLI | ✅ full — `ANTHROPIC_BASE_URL` | ✅ | `cutctx wrap claude` / `cutctx init claude` |
| Codex CLI | ✅ full — `OPENAI_BASE_URL` | ✅ | `cutctx wrap codex` / `cutctx init codex` |
| Cursor app — BYOK models | ✅ full — OpenAI base-URL override | ✅ | `cutctx init cursor --byok` |
| Cursor app — subscription models (`auto`, `composer`, …) | ❌ not possible | ✅ | `cutctx init cursor` |
| Cursor CLI (`cursor-agent`) | ❌ not possible | ✅ | `cutctx wrap cursor-agent` |
| Claude Desktop | ❌ not possible | ✅ | `cutctx mcp install --agent claude-desktop --gateway` |

## Why the ❌ rows are hard limits

**Cursor CLI (`cursor-agent`).** It speaks Connect RPC with
`content-type: application/proto` — binary protobuf against an undocumented
`aiserver.v1.*` schema — to `https://api2.cursor.sh`. `CURSOR_API_ENDPOINT`
(and `--endpoint`) repoint the *host*, but the payload cannot be parsed
without Cursor's proto definitions, and inference runs on Cursor's servers
against your Cursor subscription. There is no model choice for Cutctx to
route and no JSON body for it to compress.

**Cursor subscription models in the app.** Same backend, same constraint. The
app's OpenAI base-URL override applies only to BYOK requests; hosted models
never consult it.

**Claude Desktop.** The app talks to a hosted endpoint that is not
repointable.

Do not paper over these with `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL`. Those
variables are simply ignored by these hosts, and setting them produces a
configuration that looks correct while routing nothing — the worst failure
mode, because savings stay at zero with no error to chase.

## What you still get on the MCP path

On a subscription plan the meaningful cost is quota and rate limits, not
per-token billing, so shrinking what enters context still pays:

1. **Gateway-compressed MCP output.** `cutctx mcp install --gateway` rewrites
   every other stdio MCP server in Claude Desktop and Cursor to launch through
   `cutctx mcp gateway`, which compresses `tools/call` results before the model
   sees them. Reversible; the original invocation is preserved verbatim after
   `--`.
2. **On-demand tools.** `cutctx_compress` / `cutctx_retrieve` let the agent
   shrink large content itself and fetch the original by hash when needed.
3. **Token-efficient command guidance** injected into `.cursorrules`.

## Cursor specifics

### `~/.cursor/mcp.json` is not enough for the CLI

Cursor keeps a separate approval list. A server written to `mcp.json` reports:

```
cursor-agent mcp list
cutctx: not loaded (needs approval)
```

and exposes no tools until `cursor-agent mcp enable cutctx` runs.
`CursorRegistrar` performs that step automatically; `cutctx mcp status`
reports the CLI's own state so a configured-but-inert server is visible.

The command is also resolved to an absolute path at registration time, because
Cursor.app launched from the Dock hands MCP servers a GUI `PATH` that excludes
Homebrew, pipx, pyenv, and venv bin dirs.

### Where the BYOK override actually lives

Not in `settings.json`. Cursor stores it inside a JSON blob in its Electron
state database:

```
~/Library/Application Support/Cursor/User/globalStorage/state.vscdb
  ItemTable["src.vs.platform.reactivestorage.browser
             .reactiveStorageServiceImpl.persistentStorage.applicationUser"]
    -> { "openAIBaseUrl": "...", "useOpenAIKey": true, "encryptedKey": "..." }
```

`settings.json` keys such as `cursor.openai.baseUrl`, `openai.baseUrl`, and
`cursor.general.openAIBaseUrl` are widely repeated as the way to do this and
are **silently ignored** — Cursor registers no such settings.
`cutctx init cursor --byok` removes them for exactly that reason.

`cutctx init cursor --byok` writes `openAIBaseUrl` and `useOpenAIKey`, saving
the previous values to `~/.cutctx/cursor-byok-backups/`. It **never** reads or
writes `encryptedKey` — the API key is yours to enter in Cursor's UI. Cursor
must be closed, since it rewrites the database wholesale on exit.

## Verifying

```bash
cutctx mcp status
```

reports, per host: whether the Cutctx server is configured, how many other
servers are gateway-wrapped, Cursor's own `cursor-agent` readiness, and an
explicit note for hosts whose model requests are not proxy-routable.
