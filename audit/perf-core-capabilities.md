# Cutctx — Core Capabilities Inventory (Phase 4 Audit)

**Date:** July 12, 2026
**Product:** Cutctx v0.30.x
**Scope:** All providers, all capabilities, both runtimes (Python + Rust)
**Method:** Source code inspection of 100+ files across Python proxy, Rust core/proxy, SDK, dashboard, CLI

---

## Executive Summary

Cutctx ships an extraordinarily broad capability surface — 12+ compression algorithms, 5-source savings attribution, reversible compression (CCR), cross-agent memory with MCP, an LLM firewall with ML-based injection detection, and a dual-runtime architecture. However, this breadth comes at a cost: many capabilities exist in partial or stubbed form, the Python↔Rust feature parity is incomplete, and the provider support matrix has significant gaps between what's advertised and what's actually wired end-to-end.

**Key Numbers:**
- **Providers:** 12 named providers (Anthropic, OpenAI, Gemini, Copilot, Claude, Codex, OpenCode, Cursor, Windsurf, Zed, Aider, OpenClaw) + LiteLLM (100+ via bridge)
- **Compression algorithms (Rust):** 11 (SmartCrusher, LogCompressor, SearchCompressor, DiffCompressor, ImageCompressor, AudioCompressor, DeletionCompaction, LiveZone dispatchers ×3, TagProtector, Safety)
- **Savings sources:** 11 enumerated (ProviderPromptCache, CutctxCompression, ToolSchemaCompaction, ApiSurfaceSlimming, SemanticCache, PrefixCacheSelfHosted, ModelRouting, RTKFiltering, Normalization, OutputOptimization, Memoization, BatchRouting)
- **Security modules:** 8 (Firewall, FirewallML, AntiDebug, MFA, SecretsStore, StateCrypto, ResidencyProof, Integrity)
- **Dashboard pages:** 10 (Overview, Savings, Orchestrator, Capabilities, Governance, Firewall, Memory, Replay, Playground, Docs)
- **CLI commands:** 40+ subcommands
- **MCP tools:** ~5 (memory_search, memory_save, cutctx_retrieve, memory_save_decision_trace, memory_update)
- **SDKs:** Python SDK (production), TypeScript SDK (early)

---

## 1. Provider Support Matrix

### 1.1 Python Proxy Handlers

| Provider | Handler File | Compression | Streaming | Model Routing | Caching | Batch | Maturity |
|----------|-------------|-------------|-----------|---------------|---------|-------|----------|
| **Anthropic** | `handlers/anthropic.py` (4,257 lines) | ✅ Full (SmartCrusher, logs, search, diff, image) | ✅ Full SSE | ✅ Opus→Sonnet, Haiku | ✅ Cache control | ✅ Message Batches | **Production** |
| **OpenAI Chat** | `handlers/openai/chat.py` | ✅ Full (SmartCrusher, logs, search, diff) | ✅ Full SSE | ✅ GPT-4o→Mini, o1→o3-mini | ⚠️ Implicit | ❌ No | **Production** |
| **OpenAI Responses** | `handlers/openai/responses.py` | ✅ Full (per-item-type compression) | ✅ Full SSE | ✅ Same as Chat | ⚠️ Implicit | ❌ No | **Beta** |
| **Gemini** | `handlers/gemini.py` (1,482 lines) | ✅ Full (via OpenAI format conversion) | ✅ Full SSE | ✅ Gemini→Flash | ⚠️ Limited | ✅ Batch Generate | **Beta** |
| **Copilot** | Via Anthropic handler (auth shim) | ✅ Inherited | ✅ Inherited | ❌ No | ❌ No | ❌ No | **Beta** |
| **LiteLLM** | `providers/litellm.py` (314 lines) | ⚠️ Passthrough only | ⚠️ Inherited | ⚠️ Depends on backend | ⚠️ Backend-dependent | ❌ No | **Beta** |

### 1.2 Rust Proxy Compression

