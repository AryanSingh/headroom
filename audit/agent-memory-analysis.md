# Cutctx — Agent Memory: Capability Inventory & Feature Analysis

**Date:** July 4, 2026  
**Type:** Capability audit + external landscape + feature design exploration

---

## 1. Executive Summary

Cutctx already ships a production-grade agent memory system that is more comprehensive than most standalone memory tools. The system spans four layers — from in-process short-term context sharing to persistent long-term memory with hybrid retrieval, cross-agent sync, and proxy-side injection. Two capability gaps exist relative to specialist tools: (1) temporal knowledge graph with automatic contradiction-based invalidation, and (2) self-editing memory blocks where agents actively rewrite pinned context. The recommended approach is to **integrate Zep/Graphiti** for temporal graphs (2-week adapter) and **build natively** for self-editing memory blocks (4-week MVP).

---

## 2. Cutctx Memory Infrastructure: Current State

### Layer 1: Short-Term / In-Process Memory (No Persistence)

| Component | File | What It Does | Lifetime |
|---|---|---|---|
| `SharedContext` | `cutctx/shared_context.py` (241 lines) | Compressed key→value handoff between agents in the same process. Default TTL 3600s, max 100 entries, LRU eviction. | In-process |
| `MultiAgentCoordinator` | `cutctx/shared_context.py` (604 lines) | Singleton shared compression cache — agents in the same process reuse each other's compression results by content hash. Prevents redundant recompression. Scoped by workspace. | In-process |
| `ContextTracker` | `cutctx/ccr/context_tracker.py` (660 lines) | Tracks what was compressed across conversation turns; proactively expands earlier compressed content the LLM may need. | In-process (5min TTL) |
| `CCRStore` (Python) | `cutctx/ccr/store.py` (183 lines) | String-based KV by MD5 hash; retrieval tool (`cutctx_retrieve`) returns originals referenced by `<<ccr:HASH>>` markers. | In-process (5min TTL) |

### Layer 2: Long-Term Persistent Memory ⭐

The main agent memory system. Persists to SQLite on disk, survives restarts, cross-session.

| Component | File | What It Does |
|---|---|---|
| `HierarchicalMemory` | `cutctx/memory/core.py` (910 lines) | Top-level orchestrator. API: `add`, `search`, `recall`, `supersede`, `get_history`, `clear_scope`, `remember`. Coordinate store + vector index + text index + embedder + cache. |
| `Memory` model | `cutctx/memory/models.py` (191 lines) | Dataclass: `id`, `content`, `user_id`, `workspace_id`, `project_id`, `session_id`, `agent_id`, `turn_id`, `valid_from/valid_until`, `importance`, `value_score`, `embedding` (numpy), `entity_refs`, `metadata`, `Provenance`, `supersession_chain`. Supports temporal validity windows and supersession history — **foundation for temporal graph is already in the data model**. |
| `LocalBackend` | `cutctx/memory/backends/local.py` (843 lines) | Default zero-config persistent backend. Composes SQLite + sqlite-vec (vector) + FTS5 (BM25) + sqlite-graph (entity relations). Local embedder (sentence-transformers) by default; OpenAI/Ollama optional. **No Docker required.** |
| `LocalBackend.easy()` | `cutctx/memory/easy.py` (337 lines) | `Memory()` class — one-liner: `memory = Memory()`, then `await memory.save(...)` / `await memory.search(...)`. |
| SQLite adapters | `cutctx/memory/adapters/sqlite.py`, `sqlite_vector.py`, `sqlite_graph.py`, `fts5.py`, `hnsw.py`, `graph.py`, `embedders.py`, `cache.py` | Pluggable persistent adapters: SQLite store, sqlite-vec vector index, SQLite entity-relationship graph, FTS5 BM25 text index, HNSW vector index fallback, in-memory graph variant, embedder integrations. |
| `LocalBackend.search()` | `memory/backends/local.py` | Hybrid retrieval: vector cosine → FTS5 BM25 → RRF fusion → cross-encoder rerank. |
| Qdrant + Neo4j backend | env vars via `CUTCTX_QDRANT_*` | Production backend for teams that want dedicated vector + graph DBs. `Memory(backend="qdrant-neo4j")`. |
| Mem0 backend | `cutctx/memory/backends/mem0.py` (701 lines), `direct_mem0.py` | **Mem0 already integrated** as a pluggable backend adapter. Supports both local (embedded) and cloud (Mem0 API) modes. |
| USearch backend | `cutctx/memory/backends/usearch_store.py` | USearch-based vector store as an additional backend option. |

