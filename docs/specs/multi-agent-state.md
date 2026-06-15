# Multi-Agent Shared Compression State

**Version:** 1.0  
**Status:** Design Phase  
**Author:** Aryan Singh  
**Date:** 2026-06-15

## Problem Statement

In orchestrator + subagent systems, multiple agents redundantly process the same content:

- Agent A reads and compresses `README.md` → 1000 tokens to 100 tokens
- Agent B reads the same file 2 seconds later → recompresses from scratch (same 1000 tokens to 100 tokens)
- Agent C processes it again, redundantly

For enterprise teams running multi-agent pipelines (10-50+ agents per orchestration run), this redundant compression directly impacts:
- **Cost:** Duplicate compression work multiplies API calls and processing
- **Latency:** Each agent waits for compression instead of reusing results
- **Efficiency:** Compression cache misses within a single orchestration flow

## Motivation

A shared in-process CCR (Compress-Cache-Retrieve) store means:
- Agent B gets the existing CCR pointer at zero cost
- No recompression, no duplicate storage
- Compression cache hits > 95% in multi-agent workflows

This is an optimization layer for **within-process** agent coordination. Agents in the same process share a mutable, thread-safe compression cache keyed by content hash. When Agent B compresses content that Agent A already compressed, it retrieves the cached result instantly.

## User Stories

### Story 1: Orchestrator Reduces Redundant Compression
**As a** platform engineer building a multi-agent orchestration system  
**I want to** share compression state across orchestrator + subagent instances  
**So that** the same content (e.g., user query, documentation) isn't recompressed twice  

**Acceptance Criteria:**
- Multiple agents in the same process can access the same compression cache
- Content hash is stable (deterministic) across agents
- Agents retrieve cached results in < 1ms
- Cache respects workspace boundaries (no cross-workspace leakage)

### Story 2: Agent Tracks What It Has Compressed
**As an** agent developer  
**I want to** see what content my agent has already compressed (for debugging and cost analysis)  
**So that** I can understand compression behavior and optimize my workflow

**Acceptance Criteria:**
- Agent can query "what have I compressed so far?"
- Result includes content hash, size, CCR pointer, timestamp
- Compatible with cost estimators and observability tools

### Story 3: Eviction Respects LRU + TTL
**As a** platform engineer managing a long-running orchestration  
**I want to** cache compression results with automatic eviction  
**So that** memory usage stays bounded even in workflows with 1000s of compressed items

**Acceptance Criteria:**
- Default cache size: 1000 entries
- Default TTL: 1 hour
- Eviction policy: LRU (least recently used)
- Operators can configure max_entries and ttl_seconds

### Story 4: Multiple Agents Register Themselves
**As an** orchestrator  
**I want to** track which agents are active and what they're processing  
**So that** I can monitor agent health and detect bottlenecks

**Acceptance Criteria:**
- Agents register on startup, unregister on shutdown
- Registry shows active agents and their current tasks
- Registry has hooks for observability/metrics systems

## Technical Design

### Architecture Overview

```
┌──────────────────────────────────────────────────────┐
│         MultiAgentCoordinator (Singleton)             │
│                                                       │
│  ┌──────────────────┐      ┌──────────────────────┐  │
│  │  AgentRegistry   │      │ SharedCompressionCache
│  │                  │      │                      │  │
│  │ • register()     │      │ • get_or_compress()  │  │
│  │ • unregister()   │      │ • get_compressed()   │  │
│  │ • active_agents()        │ • stats()            │  │
│  │ • current_task() │      │ • LRU eviction       │  │
│  └──────────────────┘      │ • TTL expiry         │  │
│                             └──────────────────────┘  │
└──────────────────────────────────────────────────────┘
        ↑                              ↑
        │ register/unregister          │ compress/retrieve
        │                              │
    ┌───────────┐  ┌───────────┐  ┌───────────┐
    │  Agent A  │  │  Agent B  │  │  Agent C  │
    └───────────┘  └───────────┘  └───────────┘
```

### 1. Content Identity

**Key:** SHA256(content)[:16]  
**Value:** (compressed_content, agent_id, timestamp, ccr_pointer)