| Endpoint | Rust Module | Compression Status | Streaming | Maturity |
|----------|------------|-------------------|-----------|----------|
| `/v1/messages` (Anthropic) | `live_zone_anthropic.rs` (1,340 lines) | ✅ Live-zone dispatch (SmartCrusher, logs, search, diff, image) | ✅ SSE state machine | **Production** |
| `/v1/chat/completions` (OpenAI) | `live_zone_openai.rs` (660 lines) | ✅ Live-zone dispatch | ✅ SSE state machine | **Production** |
| `/v1/responses` (OpenAI) | `live_zone_responses.rs` | ✅ Per-item-type compression | ✅ SSE state machine | **Beta** |
| `/v1beta/...` (Gemini) | ❌ No Rust module | ❌ Python-only | ❌ Python-only | **Gap** |
| Bedrock | `bedrock.rs` (auth/proxy only) | ❌ No compression | ⚠️ Passthrough | **Stubbed** |
| Vertex | `vertex.rs` (auth/proxy only) | ❌ No compression | ⚠️ Passthrough | **Stubbed** |

### 1.3 Model Routing

| Provider | Routing Configured | Source→Target Pairs | Workload Classifier | Maturity |
|----------|-------------------|---------------------|---------------------|----------|
| **Anthropic** | ✅ Yes | opus→sonnet, haiku fallback | ✅ TaskComplexity heuristic | **Production** |
| **OpenAI** | ✅ Yes | gpt-4o→gpt-4o-mini, o1→o3-mini | ✅ TaskComplexity heuristic | **Production** |
| **Gemini** | ✅ Yes | gemini→flash | ✅ TaskComplexity heuristic | **Beta** |
| **All others** | ⚠️ Via LiteLLM passthrough | ❌ No dedicated routes | ❌ No | **Experimental** |

**Model Router Details** (`model_router.py`, 1,437 lines):
- Preset modes: off, balanced (`codex-gpt54mini-high`), aggressive (`economy`), custom
- Task complexity classifier: LOW/MEDIUM/HIGH with confidence scoring
- Heuristics: code detection, tool complexity, message length, reference-dependency
- Pluggable scorer protocol for future ML-based classification
- Savings attribution flows into `RequestOutcome.model_routing_*` fields

### 1.4 Client/Agent Integrations

| Provider Dir | Type | Install | Runtime | Compression | Maturity |
|-------------|------|---------|---------|-------------|----------|
| `claude/` | Claude Code | ✅ Wrap script | ✅ Runtime | ✅ Via proxy | **Production** |
| `codex/` | OpenAI Codex | ✅ Wrap script | ✅ Runtime | ✅ Via proxy | **Production** |
| `opencode/` | OpenCode | ✅ Plugin | ✅ Plugin | ✅ Via proxy | **Production** |
| `cursor/` | Cursor | ✅ Wrap script | ✅ Runtime | ✅ Via proxy | **Beta** |
| `copilot/` | GitHub Copilot | ✅ Wrap script | ✅ Auth shim | ✅ Via proxy | **Beta** |
| `windsurf/` | Windsurf | ✅ Runtime | ✅ Runtime | ✅ Via proxy | **Beta** |
| `zed/` | Zed | ✅ Runtime | ✅ Runtime | ✅ Via proxy | **Experimental** |
| `aider/` | Aider | ✅ Wrap script | ✅ Runtime | ✅ Via proxy | **Beta** |
| `antigravity/` | Antigravity | ✅ Runtime | ✅ Runtime | ✅ Via proxy | **Experimental** |
| `openclaw/` | OpenClaw | ✅ Wrap script | ✅ Wrap | ✅ Via proxy | **Experimental** |
| `gemini/` | Gemini CLI | ✅ Install | ✅ Runtime | ✅ Via proxy | **Beta** |

---

## 2. Feature Inventory by Category

