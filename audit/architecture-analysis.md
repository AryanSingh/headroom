# CutCtx Architecture Analysis

## System Overview

CutCtx is a local-first context compression plane for AI agents. It intercepts LLM API traffic, compresses expensive context (tool outputs, logs, diffs, JSON arrays), stores originals in a local CCR (Compress-Cache-Retrieve) store for reversibility, and tracks savings attribution. The system has three major runtime layers: a Rust binary proxy, a Python SDK/proxy, and a React dashboard.

## Component Inventory

| Component | Language | Location | Role |
|-----------|----------|----------|------|
| `cutctx-core` | Rust | `crates/cutctx-core/` | Compression algorithms, CCR store, tokenizer, auth-mode classification, transforms (SmartCrusher, LogCompressor, DiffCompressor, SearchCompressor, TagProtector) |
| `cutctx-proxy` | Rust | `crates/cutctx-proxy/` | Standalone reverse proxy binary (axum). SSE streaming, live-zone compression dispatch, Bedrock/Vertex native routes, license enforcement, observability |
| `cutctx-py` | Rust→Python | `crates/cutctx-py/` | PyO3 bridge exposing `cutctx-core` as `cutctx._core` for in-process Python calls |
| `cutctx-parity` | Rust | `crates/cutctx-parity/` | Python/Rust transform parity checker using JSON fixtures |
| Python SDK | Python | `cutctx/` | `CutctxClient`, config, pipeline, transforms, providers, pricing, telemetry, billing, security |
| Python proxy | Python | `cutctx/proxy/` | FastAPI server with per-provider handlers (Anthropic, OpenAI, Gemini, Bedrock) |
| Dashboard | React/Vite | `dashboard/` | Operator UI for savings, capabilities, governance, memory |

## Architecture: Dual-Path Design

The system operates in two distinct runtime modes that share no process boundary:

### Path 1: Python proxy (legacy, current production)

```
Agent → FastAPI proxy (cutctx/proxy/) → Python compression pipeline → LLM provider
                                    ↕
                            cutctx._core (PyO3)
                            cutctx-core (Rust)
```

The Python proxy is the primary production path. It runs FastAPI/Uvicorn, uses the Python `CutctxClient` for compression orchestration, and calls into Rust via `cutctx._core` for hot-path transforms (SmartCrusher, DiffCompressor, LogCompressor, SearchCompressor, TagProtector). The PyO3 bridge is in-process — no IPC overhead — which is critical since compression runs on every request.

### Path 2: Rust standalone proxy (new, incremental rollout)

```
Agent → axum proxy (cutctx-proxy) → Rust live-zone compression → LLM provider
                                  ↕
                          cutctx-core (direct dep)
                          CCR store (in-memory / SQLite / Redis)
```

The Rust proxy (`cutctx-proxy`) is a standalone binary that sits in front of either the Python proxy or directly in front of the LLM provider. It handles: live-zone compression dispatch (Anthropic, OpenAI chat, OpenAI responses), SSE streaming with state machines, Bedrock SigV4 signing, Vertex ADC auth, license enforcement with CRL/heartbeat, and cache-stabilization drift detection.

**Key architectural note:** The Rust proxy currently operates in a "Phase A lockdown" state — compression is passthrough (`CompressionMode::Off`) by default, with `CompressionMode::LiveZone` available but not yet fully wired. Phase B PR-B2 is planned to activate real compression.

## How Rust Connects to Python

The connection is **not** via network/RPC. Instead:

1. **PyO3 in-process bridge** (`cutctx-py`): The Python SDK imports `cutctx._core` (a cdylib built by maturin). This calls Rust functions directly in the Python process. The bridge exposes SmartCrusher, DiffCompressor, LogCompressor, SearchCompressor, TagProtector, and content detection.

2. **Standalone Rust proxy** (`cutctx-proxy`): This is a separate binary that can sit in front of the Python proxy (as a transparent reverse proxy) or directly in front of LLM providers. When deployed with `--upstream http://localhost:8787`, it proxies through the Python proxy. When `compression_mode=live_zone` is enabled, it does its own Rust-native compression.

3. **Parity crate** (`cutctx-parity`): A test harness that loads JSON fixtures from Python, runs the Rust port, and compares outputs. This ensures the two implementations agree.

## Auth/Config Flow

### Auth Mode Classification

A pure function (`classify` in `auth_mode.rs` / `classify_auth_mode` in `auth_mode.py`) inspects request headers to determine one of three modes:

- **Payg**: API key auth (Anthropic `x-api-key`, OpenAI `sk-*`, Gemini). Aggressive compression allowed.
- **OAuth**: Bearer token / IAM auth (Bedrock, Vertex, Claude Pro). Cache-safety paramount, lossless-only.
- **Subscription**: CLI/IDE with rate limits (Claude Code, Cursor). Stealth mode — preserve User-Agent, never inject `X-Cutctx-*`.

The Rust and Python implementations are kept in sync via parity tests. In the Rust proxy, the classified `AuthMode` is inserted into `req.extensions()` and read by downstream compression handlers.

### Configuration

- **Rust proxy**: CLI args via `clap` (`CliArgs`), parsed into `Config`. Key settings: `listen`, `upstream`, `compression_mode`, `cache_control_auto_frozen`, `enable_bedrock_native`, `ccr_backend`, `license_key`.
- **Python SDK**: `CutctxConfig` dataclass with `CacheAlignerConfig`, `SmartCrusherConfig`, `CompressionConfig`, `CacheConfig`, `ProviderConfig`, `PricingConfig`, `TelemetryConfig`, `SecurityConfig`, `MemoryConfig`, `BillingConfig`.
- **Environment variables**: Extensive env var support (`CUTCTX_*`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AWS_*`, `GCP_*`).

## Deployment Architecture

| Mode | What Runs | Storage |
|------|-----------|---------|
| Local pip | Python proxy + Rust via PyO3 | SQLite (CCR, memory) |
| Docker | Single container (~50MB) | SQLite, optional Qdrant + Neo4j |
| docker-compose | cutctx-proxy + qdrant + neo4j | Volumes for each |
| Kubernetes | Multiple proxy instances behind LB | Redis for shared CCR |

The `docker-compose.yml` includes Qdrant (vector DB for semantic search) and Neo4j (graph DB for relationships/multi-hop reasoning) — these are for the intelligence/memory layer, not core compression.

## Architectural Gaps and Observations

### 1. Dual Implementation Drift Risk

The auth-mode classifier exists in both Rust and Python with the same logic. The parity crate helps, but `SUBSCRIPTION_UA_PREFIXES` and `CLIENT_UA_MAP` must be kept synchronized manually. Any drift means different compression behavior between the two proxy paths.

### 2. Rust Proxy Compression Not Yet Active

The Rust proxy's `CompressionMode::LiveZone` is documented as "NOT YET IMPLEMENTED" — it falls through to passthrough with a warning. The actual live-zone dispatchers exist in `compression/live_zone_*.rs` but the `CompressionMode` enum gates them off. This means the Rust proxy currently adds latency (extra hop) without compression benefit when deployed in front of the Python proxy.

### 3. No Shared State Between Proxy Instances

The deployment docs explicitly state: "Each instance has its own CCR and memory store (isolated). No shared state between instances." The Redis CCR backend exists but is cfg-gated behind `feature = "redis"`. For horizontal scaling with shared CCR, operators must opt into Redis explicitly.

### 4. License Enforcement Complexity

The Rust proxy has a multi-layered license system: fingerprint binding, CRL refresh, heartbeat seat leases, clock rollback detection. This is orchestrated across `license/client.rs`, `license/fingerprint.rs`, and periodic tokio tasks in `main.rs`. The Python side has a separate `trial.py`, `seats.py`, `billing/` module. The two systems must agree on license state but communicate through the license API, not in-process.

### 5. Pipeline Extension System (Python Only)

The Python `PipelineExtensionManager` supports entry-point-based extensions (`cutctx.pipeline_extension` group) with lifecycle hooks (SETUP through RESPONSE_RECEIVED). The Rust proxy has no equivalent extension mechanism — compression logic is hardcoded per provider. If extensibility is needed in the Rust path, a plugin system would need to be designed.

### 6. Missing Auth-Mode Documentation File

The task referenced `docs/auth-modes.md` but this file does not exist. Auth-mode information is scattered across `auth_mode.rs`, `auth_mode.py`, `bedrock.md`, `enterprise-install.md`, and `REALIGNMENT/08-phase-F-auth-mode.md`. A consolidated doc would reduce onboarding friction.

## Summary

CutCtx is a well-structured dual-runtime system where Rust provides the performance-critical compression core and Python provides the orchestration, provider handling, and SDK surface. The PyO3 bridge is the key integration point — it's in-process, low-latency, and keeps the two worlds tightly coupled. The main architectural tension is the ongoing migration from the Python proxy to the Rust proxy, with the Rust path currently in a "lockdown" passthrough state awaiting Phase B activation. The parity crate and shared `auth_mode` logic are the primary mechanisms preventing implementation drift.
