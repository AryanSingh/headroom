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
- **RAG/prose is query-aware, not lossy-blind:** with a query, the router
  drops query-irrelevant content (54.7% kept) while keeping information
  recall at 1.000 — the F1-vs-whole-input drop reflects intentionally
  removed irrelevant text. Without a query signal, prose passes through
  unchanged (100% kept, verified per-sample).
- **Code elision keeps configuration values:** omitted function bodies now
  carry a `values:` line (timeouts, backoff factors) alongside identifier
  anchors, raising code information recall from 0.400 to 0.800; the
  remainder is raw elided-body spans recoverable via the CCR retrieval
  hash. Reassembled Python is verified syntactically valid (future-import
  ordering fixed).
- **No expansion:** no cell in this run produced output larger than its
  input (the router enforces this as a hard guarantee — `expansion_guard`).

Seed: `42` | Duration: 8.7s | Datasets: ToolOutputSamples, CodeSamples, RAGSamples, MixedAgentTraces

## Compression Ratio by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 79.1% | 88.3% | 79.3% | 100.0% | 78.8% | 71.5% |
| CodeSamples | 2 | 100.0% | 100.0% | 100.0% | 100.0% | 84.8% | 87.4% |
| RAGSamples | 6 | 100.0% | 100.0% | 100.0% | 100.0% | 94.9% | 54.7% |
| MixedAgentTraces | 2 | 82.6% | 100.0% | 100.0% | 100.0% | 85.6% | 82.6% |

## Relative Delta vs SmartCrusher for Compression Ratio

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | -11.6% | -0.3% | -26.4% | +0.4% | +9.6% |
| CodeSamples | 2 | 0.0% | 0.0% | 0.0% | 0.0% | +15.2% | +12.6% |
| RAGSamples | 6 | 0.0% | 0.0% | 0.0% | 0.0% | +5.1% | +45.3% |
| MixedAgentTraces | 2 | 0.0% | -21.1% | -21.1% | -21.1% | -3.6% | 0.0% |


## F1 Score by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 1.000 | 0.882 | 0.862 | 1.000 | 0.999 | 0.945 |
| CodeSamples | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 0.951 | 0.859 |
| RAGSamples | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0.863 | 0.695 |
| MixedAgentTraces | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 0.982 | 1.000 |

## Relative Delta vs SmartCrusher for F1 Score

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | -11.8% | -13.8% | 0.0% | -0.1% | -5.5% |
| CodeSamples | 2 | 0.0% | 0.0% | 0.0% | 0.0% | -4.9% | -14.1% |
| RAGSamples | 6 | 0.0% | 0.0% | 0.0% | 0.0% | -13.7% | -30.5% |
| MixedAgentTraces | 2 | 0.0% | 0.0% | 0.0% | 0.0% | -1.8% | 0.0% |


## Information Recall by Dataset × Compressor

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 1.000 | 0.875 | 0.817 | 1.000 | 1.000 | 1.000 |
| CodeSamples | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 0.800 | 0.800 |
| RAGSamples | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| MixedAgentTraces | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Relative Delta vs SmartCrusher for Information Recall

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | -12.5% | -18.3% | 0.0% | 0.0% | 0.0% |
| CodeSamples | 2 | 0.0% | 0.0% | 0.0% | 0.0% | -20.0% | -20.0% |
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
| ToolOutputSamples | 8 | 15,283.3 | 121,308.7 | 5,605,508.0 | 754,498.5 | 52.7 | 5,846.3 |
| CodeSamples | 2 | 8,084,354.9 | 4,742,704.6 | 4,166,199.6 | 1,623,241.2 | 874.5 | 4,317.7 |
| RAGSamples | 6 | 8,709,915.7 | 3,356,209.2 | 1,661,310.1 | 995,038.3 | 423.4 | 8,202.3 |
| MixedAgentTraces | 2 | 3,018,589.0 | 3,452,865.5 | 4,364,445.6 | 2,474,172.4 | 857.0 | 23,669.8 |

## Relative Delta vs SmartCrusher for Tokens / Second

| Dataset | N | SmartCrusher | Log | Search | Diff | Kompress | ContentRouter |
|---|---|---|---|---|---|---|---|
| ToolOutputSamples | 8 | 0.0% | +693.7% | +36577.4% | +4836.8% | -99.7% | -61.7% |
| CodeSamples | 2 | 0.0% | -41.3% | -48.5% | -79.9% | -100.0% | -99.9% |
| RAGSamples | 6 | 0.0% | -61.5% | -80.9% | -88.6% | -100.0% | -99.9% |
| MixedAgentTraces | 2 | 0.0% | +14.4% | +44.6% | -18.0% | -100.0% | -99.2% |


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
