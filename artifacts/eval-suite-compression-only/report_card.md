## Cutctx Accuracy Report Card

Model: `gpt-4o-mini` | Date: 2026-07-09 | Suite Cost: $0.00 | Duration: 1s

### Compression Benchmarks -- "Big Savings, Accuracy Preserved"

| Benchmark | Category | N | Metric | Value | Secondary Metrics | Compression | Tokens Saved | Status |
|-----------|----------|---|--------|-------|-------------------|-------------|--------------|--------|
| CCR Round-trip | lossless | 50 | Byte Exact Match | 100.0% | Tokens/s 145,640.2 | 53% | 12,100 | PASS |
| Info Retention | compression | 30 | Information Recall | 100.0% | Tokens/s 42,240.3 | 66% | 11,490 | PASS |
| Verbatim Compaction | compression | 3 | Verbatim Fidelity | 100.0% | Critical Item Recall 100.0% \| Verbatim Fidelity 100.0% \| Tokens/s 4,048,760.3 | 29% | 151 | PASS |
| Tool Schema Compaction | compression | 4 | Tool Schema Integrity | 100.0% | Tokens/s 2,638,642.0 | 19% | 119 | PASS |

**VERDICT: 4/4 PASS** | Avg delta: +0.000 | Avg savings: 42%
