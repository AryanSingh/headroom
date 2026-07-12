# Quality-At-Budget Benchmark V1

Date: 2026-07-09
Status: Release-ready documentation scope

## Purpose

This benchmark is the public, reproducible proof surface for the claim:

> Cutctx reduces context cost while preserving useful answer quality on production-shaped agent context.

It is not a claim that Cutctx beats every provider-native optimization on every workload. Provider prompt caching, provider-native compaction, and Cutctx solve overlapping but different parts of the context-cost problem.

## Reproducible Commands

Run from repository root:

```bash
rtk .venv/bin/python -m cutctx.cli evals benchmark \
  --dataset tool_outputs \
  --compressors smart_crusher,content_router,diff,log,search,code \
  --metrics ratio,tokens_saved,tokens_per_second,f1,information_recall,critical_item_recall,verbatim_fidelity \
  --format markdown \
  --output /tmp/cutctx-quality-at-budget.md
```

For local comparison with the existing benchmark docs:

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

Pinned local breadth verification across code, RAG, and mixed-agent traces:

```bash
rtk .venv/bin/python -m cutctx.cli evals benchmark \
  -d code_samples -d rag_samples -d mixed_agent_traces \
  -c content_router -c smart_crusher \
  --metrics ratio --metrics tokens_saved --metrics tokens_per_second \
  --metrics f1 --metrics information_recall --metrics critical_item_recall \
  --metrics verbatim_fidelity \
  --parallel 1 \
  --output artifacts/benchmark-breadth.json \
  --markdown
```

Fresh local run on 2026-07-12 produced [`artifacts/benchmark-breadth.md`](./benchmark-breadth.md) with:

- `CodeSamples`: `content_router` now saves `63` tokens at `83.8%` ratio, runs at `3,986.3` tokens/sec, and preserves `1.000` critical-item recall / `1.000` verbatim fidelity with `0.790` F1 and `0.400` information recall; `smart_crusher` stayed unchanged at `100.0%` ratio with `1.000` F1 / recall.
- `RAGSamples`: expanded from 2 to 6 runbook, policy, recovery, capacity, privacy, and cache-incident cases. Query-aware `content_router` saves `430` tokens at `54.7%` ratio while preserving `1.000` information recall, `1.000` critical-item recall, and `1.000` verbatim fidelity. `smart_crusher` correctly stays unchanged on prose.
- `MixedAgentTraces`: both compressors saved `92` tokens at `82.6%` ratio with `1.000` F1, `1.000` information recall, and `1.000` critical-item recall.

This breadth slice proves more than a single `tool_outputs` corpus while staying fully local and deterministic. It also shows the current limit honestly: the code and prose paths now recover meaningful savings while keeping exact critical anchors, but their broad lexical F1 (`0.823` and `0.695`) is intentionally lower because irrelevant sentences are removed.

The LLMLingua research preset now treats a comparator that falls back on every
case as unavailable/skipped instead of rendering misleading zero-ratio rows.
On this machine LLMLingua is currently skipped, so this run is not presented as
a valid external head-to-head result.

## Metrics To Report

- Tokens saved: absolute token reduction versus uncompressed input.
- Compression ratio: `1 - (output_tokens / input_tokens)`.
- Tokens / second: original tokens processed divided by measured compression time.
- F1 / information recall: whether the proxy retained task-critical content.
- Critical-item recall: whether explicit must-keep strings survive compression.
- Verbatim fidelity: whether must-keep strings survive exactly, byte-for-byte.
- Latency: wall-clock cost of the compression decision.
- Decision outcome: accepted, rejected, or unchanged.

For `cutctx verify --ci`, warm one untimed case per compressor before enforcing latency thresholds so first-run cache/setup cost does not create CI-only flakes.
For throughput numbers, distinguish real compression work from passthrough-ish or near-no-op paths. Extremely high tokens/sec on unchanged outputs are useful for harness visibility but should not be marketed as equivalent to high-savings compression throughput.

## Dedicated Verbatim Compaction Slice

Pinned local verbatim-compaction verification now runs separately from the broader breadth slice:

