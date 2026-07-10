# Architecture Analysis — Cutctx Project

**Date:** 2026-07-10
**Scope:** Full codebase — Python (207K lines, 533 files) + Rust (74K lines, 195 files) + React dashboard
**Previous audit:** July 8, 2026 (10-domain analysis)

---

## Architecture Rating: 🟢

The dual-runtime architecture is **intentional and well-executed**. Python handles the high-surface proxy logic (7,903-line `server.py` notwithstanding), Rust owns the hot compression path via PyO3, and the boundary is clean. The system is production-ready with genuine compression working across three providers (Anthropic, OpenAI Chat, OpenAI Responses). The main risk is not structural drift but **concentration risk in `server.py`**.

---

## Key Strengths

- **Live-zone compression is genuinely working.** The Rust dispatcher in `cutctx-core/src/transforms/live_zone.rs` (3,289 lines) walks Anthropic/OpenAI request shapes, identifies compressible blocks, dispatches to content-specific compressors, and rewrites via byte-range surgery. Three provider dispatchers are implemented and wired. This is not stub code — it's the real product.

- **The compression pipeline has clean extensibility.** The `ReformatTransform` / `OffloadTransform` trait pair in `cutctx-core/src/transforms/pipeline/traits.rs` is well-designed. Adding a new compressor means implementing one trait, registering it with the `CompressionPipelineBuilder`, and the orchestrator handles gating, parallel bloat estimation, and CCR offload automatically. No existing code changes needed.

- **The PyO3 bridge is thorough and well-scoped.** `cutctx-py/src/lib.rs` (1,846 lines) wraps SmartCrusher, LogCompressor, DiffCompressor, SearchCompressor, content detection, tag protection, and the live-zone compression function. It calls `py.allow_threads()` for CPU-bound work and creates per-call `InMemoryCcrStore` instances to avoid cross-thread store contention.

- **The auth-mode → compression-policy → pipeline-gate chain is architecturally sound.** `auth_mode.rs` classifies headers into Payg/OAuth/Subscription. `compression_policy.rs` maps that to a `CompressionPolicy` struct with `live_zone_only`, `cache_aligner_enabled`, `volatile_token_threshold`, `max_lossy_ratio`, and `toin_read_only`. The pipeline stages read these fields rather than re-classifying. Clean separation of concerns.

- **CCR (Compress-Cache-Retrieve) has a trait-based storage backend.** `ccr/mod.rs` defines `CcrStore` with `put`/`get`/`len`. Three backends (InMemory, SQLite, Redis) implement it. The `compute_key` function (BLAKE3 → 16 hex chars) is centralized so every call site hashes identically.

---

## Critical Issues

### CRITICAL: `server.py` is a 7,903-line god object
**File:** `cutctx/proxy/server.py`
**Lines:** 1–7,903

This single file contains:
- The `CutctxProxy` class (lines 446–845+) with 40+ instance attributes
- 5 handler mixins (`StreamingMixin`, `AnthropicHandlerMixin`, `OpenAIHandlerMixin`, `GeminiHandlerMixin`, `BatchHandlerMixin`)
- All FastAPI route definitions
- Admin auth middleware (SSO, API key, MFA enforcement)
- Stats endpoint (lines 4493–4535)
- Compression cache management
- Model router binding (lines 2322–2340)
- Retention manager startup (lines 2270–2299)
- Webhook dispatcher startup (lines 2301–2319)
- Stack-graph resolver initialization (lines 1134–1163)
- `/compress` SDK endpoint (lines 6700–6766)
- Policy learning summary (lines 7868–7903)

This file is the single point of failure for the entire Python proxy. Any import error, any async initialization race, any attribute typo — the whole proxy is down. The file has grown organically from what was likely a focused proxy server into a monolith that manages every cross-cutting concern.

**Impact:** Onboarding difficulty, merge conflicts, debugging complexity, and a single-file blast radius for any regression.