- Hash is deterministic: same content always hashes to the same key
- 16-char hex provides 64-bit collision space (acceptable for in-memory cache)
- Collision detection logs a warning; duplicate stores update the entry

### 2. Agent Coordination

#### AgentRegistry

```python
class AgentRegistry:
    def register(self, agent_id: str, metadata: dict | None = None) -> None:
        """Register an agent as active."""
        
    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the active registry."""
        
    def active_agents(self) -> list[str]:
        """List all currently active agent IDs."""
        
    def set_current_task(self, agent_id: str, task: str) -> None:
        """Update the current task for an agent."""
        
    def get_agent_context(self, agent_id: str) -> dict:
        """Get metadata, task, and compressed content for this agent."""
```

#### SharedCompressionCache

Thread-safe, in-memory cache with LRU eviction and TTL:

```python
class SharedCompressionCache:
    def get_or_compress(
        self, 
        content: str, 
        compress_fn: callable, 
        agent_id: str
    ) -> tuple[str, bool]:
        """
        Get or compress content.
        
        Returns: (compressed_result, was_cache_hit)
        
        Logic:
        1. Hash the content
        2. Check if hash exists in cache and is not expired
        3. If cache hit: record access, return cached result
        4. If cache miss: call compress_fn(), store result, return new result
        """
        
    def register_compression(
        self,
        content_hash: str,
        compressed: str,
        agent_id: str,
    ) -> None:
        """Manually register a compression result."""
        
    def get_compressed(self, content_hash: str) -> str | None:
        """Retrieve compressed content by hash."""
        
    def stats(self) -> dict:
        """
        Return cache statistics:
        - cache_hits: Total hits
        - cache_misses: Total misses
        - agents_active: Count of active agents
        - entries_count: Current cache size
        - hit_rate: cache_hits / (cache_hits + cache_misses)
        """
```

#### MultiAgentCoordinator (Singleton)

Combines both registries and caches:

```python
class MultiAgentCoordinator:
    @classmethod
    def get_instance(cls) -> MultiAgentCoordinator:
        """Get the singleton instance."""
        
    def compress_shared(
        self,
        content: str,
        agent_id: str,
        compress_fn: callable | None = None,
    ) -> SharedCompressionResult:
        """
        Main entry point for multi-agent compression.
        
        Args:
            content: Raw content to compress
            agent_id: ID of the agent requesting compression
            compress_fn: Compression function (uses SharedContext.put() if None)
            
        Returns:
            SharedCompressionResult with:
            - compressed_content: Compressed version
            - cache_hit: Whether this was a cache hit
            - agent_id: Agent that performed compression (if miss)
            - content_hash: SHA256(content)[:16]
            - ccr_pointer: Reference for retrieval
        """
        
    def get_agent_context(self, agent_id: str) -> dict:
        """
        Get what this agent has compressed so far.
        
        Returns dict with:
        - agent_id
        - active: bool
        - current_task: str | None
        - compressed_count: int
        - total_tokens_saved: int
        - items: list of {hash, size, timestamp}
        """
        
    def stats(self) -> dict:
        """Aggregated stats across all agents."""
```

### 3. Cross-Agent Retrieval

Any agent can retrieve any content by hash:

```python
def retrieve_compressed(content_hash: str) -> str | None:
    """Get compressed content from any agent's prior compression."""
```

### 4. Eviction Policy

**In-Memory Cache:**
- Max entries: 1000 (configurable)
- TTL: 3600 seconds = 1 hour (configurable)
- Eviction: LRU (least recently used by timestamp)
- Algorithm:
  1. On access, update `last_accessed` timestamp
  2. Before eviction, remove all expired entries
  3. If still at capacity, remove oldest entry by `last_accessed`

**Example:**
```
Time 0:00 - Agent A compresses file1 (size 1KB)
Time 0:05 - Agent B compresses file1 (cache hit, immediate)
Time 0:10 - Agent C compresses file2 (size 1KB)
Time 0:20 - Agent A accesses file1 (updates timestamp)
Time 1:05 - file1 expires (TTL 1h from original create time)
            OR removed by LRU if cache full
```

