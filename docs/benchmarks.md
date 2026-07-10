# Cutctx Benchmarks

> **Methodology note:** Compression ratio is `1 - (output_tokens / input_tokens)`. The most trustworthy numbers are the ones reproduced from the current repo state with the scripts in [`benchmarks/`](../benchmarks/).

## Quality-At-Budget V1

Release-ready benchmark framing is documented in [`artifacts/quality-at-budget-benchmark-v1.md`](../artifacts/quality-at-budget-benchmark-v1.md).

Use it to report:

- Tokens saved.
- Compression ratio.
- Tokens / second.
- F1 / information recall.
- Critical-item recall.
- Verbatim fidelity.
- Latency.
- Accepted/rejected decision outcome.
- Whether savings came from Cutctx, RTK command filtering, model routing, or provider-native cache behavior.

Provider-native prompt caching, RTK command filtering, model routing, and Cutctx compression are complementary. Do not mix them into one undifferentiated Cutctx compression number.

## Fresh Local Verification

### Release Evidence Bundle

The release bundle binds each named comparison arm to a SHA-256-hashed report,
so reviewers can distinguish a true raw baseline from an unavailable
provider-native arm:

```bash
rtk .venv/bin/python -m cutctx.cli.main evals benchmark \
  -d code_samples -d rag_samples -d mixed_agent_traces \
  -c raw_passthrough --parallel 1 --seed 42 --markdown \
  --output artifacts/raw-passthrough-benchmark.json
rtk .venv/bin/python scripts/generate_benchmark_release_manifest.py
rtk .venv/bin/python scripts/generate_benchmark_release_bundle.py
```

[`artifacts/benchmark-release-bundle.json`](../artifacts/benchmark-release-bundle.json)
contains separate entries for raw passthrough, `content_router`,
`verbatim_compactor`, canonical LLMLingua-2 XLM-R-large, and the explicit
provider-native unavailable status.

### Dry-Run Product Benchmarks

Re-run on **2026-06-29** in the current worktree:

```bash
./.venv/bin/python benchmarks/run_all.py --dry-run --output /tmp/cutctx_bench_results.json
./.venv/bin/python benchmarks/compare.py --tool cutctx --tool llmlingua2 --corpus synthetic --corpus mixed --dry-run --output /tmp/cutctx_compare_results.json
```

| Corpus | Input tokens | Output tokens | Reduction | Latency |
|---|---:|---:|---:|---:|
| JSON | 8112 | 3326 | 59.0% | 743.6 ms |
| Code | 921 | 921 | 0.0% | 3565.3 ms |
| Prose | 607 | 607 | 0.0% | 29.5 ms |
| Mixed | 1108 | 760 | 31.4% | 655.8 ms |

Interpretation:

- Cutctx is strongest on structured JSON-like content in the local dry run.
- The current dry-run corpora did not show wins on the small code and prose fixtures; the router correctly chose not to force low-confidence compression.

### Explicit Compaction Endpoint Behavior

The direct `/v1/compress` endpoint exposes two distinct modes:

- `balanced`: proxy-style conservative acceptance.
- `max_savings`: explicit compaction mode that accepts smaller wins and returns diagnostics.

Fresh local check on **2026-06-29** using a repetitive assistant payload:

| Profile | Input tokens | Output tokens | Tokens saved | Outcome |
|---|---:|---:|---:|---|
| `balanced` | 849 | 849 | 0 | Rejected `unchanged (ratio>=0.83)` |
| `max_savings` | 849 | 823 | 26 | Accepted, reported compressed |

### LLMLingua2 Comparison on Current Dry-Run Corpora

| Corpus | Tool | Input tokens | Output tokens | Reduction | Latency | Model size |
|---|---|---:|---:|---:|---:|---:|
| Synthetic | Cutctx | 6001 | 2444 | 59.3% | 10304.1 ms | 280 MB |
| Synthetic | LLMLingua2 | 6001 | 2444 | 59.3% | 5232.9 ms | 4200 MB |
| Mixed | Cutctx | 2839 | 1010 | 64.4% | 6545.8 ms | 280 MB |
| Mixed | LLMLingua2 | 2839 | 1010 | 64.4% | 1795.4 ms | 4200 MB |

Interpretation:

- On the current synthetic and mixed dry-run inputs, both tools landed on the same output-token counts.
- The strongest currently verified advantage is not universal ratio dominance; it is product fit, structured-data behavior, reversibility, and the much smaller reported model footprint in the harness.

### Breadth Re-Run on 2026-07-09

Pinned local eval suites now give us a deterministic breadth artifact beyond `ToolOutputSamples`:

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

Observed from [`artifacts/benchmark-breadth.md`](../artifacts/benchmark-breadth.md):

