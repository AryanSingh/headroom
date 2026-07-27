# Head-to-head: ContentRouter vs LLMLingua-2

Microsoft's [LLMLingua-2](https://github.com/microsoft/LLMLingua) is the
published baseline for prompt compression, so it is the honest thing to
measure against. This page reports what happened. The result is mixed, and the
mixed part is the useful part.

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

At matched compression ratio:

| Dataset | Matched ratio | ContentRouter recall | LLMLingua-2 recall | ContentRouter | LLMLingua-2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| HotpotQA (n=30) | 0.186 | **0.532** | 0.457 | **14 ms** | 1,728 ms |
| LongBench (n=20) | 0.412 | 0.626 | **0.857** | **27 ms** | 5,498 ms |

Unmatched, for reference — this is what each system does when left to its own
default aggressiveness on HotpotQA (n=30):

| System | Ratio | Tokens saved | F1 | Info recall | ms/case |
| --- | ---: | ---: | ---: | ---: | ---: |
| ContentRouter | 0.173 | 39,185 | 0.271 | 0.532 | 23 |
| LLMLingua-2 | 0.540 | 21,841 | 0.642 | 0.843 | 7,021 |
| Raw passthrough | 1.000 | 0 | 1.000 | 1.000 | 0 |

## Reading this honestly

**Speed is a decisive, consistent win — roughly 100–200x.** ContentRouter is
structural and deterministic; LLMLingua-2 runs a 950 MB transformer per
payload. On an interactive proxy sitting in the request path, 27 ms versus
5.5 s is not a tuning detail, it is the difference between viable and not.

**Quality at matched ratio splits by workload.** We retain more on HotpotQA at
an aggressive 0.186; LLMLingua-2 retains substantially more on LongBench at a
moderate 0.412. The plausible reading is that our structural compressors
either fire hard or barely fire, while a learned token-level model degrades
more gracefully in the middle of the range. That is a real gap, not a
measurement artifact, and it points at where the compressors could improve.

**The unmatched table is the trap.** Read alone it says LLMLingua wins on
quality and loses on savings. Both systems are simply sitting at different
points on the same tradeoff curve. Any competitive claim drawn from unmatched
ratios — in either direction — is not worth making.

## Limits

- **This measures the compressor, not the product.** The harness runs a bare
  `ContentRouter` (`enable_kompress=False`, passthrough fallback, no proxy
  config). The shipped proxy additionally applies the protected-tool denylist,
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
