# Cutctx Database & Storage Analysis

**Date:** 2026-07-10
**Scope:** All storage backends, schemas, lifecycle, caching, multi-instance support, performance
**Analyst:** Deep-dive audit

---

## Overall Storage Rating: 🟡

Cutctx has a solid storage foundation with good architecting choices (pluggable backends, WAL mode, content-addressed keys, careful TTL management), but has several **medium-severity gaps** around schema evolution, WAL consistency, unbounded growth, and migration tooling that prevent a 🟢.

---

## Key Strengths

1. **Pluggable CCR backends** — Clean `CcrStore` trait in Rust with InMemory/SQLite/Redis; `CompressionStoreBackend` protocol in Python (InMemory/SQLite/entry-point extensible). Both share a simple put/get/delete interface.
2. **Content-addressed CCR keys** — BLAKE3 hashing (Rust) / MD5 (Python compat) for idempotent overwrite semantics.
3. **Atomic file writes** — `SavingsTracker._save_locked()` uses `mkstemp` + `os.fsync` + atomic rename + cleanup on failure (Medium-26 fix).
4. **WAL mode on critical paths** — Rust `SqliteCcrStore`, `PrefixTracker`, `SecretsStore` all use WAL mode.
5. **Lazy TTL expiry** — No background sweep threads; Rust `InMemoryCcrStore` and `SqliteCcrStore` both expire on read.
6. **Thread-safe concurrency** — `DashMap` (sharded) for Rust IN-MEMORY CCR, `Mutex<Connection>` for SQLite, `threading.RLock` for Python caches. TOCTOU race in InMemoryCcrStore already fixed (remove_if pattern).
7. **No silent fallbacks** — `from_config` factory surfaces every init error (per `feedback_no_silent_fallbacks.md`).

---

## Critical Issues

### CRITICAL: No schema migration system

**File:line** — Multiple files:
- `cutctx/memory/adapters/sqlite.py:97-108` — ad-hoc `_migrate_add_column` with silent `except` pass
- `cutctx/proxy/savings_tracker.py:2291-2297` — in-code schema version checks
- No Alembic, no `PRAGMA user_version`, no migration directory

**Problem:** Schema evolution is handled reactively via:
1. Catch-and-ignore `OperationalError` when adding columns (memory adapter)
2. In-code `schema_version` checks in `_sanitize_state` for JSON blobs (savings tracker)
3. Only `CREATE TABLE IF NOT EXISTS` — no column deprecation, no data migration

**Impact:** Adding a new column to any of the 4+ SQLite databases requires code changes; there is no way to roll back a schema change; existing deployed databases with old schemas will silently miss new columns unless caught by the ad-hoc migrator.

### HIGH: Python SQLite backends inconsistently use WAL mode

**WAL mode:**
- `cutctx/cache/prefix_tracker.py:404` — ✅ Sets `PRAGMA journal_mode=WAL`
- `cutctx/security/secrets_store.py:150` — ✅ Sets `PRAGMA journal_mode=WAL`
- `crates/cutctx-core/src/ccr/backends/sqlite.rs:71` — ✅ Sets WAL + `synchronous=NORMAL`

**No WAL mode (Python only):**
- `cutctx/cache/backends/sqlite.py:41-53` (`SqliteBackend`) — ❌ No PRAGMA at all
- `cutctx/storage/sqlite.py:36-64` (`SQLiteStorage`) — ❌ No PRAGMA at all
- `cutctx/memory/adapters/sqlite.py:110-118` — ❌ No PRAGMA (connection-per-request pattern)
- `cutctx/memory/adapters/sqlite_vector.py:247` — ❌ Sets `cache_size` but NOT WAL or `synchronous`
- `cutctx/memory/adapters/sqlite_graph.py:85-88` — ❌ Sets `cache_size` + `foreign_keys` but NOT WAL

**Impact:** Under concurrent proxy load, the non-WAL stores can experience `SQLITE_BUSY` when multiple connections contend for locks. The `SqliteBackend` is particularly risky because it's specifically designed for concurrent access (Python CompressionStore ↔ Rust CcrStore interop).

### MEDIUM: Unbounded growth in audit and spend databases

