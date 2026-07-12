# Phase 2: Streaming & Real-Time Path Analysis

## Streaming Architecture Overview

### Python Proxy Path

The Python proxy (FastAPI + httpx) handles streaming through `StreamingMixin` in `cutctx/proxy/handlers/streaming.py`. Two primary entry points:

1. **`_stream_response()`** (line 880) — Direct upstream HTTP streaming. Opens an httpx streaming response, yields chunks to the client via `StreamingResponse`. Each chunk is simultaneously:
   - Forwarded to the client immediately (`yield chunk` at line 1638)
   - Buffered into `sse_buffer` for usage parsing
   - Optionally accumulated into `full_sse_bytes` for post-stream memory/CCR processing

2. **`_stream_response_backend()`** (line 1926) — Backend-delegated streaming (Anthropic format). Yields events from `backend.stream_message()`.

3. **`_stream_openai_via_backend()`** (line 2103) — OpenAI backend streaming via `backend.stream_openai_message()`.

The Python path is **byte-immediate**: chunks are yielded to the client as fast as they arrive from upstream. The comment at line 1636-1638 is explicit:
```
# Always stream immediately — buffering breaks
# real-time clients (LangGraph, LangChain, etc.)
yield chunk
```

### Rust Proxy Path

The Rust proxy (`crates/cutctx-proxy/src/proxy.rs`) implements a **parallel byte-passthrough + telemetry state machine** architecture (PR-C1):

1. **Byte path**: `upstream_resp.bytes_stream()` → `map(try_send to parser_tx)` → `Body::from_stream()` → client. **Zero buffering.** The `.map()` at line 1234-1253 clones each chunk into a bounded mpsc (capacity 100, defined at line 1211) without awaiting. `try_send` is non-blocking; if the parser falls behind, the chunk is dropped for telemetry only.

2. **Telemetry state machine**: `tokio::spawn(run_sse_state_machine())` at line 1217 runs in a separate task. It consumes from the mpsc, feeds bytes through `SseFramer`, and runs provider-specific state machines (`AnthropicStreamState`, `ChunkState`, `ResponseState`). **Never blocks the byte path.**

The key architectural difference: Python does SSE parsing **in the hot path** (on each chunk before yielding). Rust does SSE parsing **in parallel** (spawned task). The Rust approach is strictly better for latency — the byte path has zero parse overhead.

---

## TTFB Measurement Status

### Python Proxy: ✅ Accurate

**`_stream_response()`** — lines 1613-1614:
```python
if stream_state["ttfb_ms"] is None:
    stream_state["ttfb_ms"] = (time.time() - start_time) * 1000
```
`start_time` is captured at line 926 (`start_time = time.time()`) before the upstream request is sent. TTFB is measured as elapsed time from request initiation to first chunk arrival. This is accurate and correct.

**`_stream_response_backend()`** — lines 1967-1968:
```python
if stream_state["ttfb_ms"] is None:
    stream_state["ttfb_ms"] = (time.time() * 1000) - start_ms
```
Same pattern, same accuracy.

**`_stream_openai_via_backend()`** — No explicit TTFB measurement. The `start_time` parameter is passed in but TTFB is not tracked in `stream_state`. This is a minor gap — OpenAI backend streaming does not report TTFB.

### Rust Proxy: ❌ No TTFB Measurement

The Rust proxy captures `start = Instant::now()` at line 424 and uses it for the final `latency_ms` log at line 1286. However:

- **No first-chunk TTFB metric.** The `latency_ms` reported at line 1286 measures the time from request entry to response *completion* (the log fires when the response is built, not when the first byte arrives).
- The `run_sse_state_machine` function has no `Instant::now()` or timing instrumentation at all.
- No Prometheus histogram or structured log field distinguishes "time to first byte" from "total request latency."

**Impact:** Without TTFB in the Rust path, operators cannot distinguish upstream latency from proxy overhead for streaming requests. This is the most significant observability gap in the Rust proxy.

**What it would take to add:**
1. Capture `Instant::now()` when the first byte arrives in the `.map()` closure at line 1234.
2. Record it to the SSE state machine (e.g., via `try_send` on a separate oneshot channel, or a `Mutex<Option<Instant>>` shared between the byte path and the parser task).
3. Emit as a new field in the `"sse stream closed"` log and/or a Prometheus histogram.

