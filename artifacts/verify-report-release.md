# Cutctx Verify Report

Git SHA: `418ae99a`
Status: **PASS**
Datasets: tool_outputs
Compressors: content_router, smart_crusher

## Thresholds

- F1 >= 0.90
- Information recall >= 0.90
- Compression ratio <= 0.95
- Latency <= 250 ms

## Results

| Dataset | Compressor | Tokens Saved | Compression Ratio | F1 | Information Recall | Critical Item Recall | Latency ms | Status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| ToolOutputSamples | content_router | 335 | 0.791 | 1.000 | 1.000 | 1.000 | 92.36 | PASS |
| ToolOutputSamples | smart_crusher | 335 | 0.791 | 1.000 | 1.000 | 1.000 | 0.12 | PASS |

Summary: 2 passed, 0 failed, 0 skipped.