### Layer 2b: Memory Tooling (LLM-Facing)

| Component | File | What It Does |
|---|---|---|
| LLM function tools | `cutctx/memory/tools.py`, `wrapper.py`, `wrapper_tools.py` | `memory_save`, `memory_search`, `memory_update`, `memory_delete`, `memory_list` — callable by the agent during conversation. Auto-wraps any OpenAI-compatible client. |
| Inline extractor | `cutctx/memory/inline_extractor.py` (229 lines) | Injects `<memory>{...}</memory>` tags into system prompt. Agent outputs memories inline during the response — zero extra LLM calls. Parsed and stored automatically. |
| Background extractor | `cutctx/memory/extractor.py` (331 lines) | `EpisodicSessionTracker` watches proxy sessions, after 5min idle runs async LLM extraction and stores insights. |
| Cross-agent sync | `cutctx/memory/sync.py` (490 lines), `sync_adapters/claude_code.py`, `sync_adapters/codex_agent.py` | Bidirectional sync between Cutctx memory DB and Claude Code native memory / Codex native memory. Endpoint: `POST /v1/memory/sync`. |
| Markdown bridge | `cutctx/memory/bridge.py` (661 lines) | Imports `MEMORY.md` / ChatGPT facts into the memory DB, exports Cutctx memories to organized markdown. Hash-based change detection. |
| Memory MCP server | `cutctx/memory/mcp_server.py` (377 lines) | Exposes memory tools as MCP tools to any MCP-compatible agent (Claude Code, Cursor, Codex, etc.). Re-indexes missing embeddings on startup. |
| Writers | `cutctx/memory/writers/{claude_writer,codex_writer,cursor_writer,generic_writer}.py` | Targeted version of the bridge for `cutctx learn` — writes corrections into `CLAUDE.md` / `AGENTS.md` / `.cursorrules`. |

### Layer 2c: Proxy-Side Memory Injection

| Component | File | What It Does |
|---|---|---|
| `MemoryHandler` | `cutctx/proxy/memory_handler.py` (2497 lines) | On every agent request, searches user's long-term memory and injects relevant memories into the context before forwarding to the LLM. Two modes: `AUTO_TAIL` (silent injection at user-message tail) and `TOOL` (model must call `memory_search`). |
| Memory injection config | `cutctx/proxy/memory_injection.py`, `memory_decision.py`, `helpers.py` | Injection routing, decision logic, and formatting helpers. |
| Memory routes | `cutctx/proxy/routes/memory.py` | `POST /v1/memory/search` endpoint for memory queries. |

### Layer 2d: Value Scoring, Lifecycle, Budget

| Component | File | What It Does |
|---|---|---|
| Value scoring | `cutctx/memory/value.py` | EWMA outcome-linked `value_score`. |
| Budget / decay | `cutctx/memory/budget.py` | Token-budget optimizer: time-based decay, similarity merge, prune. |
| Traffic learner | `cutctx/memory/traffic_learner.py` (1713 lines) | Learns from traffic patterns to improve memory decisions. |
| Factory / system | `cutctx/memory/factory.py`, `cutctx/memory/system.py` (702 lines) | `MemorySystem` high-level facade, system construction wiring. |
| Storage router | `cutctx/memory/storage_router.py` (519 lines) | Scopes storage by workspace — prevents memory leaks across projects. |

### Layer 2e: EE (Commercial) Team Memory

| Component | File | What It Does |
|---|---|---|
| Team Memory API | `cutctx_ee/memory_service/api.py`, `store.py`, `models.py` | Server-side team memory with org/workspace scoping, watermark-based delta sync, and curator review flow. **License: Commercial/EE only.** |

### Layer 3: Failure-Learning Memory (`cutctx learn`)

| Component | File | What It Does |
|---|---|---|
| CLI + analyzer + scanner + writer + registry | `cutctx/cli/learn.py`, `cutctx/cli/learn_share.py`, `cutctx/learn/*.py` | Scans past agent session logs (Claude, Codex, Gemini, Aider, Cursor), detects failure patterns, writes corrections to `CLAUDE.md` / `AGENTS.md` / `.cursorrules`. Plugin architecture for new agents. |

