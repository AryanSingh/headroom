# Cutctx Performance Analysis

**Generated:** 2026-07-10
**Scope:** Compression pipeline, Rust proxy, cache efficiency, streaming, benchmarks, concurrency, memory
**Rating:** 🟡 **Good with targeted gaps**

---

## Executive Summary

Cutctx demonstrates strong compression performance with well-engineered concurrency controls and a mature Rust proxy architecture. The dual-stack design (Python proxy + Rust binary) creates a clear performance boundary: the Rust binary is production-ready for passthrough + live-zone compression, while the Python proxy adds significant latency overhead for features that haven't migrated to Rust. The most impactful gaps are in streaming latency measurement, GIL contention on the Python→Rust bridge, and the absence of end-to-end throughput benchmarks.

---

## 1. Compression Pipeline Throughput

### Architecture

The compression pipeline is a two-tier system:

- **Python path** (`cutctx/compress.py` → `cutctx/transforms/pipeline.py`): `TransformPipeline` runs `CacheAligner → ContentRouter` (SmartCrusher for JSON, CodeCompressor for code, Kompress for text). Invoked via `pipeline.apply()` on a dedicated `ThreadPoolExecutor` with bounded concurrency.
- **Rust path** (`crates/cutctx-proxy/src/compression/live_zone_anthropic.rs`): In-process PyO3 calls for SmartCrusher, LogCompressor, SearchCompressor, DiffCompressor. Byte-range surgery rewrites only the live zone; unmodified bytes round-trip byte-equal.

### Buffering vs Streaming

**Critical finding: Compression requires full body buffering.**

- **Rust proxy** (`proxy.rs:764`): `to_bytes(req.into_body(), max)` buffers the entire request body before dispatching to the live-zone compressor. This is by design — the live-zone architecture needs to see all messages to identify the frozen prefix vs the compressible tail. The `compression_max_body_bytes` config caps this.
- **Python proxy** (`server.py:740`): Same pattern — `pipeline.apply()` receives the full message list, not a stream.
- **Streaming response path** (`handlers/streaming.py`): The proxy does NOT compress mid-stream. SSE bytes flow to the client immediately via `StreamingResponse(generate())`. Compression happens only on the **request** side (pre-upstream). The response path is pure passthrough with a side-channel state machine for telemetry (Rust: `proxy.rs:1126-1133`; Python: `streaming.py:2173` mirrors for CCR feedback).

### Latency Overhead

- **SmartCrusher** (per `benchmark_results.md`): **0.22 ms** average latency — sub-millisecond, excellent.
- **ContentRouter**: **65.61 ms** average latency — includes model routing decision + dispatch. This is the slow path.
- **Python `pipeline.apply()`**: Runs on a dedicated `ThreadPoolExecutor` (`server.py:740`) sized `min(32, cpu_count * 4)`. The `compress_with_timeout` method (`server.py:1220-1309`) wraps this with cancel-aware metrics and a configurable timeout.
- **Leaked threads**: When `asyncio.wait_for` times out, the underlying CPython thread cannot be preempted. The `_compression_leaked_threads` gauge tracks this (`server.py:759`).

### Per-Request Latency Budget

The cost-benefit analysis in `bench_latency.py` models this as: `net_benefit = (tokens_saved × ms_per_token) - compression_ms`. For a 50K-token RAG context with 50% compression on Sonnet (0.3ms/token prefill), the math works out to: `(25K × 0.3ms) - compression_latency`. Even at 100ms compression overhead, the net benefit is ~7.4 seconds of saved prefill time.

---

## 2. Rust Proxy Status

### What's Active (Phase B+)

The Rust proxy (`crates/cutctx-proxy/`) is **fully operational** for:

| Provider | Path | Status | Module |
|----------|------|--------|--------|
| Anthropic | `/v1/messages` | ✅ Live-zone compression | `compression/live_zone_anthropic.rs` |
| OpenAI Chat | `/v1/chat/completions` | ✅ Live-zone compression | `compression/live_zone_openai.rs` |
| OpenAI Responses | `/v1/responses` | ✅ Live-zone compression | `compression/live_zone_responses.rs` |
| Gemini | `POST /v1beta/...` | 🔴 Passthrough | Not yet wired |