```bash
rtk ./.venv/bin/python -m cutctx.cli.main evals benchmark \
  -d verbatim_compaction \
  -c verbatim_compactor -c content_router -c smart_crusher \
  --metrics ratio --metrics tokens_saved --metrics tokens_per_second \
  --metrics f1 --metrics information_recall --metrics critical_item_recall \
  --metrics verbatim_fidelity \
  --parallel 1 \
  --output artifacts/verbatim-compaction-benchmark.json \
  --markdown --html
```

Fresh local run on 2026-07-09 produced [`artifacts/verbatim-compaction-benchmark.md`](./verbatim-compaction-benchmark.md) with:

- `VerbatimCompactor`: `151` tokens saved at `71.4%` ratio, `3,969,719.5` tokens/sec, `1.000` critical-item recall, and `1.000` verbatim fidelity.
- `ContentRouter`: `180` tokens saved at `69.5%` ratio, but only `0.538` critical-item recall / `0.538` verbatim fidelity on these exact-preservation fixtures.
- `SmartCrusher`: highest broad overlap on this slice (`1.000` F1 / information recall) but lower exact-anchor preservation than `verbatim_compactor` and much less savings.

This is the honest narrow proof point. The dedicated compaction mode is now stronger on preserving exact file paths, line anchors, and error strings than the broader router, even when the router overlaps more of the original text overall.

## Aggregate Zero-Cost Suite

The dedicated benchmark above is also covered by the suite runner's zero-cost report-card path:

```bash
rtk ./.venv/bin/python -m cutctx.evals suite \
  --tier 2 \
  --compression-only \
  --no-proxy \
  -o artifacts/eval-suite-compression-only
```

Fresh local run on 2026-07-09 produced [`artifacts/eval-suite-compression-only/report_card.md`](./eval-suite-compression-only/report_card.md) with `4/4` passing compression-only checks:

- `CCR Round-trip`: `100.0%` byte exact match, `12,100` tokens saved, `145,640.2` tokens/sec.
- `Info Retention`: `100.0%` information recall, `11,490` tokens saved, `42,240.3` tokens/sec.
- `Verbatim Compaction`: `100.0%` verbatim fidelity, `151` tokens saved, `4,048,760.3` tokens/sec.
- `Tool Schema Compaction`: `100.0%` tool schema integrity, `119` tokens saved, `2,638,642.0` tokens/sec.

This matters because the proof now exists in both forms: a dedicated comparator benchmark and a single zero-cost suite artifact that can be handed to evaluators without live-provider dependencies.

## Provider-Native Comparison

Provider-native mechanisms remain valuable and should be reported separately:

| Mechanism | Best At | Limitation | Cutctx Relationship |
|---|---|---|---|
| Provider prompt cache | Repeated stable prefixes | Usually provider-specific and prefix-shaped | Complementary; Cutctx reports cache savings separately |
| Provider compaction | Long conversation history | Does not govern arbitrary tool outputs across providers | Complementary; Cutctx handles logs, JSON, diffs, search, and code |
| Manual truncation | Emergency context shrink | Blindly drops content | Cutctx preserves and retrieves originals where CCR is enabled |
| Cutctx compression | Tool outputs, logs, diffs, code/search payloads | Must be benchmarked per workload | Adds attribution, governance, replay, and local control |

## Acceptance Criteria

This run is buyer-safe to cite when:

- Benchmark command and git SHA are included.
- Dataset name, compressor list, and metrics are included.
- Skips or missing optional dependencies are stated.
- Provider-native savings are not double-counted as Cutctx savings.
- Claims are scoped to the workload tested.

## Current Release Positioning

Use wording like:

> Cutctx is additive to provider-native caching and compaction. It compresses production-shaped agent context such as tool outputs, logs, JSON, diffs, and search/code payloads, and it reports savings by source so buyers can see what came from Cutctx versus provider cache behavior.

Avoid:

- “Best in market” without a fresh public head-to-head run.
- “Always preserves accuracy” without workload-specific quality reporting.
- Combining provider cache savings and Cutctx compression savings into one undifferentiated number.