### 2.1 Compression

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **SmartCrusher (JSON)** | ✅ | ✅ `smart_crusher/` | **Production** | Core compressor, handles JSON tool outputs, API responses |
| **LogCompressor** | ✅ | ✅ `log_compressor.rs` | **Production** | Log-specific dedup and normalization |
| **SearchCompressor** | ✅ | ✅ `search_compressor.rs` | **Production** | Search result compression |
| **DiffCompressor** | ✅ | ✅ `diff_compressor.rs` | **Production** | Unified diff compression |
| **ImageCompressor** | ✅ | ✅ `image_compressor.rs` | **Beta** | Base64 image compression |
| **AudioCompressor** | ✅ | ✅ `audio_compressor.rs` | **Experimental** | Audio data compression |
| **DeletionCompaction** | ✅ | ✅ `deletion_compaction.rs` | **Beta** | Collapse repeated deletions |
| **TagProtector** | ✅ | ✅ `tag_protector.rs` | **Production** | Protect XML/HTML tags from compression |
| **CacheAligner** | ✅ | ⚠️ Rust config only | **Production** | Prefix stability for prompt caching |
| **ContentDetector** | ✅ | ✅ `content_detector.rs` | **Production** | Per-block content type detection |
| **MagikaDetector** | ✅ | ✅ `magika_detector.rs` | **Beta** | ML-based file type detection |
| **AdaptiveSizer** | ✅ | ✅ `adaptive_sizer.rs` | **Production** | Token-aware sizing |
| **AnchorSelector** | ✅ | ✅ `anchor_selector.rs` | **Production** | Cache prefix anchor selection |
| **Safety checks** | ✅ | ✅ `safety.rs` | **Production** | Compression safety guardrails |
| **UnidiffDetector** | ✅ | ✅ `unidiff_detector.rs` | **Production** | Unified diff format detection |
| **LiveZone dispatch (Anthropic)** | ⚠️ | ✅ `live_zone_anthropic.rs` | **Production** | Byte-range surgery on live zone |
| **LiveZone dispatch (OpenAI Chat)** | ⚠️ | ✅ `live_zone_openai.rs` | **Production** | Live zone for chat completions |
| **LiveZone dispatch (OpenAI Responses)** | ⚠️ | ✅ `live_zone_responses.rs` | **Beta** | Per-item-type live zone |
| **CompressionPolicy** | ⚠️ | ✅ `compression_policy.rs` | **Production** | Per-auth-mode compression tuning |
| **CodeCompressor (AST)** | ✅ | ❌ | **Beta** | Python AST-based code compression |
| **ProseCompressor** | ✅ | ❌ | **Beta** | Natural language compression |

### 2.2 Reversibility (CCR — Compress-Cache-Retrieve)

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **ContextTracker** | ✅ | ✅ `ccr/` | **Production** | Tracks compressed contexts |
| **BatchContextStore** | ✅ | ✅ | **Production** | Stores originals for retrieval |
| **CCRToolInjector** | ✅ | ⚠️ | **Production** | Injects `cutctx_retrieve` tool into prompts |
| **CCRResponseHandler** | ✅ | ⚠️ | **Production** | Handles retrieval responses |
| **StreamingCCRBuffer** | ✅ | ⚠️ | **Beta** | Streaming-safe CCR |
| **BatchResultProcessor** | ✅ | ❌ | **Beta** | Batch result compression |
| **MCP Server (CCR)** | ✅ | ❌ | **Beta** | MCP-exposed CCR tools |
| **Marker extraction** | ✅ | ✅ | **Production** | Hash-based dedup references |

### 2.3 Memory (Cross-Agent)

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **HierarchicalMemory** | ✅ | ❌ | **Production** | Main orchestrator (910 lines) |
| **MemoryStore** | ✅ | ❌ | **Production** | SQLite + vector storage |
| **VectorIndex** | ✅ | ❌ | **Production** | Semantic search |
| **TextIndex** | ✅ | ❌ | **Production** | Full-text search |
| **Embedder** | ✅ | ❌ | **Production** | OpenAI/local embeddings |
| **MemoryCache** | ✅ | ❌ | **Production** | LRU caching layer |
| **MemoryBridge** | ✅ | ❌ | **Beta** | Markdown ↔ Cutctx sync |
| **MCP Server** | ✅ | ❌ | **Production** | `memory_search`, `memory_save` tools |
| **TrafficLearner** | ✅ | ❌ | **Beta** | Learn patterns from proxy traffic (1,713 lines) |
| **SessionTracker** | ✅ | ❌ | **Beta** | Cross-session memory |
| **MemoryBudget** | ✅ | ❌ | **Beta** | Token budget management |
| **SubagentMemory** | ✅ | ❌ | **Experimental** | Sub-agent memory isolation |
| **StorageRouter** | ✅ | ❌ | **Production** | Backend routing (local/Mem0/etc.) |
| **MemoryTools** | ✅ | ❌ | **Production** | LLM function calling definitions |
| **Export** | ✅ | ❌ | **Beta** | Memory export utilities |