### HIGH: Python/Rust compression pipeline duplication
**Files:** `cutctx/transforms/content_router.py` (Python) vs `cutctx-core/src/transforms/` (Rust)

Both runtimes implement content-type detection, SmartCrusher, LogCompressor, DiffCompressor, SearchCompressor, and tag protection. The PyO3 bridge wraps the Rust implementations so Python can call them, but the Python implementations still exist for:
1. Fallback when `_core.so` is not loaded
2. The Python proxy's hot path (which uses Python transforms unless explicitly swapped)
3. Parity testing

The `cutctx-parity` crate exists specifically to detect drift between these implementations. This is honest engineering, but the duplication surface is large (SmartCrusher alone is ~2,000 lines in each language).

**Risk:** A bug fix in one language doesn't automatically propagate to the other. The parity tests catch this, but they run in CI, not at dev time.

### HIGH: `deny.toml` is intentionally permissive
**File:** `deny.toml` (32 lines)

```toml
[bans]
multiple-versions = "allow"
wildcards = "allow"
```

The comment says "Intentionally permissive during Phase 0 — tighten before Phase 2 goes to production." The project is at v0.30.0 — well past Phase 0. Multiple version duplication and wildcard dependencies are allowed, which means:
- Security vulnerabilities in old versions won't be flagged
- Build times are longer due to duplicate compilation
- Binary size includes redundant crate versions

### MEDIUM: Auth/RBAC boundary is opaque
**Files:** `crates/cutctx-core/src/auth_mode.rs` vs `cutctx/rbac.py`

`auth_mode.rs` is a clean, well-tested, pure classifier (252 lines). But `rbac.py` is a 30-line shim that re-exports from `cutctx_ee.rbac` (commercial package). The actual RBAC implementation is invisible in the open-source codebase. This means:
- Community contributors cannot reason about the full auth flow
- The Python proxy's admin auth (lines 3400–3493 of `server.py`) calls into code that may not exist in the OSS build
- The Rust proxy has no RBAC equivalent — it only has `auth_mode` classification

### MEDIUM: Model router is Python-only
**File:** `cutctx/proxy/model_router.py` (705 lines)

The model routing logic (deciding when to downgrade opus→sonnet, gpt-4o→gpt-4o-mini) lives exclusively in Python. The Rust proxy has no equivalent. If the project moves toward a Rust-primary proxy, model routing will need to be ported or the Python proxy will remain the canonical request path.

---

## Quick Wins (fixable in <1 week)

1. **Split `server.py` into focused modules.** Extract:
   - `server.py` → FastAPI app creation + startup/shutdown lifecycle only (~500 lines)
   - `proxy/routes.py` → Route registration
   - `proxy/middleware.py` → Admin auth, SSO, MFA
   - `proxy/stats.py` → Stats endpoint logic
   - `proxy/startup.py` → Retention, webhooks, model router binding, stack-graph init
   - `proxy/compression_cache.py` → Compression cache management

2. **Tighten `deny.toml`.** Set `multiple-versions = "warn"` and `wildcards = "deny"`. Run `cargo deny` and fix the output. This catches stale deps before they become security issues.

3. **Add a Rust-side model router stub.** Even a `match` that returns `None` (no routing) establishes the pattern so the Rust proxy can route requests to cheaper models when Phase B compression is live-zone-only.

4. **Document the Python↔Rust feature matrix.** A table showing which compressors are available in Python, Rust, and via PyO3 would make the parity surface explicit.

---

## Detailed Analysis

### 1. System Design & Component Coupling

The architecture has three layers:

| Layer | Runtime | Responsibility | Entry Point |
|-------|---------|---------------|-------------|
| Proxy surface | Python (FastAPI) | Request routing, auth, admin, stats, dashboard | `cutctx/proxy/server.py` |
| Compression core | Rust (via PyO3) | Live-zone compression, CCR, tokenization | `cutctx-core/src/transforms/live_zone.rs` |
| Rust proxy | Rust (axum) | Transparent reverse proxy, compression gate, SSE | `crates/cutctx-proxy/src/proxy.rs` |