---

## Buffering Analysis

### Where buffering occurs

| Layer | Python | Rust |
|-------|--------|------|
| **Request body** | Full JSON parse + compress before upstream send | Full JSON parse + compress before upstream send |
| **Response body (byte path)** | **None** — `yield chunk` immediately | **None** — `Body::from_stream()` directly |
| **SSE buffer for usage** | `sse_buffer` (bytearray, grows per chunk) | `SseFramer` (BytesMut, bounded) |
| **Full SSE mirror** | `full_sse_bytes` (bytearray, full stream copy) | **None** — state machines track structured state only |
| **Memory mode buffer** | `buffered_chunks` list (full response copy) | N/A |
| **Compression (response)** | None on streaming path | `StreamingCompressor` (incremental, threshold-based) |

### Key findings

1. **Python `full_sse_bytes` is a full-stream copy.** When memory, CCR feedback, or structured output validation is enabled, the entire SSE response is accumulated in `full_sse_bytes` (line 1664, 1673). For a 100KB response, this is 100KB of allocation. For memory mode, `buffered_chunks` duplicates it further. **Severity: Medium** — only active when memory/CCR features are enabled, but unbounded for long responses (mitigated by `MAX_SSE_BUFFER_SIZE` check at line 1665).

2. **Rust state machines are O(1) memory.** The `SseFramer` holds one `BytesMut` buffer (drained per complete event). State machines (`AnthropicStreamState`, `ChunkState`, `ResponseState`) hold only parsed fields (token counts, status). No full-response copy.

3. **Rust `StreamingCompressor` buffers text deltas.** It accumulates `content_block_delta` text until `text_compress_threshold` tokens (default 100), then compresses and emits. This adds **one compression cycle of latency** per compressed block. For most responses, the first ~100 tokens are forwarded uncompressed, then subsequent deltas are batch-compressed. **Severity: Low** — the threshold is configurable and the first chunk is always forwarded immediately.

4. **Python SSE buffer safety.** `MAX_SSE_BUFFER_SIZE` is checked at line 1625 and truncates to the most recent half. This prevents OOM but may lose telemetry data for very long streams. The check is also applied to `full_sse_bytes` at line 1665.

### Buffering bottlenecks for large payloads

- **Request-side compression** (Rust): `compress_anthropic_request_with_ccr()` buffers the full request JSON in memory (`buffered` at line 759), parses it, compresses, and re-serializes. For a 10MB request body, this is 10MB peak allocation. This is a known tradeoff — live-zone compression requires full-body access. **Severity: Low** for typical LLM requests (1-5KB), **Medium** for tool-heavy requests (50KB+).

- **Response-side**: No full-response buffering in either runtime for the streaming path. Both Python and Rust forward bytes as they arrive.

---

## State Machine Quality Assessment

### Python SSE: Anthropic (`_parse_sse_usage`)

- ✅ Correctly handles `message_start` (input tokens, cache reads, cache creation with TTL buckets)
- ✅ Correctly handles `message_delta` (output tokens)
- ✅ UTF-8 safe: uses `parse_sse_events_from_byte_buffer()` which handles split codepoints (P1-15 fix)
- ⚠️ Does **not** parse `content_block_delta` for text content — only extracts usage events. This is intentional (Python is not doing mid-stream processing).

### Python SSE: OpenAI Chat (`_parse_sse_usage_from_buffer`)

- ✅ Parses usage from final chunk when `stream_options.include_usage=true`
- ✅ Falls back to per-chunk `completion_tokens` parsing via `_parse_completion_tokens_from_sse_chunk()`
- ⚠️ Same limitation: only extracts usage, not content deltas.

### Rust SSE: Anthropic (`sse/anthropic.rs`)

- ✅ **Complete event coverage**: `message_start`, `content_block_start`, `content_block_delta` (all 5 delta types: `text_delta`, `thinking_delta`, `signature_delta`, `input_json_delta`, `citations_delta`), `content_block_stop`, `message_delta`, `message_stop`
- ✅ Blocks keyed by `index` (not position) — tolerates out-of-order completion
- ✅ `UsageBuilder::merge_from()` correctly handles monotone non-decreasing usage fields
- ✅ Unknown delta types emit `tracing::warn` with `event=sse_unknown_event` — wire-format drift is visible

