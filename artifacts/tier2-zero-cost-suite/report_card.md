## Cutctx Accuracy Report Card

Model: `gpt-4o-mini` | Date: 2026-07-09 | Suite Cost: $0.00 | Duration: 1s

### Compression Benchmarks -- "Big Savings, Accuracy Preserved"

| Benchmark | Category | N | Metric | Value | Secondary Metrics | Compression | Tokens Saved | Status |
|-----------|----------|---|--------|-------|-------------------|-------------|--------------|--------|
| CCR Round-trip | lossless | 50 | Byte Exact Match | 100.0% | Tokens/s 161,293.6 | 53% | 12,100 | PASS |
| Info Retention | compression | 30 | Information Recall | 100.0% | Tokens/s 76,545.3 | 66% | 11,490 | PASS |
| Verbatim Compaction | compression | 3 | Verbatim Fidelity | 100.0% | Critical Item Recall 100.0% \| Verbatim Fidelity 100.0% \| Tokens/s 4,107,062.5 | 29% | 151 | PASS |
| Tool Schema Compaction | compression | 4 | Tool Schema Integrity | 100.0% | Tokens/s 2,885,628.8 | 19% | 119 | PASS |

**VERDICT: 4/4 PASS** | Avg delta: +0.000 | Avg savings: 42%