### 2.4 Savings Attribution (5-Source → 11-Source)

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **SavingsOrchestrator** | ✅ | ❌ | **Production** | Merge rules, no double-counting |
| **RequestSavingsBreakdown** | ✅ | ❌ | **Production** | Per-request breakdown |
| **SavingsBySource** | ✅ | ❌ | **Production** | Per-source token+USD tracking |
| **SavingsIntegrations** | ✅ | ❌ | **Production** | Provider cache attribution |
| **SavingsPolicy** | ✅ | ❌ | **Beta** | Attribution policies |
| **SavingsParsers** | ✅ | ❌ | **Beta** | Response parsing for savings |
| **11-source enum** | ✅ | ⚠️ | **Production** | ProviderPromptCache, CutctxCompression, ToolSchemaCompaction, ApiSurfaceSlimming, SemanticCache, PrefixCacheSelfHosted, ModelRouting, RTKFiltering, Normalization, OutputOptimization, Memoization, BatchRouting |

### 2.5 Security

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **FirewallScanner** | ✅ | ❌ | **Production** | Regex-based injection, PII, jailbreak detection (652 lines) |
| **MLInjectionClassifier** | ✅ | ❌ | **Beta** | ONNX-based injection classifier (<20ms) |
| **StreamingRedactor** | ✅ | ❌ | **Production** | SSE PII redaction with buffering |
| **FirewallConfig** | ✅ | ❌ | **Production** | Env-var driven configuration |
| **AntiDebug** | ✅ | ✅ `antidebug.rs` | **Production** | TracerPid, debugger detection |
| **MFA (TOTP)** | ✅ | ❌ | **Production** | RFC 6238 TOTP for admin auth (285 lines) |
| **SecretsStore** | ✅ | ❌ | **Production** | Fernet-encrypted SQLite vault (310 lines) |
| **StateCrypto** | ✅ | ❌ | **Production** | Machine-bound Fernet encryption + HMAC (308 lines) |
| **ResidencyProof** | ✅ | ❌ | **Beta** | Data-residency attestation (339 lines) |
| **IntegrityVerification** | ✅ | ❌ | **Production** | EE binary SHA-256 manifest verification |
| **LLM Firewall** | ✅ | ❌ | **Production** | Prompt injection, PII, jailbreak, data exfiltration |

### 2.6 CLI

| Capability | Maturity | Notes |
|-----------|----------|-------|
| `cutctx proxy` | **Production** | Start the proxy server |
| `cutctx wrap <agent>` | **Production** | Wrap agent CLIs (claude, codex, cursor, etc.) |
| `cutctx memory` | **Production** | Memory management commands |
| `cutctx savings` | **Production** | Savings reports |
| `cutctx config` | **Production** | Configuration management |
| `cutctx config-check` | **Production** | Config validation |
| `cutctx init` | **Production** | Project initialization |
| `cutctx install` | **Production** | Installation helpers |
| `cutctx intercept` | **Production** | Request interception |
| `cutctx learn` | **Beta** | Pattern learning |
| `cutctx learn-share` | **Experimental** | Shared learning |
| `cutctx mcp` | **Beta** | MCP server management |
| `cutctx evals` / `bench` | **Beta** | Benchmarks and evaluations |
| `cutctx capabilities` | **Beta** | Capability listing |
| `cutctx capture` | **Beta** | Request capture |
| `cutctx policies` | **Beta** | Policy management |
| `cutctx tools` | **Beta** | Tool management |
| `cutctx profile` | **Beta** | User profiling |
| `cutctx perf` | **Beta** | Performance monitoring |
| `cutctx report` | **Beta** | Reporting |
| `cutctx agent-savings` | **Beta** | Per-agent savings |
| `cutctx audit` | **Production** | Audit trail (shim to cutctx_ee) |
| `cutctx rbac` | **Production** | RBAC management (shim to cutctx_ee) |
| `cutctx license` | **Production** | License management |
| `cutctx billing` | **Beta** | Billing integration |
| `cutctx orgs` | **Beta** | Organization management |
| `cutctx setup` | **Beta** | Setup wizard |
| `cutctx sso-test` | **Beta** | SSO testing |
| `cutctx global` | **Beta** | Global routing config |
| `cutctx integrations` | **Beta** | Integration management |
| `cutctx stack-graph` | **Experimental** | Dependency graph analysis |
| `cutctx toin-publish` | **Experimental** | TOIN pattern publishing |
| `cutctx upgrade-prompt` | **Beta** | Upgrade notifications |