### Compression Dispatch Flow

1. `proxy.rs:764`: Buffer body via `to_bytes()`
2. `proxy.rs:795`: Classify endpoint via `classify_compressible_path()`
3. `proxy.rs:813`: Parse JSON once (shared for volatile detector + drift detector + compressor)
4. `proxy.rs:850-908`: Dispatch to provider-specific compressor
5. `proxy.rs:929-1016`: Handle `Outcome::Compressed` / `NoCompression` / `Passthrough`
6. `proxy.rs:1018-1034`: Cache-safety alarm (byte-delta check on passthrough arms)
7. `proxy.rs:1036-1068`: PR-E4: OpenAI `prompt_cache_key` auto-injection (PAYG only)

### What Remains for Phase B Completion

- **Gemini compression**: No `live_zone_gemini.rs` exists. Gemini requests pass through untouched.
- **Bedrock/Vertex compression**: Bedrock requests use a different wire shape (`raw_predict.rs`) and the compression module explicitly skips drift detection for them (`proxy.rs:808-812`).
- **CCR store on Rust side**: CCR retrieval-marker injection is wired in the Rust proxy via `compress_anthropic_request_with_ccr` (`proxy.rs:863`), gated on `tier.allows_ccr()`.

---

## 3. Cache Efficiency

### Semantic Cache (`cutctx/proxy/semantic_cache.py`)

**Type:** Exact-match response cache with LRU eviction, keyed by SHA-256 of normalized `{model, messages}`.

**Normalization** strips volatile elements:
- System reminder blocks (`_SYSTEM_REMINDER_BLOCK_RE`)
- Per-call cache breakpoints (`cache_control`)
- Volatile metadata keys (timestamps, request IDs, nonces)
- Trailing whitespace

**Performance characteristics:**
- **Lock**: Single `asyncio.Lock` — serializes all cache operations. Under high concurrency, this is a potential bottleneck. `stats()` also acquires the lock, meaning dashboard requests compete with request-path cache lookups.
- **Eviction**: LRU via `OrderedDict`. No size-based memory budget — only entry count (`max_entries=1000`).
- **Hit rate**: Depends heavily on workload. The name "semantic" is misleading — it's content-hash matching, not embedding similarity. For agent workloads with dynamic timestamps/UUIDs in messages, hit rates will be low. The normalization helps but doesn't eliminate all variance.

**Key limitation:** This is NOT a prefix cache. It caches complete responses. For multi-turn conversations, only exact-repetition of the full message list hits. The provider-native prefix cache (Anthropic/OpenAI) is far more impactful for conversation workloads.

### Prefix Tracker (`cutctx/cache/prefix_tracker.py`)

**Purpose:** Tracks how many tokens the provider cached between turns so the compression pipeline can freeze that prefix and avoid cache invalidation.

**Mechanism:**
- After each response, records `cache_read_input_tokens` from the provider's usage response
- On the next turn, freezes that many messages so the transform pipeline skips them entirely
- Session-scoped (keyed by `caller_fp:session_id`)

**Economics modeling** (`prefix_tracker.py:36-49`):
- Anthropic: 90% read discount, 25% write penalty
- OpenAI: 50% read discount

**Cache-bust detection** (`anthropic.py:3046-3055`): When `expected_cached > actual_read`, the proxy logs a `CACHE-BUST` event with token counts. This is critical for operator visibility.

**Does it work in practice?** The prefix tracker is architecturally sound but its effectiveness depends on the client maintaining a stable prefix. Claude Code already manages its own prefix cache with 4 `cache_control` breakpoints. The tracker's value is in preventing Cutctx's compression from accidentally invalidating that prefix — it's a **defensive** mechanism, not an additive cache.

---

## 4. Streaming

### SSE Streaming Path