### 5. Workspace Scoping

**Security:** No cross-workspace leakage (learned from ccr/context_tracker.py incident)

Each compression entry includes a `workspace_key` (CWD or project identity):

```python
@dataclass
class CompressionCacheEntry:
    content_hash: str
    compressed: str
    agent_id: str
    workspace_key: str  # Prevents cross-project leaks
    timestamp: float
    ccr_pointer: str | None = None
```

Retrieve only works within same workspace:

```python
def get_compressed(self, content_hash: str, workspace_key: str) -> str | None:
    """Get compressed content only if workspace matches."""
```

### 6. HTTP Endpoint (Optional: Future)

For distributed agents across processes:

```
POST /v1/compress
{
  "content": "...",
  "agent_id": "agent-123",
  "workspace_key": "proj-abc"
}
→ { "compressed": "...", "cache_hit": true, "hash": "abc123" }

GET /v1/compressed/:hash?workspace_key=proj-abc
→ { "content": "..." }
```

## API Design

### Import

```python
from headroom import MultiAgentCoordinator, SharedCompressionResult

coordinator = MultiAgentCoordinator.get_instance()
```

### Usage Example

```python
# Agent A: Compress and store
result = coordinator.compress_shared(
    content=readme_text,
    agent_id="agent-research",
    compress_fn=None  # Uses SharedContext.put() by default
)
print(result.cache_hit)  # False (first time)
print(result.content_hash)  # "abc123def456"

# Agent B: Same content, reuse
result2 = coordinator.compress_shared(
    content=readme_text,
    agent_id="agent-followup"
)
print(result2.cache_hit)  # True!
assert result2.compressed_content == result.compressed_content
assert result2.content_hash == result.content_hash

# Debugging: What did agent-research compress?
context = coordinator.get_agent_context("agent-research")
print(context["compressed_count"])  # 5
print(context["total_tokens_saved"])  # 2500
```

## Success Metrics

1. **Duplicate Compression Rate < 5%**
   - In a 10-agent workflow, < 5% of compressions should be on content already compressed
   - Measure: `duplicate_compressions / total_compressions`

2. **Cache Hit Latency < 1ms**
   - Retrieving cached compression should be near-instant
   - Measure: p95 latency of `get_or_compress()` on cache hit

3. **Memory Bounded**
   - Cache size stays under (max_entries * avg_compressed_size)
   - No memory leaks from stale entries
   - TTL and LRU eviction working as designed

4. **Workspace Isolation**
   - Zero cross-project compression leakage
   - Audit: no compression from Project A appears in Project B's cache

5. **Agent Observability**
   - Operators can see per-agent compression stats
   - Useful for cost estimation and debugging

## Implementation Phases

### Phase 1: Core (This PR)
- AgentRegistry
- SharedCompressionCache (in-memory, thread-safe)
- MultiAgentCoordinator (singleton)
- Unit tests

### Phase 2: Integration
- Hook into SharedContext.put() to auto-register compressions
- Add stats() endpoint for observability
- Update CCR context_tracker to respect workspace keys

### Phase 3: Distributed (Future)
- Redis backend for cross-process sharing
- HTTP proxy endpoint for inter-process agents
- Telemetry integration

## Open Questions

1. **Workspace Key Source:** Should agents pass workspace_key, or derive from CWD?
   - Recommendation: Pass explicitly for clarity; default to CWD if not provided

2. **Collision Handling:** If two different contents hash to same key, log warning or error?
   - Recommendation: Log warning (SHA256[:16] has acceptable collision rate)

3. **Compression Function:** Should we always use SharedContext.put(), or support custom compressors?
   - Recommendation: Support callable compress_fn for flexibility (agents may use different strategies)

4. **Metrics Export:** Should stats() update a metrics registry (Prometheus, etc.)?
   - Recommendation: Return dict; let operators wire to their metrics system

## References

- `headroom/shared_context.py` — Existing SharedContext implementation
- `headroom/ccr/context_tracker.py` — CCR tracking (see lines 40-48 for cross-project leak incident)
- `headroom/cache/compression_store.py` — Compression cache implementation
