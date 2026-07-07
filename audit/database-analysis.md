# CutCtx Database & Storage Analysis

**Date:** 2026-07-08  
**Scope:** Cache, CCR store, persistence, state management, data retention

---

## 1. Storage Architecture

CutCtx uses a **layered storage architecture** with multiple backends handling different concerns:

### CCR Store (Compress-Cache-Retrieve)
- **Primary purpose:** Store original uncompressed content so compression is reversible
- **Backends:** In-memory (default), SQLite (`cutctx_memory.db`), Redis (cfg-gated behind `feature = "redis"`)
- **Location:** `crates/cutctx-core/src/cache_control.rs`, `crates/cutctx-core/src/semantic_cache.rs`
- **Schema:** Key-value with TTL expiration, content-addressed by hash

### SQLite Databases (Project Root)
Three SQLite databases exist in the project root:
| Database | Purpose | Size |
|----------|---------|------|
| `cutctx_audit.db` | Audit log events (security, compliance) | ~4KB |
| `cutctx_memory.db` | Agent memory, compression profile data | ~1.1MB |
| `spend_ledger.db` | Token spend tracking, billing records | ~4.5MB |

### State Persistence
- **Compression profiles:** Stored as JSON files in `.cutctx/` directory per workspace. The `ProfileManager` singleton handles loading/caching
- **Agent memory:** SQLite-backed via `cutctx/memory/` modules. Schema includes sessions, messages, embeddings
- **Config/state:** `.env.local`, environment variables, config files. No central config DB

### Auxiliary Stores (Docker Compose)
- **Qdrant:** Vector database for semantic search (compression/retrieval quality)
- **Neo4j:** Graph database for relationship/multi-hop reasoning (memory layer)
- Both used exclusively for the "intelligence" layer, not core compression

---

## 2. Caching Strategy

| Cache Type | Implementation | Backend | Invalidation |
|-----------|---------------|---------|-------------|
| Token cache | `semantic_cache.rs` | SQLite/memory | TTL-based |
| Compression cache | `cache_control.rs` | Memory/SQLite/Redis | LRU + TTL |
| Dashboard stats | Polling every 5s | In-memory | Time-windowed |
| Profile cache | `ProfileManager` singleton | JSON file | Workspace-hash keyed |

The Rust proxy has `CacheControlAutoFrozen` feature that detects when prompt caching mandates immutable prior-turn content. This is a safety mechanism, not a performance cache.

---

## 3. Data Retention & Cleanup

- **CCR store entries:** TTL-based expiration (configurable via `ccr_ttl`)
- **Audit logs:** Appended indefinitely in `cutctx_audit.db` — no rotation policy visible
- **Spend ledger:** Appended indefinitely in `spend_ledger.db` — no archival mechanism
- **Memory:** `cutctx/retention.py` handles memory-specific retention (summarization, pruning)
- **No global data lifecycle policy** for audit or spend databases

---

## 4. Gaps & Recommendations

| Gap | Impact | Recommendation |
|-----|--------|---------------|
| No shared CCR by default | Horizontal scaling requires explicit Redis opt-in | Make Redis the default for multi-instance deployments |
| No audit log rotation | unbounded growth of `cutctx_audit.db` | Add configurable retention + archival |
| No spend ledger archival | Long-term cost analysis data unbounded | Add monthly rollup + purge raw data >90 days |
| SQLite for memory + CCR in single file | Potential contention | Split into separate database files with connection pooling |
| No backup/replication strategy | Data loss on instance failure | Add WAL-mode SQLite + periodic checkpoint to object store |
| No storage performance benchmarks | Unknown read/write latency | Add `cutctx perf --storage` benchmark command |