**File:line:**
- `cutctx_audit.db` — `audit_events` table, no retention/rotation policy anywhere in the Python codebase (the `cutctx.audit` module is in proprietary `cutctx_ee`)
- `spend_ledger.db` — `spend_events` table (6 indexes), inserted on every API call with no archival mechanism

**Impact:** Both databases grow unboundedly. With 6 indexes on `spend_events`, insert performance degrades over time. No VACUUM is called on these databases. The savings tracker (`proxy_savings.json`) does have trimming (`_trim_history_locked`, max 5000 history points, 365-day max age), but the SQLite stores have none.

### MEDIUM: Request-scoped connection-per-request pattern in memory adapters

**File:line:** `cutctx/memory/adapters/sqlite.py:110-118`

```python
def _get_conn(self) -> sqlite3.Connection:
    conn = sqlite3.connect(str(self.db_path))
    conn.row_factory = sqlite3.Row
    return conn
```

**Pattern used in:** `sqlite.py` (memory store), `sqlite_graph.py`, `sqlite_vector.py`, `FTS5TextIndex`

**Impact:** Every single query opens and closes a new SQLite connection. No connection pooling. No `WAL` mode (stated rationale: "connection-per-request pattern, so there's typically nothing to close"). This is bad for:
- **Performance:** Each `sqlite3.connect()` involves a filesystem stat, journal initialization, and schema parsing
- **Concurrency:** Without WAL, concurrent connections block on writes
- **Cache:** The SQLite page cache is per-connection, so it's cold on every request

---

## Quick Wins

| # | Win | Effort | Impact |
|---|-----|--------|--------|
| 1 | Add `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` to `cache/backends/sqlite.py` | 5 min | Eliminates `SQLITE_BUSY` contention on shared CCR DB |
| 2 | Add `PRAGMA journal_mode=WAL` to `memory/adapters/sqlite.py` | 5 min | Prevents read-write contention on memory DB |
| 3 | Add `PRAGMA journal_mode=WAL` to `storage/sqlite.py` | 5 min | Same for metrics storage |
| 4 | Add a cron-friendly VACUUM command for audit and spend DBs | 1 hour | Prevents long-term bloat from deleted/replaced rows |
| 5 | Document the max DB sizes and add monitoring | 2 hours | Catches growth before it becomes a P0 |

---

## Storage Layers Inventory

| Layer | Backend | Persistence | Location | Tech | Size |
|-------|---------|-------------|----------|------|------|
| **CCR Store (Python)** | InMemoryBackend | ❌ Process-only | `cutctx/cache/backends/memory.py` | `dict` + `threading.Lock` | Configurable (default 1000 entries, 300s TTL) |
| **CCR Store (Python)** | SqliteBackend | ✅ Disk | `~/.cutctx/ccr.db` | SQLite (NO WAL❗) | Configurable |
| **CCR Store (Python)** | Entry-point extensible | Depends | Set via `CUTCTX_CCR_BACKEND` env | e.g. Redis | Depends |
| **CCR Store (Rust)** | InMemoryCcrStore | ❌ Process-only | `crates/cutctx-core/src/ccr/backends/in_memory.rs` | `DashMap` + `Mutex<VecDeque>` | Default 1000 entries, 300s TTL |
| **CCR Store (Rust)** | SqliteCcrStore | ✅ Disk | `crates/cutctx-core/src/ccr/backends/sqlite.rs` | SQLite + WAL | TTL-based, lazy purge |
| **CCR Store (Rust)** | RedisCcrStore | ✅ Redis | `crates/cutctx-core/src/ccr/backends/redis.rs` | `redis` crate, cfg-gated | TTL-based (Redis expiry) |
| **Metrics Storage** | SQLiteStorage | ✅ Disk | `cutctx/storage/sqlite.py` | SQLite (NO WAL❗) | Depends on request volume |
| **Metrics Storage** | JSONLStorage | ✅ Disk | `cutctx/storage/jsonl.py` | JSONL file | Depends on request volume |
| **Memory (Primary)** | SQLiteMemoryStore | ✅ Disk | `cutctx_memory.db` | SQLite + FTS5 | ~1.1MB |
| **Memory (Vector)** | SQLiteVecIndex | ✅ Disk | `cutctx_memory_vectors.db` | SQLite + `sqlite-vec` | Separate DB |
| **Memory (Vector)** | USearchIndex | ✅ Disk | `cutctx/memory/backends/usearch_store.py` | USearch (optional) | Configurable |
| **Memory (Graph)** | SQLiteGraphStore | ✅ Disk | Same as memory DB (or separate) | SQLite | Configurable |
| **Memory (Graph)** | InMemoryGraphStore | ❌ Process-only | `cutctx/memory/adapters/graph.py` | Python dicts | Process memory |
| **Memory (Remote)** | Mem0Backend | ✅ External | `cutctx/memory/backends/mem0.py` | Neo4j + Qdrant | Depends |
| **Cache** | CompressionCache | ❌ Process-only | `cutctx/cache/compression_cache.py` | `OrderedDict` + `RLock` | Default 10,000 entries |
| **Cache** | SemanticCache (in-memory) | ❌ Process-only | `cutctx/cache/semantic.py` | `OrderedDict` + LRU | Configurable |
| **Session State** | PrefixTracker (SQLite) | ✅ Disk | `cutctx/cache/prefix_tracker.py` | SQLite + WAL | Session-scoped |
| **Secrets** | SecretStore (SQLite) | ✅ Disk | `cutctx/security/secrets_store.py` | SQLite + WAL + Fernet AES | Configurable |
| **Savings** | SavingsTracker (JSON) | ✅ Disk | `.cutctx/proxy_savings.json` | JSON file | Bounded (5000 history points, 365d) |
| **Audit** | Audit DB (SQLite) | ✅ Disk | `cutctx_audit.db` | SQLite (in `cutctx_ee`) | **Unbounded** |
| **Spend** | Spend Ledger (SQLite) | ✅ Disk | `spend_ledger.db` | SQLite (6 indexes) | **Unbounded** |

