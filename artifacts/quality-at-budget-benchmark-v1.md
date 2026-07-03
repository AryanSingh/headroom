# Quality-At-Budget Benchmark V1

Date: 2026-07-03
Status: Release-ready documentation scope

## Purpose

This benchmark is the public, reproducible proof surface for the claim:

> Cutctx reduces context cost while preserving useful answer quality on
> production-shaped agent context.

It is not a claim that Cutctx beats every provider-native optimization on every
workload. Provider prompt caching, provider-native compaction, and Cutctx solve
overlapping but different parts of the context-cost problem.

## Reproducible Command

Run from the repository root:

```bash
rtk .venv/bin/python -m cutctx.cli evals benchmark \
  --dataset tool_outputs \
  --compressors smart_crusher,content_router,diff,log,search,code \
  --metrics ratio,tokens_saved,f1,information_recall \
  --format markdown \
  --output /tmp/cutctx-quality-at-budget.md
```

For local comparison with existing benchmark docs:

```bash
rtk .venv/bin/python benchmarks/run_all.py --dry-run \
  --output /tmp/cutctx_bench_results.json
rtk .venv/bin/python benchmarks/compare.py \
  --tool cutctx \
  --tool llmlingua2 \
  --corpus synthetic \
  --corpus mixed \
  --dry-run \
  --output /tmp/cutctx_compare_results.json
```

## Metrics To Report

- Tokens saved: absolute token reduction versus uncompressed input.
- Compression ratio: `1 - (output_tokens / input_tokens)`.
- F1 / information recall: proxy for retained task-critical content.
- Latency: wall-clock cost of the compression decision.
- Decision outcome: accepted, rejected, or unchanged.

## Provider-Native Comparison

Provider-native mechanisms remain valuable and should be reported separately:

| Mechanism | Best At | Limitation | Cutctx Relationship |
|---|---|---|---|
| Provider prompt cache | Repeated stable prefixes | Usually provider-specific and prefix-shaped | Complementary; Cutctx reports cache savings separately |
| Provider compaction | Long conversation history | Does not govern arbitrary tool outputs across providers | Complementary; Cutctx handles logs, JSON, diffs, search, code |
| Manual truncation | Emergency context shrink | Blindly drops content | Cutctx preserves/retrieves originals where CCR is enabled |
| Cutctx compression | Tool outputs, logs, diffs, code/search payloads | Must be benchmarked per workload | Adds attribution, governance, replay, and local control |

## Acceptance Criteria

A run is buyer-safe to cite when:

- The benchmark command and git SHA are included.
- Dataset name, compressor list, and metrics are included.
- Skips or missing optional dependencies are stated.
- Provider-native savings are not double-counted with Cutctx savings.
- Claims are scoped to the workload tested.

## Current Release Positioning

Use this wording:

> Cutctx is additive to provider-native caching and compaction. It compresses
> production-shaped agent context such as tool outputs, logs, JSON, diffs, and
> search/code payloads, then reports savings by source so buyers can see what
> came from Cutctx versus provider cache behavior.

Avoid:

- "Best in market" without a fresh public head-to-head run.
- "Always preserves accuracy" without a workload-specific quality report.
- Combining provider cache savings and Cutctx compression savings into one
  undifferentiated number.
