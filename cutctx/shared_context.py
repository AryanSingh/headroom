"""SharedContext — compressed inter-agent context sharing.

When agents hand off to each other, context gets replayed in full.
SharedContext compresses what moves between agents, using Cutctx's
existing CCR (Compress-Cache-Retrieve) architecture.

Usage:

    from cutctx import SharedContext

    ctx = SharedContext()

    # Agent A stores large output
    ctx.put("research", big_research_output)

    # Agent B gets compressed version (~80% smaller)
    summary = ctx.get("research")

    # Agent B needs full details on something specific
    full = ctx.get("research", full=True)

Works with any agent framework. The compression pipeline is the same
one used by the proxy and MCP server.

Multi-Agent Compression State:

    from cutctx import MultiAgentCoordinator

    coordinator = MultiAgentCoordinator.get_instance()

    # Agent A: Compress content
    result = coordinator.compress_shared(
        content=large_content,
        agent_id="agent-research"
    )

    # Agent B: Reuse compression from Agent A (cache hit)
    result2 = coordinator.compress_shared(
        content=large_content,
        agent_id="agent-followup"
    )
    # result2.cache_hit == True, result2.compressed_content == result.compressed_content
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """A stored context entry with original and compressed versions."""

    key: str
    original: str
    compressed: str
    original_tokens: int
    compressed_tokens: int
    agent: str | None
    timestamp: float
    transforms: list[str] = field(default_factory=list)

    @property
    def savings_percent(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return round((1 - self.compressed_tokens / self.original_tokens) * 100, 1)


@dataclass
class SharedContextStats:
    """Aggregated stats for the shared context."""

    entries: int
    total_original_tokens: int
    total_compressed_tokens: int
    total_tokens_saved: int
    savings_percent: float


class SharedContext:
    """Compressed shared context for multi-agent workflows.

    Agents put content in, other agents get compressed versions out.
    Originals are stored for on-demand full retrieval.

    Args:
        model: Model name for token counting (default: claude-sonnet-4-5).
        ttl: Time-to-live in seconds (default: 3600 = 1 hour).
        max_entries: Maximum stored entries (default: 100).
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250929",
        ttl: int = 3600,
        max_entries: int = 100,
    ) -> None:
        self._model = model
        self._ttl = ttl
        self._max_entries = max_entries
        self._entries: dict[str, ContextEntry] = {}
        self._lock = threading.Lock()

    def put(
        self,
        key: str,
        content: str,
        *,
        agent: str | None = None,
    ) -> ContextEntry:
        """Store content under a key, compressing automatically.

        Args:
            key: Name for this context (e.g., "research_findings").
            content: The content to store and compress.
            agent: Optional agent identifier for tracking.

        Returns:
            ContextEntry with compression stats.
        """
        from cutctx.compress import compress

        messages = [{"role": "tool", "content": content}]
        result = compress(messages, model=self._model)

        compressed = result.messages[0].get("content", content)
        if not isinstance(compressed, str):
            import json

            compressed = json.dumps(compressed)

        entry = ContextEntry(
            key=key,
            original=content,
            compressed=compressed,
            original_tokens=result.tokens_before,
            compressed_tokens=result.tokens_after,
            agent=agent,
            timestamp=time.time(),
            transforms=result.transforms_applied,
        )

        with self._lock:
            self._evict_if_needed()
            self._entries[key] = entry

        logger.debug(
            "SharedContext.put(%s): %d → %d tokens (%.1f%% saved)",
            key,
            entry.original_tokens,
            entry.compressed_tokens,
            entry.savings_percent,
        )

        return entry

    def get(
        self,
        key: str,
        *,
        full: bool = False,
    ) -> str | None:
        """Get content by key.

        Args:
            key: The key to retrieve.
            full: If True, return the original uncompressed content.
                  If False (default), return the compressed version.

        Returns:
            Content string, or None if key not found or expired.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if time.time() - entry.timestamp > self._ttl:
                del self._entries[key]
                return None

        return entry.original if full else entry.compressed

    def get_entry(self, key: str) -> ContextEntry | None:
        """Get the full ContextEntry with metadata."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if time.time() - entry.timestamp > self._ttl:
                del self._entries[key]
                return None
            return entry

    def keys(self) -> list[str]:
        """List all non-expired keys."""
        now = time.time()
        with self._lock:
            return [k for k, e in self._entries.items() if now - e.timestamp <= self._ttl]

    def stats(self) -> SharedContextStats:
        """Get aggregated stats."""
        now = time.time()
        with self._lock:
            active = [e for e in self._entries.values() if now - e.timestamp <= self._ttl]
        total_orig = sum(e.original_tokens for e in active)
        total_comp = sum(e.compressed_tokens for e in active)
        total_saved = total_orig - total_comp
        pct = round(total_saved / total_orig * 100, 1) if total_orig > 0 else 0.0
        return SharedContextStats(
            entries=len(active),
            total_original_tokens=total_orig,
            total_compressed_tokens=total_comp,
            total_tokens_saved=total_saved,
            savings_percent=pct,
        )

    def clear(self) -> None:
        """Remove all entries."""
        with self._lock:
            self._entries.clear()

    def _evict_if_needed(self) -> None:
        """Evict expired and oldest entries if at capacity. Lock must be held."""
        now = time.time()
        expired = [k for k, e in self._entries.items() if now - e.timestamp > self._ttl]
        for k in expired:
            del self._entries[k]

        while len(self._entries) >= self._max_entries:
            oldest_key = min(self._entries, key=lambda k: self._entries[k].timestamp)
            del self._entries[oldest_key]


