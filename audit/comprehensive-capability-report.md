# Headroom v0.28.0 — Comprehensive Product Capability Report

**Date:** 2026-06-29 (Updated)  
**Method:** Read-only audit of full codebase across 5 parallel deep-dive lanes  
**Previous report superseded by this update reflecting fixes applied since initial audit.**

---

## Executive Summary

Headroom is an open-core (Apache 2.0 + Proprietary EE) context optimization layer for AI coding agents, shipping as a Python+Rust proxy, CLI, SDK, MCP server, IDE extensions, and React dashboard. It serves as a MITM proxy for LLM API calls, compressing both input and output tokens across 17 compression strategies, with lossless reversible compression (CCR), cross-agent memory, and enterprise governance.

**7,289 tests pass, 87 pre-existing failures, 249 skipped.**  
**57 manual testing sections: 157 pass, 1 fail (JetBrains CI config), 11 skipped (GUI/API-key only).**

---

## 1. Architecture Overview

```
LLM Client (Claude Code, Codex, Cursor, etc.)
    │
    ▼
Cutctx Proxy (FastAPI + uvicorn, default :8787)
    │
    ├─ Middleware: Rate limiter, Firewall, Trial enforcement, CORS
    │
    ├─ Transform Pipeline:
    │   [1] CacheAligner (configurable)
    │   [2] ToolResultInterceptorTransform (ast-grep / difft / graphify)
    │   [3] ContentRouter (17 strategies)
    │
    ├─ Handlers: Anthropic / OpenAI / Gemini / Cloud Code / Batch
    ├─ Memory: Local (SQLite+HNSW+FTS5) / Qdrant-Neo4j
    ├─ CCR: Reversible compression with retrieval tool
    ├─ Admin API: 79+ endpoints (RBAC/audit/orgs/fleet/SCIM/secrets/MFA)
    └─ Observability: OTEL, Prometheus, Langfuse, Dashboard SPA
        │
        ▼
    Upstream LLM Provider (Anthropic / OpenAI / Gemini / Bedrock / LiteLLM)
```

**Runtime:** Python 3.10+ with Rust `_core.so` (hard dep — `sys.exit(78)` if missing)  
**Entry:** `cutctx` CLI (Click), `cutctx proxy` (main server, ~100 flags), `cutctx wrap` (14 agents)  
**Package:** `cutctx-ai` on PyPI, 24 optional extra groups  
**EE:** `cutctx-ee` (proprietary, compiled Cython .so)  

---

## 2. Product Capability Map

### 2.1 Compression Pipeline (17 Strategies)

| Feature | Status | CLI Flag | Env Var | Notes |
|---------|--------|----------|---------|-------|
| ContentRouter | ✅ Always active | — | — | Routes by content type, 3-tier fallback chains |
| SmartCrusher (JSON) | ✅ Active (Rust) | — | — | Lossless + compact table + CCR sentinels |
| CodeCompressor (AST) | ⚠️ Opt-in (tree-sitter) | `--code-aware` | `CUTCTX_CODE_AWARE_ENABLED` | 8 languages |
| LogCompressor | ✅ Active (Rust) | — | — | 6 log formats |
| SearchCompressor | ✅ Active (Rust) | — | — | grep/ripgrep output |
| DiffCompressor | ✅ Active (Rust+Python) | — | — | 40-70% line reduction |
| Kompress (ML) | ✅ Active (ModernBERT) | `--disable-kompress` | `CUTCTX_DISABLE_KOMPRESS` | ONNX INT8, 8K context |
| CompactTable | ✅ Active | — | — | JSON arrays→tables |
| HTMLExtractor | ⚠️ Opt-in | — | — | `pip install cutctx-ai[html]` |
| SelectiveFilter | ⚠️ Opt-in | `--selective-filter` | `CUTCTX_SELECTIVE_FILTER` | BM25 message pruning |
| QueryAware | ⚠️ Opt-in | `--query-aware` | `CUTCTX_QUERY_AWARE` | Task-adaptive ratios |
| Drain3 (ML logs) | ⚠️ Opt-in | `--drain3` | `CUTCTX_DRAIN3` | `[log-ml]` extra |
| Difftastic (diffs) | ⚠️ Opt-in | `--difftastic` | `CUTCTX_DIFFTASTIC` | Binary auto-fetch |
| Graphify (KG) | ⚠️ Opt-in | `--knowledge-graph` | `CUTCTX_KNOWLEDGE_GRAPH` | `[knowledge-graph]` extra |
| LLMLingua-2 | 🟡 Optional | `--llmlingua` | `CUTCTX_USE_LLMLINGUA` | Code live + pyproject extra; some docs were stale |
| Audio | 🟡 Pass-through only | — | — | Logs payload size; no actual compression |
| Image | ✅ Active (ML router) | — | — | 40-90% reduction |