---

## Detailed Analysis

### 1. Storage Layers & Architecture

#### CCR (Compress-Cache-Retrieve) Layer — 🟢
The strongest layer. Clean Rust trait (`CcrStore`) with three backends:

| Backend | Concurrency | Persistence | WAL | Selected By |
|---------|------------|-------------|-----|-------------|
| `InMemoryCcrStore` | `DashMap` (sharded) | ❌ | N/A | Default (test) |
| `SqliteCcrStore` | `Mutex<Connection>` | ✅ | ✅ | Production default |
| `RedisCcrStore` | `redis::Client` (conn-per-call) | ✅ | N/A | Multi-worker opt-in |

Python mirrors this with `CompressionStoreBackend` protocol:
- `InMemoryBackend` — `dict` + `threading.Lock` (no sharding, unlike Rust)
- `SqliteBackend` — shared `ccr_entries` table schema with Rust, but **missing WAL mode**
- Extensible via `entry_points` group `cutctx.ccr_backend` (e.g., Redis)

**Key files:**
- `crates/cutctx-core/src/ccr/mod.rs` (trait + key computation + markers)
- `crates/cutctx-core/src/ccr/backends/sqlite.rs` (prepared statements, WAL, lazy TTL)
- `crates/cutctx-core/src/ccr/backends/redis.rs` (SETEX, GET, key prefix)
- `cutctx/cache/compression_store.py` (Python store with BM25 search, retrieval events)
- `cutctx/cache/backends/sqlite.py` (Python ↔ Rust interop backend)

**Schema (shared by Rust and Python SqliteBackend):**
```sql
CREATE TABLE IF NOT EXISTS ccr_entries (
    hash         TEXT PRIMARY KEY,
    original     BLOB NOT NULL,
    created_at   INTEGER NOT NULL,
    ttl_seconds  INTEGER NOT NULL
);
```

#### Memory Layer — 🟡
By far the most complex layer with the most storage backends:

| Component | Backend(s) | Schema File |
|-----------|-----------|-------------|
| `SQLiteMemoryStore` | SQLite | `cutctx/memory/adapters/sqlite.py:124-205` |
| `SQLiteVecIndex` | `sqlite-vec` | `cutctx/memory/adapters/sqlite_vector.py` |
| `FTS5TextIndex` | SQLite FTS5 | `cutctx/memory/adapters/fts5.py` |
| `SQLiteGraphStore` | SQLite | `cutctx/memory/adapters/sqlite_graph.py` |
| `InMemoryGraphStore` | Python dicts | `cutctx/memory/adapters/graph.py` |
| `UsearchIndex` | USearch | `cutctx/memory/backends/usearch_store.py` |
| `Mem0Backend` | Neo4j + Qdrant | `cutctx/memory/backends/mem0.py` |

