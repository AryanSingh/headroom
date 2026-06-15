"""Tests for compression profiles module."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

from headroom.profiles import (
    CompressionProfile,
    ContentTypeStats,
    ProfileManager,
    _compute_workspace_hash,
    _get_profile_path,
)


class TestContentTypeStats:
    """Tests for ContentTypeStats dataclass."""

    def test_init(self):
        """Test basic initialization."""
        stats = ContentTypeStats(content_type="json_api")
        assert stats.content_type == "json_api"
        assert stats.sessions_seen == 0
        assert stats.total_compressions == 0
        assert stats.retrieval_rate == 0.0

    def test_retrieval_rate_calculation(self):
        """Test retrieval rate property."""
        stats = ContentTypeStats(content_type="test")
        stats.total_compressions = 10
        stats.total_retrievals = 3
        assert stats.retrieval_rate == 0.3

    def test_retrieval_rate_with_zero_compressions(self):
        """Test retrieval rate when no compressions recorded."""
        stats = ContentTypeStats(content_type="test")
        assert stats.retrieval_rate == 0.0

    def test_update_from_session(self):
        """Test updating stats from a compression event."""
        stats = ContentTypeStats(content_type="json")
        stats.update_from_session(original_count=100, compressed_count=30)

        assert stats.total_compressions == 1
        assert stats.avg_compression_ratio == 0.3

    def test_update_with_retrieval(self):
        """Test updating stats when content is retrieved."""
        stats = ContentTypeStats(content_type="json")
        stats.update_from_session(original_count=100, compressed_count=30, was_retrieved=True)

        assert stats.total_compressions == 1
        assert stats.total_retrievals == 1
        assert stats.retrieval_rate == 1.0

    def test_recommendation_with_high_retrieval_rate(self):
        """Test recommendation adjustment when retrieval rate is high."""
        stats = ContentTypeStats(content_type="test", avg_compression_ratio=0.2)
        stats.total_compressions = 10
        stats.total_retrievals = 6  # 60% retrieval rate

        stats._update_recommendation()

        # When retrieval rate > 50%, should compress less (higher ratio)
        assert stats.recommended_ratio > stats.avg_compression_ratio
        assert stats.recommended_ratio <= 0.4

    def test_recommendation_with_low_retrieval_rate(self):
        """Test recommendation when retrieval rate is low."""
        stats = ContentTypeStats(content_type="test", avg_compression_ratio=0.3)
        stats.total_compressions = 10
        stats.total_retrievals = 1  # 10% retrieval rate

        stats._update_recommendation()

        # When retrieval rate < 20%, compression is good
        assert stats.recommended_ratio == stats.avg_compression_ratio

    def test_to_dict(self):
        """Test serialization to dict."""
        stats = ContentTypeStats(
            content_type="json",
            sessions_seen=5,
            total_compressions=20,
            total_retrievals=3,
            avg_compression_ratio=0.25,
        )

        d = stats.to_dict()
        assert d["content_type"] == "json"
        assert d["sessions_seen"] == 5
        assert d["total_compressions"] == 20
        assert d["total_retrievals"] == 3
        assert d["retrieval_rate"] == 0.15

    def test_from_dict(self):
        """Test deserialization from dict."""
        d = {
            "content_type": "json",
            "sessions_seen": 5,
            "total_compressions": 20,
            "total_retrievals": 3,
            "avg_compression_ratio": 0.25,
            "recommended_ratio": 0.3,
            "last_session_timestamp": 0.0,
        }

        stats = ContentTypeStats.from_dict(d)
        assert stats.content_type == "json"
        assert stats.sessions_seen == 5
        assert stats.total_compressions == 20


class TestCompressionProfile:
    """Tests for CompressionProfile class."""

    def test_init_empty(self):
        """Test initialization of empty profile."""
        profile = CompressionProfile(workspace_hash="test123")
        assert profile.workspace_hash == "test123"
        assert len(profile.stats) == 0

    def test_init_with_stats(self):
        """Test initialization with existing stats."""
        stats = {
            "json": ContentTypeStats(
                content_type="json",
                sessions_seen=5,
                total_compressions=20,
                avg_compression_ratio=0.3,
            )
        }
        profile = CompressionProfile(workspace_hash="test123", stats=stats)
        assert len(profile.stats) == 1
        assert profile.stats["json"].content_type == "json"

    def test_record_session_new_type(self):
        """Test recording a session with a new content type."""
        profile = CompressionProfile(workspace_hash="test123")

        stats = [
            {
                "content_type": "json",
                "original_count": 100,
                "compressed_count": 30,
            }
        ]
        profile.record_session("session1", stats)

        assert "json" in profile.stats
        assert profile.stats["json"].total_compressions == 1

    def test_record_session_existing_type(self):
        """Test recording multiple sessions for same type."""
        profile = CompressionProfile(workspace_hash="test123")

        for i in range(3):
            stats = [
                {
                    "content_type": "json",
                    "original_count": 100,
                    "compressed_count": 30 + i,  # Vary compression ratio slightly
                }
            ]
            profile.record_session(f"session{i}", stats)

        assert profile.stats["json"].total_compressions == 3
        assert profile.stats["json"].sessions_seen == 3
        # Average ratio should be around 0.31
        assert 0.30 <= profile.stats["json"].avg_compression_ratio <= 0.32

    def test_record_session_with_retrieval(self):
        """Test recording when content is retrieved."""
        profile = CompressionProfile(workspace_hash="test123")

        stats = [
            {
                "content_type": "json",
                "original_count": 100,
                "compressed_count": 30,
                "was_retrieved": True,
            }
        ]
        profile.record_session("session1", stats)

        assert profile.stats["json"].total_retrievals == 1

    def test_get_compression_target_known_type(self):
        """Test getting compression target for known content type."""
        profile = CompressionProfile(workspace_hash="test123")

        # Manually set up stats
        stats = ContentTypeStats(
            content_type="json",
            total_compressions=10,
            avg_compression_ratio=0.3,
            recommended_ratio=0.35,
        )
        profile.stats["json"] = stats

        target = profile.get_compression_target("json")
        assert target == 0.35

    def test_get_compression_target_unknown_type(self):
        """Test getting compression target for unknown type returns default."""
        profile = CompressionProfile(workspace_hash="test123")

        target = profile.get_compression_target("unknown_type")
        assert target == 0.5  # DEFAULT_COMPRESSION_RATIO

    def test_update_from_ccr_retrieval(self):
        """Test updating profile when CCR retrieval occurs."""
        profile = CompressionProfile(workspace_hash="test123")

        # Simulate existing stats
        profile.stats["json"] = ContentTypeStats(
            content_type="json",
            total_compressions=10,
            total_retrievals=1,
        )

        # Update from retrieval
        profile.update_from_ccr_retrieval("json")

        assert profile.stats["json"].total_retrievals == 2

    def test_update_from_ccr_retrieval_new_type(self):
        """Test CCR retrieval for type that hasn't been compressed yet."""
        profile = CompressionProfile(workspace_hash="test123")

        profile.update_from_ccr_retrieval("json")

        assert "json" in profile.stats
        assert profile.stats["json"].total_retrievals == 1

    def test_summary(self):
        """Test getting profile summary."""
        profile = CompressionProfile(workspace_hash="test123")

        # Add some stats
        profile.stats["json"] = ContentTypeStats(
            content_type="json",
            sessions_seen=5,
            total_compressions=20,
            total_retrievals=3,
            avg_compression_ratio=0.3,
        )

        summary = profile.summary()

        assert summary["workspace_hash"] == "test123"
        assert summary["total_content_types"] == 1
        assert summary["total_compressions"] == 20
        assert summary["total_retrievals"] == 3
        assert "json" in summary["stats_by_type"]

    def test_save_and_load(self):
        """Test saving and loading profile from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create profile with mock path
            profile = CompressionProfile(workspace_hash="test123abc")

            # Add some stats
            profile.stats["json"] = ContentTypeStats(
                content_type="json",
                sessions_seen=5,
                total_compressions=20,
                total_retrievals=3,
                avg_compression_ratio=0.3,
            )

            # Mock the profile path to use temp directory
            expected_path = Path(tmpdir) / "test123abc.json"

            with mock.patch("headroom.profiles._get_profile_path", return_value=expected_path):
                profile.save()
                assert expected_path.exists()

                # Load and verify
                loaded = CompressionProfile.load()
                assert loaded.workspace_hash == "test123abc"
                assert "json" in loaded.stats
                assert loaded.stats["json"].total_compressions == 20

    def test_thread_safety(self):
        """Test that profile updates are thread-safe."""
        profile = CompressionProfile(workspace_hash="test123")

        import threading

        def update_profile():
            for i in range(10):
                stats = [
                    {
                        "content_type": "json",
                        "original_count": 100,
                        "compressed_count": 30,
                    }
                ]
                profile.record_session(f"session{i}", stats)

        threads = [threading.Thread(target=update_profile) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After 5 threads * 10 updates each = 50 compressions
        assert profile.stats["json"].total_compressions == 50


class TestWorkspaceHash:
    """Tests for workspace hash computation."""

    def test_workspace_hash_consistent(self):
        """Test that workspace hash is consistent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)

            hash1 = _compute_workspace_hash(workspace_dir)
            hash2 = _compute_workspace_hash(workspace_dir)

            assert hash1 == hash2
            assert len(hash1) == 16  # Truncated to 16 hex chars

    def test_workspace_hash_different_paths(self):
        """Test that different paths produce different hashes."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                hash1 = _compute_workspace_hash(Path(tmpdir1))
                hash2 = _compute_workspace_hash(Path(tmpdir2))

                assert hash1 != hash2

    def test_workspace_hash_with_git(self):
        """Test workspace hash includes git remote if available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)

            # Mock git remote
            with mock.patch(
                "headroom.profiles.subprocess.run"
            ) as mock_run:
                mock_run.return_value = mock.Mock(
                    returncode=0,
                    stdout="https://github.com/example/repo.git\n",
                )

                hash_with_git = _compute_workspace_hash(workspace_dir)
                assert len(hash_with_git) == 16

                # Different remote should produce different hash
                mock_run.return_value.stdout = "https://github.com/other/repo.git\n"
                hash_with_other = _compute_workspace_hash(workspace_dir)
                assert hash_with_git != hash_with_other

    def test_get_profile_path(self):
        """Test profile path generation."""
        path = _get_profile_path("abc123def456")
        assert str(path).endswith("abc123def456.json")
        assert ".headroom/profiles" in str(path)