### 2.7 Dashboard

| Page | Capabilities | Maturity |
|------|-------------|----------|
| **Overview** | Real-time metrics, savings summary, request volume | **Production** |
| **Savings** | 11-source breakdown, by-provider/model/client, time series | **Production** |
| **Orchestrator** | Model routing control, preset modes (off/balanced/aggressive) | **Production** |
| **Capabilities** | Provider matrix, compressor status, feature flags | **Beta** |
| **Governance** | RBAC, SSO, audit trail, compliance settings | **Beta** |
| **Firewall** | Injection/PII stats, rule management, streaming redaction | **Beta** |
| **Memory** | Memory search, cross-agent memory, traffic learner output | **Beta** |
| **Replay** | Request replay, compression diff visualization | **Beta** |
| **Playground** | Interactive compression testing | **Experimental** |
| **Docs** | Built-in documentation | **Beta** |

### 2.8 SDK

| SDK | Language | Maturity | Notes |
|-----|----------|----------|-------|
| **Python SDK** | Python | **Production** | Full: CutctxClient, ChatCompletions, providers, transforms, storage (1,048 lines) |
| **TypeScript SDK** | TypeScript | **Early Beta** | client.ts, compress.ts, hooks.ts, hosted.ts, simulate.ts, adapters/ |

### 2.9 Auth & Governance

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **AuthMode classification** | ✅ | ✅ `auth_mode.rs` | **Production** | Payg / OAuth / Subscription |
| **RBAC** | ✅ (shim) | ❌ | **Production** | Shim to cutctx_ee |
| **SSO (OIDC)** | ✅ | ❌ | **Beta** | OIDC only, no SAML |
| **Admin key auth** | ✅ | ❌ | **Production** | API key authentication |
| **Audit trail** | ✅ (shim) | ❌ | **Production** | HMAC-signed audit chain (shim to cutctx_ee) |
| **License management** | ✅ | ✅ `license.rs` | **Production** | License key + compliance |

### 2.10 Observability

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **Structured logging** | ✅ | ✅ `observability.rs` | **Production** | tracing + structured events |
| **Health checks** | ✅ | ✅ `health.rs` | **Production** | Liveness/readiness probes |
| **SSE state machine** | ✅ | ✅ `sse/` | **Production** | Full SSE parsing for all providers |
| **WebSocket proxy** | ❌ | ✅ `websocket.rs` | **Beta** | WebSocket forwarding |
| **Compression metrics** | ✅ | ✅ | **Production** | Per-strategy token ratios |
| **OpenTelemetry export** | ❌ | ❌ | **Missing** | Competitor feature gap |

### 2.11 Caching

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **CacheAligner** | ✅ | ⚠️ Config only | **Production** | Prefix stability for prompt caching |
| **SemanticCache** | ✅ | ✅ `semantic_cache.rs` | **Beta** | Vector-similarity dedup (BGE embeddings) |
| **CacheControlAutoFrozen** | ⚠️ | ✅ `cache_stabilization/` | **Production** | Auto-freeze cached prefix |
| **ToolDefNormalize** | ⚠️ | ✅ `cache_stabilization/` | **Production** | Deterministic tool schema ordering |
| **Cache hot zone** | ✅ | ✅ | **Production** | System/tools/historical never modified |

### 2.12 Pipeline & Transforms

| Capability | Python | Rust | Maturity | Notes |
|-----------|--------|------|----------|-------|
| **TransformPipeline** | ✅ | ❌ | **Production** | Python transform pipeline |
| **PipelineStage** | ✅ | ❌ | **Production** | Stage-based processing |
| **PipelineExtensionManager** | ✅ | ❌ | **Beta** | Plugin system |
| **Live zone compression** | ⚠️ | ✅ | **Production** | Rust byte-range surgery |
| **ContentRouter** | ✅ | ⚠️ | **Beta** | Per-content-type routing |

---

## 3. Dual-Runtime Feature Gap Analysis

