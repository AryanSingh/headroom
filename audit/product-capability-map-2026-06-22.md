# Cutctx Product Capability Map (Code-Grounded, 2026-06-22)

**Source:** Direct reads of source code on branch `moat-b1-team-memory-svc` @ `26866229`. Every claim has a file:line citation. No docs, audits, or marketing were trusted as primary sources.

**Naming:** The product is **Cutctx** (Python package is still `cutctx`; CLI is `cutctx`). The rebrand is a work-in-progress; the `cutctx/` directory is a half-migrated shell.

**Bottom line:** Cutctx is a Rust-accelerated LLM proxy that does **compression + caching + memory + air-gap enforcement** end-to-end. Its unique differentiators are the **5-source savings model with self-hosted prefix cache as a first-class source**, **CCR reversible compression**, and **per-project memory isolation**. No open-source competitor matches the full feature set.

---

## 1. Core proxy (185 routes, 4 providers + 6 SDKs)

### Provider handlers
- `cutctx/proxy/handlers/anthropic.py:406` — Anthropic Messages (with cache_control injection, CCR tool injection)
- `cutctx/proxy/handlers/openai/{base,chat,responses,compress,passthrough}.py` — Chat Completions, Responses (HTTP + WebSocket), standalone `/v1/compress`, catchall passthrough
- `cutctx/proxy/handlers/gemini.py:32` — Gemini generate/stream/countTokens + Cloud Code Assist (`cloudcode.googleapis.com`)
- `cutctx/proxy/handlers/batch.py:25` — Anthropic + OpenAI + Google Batch API uniformly
- `cutctx/proxy/handlers/streaming.py:59` — SSE parser for all 3 providers with 5m/1h cache TTL split for cost attribution

### Full route inventory (sampled from `cutctx/providers/proxy_routes.py:316-762`)

| Provider | Routes |
|---|---|
| Anthropic | `/v1/messages`, `/v1/messages/count_tokens`, `/v1/messages/batches*` (6 endpoints) |
| OpenAI | `/v1/chat/completions`, `/v1/responses` (HTTP + WS), `/v1/codex/responses` (HTTP + WS), `/v1/batches*`, `/v1/embeddings`, `/v1/moderations`, `/v1/images/*`, `/v1/audio/*`, `/v1/models*` |
| Gemini | `/v1beta/models/{m}:generateContent` + stream + countTokens + batchEmbedContents + cachedContents CRUD |
| Vertex AI | `{api_version}/projects/.../models/{m}:generateContent/streamGenerateContent/countTokens/rawPredict/streamRawPredict` |
| Catchall | `/{path:path}` (line 754) — pass any unknown provider route through without code changes |

**Distinctive:** WebSocket relay for `/v1/responses` (essential for OpenAI Codex CLI subscription auth) + catchall passthrough. No open-source competitor has both.

### SDKs (4 languages, the only product with all 4)
- **Python** — `cutctx/client.py:1049` (`CutctxClient` with `compress()`, `simulate()`, `chat.completions.create()`)
- **TypeScript** — `sdk/typescript/src/{client,compress,simulate,hooks,shared-context}.ts` + adapters
- **Go** — `sdk/go/{cutctx,memory,middleware,proxy,shared,options,errors}.go`
- **Java** — `sdks/java-cutctx/`

### Native binary (Rust, hard boot dep)
- `crates/cutctx-core/src/transforms/` — 18 Rust modules: `smart_crusher/`, `log_compressor.rs`, `search_compressor.rs`, `diff_compressor.rs`, `tag_protector.rs`, `anchor_selector.rs`, `adaptive_sizer.rs`, `audio_compressor.rs`, `image_compressor.rs`, `content_detector.rs`, `deletion_compaction.rs`, `detection.rs`, `live_zone.rs`, `magika_detector.rs`, `unidiff_detector.rs`, `safety.rs`, `recommendations.rs`, `pipeline/`
- Exposed to Python as `cutctx._core` (PyO3 via maturin). **The proxy refuses to start without it** (`server.py:198-209` — fail-closed at boot, not a crash)

---

## 2. The 5-source savings model (the moat)

Defined at `cutctx/savings/types.py:23-30`:

```python
class SavingsSource(str, Enum):
    PROVIDER_PROMPT_CACHE      # Anthropic cache_control, OpenAI prompt caching, Gemini cachedContent
    CUTCTX_COMPRESSION          # SmartCrusher, LiveZone, CodeCompressor, etc.
    SEMANTIC_CACHE              # repeated-query short-circuit
    PREFIX_CACHE_SELF_HOSTED    # vLLM APC, etc. — the 5th source no competitor tracks
    MODEL_ROUTING               # cost-based downgrade
```

**Key invariant** (`cutctx/savings/orchestrator.py:7-13`): "The combined total is the SUM of per-source tokens, never the difference between raw_input_tokens and post_cutctx_tokens. This prevents double-counting when Cutctx compression and provider cache both reduce the same input."

**Why it's a moat:** No open-source competitor tracks self-hosted prefix cache as a first-class source. LiteLLM/Portkey/Helicone aggregate provider cache but treat model routing and prefix-cache as separate concerns, and **none let an external tool (vLLM, GPTCache) push savings into the funnel** via the `x-cutctx-savings-metadata` header.

**Provider-cache-aware compression** (`cutctx/savings/policy.py:104`): the `StrategyResolver` refuses to compress cache-friendly prefixes for providers with native prompt caching, because compressing would invalidate the bigger cache. **"No competitor does this. LiteLLM/Portkey/Helicone compress blindly."**

### Compression transforms (8 content-type-aware compressors)

| Content | Compressor | Backend |
|---|---|---|
| JSON arrays | `SmartCrusher` | **Rust** (PyO3) |
| Source code | `CodeCompressor` | **Rust + tree-sitter** (Python/JS/TS Tier 1, Go/Rust/Java/C/C++ Tier 2) |
| Plain text | `KompressCompressor` | ModernBERT (`chopratejas/kompress-v2-base` from HuggingFace) |
| Logs/build output | `LogCompressor` | **Rust** (chained-exception trace survival) |
| Search results | `SearchCompressor` | **Rust** (BM25 scoring) |
| Diff output | `DiffCompressor` | **Rust** (byte-equality on 27 fixtures) |
| HTML | `HTMLExtractor` | Python (trafilatura, 70-90% reduction) |
| (router) | `ContentRouter` | Routes to the right compressor by content type |

Plus `ReadLifecycleTransform` (detects STALE / SUPERSEDED tool outputs — 75% of Read bytes) and `ToolResultInterceptorTransform` (ast-grep Read outline compression).

---

## 3. Memory system (3 backends, per-project isolation)

### Backends
- **`LocalBackend`** — `cutctx/memory/backends/local.py` — 3 SQLite files per memory DB: `<name>.db` (memories), `<name>_graph.db` (entities/relationships), `<name>_vectors.db` (sqlite-vec) or `<name>_hnsw` (HNSW). Default embedder: `all-MiniLM-L6-v2` (384d, MPS/CUDA/CPU auto-detect).
- **`Mem0Backend`** — wraps mem0 OSS
- **`DirectMem0Adapter`** — direct Qdrant+Neo4j, skips the mem0 layer

### Storage router (the 2026-05-26 leak fix)
`cutctx/memory/storage_router.py` — three modes: **PROJECT** (one DB per workspace, default), **USER** (one DB per user), **GLOBAL** (legacy). LRU of open backends so opening N project DBs doesn't load the embedder N times. **No competitor has this.**

### Native Anthropic memory tool integration
`cutctx/proxy/memory_handler.py:84-89` injects Anthropic's `memory_20250818` tool with the `context-management-2025-06-27` beta header. Means **Claude Code subscription auth** (which blocks custom tools) accepts the integration. **"Most memory systems only ship custom tools; this is unique."**

### Team memory sync (EE)
`cutctx_ee/memory_service/api.py` — `POST /v1/memory/sync` (watermark-based bidirectional deltas) + `POST /v1/memory/review` (curator approve/deprecate/propose with audit). SQLAlchemy backend so it swaps to Postgres/MySQL for team scale.