**How they connect:**

- **Python → Rust (in-process):** The Python proxy imports `cutctx._core` (built by maturin from `cutctx-py/src/lib.rs`). The `ContentRouter` in Python calls `cutctx._core.detect_content_type()`, `cutctx._core.SmartCrusher`, etc. This is the primary compression path today.

- **Rust → Rust (crates):** `cutctx-proxy` depends on `cutctx-core` via path dependency (`crates/cutctx-proxy/Cargo.toml:43`). The proxy calls `cutctx_core::auth_mode::classify()`, `cutctx_core::compression_policy::CompressionPolicy::for_mode()`, and the live-zone compression functions. The Rust proxy is a transparent reverse proxy that buffers requests, runs compression, and forwards to upstream.

- **Python ↔ Rust (proxy relationship):** The Python proxy and Rust proxy are **separate processes**. The Rust proxy (`cutctx-proxy/src/main.rs`) sits in front of the Python proxy as a transparent reverse proxy. It adds compression, header stripping, and SSE telemetry. The Python proxy handles the business logic (provider routing, CCR, admin, stats).

**Coupling assessment:** The coupling is clean. The PyO3 bridge has a well-defined API surface. The Rust proxy doesn't depend on Python at all. The main coupling risk is the Python proxy's dependency on `cutctx._core` — if the extension module fails to load, the proxy falls back to pure-Python transforms (which exist as fallbacks).

### 2. Dependency Graph

**Python (`pyproject.toml`):**
- Build system: maturin (≥1.5, <2.0) — appropriate for PyO3 extension modules
- Runtime deps are not listed in `pyproject.toml` (they're in the package's `__init__.py` or implicit)
- Dev deps: pytest ≥9.0.3, pytest-timeout ≥2.4.0, drain3 ≥0.9.11 — minimal and current
- Python ≥3.10 — reasonable floor

**Rust (`Cargo.toml` workspace):**
- `pyo3 = "0.21"` with `abi3-py310` — stable ABI for Python 3.10+, appropriate
- `serde_json` with `preserve_order` + `arbitrary_precision` + `raw_value` — all three features are load-bearing (documented in Cargo.toml comments)
- `tokio` with full async runtime features — appropriate
- `reqwest` with rustls-tls — no OpenSSL dependency, good for static linking
- AWS deps (`aws-sigv4`, `aws-config`, `gcp_auth`) — Phase D provider support
- `prometheus = "=0.13.4"` — pinned exactly for scrape contract stability

**Rust (`cutctx-core/Cargo.toml`):**
- `tiktoken-rs = "0.11"`, `tokenizers = "0.22"` — tokenization backends
- `dashmap = "6"` — concurrent CCR store
- `blake3` — CCR key computation
- `rayon` — parallel bloat estimation in pipeline orchestrator
- `fastembed = "5"` — ML-based content detection (platform-conditional)

**Rust (`cutctx-proxy/Cargo.toml`):**
- `axum = "0.7"` — HTTP framework
- `tower-http = "0.6"` — middleware
- `reqwest = "0.12"` — upstream HTTP client
- `tokio-tungstenite = "0.24"` — WebSocket support
- `opentelemetry = "0.27"` — enterprise observability

**Dependency health assessment:** Dependencies are generally current and well-chosen. The pinned `prometheus` version is a deliberate choice for contract stability. The `deny.toml` permissiveness is the main concern (see Critical Issues).

### 3. Phase B Readiness

Phase B = live-zone compression in the Rust proxy. Status:

