# Measured savings, by engine

Every number here was produced by `scripts/savings_harness.py` against a real
proxy subprocess and a capture upstream, counting BPE tokens in and out.
Reproduce with:

```bash
python scripts/savings_harness.py --all --json artifacts/savings-harness.json
```

Nothing in this file is modelled, extrapolated, or taken from a unit test.
Where an engine saves nothing, it says so.

## What is on by default

Two numbers per content type, because they answer different questions.
**Compression alone** is what the compressors do to a single block. **Default
stack** adds semantic dedup and drain3, which are now on by default.

| Content type | Compression alone | Default stack |
| --- | --- | --- |
| Log-shaped output | 66.0% | **82.3%** |
| JSON tool output | 53.4% | **79.4%** |
| HTML | 40.8% | **75.9%** |
| Source code | 0% | **81.4%** |
| Prose | 0% | **80.6%** |
| Markdown tables | 0% | **81.6%** |

Plus, independent of content type:

| Engine | Measured |
| --- | --- |
| Semantic cache | **82.9%** (second identical request never leaves the proxy) |
| Tool-schema compaction | **55.4%** (40-tool surface) |

**The gap between those two columns is almost entirely semantic dedup, and you
should understand what it is before you quote it.** Dedup collapses content
repeated across turns into a retrieval pointer. The harness corpus is six
turns carrying the *identical* tool result, so it repeats perfectly and these
figures are an upper bound for repetition-heavy traffic. It is why code, prose
and tables move from 0% to ~81%: nothing is compressing that content, the
repeated copies are being collapsed. An agent that reads a different file
every turn will see far less. An agent that re-reads the same files while it
reasons — which is the common loop — will see something in this range.

## What is opt-in

## What changed to on by default, and why

Semantic dedup and drain3 now default on. Both were opt-in, both were inert
until the fixes below, and neither can lose:

- **Semantic dedup** — the largest single lever in the table above, and the
  only thing that helps code, prose or tables at all. It swaps repeated
  content for a `cutctx_retrieve` pointer, which the proxy resolves
  transparently using the tool it *already* injects for compression — so this
  reuses a default-on mechanism rather than adding a new way to lose context.
  Opt out with `--no-semantic-dedup`.
- **Drain3** — ships as the optional `[log-ml]` extra. Installing that extra
  is signal enough; previously you had to install it *and* pass a flag, and
  got silence otherwise. Absent the extra it is inert, and the router discards
  drain3 output that fails to shrink the payload, so it can never do worse
  than the standard log path. Opt out with `--no-drain3`.

## What is still opt-in, and why

| Engine | Flag | Measured | Why not default |
| --- | --- | --- | --- |
| Context budget | `--enable-context-budget` | 82.7% (+3.3pp over default stack) | Trims conversation once past 60% of the ceiling. Silent context loss the user cannot easily detect. |
| Difftastic | `--difftastic` | 51.7% on diffs | Spawns a `difft` subprocess per file with a 10s timeout, needs an external binary, and only fires on Bash git diffs. |
| Memoization | `--memoize` | 79.8% (**+0.4pp** over default stack) | Dedup already collapses the repeated tool results it targets, so it adds almost nothing now. |
| Model routing | `--model-routing-preset …` | routes `sonnet → haiku` | Changes which model answers — a cost/quality decision that belongs to the operator. |
| Knowledge graph | `--knowledge-graph` | unavailable | Dependency mismatch, see below. |

The memoization row is the interesting one: on its own corpus it looks like a
79.8% engine, but measured against the new default stack it contributes
**0.4 percentage points**, because dedup gets there first. Two engines, one
win.

## Why the engines read zero

Five opt-in engines reported 0%. That was read as "did not fire on this
corpus". It was wrong for four of them, and the fifth was worse.

- **drain3** — `miner.add_log_message()` returns a dict, but the code read
  `result.cluster_id`. Every line raised `AttributeError` into a per-line
  handler that assigned `hash(line)` as a fallback cluster, so 600
  identical-shaped lines produced 600 clusters. The router then assigned
  drain3's output unconditionally, making the standard log path unreachable:
  **enabling `--drain3` took log compression from 99.8% to 0%.** The flag was
  worse than useless.
- **difftastic** — invoked with difft's default side-by-side display, which is
  reliably ~2x *larger* than the unified diff it replaces, so the
  never-enlarge guard rejected 100% of results. Measured on a
  reformatting-heavy diff: unified 5836 chars, side-by-side 13264, inline
  1014. Also set `DFT_CONTEXT_LINES`, which is not a difft variable
  (`DFT_CONTEXT` is), so the context setting never applied.
- **dedup** — skipped any message whose `content` was not a `str`. Anthropic
  messages carry a *list of blocks*, and a repeated `tool_result` is always a
  block, so dedup never saw the content it exists to collapse. Separately, the
  pipeline built `SessionDeduplicator()` with no CCR store, so every pointer
  it emitted was unresolvable — that path was silently lossy, and is now
  wired and covered by a round-trip test.
- **memoization** — its allowlist was `{file_read, code_search}` and its
  write-list `{file_write, file_edit, file_delete}`: a vocabulary no client
  speaks. Claude Code sends `Read` and `Edit`, so nothing was memoized — and
  the write side was the dangerous half, because an unrecognised write name
  meant a file could be edited and the next read still answered from cache.
  Both lists now match on the shared cross-agent name map, and `Bash` counts
  as a write (it can `sed -i` or `git checkout`; the module's own rule is
  "when in doubt, flush the whole session").