**Memory schema** (from `cutctx_memory.db`):
- `memories` table: 20+ columns including hierarchical scoping (user/session/agent/turn), temporal versioning (valid_from/valid_until), supersession chains (supersedes/superseded_by), embedding BLOBs, entity refs (JSON array), and metadata (JSON object)
- `memory_fts` virtual table: FTS5 with Porter stemmer and Unicode61 tokenizer
- 12 indexes on `memories` including composite scope index

**Connection pattern:** Connection-per-request (no pooling, no WAL). The response handler mentions "the store uses connection-per-request pattern, so there's typically nothing to close" — this is a design choice that trades CPU overhead for simplicity.

#### Storage Router (Per-project isolation) — 🟢
`cutctx/memory/storage_router.py` provides three modes to avoid cross-project memory bleed:
- `PROJECT` (default): one SQLite DB per resolved project
- `USER`: one DB per `x-cutctx-user-id`
- `GLOBAL`: single DB (pre-fix behavior)
Uses an LRU cache of open `LocalBackend` instances bounded by `MAX_OPEN_BACKENDS` to control file-handle pressure.

#### Metrics Storage — 🟡
The `cutctx/storage/` module has two backends behind `Storage` ABC:
- `SQLiteStorage` — `requests` table with 20+ columns, no WAL, connection-per-call
- `JSONLStorage` — Append-only JSONL file (no random access, full-scan query)

Both implement the same interface: save/get/query/count/iter_all/get_summary_stats.

#### Savings Tracker — 🟢
JSON file persistence at `.cutctx/proxy_savings.json` with:
- Schema versioning (v6)
- Atomic write pattern (temp file + fsync + rename)
- Corrupt-file quarantine
- Bounded history (5000 points, 365 days)
- Integrity checker

### 2. Schema & Migration — 🔴

**There is no migration system.** This is the single biggest risk.

**Current approach:**
1. **`CREATE TABLE IF NOT EXISTS`** — Every SQLite store uses this on init. Works for new deploys; silently adds new columns only if the table doesn't already exist.
2. **Ad-hoc ALTER TABLE** (`memory/adapters/sqlite.py:97-108`):
   ```python
   @staticmethod
   def _migrate_add_column(conn, table, column, col_type):
       try:
           conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
       except sqlite3.OperationalError:
           pass  # Column already exists
   ```
   Used for `workspace_id` and `project_id` columns. Catches ALL `OperationalError`, not just "duplicate column". Would silently swallow real errors.
3. **In-code schema version** (`proxy/savings_tracker.py:2291-2297`):
   Checks `schema_version` field in JSON blob; v6 added attribution tracking.
4. **No `PRAGMA user_version`** — None of the SQLite databases use SQLite's built-in schema version tracking.

**Missing:**
- Alembic migrations or equivalent
- Schema version stored in DB
- Forward/backward compatibility policy
- Column deprecation or removal strategy
- Data migration for schema changes

### 3. Data Lifecycle — 🟡

| Store | TTL/Retention | Eviction | Cleanup Method |
|-------|--------------|----------|----------------|
| CCR (InMemory) | 300s default | Capacity-bound LRU | Lazy on `get` |
| CCR (SQLite) | 300s default | TTL on read | `WHERE created_at + ttl_seconds < now` |
| CCR (Redis) | 300s default | Redis TTL | Native Redis expiry |
| BatchContext | 86400s (24h) | 10,000 max | `cleanup_expired()` async task |
| CompressionCache | LRU | 10,000 entries | Evict oldest on insert |
| SemanticCache | LRU | Configurable | Evict oldest on insert |
| PrefixTracker | Session inactivity | Configurable | Periodic `_maybe_cleanup()` sweep |
| Memory | Temporal versioning | Supersession chains | Manual prune via `clear_*()` |
| Audit DB | **None** | **None** | **No cleanup** — unbounded |
| Spend Ledger | **None** | **None** | **No cleanup** — unbounded |
| Savings JSON | 365 days | 5000 points | `_trim_history_locked()` on each save |