**What works:**
- `cutctx-core/src/transforms/live_zone.rs` — the core live-zone dispatcher (3,289 lines). Walks Anthropic request shapes, identifies compressible blocks within the live zone, dispatches to content-specific compressors, rewrites via byte-range surgery.
- `crates/cutctx-proxy/src/compression/live_zone_anthropic.rs` — Anthropic `/v1/messages` dispatcher entry point (1,340 lines). Resolves frozen message count, calls `compress_anthropic_live_zone`, translates `LiveZoneOutcome` → `Outcome`.
- `crates/cutctx-proxy/src/compression/live_zone_openai.rs` — OpenAI Chat Completions `/v1/chat/completions` dispatcher (660 lines).
- `crates/cutctx-proxy/src/compression/live_zone_responses.rs` — OpenAI Responses `/v1/responses` dispatcher (678 lines).
- `crates/cutctx-proxy/src/compression/mod.rs` — path classification (`is_compressible_path`, `classify_compressible_path`) and `CompressibleEndpoint` enum.

**What's missing:**
- Google Gemini compression dispatcher — listed in the provider matrix as "follow-up"
- Bedrock native payload compression — the Bedrock handler (`crates/cutctx-proxy/src/bedrock/`) forwards but doesn't compress
- Vertex compression — similar to Bedrock

**What needs unblocking:**
- The `forward_http` function in `proxy.rs` (line 419) already dispatches to the correct live-zone compressor based on `classify_compressible_path`. The gate is wired. Adding a new provider means:
  1. Adding a new variant to `CompressibleEndpoint`
  2. Adding a path match in `classify_compressible_path`
  3. Implementing the walker in a new `live_zone_<provider>.rs` module
  4. Calling it from the dispatch block in `forward_http`

The Phase B compression infrastructure is **complete and operational** for Anthropic and OpenAI. The remaining work is provider-specific walker implementations, which are mechanical given the established pattern.

### 4. Cross-Cutting Concerns

**Auth flow:**
- **Rust proxy:** `auth_mode.rs` classifies requests into Payg/OAuth/Subscription based on headers. This is a pure function, no I/O. The `CompressionPolicy::for_mode()` maps the classification to compression decisions.
- **Python proxy:** Admin auth uses API key + SSO + MFA (lines 3400–3493 of `server.py`). RBAC is in `cutctx_ee` (commercial). The Python proxy also has provider-specific auth (Anthropic API key, OpenAI Bearer token, Gemini x-goog-api-key).
- **Gap:** The Rust proxy has no RBAC. If enterprise deployments need RBAC on the proxy layer, it would need to be added to `cutctx-proxy`.

**Audit logging:**
- **Python proxy:** `cutctx.audit.AuditEvent` is logged at system start (line 2352), auth events (lines 3406–3492), and presumably on request completion. The audit logger is `proxy.audit_logger`.
- **Rust proxy:** Observability is via Prometheus metrics (`observability/prometheus.rs`) and tracing spans. No structured audit log equivalent.
- **Gap:** Enterprise audit requirements may need a Rust-side structured audit emitter.

**Telemetry:**
- **Python proxy:** Savings tracking via `SavingsTracker`, stats endpoint, dashboard data.
- **Rust proxy:** Prometheus metrics (`observability/prometheus.rs`), OpenTelemetry integration (`observability/otel.rs`), compression ratio tracking (`observability/compression_ratio.rs`).
- **Assessment:** Telemetry is well-instrumented on both sides. The Rust proxy's Prometheus metrics are production-ready with cardinality discipline.

### 5. Extensibility

**Adding a new provider:**
- **Python proxy:** Add a handler mixin to `CutctxProxy`, register routes in `proxy_routes.py`. The `Provider` ABC in `providers/base.py` defines the contract. The `registry.py` maps providers to transport functions.
- **Rust proxy:** Add a variant to `CompressibleEndpoint`, implement `live_zone_<provider>.rs`, wire into `forward_http`. The `compression/mod.rs` module provides the extension point.
- **Assessment:** Both sides have clear extension points. The Python side is more flexible (route registration is dynamic); the Rust side requires code changes but the pattern is established.