class TestProfileManager:
    """Tests for ProfileManager singleton."""

    def test_get_profile_creates_new(self):
        """Test that ProfileManager creates new profile on first call."""
        ProfileManager.clear_cache()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)

            profile = ProfileManager.get_profile(workspace_dir)

            assert isinstance(profile, CompressionProfile)
            assert len(profile.stats) == 0

    def test_get_profile_caches(self):
        """Test that ProfileManager caches profiles."""
        ProfileManager.clear_cache()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)

            profile1 = ProfileManager.get_profile(workspace_dir)
            profile2 = ProfileManager.get_profile(workspace_dir)

            # Same object in cache
            assert profile1 is profile2

    def test_clear_cache(self):
        """Test clearing profile cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)

            profile1 = ProfileManager.get_profile(workspace_dir)
            ProfileManager.clear_cache()
            profile2 = ProfileManager.get_profile(workspace_dir)

            # Different objects after cache clear
            assert profile1 is not profile2


class TestIntegration:
    """Integration tests for full profile lifecycle."""

    def test_full_lifecycle(self):
        """Test complete profile lifecycle: create, record, save, load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_dir = Path(tmpdir)

            # Create new profile
            profile = CompressionProfile.load(workspace_dir)
            assert len(profile.stats) == 0

            # Record some sessions
            for session_id in ["session1", "session2", "session3"]:
                stats = [
                    {
                        "content_type": "python",
                        "original_count": 50,
                        "compressed_count": 40,
                        "was_retrieved": False,
                    },
                    {
                        "content_type": "json",
                        "original_count": 100,
                        "compressed_count": 20,
                        "was_retrieved": True,
                    },
                ]
                profile.record_session(session_id, stats)

            # Verify stats
            assert profile.stats["python"].total_compressions == 3
            assert profile.stats["json"].total_retrievals == 3

            # Save to disk
            profile_path = _get_profile_path(profile.workspace_hash)
            with mock.patch("headroom.profiles._get_profile_path", return_value=profile_path):
                profile.save()

                # Load from disk
                loaded = CompressionProfile.load(workspace_dir)
                assert loaded.workspace_hash == profile.workspace_hash
                assert loaded.stats["python"].total_compressions == 3
                assert loaded.stats["json"].total_retrievals == 3

    def test_multiworkspace_profiles(self):
        """Test that different workspaces maintain separate profiles."""
        ProfileManager.clear_cache()

        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                workspace1 = Path(tmpdir1)
                workspace2 = Path(tmpdir2)

                profile1 = ProfileManager.get_profile(workspace1)
                profile2 = ProfileManager.get_profile(workspace2)

                # Different workspaces should have different hashes
                assert profile1.workspace_hash != profile2.workspace_hash

                # Update profile1
                profile1.stats["json"] = ContentTypeStats(
                    content_type="json",
                    total_compressions=10,
                )

                # Profile2 should not be affected
                assert "json" not in profile2.stats
