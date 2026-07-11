"""Prefix Cache Tracker — session-scoped state for cache-aware compression.

Tracks provider prefix cache state between turns so the transform pipeline
can freeze already-cached messages and only compress new content.

Problem: Clients like Claude Code already manage prefix caching (up to 4
cache_control breakpoints, growing-prefix strategy). If Cutctx compresses
or modifies messages in the cached prefix, it invalidates the cache —
replacing a 90% read discount (Anthropic) or 50% (OpenAI) with a 25%
write penalty.

Solution: After each API response, record how many tokens the provider
cached. On the next turn, freeze that many messages so the transform
pipeline skips them entirely.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cutctx.proxy.helpers import is_stateless

logger = logging.getLogger(__name__)

# Provider cache economics for cost comparisons
_PROVIDER_READ_DISCOUNT = {
    "anthropic": 0.9,  # 90% discount on reads
    "openai": 0.5,  # 50% discount on reads
    "gemini": 0.9,
    "bedrock": 0.9,
}

_PROVIDER_WRITE_PENALTY = {
    "anthropic": 0.25,  # 25% surcharge on writes
    "openai": 0.0,  # No write penalty
    "gemini": 0.0,
    "bedrock": 0.25,
}


@dataclass
class PrefixFreezeConfig:
    """Configuration for cache-aware prefix freezing."""

    enabled: bool = True
    min_cached_tokens: int = 1024  # Min cached tokens to activate freeze
    session_ttl_seconds: int = 600  # Session tracker cleanup TTL
    force_compress_threshold: float = 0.5  # Bust cache if compression saves > this fraction


@dataclass
class FreezeStats:
    """Statistics from prefix freezing for metrics/dashboard."""

    busts_avoided: int = 0
    tokens_preserved: int = 0
    compression_foregone_tokens: int = 0
    net_benefit_tokens: int = 0  # tokens_preserved - compression_foregone
    frozen_message_count: int = 0
    turn_number: int = 0
    consecutive_write_only_turns: int = 0
    remediation_active: bool = False


class PrefixCacheTracker:
    """Tracks provider prefix cache state across turns in a session.

    Usage:
        tracker = PrefixCacheTracker("anthropic")

        # Before compression (turn 2+):
        frozen = tracker.get_frozen_message_count()
        result = pipeline.apply(messages, model, frozen_message_count=frozen)

        # After API response:
        tracker.update_from_response(
            cache_read_tokens=usage["cache_read_input_tokens"],
            cache_write_tokens=usage["cache_creation_input_tokens"],
            messages=optimized_messages,
            tokenizer=tokenizer,
        )
    """

    def __init__(
        self,
        provider: str,
        config: PrefixFreezeConfig | None = None,
        *,
        on_change: Any | None = None,
    ):
        self.provider = provider
        self.config = config or PrefixFreezeConfig()
        self._cached_token_count: int = 0
        self._cached_message_count: int = 0
        self._turn_number: int = 0
        self._last_activity: float = time.time()
        self._last_original_messages: list[dict[str, Any]] = []
        self._last_forwarded_messages: list[dict[str, Any]] = []

        # Stats
        self._busts_avoided: int = 0
        self._tokens_preserved: int = 0
        self._compression_foregone_tokens: int = 0
        self._consecutive_write_only_turns: int = 0
        self._on_change = on_change

    def _notify_change(self) -> None:
        if self._on_change is None:
            return
        try:
            self._on_change(self)
        except Exception:
            logger.debug("PrefixCacheTracker persistence callback failed", exc_info=True)

    def snapshot_state(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the tracker state."""
        return {
            "provider": self.provider,
            "cached_token_count": self._cached_token_count,
            "cached_message_count": self._cached_message_count,
            "turn_number": self._turn_number,
            "last_activity": self._last_activity,
            "last_original_messages": copy.deepcopy(self._last_original_messages),
            "last_forwarded_messages": copy.deepcopy(self._last_forwarded_messages),
            "busts_avoided": self._busts_avoided,
            "tokens_preserved": self._tokens_preserved,
            "compression_foregone_tokens": self._compression_foregone_tokens,
            "consecutive_write_only_turns": self._consecutive_write_only_turns,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore tracker state from a previously persisted snapshot."""
        self.provider = str(state.get("provider", self.provider))
        self._cached_token_count = int(state.get("cached_token_count", 0) or 0)
        self._cached_message_count = int(state.get("cached_message_count", 0) or 0)
        self._turn_number = int(state.get("turn_number", 0) or 0)
        self._last_activity = float(state.get("last_activity", time.time()) or time.time())
        self._last_original_messages = list(state.get("last_original_messages") or [])
        self._last_forwarded_messages = list(state.get("last_forwarded_messages") or [])
        self._busts_avoided = int(state.get("busts_avoided", 0) or 0)
        self._tokens_preserved = int(state.get("tokens_preserved", 0) or 0)
        self._compression_foregone_tokens = int(
            state.get("compression_foregone_tokens", 0) or 0
        )
        self._consecutive_write_only_turns = int(
            state.get("consecutive_write_only_turns", 0) or 0
        )

    def get_frozen_message_count(self) -> int:
        """How many leading messages to skip compression on the next turn.

        Returns 0 on turn 0 (cold start) or if caching is disabled/below threshold.
        """
        if not self.config.enabled:
            return 0
        if self._turn_number == 0:
            return 0
        if self._cached_token_count < self.config.min_cached_tokens:
            return 0
        frozen_count = self._cached_message_count
        if (
            self._consecutive_write_only_turns >= 2
            and frozen_count > 0
            and len(self._last_forwarded_messages) > frozen_count
        ):
            frozen_count += 1
        return min(frozen_count, max(0, len(self._last_forwarded_messages) - 1))

    def update_from_response(
        self,
        cache_read_tokens: int,
        cache_write_tokens: int,
        messages: list[dict[str, Any]],
        message_token_counts: list[int] | None = None,
        original_messages: list[dict[str, Any]] | None = None,
        system_token_count: int = 0,
    ) -> None:
        """Update tracker with cache metrics from the API response.

        Called after every API call. Computes how many messages to freeze
        on the next turn based on the cache_read_tokens reported.

        Args:
            cache_read_tokens: Tokens read from cache (cache hit portion).
            cache_write_tokens: Tokens written to cache (new cache entries).
            messages: The messages that were sent to the API.
            message_token_counts: Pre-computed token counts per message.
                If None, estimates from content length.
            system_token_count: Estimated token count of the system prompt
                (not included in `messages`). Subtracted from total_cached
                before walking messages so system-prompt-heavy caches do not
                incorrectly freeze the entire message array.
        """
        self._last_activity = time.time()
        self._turn_number += 1
        self._last_original_messages = copy.deepcopy(original_messages or messages)
        self._last_forwarded_messages = copy.deepcopy(messages)

        # Compute total cached tokens (read + write = what's in cache now)
        total_cached = cache_read_tokens + cache_write_tokens

        if cache_write_tokens > 0 and cache_read_tokens == 0:
            self._consecutive_write_only_turns += 1
        elif cache_read_tokens > 0:
            self._consecutive_write_only_turns = 0

        if total_cached == 0:
            self._cached_token_count = 0
            self._cached_message_count = 0
            self._consecutive_write_only_turns = 0
            self._notify_change()
            return

        # Estimate per-message token counts if not provided
        if message_token_counts is None:
            message_token_counts = self._estimate_message_tokens(messages)

        # Subtract system prompt tokens from the cache budget before walking
        # messages. For Claude Code sessions, the system prompt (tools + context)
        # can be 200-400k tokens. Without this, total_cached >> sum(messages),
        # so all messages appear "within the cache boundary" and frozen_count
        # equals len(messages) — nothing left to compress.
        message_budget = max(0, total_cached - system_token_count)

        # Walk messages from the start, accumulating tokens until we exceed
        # the message budget. All messages within the cached prefix are frozen.
        accumulated = 0
        frozen_count = 0
        for i, tok_count in enumerate(message_token_counts):
            accumulated += tok_count
            if accumulated <= message_budget:
                frozen_count = i + 1
            else:
                break

        self._cached_token_count = total_cached
        self._cached_message_count = frozen_count
        self._notify_change()

        logger.debug(
            "PrefixCacheTracker[%s]: turn=%d, cached=%d tokens (system=%d, msg_budget=%d), "
            "frozen=%d/%d messages (read=%d, write=%d)",
            self.provider,
            self._turn_number,
            total_cached,
            system_token_count,
            message_budget,
            frozen_count,
            len(messages),
            cache_read_tokens,
            cache_write_tokens,
        )

    def get_last_original_messages(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._last_original_messages)

    def get_last_forwarded_messages(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._last_forwarded_messages)

    def record_bust_avoided(self, tokens_preserved: int, compression_foregone: int) -> None:
        """Record when we chose to preserve cache over compressing."""
        self._busts_avoided += 1
        self._tokens_preserved += tokens_preserved
        self._compression_foregone_tokens += compression_foregone
        self._notify_change()

    def should_force_compress(
        self,
        message_index: int,
        message_tokens: int,
        estimated_compressed_tokens: int,
    ) -> bool:
        """Check if compression savings outweigh cache preservation.

        Returns True if we should bust the cache and compress anyway.
        This happens when compression would save a large fraction of tokens
        AND the savings exceed the cache read discount.
        """
        if message_index >= self._cached_message_count:
            return True  # Not in frozen prefix, always compress

        if message_tokens == 0:
            return False

        savings_fraction = (message_tokens - estimated_compressed_tokens) / message_tokens

        # Would compression savings exceed the cache read discount?
        read_discount = _PROVIDER_READ_DISCOUNT.get(self.provider, 0.5)
        return savings_fraction > read_discount

    @property
    def is_expired(self) -> bool:
        """Check if this tracker has been idle beyond TTL."""
        return (time.time() - self._last_activity) > self.config.session_ttl_seconds

    @property
    def stats(self) -> FreezeStats:
        """Return stats for dashboard/metrics."""
        return FreezeStats(
            busts_avoided=self._busts_avoided,
            tokens_preserved=self._tokens_preserved,
            compression_foregone_tokens=self._compression_foregone_tokens,
            net_benefit_tokens=self._tokens_preserved - self._compression_foregone_tokens,
            frozen_message_count=self._cached_message_count,
            turn_number=self._turn_number,
            consecutive_write_only_turns=self._consecutive_write_only_turns,
            remediation_active=self._consecutive_write_only_turns >= 2,
        )

    @staticmethod
    def _estimate_message_tokens(messages: list[dict[str, Any]]) -> list[int]:
        """Rough token count per message (chars / 3.5).

        Counts text, tool_result content, and tool_use input fields
        for accurate Anthropic-format estimation.
        """
        counts = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                chars = len(content)
            elif isinstance(content, list):
                chars = 0
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type", "")
                    if block_type == "text":
                        chars += len(block.get("text", ""))
                    elif block_type == "tool_result":
                        inner = block.get("content", "")
                        if isinstance(inner, str):
                            chars += len(inner)
                        elif isinstance(inner, list):
                            chars += sum(
                                len(b.get("text", "")) for b in inner if isinstance(b, dict)
                            )
                    elif block_type == "tool_use":
                        inp = block.get("input")
                        if isinstance(inp, str):
                            chars += len(inp)
                        elif isinstance(inp, dict):
                            chars += len(json.dumps(inp, separators=(",", ":")))
                    else:
                        text = block.get("text", "")
                        if text:
                            chars += len(text)
            else:
                chars = 0
            # Add overhead for role, block structure, etc.
            chars += 20
            counts.append(max(1, int(chars / 3.5)))
        return counts


class SessionTrackerStore:
    """Manages PrefixCacheTracker instances across sessions.

    Keyed by session ID (from x-cutctx-session-id header or computed hash).
    Automatically cleans up expired sessions.
    """

    DEFAULT_DB_PATH = "~/.cutctx/prefix_tracker.db"

    def __init__(
        self,
        default_config: PrefixFreezeConfig | None = None,
        *,
        db_path: str | os.PathLike[str] | None = None,
    ):
        self._trackers: dict[str, PrefixCacheTracker] = {}
        self._default_config = default_config or PrefixFreezeConfig()
        self._last_cleanup: float = time.time()
        self._cleanup_interval: float = 60.0  # Cleanup every 60s
        self._lock = threading.RLock()
        self._stateless = is_stateless()
        if self._stateless:
            self._db_path = ":memory:"
            self._memory_conn: sqlite3.Connection | None = None
        else:
            path = Path(os.path.expanduser(str(db_path or self.DEFAULT_DB_PATH)))
            path.parent.mkdir(parents=True, exist_ok=True)
            self._db_path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if self._stateless:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", timeout=5.0, check_same_thread=False)
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_prefix_trackers (
                    session_id         TEXT PRIMARY KEY,
                    provider           TEXT NOT NULL,
                    state_json         TEXT NOT NULL,
                    last_activity_ts   REAL NOT NULL,
                    updated_at_ts      REAL NOT NULL
                )
                """
            )

    def _tracker_state_json(self, tracker: PrefixCacheTracker) -> str:
        return json.dumps(tracker.snapshot_state(), separators=(",", ":"), ensure_ascii=False)

    def _save_tracker(self, session_id: str, tracker: PrefixCacheTracker) -> None:
        if not session_id:
            return
        if tracker.is_expired:
            self._delete_persisted_tracker(session_id)
            return
        payload = self._tracker_state_json(tracker)
        now = time.time()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO session_prefix_trackers
                    (session_id, provider, state_json, last_activity_ts, updated_at_ts)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    provider = excluded.provider,
                    state_json = excluded.state_json,
                    last_activity_ts = excluded.last_activity_ts,
                    updated_at_ts = excluded.updated_at_ts
                """,
                (session_id, tracker.provider, payload, tracker._last_activity, now),
            )

    def _delete_persisted_tracker(self, session_id: str) -> None:
        if self._stateless:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM session_prefix_trackers WHERE session_id = ?",
                (session_id,),
            )

    def _load_tracker(self, session_id: str) -> PrefixCacheTracker | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT provider, state_json, last_activity_ts FROM session_prefix_trackers "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None

        tracker = PrefixCacheTracker(
            str(row["provider"]),
            self._default_config,
            on_change=lambda t, sid=session_id: self._save_tracker(sid, t),
        )
        try:
            state = json.loads(row["state_json"])
            if isinstance(state, dict):
                tracker.restore_state(state)
        except Exception:
            logger.debug("Failed to restore prefix tracker state for %s", session_id, exc_info=True)
            return None

        tracker._last_activity = float(row["last_activity_ts"] or tracker._last_activity)
        if tracker.is_expired:
            self._delete_persisted_tracker(session_id)
            return None
        tracker._on_change = lambda t, sid=session_id: self._save_tracker(sid, t)
        return tracker

    def get_or_create(self, session_id: str, provider: str) -> PrefixCacheTracker:
        """Get existing tracker or create a new one for this session."""
        self._maybe_cleanup()

        with self._lock:
            if session_id in self._trackers:
                tracker = self._trackers[session_id]
                tracker._last_activity = time.time()
                return tracker

            tracker = self._load_tracker(session_id)
            if tracker is None:
                tracker = PrefixCacheTracker(
                    provider,
                    self._default_config,
                    on_change=lambda t, sid=session_id: self._save_tracker(sid, t),
                )
                self._save_tracker(session_id, tracker)
            self._trackers[session_id] = tracker
            return tracker

    def _derive_caller_fingerprint(self, request: Any) -> str:
        """Derive a caller fingerprint from request auth headers.

        Security: Binds session_id to calling client identity.
        - Extracts x-api-key or authorization header
        - Hashes with sha256 (never stores raw key)
        - Uses "anon" placeholder if no auth header present
        """
        auth_key = ""
        if hasattr(request, "headers"):
            # Try x-api-key first (preferred), then authorization
            auth_key = request.headers.get("x-api-key", "")
            if not auth_key:
                auth_key = request.headers.get("authorization", "")

        if auth_key:
            # Hash the key, never store or log raw value
            return hashlib.sha256(auth_key.encode()).hexdigest()[:16]
        else:
            # Proxy may run without upstream auth in some deployments
            return "anon"

    def compute_session_id(
        self,
        request: Any,
        model: str,
        messages: list[dict[str, Any]],
    ) -> str:
        """Compute a session ID from the request.

        Binds session_id to calling client's identity for isolation.

        Priority:
        1. x-cutctx-session-id header (explicit) + caller fingerprint
        2. Hash of (model + system prompt) + caller fingerprint
        """
        # Derive caller fingerprint to prevent cross-client collisions
        caller_fp = self._derive_caller_fingerprint(request)

        # Check for explicit session header
        if hasattr(request, "headers"):
            session_header = request.headers.get("x-cutctx-session-id")
            if session_header:
                return f"{caller_fp}:{session_header}"

        # Fall back to hashing model + system prompt
        system_content = ""
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str):
                    system_content = content[:500]  # First 500 chars is enough
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            system_content = block.get("text", "")[:500]
                            break
                break

        key = f"{model}:{system_content}"
        content_hash = hashlib.md5(key.encode()).hexdigest()[:16]  # nosec B324
        return f"{caller_fp}:{content_hash}"

    def _maybe_cleanup(self) -> None:
        """Remove expired trackers periodically."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        with self._lock:
            expired = [sid for sid, tracker in self._trackers.items() if tracker.is_expired]
            for sid in expired:
                del self._trackers[sid]
                self._delete_persisted_tracker(sid)

        if expired:
            logger.debug("SessionTrackerStore: cleaned up %d expired sessions", len(expired))

        self._last_cleanup = now

    @property
    def active_sessions(self) -> int:
        """Number of active session trackers."""
        return len(self._trackers)
