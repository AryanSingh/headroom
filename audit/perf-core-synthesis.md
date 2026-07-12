# Performance & Core Capabilities — Synthesis

**Date:** 2026-07-10
**Method:** 4-phase parallel deep-dive (compression pipeline, streaming, caching/perf infra, core capabilities)
**Previous baseline:** `audit/performance-analysis.md` (July 10, 2026)
**Source audits:**
- Phase 1 → `audit/perf-core-compression.md` (321 lines)
- Phase 2 → `audit/perf-core-streaming.md` (232 lines)
- Phase 3 → `audit/perf-core-caching.md` (279 lines)
- Phase 4 → `audit/perf-core-capabilities.md` (461 lines)

---

## Executive Summary

Cutctx has a mature compression engine at its core (SmartCrusher at 0.22ms, live-zone architecture, 12 specialized formats) but carries **significant performance debt from dual-runtime duplication** and a **widening capability gap in the Rust proxy**. The product has 42 production capabilities and 31 in beta across 12+ providers, but the Rust proxy lags behind the Python proxy in nearly every dimension — compression transform coverage, TTFB measurement, caching, and provider support.

**Key finding:** The dual-runtime architecture is the single largest source of both performance overhead and capability risk. Every request passes through both runtimes — Rust compresses, Python does everything else. Python has the full feature set but carries 69 bare `except Exception` clauses, a 7,903-line monolith, and triple-`deep_copy` overhead. Rust has better performance characteristics but lacks CodeCompressor, DiffCompressor reliability, TTFB measurement, Gemini compression, CacheAligner transform, and model routing. As long as Python owns non-compression features, the Rust proxy cannot be a standalone replacement, and Python's brittleness (69 bare excepts) affects every request regardless of Rust proxy speed.

**Performance score:** 62/100 (core path throughput: 75, full coverage: 55)
**Capability maturity:** 44% Production / 33% Beta / 8% Experimental / 5% Stubbed / 10% Gaps

---

## Cross-Phase Findings

### 🔴 Critical (5)

| ID | Phase | Finding | Impact | Effort |
|----|-------|---------|--------|--------|
| S-1 | P1 | **CodeCompressor not ported to Rust** — Rust live-zone dispatcher skips `SourceCode` blocks entirely. Code passes through uncompressed in the Rust proxy path. | No AST-based code compression for Rust proxy users. | 2w |
| S-2 | P1 | **Triple `deep_copy_messages` overhead** — 2-3 full message list copies per request (`pipeline.py:301`, `cache_aligner.py:282`, `smart_crusher.py:903`). For 100K+ token conversations, adds 15-45ms of waste. | Latency overhead scales linearly with context size. | 3d |
| S-3 | P2 | **Rust proxy has zero TTFB measurement** — Python measures accurately at `streaming.py:1613/1967` via `(time.time() - start_time) * 1000`. Rust has nothing. Only total `latency_ms` at `proxy.rs:1286`. | Cannot detect streaming latency regressions on the Rust path. | 1d |
| S-4 | P3 | **`PrometheusMetrics.export()` locks entire hot path** — Holds its `asyncio.Lock` during full text generation. Every `/metrics` scrape (typically every 15s) blocks every `record_request()` call on the request path. | Under Prometheus scrape frequency, burst of blocking on request path. | 1d |
| S-5 | P4 | **No SOC 2 or SAML SSO** — Enterprise procurement blockers. 10% of capability inventory is compliance/security gaps. | Blocks all enterprise deals. | 30d |

### 🟠 High (7)

| ID | Phase | Finding | Impact | Effort |
|----|-------|---------|--------|--------|
| S-6 | P1 | **DiffCompressor Rust non-functional** — Returns input unchanged for many diffs, forcing Python fallback. Parity fixture likely not running or not catching. | No diff compression on Rust path for affected diffs. | 3d |
| S-7 | P1 | **ContentRouter 65ms = cumulative sub-compressor invocations** — The 65ms is NOT model routing. It's the cost of running 8 sub-compressors and picking the best result. SmartCrusher itself is only 0.22ms. | Misattributed bottleneck — optimization should target sub-compressor dispatch order, not routing logic. | 1d (measurement fix) |
| S-8 | P2 | **Rust WebSocket: no telemetry, compression, or fallback** — Clean bidirectional pump with `CancellationToken` but none of the features Python WS has (compression on `response.create`, HTTP fallback, session registry, metrics). | Rust WS path is feature-incomplete for production use. | 1w |
| S-9 | P3 | **`SqliteBackend` (CCR store) missing WAL** — DELETE journal mode on the compression hot-path store shared with Python and Rust. Writer-blocks-reader behavior under concurrent load. | `SQLITE_BUSY` errors under concurrent load on hot path. | 5min |
| S-10 | P4 | **Gemini has no Rust compression** — All Gemini requests bypass the Rust proxy's live-zone compressor. Python format conversion works, but zero value from Rust path. | Entire Gemini user segment unserved by Rust proxy. | 2w |
| S-11 | P4 | **9,600+ lines of Python handler logic not ported to Rust** — Rust proxy handles compression only. Python still owns parsing, routing, memory, CCR, savings, and response processing. | Dual-runtime drift risk increases with every feature addition. | 3mo (full porting) |
| S-12 | P4 | **CacheAligner has no Rust transform** — The entire prefix stabilization and cache alignment logic is Python-only, on the hot path. | Cache alignment overhead for Rust proxy path. | 1mo |

