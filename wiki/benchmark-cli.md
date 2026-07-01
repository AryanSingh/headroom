# Benchmark CLI (`cutctx evals benchmark`)

Reproducible compressor benchmarking on standard datasets (zero-LLM by default). Runs one or more compression algorithms against one or more evaluation datasets, scores compression ratio, token savings, F1 retention, and information recall, then produces comparable results in JSON and Markdown table format.

## Overview

### Problem

Compressor development requires measurable, reproducible comparisons:
- "Is SmartCrusher better than Kompress on code?"
- "Does ContentRouter help information recall?"
- "How much does each compressor save in tokens?"

Running compressors ad-hoc on arbitrary data gives inconsistent results. The benchmark command provides:
1. **Standard datasets** — tool_outputs, LongBench, SQuAD, HotpotQA (same data every run)
2. **Reproducible sampling** — seed-based random selection so results are replicable
3. **Multiple metrics** — compression ratio, token savings, F1, ROUGE-L, information recall, exact match
4. **Parallel execution** — test multiple compressors in parallel
5. **Table output** — LLMLingua-paper-style Markdown for publications

### How It Differs from Memory Evaluation

| Aspect | Benchmark | Memory Eval |
|--------|-----------|------------|
| **Purpose** | Measure compression quality (ratio, retention) | Measure retrieval quality (top-K recall) |
| **Datasets** | Static evaluation datasets (tool_outputs, SQuAD) | Long-context memory tasks (LoCoMo) |
| **LLM** | None required (all metrics local) | LLM-required (answer generation, judging) |
| **Output** | Tables, JSON | Structured eval results |

---

## Datasets

The benchmark supports:

| Dataset | Name | Size | Content | Notes |
|---------|------|------|---------|-------|
| **Tool Outputs** | `tool_outputs` | Fixed | LLM tool output (JSON, logs, diffs) | Built-in, no dependency |
| **LongBench** | `longbench` | Variable | Long documents (1–4K tokens) | Requires `longbench` package; subtask selectable |
| **SQuAD** | `squad` | 100 samples | QA contexts and questions | Requires `datasets` package |
| **HotpotQA** | `hotpotqa` | Variable | Multi-hop QA contexts | Requires `datasets` package |

### LongBench Subtasks

When using `longbench`, specify a subtask with `--longbench-task`:
- `qasper` (default) — Academic papers (QA)
- `multifieldqa_en` — Diverse documents
- `narrativeqa` — Long narratives

---

## Compressors

All compressors in the registry can be benchmarked:

| Compressor | Key | Type | Status |
|------------|-----|------|--------|
| SmartCrusher | `smart_crusher` | Syntax-aware JSON | Production |
| Log Compressor | `log` | Log line summarization | Production |
| Search Compressor | `search` | Search result dedup | Production |
| Diff Compressor | `diff` | Git diff formatting | Production |
| Code Compressor | `code` | Source code reduction | Production |
| Kompress | `kompress` | Token-level compression | Production |
| LLMLingua | `llmlingua` | LLM-guided compression | Experimental |
| Drain3 | `drain3` | Log clustering | Experimental |
| ContentRouter | `content_router` | Dispatch to best compressor | Production |

Use `--compressors all` (default) to test all, or name specific ones: `--compressors smart_crusher log content_router`.

---

## Metrics

Computed per compressor per dataset:

| Metric | Description | LLM Required | Formula |
|--------|-------------|--------------|---------|
| **ratio** | Compressed tokens / original tokens | No | `len(compressed) / len(original)` |
| **tokens_saved** | Original tokens − compressed tokens (total across dataset) | No | Sum over all cases |
| **f1** | F1 token-level overlap between original and compressed | No | F1(original tokens, compressed tokens) |
| **rouge_l** | ROUGE-L (longest common subsequence) | No | LCS-based similarity |
| **information_recall** | Fraction of key information preserved | No | Probe-based (5 retrieval probes per case) |
| **exact_match** | Percentage of cases unchanged | No | `compressed == original` |