### Layer 4: Rust CCR Persistence

| Component | File | What It Does |
|---|---|---|
| `CcrStore` trait | `crates/cutctx-core/src/ccr/mod.rs` | Put/get/len interface. `compute_key()` uses BLAKE3 truncated to 16 hex chars — matches Python's `<<ccr:HASH>>` marker regex. |
| `SqliteCcrStore` | `crates/cutctx-core/src/ccr/backends/sqlite.rs` | **Production default.** Persistent across worker restarts, shared via DB file. WAL mode, prepared statements, lazy TTL purge. |
| `RedisCcrStore` | `crates/cutctx-core/src/ccr/backends/redis.rs` | Opt-in for multi-worker without sticky sessions. |
| Python bindings | `crates/cutctx-py/src/lib.rs` | `ccr_hash`, `ccr_get`, `ccr_len` exposed; `SqliteCcrStore::open()` wired in. |

---

## 3. External Agent Memory Tool Landscape

### 3.1 Major Tools

| Tool | Stars | Memory Model | Self-Host | MCP | Local-First | Key SDK | Pricing (entry) |
|---|---|---|---|---|---|---|---|
| **Mem0** | 60.1k | Vector + Graph + KV (hybrid) | ✅ Apache 2.0 | ✅ (skill) | ✅ | Python, TS, CLI | Free / $19/mo |
| **Zep / Graphiti** | 28.4k (engine) | Temporal knowledge graph | Partial (engine only) | ✅ | Partial (Neo4j needed) | Python, TS, Go | Free / $25/mo |
| **Supermemory** | 28.1k | Memory + RAG + User Profiles + Connectors | ✅ (one binary) | ✅ | ✅ | TS, Python | Free / $19/mo |
| **Letta (MemGPT)** | 23.6k | Self-editing blocks + git repos | ✅ (Docker) | ✅ | ✅ | TS, Python | Free OSS |
| **LangMem** | 1.5k | LangGraph BaseStore (JSON docs) | ✅ (you operate) | via LangGraph | ✅ | Python | Free |
| **CrewAI Memory** | 54.9k | LLM-analyzed hierarchical + LanceDB | ✅ (file-based) | via CrewAI | Partial | Python | Free |
| **AutoGen Memory** | 59.5k | Pluggable `Memory` protocol | ✅ | ✅ (workbench) | ✅ (you bring DB) | Python, .NET | Free (maintenance) |
| **Khoj** | 35.5k | Semantic search + agents | ✅ (AGPL) | ✅ | ✅ (AGPL) | Python, web | Free |
| **Total Agent Memory** | new (2026) | Multi-embedding + AST codebase | ✅ | ✅ | ✅ (SQLite+FastEmbed) | Python | Free |

### 3.2 Coding-Agent-Specific Memory (2026 Category)

A new wave of tools targeting coding agents specifically:

| Tool | Approach | Key Differentiator |
|---|---|---|
| **agentmemory** (rohitg00) | MCP server, 41 tools, BM25+vector+graph (RRF) | "Replaces CLAUDE.md/.cursorrules" — 581 tests, triple-stream retrieval |
| **agentmemory** (moses-y) | MCP, versioned memories, cascading staleness | Cross-agent single instance for Claude Code/Cursor/Codex |
| **Total Agent Memory** | Local, MCP, multi-embedding, AST codebase ingest | LongMemEval R@5=97.45%, 3D WebGL viewer, tree-sitter 9 langs |
| **Cortex** | Local Rust daemon + HTTP/MCP/desktop | "Install once, all tools share one brain" — 30MB binary |

### 3.3 Common Architecture Pattern

```
Agent → Memory Layer (LLM extraction + dedup + scoring) → Storage (vector + BM25 + graph)
```

**2026 consensus:**
- Hybrid retrieval (vector + BM25 + graph) with cross-encoder rerank
- LLM-driven extraction (no manual `add()` calls)
- MCP server exposure
- Background / sleep-time consolidation
- Local-first by default

---

## 4. Fit Assessment

### Already Integrated