### 2.2 Tool-Result Interceptors

| Interceptor | Status | What It Does | Progressive Disclosure |
|-------------|--------|-------------|----------------------|
| AstGrep | ✅ Active | Replace Read tool with function outlines | By file path |
| Graphify | ⚠️ Opt-in | Replace Read/Glob/Grep with KG subgraph | By file path |
| Difftastic | ⚠️ Opt-in | Replace git diffs with structural diff | By command hash |

### 2.3 CCR (Lossless Reversible Compression)

| Feature | Status | Notes |
|---------|--------|-------|
| Row-drop sentinel | ✅ Active | `{"_ccr_dropped": "<<ccr:HASH N>>"}` |
| `cutctx_retrieve` tool | ✅ Active | Proxy + MCP distribution |
| Response handler | ✅ Active | Auto-decompress, max 3 rounds |
| Context tracker | ✅ Active | Proactive expansion |
| Batch API support | ✅ Active | Anthropic, OpenAI, Google |
| CCR store | ✅ Active | In-memory (default) / SQLite / Redis |
| Multi-worker | ⚠️ Warning | In-memory store per-worker; use SQLite for multi-process |

### 2.4 Memory System

| Feature | Status | Notes |
|---------|--------|-------|
| LocalBackend | ✅ Active | SQLite + HNSW + FTS5 |
| Qdrant-Neo4j | ⚠️ Opt-in | `[memory-stack]` extra, requires Docker |
| Mem0Backend | ⚠️ Opt-in | `pip install cutctx-ai[memory-stack]` |
| DirectMem0Adapter | ✅ Active | 0 LLM calls with pre-extracted data |
| MemoryBridge | ✅ Active | Markdown ↔ Cutctx bidirectional sync |
| Team sync | ✅ Active | Server deltas now apply idempotently on the client |
| Episodic memory | ⚠️ EE (BUSINESS tier) | `CUTCTX_EPISODIC_MEMORY_ENABLED` |
| Traffic learning | ⚠️ Opt-in | Rule-based pattern extraction |

### 2.5 Proxy Server (Core)

| Feature | Status | Notes |
|---------|--------|-------|
| Anthropic Messages | ✅ Active | `/v1/messages` |
| OpenAI Chat | ✅ Active | `/v1/chat/completions` |
| OpenAI Responses | ✅ Active | `/v1/responses` HTTP + WebSocket |
| Gemini | ✅ Active | `/v1beta/models:generateContent` |
| Cloud Code | ✅ Active | Google Cloud Code Assist |
| Batch API | ✅ Active | All 3 providers |
| Cache modes | ✅ Active | `token` (aggressive) / `cache` (prefix-freeze) |
| Rate limiting | ⚠️ Configurable | Token bucket, 60 RPM / 100k TPM |
| Budget enforcement | ⚠️ Configurable | Daily USD cap, stream cut-off |
| 5 compatibility aliases | ✅ Accepted | `token_mode`, `cache_mode`, `token_savings`, `cost_savings`, `token_cutctx` |

### 2.6 Admin API (79+ Endpoints)