**Python proxy** (`handlers/streaming.py`):
- Request compression happens BEFORE streaming starts (full body buffer → compress → forward)
- Response streaming is pure passthrough: `StreamingResponse(generate())` yields chunks as they arrive
- A side-channel `full_sse_bytes` bytearray (`streaming.py:2173`) mirrors the stream for post-hoc CCR feedback, but does NOT buffer chunks back to the client
- `_absorb()` parses usage frames from SSE chunks incrementally (`streaming.py:2175-2185`)
- Late-flush on stream truncation (`streaming.py:2215-2218`)

**Rust proxy** (`proxy.rs:1122-1153`):
- SSE detection via `is_sse_response()` headers check
- `SseStreamKind` classification: Anthropic, OpenAiChat, OpenAiResponses, or None
- OpenAiResponses state machine gated by `enable_responses_streaming` config
- State machine runs in a spawned task via `tokio::sync::mpsc` — bytes flow to client unchanged while telemetry is collected in parallel (`proxy.rs:1126-1127`)
- Per-session cache-hit-rate computed from Anthropic stream state (`proxy.rs:1501-1526`)

### Time-to-First-Token (TTFT) Overhead

**Gap:** `ttfb_ms` is hardcoded to `0` in the Python streaming path (`streaming.py:2526`). The Rust proxy doesn't explicitly measure TTFB either. The actual overhead per request is:

1. Body buffering: O(body_size) — dominated by network I/O
2. JSON parse + compression: sub-ms (SmartCrusher) to ~65ms (ContentRouter)
3. Forward to upstream: network latency
4. First SSE chunk arrives: this is the real TTFT, but it's upstream-dependent

**Estimated TTFT overhead from Cutctx:** ~1-65ms depending on compressor, plus body buffering time. For typical agent payloads (10-50KB), body buffering is <10ms on a fast connection.

### WebSocket Path

The Rust proxy has a `ws_handler` (`proxy.rs:28` import, routed at `proxy.rs:41`). WebSocket traffic passes through without compression — the live-zone architecture only applies to HTTP POST bodies.

---

## 5. Benchmark Results

### Compression Ratio (`benchmark_results.md`)

| Compressor | Ratio | F1 | Info Recall | Latency |
|------------|-------|-----|-------------|---------|
| SmartCrusher | 79.1% | 1.000 | 1.000 | 0.22ms |
| ContentRouter | 78.2% | 0.999 | 1.000 | 65.61ms |
| Kompress | 78.8% | 0.999 | 1.000 | — |
| Diff | 100.0% | 1.000 | 1.000 | — |
| Log | 88.3% | 0.882 | 0.875 | — |
| Search | 79.3% | 0.862 | 0.817 | — |

**Key observations:**
- SmartCrusher achieves **0.22ms** — this is the fast path and should be the default for JSON payloads
- ContentRouter at **65.61ms** includes model routing overhead — this is 300× slower than SmartCrusher
- F1 > 0.99 for top compressors — quality is excellent
- Log and Search compressors have lower recall (0.875, 0.817) — acceptable for their use case but worth noting

### Latency Benchmark Framework (`bench_latency.py`)

The framework is comprehensive (1278 lines) covering JSON, code, text, logs, agentic, and RAG scenarios with:
- Per-transform profiling (`ProfilingPipeline`)
- Cost-benefit analysis against reference models
- P50/P95/P99 latency percentiles

**Missing:** No published latency benchmark results in the repo. The framework exists but no `LATENCY_BENCHMARKS.md` output is committed.

### Proxy Mode Benchmark (`proxy_mode_benchmark.py`)

Compares baseline / token mode / cache mode locally. Measures compression %, cache hit %, and uncached tokens across simulated turns. Results are printed to terminal only — no persistent output.

---

## 6. Concurrency

### Python Proxy (FastAPI + Uvicorn)

**Async patterns:**
- FastAPI with async handlers throughout
- Compression offloaded to `ThreadPoolExecutor` (`server.py:740`) — critical for GIL avoidance
- `compress_with_timeout` (`server.py:1220-1309`) provides cancel-aware execution with leaked-thread tracking
- Separate `ThreadPoolExecutor` instances for OpenAI Responses units (`handlers/openai/utils.py:102-106`)