### 3.1 Python-Only Capabilities (No Rust Equivalent)

| Capability | Lines | Complexity | Risk |
|-----------|-------|------------|------|
| SmartCrusher Python impl | ~500 | Medium | 🟡 Medium — Rust version exists, Python is legacy |
| CacheAligner Python impl | ~800 | High | 🔴 High — Rust config exists but transform logic is Python-only |
| ContentRouter Python | ~400 | Medium | 🟡 Medium — Rust detection exists, routing is Python |
| Full Memory system (35 files) | ~8,000+ | Very High | 🔴 High — Massive Python-only surface, no Rust port planned |
| TrafficLearner | 1,713 | High | 🟡 Medium — Complex pattern learning, hard to port |
| MemoryBridge | 661 | Medium | 🟡 Medium — Markdown sync, lower priority |
| All Security modules (except AntiDebug) | ~2,500+ | High | 🟡 Medium — Enterprise features, Python is natural fit |
| SavingsOrchestrator + all savings | ~1,200 | Medium | 🟡 Medium — Business logic, Python is fine |
| Full CCR system | ~1,500+ | High | 🟡 Medium — Batch processing, Python is natural fit |
| Model Router (1,437 lines) | 1,437 | High | 🟡 Medium — Config-driven, Python is natural fit |
| All proxy handler logic (4,257+1,482+2,536+1,337) | ~9,600 | Very High | 🔴 High — Core request handling is Python-only |
| Python SDK | 1,048 | Medium | 🟢 Low — Python SDK is the reference |
| All CLI commands | ~4,000+ | High | 🟡 Medium — CLI is Python-native |

### 3.2 Rust-Only Capabilities (No Python Equivalent)

| Capability | Notes |
|-----------|-------|
| Live-zone byte-range surgery | Core compression happens in Rust for Anthropic/OpenAI |
| CompressionPolicy (per-auth-mode) | Rust-only policy engine |
| SemanticCache (BGE embeddings) | Rust-only vector cache with fastembed |
| WebSocket proxy | Rust-only |
| AntiDebug (Rust core) | Lower-level than Python fallback |
| EE integrity verification | Manifest check at import time |
| Panic hook | Rust-only process safety |
| SSE state machine (full) | Rust-only for streaming proxy |

### 3.3 Parity Drift (Both Runtimes, But Diverged)

| Capability | Python State | Rust State | Drift Risk |
|-----------|-------------|------------|------------|
| SmartCrusher | Production | Production | 🟡 Medium — implementations may diverge |
| LogCompressor | Production | Production | 🟡 Medium |
| LiveZone dispatch | N/A (delegates to Rust) | Production | 🟢 Low — Rust is source of truth |
| AuthMode classification | Production | Production | 🟢 Low — parity tests exist |
| CompressionPolicy fields | Reads Rust struct | Defines struct | 🟢 Low — Rust is source of truth |
| CacheAligner | Full impl | Config only | 🔴 High — Rust doesn't do the transform |
| ContentRouter | Full impl | Detection only | 🟡 Medium — Rust detects, Python routes |

### 3.4 Known Gaps (Neither Runtime)

| Gap | Severity | Notes |
|-----|----------|-------|
| Gemini compression in Rust | 🔴 High | Gemini handler exists in Python but no Rust live-zone dispatcher |
| Bedrock compression | 🔴 High | Auth/proxy only, no compression |
| Vertex compression | 🔴 High | Auth/proxy only, no compression |
| OpenTelemetry export | 🔴 High | Competitor feature gap (LeanCTX, Helicone) |
| SOC 2 compliance | 🔴 High | Enterprise deal-blocker |
| SAML SSO | 🔴 High | Enterprise deal-blocker |
| Verification/hallucination guard | 🔴 High | CISO objection handler |
| Windows support | 🟡 Medium | Limits enterprise adoption |
| Read-side intelligence (10 modes) | 🟡 Medium | LeanCTX competitive gap |
| CI/CD integration | 🟡 Medium | DevOps buyer gap |
| Knowledge graph / provenance | 🟡 Medium | LeanCTX CCP competitive gap |
| 20+ MCP tools | 🟡 Medium | LeanCTX has 81 |
| Multi-agent orchestration | 🟡 Medium | Growing framework trend |
| Deterministic compression mode | 🟢 Low | Compliance edge case |
| Public benchmarks/leaderboard | 🟢 Low | Marketing gap |