| Category | Endpoints | Hide/Expose |
|----------|-----------|-------------|
| Dashboard | `/admin` (SPA) | ✅ Exposed |
| Stats | `/stats`, `/stats-history` | ✅ Exposed |
| Webhooks | CRUD `/webhooks/*` | ✅ Exposed |
| Entitlements | `/entitlements` | ✅ Exposed |
| Audit | `/audit/*` | ✅ Exposed |
| RBAC | CRUD `/rbac/*` | ✅ Exposed |
| Orgs | CRUD `/orgs/*` | ✅ Exposed |
| SCIM 2.0 | `/scim/v2/*` | ✅ Exposed |
| Secrets | CRUD `/v1/secrets/*` | ✅ Exposed |
| MFA | `/v1/admin/mfa/*` | ✅ Exposed |
| Residency | `/v1/residency/proof` | ✅ Exposed |
| Rate limits | `/v1/rate_limit/stats` | ✅ Exposed |
| License | `/v1/license/*` | ✅ Exposed |
| Fleet | `/fleet/*` | ✅ Exposed |
| **Live config flags** | **`POST /admin/config/flags`** | ✅ Documented in wiki + dashboard docs |
| Firewall | `/firewall/*` | ✅ Exposed |
| Intelligence | `/intelligence/*/status` | ✅ Exposed |
| Cache | `/cache/clear` | ✅ Exposed |
| CCR retrieve | `/v1/retrieve` | ✅ Exposed |
| CCR compress | `POST /v1/compress` | ✅ Exposed (was admin-gated, fixed) |

### 2.7 Intelligence Layer (6 Features)

| Feature | Status | Lines | CLI Flag | Notes |
|---------|--------|-------|----------|-------|
| Task-aware compression | ✅ Wired | 425 | `--enable-task-aware` | Real impl, env-only before fix |
| Semantic dedup | ✅ Wired | 404 | `--enable-semantic-dedup` | Real impl, env-only before fix |
| Context budget | ✅ Wired | 505 | `--enable-context-budget` | Real impl, env-only before fix |
| Cross-session profiles | ✅ Wired | 425 | `--enable-cross-session` | Real impl, env-only before fix |
| Multi-agent shared ctx | ✅ Wired | 919 | `--enable-multi-agent` | Real impl, env-only before fix |
| Cost forecasting | ✅ Wired | 535 | `--enable-cost-forecasting` | Real impl, env-only before fix |

**All 6 now have CLI flags** (were env-var only before the audit).

### 2.8 Security

| Feature | Status | Notes |
|---------|--------|-------|
| LLM Firewall | ⚠️ Default OFF, **has CLI flag now** | `--enable-firewall` |
| Anti-debug | ✅ Active at EE import | PT_DENY_ATTACH + /proc detection |
| Integrity Guard | ✅ Active | SHA-256 + HMAC signed manifest |
| Encrypted Secrets | ✅ Active | Fernet AES-128-CBC + SQLite |
| TOTP MFA | ✅ Active | RFC 6238, stdlib-only, replay-protected |
| RBAC | ✅ Active (EE) | 4 roles, 40+ permissions, fail-closed |
| SCIM 2.0 | ✅ Active (EE) | Users + Groups |
| Audit (hash chain) | ✅ Active (EE) | HMAC-SHA256, strict mode |
| Data Residency | ✅ Active (EE) | Ed25519-signed attestation |
| Egress enforcement | ✅ Active | Air-gap mode with allowlist |
| OAuth2 plugin | ✅ Available | `cutctx-oauth2` separate package |

### 2.9 CLI Commands

| Command | Status | Notes |
|---------|--------|-------|
| `proxy` | ✅ Active | ~100 flags |
| `wrap` (14 agents) | ✅ Active | **windsurf/zed/opencode now in CLI** (fixed in audit) |
| `unwrap` (3) | ✅ Active | Claude, Codex, OpenClaw |
| `init` (8 targets) | ✅ Active | Persistent install |
| `install` (6 subcmd) | ✅ Active | Persistent deployment |
| `bench` | ✅ Active | 6 inline algorithms |
| `savings` | ✅ Active | HTML reports, verify-integrity |
| `learn` | ✅ Active | Failure analysis |
| `evals` (3 subcmd) | ✅ Active | Memory + probes |
| `license` (5 subcmd) | ✅ Active | HMAC-signed keys |
| `billing` (2 subcmd) | ✅ Active | URL opener |
| `capabilities` | ✅ Active | Runtime feature doctor |
| `capture` (1 subcmd) | ✅ Active | Network diff |
| `mcp` (4 subcmd) | ✅ Active | MCP lifecycle |
| `report` (5 subcmd) | ⚠️ Partial | Schedule UI present, no cron daemon |
| `audit` (3 subcmd) | ✅ Active | List/export/stats |
| `rbac` (3 subcmd) | ✅ Active | List/assign/revoke |
| `orgs` (4 subcmd) | ✅ Active | List/create/delete/show |
| `tools` (4 subcmd) | ✅ Active | Doctor + install |
| `perf` | ✅ Active | Log analyzer |
| `agent-savings` | ✅ Active | Profile checker |
| `config-check` | ✅ Active | Env preflight |
| `sso-test` | ✅ Active | OIDC JWKS fetch |
| `setup` | ✅ Active | 5-step wizard |
| `intercept` (hidden) | ✅ Active | macOS HTTPS intercept |
| `memory-eval` (hidden) | 🔵 Deprecated | Redirects to `evals memory` |

