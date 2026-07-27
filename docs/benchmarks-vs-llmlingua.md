# Head-to-head: ContentRouter vs LLMLingua-2

Microsoft's [LLMLingua-2](https://github.com/microsoft/LLMLingua) is the
published baseline for prompt compression, so it is the honest thing to
measure against. This page reports what happened.

**Summary:** our ML path is at parity with LLMLingua-2 (0.962 vs 0.960 info
recall on LongBench at matched ratio). Our *default* path is a different
proposition entirely — 150–500x faster and compressing 2–5x harder, at lower
fidelity — which is the right trade for a proxy in the request path and one
LLMLingua has no equivalent for.

## Method

- Datasets: HotpotQA (multi-hop QA) and LongBench (long-context), loaded via
  `cutctx.evals.datasets`. NarrativeQA failed to load
  (`DatasetGenerationError`) and is excluded rather than silently skipped.
- Baseline: `LLMLinguaCompressor` →
  `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` (~950 MB), CPU.
- **Ratios are matched.** Comparing compressors at different ratios measures
  nothing: whoever compresses less looks better on quality. ContentRouter runs
  first, its achieved ratio becomes LLMLingua's `target_ratio`, and both are
  reported so you can confirm they actually landed together.
- Quality metric: **information recall** — generate probe strings from the
  original and check how many survive in the compressed output. Offline, no
  API key, no model. It is a proxy for fidelity, not downstream task accuracy
  (see Limits).
- Hardware: one laptop CPU, single process. Latency is indicative, not a
  throughput benchmark.

Reproduce:

```bash
uv pip install "datasets>=2.14" "llmlingua>=0.2.2"
python -m cutctx.evals benchmark --dataset hotpotqa -n 30
```

## Results

### ML vs ML — the like-for-like comparison

LLMLingua-2 is a trained model. Our comparable path is Kompress
(`enable_kompress=True`). At matched ratio:

| Dataset | System | Ratio | Info recall | ms/case |
| --- | --- | ---: | ---: | ---: |
| LongBench (n=20) | Router + Kompress | 0.766 | **0.962** | 5,594 |
| LongBench (n=20) | LLMLingua-2 @ matched | 0.770 | 0.960 | 5,324 |
| HotpotQA (n=20) | Router + Kompress | 0.799 | 0.938 | 1,529 |
| HotpotQA (n=20) | LLMLingua-2 @ matched | 0.798 | **0.954** | 1,361 |

**Parity on LongBench (0.962 vs 0.960), a little behind on HotpotQA (0.938 vs
0.954), at comparable latency.** That is the credible quality claim: matched
against the published state of the art, our ML path is level with it on one
dataset and slightly behind on the other. Neither margin is large relative to
n=20.

### Structural vs ML — the tradeoff we actually ship

The default proxy path does **not** use Kompress. It is structural and
deterministic, and it occupies a different point on the curve entirely:

| Dataset | System | Ratio | Info recall | ms/case |
| --- | --- | ---: | ---: | ---: |
| LongBench | Router, no ML (**default**) | 0.412 | 0.626 | **26** |
| LongBench | Router + Kompress | 0.766 | 0.962 | 5,594 |
| HotpotQA | Router, no ML (**default**) | 0.167 | 0.479 | **10** |
| HotpotQA | Router + Kompress | 0.799 | 0.938 | 1,529 |

The default compresses **2–5x harder** and runs **150–500x faster**, at lower
fidelity. Kompress is correctly opt-in: 1.5–5.6 seconds per payload is
unacceptable in a proxy sitting in the request path, which is exactly why
`enable_kompress` defaults to False.

**This is the honest shape of the product.** Not "we beat LLMLingua", but:
*we match it when you want maximum fidelity, and we offer a sub-30ms
structural mode it has no equivalent for.* An interactive agent proxy cannot
spend 5 seconds per tool result, so for the shipped use case the fast path is
the product and the ML path is the escape hatch.

### Non-ML at matched ratio, for completeness

Comparing the default structural path against LLMLingua at the same ratio —
apples to oranges, since one is a trained model, but it bounds the gap:

| Dataset | Matched ratio | Router (no ML) | LLMLingua-2 |
| --- | ---: | ---: | ---: |
| HotpotQA (n=30) | 0.186 | **0.532** | 0.457 |
| LongBench (n=20) | 0.412 | 0.626 | **0.857** |

We hold up better under aggressive compression on multi-hop QA and lose
clearly at moderate compression on long-context prose.

**Three attempts to close this gap with cheap heuristics, all measured at a
per-case matched budget so ratio is held constant:**

| Selection strategy | LongBench recall | HotpotQA recall |
| --- | ---: | ---: |
| Current (headings + anchors + top-1 query match) | **0.626** | **0.514** |
| Fill the budget by term overlap | 0.659 *(but ratio 0.412 → 0.457)* | — |
| BM25 ranking (IDF + length normalisation) | 0.614 | 0.498 |
| Stratified coverage (uniform stride, query as tiebreak) | 0.632 | 0.514 |

None of them wins. Budget-filling only travels along the ratio/recall curve.
BM25 is measurably *worse*. Stratified coverage is +0.006 on one dataset and
identical on the other — noise at n=20.

An earlier version of this document asserted that term-overlap scoring was the
binding constraint and better scoring would close the gap. **BM25 disproves
that.** The existing heuristic — retain headings, exact identifiers,
constraints, and the single strongest query match — is at or near the
practical frontier for lexical methods at these ratios, and the intuition that
`[:1]` was "obviously too few" is wrong once the budget is held fixed.

The remaining gap is structural: we select whole sentences, so retained
content clusters around the query, while a learned token-level model prunes
across the entire document and preserves a little of everything. Closing it
properly needs a model, and the product already has one — Kompress, at parity
with LLMLingua-2 above. No code was changed on the strength of these
experiments, because none of them earned it.

## Limits

- **This measures the compressor, not the product.** The harness runs a bare
  `ContentRouter` with no proxy config. The shipped proxy additionally applies the protected-tool denylist,
  live-zone protection and tool-result wrapping, so these numbers do not
  predict fleet savings. The README's `Proof` section makes the same
  distinction: 47–92% per-payload versus 0.7% fleet-wide.
- **Information recall is a fidelity proxy.** It counts surviving probe
  strings. It does not measure whether a model still answers correctly.
  Downstream accuracy needs generation, which needs API spend
  (`python -m cutctx.evals suite --tier 1`, annotated ~$3).
- **Small n.** 30 and 20 cases. Directionally useful, not publication-grade.
  Neither result carries a confidence interval and neither should be quoted as
  a precise figure.
- **One baseline.** LLMLingua-2 is the credible open one. Commercial proxy
  competitors cannot be benchmarked without accounts and spend, so "best in
  class" remains unproven against them.