- **context_budget** — counted only `block["text"]`, but a `tool_result`
  stores its payload under `content`. Tool output therefore counted as zero
  tokens: a 77k-token conversation measured as **12**, the controller never
  left the GREEN zone, and the ceiling was never enforced. The Click CLI also
  never passed `context_budget_max_tokens`, so the ceiling was fixed at
  100000 regardless of configuration; `--context-budget-max-tokens` and
  `--context-budget-policy` now exist.
- **graphify** — still unavailable, and the honest reason is a dependency
  mismatch. The indexer shells out to `python -m graphify.cli build
  --project-dir ... --output-dir ...`. The package currently installed under
  the name `graphify` has no `cli` submodule, no `build` subcommand and no
  `--output-dir`; it writes to `<project>/graphify-out` via `update <path>`.
  `graphify_available()` only checked that the *name* imported, so startup
  advertised the knowledge graph as active while every build died with "No
  module named graphify.cli" in a debug log. The check now verifies the CLI
  entry point, so this reports `unavailable` instead of pretending. Resolving
  which graphify package the product targets is a packaging decision, not a
  code fix, so it is left open rather than guessed at.

The general lesson: an engine that is enabled, throws nothing, and saves
nothing looks exactly like an engine that legitimately did not apply. Four of
five here were the former.

## Honest limits

**Savings are content-shaped.** The headline figure depends heavily on what
your agents actually send. Log-heavy tool output compresses ~66% and JSON
record arrays ~53%; prose, markdown tables and source code do not compress at
all. An agent that mostly reads source files and prose will see far less than
one that reads build logs and tool output.

**Why the zeros:**

- **Code** — `code_aware_enabled` is off by default. The CODE_AWARE strategy
  is still selected and then no-ops, so it reports 0% rather than routing
  elsewhere; `strategy_chain` says `code_aware_disabled`, so this reads as a
  switch rather than a limit.

  This default was inherited as "use code graph tools instead". Measured, it
  is the right call for a stronger reason. Turning it on and comparing ASTs
  before and after on `cutctx/utils.py`: every function, class and module
  constant survives, but **6 of 20 function bodies lose statements — 44 body
  statements become 34**. Signatures and names stay intact while roughly a
  quarter of the implementation is silently elided. That shape is precisely
  wrong for a coding agent: it reads a file in order to *edit* it, and would
  write changes against logic it cannot see, with nothing in the output
  marking what was dropped.

  It is also unreliable. On four real source files it produced **invalid
  Python on two of them** ("Code compression produced invalid syntax"), where
  the syntax guard correctly discarded the result and returned the original —
  another engine whose safety net converts a defect into a silent 0%. Where
  it does work it saves 15.7%–35.7%.

  So: off by default on evidence, not preference. Anyone wanting to revisit it
  should fix the invalid-syntax cases first, and treat body elision as a
  correctness question rather than a compression ratio.
- **Markdown tables** — `CompactTableCompressor` declines this shape; it
  targets JSON arrays of records, not text that is already a pipe table.
  Markdown routes to TEXT passthrough.
- **Prose** — routes to TEXT passthrough. Lossy prose compression is gated
  behind Kompress (`CUTCTX_ENABLE_KOMPRESS=1`), which is the only path that is
  not 100% on-machine.

## A note on how savings are counted

Until 2026-07-27 the router counted "tokens" as `len(text.split())` —
whitespace words. For whitespace-poor output that diverges wildly from what a
provider bills: a comma-separated CSV block scored **1** against an original
of 3600, reporting a 99.97% saving on a change that actually cost 17 more
tokens on the wire.

Counting is now BPE (`token_len`), and a swap is judged on the JSON-serialized
payload, because escaping is not ratio-neutral. Figures produced before that
change overstate savings on any content that compresses to something without
spaces. Treat older dashboard history accordingly.

## Why JSON went from 0% to 53.4%

Fixing the accounting above made JSON a truthful 0%: SmartCrusher's CSV
rewrite inflated the wire, and the router correctly began discarding it
(`discarded:inflates_wire`). That exposed the real problem — the compressor
built for this shape was never running.

`CompactTableCompressor` turns JSON arrays of records into pipe tables. It sat
behind this gate:

```python
if result.strategy in ("lossless", "passthrough"):
```

The Rust SmartCrusher decorates its label with detail, so the value is
`"lossless:table(400->len=13829)"` — never the bare `"lossless"`. The equality
test could only match `"passthrough"`, which is what SmartCrusher returns for
logs, prose and CSV: precisely the shapes CompactTable declines. The
compressor was unreachable for its entire life.

Behind it sat a second defect. The CCR marker path imported
`cutctx.proxy.compression_store`, a module that has never existed, and the
handler logged the `ImportError` at debug level — so even with the gate fixed,
CompactTable threw and was swallowed silently. It now logs at warning with a
traceback, because a decline is `None`; reaching that handler is a defect.

Both are fixed, and the retrieval round-trip is pinned by a test: the hash in
the emitted marker must resolve in the compression store and return the
original bytes, or compression would be silently lossy.
