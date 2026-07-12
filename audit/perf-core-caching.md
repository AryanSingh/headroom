# Performance & Core Capabilities Audit — Phase 3: Caching & Performance Infrastructure

**Audit Date:** 2026-07-12
**Scope:** Lock contention, concurrency model, cache efficiency, SQLite WAL status, PyO3 GIL management

---

## 1. Lock Contention Map

### 1.1 Hot-Path asyncio.Lock Instances

| Lock | File | Scope | Contention Risk | Notes |
|------|------|-------|----------------|-------|
| `SemanticCache._lock` | `proxy/semantic_cache.py:126` | get/set/stats/clear | **MEDIUM** | Single lock serializes all cache ops. `stats()` acquires on every dashboard scrape. `get()` runs on every request. |
| `PrometheusMetrics._lock` | `proxy/prometheus_metrics.py:242` | record_request, export, reset_runtime, record_cache_bust, record_rate_limited, record_failed | **HIGH** | `export()` holds lock while building full Prometheus string (~thousands of lines). `record_request()` runs on every request path. Direct contention with dashboard scrapes. |
| `PrometheusMetrics._stage_timing_lock` | `proxy/prometheus_metrics.py:249` | stage_timing triple updates | **LOW** | threading.Lock (sync), tiny critical section. No async contention. |
| `RateLimiter._lock` | `proxy/rate_limiter.py:50` | check_request, check_token | **MEDIUM** | Acquired on every request for rate-limit checks. |
| `BatchContextStore._lock` | `ccr/batch_store.py:128` | store/get/cleanup | **LOW** | Only CCR batch path, not hot. |
| `MemoryHandler._init_lock` | `proxy/memory_handler.py:209` | backend initialization singleflight | **LOW** | Only first-request cold start. |
| `stats_snapshot_lock` | `proxy/server.py:2343` | /stats endpoint snapshot | **MEDIUM** | Acquired by every /stats scrape. Contends with anything that mutates stats. |
| `_upstream_check_lock` | `proxy/server.py:2357` | upstream health check cache | **LOW** | Only /health endpoint, 30s TTL. |
| `_request_counter_lock` | `proxy/server.py:788` | request ID generation | **LOW** | Single integer increment, microsecond hold. |

### 1.2 Hot-Path threading.Lock / RLock Instances

| Lock | File | Scope | Contention Risk | Notes |
|------|------|-------|----------------|-------|
| `CompressionCache._lock` | `cache/compression_cache.py:97` | All per-session cache ops | **MEDIUM** | RLock, per-session instance. Contention only if parallel requests share session. |
| `CompressionStore._lock` | `cache/compression_store.py:230` | store/retrieve/search | **MEDIUM** | CCR hot path. Search involves BM25 scoring under lock. |
| `CompressionFeedback._lock` | `cache/compression_feedback.py:179` | pattern learning | **LOW** | Background analysis, not request-path. |
| `SessionTrackerStore._lock` | `cache/prefix_tracker.py:385` | tracker CRUD + SQLite writes | **MEDIUM** | Blocks prefix freeze lookups during DB writes. |
| `_compression_metrics_lock` | `proxy/server.py:751` | compression executor metrics | **MEDIUM** | Acquired by worker threads on every compression task start/end/timeout. 5 acquisitions per task lifecycle. |
| `_compression_caches_lock` | `proxy/server.py:657` | session→cache dict lookup | **LOW** | RLock, only creates new entries. |

### 1.3 Key Contention Scenarios

**Scenario A: Dashboard scrape blocks request path**
`PrometheusMetrics.export()` holds `_lock` for the entire duration of building the Prometheus text format. A full scrape can take 1-5ms with many metrics. During this time, every `record_request()` call on the request path is blocked waiting for the same lock. Under high concurrency, this creates a head-of-line blocking pattern.

