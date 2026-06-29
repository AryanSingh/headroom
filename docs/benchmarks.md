# Cutctx Benchmarks

> **Methodology note:** Compression ratio is `1 - (output_tokens / input_tokens)`. The most trustworthy numbers are the ones reproduced from the current repo state with the scripts in [`benchmarks/`](../benchmarks/).

## Fresh Local Verification

Re-run on **2026-06-29** in the current worktree:

```bash
./.venv/bin/python benchmarks/run_all.py --dry-run --output /tmp/cutctx_bench_results.json
./.venv/bin/python benchmarks/compare.py --tool cutctx --tool llmlingua2 --corpus synthetic --corpus mixed --dry-run --output /tmp/cutctx_compare_results.json
```

### Cutctx dry-run results

| Corpus | Input tokens | Output tokens | Reduction | Latency |
|---|---:|---:|---:|---:|
| JSON | 8112 | 3326 | 59.0% | 743.6 ms |
| Code | 921 | 921 | 0.0% | 3565.3 ms |
| Prose | 607 | 607 | 0.0% | 29.5 ms |
| Mixed | 1108 | 760 | 31.4% | 655.8 ms |

What this says:
- Cutctx is strongest on structured JSON-like content in this local run.
- The current dry-run corpora did not show wins on the small code and prose fixtures because the router correctly chose not to force low-confidence compression.

### Explicit compaction endpoint behavior

The direct `/v1/compress` endpoint now exposes two distinct operating modes:
- `balanced`: proxy-style conservative acceptance
- `max_savings`: explicit compaction mode that accepts smaller wins and returns diagnostics

Fresh local check on 2026-06-29 for a repetitive assistant payload:

| Profile | Input tokens | Output tokens | Tokens saved | Outcome |
|---|---:|---:|---:|---|
| `balanced` | 849 | 849 | 0 | Rejected as `unchanged (ratio>=0.83)` |
| `max_savings` | 849 | 823 | 26 | Accepted and reported as compressed |

This is important because it shows the product can now explain why savings were low and can intentionally trade strict acceptance for higher savings on explicit compaction requests.

### LLMLingua2 comparison on current dry-run corpora

| Corpus | Tool | Input tokens | Output tokens | Reduction | Latency | Model size |
|---|---|---:|---:|---:|---:|---:|
| Synthetic | Cutctx | 6001 | 2444 | 59.3% | 10304.1 ms | 280 MB |
| Synthetic | LLMLingua2 | 6001 | 2444 | 59.3% | 5232.9 ms | 4200 MB |
| Mixed | Cutctx | 2839 | 1010 | 64.4% | 6545.8 ms | 280 MB |
| Mixed | LLMLingua2 | 2839 | 1010 | 64.4% | 1795.4 ms | 4200 MB |

Interpretation:
- On the current synthetic and mixed dry-run inputs, both tools landed the same output-token counts.
- The strongest currently verified advantage is not universal ratio dominance; it is product fit, structured-data behavior, reversibility, and a much smaller reported model footprint in this harness.

## Practical Positioning

What we can support from current evidence:
- Cutctx delivers meaningful token reduction on structured agent context.
- Cutctx has first-class proxy, wrap, CCR retrieval, observability, and dashboard integration.
- Cutctx can compete on compression while using a much smaller reported model artifact than LLMLingua2 in the local comparison harness.

What we should avoid claiming without broader runs:
- "Best in market" across every workload
- blanket superiority over every competitor on raw compression ratio

## Why Some Corpora Show Zero Reduction

Zero reduction in the local `code` and `prose` dry-run fixtures is not automatically a bug.

Common reasons:
- the sample is too small to justify compression overhead
- the router judged the transform as low-confidence and skipped it
- the benchmark fixture is intentionally safety-biased rather than tuned for maximal shrinking

That is generally preferable to forcing lossy compression on weak candidates.

## Reproducing These Results

```bash
# Fresh Cutctx-only dry-run
./.venv/bin/python benchmarks/run_all.py --dry-run --output /tmp/cutctx_bench_results.json

# Head-to-head dry-run with LLMLingua2
./.venv/bin/python benchmarks/compare.py \
  --tool cutctx \
  --tool llmlingua2 \
  --corpus synthetic \
  --corpus mixed \
  --dry-run \
  --output /tmp/cutctx_compare_results.json
```

For larger or real corpora, see [`benchmarks/README.md`](../benchmarks/README.md).