### Rust SSE: OpenAI Chat (`sse/openai_chat.rs`)

- ✅ Correctly parses `choices[].delta` format
- ✅ Tool call `id` and `function.name` only set on first chunk (P4-48 fix)
- ✅ `function.arguments` accumulated via `push_str` (correct for streaming JSON fragments)
- ✅ `[DONE]` sentinel detection
- ✅ Usage extraction when present

### Rust SSE: OpenAI Responses (`sse/openai_responses.rs`)

- ✅ **All 17 event types** handled: `response.created`, `response.in_progress`, `output_item.added`, `output_item.done`, `content_part.added`, `content_part.done`, `output_text.delta`, `output_text.done`, `function_call_arguments.delta`, `function_call_arguments.done`, `reasoning_summary.delta`, `reasoning_summary.done`, `response.completed`, `response.failed`, `response.incomplete`
- ✅ Items keyed by `item.id` (not position) — P1-17 fix
- ✅ `capture_envelope_metadata()` extracts `service_tier` and `incomplete_details.reason`

### Rust SSE: Framing (`sse/framing.rs`)

- ✅ **Byte-level framing** — accumulates raw bytes, finds `\n\n` terminators in bytes, decodes UTF-8 only on complete events. This is the P1-15 fix for split-codepoint corruption.
- ✅ Comment lines (`: ping`) silently dropped
- ✅ `[DONE]` sentinel detection with `done_seen()` flag
- ✅ Zero-copy: `Bytes` slicing for event payloads (reference-counted, no allocation per event)
- ✅ Well-tested (6 unit tests covering empty, comment, data-only, event+data, multi-data, done sentinel)

**Overall state machine quality: Excellent.** The Rust implementation is strictly superior to Python — complete event coverage, byte-level safety, and provider-specific edge cases handled. The Python side is intentionally thin (usage-only parsing) since it delegates content handling to the caller.

---

## WebSocket Path Analysis

### Rust WebSocket (`websocket.rs`)

- **Architecture**: Bidirectional pump with `CancellationToken` for clean teardown. Two spawned tasks: `client → upstream` and `upstream → client`. Each direction has its own cancel token.
- **No compression**: Raw message relay. No live-zone compression on WS frames.
- **No telemetry**: No SSE state machine equivalent for WS frames. No token counting.
- **No timeout**: No idle timeout or maximum session duration. Connections persist until one side closes.
- **Clean shutdown**: `CancellationToken` prevents the half-close hang bug (line 169-174). When either side closes, the other is aborted immediately.
- **Header forwarding**: Selective — skips tungstenite-managed headers, forwards user-meaningful ones (Authorization, Sec-WebSocket-Protocol, etc.).

### Python WebSocket (`responses.py:handle_openai_responses_ws`)

- **Architecture**: Same bidirectional pump pattern (two asyncio tasks, `asyncio.wait(FIRST_COMPLETED)`).
- **Compression**: `response.create` frame is intercepted and compressed through the Python ContentRouter before forwarding to upstream. Subsequent frames are relayed raw.
- **First-frame timeout**: `WS_FIRST_FRAME_TIMEOUT_SECONDS = 60.0` (defined in `utils.py:508`). If the client doesn't send `response.create` within 60s, the session is closed.
- **Fallback**: When WS upstream connect fails after retries, the handler reads the first client frame and falls back to HTTP POST (`_ws_http_fallback`).
- **Session registry**: `WebSocketSessionRegistry` tracks active sessions, supports cancellation and metrics.
- **Extensive telemetry**: Token counts, frame counts, cancel frame counts, duration, termination cause classification.

### Fallback from WS to HTTP

The Python proxy has explicit fallback logic (line 3603-3648): when WS upstream connect fails, it reads the first client frame (with timeout), parses the `response.create` body, and routes through `_ws_http_fallback()`. The Rust proxy has **no fallback** — WS connect failure returns 502 immediately.

---