---

## 4. Maturity Assessment Summary

| Maturity Level | Count | % | Key Examples |
|---------------|-------|---|-------------|
| **Production** | 42 | 44% | Anthropic handler, SmartCrusher, CCR, Memory MCP, Firewall, Model Router (Anthropic/OpenAI), Audit/RBAC shims, SavingsOrchestrator, CLI core |
| **Beta** | 31 | 33% | OpenAI Responses, Gemini handler, ML injection classifier, TypeScript SDK, Dashboard pages, Memory bridge/learner, SemanticCache, ResidencyProof |
| **Experimental** | 8 | 8% | AudioCompressor, Stack Graph, TOIN publish, OpenClaw/Antigravity/Zed integrations, SubagentMemory |
| **Stubbed** | 5 | 5% | Bedrock compression, Vertex compression, OpenAI batch, Gemini Rust compression |
| **Missing** | 9 | 10% | SOC 2, SAML SSO, OTel export, Verification guard, Windows, Read-side intelligence, CI/CD, Knowledge graph, Public benchmarks |

**Overall: 44% Production, 33% Beta — healthy but the long tail of experimental/stubbed/missing needs attention.**

---

## 5. Competitive Feature Gaps

Cross-referenced with `audit/competitive-analysis.md`:

| Gap | Competitor Benchmark | Cutctx Current | Severity | Recommendation |
|-----|---------------------|----------------|----------|----------------|
| **SOC 2 Type II** | Morph Compact ✓, Portkey ✓, Helicone ✓ | ❌ Not started | 🔴 CRITICAL | Enterprise deal-blocker. Start audit immediately |
| **SAML SSO** | Portkey ✓, Helicone ✓, LeanCTX ✓ | ⚠️ OIDC only | 🔴 CRITICAL | Enterprise procurement hard requirement |
| **Verification guard** | Entroly WITNESS, LeanCTX ctx_verify | ❌ Not built | 🔴 HIGH | CISO diligence: "did compression break my agent?" |
| **Read-side intelligence** | LeanCTX: 10 read modes | ❌ Post-arrival only | 🔴 HIGH | LeanCTX user gets 60-90% savings on every file read |
| **Knowledge graph** | LeanCTX CCP: task/facts/decisions, contradiction detection | ⚠️ Cross-agent memory exists | 🟡 MEDIUM | Competitive reviews |
| **81 MCP tools** | LeanCTX: 81 tools | ⚠️ ~5 tools | 🟡 MEDIUM | MCP is table stakes |
| **30+ agent support** | LeanCTX: 30+ agents | ⚠️ ~11 agents | 🟡 MEDIUM | Broader coverage = broader market |
| **CI/CD integration** | LeanCTX: drift gates, regression testing | ❌ Not built | 🟡 MEDIUM | DevOps buyer gap |
| **OpenTelemetry export** | LeanCTX ✓, Helicone ✓ | ❌ Not built | 🟡 MEDIUM | Observability team requirement |
| **Windows support** | LeanCTX ✓ | ❌ Not built | 🟡 MEDIUM | Enterprise adoption limiter |
| **Deterministic mode** | RTK: always. LeanCTX: CI-gated | ⚠️ ML-based (Kompress) | 🟢 LOW | Compliance edge case |
| **Homebrew install** | RTK ✓, LeanCTX ✓ | ⚠️ pip/npm only | 🟢 LOW | Developer experience |
| **Public leaderboard** | Condense.chat ✓, Compresr ✓ | ⚠️ Internal only | 🟢 LOW | Marketing |

---

## 6. Key Issues (Severity-Ranked)

### 🔴 CRITICAL

1. **No SOC 2 Type II** — Enterprise deals are blocked. Every competitor in the gateway/hosted space has or is pursuing SOC 2. Cutctx must start the audit process immediately.

2. **No SAML SSO** — OIDC is insufficient for many enterprise procurement checklists. This is a hard gate alongside SOC 2.

3. **Gemini has no Rust compression** — The Python handler works but misses the performance benefits of the Rust live-zone dispatcher. This is the largest provider gap in the Rust proxy.