### 🟡 Medium (8)

| ID | Phase | Finding | Impact | Effort |
|----|-------|---------|--------|--------|
| S-13 | P1 | **AnchorSelector + AdaptiveSizer have no parity fixtures** — Two orchestration transforms with no cross-runtime verification. | Drift may exist without detection. | 2d |
| S-14 | P1 | **SmartCrusher behavioral divergence between runtimes** — Python has lossless → CompactTable → Kompress → Log fallback chain. Rust avoids this by dispatching directly by content type. Not a correctness gap, but divergent behavior needs verification. | Different compression output for edge-case content. | 1w |
| S-15 | P2 | **Python `full_sse_bytes` is full-stream copy** — Entire SSE response accumulated when memory/CCR features active. Unbounded for long responses (mitigated by `MAX_SSE_BUFFER_SIZE`). | Memory spike for long-running SSE streams with memory features enabled. | 2d |
| S-16 | P2 | **Python `_stream_openai_via_backend()` has no TTFB measurement** — OpenAI backend streaming path (`streaming.py:2103-2280`) lacks TTFB capture entirely. | OpenAI backend streaming has zero observability. | 1d |
| S-17 | P3 | **SemanticCache.stats() iterates 1000 entries under lock** — Blocks `get()`/`set()` operations during stats generation. | Dashboard polling competes with request-path cache lookups. | 2d |
| S-18 | P3 | **`_compression_metrics_lock` acquired 5x per compression task** — Each compression operation acquires and releases the lock 5 times for different metrics. | Cumulative lock overhead under high concurrency. | 1d |
| S-19 | P3 | **4 memory SQLite stores missing WAL** — Memory adapters (sqlite, sqlite_vector, sqlite_graph, memory adapter) lack WAL mode. | `SQLITE_BUSY` risk under concurrent memory operations. | 30min |
| S-20 | P4 | **Bedrock/Vertex compression stubbed** — Enterprise cloud provider endpoints have auth-only support, no compression. | Enterprise cloud users get no compression value. | 1w |

### 🟢 Low (4)

| ID | Phase | Finding | Impact | Effort |
|----|-------|---------|--------|--------|
| S-21 | P2 | Rust `StreamingCompressor` buffers text deltas to 100-token threshold | Adds one compression cycle of latency per block. Configurable. | Config change |
| S-22 | P3 | `CompressionStore.search()` runs BM25 under `threading.Lock` | Low-traffic path, acceptable. | None |
| S-23 | P4 | 8 Experimental capabilities (AudioCompressor, Stack Graph, Zed, etc.) | Not blocking, known experimental status. | Variable |
| S-24 | P4 | Rust WebSocket has no idle timeout | Zombie connections persist. Easy 300s timeout fix. | 30min |

---

## Dual-Runtime Performance Gap Analysis

### Where Rust is Better

| Aspect | Python | Rust | Gap |
|--------|--------|------|-----|
| SmartCrusher latency | Wrapped via PyO3 | Native 0.22ms ✅ | Negligible (PyO3 overhead <0.1ms) |
| Memory model | Multiple deep copies | Single copy, live-zone byte surgery ✅ | 15-45ms advantage per request |
| SSE state machine | Thick (usage + parsing) | Thin state machines with byte-level framing ✅ | Rust cleaner for core streaming |

### Where Python is Better

| Aspect | Python | Rust | Gap |
|--------|--------|------|-----|
| Transform coverage | All 12 compressors ✅ | Missing CodeCompressor, DiffCompressor unstable | Must port or fallback |
| TTFB measurement | Accurate measurement ✅ | Zero measurement | Must implement |
| Provider coverage | 12 providers + LiteLLM ✅ | 3 providers (Anthropic, OpenAI Chat, OpenAI Responses) | Must expand |
| Cache alignment | CacheAligner transform ✅ | No equivalent | Must port |
| Model routing | 705 lines, full routing ✅ | No model routing | Must port |
| WebSocket | Full features + compression + fallback ✅ | Clean pump, no features | Must add features |
| Memory system | 35 files, 8,000+ lines ✅ | None | Massive porting effort |
| Monitoring | Detailed `/status` + `/health` + `/metrics` | Basic | Must enrich |

---

## Capability Gaps by Type

| Category | Items | % of Total |
|----------|-------|-----------|
| **Compliance Gaps** | SOC 2, SAML SSO | 2% |
| **Missing Capabilities** | OTel export, Verification guard, Read-side intelligence, Batch routing, Webhook reliability | 5% |
| **Stubbed Features** | Bedrock/Vertex compression, OpenAI batch, Gemini Rust, Windows installer | 5% |
| **Experimental** | AudioCompressor, Stack Graph, Zed/Antigravity/OpenClaw, Vector store | 8% |