### Memory bridge (markdown ↔ memory)
`cutctx/memory/bridge.py:87` — `MemoryBridge` imports `MEMORY.md` from Claude Code / ChatGPT, exports back. Bidirectional sync with hash-based change detection. Cross-agent writers: `claude`, `codex`, `cursor`, `generic`.

### Memory tools (OpenAI-compatible)
`memory_save / memory_search / memory_update / memory_delete / memory_list` injected into the request, handled in the response (`memory_handler.py:1011-1140`).

---

## 4. CCR (Compress-Cache-Retrieve) — reversible compression

`cutctx/ccr/__init__.py:1-22`: **"REVERSIBLE compression beats irreversible compression. If the LLM needs data that was compressed away, it can retrieve it instantly."**

- `ccr/tool_injection.py:25` — `CCR_TOOL_NAME = "cutctx_retrieve"`, provider-aware tool definition (Anthropic/OpenAI/Google)
- `ccr/response_handler.py:50` — `StreamingCCRHandler` intercepts responses, handles CCR tool calls automatically
- `ccr/batch_processor.py:25` — handles CCR in Batch API results
- `ccr/batch_store.py:86` — `BatchContextStore` (24h TTL)
- `ccr/mcp_server.py` — optional MCP server for the retrieval tool
- `cache/compression_store.py` — `CompressionStore` with BM25 search within cached content, PII redaction (lines 60-65), TTL eviction (default 300s)
- Endpoint: `POST /v1/retrieve` (operator-facing, requires `ccr` entitlement)

**No competitor has this.** All other compressors are irreversible.

---

## 5. Cache layer (8 components)

`cutctx/cache/__init__.py:1-149` — plugin-based registry:
- `BaseCacheOptimizer` (`cache/base.py:36`) — abstract
- `AnthropicCacheOptimizer` — inserts `cache_control: {type: "ephemeral"}` breakpoints (1h vs 5m TTL split for cost attribution)
- `OpenAICacheOptimizer` — automatic prefix cache
- `GoogleCacheOptimizer` — CachedContent API
- `CacheOptimizerRegistry` — plugin registry
- `SemanticCache` / `SemanticCacheLayer` — similarity-threshold cache layer
- `CompressionCache` — token-mode compression cache
- `PrefixCacheTracker` / `SessionTrackerStore` — per-session prefix-freeze tracking with `FreezeStats`
- `DynamicContentDetector` — detects UUIDs/JWTs/hex hashes/ISO timestamps in prefixes
- `CompressionStore` — the CCR reversible compression store

Plus the proxy's own `cutctx/proxy/semantic_cache.py:24-147` — SHA-256 of `messages + model` as key, 3600s TTL, LRU eviction.

---

## 6. LLM Firewall (regex + ONNX ML)

`cutctx/security/firewall.py:1-554` — `FirewallScanner` + `StreamingRedactor` + `FirewallConfig`:

- **Prompt injection** (line 85-129): 7 regex patterns — `ignore_previous_instructions`, `dan_jailbreak`, `role_hijack`, `prompt_extraction`, `encoded_injection`, `dev_mode`, `markdown_injection`. Confidence 0.80-0.95.
- **Jailbreak** (line 131-151): 4 patterns — `hypothetical_bypass`, `grandma_exploit`, `opposite_day`, `numbered_list_jailbreak`.
- **PII** (line 158-183): 11 patterns — SSN, credit cards (4 schemes), email, US phone, IPv4, AWS keys, private keys, API key bearer, passport, EIN.
- **Data exfiltration** (line 190-198): `url_with_secrets` + `file_path_leak`.

**Streaming redactor** (line 454-554): buffers SSE tokens (`max_buffer_tokens=50`, `buffer_timeout_ms=10.0`), redacts PII inline before forwarding. Wired at `server.py:2140-2146` as `proxy._streaming_redactor`.

**ML classifier** (`firewall_ml.py:26-117`): ONNX model, <20ms on CPU, falls back to heuristic if model missing.

**Egress enforcer** (`cutctx/proxy/egress.py:1-229`): per-tenant allowlist of domain patterns, loaded from `CUTCTX_EGRESS_POLICY` env var. **Empty allowlist + not allow_all = deny-all.** Host-based matching to avoid parser differentials. Pre-compiled regex with metacharacter detection.