**Scenario B: SemanticCache.stats() blocks cache.get()**
The `/stats` or dashboard endpoint calls `SemanticCache.stats()` which acquires `_lock`. While iterating all entries to sum `hit_count` and `tokens_saved_per_hit`, every `get()` and `set()` on the request path is blocked. With 1000 entries, this iteration is O(n).

**Scenario C: Compression executor metrics contention**
`_compression_metrics_lock` is acquired 5 times per compression task:
1. Queue increment (asyncio event loop)
2. Queue→in-flight transition (worker thread)
3. In-flight decrement + elapsed time (worker thread finally block)
4. Timeout marking (asyncio event loop)
5. Queue decrement on timeout (asyncio event loop)

Under burst compression (e.g., 32 concurrent tasks), this creates cross-thread contention on a single `threading.Lock`. Not catastrophic (critical sections are ~microseconds), but measurable under load.

---

## 2. Concurrency Architecture Analysis

### 2.1 ThreadPoolExecutor Sizing

**Compression executor** (`server.py:725-734`):
```python
_compression_max = min(32, (os.cpu_count() or 1) * 4)
```

**Assessment:** Reasonable for CPU-bound Rust work that releases the GIL. On an 8-core machine, this yields 32 workers. However:
- The formula assumes all workers do GIL-releasing Rust work. If any worker does Python-level work (e.g., cache lookups, serialization), they'll contend for the GIL.
- The cap at 32 is sensible — beyond that, context-switching overhead dominates.
- The `compression_max_workers` config override allows operators to tune.

**OpenAI Responses Unit executor** (`handlers/openai/utils.py:102-110`):
```python
_OPENAI_RESPONSES_UNIT_PARALLELISM_MAX = 8
```
Separate pool for OpenAI unit-level parallelism. Appropriate sizing.

### 2.2 Leaked Thread Tracking

**Mechanism** (`server.py:1258-1301`):

