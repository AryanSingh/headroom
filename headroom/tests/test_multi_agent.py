"""Tests for MultiAgentCoordinator and related compression/registry classes.

Covers:
  - AgentRegistry: registration, unregistration, task tracking
  - SharedCompressionCache: cache hits/misses, LRU eviction, TTL expiry
  - MultiAgentCoordinator: singleton pattern, shared compression, agent context
  - Thread safety: concurrent compression without state corruption
  - Workspace scoping: separate cache entries for different workspace keys
"""

import threading
import time
from unittest.mock import MagicMock

import pytest

from headroom.shared_context import (
    AgentContextInfo,
    AgentRegistry,
    CompressionCacheEntry,
    MultiAgentCoordinator,
    SharedCompressionCache,
    SharedCompressionResult,
)


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def setup_method(self):
        """Create fresh registry for each test."""
        self.registry = AgentRegistry()

    def test_register_agent(self):
        """Test registering an agent."""
        self.registry.register("agent-1", metadata={"version": "1.0"})
        assert "agent-1" in self.registry.active_agents()

    def test_unregister_agent(self):
        """Test unregistering an agent."""
        self.registry.register("agent-1")
        self.registry.unregister("agent-1")
        assert "agent-1" not in self.registry.active_agents()

    def test_active_agents_list(self):
        """Test listing active agents."""
        self.registry.register("agent-1")
        self.registry.register("agent-2")
        assert set(self.registry.active_agents()) == {"agent-1", "agent-2"}

    def test_set_current_task(self):
        """Test setting current task for an agent."""
        self.registry.register("agent-1")
        self.registry.set_current_task("agent-1", "compress_output")
        assert self.registry.get_current_task("agent-1") == "compress_output"

    def test_get_current_task_unregistered(self):
        """Test getting task for unregistered agent returns None."""
        assert self.registry.get_current_task("agent-nonexistent") is None

    def test_get_current_task_not_set(self):
        """Test getting task when not set returns None."""
        self.registry.register("agent-1")
        assert self.registry.get_current_task("agent-1") is None

    def test_set_task_unregistered_agent_ignored(self):
        """Test setting task on unregistered agent is silently ignored."""
        self.registry.set_current_task("agent-nonexistent", "task")
        # No error, just silently ignored

    def test_get_agent_info(self):
        """Test retrieving full agent info."""
        self.registry.register("agent-1", metadata={"framework": "langgraph"})
        info = self.registry.get_agent_info("agent-1")
        assert info is not None
        assert info["id"] == "agent-1"
        assert info["metadata"]["framework"] == "langgraph"

    def test_get_all_agents(self):
        """Test retrieving all agents."""
        self.registry.register("agent-1")
        self.registry.register("agent-2")
        agents = self.registry.get_all_agents()
        assert len(agents) == 2
        assert {a["id"] for a in agents} == {"agent-1", "agent-2"}

    def test_clear_all_agents(self):
        """Test clearing all agents."""
        self.registry.register("agent-1")
        self.registry.register("agent-2")
        self.registry.clear()
        assert self.registry.active_agents() == []