**GIL impact on Rust bridge:**
- PyO3 calls release the GIL via `py.allow_threads()` (noted in `server.py:1230`)
- The `cutctx-py` crate (`crates/cutctx-py/src/lib.rs`) wraps Rust compressors (SmartCrusher, LogCompressor, etc.) as PyO3 classes
- CPU-bound Rust work runs GIL-free; only the Python→Rust call overhead and result marshaling hold the GIL
- The dedicated compression executor prevents compression bursts from starving other `asyncio.to_thread` callers

**Potential bottleneck:** The single `asyncio.Lock` in `SemanticCache` serializes all cache operations. Under high concurrency with frequent cache checks, this could become a contention point.

### Rust Proxy (Tokio + Axum)

- `#[tokio::main]` async runtime (`main.rs:15`)
- Axum framework with `Router` and handler functions
- SSE state machine runs in spawned tasks via `tokio::sync::mpsc` (`proxy.rs:1126-1127`)
- `reqwest` client for upstream HTTP — connection pooling built in
- Graceful shutdown with configurable drain timeout (`main.rs:184-194`)

**Excellent patterns:**
- Body buffering with `to_bytes()` + `max` limit prevents OOM on oversized payloads
- Cache-safety alarm (`proxy.rs:1018-1034`) catches accidental byte mutations in passthrough arms
- Rate limit header extraction from upstream responses (`proxy.rs:1157-1164`)

---

## 7. Memory

### Cache Memory

- **SemanticCache**: Stores full response bodies in `OrderedDict`. `max_entries=1000` bounds entry count but not memory. A response of 100KB × 1000 entries = ~100MB worst case. No `budget_bytes` enforcement (`semantic_cache.py:241` shows `budget_bytes=None`).
- **CompressionCache**: Per-session, stored in a dict keyed by session ID. Bounded by session count.
- **PrefixTracker**: SQLite-backed persistence (`prefix_tracker.py:24`) with in-memory `OrderedDict` cache. Auto-cleanup of expired trackers (`_maybe_cleanup`).

### CCR (Compressed Context Retrieval) Memory

- **Rust side**: `CcrStore` trait with InMemory and SQLite backends (`main.rs:217-286`). InMemory bounded by `DEFAULT_CAPACITY`. SQLite on disk.
- **Python side**: `CompressionStore` with `_backend.clear()` and `_retrieval_events.clear()` patterns.

### Memory Leak Indicators

**No critical leaks detected.** The codebase shows consistent cleanup patterns:
- `shared_context.py`: `.clear()` on `_entries`, `_agents`, `_cache`
- `ccr/context_tracker.py`: `.clear()` on `_contexts`, `_turn_order`
- `telemetry/collector.py`: `.clear()` on `_events`, `_tool_stats`, `_retrieval_stats`
- `compression_feedback.py`: `.clear()` on `_tool_patterns`

**Potential concern:** `shared_context.py:670` uses `del self._cache[lru_key]` for LRU eviction — standard pattern but worth monitoring under sustained load.

---

## Critical Issues

| Severity | Issue | Location | Impact |
|----------|-------|----------|--------|
| 🟡 Medium | `SemanticCache` single `asyncio.Lock` serializes all operations | `semantic_cache.py:126` | Cache contention under high concurrency |
| 🟡 Medium | `ttfb_ms` hardcoded to 0 — no actual TTFT measurement | `streaming.py:2526` | Cannot measure streaming latency overhead |
| 🟡 Medium | ContentRouter latency (65ms) is 300× SmartCrusher (0.22ms) | `benchmark_results.md` | Model routing decision dominates compression time |
| 🟡 Medium | No Gemini compression in Rust proxy | `proxy.rs:808-812` | Gemini requests bypass all compression |
| 🟢 Low | `SemanticCache` has no memory budget (`budget_bytes=None`) | `semantic_cache.py:241` | Large responses could cause memory pressure |
| 🟢 Low | No published latency benchmark results | `benchmarks/` | Performance regression detection relies on ad-hoc runs |
| 🟢 Low | `SemanticCache.get()` is exact-match, not semantic similarity | `semantic_cache.py:134-147` | Misleading name; low hit rates for dynamic workloads |

---

## Quick Wins

