# Why isn't my output compressing?

If a payload you expected to shrink came back unchanged, or `cutctx perf`
reports far lower savings than the per-workload figures in the README, one of
the causes below almost always explains it. They are ordered by how often they
turn out to be the answer.

## 1. The tool is on the protected denylist

**This is the most common cause.** Cutctx refuses to compress output from
tools whose results an agent is most sensitive to. If the compressed result
carries the transform tag `router:excluded:tool`, this is what happened.

The default denylist is defined in [`cutctx/config.py`](../cutctx/config.py)
as `DEFAULT_EXCLUDE_TOOLS`:

```
Read  Grep  Glob  Write  Edit  Bash
read  grep  glob  write  edit  bash
```

Matching is on the **tool name** and is **case-sensitive** for names outside
that list. Any tool call whose name is in the set passes through with **0%
reduction, by design** — Cutctx would rather forward a large payload than risk
altering the file contents or command output an agent is reasoning over.

This has a direct consequence for benchmarking. The README's "Code search
(100 results) → 92%" row was measured with a tool name that is *not* on the
denylist. The identical payload delivered as a `Grep` result compresses by 0%.
A measured comparison on one ~44 kB, 100-object code-search payload:

| Tool name           | Exclude list | Transform tag          | Reduction |
|---------------------|--------------|------------------------|----------:|
| `Grep`              | default      | `router:excluded:tool` |    **0%** |
| `Read`              | default      | `router:excluded:tool` |    **0%** |
| `Bash` (any output) | default      | `router:excluded:tool` |    **0%** |
| `Bash` (logs)       | + `CUTCTX_BASH_CONTENT_ROUTING=1` | `router:log:…` | **~95%** |
| `Bash` (tree/ls)    | + `CUTCTX_BASH_CONTENT_ROUTING=1` | `router:excluded:tool` | **0%** |
| `CodeSearch`         | default      | `router:mixed:0.08`    |   **42%** |
| `search`            | default      | `router:mixed:0.08`    |   **42%** |
| `Grep`              | *empty set, library API* | `router:mixed:0.08` | **42%** |

Each entry is there for a reason. `Read`/`Glob`/`Grep` carry exact file
contents and search results the agent needs in order to edit correctly;
`Write`/`Edit` record what changes were made, and compressing them causes
duplicate or conflicting edits. `Bash` receives special content-shape routing
(see "Note on Bash" below).

**What you can and cannot change.** Both `--exclude-tools` and
`CUTCTX_EXCLUDE_TOOLS` are **additive** — they add names to the built-in set
and cannot remove them (see `_parse_exclude_tools` in
[`cutctx/proxy/server.py`](../cutctx/proxy/server.py)). So:

```bash
# Adds two more protected tools. Does NOT un-protect anything.
cutctx proxy --exclude-tools="MyCustomTool,AnotherTool"
export CUTCTX_EXCLUDE_TOOLS="MyCustomTool,AnotherTool"
```

Setting `CUTCTX_EXCLUDE_TOOLS=""` does **not** unlock the built-in six — an
empty value yields an empty *additional* set and leaves the defaults in place.
There is currently **no proxy-level way to un-protect a default tool.** If you
need that, call the library directly and pass your own `exclude_tools` set to
`ContentRouter`, having satisfied yourself that compressing that tool's output
is safe for your agent.

**Note on `Bash` — content-shape routing (opt-in, off by default):**

By default `Bash` is excluded like the rest of the denylist, so build logs and
test output are **not** compressed. That is the main reason an SRE-style log
workload measures far below the per-workload figures in the README.

There is an opt-in mode that routes Bash output by content shape instead:

```bash
export CUTCTX_BASH_CONTENT_ROUTING=1
```

With it enabled, `_is_directory_listing_output()` classifies each Bash result:

- **Directory listings** (`tree`, `ls`, `find`) stay excluded and pass through
  byte-identical. Commit `4605fc197` added `Bash` to the denylist precisely
  because the text compressor was mangling `tree`/`ls` output.
- **Build and test logs** (`pytest`, `cargo`, `npm`, `make`, timestamped app
  logs, tracebacks) route to the LogCompressor, which reaches 95%+ on these and
  provably retains FATAL/CRITICAL lines.

Classification precedence is deliberately conservative:

1. An unambiguous structural log marker (ISO timestamp, pytest banner, cargo
   `Compiling`/`error[E…]`, Python traceback) means "log".
2. Otherwise real `tree`/`ls` syntax — box-drawing characters, permission
   strings, a `total N` header — means "listing". This matters because the
   severity keywords are matched case-insensitively anywhere in the line, so an
   `ls` of a log directory full of `error.log` and `WARNING.md` must not be
   mistaken for a log.
3. Only with no listing syntax at all do bare severity keywords decide, and
   several are required.

**Why opt-in:** misclassifying a listing reintroduces the original mangling bug
on the request path. Enable it once you have confirmed the classification
behaves on your own traffic. If a payload routes the wrong way, check
`transforms_applied`: `router:excluded:tool` means it was treated as a listing.

## 2. The payload was a user message, not a tool result

Text the user authored is never compressed. If you see
`router:protected:user_message`, the payload was placed in a user message.
Move it into a `tool_result` / `tool_call` block to make it eligible.

## 3. The payload is too short to be worth compressing

Short turns are bypassed. This is the single largest reason fleet-wide savings
look small next to per-workload figures: on our own production traffic, most
requests are short and pass straight through, which is why the fleet-wide
number is **0.7%** while eligible long-context payloads reach 47–92%.

## 4. Most of your token volume is provider cache reads

Cache reads are already billed at a discount and are not a compression
target. On our traffic 870M of 927M tokens were cache reads. Check the "Cache
Performance" section of `cutctx perf` before concluding compression is
underperforming.

## 5. The recent-message protection window is holding it back

Output from an excluded tool is protected while it is still "recent". The
default `protect_recent_reads_fraction` is `0.0`, which protects **all**
messages from excluded tools. Raising it lets older excluded-tool output
become compressible while still protecting the newest turns. This only affects
history — it will never make a fresh `Grep` result compress.

## How to diagnose a specific payload

Inspect `transforms_applied` on the result. The tag tells you which rule fired:

| Tag                            | Meaning                                        |
|--------------------------------|------------------------------------------------|
| `router:excluded:tool`         | Tool is on the denylist — cause 1              |
| `router:protected:user_message`| User-authored text — cause 2                   |
| `router:mixed:<ratio>`         | Compression ran; the number is the achieved ratio |

## Related

- [Configuration reference](configuration-reference.md) — `CUTCTX_EXCLUDE_TOOLS`
  and every other setting
- `cutctx perf` — realised savings on your own telemetry, which is what you
  should model cost against