**Risks:**
- Audit and spend databases have **no retention policy, no rotation, no archival mechanism, no VACUUM**.
- The `spend_events` table has 6 indexes; every insert gets slower as the table grows.
- No store calls `VACUUM` except `sqlite_vector.py` and `sqlite_graph.py` which expose it as an explicit `vacuum()` method (not automated).

### 4. Caching — 🟡

#### Compression Cache
`cutctx/cache/compression_cache.py` — Content-addressed LRU cache (default 10,000 entries):
- Maps original content hash → compressed content
- Thread-safe via `RLock` (required for async proxy with `asyncio.to_thread`)
- Tracks `_stable_hashes` for content known not to compress further
- No persistence, no cross-session sharing

#### Semantic Cache
`cutctx/cache/semantic.py` — Query-level semantic cache:
- Embeds queries → cosine similarity search → threshold check
- In-memory `OrderedDict` LRU; no persistence
- Separate from provider prompt caching (orthogonal concern)
- No vector index for similarity search at the cache level (uses brute-force)

#### Prefix Cache Tracker
`cutctx/cache/prefix_tracker.py` — Session-scoped provider cache state:
- SQLite-backed with WAL mode
- Maps session IDs to `PrefixCacheTracker` state (frozen message count, last activity)
- Uses `ON CONFLICT ... DO UPDATE` for upsert
- Periodic cleanup of expired sessions
- Session fingerprinting for stateless clients

#### Cache Coherence
- No distributed cache invalidation protocol
- No write-through/write-behind for multi-instance
- SemanticCache and CompressionCache are process-local; CCR is the only shared cache (via Redis/SQLite)

### 5. Multi-Instance Support — 🟡

| Component | Multi-Instance Ready? | Mechanism |
|-----------|----------------------|-----------|
| CCR Store | ✅ (opt-in) | Redis backend (`feature = "redis"`); shared SQLite file (WAL-mode) |
| Memory | ❌ | LocalBackend is filesystem-local; Mem0Backend can be shared (Neo4j + Qdrant) |
| Prefix Tracker | ❌ | Per-worker SQLite; needs Redis/etcd for shared session state |
| CompressionCache | ❌ | Process-local only |
| SemanticCache | ❌ | Process-local only |
| Savings | ✅ | JSON file on shared filesystem (NFS) or per-worker |
| Audit/Spend | ❌ | SQLite is not network-shareable with concurrent writers |

**Key constraint:** `SqliteCcrStore` uses `Mutex<Connection>` with WAL mode — works with concurrent readers but writes serialize on the mutex. For multi-worker, Redis is recommended.

The Rust code has a clear comment in `sqlite.rs:30`:
> "Operators who measure contention can shard by spinning up N stores backed by N DB files (e.g. one per worker) — multi-worker safety is provided by SQLite's own file locking."

### 6. Performance — 🟡

#### SQLite connection patterns (inventory)

| Store | Pattern | Pool | WAL | Cache Size |
|-------|---------|------|-----|------------|
| `SqliteCcrStore` (Rust) | Mutex around single connection | ❌ | ✅ | SQLite default |
| `SqliteBackend` (Python) | `sqlite3.connect()` per call (shared conn for `:memory:`) | ❌ | ❌ | SQLite default |
| `PrefixTracker` | `sqlite3.connect()` per call (reused for `:memory:`) | ❌ | ✅ | SQLite default |
| `SecretsStore` | `sqlite3.connect()` per call | ❌ | ✅ | SQLite default |
| `SQLiteStorage` | `sqlite3.connect()` per call (no reuse) | ❌ | ❌ | SQLite default |
| `SQLiteMemoryStore` | `sqlite3.connect()` per call | ❌ | ❌ | SQLite default |
| `SQLiteVecIndex` | `sqlite3.connect()` per call + optional conn cache | RLock-guarded cache | ❌ | `PRAGMA cache_size = -N` |
| `SQLiteGraphStore` | `sqlite3.connect()` per call | ❌ | ❌ | `PRAGMA cache_size = -N` |
| `FTS5TextIndex` | `sqlite3.connect()` per call | ❌ | ❌ | SQLite default |

