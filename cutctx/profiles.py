"""Cross-session compression profiles — learns from past sessions to improve future ones.

After each session, records what compression ratios were used and what content
was retrieved via CCR (a signal that content was over-compressed). Builds a
per-workspace profile that adjusts compression aggressiveness for future sessions.

The longer you use Cutctx in a codebase, the better it gets.

Usage:
    profile = CompressionProfile.load()  # loads for current workspace
    config = profile.get_compressor_config()  # adjusted UniversalCompressorConfig
    # ... run session ...
    profile.record_session(session_stats)  # update profile
    profile.save()
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

DEFAULT_COMPRESSION_RATIO = 0.5  # Default target: compress to 50% of original
_MAX_RECOMMENDED_RATIO = 0.95  # Security cap: ensure compression never fully disables


@dataclass
class ContentTypeStats:
    """Learned compression statistics for a specific content type.

    Tracks compression effectiveness and retrieval patterns to inform
    future compression decisions.
    """

    content_type: str
    sessions_seen: int = 0
    total_compressions: int = 0
    total_retrievals: int = 0
    avg_compression_ratio: float = 0.0
    recommended_ratio: float = DEFAULT_COMPRESSION_RATIO

    # Timestamp tracking
    last_session_timestamp: float = 0.0

    @property
    def retrieval_rate(self) -> float:
        """Fraction of compressions that triggered CCR retrieval."""
        if self.total_compressions == 0:
            return 0.0
        return self.total_retrievals / self.total_compressions

    def update_from_session(
        self,
        original_count: int,
        compressed_count: int,
        was_retrieved: bool = False,
    ) -> None:
        """Update stats from a single compression event.

        Args:
            original_count: Number of items before compression.
            compressed_count: Number of items after compression.
            was_retrieved: Whether this content was retrieved via CCR.
        """
        if original_count == 0:
            return

        current_ratio = compressed_count / original_count
        self.total_compressions += 1
        self.last_session_timestamp = time.time()

        # Update running average of compression ratio
        old_avg = self.avg_compression_ratio
        self.avg_compression_ratio = (
            old_avg * (self.total_compressions - 1) + current_ratio
        ) / self.total_compressions

        # Track retrieval
        if was_retrieved:
            self.total_retrievals += 1

        # Update recommended ratio based on retrieval rate
        self._update_recommendation()

    def _update_recommendation(self) -> None:
        """Adjust recommended compression ratio based on retrieval patterns."""
        if self.total_compressions < 3:
            # Not enough data, keep default
            self.recommended_ratio = DEFAULT_COMPRESSION_RATIO
            return

        retrieval_rate = self.retrieval_rate

        # Heuristic: if retrieval rate is high, we're over-compressing
        # Increase the ratio (compress less aggressively)
        if retrieval_rate > 0.5:
            # Over 50% retrieval rate: compress much less
            self.recommended_ratio = min(_MAX_RECOMMENDED_RATIO, self.avg_compression_ratio + 0.2)
        elif retrieval_rate > 0.2:
            # 20-50% retrieval rate: compress slightly less
            self.recommended_ratio = min(_MAX_RECOMMENDED_RATIO, self.avg_compression_ratio + 0.1)
        else:
            # Under 20% retrieval rate: current compression is good
            self.recommended_ratio = self.avg_compression_ratio

        # Clamp to [0.0, _MAX_RECOMMENDED_RATIO]
        self.recommended_ratio = max(0.0, min(_MAX_RECOMMENDED_RATIO, self.recommended_ratio))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "content_type": self.content_type,
            "sessions_seen": self.sessions_seen,
            "total_compressions": self.total_compressions,
            "total_retrievals": self.total_retrievals,
            "avg_compression_ratio": self.avg_compression_ratio,
            "retrieval_rate": self.retrieval_rate,
            "recommended_ratio": self.recommended_ratio,
            "last_session_timestamp": self.last_session_timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentTypeStats:
        """Create from dictionary (for JSON deserialization)."""
        return cls(
            content_type=data["content_type"],
            sessions_seen=data.get("sessions_seen", 0),
            total_compressions=data.get("total_compressions", 0),
            total_retrievals=data.get("total_retrievals", 0),
            avg_compression_ratio=data.get("avg_compression_ratio", 0.0),
            recommended_ratio=data.get("recommended_ratio", DEFAULT_COMPRESSION_RATIO),
            last_session_timestamp=data.get("last_session_timestamp", 0.0),
        )


class CompressionProfile:
    """Manages per-workspace compression profiles.

    Stores learned compression patterns and applies them to future sessions.
    Profiles are workspace-specific (identified by git remote + repo path).
    """

    def __init__(self, workspace_hash: str, stats: dict[str, ContentTypeStats] | None = None):
        """Initialize a compression profile.

        Args:
            workspace_hash: SHA-256 hash of workspace identity.
            stats: Existing stats dict (for loading). If None, starts empty.
        """
        self.workspace_hash = workspace_hash
        self.stats: dict[str, ContentTypeStats] = stats or {}
        self._lock = threading.Lock()
        self._dirty = False
        self._session_count = sum(s.sessions_seen for s in self.stats.values()) if self.stats else 0

    @classmethod
    def load(cls, workspace_dir: Path | None = None) -> CompressionProfile:
        """Load profile for current workspace.

        Args:
            workspace_dir: Override workspace directory. Defaults to cwd.

        Returns:
            Profile (empty if first session).
        """
        if workspace_dir is None:
            workspace_dir = Path.cwd()
        else:
            workspace_dir = Path(workspace_dir).resolve()

        # Compute workspace hash
        workspace_hash = _compute_workspace_hash(workspace_dir)

        # Look for profile file
        profile_path = _get_profile_path(workspace_hash)

        if profile_path.exists():
            try:
                with open(profile_path) as f:
                    data = json.load(f)
                    stats = {
                        name: ContentTypeStats.from_dict(s)
                        for name, s in data.get("stats", {}).items()
                    }
                    logger.info(f"Loaded profile for workspace {workspace_hash}: {len(stats)} types")
                    return CompressionProfile(workspace_hash, stats)
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_path}: {e}")

        # No existing profile, create new
        logger.info(f"Creating new profile for workspace {workspace_hash}")
        return CompressionProfile(workspace_hash)

    def save(self) -> None:
        """Save profile to disk."""
        profile_path = _get_profile_path(self.workspace_hash)

        # Ensure directory exists
        profile_path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            data = {
                "workspace_hash": self.workspace_hash,
                "saved_at": time.time(),
                "stats": {
                    name: stat.to_dict()
                    for name, stat in self.stats.items()
                },
            }

            try:
                with open(profile_path, "w") as f:
                    json.dump(data, f, indent=2)
                logger.info(f"Saved profile to {profile_path}")
                self._dirty = False
            except Exception as e:
                logger.error(f"Failed to save profile {profile_path}: {e}")

    def record_session(
        self,
        session_id: str,
        stats: list[dict[str, Any]],
    ) -> None:
        """Update profile from session statistics.

        Args:
            session_id: Unique session identifier.
            stats: List of dicts with keys:
                - content_type: str
                - original_count: int
                - compressed_count: int
                - was_retrieved: bool (optional)
        """
        with self._lock:
            for stat in stats:
                content_type = stat.get("content_type")
                if not content_type:
                    continue

                original_count = stat.get("original_count", 0)
                compressed_count = stat.get("compressed_count", 0)
                was_retrieved = stat.get("was_retrieved", False)

                if content_type not in self.stats:
                    self.stats[content_type] = ContentTypeStats(content_type=content_type)

                self.stats[content_type].update_from_session(
                    original_count,
                    compressed_count,
                    was_retrieved,
                )

            # Mark session seen only for content types actually encountered this session
            seen_types = {s.get("content_type") for s in stats if s.get("content_type")}
            for content_type in seen_types:
                if content_type in self.stats:
                    self.stats[content_type].sessions_seen += 1

            self._dirty = True
            logger.info(
                f"Recorded session {session_id} with {len(stats)} content types"
            )

    def update_from_ccr_retrieval(self, content_type: str) -> None:
        """Signal that content was retrieved via CCR (was over-compressed).

        Args:
            content_type: The content type that triggered retrieval.
        """
        with self._lock:
            if content_type not in self.stats:
                self.stats[content_type] = ContentTypeStats(content_type=content_type)

            # Increment retrieval count to indicate over-compression
            self.stats[content_type].total_retrievals += 1
            self.stats[content_type]._update_recommendation()
            self._dirty = True

    def get_compression_target(self, content_type: str) -> float:
        """Get recommended compression ratio for content type.

        Args:
            content_type: The content type to get target for.

        Returns:
            Compression ratio in [0.0, 1.0] where 0 = fully compressed.
        """
        with self._lock:
            if content_type in self.stats:
                return self.stats[content_type].recommended_ratio
            return DEFAULT_COMPRESSION_RATIO

    def summary(self) -> dict[str, Any]:
        """Get human-readable profile summary.

        Returns:
            Dict with profile statistics.
        """
        with self._lock:
            return {
                "workspace_hash": self.workspace_hash,
                "total_content_types": len(self.stats),
                "total_compressions": sum(s.total_compressions for s in self.stats.values()),
                "total_retrievals": sum(s.total_retrievals for s in self.stats.values()),
                "overall_retrieval_rate": (
                    sum(s.total_retrievals for s in self.stats.values())
                    / max(1, sum(s.total_compressions for s in self.stats.values()))
                ),
                "stats_by_type": {
                    name: {
                        "sessions_seen": stat.sessions_seen,
                        "total_compressions": stat.total_compressions,
                        "retrieval_rate": stat.retrieval_rate,
                        "avg_compression_ratio": stat.avg_compression_ratio,
                        "recommended_ratio": stat.recommended_ratio,
                    }
                    for name, stat in sorted(self.stats.items())
                },
            }


def _compute_workspace_hash(workspace_dir: Path) -> str:
    """Compute workspace identity hash.

    Args:
        workspace_dir: Root directory of workspace.

    Returns:
        SHA-256 hash of workspace identity, truncated to 16 hex chars.
    """
    workspace_dir = workspace_dir.resolve()

    # Try to get git remote
    git_remote = None
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            git_remote = result.stdout.strip()
    except Exception:
        pass

    # Combine git remote + repo path for identity
    if git_remote:
        identity = f"{git_remote}:{workspace_dir}"
    else:
        identity = str(workspace_dir)

    # Compute hash
    hash_obj = hashlib.sha256(identity.encode())
    return hash_obj.hexdigest()[:16]


def _get_profile_path(workspace_hash: str) -> Path:
    """Get path to profile file.

    Args:
        workspace_hash: Workspace hash (16 hex chars).

    Returns:
        Path to profile JSON file.
    """
    profiles_dir = Path.home() / ".cutctx" / "profiles"
    return profiles_dir / f"{workspace_hash}.json"


# Global ProfileManager for caching
_profile_cache: dict[str, CompressionProfile] = {}
_profile_cache_lock = threading.Lock()


class ProfileManager:
    """Manages compression profile lifecycle.

    Singleton-like interface with caching for efficiency.
    """

    @classmethod
    def get_profile(cls, workspace_dir: Path | None = None) -> CompressionProfile:
        """Get or load profile, with caching.

        Args:
            workspace_dir: Override workspace directory. Defaults to cwd.

        Returns:
            CompressionProfile instance.
        """
        if workspace_dir is None:
            workspace_dir = Path.cwd()
        else:
            workspace_dir = Path(workspace_dir).resolve()

        workspace_hash = _compute_workspace_hash(workspace_dir)

        with _profile_cache_lock:
            if workspace_hash not in _profile_cache:
                # Load from disk
                profile = CompressionProfile.load(workspace_dir)
                _profile_cache[workspace_hash] = profile
            return _profile_cache[workspace_hash]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached profiles.

        Mainly for testing.
        """
        global _profile_cache
        with _profile_cache_lock:
            _profile_cache.clear()