### 2.10 Integrations (7 Frameworks)

| Framework | Status | Package | Notes |
|-----------|--------|---------|-------|
| LangChain | ✅ Active | `cutctx-ai` base | ChatModel, Memory, Tools, Retriever, LangGraph, LangSmith |
| Agno | ✅ Active | `cutctx-ai` base | Full model wrapper; hooks are observability-only |
| LlamaIndex | ✅ Active | `cutctx-ai` base | NodePostprocessor with BM25/Hybrid |
| Strands | ✅ Active | `cutctx-ai[strands]` | Full model + hooks + bundle; hooks off by default |
| LiteLLM | ✅ Active | `cutctx-ai` base | Callback (local + cloud modes) |
| ASGI | ✅ Active | `cutctx-ai` base | Middleware for FastAPI/Starlette |
| TypeScript SDK | ✅ Published | `cutctx-ai` npm | compress(), CutctxClient, Vercel AI SDK middleware |

### 2.11 EE/Enterprise Features

| Feature | Tier | Status |
|---------|------|--------|
| RBAC (4 roles) | ENTERPRISE | ✅ Active |
| SCIM 2.0 | ENTERPRISE | ✅ Active |
| Audit (hash chain) | ENTERPRISE | ✅ Active |
| Data Residency | ENTERPRISE | ✅ Active |
| Fleet management | ENTERPRISE | ✅ Active |
| Org hierarchy | BUSINESS | ✅ Active |
| Episodic memory | BUSINESS | ✅ Active |
| Traffic learning | BUSINESS | ✅ Active |
| Code graph | BUSINESS | ✅ Active |
| CCR | TEAM | ✅ Active |
| Multi-agent memory | TEAM | ✅ Active |
| Savings reports | TEAM | ✅ Active |
| Budget controls | TEAM | ✅ Active |
| All compressors | BUILDER (free) | ✅ Active |

---

## 3. Hidden / Unexposed Functionality

### 3.1 Hidden API Surface

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `POST /admin/config/flags` | **Live feature toggles** for 4 intelligence features | ✅ Covered in wiki/api.md, wiki/proxy.md, and dashboard Docs page |
| `/admin` basename | Dashboard mountable at `/admin` in production | ✅ Documented in proxy docs |
| `POST /v1/compress` | Compression-only endpoint (no LLM call) | ✅ Now documented (was admin-gated, fixed) |

### 3.2 Hidden CLI Features

| Feature | Purpose | Status |
|---------|---------|--------|
| `cutctx intercept` (hidden) | macOS HTTPS MITM intercept | ✅ Works, `hidden=True` |
| `--prepare-only` (hidden) | Test wrap config without launching agent | ✅ Works, on every wrap subcommand |
| `cutctx init hook ensure` (hidden) | Called by agent hooks to ensure runtime | ✅ Works |
| `cutctx install agent run/ensure` (hidden) | Supervisor callbacks | ✅ Works |
| `CUTCTX_EXPERIMENTAL=1` | Gating for intercept feature | ✅ Enforced in CLI; docs/tests added |

### 3.3 Dashboard Discovery Notes

| Feature | Status | Notes |
|---------|--------|-------|
| `searchQuery` state | ✅ Covered | Captured in AppFrame and filters Capabilities, Governance, Firewall, Memory, Replay, and the Overview request / attribution panels |
| `STRATEGY_DISPLAY` rebrand map | ✅ Documented | Canonical mapping lives in wiki/ARCHITECTURE.md and dashboard code |
| JavaScript obfuscation | 🟡 Inactive placeholder | Commented-out hook in dashboard/vite.config.js; source maps disabled |
| Sample image generator | 🟢 Demo helper | Canvas-based PNG generator in Playground |
| 5s/60s polling cadence | ✅ Documented | DashboardDataProvider default behavior |

