# Proxy, Provider Compatibility, Routing, and Control Plane

Use the standard `BASE_URL`, test client/admin credentials, and synthetic provider keys from [00](00-prerequisites-and-evidence.md). For each request capture upstream-received payload (via a test stub where possible) to verify preservation, not merely a 200 response.

## Startup, health, authentication, and request validation

### PX-001 — Lifecycle and health contract

**Priority:** P0. **Purpose:** prove an operator can start, stop, and assess the proxy. **Actions:** (1) start with minimal valid config. (2) GET `/livez`, `/readyz`, `/health`, `/health/config`, `/v1/version`, `/stats`, and `/stats-history`. (3) stop with SIGTERM and restart. **Expected evidence:** liveness/ready distinction is meaningful during initialization; version matches artifact; health has no secret; graceful shutdown logs completion. **Negative:** occupied port, unreadable config, unavailable configured dependency. **Cleanup:** stop process. **Pass:** startup failures are actionable and restarts do not corrupt persisted state.

### PX-002 — Client/admin auth and loopback guard

**Priority:** P0. **Actions:** for a public/data/admin endpoint, test no key, malformed key, wrong client key, wrong admin key, valid least-privilege key, valid admin key, and remote/non-loopback origin where enabled. **Expected:** 401/403 are consistent, valid access works only for the permitted endpoint class, logs redact credentials. **Negative:** duplicate headers, URL/query key, expired/rotated key, CORS preflight. **Pass:** no unauthenticated control-plane mutation or privilege escalation.

### PX-003 — HTTP validation and error envelope

**Priority:** P0. **Actions:** POST invalid JSON, wrong content type, missing required fields, invalid enum/model, excessively large body, malformed compressed body, and unknown route. **Expected:** bounded 4xx response with request ID and no stack trace/secrets; valid request remains accepted after failures. **Pass:** errors follow the documented provider/control-plane format.

### PX-004 — Observability baseline

**Priority:** P0. **Actions:** issue one successful and one failed request; inspect structured logs, `/stats`, history, and enabled metrics/OTel exporter. **Expected:** request/session correlation; latency/status/savings/routing outcomes appear exactly once; raw credentials and protected content are absent unless explicitly configured in secure test capture. **Pass:** evidence can connect client request to operator view.

### PX-005 — Configuration precedence and feature flags

**Priority:** P1. **Actions:** set a test-safe flag/config value in file, environment, CLI, and `/admin/config/flags`; restart where documented. **Expected:** documented precedence, schema rejection of unknown/invalid values, persisted/transient behavior is clear. **Negative:** unauthorized PATCH/POST, invalid boolean/number, restart during update. **Cleanup:** restore baseline. **Pass:** effective state equals API/UI/health reporting.

## Provider-compatible data plane

### PX-010 — OpenAI-compatible non-streaming request

**Priority:** P0. **Actions:** POST a fixture to each supported OpenAI-compatible endpoint advertised by `/docs`/API docs: chat completion and responses/completions as applicable. Include system/user/tool calls, JSON/schema response options, cache controls, metadata, model alias, and `stream:false`. **Expected:** upstream stub receives protocol-valid request preserving all non-compression semantics; caller receives OpenAI-shaped status/headers/body and usage; a request ID/savings event exists. **Negative:** invalid tool schema, unsupported model, upstream 4xx/5xx, timeout. **Pass:** output content/tool calls/finish reason are correct and errors retain client protocol shape.

### PX-011 — OpenAI streaming and WebSocket/SSE path

**Priority:** P0. **Actions:** repeat PX-010 with `stream:true`; for any `/v1/responses` WebSocket path, test connect/send/receive/close. **Expected:** ordered SSE/WS events, no cross-request frames, exactly one completion/error terminal event, cancellable client. **Negative:** client disconnect, upstream disconnect, invalid frame, slow consumer. **Pass:** reconstructed stream matches non-stream semantics.

### PX-012 — Anthropic Messages compatibility

**Priority:** P0. **Actions:** submit Messages API fixture with system blocks, content blocks, tools, tool use/result, cache controls, beta/version headers and both stream modes. **Expected:** Anthropic request/response/SSE event names and fields remain valid after proxy translation; cache/savings attribution is not double-counted. **Negative:** missing version/key, invalid content block/tool result, upstream rate limit. **Pass:** official Anthropic client can consume the result without adapter changes.

### PX-013 — Gemini compatibility

**Priority:** P0. **Actions:** submit generateContent/streamGenerateContent-style fixture with multi-part content, function declarations/calls, safety/config and cached-content fields. **Expected:** Gemini shape/usage/safety/result semantics survive translation; configured provider route is observable. **Negative:** malformed parts, unsupported model, safety-blocked upstream response, invalid key. **Pass:** official Gemini SDK/client parses the response and errors correctly.

### PX-014 — Other advertised pass-through protocols

**Priority:** P1. **Actions:** enumerate routes/handlers and run an allowed/denied sample for audio, embeddings, images, Bedrock/Vertex/Cohere/LiteLLM/custom endpoint or any provider shown in configuration. **Expected:** explicitly pass-through media is never claimed compressed; unsupported route returns capability error. **Pass:** each enabled adapter has a route-level result row.

## Compression, cache, budgets, and preservation

### PX-020 — Compression safety end-to-end