**Adding a new compression algorithm:**
- **Rust:** Implement `ReformatTransform` or `OffloadTransform` from `pipeline/traits.rs`. Register with `CompressionPipelineBuilder`. The orchestrator handles gating and parallel execution.
- **Python:** Add a transform to `cutctx/transforms/`. The `ContentRouter` dispatches by content type.
- **Assessment:** The Rust pipeline is well-architected for extension. The Python side is more ad-hoc but functional.

**Adding a new storage backend:**
- Implement `CcrStore` trait from `ccr/mod.rs`. Three backends exist as templates (InMemory, SQLite, Redis).
- **Assessment:** Clean and well-documented.

### 6. Risk Spots

**Single Points of Failure:**
- `server.py` (7,903 lines) — any crash takes down the entire Python proxy
- `proxy.rs::forward_http` (line 419) — single function handles all request forwarding in the Rust proxy. A panic here would drop the connection (but tokio catches panics per-task).

**Untestable Coupling:**
- `CutctxProxy.__init__` (lines 461–845) creates 40+ instance attributes with complex initialization logic. Testing individual features requires constructing the entire proxy object.
- The `intelligence_pipeline` (line 479) is created during init and lives for the proxy's lifetime — hard to mock in isolation.

**Shared Mutable State:**
- `_compression_caches` (line 5668) is a dict guarded by `_compression_caches_lock` — thread-safe but a contention point under high concurrency.
- `_compression_executor` (line 740) is a `ThreadPoolExecutor` with configurable max workers — bounded, which is good, but the leaked-threads counter (line 759) indicates this has been a problem.

**Drift Risk:**
- The Python `CutctxProxy` class attributes (`ANTHROPIC_API_URL`, `OPENAI_API_URL`, etc.) are set as class-level constants (lines 455–459) but then overwritten in `__init__` (lines 485–489). This is a code smell — class attributes shouldn't be mutated per-instance.

---

## Phase B Status

### What works
- Live-zone block dispatcher for Anthropic (`live_zone_anthropic.rs`)
- Live-zone block dispatcher for OpenAI Chat (`live_zone_openai.rs`)
- Live-zone block dispatcher for OpenAI Responses (`live_zone_responses.rs`)
- Byte-range surgery for cache-safe compression
- Per-content-type compressor dispatch (SmartCrusher, LogCompressor, SearchCompressor, DiffCompressor)
- Tool array deterministic sorting (cache stabilization)
- Cache-control auto-frozen count resolution
- Compression policy per auth mode
- SSE state machine for streaming responses

### What's missing
- Google Gemini compression dispatcher
- Bedrock native payload compression
- Vertex compression
- Model routing in the Rust proxy (currently Python-only)
- Structured audit logging in the Rust proxy

### What needs unblocking
- Nothing structural. The Phase B infrastructure is complete. Remaining work is provider-specific walker implementations, which follow an established pattern.

---

## Summary

| Area | Status | Notes |
|------|--------|-------|
| Dual-runtime architecture | 🟢 Clean | PyO3 bridge is well-scoped, no IPC overhead |
| Live-zone compression | 🟢 Working | 3 providers wired, pattern established for more |
| Compression pipeline | 🟢 Extensible | Trait-based, parallel bloat estimation, CCR offload |
| Auth mode classification | 🟢 Sound | Pure function, per-mode policy, tested |
| CCR storage | 🟢 Pluggable | 3 backends, trait-based, BLAKE3 keys |
| `server.py` size | 🔴 7,903 lines | God object, needs decomposition |
| `deny.toml` permissiveness | 🟡 Phase 0 | Should be tightened for production |
| Python/Rust duplication | 🟡 Managed | Parity tests exist, but dual maintenance cost |
| RBAC boundary | 🟡 Opaque | Commercial-only, invisible in OSS |
| Model routing | 🟡 Python-only | Needs Rust port if proxy migrates |