class TestSharedCompressionCache:
    """Tests for SharedCompressionCache."""

    def setup_method(self):
        """Create fresh cache for each test."""
        self.cache = SharedCompressionCache(max_entries=10, ttl_seconds=3600)

    def test_get_or_compress_cache_miss(self):
        """Test cache miss calls compress_fn."""
        compress_fn = MagicMock(return_value="compressed_output")
        content = "large_content_here"

        result, was_hit = self.cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id="agent-1",
            workspace_key="project-1",
        )

        assert result == "compressed_output"
        assert was_hit is False
        compress_fn.assert_called_once_with(content)

    def test_get_or_compress_cache_hit(self):
        """Test cache hit skips compress_fn."""
        compress_fn = MagicMock(return_value="compressed_output")
        content = "large_content_here"

        # First call: cache miss
        result1, hit1 = self.cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id="agent-1",
            workspace_key="project-1",
        )
        assert hit1 is False

        # Second call: cache hit
        result2, hit2 = self.cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id="agent-2",  # Different agent
            workspace_key="project-1",
        )

        assert result2 == "compressed_output"
        assert hit2 is True
        # compress_fn called only once (not on cache hit)
        compress_fn.assert_called_once()

    def test_register_and_get_compressed(self):
        """Test manually registering compression and retrieving it."""
        content_hash = "abcd1234efgh5678"
        self.cache.register_compression(
            content_hash=content_hash,
            compressed="compressed_data",
            agent_id="agent-1",
            workspace_key="project-1",
        )

        result = self.cache.get_compressed(content_hash, workspace_key="project-1")
        assert result == "compressed_data"

    def test_get_compressed_nonexistent(self):
        """Test retrieving nonexistent hash returns None."""
        result = self.cache.get_compressed("nonexistent", workspace_key="project-1")
        assert result is None

    def test_get_compressed_wrong_workspace(self):
        """Test workspace scoping: wrong workspace returns None."""
        content_hash = "abcd1234efgh5678"
        self.cache.register_compression(
            content_hash=content_hash,
            compressed="data",
            agent_id="agent-1",
            workspace_key="project-1",
        )

        # Attempt to retrieve with different workspace
        result = self.cache.get_compressed(content_hash, workspace_key="project-2")
        assert result is None

    def test_dedup_same_content_from_different_agents(self):
        """Test that same content from two agents hits cache on second call."""
        content = "identical_content"
        compress_fn = MagicMock(return_value="compressed")

        # Agent 1 compresses
        result1, hit1 = self.cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id="agent-1",
            workspace_key="project-1",
        )
        assert hit1 is False

        # Agent 2 compresses same content
        result2, hit2 = self.cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id="agent-2",
            workspace_key="project-1",
        )

        # Should be cache hit
        assert hit2 is True
        assert result2 == result1
        # compress_fn called only once total
        compress_fn.assert_called_once()

    def test_lru_eviction_when_max_entries_exceeded(self):
        """Test LRU eviction when max_entries is exceeded."""
        small_cache = SharedCompressionCache(max_entries=3, ttl_seconds=3600)
        compress_fn = lambda x: f"compressed_{x}"

        # Add 3 entries
        for i in range(3):
            content = f"content_{i}"
            small_cache.get_or_compress(
                content=content,
                compress_fn=compress_fn,
                agent_id=f"agent-{i}",
                workspace_key="project-1",
            )

        stats = small_cache.stats()
        assert stats["entries_count"] == 3

        # Add 4th entry, should evict oldest
        small_cache.get_or_compress(
            content="content_3",
            compress_fn=compress_fn,
            agent_id="agent-3",
            workspace_key="project-1",
        )

        stats = small_cache.stats()
        assert stats["entries_count"] == 3  # Still 3, oldest was evicted

    def test_ttl_expiry_returns_none(self):
        """Test that expired entries are not returned."""
        tiny_cache = SharedCompressionCache(max_entries=100, ttl_seconds=1)
        content = "content_to_expire"
        compress_fn = lambda x: "compressed"

        # Add entry
        tiny_cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id="agent-1",
            workspace_key="project-1",
        )

        # Retrieve immediately (should work)
        result1 = tiny_cache.get_compressed(
            SharedCompressionCache._hash_content(content),
            workspace_key="project-1",
        )
        assert result1 == "compressed"

        # Wait for TTL to expire
        time.sleep(1.1)

        # Should return None now
        result2 = tiny_cache.get_compressed(
            SharedCompressionCache._hash_content(content),
            workspace_key="project-1",
        )
        assert result2 is None

    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        compress_fn = lambda x: f"compressed_{x}"
        content = "test_content"

        # Miss then hit
        self.cache.get_or_compress(content, compress_fn, "agent-1", "project-1")
        self.cache.get_or_compress(content, compress_fn, "agent-2", "project-1")

        stats = self.cache.stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1
        assert stats["hit_rate_percent"] == 50.0