1. Before dispatching to executor: increment `_compression_queued` under `_compression_metrics_lock`.
2. Worker `_wrapped()` function: on start, transition from queued→in-flight under lock.
3. On `asyncio.wait_for` timeout: mark `state["timed_out"] = True` under lock. The worker thread **keeps running** (Python can't preempt threads).
4. Worker `finally` block: if `state["timed_out"]`, increment `_compression_leaked_threads`.

**Assessment:** This is a correct and well-documented approach to Python's thread cancellation limitation. The leaked-thread counter is the right observable signal for operators. However:
- Leaked threads **are not recovered** — they run to completion and the thread returns to the pool. This is inherent to Python's thread model.
- If a burst of timeouts occurs, the pool can fill up with leaked workers, causing new tasks to queue indefinitely.
- The `_compression_queue_timeouts` counter (jobs that timeout before a worker starts) is a leading indicator of pool exhaustion.

### 2.3 GIL Contention (PyO3 Bridge)

**File:** `crates/cutctx-py/src/lib.rs`

Every compute-heavy PyO3 method releases the GIL via `py.allow_threads()`:

| Method | Line | GIL Released? |
|--------|------|---------------|
| `SmartCrusher.compress()` | 444 | ✅ Yes |
| `SmartCrusher.compress_with_stats()` | 462 | ✅ Yes |
| `SmartCrusher.crush()` | 762 | ✅ Yes |
| `SmartCrusher.smart_crush_content()` | 781 | ✅ Yes |
| `SmartCrusher.crush_array_json()` | 814, 861 | ✅ Yes |
| `detect_content_type()` | 989 | ✅ Yes |
| `is_json_array_of_dicts()` | 1004 | ✅ Yes |
| `LogCompressor` methods | 1266 | ✅ Yes |
| `SearchCompressor` methods | 1453 | ✅ Yes |
| `TagProtector` methods | 1502, 1513 | ✅ Yes |

**Assessment:** Excellent GIL discipline. All compute-bound operations release the GIL, allowing true parallelism across the thread pool. This is critical for the `min(32, cpu_count*4)` sizing to actually work — without GIL release, 32 threads would serialize on CPython.

**Potential issue:** The `Mutex` import (`std::sync::Mutex`) in `lib.rs:17` suggests some shared Rust state. If this mutex is held during `allow_threads`, it could cause thread parking that isn't visible from Python. This is a Rust-internal concern and likely fine, but worth noting.

### 2.4 Blocking Calls on Event Loop

**No blocking calls found on the async hot path.** The compression executor correctly offloads sync work to threads. The semantic cache uses `asyncio.Lock` (not blocking). The rate limiter is async. The only potential issue:
- `SemanticCache._compute_key()` does JSON serialization + SHA256 hashing **outside** the lock (before `async with self._lock`). This is correct — the key computation doesn't need the lock — but it does mean two concurrent `get()` calls for the same key compute the hash twice. This is a minor inefficiency, not a correctness issue.

---

## 3. Cache Efficiency Assessment

### 3.1 Semantic Cache Hit Rate

The semantic cache (`proxy/semantic_cache.py`) is an **exact-match** cache keyed by SHA256 of normalized `{model, messages}`. Normalization strips:
- Per-call cache breakpoints (`cache_control`)
- Volatile metadata keys (timestamps, request IDs, session IDs)
- System-reminder blocks (Anthropic-specific)
- Trailing whitespace

**Estimated hit rate:** LOW to MODERATE. The exact-match design means any message change (new tool result, updated context) produces a miss. The normalization helps with metadata churn but can't help with content growth across turns. This is by design — it's a response cache, not a prefix cache.

**Key limitation:** The cache stores full response bodies (including streaming responses). With `max_entries=1000` and large responses, memory usage can be significant. No memory budget is enforced — only entry count.

### 3.2 Prefix Tracker Effectiveness

**File:** `cache/prefix_tracker.py`

The `PrefixCacheTracker` tracks how many tokens the provider cached after each response. On the next turn, it freezes that many messages so the transform pipeline skips them entirely.

**Effectiveness:** HIGH when the provider cooperates. The tracker correctly:
- Uses provider-reported `cache_read_input_tokens` / `cache_creation_input_tokens` to determine the frozen boundary.
- Persists state to SQLite for cross-restart continuity.
- Handles session TTL and expiry.

**Cache-bust detection:** The `FreezeStats` dataclass tracks `busts_avoided`, `tokens_preserved`, and `compression_foregone_tokens`. This gives operators visibility into whether prefix freezing is actually saving money vs. foreclosing compression savings.

**Potential issue:** The `force_compress_threshold` (default 0.5) means if compression would save >50% of tokens, the cache is busted intentionally. This is a reasonable heuristic but may surprise operators who see unexpected cache invalidations.

### 3.3 CacheAligner (Detector-Only)

**File:** `transforms/cache_aligner.py`

The `CacheAligner` is now a **detector-only** transform (after PR-A2 / P2-23 fix). It:
1. Detects volatile content in system prompts (UUIDs, timestamps, JWTs, hex hashes)
2. Emits warnings for observability
3. **Never modifies messages**

**Assessment:** This is the correct design. The previous rewrite path violated the invariant that the cache hot zone must never be mutated. The detector-only approach gives operators visibility without risk.

---

## 4. SQLite WAL Status

### 4.1 Stores WITH WAL

| Store | File | WAL? | Notes |
|-------|------|------|-------|
| `SessionTrackerStore` | `cache/prefix_tracker.py:404` | ✅ `PRAGMA journal_mode=WAL` | Set on every `_connect()` call. |
| `SecuritySecretsStore` | `security/secrets_store.py:150` | ✅ `PRAGMA journal_mode=WAL` | Enterprise security. |
| `WebhookStore` (2 stores) | `proxy/webhook_stores.py:129,318` | ✅ `PRAGMA journal_mode=WAL` | Both webhook stores. |
| `FleetManager` | `fleet.py:44` | ✅ `PRAGMA journal_mode=WAL` | Fleet coordination. |
| `MFAStore` | `security/mfa.py:206` | ✅ `PRAGMA journal_mode=WAL` | MFA state. |
| `cutctx_ee/*` (5+ stores) | `cutctx_ee/org.py:92`, `audit.py:222`, `rbac.py:285`, `scim.py:62`, `license_db.py:74` | ✅ `PRAGMA journal_mode=WAL` | Enterprise edition. |

### 4.2 Stores WITHOUT WAL (Missing)

| Store | File | WAL? | Concurrent Access Risk | Remediation |
|-------|------|------|----------------------|-------------|
| `SqliteBackend` (CCR) | `cache/backends/sqlite.py:41-53` | ❌ **Missing** | **HIGH** — CCR store is on the request path (store/retrieve during compression). Default journal mode (DELETE) means writers block readers and vice versa. | 1 line: `conn.execute("PRAGMA journal_mode=WAL")` in `_init_db()` |
| `SQLiteStorage` (request metrics) | `storage/sqlite.py:36-64` | ❌ **Missing** | **MEDIUM** — Request-path writes (`save()`), but reads are analytics-only. Single connection pattern mitigates but doesn't eliminate. | 1 line in `_ensure_db_exists()` |
| `SQLiteMemoryAdapter` | `memory/adapters/sqlite.py:110-118` | ❌ **Missing** | **MEDIUM** — Memory store creates new connections per call (`_get_conn()` returns `sqlite3.connect(...)`). Without WAL, concurrent memory operations (store/recall) can block each other. | 1 line in `_get_conn()` |
| `SQLiteVectorIndex` | `memory/adapters/sqlite_vector.py:235-249` | ❌ **Missing** | **MEDIUM** — Vector search can be slow (embedding lookup). Without WAL, a long read blocks writes. Per-thread connection pool helps but doesn't eliminate. | 1 line in `_create_conn()` |
| `SQLiteGraphAdapter` | `memory/adapters/sqlite_graph.py:80-90` | ❌ **Missing** | **MEDIUM** — Graph traversal can be slow. Similar to vector. | 1 line in `_create_conn()` |

### 4.3 Remediation Cost

**Total:** 5 stores need WAL. Each requires exactly 1 line:
```python
conn.execute("PRAGMA journal_mode=WAL")
```
added after connection creation in `_get_conn()` / `_create_conn()` / `_init_db()`.

**Risk of adding WAL:** Near-zero for existing deployments. WAL is backwards-compatible with existing data. The only consideration is that WAL creates `-wal` and `-shm` sidecar files, which operators should be aware of for backup/restore.

**Note:** `SqliteBackend` (CCR) is the most critical miss — it's shared with Rust's `SqliteCcrStore` and is on the hot compression path.

---

## 5. PyO3 Bridge GIL Analysis

### 5.1 GIL Release Coverage

All 14+ compute-heavy PyO3 methods release the GIL via `py.allow_threads()`. This is the gold standard for PyO3 bindings doing CPU work.

### 5.2 Potential Blocking Patterns

**No blocking calls on the event loop found.** The architecture is:
1. Async handler receives request
2. Offloads sync compression to `ThreadPoolExecutor` via `_run_compression_in_executor()`
3. Worker thread calls into Rust via PyO3 (GIL released)
4. Result returned to asyncio future

The GIL release means that while one thread is in Rust (no GIL held), other Python threads can execute freely. This is critical for the proxy's concurrency model.

### 5.3 `std::sync::Mutex` in Rust

`lib.rs:17` imports `std::sync::Mutex`. This is used for Rust-internal shared state (likely the `KeywordRegistry` or similar). Since it's a Rust mutex (not Python), it only blocks Rust threads, not the Python event loop. The `allow_threads` wrapper ensures Python threads aren't blocked.

---

## 6. Key Issues (Severity)

### 🔴 HIGH SEVERITY

1. **`PrometheusMetrics.export()` holds `_lock` during full text generation** (`prometheus_metrics.py:840-1164+`)
   - Every `/metrics` scrape holds the lock for the entire duration of building ~hundreds of metric lines.
   - Every `record_request()` call (hot path) blocks during scrapes.
   - **Fix:** Snapshot all counters under lock, then build the text string outside the lock. The `_stage_timing_lock` pattern already demonstrates this approach correctly.

2. **`SqliteBackend` (CCR) missing WAL** (`cache/backends/sqlite.py:41-53`)
   - CCR store is on the compression hot path. Default DELETE journal mode causes writer-blocks-reader behavior.
   - **Fix:** Add `conn.execute("PRAGMA journal_mode=WAL")` in `_init_db()`.

### 🟡 MEDIUM SEVERITY

3. **`SemanticCache.stats()` iterates all entries under lock** (`semantic_cache.py:200-217`)
   - Dashboard scrapes iterate all 1000 entries to sum `hit_count` and `tokens_saved_per_hit`.
   - Blocks `get()` and `set()` on the request path during iteration.
   - **Fix:** Maintain running totals as atomic counters (updated in `get()`/`set()`), eliminating the need for iteration.

4. **`CompressionStore.search()` runs BM25 under lock** (`compression_store.py`)
   - BM25 scoring involves tokenization and scoring loops. This is a non-trivial computation held under `threading.Lock`.
   - **Fix:** Consider a read-write lock or copy-on-read pattern for search operations.

5. **Four memory-related SQLite stores missing WAL** (`sqlite.py`, `sqlite_vector.py`, `sqlite_graph.py`, `sqlite.py` adapter)
   - Memory operations can block each other under concurrent load.
   - **Fix:** 1 line each, as detailed in §4.2.

6. **`_compression_metrics_lock` acquired 5 times per compression task**
   - Cross-thread contention under burst compression. Not catastrophic but measurable.
   - **Fix:** Consider atomic counters (`threading` doesn't have them, but `multiprocessing.atomic` or a simple `with` block consolidation could reduce acquisitions from 5 to 2).

### 🟢 LOW SEVERITY

7. **`SemanticCache._compute_key()` does SHA256 outside lock** — Minor inefficiency (double computation under concurrency), but correct.

8. **`BatchContextStore` uses `asyncio.Lock`** — Correct for its async context, low contention.

9. **Leaked threads are not recovered** — Inherent Python limitation. The monitoring signals (counter + queue pressure) are correctly implemented.

---

## 7. Recommendations

### Immediate (1-line fixes each)
1. Add WAL to `SqliteBackend._init_db()` — `conn.execute("PRAGMA journal_mode=WAL")`
2. Add WAL to `SQLiteStorage._ensure_db_exists()`
3. Add WAL to `SQLiteMemoryAdapter._get_conn()`
4. Add WAL to `SQLiteVectorIndex._create_conn()`
5. Add WAL to `SQLiteGraphAdapter._create_conn()`

### Short-term (architecture improvements)
6. **Decouple `PrometheusMetrics.export()` from hot-path lock.** Snapshot counters under lock, build text outside. This is the single highest-impact change for request-path latency under dashboard load.
7. **Add running totals to `SemanticCache`.** Maintain `_total_hit_count` and `_total_saved_per_hit` as integers updated in `get()`/`set()`, so `stats()` can return them without iterating.
8. **Consider `threading.RLock` for `CompressionStore._lock`** if any method path calls another locked method (currently not the case, but defensive).

### Long-term (monitoring improvements)
9. **Add lock contention metrics.** Instrument `asyncio.Lock` and `threading.Lock` acquisitions with timing to surface hidden contention. Python 3.12+ has `threading.get_stats()`, or use manual timing wrappers.
10. **Add cache hit-rate dashboards.** The semantic cache emits `_hits`/`_misses` but these aren't exposed in the Prometheus export. Add `cutctx_cache_hit_ratio` gauge.
11. **Add compression executor saturation alerting.** The `leaked_threads_total` and `queue_timeouts_total` counters exist but aren't in the Prometheus export. Expose them as gauges.