| Tool | Integration | Cutctx Adapter |
|---|---|---|
| **Mem0** | ✅ Full backend adapter | `cutctx/memory/backends/mem0.py` (701 lines), `direct_mem0.py` |
| **Qdrant + Neo4j** | ✅ First-class production backend | `Memory(backend="qdrant-neo4j")`, Docker compose |
| **OpenAI / Ollama embeddings** | ✅ Optional embedder backends | `embedders.py` — sentence-transformers default, OpenAI/Ollama optional |
| **Claude Code native memory** | ✅ Bidirectional sync | `sync_adapters/claude_code.py` |
| **Codex native memory** | ✅ Bidirectional sync | `sync_adapters/codex_agent.py` |

### High-Fit for Integration

| Tool | Fit | Why | Integration Effort |
|---|---|---|---|
| **Zep/Graphiti** | ⚠️ Medium — temporal graph is a gap | Contradiction detection + temporal graph traversal. Cutctx data model already has the fields (`valid_from/valid_until`, `supersession_chain`). Adding a Zep backend adapter gives users the choice without building core graph algorithms. | ~2 weeks (adapter) |
| **Letta self-editing blocks** | ❌ Low — integration is heavy | Letta wants to be the agent runtime, not a memory backend. Better to **build natively** (Cutctx already has 80% of the pieces). | N/A — build approach preferred |
| **Supermemory connectors** | ⚠️ Medium — connectors are a gap | Supermemory's Google Drive, Gmail, Notion integrations are valuable for enterprise memory import. Cutctx has the markdown bridge but no SaaS connector pipeline. | ~4 weeks (connector plugin) |

### Key Differentiator (What Cutctx Has That No One Else Does)

Cutctx's **proxy-side memory injection** (`cutctx/proxy/memory_handler.py`) is unique in the market. Every other memory tool requires the agent to call its API or MCP tools. Cutctx intercepts the agent→LLM request, searches memory, and injects relevant facts into the prompt — the agent may not even know memory exists. This means:

- Works with any agent (no agent-side code changes)
- Zero integration friction: `pip install cutctx-ai && cutctx wrap claude` → memory works
- Consistent across Claude Code, Codex, Gemini CLI, Cursor, etc.
- Memory is applied at the proxy level, not the tool level — covers all traffic

---

## 5. Proposed Feature: Temporal Knowledge Graph

### Goal

Automatically detect contradictory facts and invalidate old ones. E.g., "Alice works on frontend" → later "Alice works on backend" should auto-invalidate the first fact and set its `valid_until`.

### Why It Matters

Without this, the memory system accumulates stale or contradictory facts. The agent gets confused, trust in memory degrades, and users disable it. Zep/Graphiti is the reference implementation (28.4k★, published paper).

### What Exists

The data model already supports it:

```python
# cutctx/memory/models.py
valid_from: datetime | None       # already exists
valid_until: datetime | None      # already exists
supersession_chain: list[str]     # already exists — tracks which memory IDs replaced which
entity_refs: list[str]            # already exists — entity names for graph edges
```

The `sqlite_graph` adapter and entity-relationship edge model also exist.

### What Needs to Change

**Option A: Integrate Zep/Graphiti as a backend (recommended)**

Add `Memory(backend="zep")`:

1. New adapter: `cutctx/memory/backends/zep.py` (∼400 lines)
2. Maps Cutctx's `Memory` model ↔ Zep's `EpisodicNode` / `SemanticNode` schema
3. Passes `add()` → Zep's `add_episode()` with temporal metadata
4. Passes `search()` → Zep's graph + vector hybrid retrieval
5. Requires Zep server running (or Graphiti engine with Neo4j)
6. No changes to the existing memory pipeline — pure backend switch

**Option B: Build contradiction detection in-core (more work, tighter integration)**

1. **Pre-save contradiction check** (`memory/core.py`): Before inserting, query existing memories for same entity + attribute pair. LLM classifier decides: contradiction, refinement, or independent. If contradiction, set `valid_until` on matched entries and `supersession_chain` on new entry.
2. **Temporal graph traversal** (`memory/backends/local.py`): After vector search, traverse entity graph 1-2 hops and collect active facts (valid_until IS NULL).
3. **Community clustering** (`memory/clustering.py`, new): Sleep-time Louvain/Leiden clustering on entity edges for higher-level retrieval.