| Dataset | Compressor | Reduction | Tokens Saved | Tokens / Second | F1 | Information Recall | Critical Item Recall | Verbatim Fidelity |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| CodeSamples | ContentRouter | 74.8% | 111 | 3,225.8 | 0.823 | 1.000 | 1.000 | 1.000 |
| CodeSamples | SmartCrusher | 100.0% | 0 | 6,846,168.1 | 1.000 | 1.000 | 1.000 | 1.000 |
| RAGSamples | ContentRouter | 100.0% | 0 | 15,680.9 | 1.000 | 1.000 | 1.000 | 1.000 |
| RAGSamples | SmartCrusher | 100.0% | 0 | 8,888,897.9 | 1.000 | 1.000 | 1.000 | 1.000 |
| MixedAgentTraces | ContentRouter | 82.6% | 92 | 22,347.0 | 1.000 | 1.000 | 1.000 | 1.000 |
| MixedAgentTraces | SmartCrusher | 82.6% | 92 | 2,907,393.5 | 1.000 | 1.000 | 1.000 | 1.000 |

Interpretation:

- We now have repo-local breadth coverage across code, RAG, and mixed-agent traces.
- The benchmark is honest about abstentions: both compressors left the RAG fixtures unchanged, and `smart_crusher` declined the code fixtures rather than forcing low-confidence compression.
- `content_router` now recovers some savings on the local code fixtures while preserving all declared critical items and exact verbatim anchors.
- The previously broken local code-path proof is fixed: `content_router` now recovers meaningful savings on the local code fixtures while preserving declared critical items, exact verbatim anchors, and full information recall.
- The remaining code-path tradeoff is stylistic overlap quality: `F1` is still lower on those code fixtures because the safe fallback removes low-value comments and redundant whitespace while preserving executable content.
- Raw tokens/sec is now visible, but it needs context: unchanged or near-no-op paths can look extremely fast, so throughput should be interpreted alongside tokens saved and fidelity, not in isolation.

### LLMLingua Research Preset on 2026-07-09

We now also have a named CLI preset for the LLMLingua baseline path, using the same repo-local fixtures for both arms:

```bash
rtk ./.venv/bin/python -m cutctx.cli.main evals benchmark \
  --preset llmlingua_research \
  --disable-hf-xet \
  --hf-download-timeout 600 \
  --parallel 1 \
  --output artifacts/llmlingua-research-preset.json \
  --markdown
```

For a constrained machine, retain the same preset and explicitly identify the
smaller official LLMLingua-2 checkpoint in the artifact:

```bash
rtk ./.venv/bin/python -m cutctx.cli.main evals benchmark \
  --preset llmlingua_research \
  --llmlingua-model microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank \
  --disable-hf-xet \
  --hf-download-timeout 600 \
  --parallel 1 \
  --output artifacts/llmlingua-bert-base-research-preset.json \
  --markdown
```

Observed [`artifacts/llmlingua-research-preset.md`](../artifacts/llmlingua-research-preset.md):

| Dataset | ContentRouter Tokens Saved | LLMLingua Tokens Saved |
|---|---:|---:|
| CodeSamples | 111 | 202 |
| RAGSamples | 0 | 145 |
| MixedAgentTraces | 92 | 216 |
| VerbatimCompactionSamples | 180 | 299 |

This is a completed live run on 2026-07-10: 8/8 cells, zero errors, seed 42, and `metadata.llmlingua_model = microsoft/llmlingua-2-xlm-roberta-large-meetingbank` in the JSON artifact. The `llmlingua` optional extra is installed in the repo `uv` environment. `--disable-hf-xet` makes the comparison use the standard resumable HTTP downloader when the optional Xet transport is unavailable or stalls, while `--hf-download-timeout 600` prevents the default short transfer timeout from invalidating a large baseline-model download. `--llmlingua-model` supports separately labeled checkpoint comparisons.

### Completed LLMLingua-2 BERT Base Run on 2026-07-10

[`artifacts/llmlingua-bert-base-research-preset.json`](../artifacts/llmlingua-bert-base-research-preset.json)
records a completed real run with `metadata.llmlingua_model` set to
`microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank`: 8/8 cells,
zero errors, and the pinned seed 42 fixtures.

| Dataset | ContentRouter Saved | LLMLingua Saved | ContentRouter Critical Recall | LLMLingua Critical Recall |
|---|---:|---:|---:|---:|
| CodeSamples | 111 | 150 | 1.000 | 0.833 |
| RAGSamples | 0 | 140 | 1.000 | 0.333 |
| MixedAgentTraces | 92 | 164 | 1.000 | 0.333 |
| VerbatimCompactionSamples | 180 | 244 | 0.538 | 0.154 |

The comparison is intentionally not a win-only claim. On these fixtures the BERT-base
baseline removes more tokens, while `content_router` retains substantially more declared
critical items in every category. This is a live smaller-checkpoint comparison, not a
substitute for the still-pending canonical XLM-R large run.

Where Cutctx should beat LLMLingua-2:

- Structured agent context where route-aware abstention and critical-item preservation matter more than raw deletion.
- Workloads where reversibility, CCR retrieval, and gateway observability are part of the product requirement rather than separate concerns.

Where LLMLingua-2 may still look better:

- Raw prompt-compression bake-offs focused narrowly on deleting tokens from dense text without measuring retrieval, routing, or exact-anchor preservation.
- Environments that already have the model loaded on appropriate hardware and care primarily about the standalone compressor baseline.

### Compressor Task Classes

