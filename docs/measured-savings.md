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
| Compression — HTML | **40.8%** | |
| Tool-schema compaction | **36.9%** | 40-tool surface. |
| Semantic cache | **83%** | Second identical request never leaves the proxy. |
| Compression — JSON / prose / tables / code | **0%** | See "Honest limits". |

## What is opt-in

| Engine | Flag | Measured |
| --- | --- | --- |
| Memoization | `--memoize` | **50%** (repeat tool results) |
| Model routing | `--model-routing-preset codex-gpt54mini-high` | routes `sonnet → haiku` |
| Semantic dedup | `--enable-semantic-dedup` | 0% on the corpus tested |
| Context budget | `--enable-context-budget` | 0% on the corpus tested |
| Drain3 | `--drain3` | 0% on the corpus tested |
| Knowledge graph (Graphify) | `--knowledge-graph` | 0% on the corpus tested |
| Difftastic | `--difftastic` | 0% on the corpus tested |

"0% on the corpus tested" means the engine did not fire on the payloads in the
harness. It is a gap in evidence as much as a statement about the engine — if
you have a workload one of these should help with, add a scenario rather than
assuming.

## Honest limits

**Savings are content-shaped.** The headline figure depends heavily on what
your agents actually send. Log-heavy tool output compresses ~66%; prose,
markdown tables and JSON currently do not compress at all. An agent that
mostly reads source files and prose will see far less than one that reads
build logs.

**Why the zeros:**

- **Code** — `code_aware_enabled` is off by default, a deliberate product
  choice ("use code graph tools instead"). The CODE_AWARE strategy is still
  selected and then no-ops, so it reports 0% rather than routing elsewhere.
- **JSON** — SmartCrusher rewrites it to CSV, which is smaller as a string but
  larger once re-escaped into the JSON request body. The router now detects
  that and declines the swap, so JSON is a truthful 0% instead of a
  slightly-negative "saving". See `discarded:inflates_wire` in
  `strategy_chain`.
- **Markdown tables** — `CompactTableCompressor` declines this shape; it
  targets structured arrays, not pipe tables.
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