The **connection-per-request** pattern is the most common. Benefits: no stale connections, no thread-safety issues. Costs: cold page cache, repeated filesystem overhead for DB open. For proxy workloads handling 10+ req/s, this is wasteful.

#### Query patterns
- **N+1 risk:** Low. Most queries are single-row key lookups (CCR) or indexed range scans (memory scope queries).
- **Bulk operations:** Batch context store iterates all contexts for stats (O(n)); compression store `_evict_oldest` is O(1) amortized.
- **Prepared statements:** Only Rust `SqliteCcrStore` uses prepared statements. Python stores build SQL strings each time (minor, but adds up at high throughput).

#### Bottlenecks
1. **`Mutex<Connection>` in SqliteCcrStore** — Contention under multi-worker proxy when many CCR gets land simultaneously. The Rust comment acknowledges this; Redis is the recommended escape hatch.
2. **Missing WAL on critical Python stores** — `SqliteBackend` is shared between Python and Rust; without WAL, concurrent accesses from both sides hang on `SQLITE_BUSY`.
3. **No VACUUM on audit/spend DBs** — Over time, DELETE/UPDATE operations leave free pages that aren't reclaimed.

### 7. File Layout Summary

```
Project Root SQLite databases:
  cutctx_audit.db              → audit_events (cutctx_ee, proprietary)
  spend_ledger.db              → spend_events
  cutctx_memory.db             → memories, memory_fts (FTS5), 12 indexes
  cutctx_memory_vectors.db     → vec_embeddings (sqlite-vec), vec_metadata

User home SQLite databases:
  ~/.cutctx/ccr.db             → ccr_entries

JSON persistence:
  .cutctx/proxy_savings.json   → SavingsTracker state (v6 schema)

Rust CCR trait (pluggable):
  InMemoryCcrStore              → Test default (DashMap)
  SqliteCcrStore                → Production default (WAL + Mutex)
  RedisCcrStore                 → Multi-worker opt-in (cfg-gated)

Python CCR protocol:
  InMemoryBackend               → dict + Lock (default)
  SqliteBackend                 → Shares ccr_entries with Rust (NO WAL)
  Entry-point extensible        → e.g. Redis, MongoDB
```

---

## File:line Reference Index