Default metrics: `ratio`, `f1`, `information_recall`.

---

## CLI Usage

### Basic Invocation

```bash
cutctx evals benchmark
```

Runs all compressors against `tool_outputs` (default dataset), 50 samples, seed=42.

### Specifying Datasets

```bash
# Single dataset
cutctx evals benchmark -d squad -n 30

# Multiple datasets
cutctx evals benchmark -d tool_outputs -d squad -d hotpotqa -n 20

# LongBench with subtask
cutctx evals benchmark -d longbench --longbench-task multifieldqa_en -n 100
```

### Selecting Compressors

```bash
# Test three compressors
cutctx evals benchmark -c smart_crusher -c log -c content_router

# All compressors (default)
cutctx evals benchmark -c all

# Single compressor
cutctx evals benchmark -c smart_crusher
```

### Selecting Metrics

```bash
# Custom metrics
cutctx evals benchmark --metrics ratio --metrics f1 --metrics information_recall

# All available metrics
cutctx evals benchmark --metrics ratio --metrics tokens_saved --metrics f1 --metrics rouge_l --metrics information_recall --metrics exact_match
```

### Parallel Execution

```bash
# Test 8 compressors in parallel (default 4)
cutctx evals benchmark --parallel 8
```

### Output to File

```bash
# Save JSON results
cutctx evals benchmark --output results.json

# Also save Markdown table
cutctx evals benchmark --output results.json --markdown
# Creates results.json and results.md
```

### Reproducible Sampling

```bash
# Use seed 123 instead of default (42)
cutctx evals benchmark --seed 123
```

### Full Example

```bash
cutctx evals benchmark \
  -d tool_outputs -d squad \
  -c smart_crusher -c content_router -c llmlingua \
  --metrics ratio --metrics information_recall \
  -n 50 \
  --parallel 6 \
  --seed 42 \
  --output benchmark_results.json \
  --markdown
```

---

## Example Output

### Console Output (Text Summary)

```
╔═══════════════════════════════════════════════════════════════════════╗
║ CUTCTX COMPRESSOR BENCHMARK ║
║ Reproducible Cross-Compressor Comparison ║
╚═══════════════════════════════════════════════════════════════════════╝

Configuration:
  Datasets:         tool_outputs, squad
  Samples/dataset:  50
  Compressors:      SmartCrusher, Log, ContentRouter
  Metrics:          ratio, f1, information_recall
  Seed:             42
  Parallel:         4

Running benchmarks...
  Loading dataset: tool_outputs ... 42 cases loaded
    Running 3 compressors ...
  Loading dataset: squad ... 50 cases loaded
    Running 3 compressors ...

Results:

tool_outputs:
  ✓ SmartCrusher   45.2% (124,560 tokens saved)
  ✓ Log            38.1% (156,200 tokens saved)
  ✓ ContentRouter  42.8% (132,840 tokens saved)

  F1 Score:
    SmartCrusher        0.845
    Log                 0.762
    ContentRouter       0.891

  Information Recall:
    SmartCrusher        0.92
    Log                 0.78
    ContentRouter       0.95

squad:
  ✓ SmartCrusher   48.1% (98,560 tokens saved)
  ✓ Log            52.3% (75,200 tokens saved)
  ✓ ContentRouter  46.2% (105,840 tokens saved)

  F1 Score:
    SmartCrusher        0.798
    Log                 0.712
    ContentRouter       0.823

  Information Recall:
    SmartCrusher        0.88
    Log                 0.71
    ContentRouter       0.91
```

### JSON Output

```json
{
  "seed": 42,
  "compressors": ["smart_crusher", "log", "content_router"],
  "datasets": ["tool_outputs", "squad"],
  "results": [
    {
      "dataset": "tool_outputs",
      "compressor": "smart_crusher",
      "n": 42,
      "ratio": 0.452,
      "tokens_saved": 124560,
      "f1": 0.845,
      "information_recall": 0.92,
      "avg_ms": 2.3,
      "p50_ms": 1.8,
      "errors": 0,
      "skipped": false
    },
    ...
  ],
  "totals": {
    "duration_seconds": 45.2,
    "total_tokens_saved": 604200
  }
}
```

