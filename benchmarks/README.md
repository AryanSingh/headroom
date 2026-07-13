# Cutctx Benchmarks

This directory contains reproducible benchmark runners for the compression results reported in `/docs/benchmarks.md`.

## Quick Start

### Install Dependencies

```bash
pip install "cutctx-ai" tiktoken
```

Optional: For comparisons with other tools:
```bash
pip install llmlingua2
```

For the main eval CLI preset, install the optional adapter extra:
```bash
pip install "cutctx-ai[llmlingua]"
```

### Run Benchmarks

#### Run all benchmarks with synthetic data (no corpus download needed):
```bash
cd benchmarks/
python run_all.py --dry-run
```

#### Run full benchmarks (requires corpus files):
```bash
python run_all.py --output results.json
```

#### Compare specific tools on a corpus:
```bash
python compare.py --tool cutctx --tool llmlingua2 --corpus toolbench --dry-run
```

#### Run the publishable-comparison smoke harness:

```bash
# Both invocations are supported. Use at least three measured runs and one
# warm-up so one-time model loading does not dominate latency.
python benchmarks/run_comparison.py --runs 3 --warmup-runs 1 \
  --output benchmarks/results/latest.json
```

The harness records cl100k token counts, F1/ROUGE-L retention against the input,
median per-fixture latency, run counts, interpreter, and platform metadata. It is
a fixture regression check, not a substitute for a public comparison protocol with
real corpora and downstream task-quality evaluation.

#### Verify model-routing quality and unsafe-downgrade safety:

```bash
python benchmarks/model_routing_quality.py \
  --ci \
  --output artifacts/model-routing-quality.json
```

This deterministic labeled set reports a confusion matrix, balanced accuracy,
Mini/Luna/strong tier accuracy, per-tier recall, and unsafe-downgrade rate. The
CI gate requires zero unsafe Mini downgrades and at least 95% balanced and tier
accuracy.

#### Run the fixed-fixture LLMLingua research preset through the main eval CLI:
```bash
cutctx evals benchmark --preset llmlingua_research --parallel 1 --output artifacts/llmlingua-research-preset.json --markdown
```

This preset pins four repo-local fixture datasets and runs `content_router` and
`llmlingua` side by side on the same prompts with ratio, savings, throughput,
F1, information recall, critical-item recall, and verbatim fidelity.

## Setup

### CPU vs GPU Configuration

**Cutctx** runs primarily on CPU (SmartCrusher is pure Rust, CodeCompressor uses AST). The ONNX int8 model is optimized for CPU inference and uses ~280 MB RAM.

**LLMLingua2** requires GPU for best performance. Set:
```bash
export CUDA_VISIBLE_DEVICES=0  # Use GPU 0
```

### Corpus Files (Optional)

For real corpus benchmarks, place the following in a `corpora/` directory:

- **toolbench**: Download from [Llama-index ToolBench](https://github.com/run-llama/llama-index-tools)
- **longbench**: Download from [LongBench](https://github.com/THUDM/LongBench)
- **mixed**: Combine samples from both corpora

Example structure:
```
benchmarks/
├── corpora/
│   ├── toolbench/
│   │   ├── queries.jsonl
│   │   └── tools.jsonl
│   └── longbench/
│       └── data.jsonl
├── run_all.py
├── compare.py
└── results.json
```

### Environment Variables

- `CUTCTX_MODEL_PATH`: Override default Kompress model path (if using custom quantization)
- `TIKTOKEN_CACHE_DIR`: Override tiktoken model cache location

## Results

Results are saved as JSON with this structure:

```json
{
  "timestamp": "2026-06-15T10:30:00Z",
  "machine": {
    "cpu": "...",
    "cores": 8,
    "ram_gb": 32,
    "gpu": "..."
  },
  "benchmarks": [
    {
      "tool": "cutctx",
      "corpus": "toolbench",
      "metrics": {
        "input_tokens": 45000,
        "output_tokens": 9200,
        "compression_ratio": 0.795,
        "latency_ms": 125.5,
        "throughput_tokens_per_sec": 2400
      }
    }
  ]
}
```

## Interpreting Results

### Compression Ratio
- Formula: `1 - (output_tokens / input_tokens)`
- **0.80** = 80% reduction (10x efficiency)
- **0.50** = 50% reduction (2x efficiency)

### Quality Retention (CCR)
- Cutctx+CCR allows on-demand retrieval of original content
- Downstream task accuracy stays within 1% of uncompressed

### Throughput
- Cutctx SmartCrusher: ~45,000 tok/s (pure Rust)
- Cutctx Kompress: ~2,400 tok/s (ONNX int8)
- LLMLingua2: ~800 tok/s (PyTorch GPU)

## Hardware Used in Documentation

All benchmarks in `/docs/benchmarks.md` were run on:
- **Machine**: MacBook Pro M3 (8-core CPU, 36 GB RAM)
- **GPU**: None (all tools run on CPU)
- **Python**: 3.11.x

To match these results, use similar hardware or adjust expectations for your platform.

## Extending Benchmarks

### Add a New Corpus

1. Create a function in `run_all.py` that loads your corpus (see `load_synthetic_data()`)
2. Add to `AVAILABLE_CORPORA` dict
3. Update `compare.py` to include your corpus

### Add a New Tool

1. Import the tool's compression API
2. Add a handler function (e.g., `compress_with_llmlingua2()`)
3. Handle ImportError gracefully (tool is optional)
4. Run benchmarks with `--tool your_tool_name`

## Troubleshooting

### "llmlingua2 not installed"
Install: `pip install llmlingua2`

### "Cutctx model not found"
Run: `python -c "from cutctx import compress; compress('test')"` to download models

### Inconsistent timing results
- Warm up with a few iterations before measuring
- Close other applications
- Run multiple times and report mean ± std dev

### OOM (Out of Memory) errors
- Reduce corpus size: modify `--corpus-limit 100` in scripts
- Disable GPU: `export CUDA_VISIBLE_DEVICES=''`
- Use `--dry-run` instead of full corpus

## References

- [Cutctx Documentation](https://github.com/cutctx-sdk/cutctx)
- [LLMLingua2 Paper](https://arxiv.org/abs/2403.12968)
- [ToolBench Dataset](https://github.com/run-llama/llama-index-tools)