class TestMultiAgentCoordinator:
    """Tests for MultiAgentCoordinator."""

    def setup_method(self):
        """Reset singleton and create fresh coordinator for each test."""
        MultiAgentCoordinator.reset_instance()
        self.coordinator = MultiAgentCoordinator.get_instance()

    def teardown_method(self):
        """Clean up after each test."""
        if self.coordinator:
            self.coordinator.clear()

    def test_singleton_pattern(self):
        """Test that get_instance() returns the same object."""
        coordinator1 = MultiAgentCoordinator.get_instance()
        coordinator2 = MultiAgentCoordinator.get_instance()
        assert coordinator1 is coordinator2

    def test_compress_shared_two_agents_cache_hit(self):
        """Test compress_shared with two agents hitting cache on second call."""
        content = "shared_large_content"
        compress_fn = lambda x: f"compressed_{x}"

        # Agent 1 compresses
        result1 = self.coordinator.compress_shared(
            content=content,
            agent_id="agent-1",
            compress_fn=compress_fn,
            workspace_key="project-1",
        )
        assert result1.cache_hit is False

        # Agent 2 compresses same content
        result2 = self.coordinator.compress_shared(
            content=content,
            agent_id="agent-2",
            compress_fn=compress_fn,
            workspace_key="project-1",
        )
        assert result2.cache_hit is True
        assert result2.compressed_content == result1.compressed_content
        assert result2.content_hash == result1.content_hash

    def test_get_agent_context_returns_correct_stats(self):
        """Test get_agent_context returns per-agent compression stats."""
        compress_fn = lambda x: f"compressed_{x}"

        # Agent 1 compresses two items
        result1 = self.coordinator.compress_shared(
            content="content_a",
            agent_id="agent-1",
            compress_fn=compress_fn,
            workspace_key="project-1",
        )
        result2 = self.coordinator.compress_shared(
            content="content_b",
            agent_id="agent-1",
            compress_fn=compress_fn,
            workspace_key="project-1",
        )

        context = self.coordinator.get_agent_context("agent-1")
        assert context.agent_id == "agent-1"
        assert context.total_items_compressed == 2
        assert len(context.compressed_items) == 2

    def test_clear_resets_all_state(self):
        """Test clear() resets coordinator state."""
        compress_fn = lambda x: "compressed"

        # Register agents and add compressions
        self.coordinator.compress_shared("content", "agent-1", compress_fn, "project-1")
        self.coordinator.register_agent("agent-2")

        assert len(self.coordinator.get_active_agents()) > 0

        # Clear
        self.coordinator.clear()

        # State should be reset
        assert self.coordinator.get_active_agents() == []
        assert self.coordinator._agent_compressions == {}

    def test_workspace_scoping(self):
        """Test workspace_key creates separate cache entries."""
        compress_fn = lambda x: f"compressed_{x}"
        same_content = "identical_content"

        # Compress in workspace-1
        result1 = self.coordinator.compress_shared(
            content=same_content,
            agent_id="agent-1",
            compress_fn=compress_fn,
            workspace_key="workspace-1",
        )

        # Compress same content in workspace-2
        result2 = self.coordinator.compress_shared(
            content=same_content,
            agent_id="agent-2",
            compress_fn=compress_fn,
            workspace_key="workspace-2",
        )

        # Different workspaces = different cache entries = both cache misses
        assert result1.cache_hit is False
        assert result2.cache_hit is False
        # Same content but different workspace_key, so they're separate

    def test_register_unregister_agents(self):
        """Test agent registration and unregistration."""
        self.coordinator.register_agent("agent-1")
        assert "agent-1" in self.coordinator.get_active_agents()

        self.coordinator.unregister_agent("agent-1")
        assert "agent-1" not in self.coordinator.get_active_agents()

    def test_set_agent_task(self):
        """Test setting agent task."""
        self.coordinator.register_agent("agent-1")
        self.coordinator.set_agent_task("agent-1", "research")

        context = self.coordinator.get_agent_context("agent-1")
        assert context.current_task == "research"

    def test_stats_aggregation(self):
        """Test stats() returns aggregated stats."""
        compress_fn = lambda x: "compressed"

        self.coordinator.compress_shared("content-1", "agent-1", compress_fn, "project-1")
        self.coordinator.compress_shared("content-2", "agent-2", compress_fn, "project-1")

        stats = self.coordinator.stats()
        assert "cache" in stats
        assert "agents" in stats
        assert stats["agents"]["active_count"] >= 2

    def test_compress_shared_auto_registers_agent(self):
        """Test compress_shared auto-registers agent if not already registered."""
        compress_fn = lambda x: "compressed"

        self.coordinator.compress_shared("content", "new-agent", compress_fn, "project-1")

        assert "new-agent" in self.coordinator.get_active_agents()