**Total inventoried: ~95 capabilities** — 42 Production (44%), 31 Beta (33%), 8 Experimental (8%), 5 Stubbed (5%), 5 Missing (5%), 4 Compliance Gaps (4%)

---

## Recommendations

### 🔴 Immediate (Week 1)

| # | Action | Phase Ref | Effort |
|---|--------|-----------|--------|
| 1 | Add WAL to `SqliteBackend` (CCR hot-path store) + 4 memory SQLite stores | S-9, S-19 | 30min |
| 2 | Add TTFB measurement to Rust proxy (`proxy.rs` — capture first-byte arrival time) | S-3 | 1d |
| 3 | Fix `PrometheusMetrics.export()` lock — snapshot under lock, build text outside | S-4 | 1d |
| 4 | Eliminate redundant `deep_copy_messages` in CacheAligner (`cache_aligner.py:282`) — it's detector-only, no mutation needed | S-2 | 1d |
| 5 | Reduce `_compression_metrics_lock` acquisitions from 5x to 2x per task | S-18 | 1d |
| 6 | Add TTFB measurement to Python OpenAI backend streaming path (`streaming.py:2103-2280`) | S-16 | 1d |

### 🟡 Short-term (Week 2-4)

| # | Action | Phase Ref | Effort |
|---|--------|-----------|--------|
| 7 | Fix DiffCompressor Rust path — investigate parity fixtures, fix root cause | S-6 | 3d |
| 8 | Add SemanticCache stats snapshot (iterate under lock, format outside) | S-17 | 2d |
| 9 | Fix ContentRouter metric attribution — separate routing vs sub-compressor costs | S-7 | 1d |
| 10 | Add Gemini live-zone compression in Rust proxy | S-10 | 2w |
| 11 | Verify SmartCrusher behavioral divergence (fallback chain) between runtimes | S-14 | 1w |

### 🟢 Medium-term (Month 2-3)

| # | Action | Phase Ref | Effort |
|---|--------|-----------|--------|
| 12 | Port CodeCompressor to Rust live-zone dispatcher | S-1 | 2w |
| 13 | Add Rust proxy WebSocket features (compression, fallback, telemetry) | S-8 | 1w |
| 14 | Add AnchorSelector + AdaptiveSizer parity fixtures | S-13 | 2d |
| 15 | Open SOC 2 Type II audit | S-5 | 30d |
| 16 | Add SAML SSO provider | S-5 | 30d |

### 🔵 Long-term (Month 3+)

| # | Action | Phase Ref | Effort |
|---|--------|-----------|--------|
| 17 | Port CacheAligner transform to Rust | S-12 | 1mo |
| 18 | Port model router to Rust | S-11 | 2w |
| 19 | Reduce Python proxy dependency — port parsing/CCR bookkeeping to Rust | S-11 | 3mo |
| 20 | Add Bedrock/Vertex compression in Rust | S-20 | 1w |

---

## Performance Score: 62/100

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Core path throughput | 75 | SmartCrusher 0.22ms is excellent; missing CodeCompressor in Rust drags *coverage* not *throughput* |
| Full coverage throughput | 55 | DiffCompressor unreliability + fallback chain divergence reduces average-case throughput |
| Streaming | 65 | Python TTFB accurate, Rust missing entirely, OpenAI backend path also missing; zero-buffer byte path is good |
| Caching efficiency | 55 | Lock contention in Prometheus metrics + semantic cache; missing WAL on hot path |
| Concurrency | 60 | Good executor sizing and PyO3 release; lock contention and deep_copy drag score |
| Dual-runtime parity | 50 | Large capability gap between Python and Rust; 9,600+ lines not ported |
| Capability maturity | 60 | 44% production is good but 10% gaps (SOC 2, SAML, OTel) blocks enterprise |

**Overall: 62/100**

---

## Oracle Final Review

**Reviewer:** Oracle
**Date:** 2026-07-12
**Source audits verified:** All 4 phases read in full

### Overall Assessment: 🟢 Approved

The synthesis is accurate, complete enough to be actionable, and well-structured. All 4 source phases are correctly represented. The corrections from review were applied.

### Changes Applied from Review
1. ✅ **S-25 added**: P2 OpenAI backend TTFB gap (now S-16)
2. ✅ **S-8 reframed**: SmartCrusher divergence → "behavioral divergence" (now S-14), demoted to MEDIUM
3. ✅ **WAL fixes moved to #1** in recommendations
4. ✅ **"Missing" renamed to "Gaps"** with Compliance vs Capability split
5. ✅ **Hard Truth section merged** into executive summary key finding
6. ✅ **Rust is Better table trimmed** to 3 strategic items
7. ✅ **Capability maturity summary condensed**
8. ✅ **File Reference Index removed** (source refs at top suffice)

### Remaining (Defensible Omissions)
- P3 leaked thread recovery (inherent Python limitation, monitored)
- P4 MCP tools gap vs LeanCTX (competitive detail, covered in competitive analysis)
- Rust WS idle timeout (now S-24, Low)

No further changes needed. Ship it.