| Component | File:Line | Notes |
|-----------|-----------|-------|
| CCR Rust trait | `crates/cutctx-core/src/ccr/mod.rs:40-57` | `CcrStore` trait definition |
| CCR Rust InMemory | `crates/cutctx-core/src/ccr/backends/in_memory.rs:31-159` | DashMap + FIFO eviction + lazy TTL |
| CCR Rust SQLite | `crates/cutctx-core/src/ccr/backends/sqlite.rs:40-204` | WAL mode, prepared statements, lazy TTL |
| CCR Rust Redis | `crates/cutctx-core/src/ccr/backends/redis.rs:37-146` | SETEX, GET, key prefix |
| CCR Rust factory | `crates/cutctx-core/src/ccr/backends/mod.rs:29-152` | `from_config` — no silent fallback |
| CCR key hashing | `crates/cutctx-core/src/ccr/mod.rs:68-74` | BLAKE3 → 16 hex chars |
| Python CCR store | `cutctx/cache/compression_store.py:33-1316` | Full store with BM25 search |
| Python CCR backend | `cutctx/cache/backends/base.py:17-133` | CompressionStoreBackend protocol |
| Python InMemoryBackend | `cutctx/cache/backends/memory.py:17-140` | dict + Lock |
| Python SqliteBackend | `cutctx/cache/backends/sqlite.py:7-177` | **Missing WAL** |
| Python env config | `cutctx/cache/compression_store.py:1221-1264` | Backend selection via env |
| Global singleton | `cutctx/cache/compression_store.py:1267-1306` | Request-scoped or global |
| Batch store | `cutctx/ccr/batch_store.py:31-314` | In-memory dict, 24h TTL |
| Batch processor | `cutctx/ccr/batch_processor.py:1-562` | Post-processes batch results |
| Context tracker | `cutctx/ccr/context_tracker.py:1-660` | Multi-turn expansion |
| Legacy CCRStore | `cutctx/ccr/store.py:33-183` | Wraps BatchContextStore |
| SQLite metrics store | `cutctx/storage/sqlite.py:17-289` | **No WAL, no pooling** |
| JSONL metrics store | `cutctx/storage/jsonl.py:16-220` | Append-only, full-scan queries |
| Memory SQLite store | `cutctx/memory/adapters/sqlite.py:1-837` | **No WAL, conn-per-request** |
| Memory ad-hoc migration | `cutctx/memory/adapters/sqlite.py:97-108` | `_migrate_add_column` silent catch |
| Memory SQLite vector | `cutctx/memory/adapters/sqlite_vector.py:1-927` | sqlite-vec, cache_size PRAGMA |
| Memory SQLite graph | `cutctx/memory/adapters/sqlite_graph.py:1-758` | cache_size + foreign_keys PRAGMA |
| Memory FTS5 index | `cutctx/memory/adapters/fts5.py:38-455` | Porter stemmer, BM25 |
| Memory storage router | `cutctx/memory/storage_router.py:1-519` | Per-project isolation |
| Memory LocalBackend | `cutctx/memory/backends/local.py:1-843` | All local adapters combined |
| Memory USearch | `cutctx/memory/backends/usearch_store.py:1-776` | f16 quantization, memory-mapped |
| Mem0 backend | `cutctx/memory/backends/mem0.py:1-701` | Neo4j + Qdrant |
| Prefix tracker | `cutctx/cache/prefix_tracker.py:1-590` | WAL-mode SQLite for session state |
| Compression cache | `cutctx/cache/compression_cache.py:77-314` | RLock-guarded OrderedDict LRU |
| Semantic cache | `cutctx/cache/semantic.py:1-455` | In-memory LRU, cosine similarity |
| Savings tracker | `cutctx/proxy/savings_tracker.py:1-2874` | JSON persistence, v6 schema |
| Savings orchestrator | `cutctx/savings/orchestrator.py:29-126` | In-memory aggregate |
| Savings types | `cutctx/savings/types.py:10-211` | 11 SavingsSource enum values |
| Savings integrations | `cutctx/savings/integrations.py:25-111` | LiteLLM, vLLM APC, GPTCache |
| Secrets store | `cutctx/security/secrets_store.py:31-310` | WAL-mode SQLite + Fernet AES |
| Audit stub | `cutctx/audit.py:1-30` | Shim to `cutctx_ee` |
| Spend ledger schema | `spend_ledger.db` | 6 indexes, no retention |
| Audit DB schema | `cutctx_audit.db` | Merkle-chain event hashes, no retention |

---

## Recommendations by Priority

### P0 — Must Fix
1. **Add WAL mode to Python SqliteBackend** (`cache/backends/sqlite.py:41`) — This is the shared CCR DB between Python and Rust. Without WAL, concurrent access hangs.
2. **Add schema version tracking** (`PRAGMA user_version`) to all SQLite databases — Replace ad-hoc `_migrate_add_column` with proper version checks.

### P1 — Should Fix
3. **Add WAL mode + synchronous=NORMAL** to `memory/adapters/sqlite.py`, `storage/sqlite.py`, `sqlite_vector.py`, `sqlite_graph.py`
4. **Add retention policy** to audit and spend databases (configurable window + archival + VACUUM)
5. **Add connection pooling** or at least a per-thread singleton connection for hot-path stores (CCR SQLite in Python)

### P2 — Nice to Have
6. **Make connection-per-request stores cache connections** per thread/lifetime to warm the page cache
7. **Add storage metrics** (DB file sizes, query latency, connection count) to the prometheus endpoint
8. **Add `VACUUM` scheduling** for all mutable SQLite stores (configurable interval)
9. **Document the migration policy** — how to add columns, how to deprecate columns, how to backfill data

### P3 — Future
10. **Replace JSON savings file** with dedicated SQLite database (avoids read-modify-write race on concurrent worker saves)
11. **Add Redis as default** for multi-worker CCR (vs. opt-in)
12. **Consider SQLite connection pooling** library for Python (e.g., `pysqlite3-pool` or SQLAlchemy pooling)