class TestThreadSafety:
    """Tests for thread safety of SharedCompressionCache and MultiAgentCoordinator."""

    def setup_method(self):
        """Create fresh coordinator for each test."""
        MultiAgentCoordinator.reset_instance()
        self.coordinator = MultiAgentCoordinator.get_instance()

    def teardown_method(self):
        """Clean up."""
        self.coordinator.clear()

    def test_concurrent_compression_no_state_corruption(self):
        """Test two agents compressing concurrently don't corrupt state."""
        compress_fn = lambda x: f"compressed_{x}"
        results = []
        errors = []

        def agent_compress(agent_id, content):
            try:
                result = self.coordinator.compress_shared(
                    content=content,
                    agent_id=agent_id,
                    compress_fn=compress_fn,
                    workspace_key="project-1",
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Create threads for two agents compressing simultaneously
        thread1 = threading.Thread(target=agent_compress, args=("agent-1", "content-1"))
        thread2 = threading.Thread(target=agent_compress, args=("agent-2", "content-2"))

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # No errors
        assert len(errors) == 0
        # Both results recorded
        assert len(results) == 2

    def test_concurrent_cache_hit_race_condition(self):
        """Test concurrent agents hitting same cache entry doesn't race."""
        compress_fn = lambda x: "compressed"
        content = "shared_content"
        results = []
        errors = []

        def agent_compress(agent_id):
            try:
                result = self.coordinator.compress_shared(
                    content=content,
                    agent_id=agent_id,
                    compress_fn=compress_fn,
                    workspace_key="project-1",
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Multiple threads try to compress same content simultaneously
        threads = [
            threading.Thread(target=agent_compress, args=(f"agent-{i}",))
            for i in range(5)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # No errors
        assert len(errors) == 0
        # All got same result
        assert len(results) == 5
        all_hashes = {r.content_hash for r in results}
        assert len(all_hashes) == 1  # Same hash

    def test_concurrent_ttl_expiry_no_corruption(self):
        """Test concurrent TTL expiry checks don't corrupt state."""
        tiny_cache = SharedCompressionCache(max_entries=100, ttl_seconds=1)
        compress_fn = lambda x: "compressed"
        errors = []

        def add_and_retrieve(agent_id):
            try:
                content = f"content_{agent_id}"
                tiny_cache.get_or_compress(
                    content=content,
                    compress_fn=compress_fn,
                    agent_id=agent_id,
                    workspace_key="project-1",
                )
                content_hash = SharedCompressionCache._hash_content(content)
                result = tiny_cache.get_compressed(content_hash, workspace_key="project-1")
                return result
            except Exception as e:
                errors.append(e)
                return None

        # Add entries from multiple threads
        threads = [
            threading.Thread(target=add_and_retrieve, args=(f"agent-{i}",))
            for i in range(3)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0


class TestWorkspaceScoping:
    """Tests for workspace scoping isolation."""

    def setup_method(self):
        """Create fresh cache for each test."""
        self.cache = SharedCompressionCache(max_entries=100, ttl_seconds=3600)

    def test_same_content_different_workspaces_separate_entries(self):
        """Test same content in different workspaces creates separate cache entries."""
        content = "identical_content"
        compress_fn = lambda x: "compressed"

        # Compress in workspace-1
        hash1, hit1 = self.cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id="agent-1",
            workspace_key="workspace-1",
        )

        # Compress same content in workspace-2
        hash2, hit2 = self.cache.get_or_compress(
            content=content,
            compress_fn=compress_fn,
            agent_id="agent-2",
            workspace_key="workspace-2",
        )

        # Same content hash, but both are cache misses (different workspaces)
        assert hash1 == hash2  # Same content
        assert hit1 is False
        assert hit2 is False  # workspace-2 doesn't see workspace-1's cache

    def test_workspace_isolation_get_compressed(self):
        """Test get_compressed respects workspace boundaries."""
        content_hash = "test_hash_1234"
        self.cache.register_compression(
            content_hash=content_hash,
            compressed="data_from_ws1",
            agent_id="agent-1",
            workspace_key="workspace-1",
        )

        # Retrieve from same workspace
        result_same = self.cache.get_compressed(content_hash, workspace_key="workspace-1")
        assert result_same == "data_from_ws1"

        # Retrieve from different workspace
        result_different = self.cache.get_compressed(
            content_hash, workspace_key="workspace-2"
        )
        assert result_different is None  # Isolated

    def test_list_by_agent_respects_workspace(self):
        """Test list_by_agent filters by workspace."""
        # Register entries from agent-1 in two workspaces
        self.cache.register_compression(
            content_hash="hash_1",
            compressed="data_1",
            agent_id="agent-1",
            workspace_key="workspace-1",
        )
        self.cache.register_compression(
            content_hash="hash_2",
            compressed="data_2",
            agent_id="agent-1",
            workspace_key="workspace-2",
        )

        # List agent-1's entries in workspace-1
        entries = self.cache.list_by_agent("agent-1", workspace_key="workspace-1")
        assert len(entries) == 1
        assert entries[0].content_hash == "hash_1"


class TestEdgeCases:
    """Tests for edge cases and corner cases."""

    def setup_method(self):
        """Create fresh coordinator for each test."""
        MultiAgentCoordinator.reset_instance()
        self.coordinator = MultiAgentCoordinator.get_instance()

    def teardown_method(self):
        """Clean up."""
        self.coordinator.clear()

    def test_empty_content_compression(self):
        """Test compressing empty string."""
        compress_fn = lambda x: ""
        result = self.coordinator.compress_shared(
            content="",
            agent_id="agent-1",
            compress_fn=compress_fn,
            workspace_key="project-1",
        )
        assert result.compressed_content == ""
        assert result.cache_hit is False

    def test_very_large_content(self):
        """Test compressing very large content."""
        large_content = "x" * 100000  # 100KB of repeated character
        compress_fn = lambda x: x[:100]  # Reduce to 100 chars

        result1 = self.coordinator.compress_shared(
            content=large_content,
            agent_id="agent-1",
            compress_fn=compress_fn,
            workspace_key="project-1",
        )

        result2 = self.coordinator.compress_shared(
            content=large_content,
            agent_id="agent-2",
            compress_fn=compress_fn,
            workspace_key="project-1",
        )

        # Second agent should get cache hit
        assert result2.cache_hit is True

    def test_get_agent_context_nonexistent_agent(self):
        """Test getting context for agent that never compressed anything."""
        context = self.coordinator.get_agent_context("nonexistent-agent")
        assert context.agent_id == "nonexistent-agent"
        assert context.total_items_compressed == 0
        assert context.active is False

    def test_multiple_compressions_same_agent(self):
        """Test same agent compressing multiple different items."""
        compress_fn = lambda x: f"compressed_{x}"

        items = ["content_1", "content_2", "content_3"]
        for item in items:
            self.coordinator.compress_shared(
                content=item,
                agent_id="agent-1",
                compress_fn=compress_fn,
                workspace_key="project-1",
            )

        context = self.coordinator.get_agent_context("agent-1")
        assert context.total_items_compressed == 3

    def test_unicode_content_compression(self):
        """Test compression with unicode content."""
        unicode_content = "Hello 世界 🌍 Здравствуй мир"
        compress_fn = lambda x: x[:10]

        result = self.coordinator.compress_shared(
            content=unicode_content,
            agent_id="agent-1",
            compress_fn=compress_fn,
            workspace_key="project-1",
        )

        assert result.cache_hit is False
        assert len(result.compressed_content) > 0