### Effort Comparison

| Approach | Effort | Risk | Outcome |
|---|---|---|---|
| **A: Zep integration** | 2 weeks | Low — well-defined adapter | Users with Zep get temporal graphs. Default LocalBackend users don't. |
| **B: Build in-core** | 6 weeks | Medium — new LLM call, heuristic tuning | All users get temporal graphs. Deeper integration with existing pipeline. |

### Recommendation

**Do both.** Ship the Zep adapter first (2 weeks) to prove the pattern and serve users who already use Zep. Then build contradiction detection in the default LocalBackend as a follow-up (6 weeks), informed by Zep's algorithms. This gives immediate value while the deeper work develops.

---

## 6. Proposed Feature: Self-Editing Memory Blocks

### Goal

Allow the agent to rewrite its own pinned memory blocks during conversation. Core memory stays in context (pinned), the agent calls `memory_rewrite` to update it, and the system tracks supersession history.

### Why It Matters

Current injection is one-directional: Cutctx pushes memories into context, the agent uses them passively. Self-editing blocks make memory **bidirectional** — the agent actively shapes how it remembers. This is the difference between a smart cache and a learning agent.

Letta/MemGPT (23.6k★, Berkeley) is the reference implementation.

### What Exists (80% complete)

| Component | Status | Details |
|---|---|---|
| Inline extractor | ✅ | Agent already outputs `<memory>` tags during responses — zero-latency extraction |
| LLM memory tools | ✅ | `memory_save`, `memory_search`, `memory_update`, `memory_delete` exist |
| Hierarchical scopes | ✅ | TURN/AGENT/SESSION/USER scopes in `memory/core.py` |
| Proxy injection | ✅ | MemoryHandler injects into every request |
| Value scoring + promotion | ✅ | EWMA value scores, importance, decay, budget pruning |

### What's Missing

#### 6.1 Pinned core memory blocks

**Concept:** Memos that are always injected into context, regardless of search relevance. These are the "must-know" facts.

**Implementation:**
- Add `pinned: bool` to the `Memory` model
- Add `memory.pin(block_name: str, content: str)` and `memory.unpin(block_name: str)` API
- Modify `MemoryHandler` to fetch pinned blocks unconditionally on every request (prepend before search results)
- Store pinned blocks with a reserved scope like `AGENT.core` or `USER.core`

**Files:** `cutctx/memory/core.py` (new `pin`/`unpin` methods), `cutctx/memory/models.py` (add `pinned` flag), `cutctx/proxy/memory_handler.py` (inject pinned blocks)

**Effort:** 1 week

#### 6.2 Memory rewrite tool

**Concept:** A dedicated `memory_rewrite` tool that the agent calls explicitly to update a core memory block. Semantically different from `memory_save` (which adds a new fact) — rewrite replaces an existing understanding.

```python
@tool
async def memory_rewrite(block_name: str, content: str, reason: str):
    """Replace a core memory block. Use when you've learned new info
    that fundamentally changes this understanding.
    
    Args:
        block_name: Name of the block to rewrite (e.g. 'persona', 'project')
        content: New content for the block
        reason: Brief explanation of why this changed
    """
    old = await core.get_pinned(block_name)
    await core.set_pinned(block_name, content)
    if old:
        await core.supersede(old.id, reason=reason)
```

**Files:** `cutctx/memory/tools.py` (new tool), `cutctx/memory/core.py` (supersession wiring already exists)

**Effort:** 1 week

#### 6.3 Automatic promotion / demotion

**Concept:** Memories that are frequently accessed move to core (pinned). Memories no longer referenced get demoted to archival.

```
every N hours or on session end:
    for each pinned block:
        if not referenced in last 5 sessions → demote (unpin)
    for each top-value memory in search results:
        if referenced in 3+ of last 5 sessions and value_score > threshold → promote (pin)
```

**Files:** `cutctx/memory/budget.py` (add promotion pass), `cutctx/memory/value.py` (add reference counter)

**Effort:** 2 weeks

#### 6.4 Consolidation subagent

**Concept:** A background subagent that reads overlapping pinned blocks and consolidates them. Prevents fragmentation from repeated rewrites.

```
sleep-time:
    read all pinned blocks for this user/project
    identify overlapping / contradictory blocks via embedding similarity
    LLM produces consolidated replacement
    write consolidated block, supersede old ones
```