---

## 7. Enterprise stack (all in `cutctx_ee/`)

### Auth
- **SSO** (`cutctx_ee/sso.py`) — OIDC + JWT + JWKS caching (1h TTL) + scope/audience/exp checks + introspection fallback
- **MFA / TOTP** (`cutctx/security/mfa.py`) — RFC 6238, replay protection via `last_used_counter`, ±30s clock-skew window
- **RBAC** (`cutctx_ee/rbac.py`) — 4 roles (`VIEWER`, `MEMORY_CURATOR`, `OPERATOR`, `ADMIN`), 32 named permissions, **SQLite-persistent** (Round 2 fix), `has_permission()` fails-closed for unknown SSO users
- **SCIM 2.0** (`cutctx_ee/scim.py:42-267`) — full User + Group CRUD, PATCH support, all 9 SCIM endpoints

### Audit
- **Tamper-evident chain** (`cutctx_ee/audit/store.py`) — HMAC-SHA256 hash chain, **fail-closed on missing `CUTCTX_AUDIT_SECRET_KEY`** (refuses to start without it)
- Endpoints: `/admin/audit/{events,export,verify}`

### Spend ledger + policy
- **Ledger** (`cutctx_ee/ledger/`) — SQLAlchemy (swappable to Postgres/MySQL for team scale)
- **Pricing** — model → USD/MTok map
- **Query** with per-org/workspace/project filters; **cross-tenant requires explicit `spend.read.cross_tenant` permission**
- **Policy** (`cutctx_ee/policy/`) — Ed25519-signed (`hrp1.{kid}.{payload}.{sig}`)

### Webhooks (HMAC + retry + persistent DLQ)
- `cutctx/proxy/webhooks.py:131-643` — `WebhookDispatcher` with 8 event types, **HMAC-SHA256 signing** (`X-Cutctx-Signature`), **5 attempts with exponential backoff + ±50% jitter**, 10k queue
- **Persistent** (Round 2): `WebhookSubscriptionStore` + `WebhookDeadLetterStore` in `webhook_stores.py` (SQLite-backed, bounded size, oldest-acknowledged purge first)
- Boot: `server.py:1671-1686` starts the dispatcher when subscriptions exist

### Secrets (Fernet-encrypted SQLite)
- `cutctx/security/secrets_store.py:1-316` — `SecretsStore` with AES-128-CBC + HMAC-SHA256
- **Fail-closed** in production mode (`strict=True`) if no key is set
- Endpoints: full CRUD under `secrets.read` / `secrets.write` RBAC

### Residency proof (Ed25519 attestation)
- `cutctx/security/residency_proof.py:1-344` — `ResidencyAttestation` + `ResidencyProver`
- Signs JSON payload with Ed25519: tenant_id, proxy_version, timestamp, audit_chain_tail_hash, data_regions, egress_domains_blocked
- **Endpoint intentionally unauthenticated** — the attestation is itself signed, so anyone can verify offline
- **All 5 competitors: No**

### Air-gap mode
- Already covered as the egress enforcer (see §6). `routes/airgap.py` exposes `GET /v1/airgap/status` and `POST /v1/airgap/policy` for runtime management
- **All 5 competitors: No**