@dataclass
class CompressionCacheEntry:
    """A cached compression result shared across agents."""

    content_hash: str
    compressed: str
    agent_id: str  # ID of agent that performed compression
    workspace_key: str  # Project/CWD identity (prevent cross-project leaks)
    timestamp: float
    last_accessed: float
    ccr_pointer: str | None = None  # Reference for CCR retrieval
    original_size: int = 0  # Original content size in bytes
    compressed_size: int = 0
    original_tokens: int = 0
    compressed_tokens: int = 0

    @property
    def age_seconds(self) -> float:
        """Age in seconds from creation."""
        return time.time() - self.timestamp

    def mark_accessed(self) -> None:
        """Update last access time."""
        self.last_accessed = time.time()


@dataclass
class SharedCompressionResult:
    """Result from compress_shared() operation."""

    compressed_content: str
    cache_hit: bool
    agent_id: str  # ID of agent that performed compression
    content_hash: str
    workspace_key: str
    ccr_pointer: str | None = None
    original_tokens: int = 0
    compressed_tokens: int = 0


@dataclass
class AgentContextInfo:
    """Context information for a specific agent."""

    agent_id: str
    active: bool
    current_task: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    compressed_items: list[dict[str, Any]] = field(default_factory=list)
    total_items_compressed: int = 0
    total_original_tokens: int = 0
    total_compressed_tokens: int = 0
    total_tokens_saved: int = 0

    @property
    def savings_percent(self) -> float:
        """Compression savings as percentage."""
        if self.total_original_tokens == 0:
            return 0.0
        return round((1 - self.total_compressed_tokens / self.total_original_tokens) * 100, 1)


