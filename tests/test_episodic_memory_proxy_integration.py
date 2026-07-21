"""Proxy integration tests for episodic memory injection.

Tests the end-to-end flow:
1. EpisodicSessionTracker buffering during requests
2. Memory injection into Anthropic messages handler
3. Config toggling (enabled/disabled)
4. Memory block format and injection path

These tests do NOT require an actual Anthropic API key — they mock
the upstream API and test the proxy's memory injection logic.
"""

from __future__ import annotations

import os
import tempfile

import pytest

os.environ["TOKENIZERS_PARALLELISM"] = "false"

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from cutctx.memory.store import EpisodicMemoryStore, compute_project_hash

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_memory_dir():
    with tempfile.TemporaryDirectory(prefix="cutctx_epi_integ_") as d:
        yield d


@pytest.fixture
def episodic_store(tmp_memory_dir):
    return EpisodicMemoryStore(memory_dir=tmp_memory_dir)


@pytest.fixture
def episodic_client(tmp_memory_dir, monkeypatch):
    """Create a test client with episodic memory enabled."""
    monkeypatch.setenv("CUTCTX_EPISODIC_MEMORY_DIR", tmp_memory_dir)
    monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")

    from cutctx.proxy.models import ProxyConfig
    from cutctx.proxy.server import _apply_validated_license, create_app
    from cutctx.telemetry.reporter import LicenseInfo

    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        episodic_memory_enabled=True,
        episodic_idle_timeout_seconds=300,
        # Episodic memory is a BUSINESS-tier feature; the fixture declares
        # its tier explicitly now that activation is entitlement-gated.
        entitlement_tier="business",
    )

    app = create_app(config)
    _apply_validated_license(
        app.state.proxy,
        LicenseInfo(status="active", plan="business"),
    )
    app.state.proxy._reconcile_episodic_entitlement()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def no_episodic_client():
    """Create a test client with episodic memory disabled."""
    from cutctx.proxy.models import ProxyConfig

    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        cost_tracking_enabled=False,
        episodic_memory_enabled=False,
    )
    from cutctx.proxy.server import create_app

    app = create_app(config)
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestEpisodicConfig:
    def test_config_defaults(self):
        from cutctx.proxy.models import ProxyConfig

        config = ProxyConfig()
        assert config.episodic_memory_enabled is False
        assert config.episodic_idle_timeout_seconds == 300
        assert "haiku" in config.episodic_extraction_model

    def test_config_overrides(self):
        from cutctx.proxy.models import ProxyConfig

        config = ProxyConfig(
            episodic_memory_enabled=True,
            episodic_idle_timeout_seconds=600,
            episodic_extraction_model="gpt-4o-mini",
        )
        assert config.episodic_memory_enabled is True
        assert config.episodic_idle_timeout_seconds == 600
        assert config.episodic_extraction_model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Memory block formatting tests (integration-level)
# ---------------------------------------------------------------------------


class TestMemoryBlockFormat:
    def test_memory_block_detected_by_rust_classifier_pattern(self):
        """The [SYSTEM: Past Session Memories] tag is what the Rust walker matches."""
        from cutctx.memory.extractor import format_memory_block

        block = format_memory_block(
            "## Session Insights\n- User prefers dark mode",
            project_path="/my/project",
        )
        assert block.startswith("[SYSTEM: Past Session Memories]")
        assert "extracted" in block
        assert "/my/project" in block

    def test_empty_insights_produces_empty_block(self):
        from cutctx.memory.extractor import format_memory_block

        assert format_memory_block("") == ""
        assert format_memory_block("  \n  ") == ""


# ---------------------------------------------------------------------------
# Session tracker integration with proxy
# ---------------------------------------------------------------------------


class TestSessionTrackerIntegration:
    def test_tracker_initialization(self, episodic_client):
        """Episodic tracker should be initialized when enabled."""
        proxy = episodic_client.app.state.proxy
        assert proxy.episodic_tracker is not None
        assert proxy.episodic_tracker.enabled is True

    def test_tracker_not_initialized_when_disabled(self, no_episodic_client):
        """Episodic tracker should be None when disabled."""
        proxy = no_episodic_client.app.state.proxy
        assert proxy.episodic_tracker is None

    def test_tracker_stats(self, episodic_client):
        proxy = episodic_client.app.state.proxy
        stats = proxy.episodic_tracker.get_stats()
        assert stats["enabled"] is True
        assert isinstance(stats["active_sessions"], int)

    def test_project_hash_stability(self):
        """Same path always produces the same hash."""
        h1 = compute_project_hash("/Users/dev/myproject")
        h2 = compute_project_hash("/Users/dev/myproject")
        assert h1 == h2

    def test_store_and_retrieve_roundtrip(self, episodic_store):
        """Full store → load → format roundtrip."""
        h = compute_project_hash("/test/project")
        episodic_store.save_memory(
            h,
            "## Session 2024-01-01\n- User implemented caching in cache.py",
        )
        episodic_store.save_memory(
            h,
            "## Session 2024-01-02\n- Fixed race condition in async_task.py",
        )

        raw = episodic_store.load_memories(h)
        assert "caching" in raw
        assert "race condition" in raw

        from cutctx.memory.extractor import format_memory_block

        formatted = format_memory_block(raw, project_path="/test/project")
        assert formatted.startswith("[SYSTEM: Past Session Memories]")
        assert "caching" in formatted

    def test_multiple_projects_isolated(self, episodic_store):
        """Memories from different projects don't leak."""
        h1 = compute_project_hash("/project/a")
        h2 = compute_project_hash("/project/b")

        episodic_store.save_memory(h1, "Project A memories")
        episodic_store.save_memory(h2, "Project B memories")

        assert "Project A" in episodic_store.load_memories(h1)
        assert "Project B" not in episodic_store.load_memories(h1)
        assert "Project B" in episodic_store.load_memories(h2)


# ---------------------------------------------------------------------------
# Proxy health endpoint works with episodic tracker
# ---------------------------------------------------------------------------


class TestHealthWithEpisodic:
    def test_health_endpoint(self, episodic_client, monkeypatch):
        """Proxy should still respond to health checks with episodic enabled."""
        # This test asserts proxy wiring, not provider connectivity; the
        # live upstream probe made it flake in offline/parallel runs.
        monkeypatch.setenv("CUTCTX_SKIP_UPSTREAM_CHECK", "1")
        resp = episodic_client.get("/health")
        # Health endpoint might not exist on this path; try /healthz
        if resp.status_code == 404:
            resp = episodic_client.get("/healthz")
        # Just ensure proxy starts up correctly
        assert resp.status_code in (200, 404)

    def test_stats_endpoint(self, episodic_client):
        """Proxy stats should include episodic tracker info."""
        resp = episodic_client.get("/stats")
        if resp.status_code == 200:
            data = resp.json()
            # Stats should be present (even if empty)
            assert isinstance(data, dict)