**Files:** New `cutctx/memory/consolidator.py` (∼300 lines)

**Effort:** 3 weeks (requires careful prompt engineering)

### Effort Summary

| Feature | Effort | Dependencies |
|---|---|---|
| Pinned blocks | 1 week | None |
| Memory rewrite tool | 1 week | Pinned blocks |
| Promotion/demotion | 2 weeks | Pinned blocks + reference tracking |
| Consolidation | 3 weeks | Pinned blocks |
| **Total MVP** (pinned + rewrite) | **2 weeks** | |
| **Full feature set** | **7 weeks** | |

### Recommendation

**Ship pinned blocks + rewrite tool as a 2-week MVP.** This gives agents the ability to shape their own memory, which is the core differentiator. Promotion/demotion and consolidation can follow as UX improvements.

---

## 7. Recommendation Summary

| Feature | Approach | Effort | Priority | Rationale |
|---|---|---|---|---|
| **Zep/Graphiti backend adapter** | Integrate | 2 weeks | After pinned blocks | Temporal graphs are valuable but not core differentiator. Zep does it well. Adapter is clean. |
| **Pinned core memory blocks** | Build | 1 week | **Highest** | Foundational — enables all self-editing memory features. Low effort, high impact. |
| **Memory rewrite tool** | Build | 1 week | **Highest** | Gives agents bidirectional memory control. Depends on pinned blocks. |
| **Contradiction detection (LocalBackend)** | Build | 6 weeks | Post-MVP | Temporal graph for default backend. Informed by Zep patterns. |
| **Promotion/demotion** | Build | 2 weeks | Post-MVP | UX polish — ensures pinned blocks stay relevant. |
| **Consolidation subagent** | Build | 3 weeks | Future | Prevents fragmentation. Needs careful prompt engineering. |

### Phase Plan

| Phase | Timeline | Features | Value |
|---|---|---|---|
| P1 | 0-2 weeks | Pinned blocks + rewrite tool | Agent can shape its own memory |
| P2 | 2-4 weeks | Zep/Graphiti adapter | Temporal graphs via backend switch |
| P3 | 4-10 weeks | Contradiction detection (native) + promotion/demotion | Smarter memory lifecycle |
| Future | 10+ weeks | Consolidation subagent | Self-healing memory |

---

## 8. Key Files Reference

| Area | Key Files |
|---|---|
| Memory orchestration | `cutctx/memory/core.py` (910L), `__init__.py` (292L), `system.py` (702L) |
| Data model | `cutctx/memory/models.py` (191L) |
| Default backend | `cutctx/memory/backends/local.py` (843L), `easy.py` (337L) |
| Backend adapters | `memory/backends/mem0.py` (701L), `direct_mem0.py`, `usearch_store.py` |
| Storage adapters | `memory/adapters/sqlite.py`, `sqlite_vector.py`, `sqlite_graph.py`, `fts5.py`, `hnsw.py`, `graph.py`, `embedders.py` |
| LLM tools | `memory/tools.py`, `wrapper.py`, `wrapper_tools.py`, `inline_extractor.py` |
| Proxy injection | `proxy/memory_handler.py` (2497L), `memory_injection.py`, `memory_decision.py` |
| Cross-agent sync | `memory/sync.py`, `sync_adapters/claude_code.py`, `sync_adapters/codex_agent.py` |
| Markdown bridge | `memory/bridge.py` (661L), `bridge_config.py`, `bridge_parsers.py` |
| MCP | `memory/mcp_server.py` (377L) |
| Value + budget | `memory/value.py`, `memory/budget.py`, `traffic_learner.py` (1713L) |
| Failure learning | `cli/learn.py`, `learn/*.py` |
| EE team memory | `cutctx_ee/memory_service/api.py`, `store.py`, `models.py` |
| Rust CCR persistence | `crates/cutctx-core/src/ccr/backends/sqlite.rs`, `redis.rs` |
| Documentation | `PRODUCT_GUIDE.md` §9, `docs/cutctx-learn.md`, `docs/memory-portability.md`, `docs/specs/multi-agent-state.md` |

---

*This document is a capability audit and feature exploration. It is not an implementation spec. The recommended phase plan is a proposal for prioritization.*
