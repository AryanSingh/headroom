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

| Engine | Measured | Notes |
| --- | --- | --- |
| Compression — log-shaped content | **66%** | The strongest single case. |
| Compression — JSON tool output | **53.4%** | Arrays of records — file listings, search results, DB rows. |
| Compression — HTML | **40.8%** | |
| Tool-schema compaction | **36.9%** | 40-tool surface. |
| Semantic cache | **83%** | Second identical request never leaves the proxy. |
| Compression — prose / tables / code | **0%** | See "Honest limits". |

## What is opt-in

| Engine | Flag | Measured |
| --- | --- | --- |
| Memoization | `--memoize` | **76.7%** (repeat tool results) |
| Model routing | `--model-routing-preset codex-gpt54mini-high` | routes `sonnet → haiku` |
| Semantic dedup | `--enable-semantic-dedup` | 0% incremental — see note |
| Context budget | `--enable-context-budget` | 0% on the corpus tested |
| Drain3 | `--drain3` | 0% on the corpus tested |
| Knowledge graph (Graphify) | `--knowledge-graph` | 0% on the corpus tested |
| Difftastic | `--difftastic` | 0% on the corpus tested |

**Read the dedup row carefully.** The `dedup` scenario reports 53.4%, but it
runs the same JSON corpus as `compression:json` and returns byte-identical
counts (77471 → 36095). That figure is the JSON compression baseline; semantic
dedup contributes **nothing measurable on top of it**. The same caveat partly
applies to memoization, whose 76.7% combines repeat-result serving with the
JSON compression underneath it.

"0% on the corpus tested" means the engine did not fire on the payloads in the
harness. It is a gap in evidence as much as a statement about the engine — if
you have a workload one of these should help with, add a scenario rather than
assuming.

## Honest limits

**Savings are content-shaped.** The headline figure depends heavily on what
your agents actually send. Log-heavy tool output compresses ~66% and JSON
record arrays ~53%; prose, markdown tables and source code do not compress at
all. An agent that mostly reads source files and prose will see far less than
one that reads build logs and tool output.

**Why the zeros:**

- **Code** — `code_aware_enabled` is off by default, a deliberate product
  choice ("use code graph tools instead"). The CODE_AWARE strategy is still
  selected and then no-ops, so it reports 0% rather than routing elsewhere.
  `strategy_chain` says `code_aware_disabled`, so this reads as a switch
  rather than a limit.
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