class AgentRegistry:
    """Track active agents and their tasks in a multi-agent system."""

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register(self, agent_id: str, metadata: dict[str, Any] | None = None) -> None:
        """Register an agent as active.

        Args:
            agent_id: Unique identifier for the agent.
            metadata: Optional metadata (e.g., version, framework).
        """
        with self._lock:
            self._agents[agent_id] = {
                "id": agent_id,
                "registered_at": time.time(),
                "current_task": None,
                "metadata": metadata or {},
            }
        logger.debug(f"AgentRegistry: Registered agent {agent_id}")

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the active registry.

        Args:
            agent_id: ID of agent to unregister.
        """
        with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                logger.debug(f"AgentRegistry: Unregistered agent {agent_id}")

    def active_agents(self) -> list[str]:
        """List all currently active agent IDs.

        Returns:
            List of agent IDs.
        """
        with self._lock:
            return list(self._agents.keys())

    def set_current_task(self, agent_id: str, task: str) -> None:
        """Update the current task for an agent.

        Args:
            agent_id: ID of agent.
            task: Task description or name.
        """
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id]["current_task"] = task
                logger.debug(f"AgentRegistry: Agent {agent_id} -> task: {task}")

    def get_current_task(self, agent_id: str) -> str | None:
        """Get the current task for an agent.

        Args:
            agent_id: ID of agent.

        Returns:
            Task string, or None if not set or agent not found.
        """
        with self._lock:
            if agent_id in self._agents:
                return self._agents[agent_id].get("current_task")
            return None

    def get_agent_info(self, agent_id: str) -> dict[str, Any] | None:
        """Get full info for an agent.

        Args:
            agent_id: ID of agent.

        Returns:
            Agent info dict, or None if not found.
        """
        with self._lock:
            return self._agents.get(agent_id)

    def get_all_agents(self) -> list[dict[str, Any]]:
        """Get info for all active agents.

        Returns:
            List of agent info dicts.
        """
        with self._lock:
            return list(self._agents.values())

    def clear(self) -> None:
        """Clear all registered agents."""
        with self._lock:
            self._agents.clear()


class SharedCompressionCache:
    """Thread-safe in-memory compression cache shared across agents.

    Uses content hash as key, with LRU eviction and TTL expiry.
    """

    def __init__(
        self,
        max_entries: int = 1000,
        ttl_seconds: int = 3600,
    ) -> None:
        """Initialize the shared compression cache.

        Args:
            max_entries: Maximum number of cached entries (default 1000).
            ttl_seconds: Time-to-live for entries in seconds (default 3600 = 1h).
        """
        self._cache: dict[str, CompressionCacheEntry] = {}
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds

        # Statistics
        self._cache_hits = 0
        self._cache_misses = 0

    def get_or_compress(
        self,
        content: str,
        compress_fn: Callable[[str], str] | None,
        agent_id: str,
        workspace_key: str = "",
    ) -> tuple[str, bool]:
        """Get cached compression or call compress_fn().

        Args:
            content: Content to compress.
            compress_fn: Compression function that returns compressed string.
            agent_id: ID of agent requesting compression.
            workspace_key: Workspace/project identity for scoping.

        Returns:
            Tuple of (compressed_content, was_cache_hit)
        """
        content_hash = self._hash_content(content)

        # Try to get from cache
        with self._lock:
            entry = self._cache.get(content_hash)

            if (
                entry is not None
                and entry.workspace_key == workspace_key
                and not self._is_expired(entry)
            ):
                # Cache hit
                entry.mark_accessed()
                self._cache_hits += 1
                logger.debug(
                    f"SharedCompressionCache: Hit for {content_hash[:8]} (agent={agent_id})"
                )
                return entry.compressed, True

            # Cache miss
            self._cache_misses += 1

        # Compress with provided function
        if compress_fn is None:
            # Use SharedContext.put() as default compressor
            ctx = SharedContext()
            result = ctx.put("_temp", content, agent=agent_id)
            compressed = result.compressed
            original_tokens = result.original_tokens
            compressed_tokens = result.compressed_tokens
        else:
            compressed = compress_fn(content)
            original_tokens = 0
            compressed_tokens = 0

        # Store in cache
        now = time.time()
        entry = CompressionCacheEntry(
            content_hash=content_hash,
            compressed=compressed,
            agent_id=agent_id,
            workspace_key=workspace_key,
            timestamp=now,
            last_accessed=now,
            original_size=len(content),
            compressed_size=len(compressed),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
        )

        with self._lock:
            self._evict_if_needed()
            self._cache[content_hash] = entry

        logger.debug(f"SharedCompressionCache: Stored {content_hash[:8]} (agent={agent_id})")
        return compressed, False

    def register_compression(
        self,
        content_hash: str,
        compressed: str,
        agent_id: str,
        workspace_key: str = "",
        original_size: int = 0,
        compressed_size: int = 0,
        original_tokens: int = 0,
        compressed_tokens: int = 0,
    ) -> None:
        """Manually register a compression result.

        Args:
            content_hash: SHA256(content)[:16]
            compressed: Compressed content.
            agent_id: ID of agent that performed compression.
            workspace_key: Workspace/project identity.
            original_size: Size of original content in bytes.
            compressed_size: Size of compressed content in bytes.
            original_tokens: Token count before compression.
            compressed_tokens: Token count after compression.
        """
        now = time.time()
        entry = CompressionCacheEntry(
            content_hash=content_hash,
            compressed=compressed,
            agent_id=agent_id,
            workspace_key=workspace_key,
            timestamp=now,
            last_accessed=now,
            original_size=original_size,
            compressed_size=compressed_size,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
        )

        with self._lock:
            self._evict_if_needed()
            self._cache[content_hash] = entry

        logger.debug(f"SharedCompressionCache: Registered {content_hash[:8]}")

    def get_compressed(self, content_hash: str, workspace_key: str = "") -> str | None:
        """Retrieve compressed content by hash.

        Args:
            content_hash: Hash from get_or_compress().
            workspace_key: Workspace/project identity for scoping.

        Returns:
            Compressed content, or None if not found or expired.
        """
        with self._lock:
            entry = self._cache.get(content_hash)

            if (
                entry is not None
                and entry.workspace_key == workspace_key
                and not self._is_expired(entry)
            ):
                entry.mark_accessed()
                return entry.compressed

        return None

    def get_entry(self, content_hash: str, workspace_key: str = "") -> CompressionCacheEntry | None:
        """Retrieve full cache entry by hash.

        Args:
            content_hash: Hash from get_or_compress().
            workspace_key: Workspace/project identity for scoping.

        Returns:
            CompressionCacheEntry, or None if not found or expired.
        """
        with self._lock:
            entry = self._cache.get(content_hash)

            if (
                entry is not None
                and entry.workspace_key == workspace_key
                and not self._is_expired(entry)
            ):
                entry.mark_accessed()
                return entry

        return None

    def list_by_agent(self, agent_id: str, workspace_key: str = "") -> list[CompressionCacheEntry]:
        """List all cache entries created by an agent.

        Args:
            agent_id: Agent ID to filter by.
            workspace_key: Workspace/project identity for scoping.

        Returns:
            List of active cache entries from this agent.
        """
        now = time.time()
        with self._lock:
            return [
                e
                for e in self._cache.values()
                if e.agent_id == agent_id
                and e.workspace_key == workspace_key
                and not (now - e.timestamp > self._ttl_seconds)
            ]

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache_hits, cache_misses, entries_count, agents_active, hit_rate.
        """
        now = time.time()
        with self._lock:
            # Count active entries
            active_entries = [
                e for e in self._cache.values() if now - e.timestamp <= self._ttl_seconds
            ]
            active_agents = {e.agent_id for e in active_entries}

            total_requests = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0.0

            total_original_tokens = sum(e.original_tokens for e in active_entries)
            total_compressed_tokens = sum(e.compressed_tokens for e in active_entries)
            total_tokens_saved = total_original_tokens - total_compressed_tokens

            return {
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "hit_rate_percent": round(hit_rate, 1),
                "entries_count": len(active_entries),
                "total_entries_ever": len(self._cache),
                "agents_active": len(active_agents),
                "max_entries": self._max_entries,
                "ttl_seconds": self._ttl_seconds,
                "total_original_tokens": total_original_tokens,
                "total_compressed_tokens": total_compressed_tokens,
                "total_tokens_saved": total_tokens_saved,
            }

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0

    def _is_expired(self, entry: CompressionCacheEntry) -> bool:
        """Check if entry has exceeded TTL. Lock must be held."""
        return time.time() - entry.timestamp > self._ttl_seconds

    def _evict_if_needed(self) -> None:
        """Evict expired and LRU entries if at capacity. Lock must be held."""
        now = time.time()

        # First, remove expired entries
        expired_keys = [k for k, e in self._cache.items() if now - e.timestamp > self._ttl_seconds]
        for k in expired_keys:
            del self._cache[k]

        # Then, evict LRU entries if still at capacity
        while len(self._cache) >= self._max_entries:
            # Find least recently accessed (by last_accessed timestamp)
            lru_key = min(self._cache, key=lambda k: self._cache[k].last_accessed)
            del self._cache[lru_key]

    @staticmethod
    def _hash_content(content: str) -> str:
        """Hash content deterministically.

        Uses SHA256 truncated to 16 hex chars (64-bit collision space).

        Args:
            content: Content to hash.

        Returns:
            Hex string hash.
        """
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class MultiAgentCoordinator:
    """Singleton coordinator for multi-agent compression state.

    Manages shared compression cache and agent registry to avoid redundant
    compression across multiple agents in the same process.
    """

    _instance: MultiAgentCoordinator | None = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        max_cache_entries: int = 1000,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        """Initialize the coordinator.

        Args:
            max_cache_entries: Max entries in shared compression cache.
            cache_ttl_seconds: TTL for cache entries in seconds.
        """
        self._cache = SharedCompressionCache(max_cache_entries, cache_ttl_seconds)
        self._registry = AgentRegistry()
        self._lock = threading.Lock()

        # Agent compression tracking
        self._agent_compressions: dict[str, list[str]] = {}  # agent_id -> [hash1, hash2, ...]

    @classmethod
    def get_instance(cls) -> MultiAgentCoordinator:
        """Get the singleton instance.

        Returns:
            MultiAgentCoordinator singleton.
        """
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = MultiAgentCoordinator()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (mainly for testing)."""
        with cls._instance_lock:
            cls._instance = None

    def compress_shared(
        self,
        content: str,
        agent_id: str,
        compress_fn: Callable[[str], str] | None = None,
        workspace_key: str = "",
    ) -> SharedCompressionResult:
        """Compress content, reusing cached results from other agents.

        Main entry point for multi-agent compression.

        Args:
            content: Content to compress.
            agent_id: ID of requesting agent.
            compress_fn: Compression function (uses SharedContext if None).
            workspace_key: Workspace/project identity (prevents cross-project leaks).

        Returns:
            SharedCompressionResult with compression details and cache_hit flag.
        """
        # Ensure agent is registered
        if agent_id not in self._registry.active_agents():
            self._registry.register(agent_id)

        # Try get_or_compress from shared cache
        compressed, cache_hit = self._cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id=agent_id,
            workspace_key=workspace_key,
        )

        # Get the cache entry for metadata
        content_hash = SharedCompressionCache._hash_content(content)
        entry = self._cache.get_entry(content_hash, workspace_key)

        # Track compression for this agent
        with self._lock:
            if agent_id not in self._agent_compressions:
                self._agent_compressions[agent_id] = []
            self._agent_compressions[agent_id].append((workspace_key, content_hash))

        return SharedCompressionResult(
            compressed_content=compressed,
            cache_hit=cache_hit,
            agent_id=agent_id,
            content_hash=content_hash,
            workspace_key=workspace_key,
            original_tokens=entry.original_tokens if entry else 0,
            compressed_tokens=entry.compressed_tokens if entry else 0,
        )

    def get_agent_context(self, agent_id: str) -> AgentContextInfo:
        """Get compression context for a specific agent.

        Returns what this agent has compressed so far: items, tokens, stats.

        Args:
            agent_id: ID of agent to query.

        Returns:
            AgentContextInfo with agent's compression activities.
        """
        is_active = agent_id in self._registry.active_agents()
        agent_info = self._registry.get_agent_info(agent_id) or {}
        current_task = agent_info.get("current_task")

        # Get all items this agent compressed
        with self._lock:
            compressed_hashes = self._agent_compressions.get(agent_id, [])

        compressed_items = []
        total_original_tokens = 0
        total_compressed_tokens = 0

        for workspace_key, content_hash in compressed_hashes:
            entry = self._cache.get_entry(content_hash, workspace_key)
            if entry:
                compressed_items.append(
                    {
                        "hash": content_hash,
                        "original_size": entry.original_size,
                        "compressed_size": entry.compressed_size,
                        "original_tokens": entry.original_tokens,
                        "compressed_tokens": entry.compressed_tokens,
                        "timestamp": entry.timestamp,
                        "age_seconds": entry.age_seconds,
                    }
                )
                total_original_tokens += entry.original_tokens
                total_compressed_tokens += entry.compressed_tokens

        total_tokens_saved = total_original_tokens - total_compressed_tokens

        return AgentContextInfo(
            agent_id=agent_id,
            active=is_active,
            current_task=current_task,
            metadata=agent_info.get("metadata", {}),
            compressed_items=compressed_items,
            total_items_compressed=len(compressed_items),
            total_original_tokens=total_original_tokens,
            total_compressed_tokens=total_compressed_tokens,
            total_tokens_saved=total_tokens_saved,
        )

    def register_agent(self, agent_id: str, metadata: dict[str, Any] | None = None) -> None:
        """Register an agent with optional metadata.

        Args:
            agent_id: Unique agent ID.
            metadata: Optional metadata dict (e.g., version, framework).
        """
        self._registry.register(agent_id, metadata)

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent.

        Args:
            agent_id: Agent ID to unregister.
        """
        self._registry.unregister(agent_id)

    def set_agent_task(self, agent_id: str, task: str) -> None:
        """Set the current task for an agent.

        Args:
            agent_id: Agent ID.
            task: Task description.
        """
        self._registry.set_current_task(agent_id, task)

    def get_active_agents(self) -> list[str]:
        """Get list of active agent IDs.

        Returns:
            List of agent IDs.
        """
        return self._registry.active_agents()

    def stats(self) -> dict[str, Any]:
        """Get aggregated statistics across all agents.

        Returns:
            Dict with cache stats, active agents, and compression summary.
        """
        cache_stats = self._cache.stats()
        active_agents = self._registry.active_agents()

        # Agent summary
        agent_summaries = []
        for agent_id in active_agents:
            context = self.get_agent_context(agent_id)
            agent_summaries.append(
                {
                    "agent_id": agent_id,
                    "items_compressed": context.total_items_compressed,
                    "tokens_saved": context.total_tokens_saved,
                    "current_task": context.current_task,
                }
            )

        return {
            "cache": cache_stats,
            "agents": {
                "active_count": len(active_agents),
                "summaries": agent_summaries,
            },
        }

    def clear(self) -> None:
        """Clear all state (mainly for testing)."""
        self._cache.clear()
        self._registry.clear()
        with self._lock:
            self._agent_compressions.clear()