---

## 4. Dependency Analysis

### 4.1 Core Dependencies (12)

| Dep | Purpose | Risk |
|-----|---------|------|
| `tiktoken` | Token counting | Low |
| `pydantic` | Config models | Low |
| `litellm>=1.86.2` | Provider routing | Medium (CVE-2026-42271 below 1.86.2 — floor is correct) |
| `click` | CLI framework | Low |
| `rich` | Terminal tables | Low |
| `opentelemetry-*` | Telemetry | Low |
| `cryptography>=46.0.0` | Fernet/HMAC | Low |
| `graphifyy>=0.8.46` | Knowledge graph | Low (optional) |
| `networkx>=3.4.2` | Graph queries | Low (optional) |
| `ast-grep-cli` | Interceptor | Low |

### 4.2 Heavy Optional Dependencies

| Extra | Key Deps | Size Concern |
|-------|----------|--------------|
| `[proxy]` | fastapi, uvicorn, httpx, openai, onnxruntime, transformers, magika, mcp | ~500 MB |
| `[ml]` | torch, transformers, huggingface-hub | ~2 GB |
| `[llmlingua]` | llmlingua, torch, transformers | ~2 GB |
| `[memory-stack]` | mem0ai, qdrant-client, neo4j | ~200 MB |
| `[voice]` | onnxruntime, transformers, torch | ~2 GB |
| `[code]` | tree-sitter-language-pack | ~50 MB |
| `[demo-integrations]` | vllm, gptcache | ~5 GB (Linux only) |
| `[benchmark]` | lm-eval | ~2 GB |
| `[all]` | 16/29 extras composite | ~4+ GB |
| `[recommended]` | proxy,code,image,html,log-ml,knowledge-graph,relevance,mcp | ~600 MB |

**Risk:** `[all]` omits 13 extras the README calls out (`[agno]`, `[langchain]`, `[pytorch-mps]`, `[bedrock]`, `[memory-stack]`, `[langfuse]`, `[strands]`, `[llamaindex]`, `[anyllm]`, `[llmlingua]`, `[voice]`, `[voice-train]`, `[evals]`, `[benchmark]`, `[demo-integrations]`, `[proxy-prod]`, `[ee]`).

### 4.3 Rust Binary Dependencies (3 managed binaries)

| Binary | Version | Purpose |
|--------|---------|---------|
| `rtk` | v0.28.2 | Rust Token Killer (context tool) |
| `lean-ctx` | v3.4.7 | Alternative context tool |
| `difft` | v0.64.0 | Difftastic structural diff |

---

## 5. Documentation Gap Analysis

### 5.1 Fixed in This Audit Cycle

| Issue | Before | After |
|-------|--------|-------|
| IntelligentContextManager in wiki | 5+ pages | **Cleaned — NONE remain** |
| Wrap windsurf/zed/opencode hidden | Not in CLI `--help` | **Now present** |
| TOIN get_recommendation deprecated | 33 lines live | **Deleted** |
| Report schedule-cancel duplicate | Two definitions | **Cleaned** |
| Wiki docs stale (384 lines) | Stale in 5 files | **Trimmed** |
| CacheAligner hardcoded off | `enabled=False` | **Configurable** |
| Intelligence layer env-only | No CLI flags | **6 CLI flags added** |
| Firewall no CLI flag | Hidden | `--enable-firewall` added |
| `/v1/compress` admin-gated | Returned 403 | **Fixed — no admin required** |
| Session-sticky memory tool injection undocumented | Wiki/site docs missing env controls | **Documented and truth-tested** |

### 5.2 Still Open

| Issue | Status | Details |
|-------|--------|---------|
| LLMLingua optional support | 🟡 Code live + pyproject extra; docs are being aligned | Code at `cutctx/transforms/llmlingua_compressor.py`, `[all]` omits it |
| Compatibility aliases for modes | ✅ Intentional | `token_mode`, `cache_mode`, `token_savings`, `cost_savings`, `token_cutctx` |
| Dashboard `Docs.jsx` current | ✅ Verified current | Shows canonical token/cache modes, broad [all] bundle note, and accuracy guard |
| Team memory sync | ✅ Active | Client/server merge is now idempotent and regression-covered |
| `searchQuery` coverage | ✅ Dashboard search now filters the major summary panels and the Overview request table | Verified current |
| `/admin/config/flags` documented | ✅ Covered in wiki/api.md, wiki/proxy.md, and dashboard Docs page | Used by Governance page |

