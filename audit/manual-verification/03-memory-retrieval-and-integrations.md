# Memory, Retrieval, MCP, and Framework Integrations

### MEM-001 — Memory create/query/inject lifecycle

**Priority:** P0 when memory is enabled. **Actions:** write `RUN_ID` memories through every exposed API/CLI path; query exact/semantic results; send a request that should receive injected context; inspect resulting prompt/trace. **Expected:** stable IDs/provenance/timestamps; ranked, budgeted injection only for matching scope. **Negative:** empty query, invalid metadata, embedding backend outage, oversized record. **Cleanup:** delete by `RUN_ID`. **Pass:** stored content is retrievable and injected only when configuration permits.

### MEM-002 — Persistence, expiry, retention, export/import

**Priority:** P1. **Actions:** restart backing service/proxy; wait configured TTL/retention boundary; export/import a scoped set; test prune/purge. **Expected:** documented durable backend survives restart, expiry removes/inhibits retrieval, export omits secrets and import validates schema. **Negative:** corrupt import, unavailable store, interrupted deletion. **Pass:** lifecycle matches backend/config claim.

### MEM-003 — Isolation and concurrency

**Priority:** P0. **Actions:** create similar records under distinct tenant, user, workspace, session, and agent scopes; query concurrently using all identities. **Expected:** only authorized scope returns results; dedup never merges cross-scope records. **Negative:** forged scope header/ID, shared cache backend restart, simultaneous edit/delete. **Pass:** zero data leakage and deterministic conflict behavior.

### MEM-004 — Backends and adapters

**Priority:** P1. **Actions:** repeat MEM-001–003 for every configured backend/adapter (local/SQLite/vector/graph/Mem0/Qdrant/Neo4j/sync adapter) and for unavailable optional backend. **Expected:** factory selects configured backend, health/reporting identifies it, unsupported dependency gives install/config remediation. **Pass:** each enabled backend has evidence.

### MEM-005 — Retrieval/MCP contract

**Priority:** P0. **Actions:** install/start the documented MCP server; list tools; call compression, retrieve, stats, and any memory tools using valid/invalid inputs; test CCR expiry and server timeout. **Expected:** tool schemas/descriptions are usable, retrieval returns structured actionable errors rather than host crash. **Negative:** invalid 24-char hash, unauthorized tool caller, proxy down. **Cleanup:** unregister disposable server. **Pass:** MCP client can complete a marker retrieval without manual HTTP.

### MEM-006 — LangChain/LangGraph and LlamaIndex

**Priority:** P1 when extras installed. **Actions:** execute each documented minimal example with a stub/model test and inspect messages/documents before/after. **Expected:** wrapper/postprocessor preserves framework return type, callbacks/streaming work, optional dependency errors are clear. **Negative:** unsupported message/document, callback failure, proxy unavailable. **Pass:** all published snippets run unchanged or discrepancies are logged in DOC matrix.

### MEM-007 — Agno and Strands

**Priority:** P1 when extras installed. **Actions:** run documented agent samples, including one tool call/multi-turn memory interaction. **Expected:** agent contract and streaming survive; failures preserve uncompressed path where advertised. **Pass:** host framework produces a usable answer and memory evidence.

### MEM-008 — ASGI, LiteLLM, and provider wrappers

**Priority:** P1. **Actions:** mount compression middleware, configure LiteLLM callback, and wrap each advertised Python provider client; execute non-stream/stream. **Expected:** middleware scope excludes health/static traffic as documented; wrapper preserves kwargs and result type. **Negative:** invalid upstream, cancellation, excluded path. **Pass:** applications require no incompatible API change.

### MEM-009 — Shared context and agent provenance

**Priority:** P1. **Actions:** create/get/update/delete shared context from two agent identities; inspect provenance and TTL. **Expected:** namespacing/ACL/expiry behavior matches docs. **Negative:** stale read, conflicting writes, invalid agent ID. **Pass:** record cannot be read or modified outside intended boundary.

### MEM-010 — Retrieval/gateway host integrations

**Priority:** P1. **Actions:** execute any configured gateway/retrieval plugin path (Hermes/agent hook/Claude Desktop gateway) with a marker and an upstream-tool failure. **Expected:** original content can be fetched; gateway failure follows fail-open policy and explains degraded state. **Pass:** host remains usable and data boundary holds.

### MEM-011 — Observability and user outcomes

**Priority:** P1. **Actions:** generate write/query/injection/expiry events and inspect `/stats`, dashboard memory view, audit/telemetry. **Expected:** counts/latency/source/scope reflect operations without raw secret exposure. **Pass:** metric/UI match API/source records.

### MEM-012 — Unsupported or experimental capability sweep

**Priority:** P2. **Actions:** read feature flags and optional imports for retrieval/memory; invoke disabled/uninstalled feature via documented public surface. **Expected:** not silently enabled; actionable capability status. **Pass:** every optional/experimental memory feature is verified, declared N/A, or blocked with owner.
