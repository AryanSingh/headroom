# First load test — `/v1/compress`

**Date:** 2026-07-26
**Why:** every prior audit recorded performance as unmeasured. The most recent
scored it **4/10** with the note *"Never load-tested by anyone"*, and the only
figure in circulation was an internal tokbench claim of *"+0.9s per request
(32% overhead)"* with no throughput or tail-latency data behind it.

**Harness:** [`scripts/loadtest_compress.py`](../scripts/loadtest_compress.py)
(committed, repeatable).

---

## Setup

| | |
|---|---|
| Endpoint | `POST /v1/compress` on a local proxy (`--port 18899`) |
| Payload | 1,200-line structured log, **86.7 kB**, ~18% ERROR lines, one FATAL at the midpoint |
| Env | `CUTCTX_SKIP_UPSTREAM_CHECK=1`, `CUTCTX_ACCURACY_GUARD=off` |
| Host | macOS (Apple Silicon), otherwise idle |
| Warm-up | one discarded request per run, so tokenizer/model load does not skew results |

`/v1/compress` exercises the compression path without an LLM provider, so these
numbers isolate **Cutctx's own cost** — they do not include upstream model time.

## Results

| Concurrency | Throughput | p50 | p90 | p99 | Errors | FATAL preserved |
|---:|---:|---:|---:|---:|---:|---:|
| 8 | 335 req/s | 13 ms | 27 ms | 154 ms | 0/120 | **120/120** |
| **16** | **603 req/s** | 24 ms | 33 ms | 60 ms | 0/200 | **200/200** |
| 32 | 339 req/s | 65 ms | 175 ms | 413 ms | 0/200 | **200/200** |
| 64 | 205 req/s | 175 ms | 619 ms | 751 ms | 0/200 | **200/200** |

**720 requests total, zero errors at every level.**

## What this tells us

**Throughput peaks at concurrency ~16 (~600 req/s) and degrades past it.** That
is textbook saturation: beyond the knee, added concurrency buys queueing rather
than work. p99 grows 12× between 16 and 64 while throughput *falls* by two
thirds.

**Practical guidance:** size deployments around ~16 in-flight compressions per
instance and scale horizontally beyond that. Note `k8s/deployment.yaml` runs a
single replica by default because the bundled PVC is ReadWriteOnce — so
horizontal scale needs an RWX volume or an external state backend first.

**Compression cost is milliseconds, not seconds.** 13–24 ms p50 on an 86.7 kB
payload. This does **not** contradict the tokbench "+0.9s per request" figure —
that measured a full request including the upstream model call. It does mean the
compression step itself is not the source of that latency, and the two numbers
should stop being conflated.

**Fidelity holds under load.** The FATAL line survived in **720/720** responses.
Worth stating because compression correctness under concurrency was previously
untested, and the severity-retention guarantee is new (FATAL/CRITICAL are now a
distinct log level ranked above ERROR).

## Reproduce

```bash
CUTCTX_SKIP_UPSTREAM_CHECK=1 python -m cutctx.cli.main proxy --port 18899 &
python scripts/loadtest_compress.py --port 18899 --concurrency 16 --requests 200
```

## Limits of this test — do not over-read it

- **Single instance, single host, loopback.** No network latency, no load
  balancer, no multi-replica behaviour.
- **One payload shape.** Structured logs only. JSON tool output, code, and
  prose take different router paths with different costs.
- **No sustained-duration run.** Minutes-long soak testing would be needed to
  surface memory growth, CCR store growth, or GC effects.
- **`/v1/compress` only.** The full proxy path (`/v1/messages`) adds upstream
  I/O, streaming, and cache-alignment work that this does not measure.
- **Guard disabled.** Run with `CUTCTX_ACCURACY_GUARD=strict` to measure the
  guard's overhead separately; it is a single linear pass but unmeasured here.

Performance should no longer be scored as "never measured", but neither is this
a production capacity model.