---

## 6. Recommendations (Updated)

### P0 — Address Immediately
1. **Resolve LLMLingua status** — Keep LLMLingua as optional support and make sure docs/tests consistently describe it that way instead of using "removed" language.
2. **Keep `/admin/config/flags` docs aligned** — The endpoint is now documented in the wiki and dashboard docs page; preserve this coverage when the API changes.
3. **Keep team memory sync regression-covered** — The client/server merge is now idempotent; retain the regression test so it stays that way.

### P1 — High Impact
4. **Keep dashboard search coverage aligned** — Search now filters the major summary panels plus the Overview request table; preserve this behavior as the dashboard evolves.
5. **Preserve compatibility aliases documentation** — The aliases are intentionally supported; keep docs and tests aligned with the canonical `token` / `cache` modes while preserving backward compatibility.
6. **Add `[all]` extra completeness note** — Document exactly which extras are NOT included in `[all]` to set correct user expectations.

### P2 — Product Quality
7. **Update `Docs.jsx`** — Ensure in-app documentation matches actual CLI flags and behavior.
8. **Keep `STRATEGY_DISPLAY` rebrand docs in sync** — The mapping is documented; preserve it when labels change.
9. **Add dashboard E2E tests for Playground, Firewall, Governance toggles** — Currently only auth/nav tested.
10. **Verify all `wiki/` claims against actual code** — Automated `test_docs_truthfulness.py` only checks `docs/` (Mintlify), not `wiki/`.
11. **Remove stale wiki/api.md and wiki/ccr.md** — Already trimmed but may still have stale claims.

### P3 — Nice to Have
12. **Dashboard search for remaining summary panels** — Extend the current filtering behavior to the remaining major Overview panels and any other primary views.
13. **Report scheduling with cron/launchd** — Currently writes config file but never executes.
14. **MCP server consolidation** — Pick one canonical MCP server implementation and retire the other 2.

---

## 7. Test Coverage Observations

| Area | Coverage | Notes |
|------|----------|-------|
| Compression algorithms | ✅ Excellent | Specific tests for each, skip-if-dep for optional |
| CCR / TOIN | ✅ Excellent | Critical gap tracker with 17+ documented fixes |
| Proxy routes | ✅ Good | Provider passthrough, compress endpoint |
| Dashboard | ⚠️ Moderate | Auth + nav + TTL bucket. No Playground/Firewall/Governance |
| Memory | ✅ Good | Handler ops, storage router, adapters |
| CLI | ✅ Good | Wrap e2e with mock servers |
| Docs truthfulness | ⚠️ Partial | Only checks `docs/` (Mintlify), not `wiki/` (10+ pages) |
| Auth code paths | ⚠️ Weak | conftest auto-injects admin key so tests bypass auth |
| Playwright browser | ⚠️ Chromium only | No Firefox/Safari |

---

## 8. Summary — Current State vs Initial Audit

| Dimension | Initial State (June 29) | Current State (June 29, post-fixes) |
|-----------|----------------------|-------------------------------------|
| Incomplete features documented | 14 items | **8 remaining** (mostly minor) |
| Wiki stale references | 5+ files with retired features | **Cleaned** |
| Wrap windsurf/zed/opencode | Missing from CLI | **Now present** |
| Intelligence CLI flags | 0 | **6 added** |
| Firewall CLI flag | 0 | **1 added** |
| CacheAligner | Hardcoded disabled | **Configurable** |
| TOIN deprecated code | 33 lines | **Deleted** |
| Report schedule-cancel | Duplicate | **Cleaned** |
| Wiki pages trimmed | — | **-384 lines** |
| `/admin/config/flags` | Documented | ✅ Covered in wiki + dashboard docs |
| Dashboard search | Partial | 🟡 Filters several pages and the Overview request / attribution panels, but not every summary panel |
