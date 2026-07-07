# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""WS11 Tool-result memoizer.

Per artifacts/savings-moat-expansion-specs.md WS11:
- Flag: CUTCTX_MEMOIZE=1 (default off — additive contract).
- Built-in allowlist of read-only, deterministic tools (file_read,
  code_search, cutctx_retrieve). Anything not on the allowlist is
  never memoized.
- Key: (session_id, tool_name, canonicalized_args_hash). Canonicalization
  sorts JSON keys, normalizes paths, drops pagination-irrelevant
  fields.
- LRU per session, 256 entries/session.
- Write tool call (write/edit/delete) flushes the WHOLE session cache
  — the spec: 'When in doubt, flush the whole session cache —
  correctness beats savings.'
- Pass-through re-serialization byte-identical to the original tool
  output. Stored bytes are returned as-is on a hit; no JSON
  round-trip, no whitespace normalization.
"""

from __future__ import annotations

import hashlib
import json
import logging
import posixpath
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


# Default LRU cap (per spec): 256 entries per session.
DEFAULT_MEMOIZE_LRU_SIZE = 256

# Default allowlist (per spec): read-only, deterministic-within-a-session
# tools. Conservative — anything not on this list is never memoized.
DEFAULT_MEMOIZE_ALLOWLIST: frozenset[str] = frozenset(
    {"file_read", "code_search", "cutctx_retrieve"}
)

# Default write-tool list (per spec). Any successful call to one of
# these tools triggers session-wide cache invalidation.
DEFAULT_WRITE_TOOLS: frozenset[str] = frozenset({"file_write", "file_edit", "file_delete"})

# Pagination-irrelevant fields: these don't change the tool's output
# content, so two calls with different pagination are equivalent for
# memoization purposes.
_PAGINATION_IRRELEVANT_FIELDS = frozenset({"page", "page_size", "cursor", "offset", "limit"})


# ---------------------------------------------------------------------------
# Pure functions — public for direct testing
# ---------------------------------------------------------------------------


def canonicalize_args(args: Any) -> str:
    """Canonicalize tool-call arguments to a deterministic string.

    The canonical form is JSON with sorted keys, normalized paths,
    pagination-irrelevant fields stripped, and recursive sorting of
    nested dicts/lists. Two equivalent args (e.g. {"path": "/a/./b"}
    vs {"path": "/a/b"}) produce the same canonical string.

    Args:
        args: Tool-call arguments (any JSON-serializable type).

    Returns:
        Canonical-form string. Always a valid JSON string.
    """
    canonical = _canonicalize(args)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"))


def _canonicalize(value: Any) -> Any:
    """Recursively canonicalize a value. Returns the canonical form
    (NOT a JSON string) — the top-level call wraps with json.dumps.

    The key design point: this function returns Python objects
    (str, int, dict, list), not pre-serialized JSON. The top-level
    call applies json.dumps once. This avoids the double-encoding
    bug where strings got wrapped in extra quotes at every level.
    """
    if isinstance(value, Mapping):
        # Drop pagination-irrelevant keys; sort what remains.
        cleaned = {k: v for k, v in value.items() if k not in _PAGINATION_IRRELEVANT_FIELDS}
        # Normalize paths where the key is a path-like key.
        normalized: dict[str, Any] = {}
        for k, v in cleaned.items():
            if k in ("path", "file_path", "target", "filepath"):
                normalized[k] = _normalize_path(v)
            else:
                normalized[k] = _canonicalize(v)
        return normalized
    if isinstance(value, list | tuple):
        return [_canonicalize(item) for item in value]
    # Leaves (str, int, float, bool, None) pass through unchanged.
    return value


def _normalize_path(value: Any) -> str:
    """Normalize a path string by collapsing . and .. segments.

    Per the spec, 'normalizes paths'. We use posixpath.normpath to
    get a deterministic form. Non-string values pass through
    unchanged (caller-side bug; not our concern here).
    """
    if not isinstance(value, str):
        return value
    # Treat the path as POSIX (the spec is path-format-agnostic; the
    # tool's canonical form on the wire is what matters).
    normed = posixpath.normpath(value)
    # Strip a trailing slash that normpath leaves for root paths.
    return normed if normed != "/" else "/"


def derive_key(session_id: str, tool_name: str, args: Any) -> str:
    """Derive a stable key from (session_id, tool_name, args).

    The key is a SHA-256 hex digest truncated to 32 chars.
    """
    canonical = canonicalize_args(args) if not isinstance(args, str) else args
    raw = f"{session_id}|{tool_name}|{canonical}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def is_write_tool(tool_name: str, config: MemoizeConfig) -> bool:
    """True if this tool's successful invocation must flush the
    session cache (write/edit/delete)."""
    return tool_name in config.write_tools


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class MemoizeConfig:
    """Configuration for the tool-result memoizer.

    All sub-flags default to False / off. The flag-off golden contract
    is that ToolMemoizer(config) is a no-op.
    """

    enabled: bool = False
    max_entries_per_session: int = DEFAULT_MEMOIZE_LRU_SIZE
    allowlist: frozenset[str] = field(default_factory=lambda: DEFAULT_MEMOIZE_ALLOWLIST)
    write_tools: frozenset[str] = field(default_factory=lambda: DEFAULT_WRITE_TOOLS)

    def is_tool_allowlisted(self, tool_name: str) -> bool:
        """True if tool_name is on the allowlist. Per spec, anything
        not on the allowlist is never memoized."""
        return tool_name in self.allowlist


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class MemoizeAction(str, Enum):
    """Possible outcomes of `maybe_memoize`."""

    HIT = "hit"
    MISS = "miss"
    PASSTHROUGH = "passthrough"


@dataclass
class MemoizeDecision:
    """The result of asking the memoizer whether to memoize.

    `action`:
        "hit"    -> the call is a cache hit; `payload` is the
                   previously-stored tool result (byte-identical).
        "miss"   -> the call is a cache miss; the caller must call
                   `record(...)` after the upstream response arrives.
        "passthrough" -> the memoizer is disabled, the tool is
                   not on the allowlist, or the call should not be
                   memoized for any reason. The caller proceeds
                   normally (no cache lookup, no record).
    """

    action: str
    payload: str | None = None
    key: str = ""

    def __post_init__(self) -> None:
        # Normalize the action to a plain string so equality checks
        # work whether the caller passes a string ("passthrough") or
        # a MemoizeAction enum instance.
        if not isinstance(self.action, str):
            self.action = str(self.action)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@dataclass
class MemoizeStats:
    """Per-session memoizer statistics. Used for the dashboard
    surface and for the WS11 attribution path.
    """

    entries: int = 0
    hits: int = 0
    misses: int = 0
    invalidations: int = 0
    evictions: int = 0
    passthroughs: int = 0


# ---------------------------------------------------------------------------
# The memoizer
# ---------------------------------------------------------------------------


class ToolMemoizer:
    """Per-session, per-tool memoizer with conservative write-invalidation.

    Usage:
        cfg = MemoizeConfig(enabled=True)
        memoizer = ToolMemoizer(cfg)

        # Before the upstream call:
        decision = memoizer.maybe_memoize(session_id, tool_name, args)
        if decision.action == "hit":
            # Use decision.payload as the tool result; no upstream call
            pass
        else:
            # Make the upstream call, then:
            memoizer.record(session_id, tool_name, args, response_bytes)

        # When a write tool succeeds, call:
        memoizer.invalidate_for_write(session_id, tool_name, args)

    Flag-off behavior: when config.enabled is False, every
    maybe_memoize returns a passthrough decision and the memoizer
    holds no state. This is the spec's golden contract.
    """

    def __init__(self, config: MemoizeConfig | None = None) -> None:
        self.config = config or MemoizeConfig()
        # Per-session LRU caches. OrderedDict.move_to_end() provides
        # O(1) LRU semantics.
        self._caches: dict[str, OrderedDict[str, MemoizeEntry]] = {}
        self._stats: dict[str, MemoizeStats] = {}

    def maybe_memoize(self, session_id: str, tool_name: str, args: Any) -> MemoizeDecision:
        """Decide whether to use a cached result, miss, or pass through.

        Flag-off short-circuit happens before any state lookup.
        """
        if not self.config.enabled:
            return MemoizeDecision(action=MemoizeAction.PASSTHROUGH)

        if not self.config.is_tool_allowlisted(tool_name):
            self._bump_passthrough(session_id)
            return MemoizeDecision(action=MemoizeAction.PASSTHROUGH)

        key = derive_key(session_id, tool_name, args)
        cache = self._caches.setdefault(session_id, OrderedDict())
        entry = cache.get(key)
        if entry is not None:
            # LRU touch
            cache.move_to_end(key)
            self._bump_hit(session_id)
            return MemoizeDecision(action=MemoizeAction.HIT, payload=entry.payload, key=key)
        self._bump_miss(session_id)
        return MemoizeDecision(action=MemoizeAction.MISS, key=key)

    def record(self, session_id: str, tool_name: str, args: Any, payload: str) -> None:
        """Record the upstream tool result. No-op when disabled."""
        if not self.config.enabled:
            return
        if not self.config.is_tool_allowlisted(tool_name):
            return

        key = derive_key(session_id, tool_name, args)
        cache = self._caches.setdefault(session_id, OrderedDict())
        # If we're at capacity, evict the LRU entry.
        if len(cache) >= self.config.max_entries_per_session and key not in cache:
            evicted_key, _ = cache.popitem(last=False)
            self._bump_eviction(session_id, evicted_key)
        # Store. If the key already exists, this just overwrites the
        # payload (no size change).
        cache[key] = MemoizeEntry(tool_name=tool_name, payload=payload)
        cache.move_to_end(key)
        self._bump_record(session_id)

    def invalidate_for_write(self, session_id: str, tool_name: str, args: Any) -> None:
        """Flush the session cache because a write tool succeeded.

        Per spec: 'When in doubt, flush the whole session cache —
        correctness beats savings.' We always flush the whole session;
        path-overlap detection would be a future optimization.
        """
        if not self.config.enabled:
            return
        if tool_name not in self.config.write_tools:
            return
        # Flush the whole session.
        cache = self._caches.get(session_id)
        if cache is not None:
            cache.clear()
        self._bump_invalidation(session_id)

    def stats_for(self, session_id: str) -> MemoizeStats:
        """Return the stats for a session, creating a zero stats object
        if the session has never been seen."""
        return self._stats.setdefault(session_id, MemoizeStats())

    # Internal stat helpers
    def _bump_hit(self, session_id: str) -> None:
        self._stats.setdefault(session_id, MemoizeStats()).hits += 1

    def _bump_miss(self, session_id: str) -> None:
        self._stats.setdefault(session_id, MemoizeStats()).misses += 1

    def _bump_record(self, session_id: str) -> None:
        # entries count = current cache size
        cache = self._caches.get(session_id)
        if cache is not None:
            self._stats.setdefault(session_id, MemoizeStats()).entries = len(cache)

    def _bump_invalidation(self, session_id: str) -> None:
        s = self._stats.setdefault(session_id, MemoizeStats())
        s.invalidations += 1
        s.entries = 0

    def _bump_eviction(self, session_id: str, evicted_key: str) -> None:
        s = self._stats.setdefault(session_id, MemoizeStats())
        s.evictions += 1
        s.entries = max(0, s.entries - 1)

    def _bump_passthrough(self, session_id: str) -> None:
        self._stats.setdefault(session_id, MemoizeStats()).passthroughs += 1


@dataclass
class MemoizeEntry:
    """One cache entry: a stored tool result keyed by (session, tool, args)."""

    tool_name: str
    payload: str


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


__all__ = [
    "DEFAULT_MEMOIZE_LRU_SIZE",
    "DEFAULT_MEMOIZE_ALLOWLIST",
    "DEFAULT_WRITE_TOOLS",
    "MemoizeConfig",
    "MemoizeDecision",
    "MemoizeAction",
    "MemoizeStats",
    "MemoizeEntry",
    "ToolMemoizer",
    "canonicalize_args",
    "derive_key",
    "is_write_tool",
    "record_tool_results_from_messages",
]

def _estimate_tokens_for_payload(payload: Any) -> int:
    """Rough, conservative token estimate for a cached tool payload
    (~4 bytes/token, same heuristic used elsewhere in the funnel for
    payloads that never go through the real tokenizer)."""
    if not payload:
        return 0
    text = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    return max(0, len(text) // 4)


def record_tool_results_from_messages(
    memoizer: ToolMemoizer, messages: list[dict], session_id: str
) -> tuple[int, int]:
    """Scan conversation history and record tool results / invalidate on writes.

    Before recording each read-only tool result, this consults
    ``memoizer.maybe_memoize`` first. If an identical (session, tool,
    args) call was already recorded earlier in this same conversation
    history, that occurrence is a genuine memoization hit — the
    duplicate round-trip could have been served from cache instead of
    resent in full. Those hits are exactly what WS11
    (``RequestOutcome.memoization_hits`` / ``memoization_tokens_saved``)
    is meant to attribute.

    Returns:
        A ``(hits, tokens_saved)`` tuple for THIS call. Both are 0 when
        the memoizer is disabled, there are no messages, or no
        duplicate calls were found.
    """
    hits = 0
    tokens_saved = 0
    if not memoizer.config.enabled or not messages:
        return hits, tokens_saved

    # Map tool_call_id -> (tool_name, args) from assistant tool_calls
    tool_calls = {}
    for msg in messages:
        # OpenAI format
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg.get("tool_calls", []):
                tcid = tc.get("id")
                fn = tc.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments", "{}")
                if tcid and name:
                    try:
                        parsed_args = json.loads(args)
                    except Exception:
                        parsed_args = args
                    tool_calls[tcid] = (name, parsed_args)
        # Anthropic format
        elif msg.get("role") == "assistant" and isinstance(msg.get("content"), list):
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tcid = block.get("id")
                    name = block.get("name")
                    args = block.get("input", {})
                    if tcid and name:
                        tool_calls[tcid] = (name, args)

    def _record_or_invalidate(name: str, args: Any, content: Any) -> None:
        nonlocal hits, tokens_saved
        if is_write_tool(name, memoizer.config):
            memoizer.invalidate_for_write(session_id, name, args)
            return
        # Consult the cache BEFORE recording: if this exact call was
        # already recorded earlier in this same history, it's a hit.
        decision = memoizer.maybe_memoize(session_id, name, args)
        if decision.action == MemoizeAction.HIT:
            hits += 1
            tokens_saved += _estimate_tokens_for_payload(decision.payload)
        # record() is idempotent (overwrites the same key) and keeps
        # the LRU entry fresh — safe to call on both hit and miss.
        memoizer.record(session_id, name, args, content)

    # Process tool results
    for msg in messages:
        # OpenAI format
        if msg.get("role") == "tool":
            tcid = msg.get("tool_call_id")
            content = msg.get("content")
            if tcid in tool_calls and content is not None:
                name, args = tool_calls[tcid]
                _record_or_invalidate(name, args, content)
        # Anthropic format
        elif msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tcid = block.get("tool_use_id")
                    content = block.get("content")
                    if isinstance(content, list):
                        # Anthropic can have array of blocks for content
                        content = json.dumps(content)
                    if tcid in tool_calls and content is not None:
                        name, args = tool_calls[tcid]
                        _record_or_invalidate(name, args, content)

    return hits, tokens_saved