1. **Measure actual TTFT overhead**: Instrument the streaming path to record time from request receipt to first upstream byte forwarded. Currently `ttfb_ms=0` hides real latency.

2. **Add `max_size_bytes` to SemanticCache**: Cap total memory, not just entry count. Current `budget_bytes=None` means unbounded memory growth.

3. **Publish latency benchmark results**: The `bench_latency.py` framework is excellent but results aren't committed. Add a CI step that runs it and commits `LATENCY_BENCHMARKS.md`.

4. **Profile ContentRouter decision overhead**: 65ms for model routing is disproportionate. Consider caching the routing decision or using a cheaper classifier for common content types.

5. **Add `asyncio.Lock` contention metrics**: Wrap `SemanticCache._lock` acquisition with a timing gauge to detect contention under load.

6. **Wire Gemini compression in Rust proxy**: Add `live_zone_gemini.rs` — Gemini is the last major provider without compression.

---

## Detailed File References

| File | Lines | What to Look At |
|------|-------|-----------------|
| `crates/cutctx-proxy/src/proxy.rs` | 764, 850-908, 929-1016, 1122-1153 | Body buffering, compression dispatch, SSE tee |
| `crates/cutctx-proxy/src/compression/live_zone_anthropic.rs` | 1-40 | Live-zone architecture docstring |
| `crates/cutctx-proxy/src/compression/mod.rs` | 24, 57-88 | Provider matrix and path classification |
| `cutctx/proxy/server.py` | 740-760, 1220-1309 | Compression executor, cancel-aware timeout |
| `cutctx/proxy/handlers/streaming.py` | 2145-2536 | SSE streaming with side-channel telemetry |
| `cutctx/proxy/semantic_cache.py` | 119-165 | Cache key computation and normalization |
| `cutctx/cache/prefix_tracker.py` | 1-15, 36-49 | Prefix cache economics model |
| `cutctx/proxy/handlers/anthropic.py` | 3046-3055 | Cache-bust detection |
| `cutctx-py/src/lib.rs` | 1-14 | PyO3 bridge architecture |
| `benchmarks/bench_latency.py` | 627-680 | Profiling pipeline instrumentation |
| `benchmark_results.md` | 1-26 | Compression ratio and F1 scores |

---

## Benchmark Comparison: Expected vs Actual

| Metric | Expected | Actual | Source |
|--------|----------|--------|--------|
| SmartCrusher compression ratio | 70-85% | **79.1%** | `benchmark_results.md` |
| SmartCrusher latency | <1ms | **0.22ms** ✅ | `benchmark_results.md` |
| ContentRouter F1 | >0.95 | **0.999** ✅ | `benchmark_results.md` |
| ContentRouter latency | <50ms | **65.61ms** ⚠️ | `benchmark_results.md` |
| Compression executor size | CPU-bound | `min(32, cpu*4)` ✅ | `server.py:736` |
| Leaked thread tracking | Expected | Implemented ✅ | `server.py:1296-1297` |
| TTFB measurement | Expected | **Missing** ❌ | `streaming.py:2526` |
| Gemini compression | Expected | **Missing** ❌ | `proxy.rs:808-812` |

---

## Final Assessment

**Strengths:**
- SmartCrusher sub-millisecond latency is excellent
- Live-zone architecture preserves cache safety with byte-equal round-trip guarantees
- Dedicated compression executor with leaked-thread tracking is production-grade
- Cache-safety alarm catches accidental byte mutations in passthrough arms
- PyO3 bridge releases GIL for CPU-bound Rust work

**Gaps:**
- No end-to-end throughput benchmarks (requests/sec under load)
- TTFT not measured despite being the most user-visible latency metric
- Semantic cache is exact-match only — limited value for dynamic agent workloads
- ContentRouter model routing overhead (65ms) is disproportionate
- Gemini/Bedrock compression not yet in Rust proxy

**Bottom line:** The compression engine itself is fast and correct. The main performance risks are in the orchestration layer (Python proxy overhead, cache lock contention) and measurement gaps (TTFT, throughput). The Rust proxy is well-positioned to absorb more of the Python proxy's responsibilities for further gains.
