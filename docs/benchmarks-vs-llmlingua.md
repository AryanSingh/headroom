# Head-to-head: ContentRouter vs LLMLingua-2

Microsoft's [LLMLingua-2](https://github.com/microsoft/LLMLingua) is the
published baseline for prompt compression, so it is the honest thing to
measure against. This page reports what happened.

**Summary:** at matched compression ratio our default structural path clearly
beats trivial baselines but loses to LLMLingua-2, decisively on long context.
Our ML path scores highest overall but is not ratio-matched in the current
run, so it is not ranked here. The default's real advantage is speed:
150–500x faster, which LLMLingua has no equivalent for.

> **An earlier revision of this page reported the opposite on HotpotQA
> (0.532 vs 0.457 in our favour). That number was wrong** — it was produced
> before a bias in the quality metric was found and fixed. See
> "The metric was broken" below.

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

n=50 per dataset, per-case matched token budgets, unbiased probe sampling.
Trivial baselines are included as a floor: a compressor that cannot beat
"keep the first N tokens" is not earning its complexity.

### HotpotQA

| System | Ratio | Info recall | Stdev | ms/case |
| --- | ---: | ---: | ---: | ---: |
| router + kompress *(not ratio-matched)* | 0.797 | 0.875 | 0.101 | 1,159 |
| LLMLingua-2 | 0.169 | **0.348** | 0.265 | 1,324 |
| **Router (default)** | 0.167 | **0.332** | 0.160 | **8** |
| tail truncation | 0.165 | 0.273 | 0.182 | 0 |
| head truncation | 0.165 | 0.241 | 0.146 | 0 |
| random sentences | 0.165 | 0.218 | 0.202 | 0 |

### LongBench

| System | Ratio | Info recall | Stdev | ms/case |
| --- | ---: | ---: | ---: | ---: |
| router + kompress *(not ratio-matched)* | 0.765 | 0.938 | 0.088 | 3,726 |
| LLMLingua-2 | 0.398 | **0.757** | 0.150 | 4,168 |
| tail truncation | 0.402 | 0.632 | 0.209 | 2 |
| **Router (default)** | 0.403 | 0.627 | 0.168 | **14** |
| random sentences | 0.403 | 0.593 | 0.208 | 2 |
| head truncation | 0.402 | 0.510 | 0.175 | 2 |

**Reading it straight:**

- The default path **beats every trivial baseline on HotpotQA** (0.332 vs
  0.273 / 0.241 / 0.218), so the routing and query-aware selection are doing
  real work.
- On LongBench it is **statistically indistinguishable from tail truncation**
  (0.627 vs 0.632, stdev ~0.2 at n=50). On long-context prose the default is
  not adding much over a naive heuristic.
- **LLMLingua-2 wins at matched ratio on both**, narrowly on HotpotQA
  (0.348 vs 0.332) and clearly on LongBench (0.757 vs 0.627).
- The `router + kompress` row sits at a much gentler ratio (0.77–0.80) because
  Kompress picks its own aggressiveness and the harness cannot force a budget
  on it. Its high recall is therefore **not comparable** to the rows above.
  An earlier matched-ratio run put Kompress at 0.962 against LLMLingua's 0.960
  on LongBench; that comparison was run on the biased metric and has not been
  repeated.
- Speed remains ours: **8–14 ms versus 1.3–4.2 s**, two to three orders of
  magnitude.

## The metric was broken

`generate_retrieval_probes` selected probes with `matches[:2]` per pattern.
`re.findall` returns matches in document order, so probes came almost entirely
from the opening of the text. Measured across 20 HotpotQA contexts:

| | before | after |
| --- | ---: | ---: |
| Mean probe position (0.5 = unbiased) | 0.147 | 0.455 |
| Share in first 25% of document | 82.1% | 34.4% |
| Share in last 25% of document | 2.8% | 24.4% |

`information_recall` was therefore largely a test of *"did you keep the
beginning"*. Under the biased version, head truncation scored **0.659** on
HotpotQA and appeared to beat our router (0.487) — an artifact. With probes
spread across the document head drops to **0.241**, last of all systems, and
the ordering above is the real one.

This metric feeds `benchmark_report.py` and the release evidence, so the bias
flattered whichever system happened to preserve leading text. Probe selection
now strides evenly across document order; a regression test asserts probes are
not confined to the first half.

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
- **Small n.** 50 cases per dataset, with per-system stdev reported. Several
  gaps here are smaller than one standard deviation — the LongBench
  router-vs-tail difference (0.627 vs 0.632, stdev ~0.2) is noise, and the
  HotpotQA router-vs-LLMLingua gap (0.332 vs 0.348) is not far off it. Treat
  ranking within a few points as unresolved.
- **Kompress is not ratio-matched.** It selects its own aggressiveness and the
  harness cannot impose a budget on it, so its row is reported but not ranked.
- **Baselines.** LLMLingua-2 plus head/tail/random controls. Commercial proxy
  competitors cannot be benchmarked without accounts and spend, so "best in
  class" remains unproven against them.

Reproduce:

```bash
python scripts/compression_benchmark.py --all -n 50
```