### Markdown Output (with `--markdown`)

```markdown
# Cutctx Compressor Benchmark Report

Seed: `42` | Duration: 45.2s | Datasets: tool_outputs, squad

## Compression Ratio

| Compressor | tool_outputs | squad |
|------------|--------------|-------|
| SmartCrusher | 0.452 | 0.481 |
| Log | 0.381 | 0.523 |
| ContentRouter | 0.428 | 0.462 |

## F1 Score

| Compressor | tool_outputs | squad |
|------------|--------------|-------|
| SmartCrusher | 0.845 | 0.798 |
| Log | 0.762 | 0.712 |
| ContentRouter | 0.891 | 0.823 |

## Information Recall

| Compressor | tool_outputs | squad |
|------------|--------------|-------|
| SmartCrusher | 0.920 | 0.880 |
| Log | 0.780 | 0.710 |
| ContentRouter | 0.950 | 0.910 |

_Generated by `cutctx evals benchmark`_
```

---

## Key Implementation Notes

### Zero-LLM by Default

The benchmark requires **no LLM** by default. All metrics (ratio, F1, ROUGE-L, information recall) are computed locally using:
- Token-level string comparison (F1, ROUGE-L)
- Retrieval probes (information recall: generates 5 key phrases from original, checks if preserved in compressed)
- Exact matching (exact_match metric)

This makes benchmarking fast and reproducible without API costs.

### Reproducible Sampling

Each run with the same `--seed` selects the exact same samples from the dataset, ensuring identical comparisons across machines and time.

### Parallel Compression

Compressors run in parallel (default 4 workers) via `ThreadPoolExecutor`. Each case is compressed in isolation to avoid thread-safety issues.

### Missing Dependencies

If an optional compressor (e.g., LLMLingua) is not installed, it's marked `skipped` with a note. The benchmark continues for available compressors.

---

## Typical Workflows

### Publish Comparison Table

```bash
# Run once, save to markdown
cutctx evals benchmark \
  -d tool_outputs -d squad \
  -c smart_crusher -c content_router -c llmlingua \
  --metrics ratio --metrics f1 --metrics information_recall \
  -n 100 \
  --output paper_results.json \
  --markdown

# Markdown table is at paper_results.md
cat paper_results.md
```

### Regression Testing

```bash
# Establish baseline
cutctx evals benchmark -d tool_outputs -n 50 --seed 42 --output baseline.json

# After changes, compare
cutctx evals benchmark -d tool_outputs -n 50 --seed 42 --output current.json

# Diff the JSON
jq '.results[] | {compressor, ratio}' baseline.json current.json
```

### New Compressor Evaluation

```bash
# Test a new compressor against all others
cutctx evals benchmark \
  -d tool_outputs -d longbench -d squad \
  -c my_new_compressor -c smart_crusher -c content_router \
  --metrics ratio --metrics information_recall \
  -n 50 --output new_compressor_eval.json
```

---

## Limitations

1. **Limited dataset diversity**: Available datasets focus on JSON, code, and QA contexts. Custom datasets not yet supported.
2. **No streaming evaluation**: Benchmarks compress entire contexts; streaming or incremental compression not evaluated.
3. **Single-threaded per-case compression**: If a compressor internally parallelizes, the `--parallel` flag doesn't help it (only enables parallelism across cases).
4. **Simple information recall**: Probe-based recall (5 key phrases) is a heuristic; semantic preservation not directly measured.

---

## Related

- **LoCoMo Memory Evaluation** — `cutctx evals memory` tests long-context retrieval and reasoning
- **Session Probes** — `cutctx evals probes` scores compression quality on recorded sessions
- **Compression Profiles** — `cutctx profile show` shows learned per-workspace recommendations