**Priority:** P0. **Actions:** send the long fixture through each configured profile/mode. Compare upstream payload and returned answer against original required identifiers, structured data, tool schemas and code symbols. **Expected:** deterministic manifest/savings trace; request remains valid; accuracy guard behavior follows setting. **Negative:** sensitive/injection-like strings, enormous tool output, already-compressed markers, compression exception. **Pass:** no silent deletion/corruption of critical content and fail-open behavior is observable where promised.

### PX-021 — Cache and provider-cache attribution

**Priority:** P1. **Actions:** send identical then near-identical requests; inspect semantic cache/provider cache headers/usage and dashboard totals. **Expected:** hit/miss status, TTL/invalidation, and each savings source separated. **Negative:** cache backend down, expired entry, changing auth/tenant/model, disabled cache. **Pass:** no cached result crosses tenant/user/model boundary and totals are not double-counted.

### PX-022 — Budget, policy, egress, firewall and structured output

**Priority:** P0. **Actions:** cross token/cost thresholds; submit firewall/PII/jailbreak test strings; request schema-constrained output; configure permitted and denied egress target. **Expected:** configured warn/block/truncate/retry decision, auditable policy reason, valid schema on success. **Negative:** retry exhaustion, unsupported schema, bypass URL/redirect/private-IP target. **Pass:** a denied request is never sent upstream and a stream obeys cutoff behavior.

### PX-023 — CCR retrieval API

**Priority:** P0. **Actions:** use `POST /v1/retrieve`, `GET /v1/retrieve/{hash}`, and stats with a valid marker; repeat with malformed/missing/expired hashes and wrong client/tenant. **Expected:** exact scoped original and metadata when valid; safe 4xx/miss otherwise. **Pass:** marker is non-guessable enough per implementation and access control is enforced.

### PX-024 — Sessions, replay, traces, and reset

**Priority:** P1. **Actions:** generate activity then request sessions/recover/replay/state, transformation traces/feed, and perform stats reset only in isolated environment. **Expected:** pagination/filtering/session correlation work; replay does not re-send provider traffic unless explicitly requested; reset scope is clear. **Negative:** unknown session, unauthorized replay/reset, corrupted trace. **Cleanup:** reset/dispose test sessions. **Pass:** sensitive content is protected and operator views reconcile.

## Routing, retry, and orchestration

### PX-030 — Model aliases, presets, and precedence

**Priority:** P0. **Actions:** set documented `codex-gpt54mini-high` preset and both compatibility aliases `codex-opencode-slim`/`oh-my-opencode-slim`; submit low- and high-complexity fixtures with an explicit requested model and conflicting env/file/API values. **Expected:** low-complexity GPT task routes to `gpt-5.4-mini` at high reasoning effort; heavier task stays on requested model; selected route/evidence exposes why. **Negative:** unknown/cyclic alias, missing target credential, invalid effort. **Pass:** behavior matches `docs/content/docs/model-routing-presets.mdx` and route trace.

### PX-031 — Provider selection and cross-provider translation

**Priority:** P0. **Actions:** configure two test providers, force primary/secondary targets, then invoke a supported cross-protocol route with tools and stream. **Expected:** translation preserves compatible semantics; unsupported semantic gets explicit error, not silent loss. **Pass:** selected provider/model is visible and response translates back correctly.

### PX-032 — Retry, timeout, circuit breaker, and failover

**Priority:** P0. **Actions:** test upstream stub returns retryable 429/5xx, non-retryable 4xx, hangs, and becomes healthy. Trigger configured retry/failover/circuit thresholds. **Expected:** bounded attempts/backoff; no retry of unsafe request where documented; fallback selection and recovery logged/metricized. **Pass:** caller gets one correct result/error and no duplicate billable upstream operation.

### PX-033 — Routing control plane and rollout

**Priority:** P1. **Actions:** read/create draft contract; simulate; shadow; canary; pause; rollback; promote; query evidence/receipt/export. Test provider account/credential CRUD/test, models refresh/certify, profiles/capability manifest/harness compatibility/policy bundle. **Expected:** authorized mutations are versioned/audited and UI/API refresh to canonical state. **Negative:** stale version, invalid contract, unauthorized mutation, secret read-back. **Cleanup:** rollback/delete `RUN_ID` contract and credentials. **Pass:** no traffic change occurs outside configured rollout state.

### PX-034 — Workflows, scheduler, outcomes and receipts

**Priority:** P1. **Actions:** create/get/run/cancel workflow, approve/verify task, query execution/outcome/receipt; run route, shadow, recommend, drift endpoints. **Expected:** state machine rejects invalid transitions; receipts are exportable/verifiable. **Pass:** lifecycle is idempotent and visible in logs/audit.

### PX-035 — Administrative route-family sweep

**Priority:** P1. **Actions:** enumerate every router mounted by `server.py` (admin, airgap, audit, DSR, failover, licensing, memory, MFA, orchestration, policy, rate limit, RBAC, residency, secrets, spend, SSO and EE additions). For **each literal route**, run: authorized valid request, missing/invalid auth, malformed body/query, nonexistent resource, and side-effect verification. **Expected:** declared status/model/auth dependencies match behavior. **Evidence:** route inventory CSV containing method/path/test IDs/status/result. **Pass:** no mounted route is omitted; an unavailable optional route returns its documented unavailable response.

### PX-036 — Fault recovery and data safety

**Priority:** P0. **Actions:** kill/restart proxy while idle and during non-stream/stream request; make cache/memory/telemetry backend unavailable; restore each. **Expected:** readiness changes, bounded error/retry, no corrupted CCR/session/audit records, recovery reaches baseline. **Pass:** evidence shows recovery and a clear operator signal.