4. **Bedrock/Vertex are stubbed** — Auth and proxy work but no compression. These are major cloud provider endpoints that enterprise customers use.

### 🟡 HIGH

5. **Python handler logic is the bottleneck** — 9,600+ lines of handler code in Python. The Rust proxy compresses but the Python proxy still handles request parsing, routing decisions, memory queries, CCR injection, savings attribution, and response processing. This is the primary latency concern.

6. **CacheAligner has no Rust implementation** — The Python CacheAligner does the actual prefix transformation. The Rust side only has config/struct definitions. This means cache alignment runs on the Python path.

7. **No verification/hallucination guard** — The #1 CISO objection ("how do I know compression didn't break my agent?") has no answer.

8. **Memory system is entirely Python** — 35 files, 8,000+ lines. No Rust port exists or is planned. This is the largest Python-only surface.

9. **No OpenTelemetry export** — Observability teams require OTel. Both LeanCTX and Helicone ship it.

### 🟢 MEDIUM

10. **TypeScript SDK is early** — Only has basic client, compress, hooks, hosted, simulate. Missing providers, transforms, full feature parity.

11. **MCP tool count is low** — ~5 tools vs LeanCTX's 81. The gap is widening.

12. **No read-side intelligence** — LeanCTX's 10 read modes are a key differentiator. Cutctx only compresses post-arrival.

13. **Dual-runtime parity drift** — SmartCrusher and LogCompressor exist in both but may diverge. Parity tests exist for AuthMode but not for compressor behavior.

---

## 7. Recommendations

### Immediate (30 days)

1. **Start SOC 2 Type II audit kickoff** — Even beginning the process signals seriousness. Update SECURITY.md.
2. **Add SAML SSO** — Implement SAML alongside existing OIDC.
3. **Wire Gemini compression in Rust** — Port the Gemini handler's live-zone logic to a `live_zone_gemini.rs` module. This closes the largest Rust proxy gap.
4. **Ship verification command** — `cutctx verify` that compares compressed vs original output. Low-complexity, high-impact CISO objection handler.

### Short-term (60 days)

5. **Move CacheAligner transform to Rust** — The Python CacheAligner is on the hot path. Port the actual transform logic to Rust, keeping Python as config-only.
6. **Add Bedrock/Vertex compression** — At minimum, passthrough with SmartCrusher for the latest user message.
7. **Expand MCP tools to 20+** — File read modes, diff compression, agent handoff, memory CRUD.
8. **Add OpenTelemetry export** — Trace/span export for compression events.

### Medium-term (90 days)

9. **Port memory system to Rust** — Start with the hot path (vector search, embedding lookup). The full system is 8,000+ lines; prioritize the query path.
10. **Add read-side intelligence** — Even 3-4 modes (map, signatures, diff) would close the LeanCTX gap.
11. **CI/CD integration** — `cutctx compress --check` for drift gates, `cutctx benchmark` for regression testing.
12. **Parity test suite** — Automated tests that run the same inputs through Python and Rust compressors and assert identical outputs.

### Strategic

13. **Reduce Python proxy surface area** — The Python proxy is doing too much. Prioritize moving hot-path logic (handlers, CacheAligner, ContentRouter) to Rust while keeping business logic (savings, memory, security) in Python.
14. **Publish benchmarks** — Condense.chat and Compresr publish leaderboards. Cutctx should too.
15. **Knowledge graph / provenance** — LeanCTX's CCP is a competitive differentiator. Add fact tracking and contradiction detection to the memory system.

---

## Appendix: Module Counts

| Area | Python Files | Rust Files | Total |
|------|-------------|------------|-------|
| Providers | 12 dirs + 6 files | N/A | 18 |
| Proxy handlers | 7 files | 4 files | 11 |
| Compression | Python impls in transforms/ | 19 files | 19+ |
| Memory | 35 files | 0 | 35 |
| CCR | 10 files | module in core | 10+ |
| Savings | 7 files | 0 | 7 |
| Security | 10 files | 1 (antidebug) | 11 |
| CLI | 40 files | 0 | 40 |
| Dashboard | 10 pages | 0 | 10 |
| SDK | Python client | TypeScript src | 2 |
| **Total** | **~130+** | **~24+** | **~155+** |