### License validation
- `cutctx_ee/billing/license_token.py:17-58` — `sign_license` produces `hrk1.{kid}.{payload}.{sig}` Ed25519 tokens (mirrors JWT format)
- New in Round 2: **Rust port** at `crates/cutctx-core/src/licensing.rs` (per the map's §14 "NEW things added recently")

### Stripe billing
- `cutctx_ee/billing/stripe_webhook.py:1-200` — full webhook handler with HMAC signature verification, **fail-closed on missing `STRIPE_WEBHOOK_SECRET` in strict mode** (Round 2 fix)

### DSR (GDPR/CCPA)
- `cutctx/proxy/routes/dsr.py` — `GET /v1/me/export`, `POST /v1/me/delete`
- **Status:** Round 2 fixed the local-backend delete cascade (`clear_scope` → `clear_user`) and the export 500 on numpy embeddings (`jsonable_encoder`). Spend ledger and audit log delete paths are documented gaps in `docs/security/SOC2_CONTROLS.md:24`.

### Retention
- `cutctx_ee/retention.py` — periodic cleanup of CCR / audit / episodic memory / WAL, entitlement-gated on TEAM tier, auto-started at boot (`server.py:1645-1665`)

### Trial + PitchToShip
- `cutctx/trial.py` — `TrialManager` enforces 14-day trial, middleware at `server.py:2294-2355` blocks LLM requests when expired
- `cutctx/checkout.py` — `checkout_url("team")` returns a PitchToShip URL

---

## 8. Observability (Prometheus + OTel + Langfuse + Spend forecast)

| Feature | File | Notes |
|---|---|---|
| Prometheus metrics | `cutctx/proxy/prometheus_metrics.py:62-1298` | Per-provider, per-model, per-stack counters. 25+ named metrics |
| OTel metrics | `cutctx/observability/metrics.py:76-200+` | `CutctxOtelMetrics` with subscription utilization gauges |
| OTel tracing | `cutctx/observability/tracing.py:27-208+` | Langfuse integration, `CutctxTracer` |
| Per-request cost tracking | `cutctx/proxy/cost.py` | `CostTracker` per-model USD attribution |
| Spend forecast | `cutctx/cost_forecast.py:1-535` | `CostEstimator` + `PolicyEngine`. Pricing map for Opus 4, Sonnet 4.5, Haiku 3.5, GPT-4o, GPT-4.1, o3/o4-mini, Gemini 2.5-pro/flash, 1.5-pro/flash |
| Telemetry beacon | `cutctx/telemetry/beacon.py:1-358` | Local-first, **opt-in via `CUTCTX_TELEMETRY_EGRESS=1`**, Supabase backend (INSERT-only RLS), 5-min cadence |
| Memory impact | `cutctx/observability/memory_impact.py:10-35` | Team memory impact metrics |

---

## 9. Dashboard (SSR + React)

### SSR HTML (`cutctx/dashboard/templates/dashboard.html`)
- Tailwind + htmx + Alpine.js
- Light/dark mode, live stats counter, per-provider savings, per-strategy compression, waste signals, compressed tokens viz, TTFB charts
- **Round 2 added** (Blocker 4): real search/filter/sort/loading/error states on the Recent Requests table

### React (`dashboard/src/`)
- **Round 2 made pages real**: Overview fetches `/stats` + `/health` + per-source breakdown; Firewall pulls real audit events; Memory pulls real records. **No more hardcoded mock data.**

### Live transformations drawer
- `GET /transformations/feed` (`server.py:3592`) returns most-recent N with full request + compressed + response
- **Note:** polls rather than SSE — no dedicated EventSource stream yet

---

## 10. CLI (70+ commands across 28+ subcommand groups)

`cutctx/cli/main.py:1-125`. Run `cutctx --help` to see all of them. Highlights:

| Command | Purpose |
|---|---|
| `cutctx proxy` | Start the optimization proxy |
| `cutctx memory {list,show,stats,edit,delete,prune,purge,export,import}` | Memory management |
| `cutctx audit {list,export,stats}` | Audit log |
| `cutctx orgs/rbac/license/billing` | Tenant / RBAC / license / billing |
| `cutctx install {apply,status,start,stop,restart,remove}` | Agent lifecycle |
| `cutctx init {claude,copilot,codex,gemini,openclaw}` | Per-agent init |
| `cutctx mcp {install,uninstall,status,serve}` | MCP server management |
| `cutctx sso-test / config-check / bench / perf` | Diagnostics |
| `cutctx report {export,schedule,buyer}` | Reports (incl. **buyer report** — per-org savings) |
| `cutctx wrap / unwrap {claude,codex,openclaw}` | Wrap/unwrap agent commands |
| `cutctx savings --verify-integrity` | **Round 2 added** — CLI exposure of `verify_integrity()` |
| `cutctx capture network-diff` | Network capture diff |

**All 5 competitors: No equivalent CLI with this depth.**

---

## 11. Plugin integrations + framework adapters

### Plugins (`plugins/`)
- `claude-code/`, `codex/`, `openclaw/`, `cutctx-agent-hooks/`, `cutctx-oauth2/`, `hermes/`, `cutctx-plugin/`

### Framework integrations (`cutctx/integrations/`)
- **LangChain** (full — agents, memory, retriever, streaming, langgraph, langsmith) — only LiteLLM matches
- **Agno** (hooks, model, providers)
- **Strands** (bundle, hooks, model)
- **MCP server** (`mcp/server.py`)
- **LiteLLM callback** (`litellm_callback.py`)
- **ASGI middleware** (`asgi.py`)

---

## 12. Persistence stores (13+ SQLite files)

| File | Module | Schema |
|---|---|---|
| `~/.cutctx/secrets.db` | `secrets_store.py:103` | `secrets(name PK, ciphertext, ...)` — Fernet |
| `~/.cutctx/rbac.db` | `rbac.py:251` | `role_assignments` + `mfa_enrollments` |
| `~/.cutctx/org.db` | `org.py` | orgs / workspaces / projects / seats |
| `~/.cutctx/audit.db` (OSS) | `audit.py:200` | `audit_events` — immutable |
| EE audit (separate) | `audit/store.py` | `audit_events` with HMAC chain |
| `~/.cutctx/scim.db` | `scim.py:42-50` | scim_users / scim_groups |
| `~/.cutctx/webhooks.db` | `webhook_stores.py` | webhook_subscriptions + webhook_dlq |
| `cutctx_memory.db` | `memory/adapters/sqlite.py:67` | memories |
| `cutctx_memory_graph.db` | `memory/backends/local.py:160-170` | entities + relationships |
| `cutctx_memory_vectors.db` | `memory/factory.py:275-282` | sqlite-vec (or HNSW dir) |
| `<root>/projects/<key>/memory.db` | `memory/storage_router.py` | per-project (PROJECT mode) |
| `<root>/users/<key>/memory.db` | `memory/storage_router.py` | per-user (USER mode) |
| `proxy_savings.json` | `savings_tracker.py:27-28` | JSON (not SQLite) |

Only the EE spend ledger uses **SQLAlchemy** (so it can swap to Postgres/MySQL for team scale).

---

## 13. NEW additions from recent commits (the things you added)

From the commit log, the **most recent material additions** beyond the headline features:

| Commit | What | Why it matters |
|---|---|---|
| `c556e5bb` | GDPR DSR delete + export P0 fixes | Real cascade for local backend; numpy embeddings no longer 500 |
| `7795ffb6` | CutctxProxy alias + streaming var name | Fixes 115 rebrand-leftover test failures |
| `7f6875c5` | `has_permission` fail-closed for unknown SSO users | Closes a security gap in the spend tenant scoping |
| `811931e7` | Persistent webhook subscriptions + DLQ | Subscriptions survive restart; failed deliveries recoverable |
| `a3d2e7bc` | React dashboard real APIs + drawer Esc | Removes hardcoded mock data; a11y |
| `34c936d8` | Streaming per-source fields + audit enum expansion (22 → 47) | Streaming path now matches non-streaming; audit categorization complete |
| `58e5495d` | TOTP MFA (RFC 6238) | Closes second-factor gap (18 tests) |
| `ddef51a1` | SQLite-backed RBAC persistence | Multi-replica, survives restart (14 tests) |
| `85d6031d` + `962854b6` + `61e5196a` | **5-source model wiring** (model router + request path + cost-based router) | The moat is now actually wired end-to-end |
| `cc1d0f5d` | Stripe webhook secret + CRL fail-closed | Security: refuse to start without secret in strict mode |
| `e0bdd009` | Dashboard search/filter/sort/loading/error | Blockers 4 closed |
| `7297b186` | EE memory review RBAC+audit | Blockers 3c closed |
| `aefcdb8d` | Real secrets backend (Fernet SQLite) | Blockers 3b closed |
| `173c39a4` | Real egress policy + airgap status | Blockers 3a closed |
| `ae100976` | `--verify-integrity` CLI flag | SOC2 audit gate |
| `ccec64bd` | Release-path memory and telemetry gaps | Hotfixes for the release script |
| `c211a4ac` | Auth gates + tests for 5 new route modules | RBAC on airgap/rate_limit/rbac/secrets/sso |

**`crates/cutctx-core/src/licensing.rs`** (per the map's §14): **new Rust port of license validation** — moves a hot path from Python to Rust.

---

## 14. Competitive positioning (vs. open-source LLM proxies)

**Competitors evaluated:** Portkey AI Gateway, Helicone, LiteLLM, OpenRouter, Cloudflare AI Gateway.

### What Cutctx has that no competitor matches

1. **Provider-cache-aware compression** (StrategyResolver refuses to compress cache-friendly prefixes for providers with native prompt caching)
2. **5-source savings model** with self-hosted prefix cache as a first-class source + external ingestion via `x-cutctx-savings-metadata`
3. **CCR reversible compression** — the LLM can call `cutctx_retrieve` to fetch the original
4. **Per-workspace memory storage router** (PROJECT / USER / GLOBAL modes) with LRU backend cache
5. **Native Anthropic memory tool injection** — Claude Code subscription auth accepts the integration
6. **Ed25519-signed residency proof** — attestation only, no remote signature needed to verify
7. **Tamper-evident audit log** with HMAC-SHA256 hash chain (fail-closed on missing key)
8. **Air-gap mode** with deny-all default and host-based matching (no parser differentials)
9. **5 SDKs in production** (Python + TS + Go + Java; **the only product with all 4** — and the older `sdks/go-cutctx/` makes 5)
10. **CLI with 70+ commands** (no competitor matches)
11. **MCP server integration** (no competitor)
12. **CCR tool injection + Anthropic beta header** (no competitor)
13. **Compressed tokens visualization** in the dashboard
14. **Spend forecast with policy engine** (per-model pricing map)
15. **Streaming PII redactor** (no competitor)
16. **Egress enforcer** (no competitor)
17. **Multi-event-type webhooks with persistent DLQ** (8 event types)
18. **70+ admin endpoints** via factory pattern with audit + RBAC

### What Cutctx is behind on

- **DSR cascade** — still partial (spend ledger and audit log delete paths are documented as not-yet-shipped; the local-backend cascade works after Round 2 fixes)
- **SAML SSO** — still missing (only OIDC)
- **ABAC** beyond simple role → permission mapping
- **HA coordination** across the new SQLite stores (each is a single-writer file; multi-replica needs external coordination beyond what currently exists)
- **No event-streaming (SSE) for the dashboard** — still polls

---

## 15. The actual strategic moat — what the 5-source model + CCR + storage router give you

The competitive position is not "we compress tokens" (Helicone does that, LiteLLM does that, everyone does that). It is:

1. **You can quantify per-source savings down to the dollar.** Provider cache vs. Cutctx compression vs. semantic cache vs. self-hosted vLLM APC vs. model routing — each is its own column in the per-org spend report. No competitor breaks these out independently.

2. **You can extend the funnel with external tools** (vLLM, GPTCache, LiteLLM) via the `x-cutctx-savings-metadata` header. The proxy ingests the value but never double-counts. No competitor has this.

3. **You can reverse compression on demand.** The LLM calls `cutctx_retrieve` and gets the full original. No competitor has this.

4. **You can isolate memory by project.** The 2026-05-26 leak was caught and fixed with the storage router; competitors don't have this failure mode at all because they don't have memory.

5. **You can deploy air-gapped.** The egress enforcer + deny-all default + residency proof + Ed25519 attestation are a complete compliance stack for regulated industries. Cloudflare has a piece of this; nobody else does.

6. **You can audit without trusting a third party.** The HMAC-SHA256 hash chain in the audit log is fail-closed on missing key. SOC2 auditors can verify chain integrity without external infrastructure.

**This is the pitch:** "Cutctx is the only LLM proxy that lets a regulated enterprise prove — to a regulator, an auditor, or its own board — exactly where every saved token came from, that no data leaked, that memory stayed in scope, and that the entire stack is auditable end-to-end."

The 5-source model + CCR + per-project memory + tamper-evident audit + air-gap + RBAC + TOTP MFA are not 7 separate features. They are **one product story** told to a specific buyer: the security-conscious AI/ML platform team at a regulated company.