| Compressor | Intended task class | Strongest when | Weaker when |
|---|---|---|---|
| `content_router` | Mixed agent context | Requests blend code, logs, JSON, RAG chunks, and tool traces; abstention and routing matter more than single-method deletion | Narrow bake-offs that only reward raw token deletion on homogeneous text |
| `llmlingua` | Dense prose prompt compression baseline | Researchers or evaluators want a recognizable standalone neural prompt-compression arm on the same prompts | Workflows need reversibility, route-aware abstention, or exact-anchor guarantees |
| `verbatim_compactor` | Exact-anchor preservation | File paths, line numbers, stack traces, and error strings must survive compaction verbatim | Generic prose or mixed-context workloads where broad overlap matters more than exact anchors |

### Verbatim Compaction Benchmark on 2026-07-09

We now also have a dedicated local fixture suite for deletion-style, exact-preservation compaction:

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

Observed [`artifacts/verbatim-compaction-benchmark.md`](../artifacts/verbatim-compaction-benchmark.md):

| Dataset | Compressor | Reduction | Tokens Saved | Tokens / Second | F1 | Information Recall | Critical Item Recall | Verbatim Fidelity |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| VerbatimCompactionSamples | VerbatimCompactor | 71.4% | 151 | 3,969,719.5 | 0.741 | 0.750 | 1.000 | 1.000 |
| VerbatimCompactionSamples | ContentRouter | 69.5% | 180 | 1,688.2 | 0.839 | 0.867 | 0.538 | 0.538 |
| VerbatimCompactionSamples | SmartCrusher | 91.2% | 43 | 13,575,260.4 | 1.000 | 1.000 | 0.769 | 0.769 |

This split matters. On exact-preservation fixtures, the dedicated `verbatim_compactor` is currently the strongest local option for preserving file paths, line anchors, and error strings verbatim. `content_router` still overlaps more of the original text overall, but it is weaker on exact anchor preservation for this narrow workload.

### Aggregate Zero-Cost Suite on 2026-07-09

We now also have a single CLI entrypoint that rolls up the zero-cost compression checks into one report-card artifact:

```
rtk ./.venv/bin/python -m cutctx.evals suite \
  --tier 2 \
  --compression-only \
  --no-proxy \
  -o artifacts/eval-suite-compression-only
```

Observed from [`artifacts/eval-suite-compression-only/report_card.md`](../artifacts/eval-suite-compression-only/report_card.md):

| Benchmark | Metric | Value | Compression | Tokens Saved | Tokens / Second |
|---|---|---:|---:|---:|---:|
| CCR Round-trip | Byte Exact Match | 100.0% | 53% | 12,100 | 145,640.2 |
| Info Retention | Information Recall | 100.0% | 66% | 11,490 | 42,240.3 |
| Verbatim Compaction | Verbatim Fidelity | 100.0% | 29% | 151 | 4,048,760.3 |
| Tool Schema Compaction | Tool Schema Integrity | 100.0% | 19% | 119 | 2,638,642.0 |
| Tool Schema Compaction | Tool Schema Integrity | 100.0% | 19% | 119 | 2,885,628.8 |

This gives us one deterministic, zero-API-cost proof artifact for the local guarantees we are actually making: byte-stable CCR retention, information recall, verbatim anchor preservation, and schema integrity.

### CI Verification Surface

Fresh local run on **2026-07-09**:

```bash
rtk ./.venv/bin/python -m cutctx.cli verify --ci --format json -o verify-report.json
```

Observed from [`verify-report.json`](../verify-report.json):

- Dataset: `tool_outputs`
- Compressors: `content_router`, `smart_crusher`
- `content_router`: `335` tokens saved, `0.7912` ratio, `1.0` F1, `1.0` information recall, `1.0` critical-item recall, `65.61 ms` average latency
- `smart_crusher`: `335` tokens saved, `0.7912` ratio, `1.0` F1, `1.0` information recall, `1.0` critical-item recall, `0.22 ms` average latency

The verifier now warms one untimed case per compressor before enforcing the latency threshold, which removes first-run cold-start flakes while keeping the actual timed gate intact.

## Practical Positioning

What we can support with current evidence:

- Cutctx delivers meaningful token reduction on structured agent context.
- Cutctx has first-class proxy, wrap, CCR retrieval, observability, and dashboard integration.
- Cutctx can compete on compression while using a much smaller reported model artifact than LLMLingua2 in the local comparison harness.
- Cutctx is strongest as a local, reversible, cross-provider agent-context control plane with separate attribution for `rtk_cli_filtering`, `cutctx_compression`, cache savings, and model routing.

What we should avoid claiming without broader runs:

- “Best in market” across every workload.
- Blanket superiority over every competitor on raw compression ratio.

## Why Some Corpora Show Zero Reduction

Zero reduction in local `code` and `prose` dry-run fixtures is not automatically a bug. Common reasons:

- The sample is too small to justify compression overhead.
- The router judged the transform low-confidence and skipped it.
- The benchmark fixture is intentionally safety-biased rather than tuned for maximal shrinking.

That is generally preferable to forcing lossy compression on weak candidates.

## Reproducing Results

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