## Time-to-First-Byte Overhead Sources

### Pre-stream latency contributors

| Stage | Python | Rust |
|-------|--------|------|
| **Auth classification** | ~microseconds (in-memory) | ~microseconds (in-memory) |
| **Header forwarding** | ~microseconds | ~microseconds |
| **Request body buffering** | Full JSON read (for compression) | Full JSON read (for compression) |
| **Compression** | Python SmartCrusher (~1-10ms for typical) | Rust live-zone (~0.1-1ms) |
| **Cache lookup** | Semantic cache (network call if remote) | Drift detection (in-memory SHA) |
| **Upstream connection** | httpx connection pool (~1-10ms cold) | reqwest connection pool (~1-5ms cold) |
| **Upstream TTFB** | Provider-dependent (100ms-2s) | Provider-dependent (100ms-2s) |
| **First chunk forwarding** | `yield chunk` (immediate) | `try_send` + `Body::from_stream` (immediate) |

### Is the overhead measurable and tracked?

- **Python**: Yes. TTFB is measured at first chunk arrival. Stage timing is available via `StageTimer`.
- **Rust**: **No.** Only total `latency_ms` is tracked. No breakdown of compression time, connection time, or first-byte time. The `start.elapsed()` at line 1286 captures the total, not TTFB.

### Key overhead risks

1. **Request body buffering is synchronous** in both runtimes. For the Rust proxy, `to_bytes(&mut req.body_mut())` at ~line 759 blocks the handler until the full body arrives. For large requests, this adds measurable latency before the upstream request is even sent.

2. **Semantic cache lookup** (Python only) may involve network I/O (remote cache server). This runs before the streaming path starts, so it directly adds to TTFB.

3. **No compression overhead on streaming response path** in either runtime. Both Python and Rust forward response bytes immediately without decompression. The Rust `StreamingCompressor` is an optional post-processing step that does not block the byte path.

---

## Key Issues

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| S-1 | **High** | Rust proxy has no TTFB measurement — operators cannot distinguish proxy overhead from upstream latency for streaming requests | `proxy.rs:1286` — only `latency_ms` (total) |
| S-2 | **Medium** | Python `full_sse_bytes` accumulates full response copy when memory/CCR/SO enabled — unbounded allocation for long streams (mitigated by MAX_SSE_BUFFER_SIZE) | `streaming.py:1664` |
| S-3 | **Medium** | Python `_stream_openai_via_backend()` has no TTFB measurement | `streaming.py:2103-2280` |
| S-4 | **Low** | Rust `StreamingCompressor` accumulates text deltas before compressing — first compression cycle adds latency (mitigated by threshold and immediate first-chunk forwarding) | `streaming_compressor.rs:198` |
| S-5 | **Low** | Rust WS path has no telemetry, no compression, no fallback — strictly less capable than Python WS path | `websocket.rs` |
| S-6 | **Info** | Rust WS has no idle timeout — zombie connections persist indefinitely | `websocket.rs:169` |

---

## Recommendations

1. **[S-1] Add TTFB to Rust proxy.** Capture `Instant::now()` on first byte arrival in the `.map()` closure at `proxy.rs:1234`. Pass to the SSE state machine task via a `tokio::sync::oneshot` or shared `AtomicInstant`. Emit as `ttfb_ms` in the `"sse stream closed"` log and a Prometheus histogram. Estimated effort: ~20 lines of Rust.

2. **[S-2] Cap `full_sse_bytes` independently of `sse_buffer`.** The current code applies `MAX_SSE_BUFFER_SIZE` to both, but `full_sse_bytes` is only needed for post-stream parsing. Consider a tighter cap or streaming-parse approach for memory/CCR feedback.

3. **[S-3] Add TTFB to `_stream_openai_via_backend`.** Mirror the pattern from `_stream_response_backend` — capture `start_time` before the first `async for` yield.

4. **[S-5] Consider adding basic telemetry to Rust WS.** At minimum, count frames and measure session duration. Compression is a separate feature decision.

5. **[S-6] Add idle timeout to Rust WS.** A 300s idle timeout (matching the Python `WS_FIRST_FRAME_TIMEOUT_SECONDS` pattern) would prevent zombie connections.
