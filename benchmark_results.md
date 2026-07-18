# Cutctx Compressor Benchmark Report

**How to read this report:** "Compression Ratio" is the *kept* fraction
(`compressed_tokens / original_tokens`) — lower is better, and 100.0% means
the compressor correctly passed the content through unchanged. These are the
built-in local fixture corpora (small N — a per-workload regression check,
not a marketing claim; see `docs/content/docs/benchmarks.mdx` for the claim
protocol and its limits).

Measured highlights from this run (2026-07-18, seed 42):

- **Tool outputs (primary workload):** ContentRouter keeps 71.5% of tokens
  (28.5% reduction) at F1 0.945 with 1.000 information recall;
  SmartCrusher keeps 79.1% at F1 1.000.
- **Code and prose/RAG:** individual compressors correctly pass through
  (100% kept). The full router compresses RAG fixtures to 54.7% kept but at
  F1 0.695 — aggressive prose compression carries measurable quality cost
  on these fixtures, consistent with the documented limitation that code
  and RAG content is not the primary compression target.
- **No expansion:** no cell in this run produced output larger than its
  input (the router now enforces this as a hard guarantee —
  `expansion_guard`).

Seed: `42` | Duration: 9.7s | Datasets: ToolOutputSamples, CodeSamples, RAGSamples, MixedAgentTraces

## Compression Ratio by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 79.1% | 88.3% | 79.3% | 100.0% | 78.8% | 71.5% |
| CodeSamples | 2 | 100.0% | 100.0% | 100.0% | 100.0% | 84.8% | 86.0% |
| RAGSamples | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 94.9% | 54.7% |
| MixedAgentTraces | 2 | 82.6% | 100.0% | 100.0% | 100.0% | 85.6% | 82.6% |

## Relative Delta vs SmartCrusher for Compression Ratio

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | -11.6% | -0.3% | -26.4% | +0.4% | +9.6% |
| CodeSamples | 2 | 0.0% | 0.0% | 0.0% | 0.0% | +15.2% | +14.0% |
| RAGSamples | 6 | 0.0% | 0.0% | 0.0% | 0.0% | +5.1% | +45.3% |
| MixedAgentTraces | 2 | 0.0% | -21.1% | -21.1% | -21.1% | -3.6% | 0.0% |


## F1 Score by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 1.000 | 0.882 | 0.862 | 1.000 | 0.999 | 0.945 |
| CodeSamples | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 0.951 | 0.846 |
| RAGSamples | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0.863 | 0.695 |
| MixedAgentTraces | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 0.982 | 1.000 |

## Relative Delta vs SmartCrusher for F1 Score

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | -11.8% | -13.8% | 0.0% | -0.1% | -5.5% |
| CodeSamples | 2 | 0.0% | 0.0% | 0.0% | 0.0% | -4.9% | -15.4% |
| RAGSamples | 6 | 0.0% | 0.0% | 0.0% | 0.0% | -13.7% | -30.5% |
| MixedAgentTraces | 2 | 0.0% | 0.0% | 0.0% | 0.0% | -1.8% | 0.0% |


## Information Recall by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 1.000 | 0.875 | 0.817 | 1.000 | 1.000 | 1.000 |
| CodeSamples | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 0.800 | 0.400 |
| RAGSamples | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| MixedAgentTraces | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Relative Delta vs SmartCrusher for Information Recall

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | -12.5% | -18.3% | 0.0% | 0.0% | 0.0% |
| CodeSamples | 2 | 0.0% | 0.0% | 0.0% | 0.0% | -20.0% | -60.0% |
| RAGSamples | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| MixedAgentTraces | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |


## Critical Item Recall by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 1.000 | 0.857 | 0.762 | 1.000 | 1.000 | 1.000 |
| CodeSamples | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| RAGSamples | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| MixedAgentTraces | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Relative Delta vs SmartCrusher for Critical Item Recall

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | -14.3% | -23.8% | 0.0% | 0.0% | 0.0% |
| CodeSamples | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| RAGSamples | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| MixedAgentTraces | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |


## Tokens / Second by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 13,639.3 | 90,720.1 | 2,106,936.3 | 114,034.7 | 46.4 | 3,286.2 |
| CodeSamples | 2 | 4,604,305.6 | 7,544,298.2 | 5,833,678.2 | 1,674,677.9 | 846.9 | 3,466.2 |
| RAGSamples | 6 | 5,345,094.9 | 4,689,682.7 | 3,564,737.7 | 1,941,253.5 | 395.1 | 7,105.2 |
| MixedAgentTraces | 2 | 5,483,280.5 | 4,104,014.2 | 3,466,732.0 | 4,137,319.5 | 913.9 | 23,540.7 |

## Relative Delta vs SmartCrusher for Tokens / Second

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | +565.1% | +15347.5% | +736.1% | -99.7% | -75.9% |
| CodeSamples | 2 | 0.0% | +63.9% | +26.7% | -63.6% | -100.0% | -99.9% |
| RAGSamples | 6 | 0.0% | -12.3% | -33.3% | -63.7% | -100.0% | -99.9% |
| MixedAgentTraces | 2 | 0.0% | -25.2% | -36.8% | -24.5% | -100.0% | -99.6% |


## Verbatim Fidelity by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 1.000 | 0.857 | 0.762 | 1.000 | 1.000 | 1.000 |
| CodeSamples | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| RAGSamples | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| MixedAgentTraces | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Relative Delta vs SmartCrusher for Verbatim Fidelity

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | -14.3% | -23.8% | 0.0% | 0.0% | 0.0% |
| CodeSamples | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| RAGSamples | 6 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| MixedAgentTraces | 2 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |


_Generated by `cutctx evals benchmark`_
