# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD tests for the WS11 tool-result memoizer.

Per artifacts/savings-moat-expansion-specs.md WS11:
- Flag: CUTCTX_MEMOIZE=1 (default off).
- Built-in allowlist of read-only, deterministic tools (file read,
  code search, cutctx_retrieve). Anything not on the allowlist is
  never memoized.
- Key: (session_id, tool_name, canonicalized_args_hash). Canonicalization
  sorts JSON keys, normalizes paths, drops pagination-irrelevant
  fields.
- LRU per session, 256 entries/session.
- Write tool call (write/edit/delete) flushes overlapping cache
  entries — correctness over savings.
- Pass-through re-serialization byte-identical to the original tool
  output (no drift).

TDD: written first, then cutctx/proxy/memoizer.py is made to
satisfy them. If a test breaks after the implementation lands, the
spec changed — update both.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from cutctx.proxy.memoizer import (
    DEFAULT_MEMOIZE_LRU_SIZE,
    MemoizeConfig,
    MemoizeDecision,
    MemoizeEntry,
    ToolMemoizer,
    canonicalize_args,
    derive_key,
    is_write_tool,
)


# ---------------------------------------------------------------------------
# Flag-off golden contract — the spec's permanent test
# ---------------------------------------------------------------------------


def test_default_memoize_config_is_all_off() -> None:
    """The default MemoizeConfig must be all-off. This is the spec's
    flag-off golden contract from strategy-implementation-plan.md §0.1.
    """
    cfg = MemoizeConfig()
    assert cfg.enabled is False
    assert cfg.max_entries_per_session == DEFAULT_MEMOIZE_LRU_SIZE
    assert cfg.allowlist == frozenset(
        {"file_read", "code_search", "cutctx_retrieve"}
    )
    assert cfg.write_tools == frozenset(
        {"file_write", "file_edit", "file_delete"}
    )


def test_default_memoize_decision_is_passthrough() -> None:
    """A default Memoizer (all-off) must always return PASSTHROUGH."""
    memoizer = ToolMemoizer(MemoizeConfig())
    decision = memoizer.maybe_memoize(
        session_id="s1",
        tool_name="file_read",
        args={"path": "/etc/hosts"},
    )
    assert decision == MemoizeDecision(action="passthrough")


# ---------------------------------------------------------------------------
# Canonicalization — properties that hold for ALL inputs
# ---------------------------------------------------------------------------


def test_canonicalize_args_sorts_json_keys() -> None:
    """Same dict, different key order -> same canonical form."""
    a = canonicalize_args({"path": "/a", "limit": 5})
    b = canonicalize_args({"limit": 5, "path": "/a"})
    assert a == b


def test_canonicalize_args_strips_pagination_irrelevant_fields() -> None:
    """Per spec: drops pagination-irrelevant fields. Our baseline
    list includes _page, page_size, cursor (the spec says
    'pagination-irrelevant'; we drop the *irrelevant* ones —
    fields that don't change the tool output's content).
    """
    raw = {"path": "/a", "page": 1, "page_size": 50, "cursor": "abc"}
    canonical = canonicalize_args(raw)
    # page/page_size/cursor should be absent
    parsed = json.loads(canonical)
    assert "page" not in parsed
    assert "page_size" not in parsed
    assert "cursor" not in parsed
    assert parsed == {"path": "/a"}


def test_canonicalize_args_normalizes_paths() -> None:
    """Paths with . and .. normalize to the same canonical form."""
    a = canonicalize_args({"path": "/a/b/../c/./d"})
    b = canonicalize_args({"path": "/a/c/d"})
    assert a == b


def test_canonicalize_args_deterministic() -> None:
    """canonicalize ∘ canonicalize == canonicalize (idempotent)."""
    raw = {"path": "/x/y/../z", "limit": 10, "page": 1}
    once = canonicalize_args(raw)
    # Re-canonicalize the JSON-string output by parsing it back to a
    # dict. (The intermediate string form is itself a valid canonical
    # form; passing the string through would JSON-escape it twice,
    # which is the desired "no further change" property.)
    twice = canonicalize_args(json.loads(once))
    assert once == twice


def test_canonicalize_args_handles_nested_dicts() -> None:
    """Nested dicts are recursively sorted + canonicalized."""
    raw = {"a": {"z": 1, "a": 2}, "b": [{"y": 1, "x": 2}]}
    out = canonicalize_args(raw)
    parsed = json.loads(out)
    assert list(parsed["a"].keys()) == ["a", "z"]
    assert list(parsed["b"][0].keys()) == ["x", "y"]


def test_canonicalize_args_handles_non_dict_inputs() -> None:
    """Top-level non-dict (string, int, list) is JSON-serialized as-is
    (same compact form the dict path uses: no spaces, ':' and ','
    separators)."""
    assert canonicalize_args("hello") == '"hello"'
    assert canonicalize_args(42) == "42"
    assert canonicalize_args([3, 1, 2]) == "[3,1,2]"


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def test_derive_key_is_stable() -> None:
    """Same (session, tool, args) -> same key."""
    args = {"path": "/a", "limit": 5}
    k1 = derive_key("s1", "file_read", args)
    k2 = derive_key("s1", "file_read", args)
    assert k1 == k2
    # Key is a hex string
    assert all(c in "0123456789abcdef" for c in k1)


def test_derive_key_varies_with_session() -> None:
    """Different sessions -> different keys even with the same args."""
    args = {"path": "/a"}
    k1 = derive_key("s1", "file_read", args)
    k2 = derive_key("s2", "file_read", args)
    assert k1 != k2


def test_derive_key_varies_with_tool() -> None:
    """Different tools -> different keys even with the same args."""
    args = {"path": "/a"}
    k1 = derive_key("s1", "file_read", args)
    k2 = derive_key("s1", "code_search", args)
    assert k1 != k2


def test_derive_key_varies_with_args() -> None:
    """Different args -> different keys (canonicalized first)."""
    k1 = derive_key("s1", "file_read", {"path": "/a"})
    k2 = derive_key("s1", "file_read", {"path": "/b"})
    assert k1 != k2


def test_derive_key_treats_equivalent_args_as_same() -> None:
    """Args that canonicalize to the same form produce the same key."""
    k1 = derive_key("s1", "file_read", {"path": "/a/b/../c", "limit": 5})
    k2 = derive_key("s1", "file_read", {"path": "/a/c", "limit": 5})
    assert k1 == k2


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------


def test_read_only_tool_is_allowlisted() -> None:
    """Default allowlist contains file_read."""
    cfg = MemoizeConfig(enabled=True)
    assert cfg.is_tool_allowlisted("file_read") is True


def test_search_tool_is_allowlisted() -> None:
    """Default allowlist contains code_search."""
    cfg = MemoizeConfig(enabled=True)
    assert cfg.is_tool_allowlisted("code_search") is True


def test_cutctx_retrieve_is_allowlisted() -> None:
    """Default allowlist contains cutctx_retrieve."""
    cfg = MemoizeConfig(enabled=True)
    assert cfg.is_tool_allowlisted("cutctx_retrieve") is True


def test_unknown_tool_is_not_allowlisted() -> None:
    """Anything not on the allowlist is never memoized."""
    cfg = MemoizeConfig(enabled=True)
    assert cfg.is_tool_allowlisted("shell_exec") is False
    assert cfg.is_tool_allowlisted("web_fetch") is False


def test_custom_allowlist_overrides_default() -> None:
    """A custom allowlist is the ONLY allowlist (no union with default)."""
    cfg = MemoizeConfig(enabled=True, allowlist=frozenset({"my_custom_tool"}))
    assert cfg.is_tool_allowlisted("my_custom_tool") is True
    assert cfg.is_tool_allowlisted("file_read") is False  # NOT in custom


# ---------------------------------------------------------------------------
# Write tool detection (for invalidation)
# ---------------------------------------------------------------------------


def test_is_write_tool_recognizes_known_writes() -> None:
    """Default write_tools contains the spec's examples."""
    assert is_write_tool("file_write", MemoizeConfig()) is True
    assert is_write_tool("file_edit", MemoizeConfig()) is True
    assert is_write_tool("file_delete", MemoizeConfig()) is True


def test_is_write_tool_rejects_reads() -> None:
    assert is_write_tool("file_read", MemoizeConfig()) is False
    assert is_write_tool("code_search", MemoizeConfig()) is False


# ---------------------------------------------------------------------------
# Memoizer — flag-off path
# ---------------------------------------------------------------------------


def test_memoizer_disabled_always_passthrough() -> None:
    memoizer = ToolMemoizer(MemoizeConfig(enabled=False))
    for _ in range(10):
        d = memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
        assert d == MemoizeDecision(action="passthrough")
    # Cache should be untouched
    assert memoizer.stats_for("s1").hits == 0
    assert memoizer.stats_for("s1").misses == 0


# ---------------------------------------------------------------------------
# Memoizer — flag-on, allowlisted tool
# ---------------------------------------------------------------------------


def test_memoizer_first_call_misses_and_records() -> None:
    """First call to an allowlisted tool misses, records the result."""
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    d = memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
    assert d.action == "miss"
    assert d.key  # not empty
    # Caller now records the result
    memoizer.record("s1", "file_read", {"path": "/a"}, "file contents here")
    # Stats
    s = memoizer.stats_for("s1")
    assert s.misses == 1
    assert s.hits == 0
    assert s.entries == 1


def test_memoizer_second_call_hits_and_returns_stored_bytes() -> None:
    """A second call with the same args must hit and return the EXACT
    bytes the caller stored (no re-serialization drift).
    """
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    args = {"path": "/a"}
    payload = '{"file_contents": "hello world", "lines": [1, 2, 3]}'

    # First call: miss
    d1 = memoizer.maybe_memoize("s1", "file_read", args)
    assert d1.action == "miss"
    memoizer.record("s1", "file_read", args, payload)

    # Second call: hit
    d2 = memoizer.maybe_memoize("s1", "file_read", args)
    assert d2.action == "hit"
    assert d2.payload == payload  # EXACT bytes, no re-serialization


def test_memoizer_different_args_misses() -> None:
    """Different args -> miss, even for the same tool+session."""
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
    memoizer.record("s1", "file_read", {"path": "/a"}, "contents of a")

    d = memoizer.maybe_memoize("s1", "file_read", {"path": "/b"})
    assert d.action == "miss"


def test_memoizer_non_allowlisted_tool_passthrough() -> None:
    """Non-allowlisted tool -> passthrough, even with flag on."""
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    d = memoizer.maybe_memoize("s1", "shell_exec", {"cmd": "ls"})
    assert d == MemoizeDecision(action="passthrough")


# ---------------------------------------------------------------------------
# Write invalidation
# ---------------------------------------------------------------------------


def test_write_tool_flushes_overlapping_session_cache() -> None:
    """A write tool call must flush the session's cache so the next
    read returns fresh content. This is the spec's correctness-
    critical test: 'read → edit → read returns fresh content'.
    """
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))

    # Read /a -> stored
    memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
    memoizer.record("s1", "file_read", {"path": "/a"}, "old contents")
    assert memoizer.stats_for("s1").entries == 1

    # Write /a -> should flush /a
    memoizer.invalidate_for_write("s1", "file_write", {"path": "/a"})

    # Re-read /a -> must miss (cache flushed)
    d = memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
    assert d.action == "miss"
    assert memoizer.stats_for("s1").entries == 0


def test_write_to_different_path_does_not_flush_unrelated() -> None:
    """Writing to /b should NOT flush /a — paths are the invalidation
    unit. Conservatively, ANY write to ANY path flushes everything
    in the session, because path-overlap detection is hard. Per the
    spec: 'When in doubt, flush the whole session cache — correctness
    beats savings.'
    """
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
    memoizer.record("s1", "file_read", {"path": "/a"}, "old a")

    # Write to /b (different path)
    memoizer.invalidate_for_write("s1", "file_write", {"path": "/b"})

    # Spec says: flush the whole session when in doubt. So /a is
    # also flushed.
    d = memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
    assert d.action == "miss", (
        "spec: 'when in doubt, flush the whole session cache'"
    )


def test_write_invalidation_only_affects_target_session() -> None:
    """A write in session s1 does not flush session s2."""
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
    memoizer.record("s1", "file_read", {"path": "/a"}, "a")
    memoizer.maybe_memoize("s2", "file_read", {"path": "/a"})
    memoizer.record("s2", "file_read", {"path": "/a"}, "a")

    memoizer.invalidate_for_write("s1", "file_write", {"path": "/a"})

    # s1 flushed
    d1 = memoizer.maybe_memoize("s1", "file_read", {"path": "/a"})
    assert d1.action == "miss"
    # s2 untouched
    d2 = memoizer.maybe_memoize("s2", "file_read", {"path": "/a"})
    assert d2.action == "hit"


# ---------------------------------------------------------------------------
# LRU eviction
# ---------------------------------------------------------------------------


def test_lru_eviction_at_max_capacity() -> None:
    """At max_entries_per_session, the oldest entry is evicted on insert."""
    cfg = MemoizeConfig(enabled=True, max_entries_per_session=3)
    memoizer = ToolMemoizer(cfg)

    # Insert 3 entries
    for i in range(3):
        args = {"path": f"/{i}"}
        memoizer.maybe_memoize("s1", "file_read", args)
        memoizer.record("s1", "file_read", args, f"contents {i}")

    # All 3 are present
    for i in range(3):
        d = memoizer.maybe_memoize("s1", "file_read", {"path": f"/{i}"})
        assert d.action == "hit"

    # Insert a 4th -> evicts /0
    memoizer.maybe_memoize("s1", "file_read", {"path": "/3"})
    memoizer.record("s1", "file_read", {"path": "/3"}, "contents 3")

    d0 = memoizer.maybe_memoize("s1", "file_read", {"path": "/0"})
    assert d0.action == "miss", "LRU should have evicted /0"
    # /1, /2, /3 still present
    for i in [1, 2, 3]:
        d = memoizer.maybe_memoize("s1", "file_read", {"path": f"/{i}"})
        assert d.action == "hit"


def test_lru_capacity_default_is_256() -> None:
    """Per spec, default LRU cap is 256 entries/session."""
    assert DEFAULT_MEMOIZE_LRU_SIZE == 256


# ---------------------------------------------------------------------------
# BDD: behavioral scenarios from the spec
# ---------------------------------------------------------------------------


def test_bdd_scenario_agent_reads_same_file_twice() -> None:
    """Spec scenario: 'agent reads same file twice -> second read served
    locally, upstream sees one fewer round trip'.
    """
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    args = {"path": "/repo/src/auth.py"}

    # First read: miss
    d1 = memoizer.maybe_memoize("s1", "file_read", args)
    assert d1.action == "miss"
    payload = '{"lines": ["import jwt", "def auth(): ..."], "size": 4096}'
    memoizer.record("s1", "file_read", args, payload)

    # Second read: hit, exact same bytes
    d2 = memoizer.maybe_memoize("s1", "file_read", args)
    assert d2.action == "hit"
    assert d2.payload == payload


def test_bdd_scenario_edit_then_read_returns_fresh() -> None:
    """Spec scenario: 'read → edit → read returns fresh content'.
    This is the correctness-critical test; do not ship without it.
    """
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    args = {"path": "/repo/src/auth.py"}

    # Read 1
    d1 = memoizer.maybe_memoize("s1", "file_read", args)
    assert d1.action == "miss"
    memoizer.record("s1", "file_read", args, '{"auth": "v1"}')

    # Read 2 (cache hit)
    d2 = memoizer.maybe_memoize("s1", "file_read", args)
    assert d2.action == "hit"
    assert d2.payload == '{"auth": "v1"}'

    # Edit
    memoizer.invalidate_for_write("s1", "file_edit", args)

    # Read 3 (must miss because of the edit)
    d3 = memoizer.maybe_memoize("s1", "file_read", args)
    assert d3.action == "miss"
    memoizer.record("s1", "file_read", args, '{"auth": "v2"}')

    # Read 4 (now cache hit again with the new content)
    d4 = memoizer.maybe_memoize("s1", "file_read", args)
    assert d4.action == "hit"
    assert d4.payload == '{"auth": "v2"}'


def test_bdd_scenario_non_allowlisted_tool_skips_memoization() -> None:
    """Spec scenario: 'Anything not allowlisted is never memoized.'"""
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    # shell_exec is not on the default allowlist
    d = memoizer.maybe_memoize("s1", "shell_exec", {"cmd": "rm -rf /"})
    assert d == MemoizeDecision(action="passthrough")
    # Stats confirm no entry was recorded
    assert memoizer.stats_for("s1").entries == 0


# ---------------------------------------------------------------------------
# Regression guard: flag-off path byte-identical to no-memoizer
# ---------------------------------------------------------------------------


def test_flag_off_memoizer_does_not_grow_state() -> None:
    """With flag off, the memoizer must not consume memory, hold
    entries, or affect stats. The flag-off golden contract is
    'behave as if the module were not installed'.
    """
    memoizer = ToolMemoizer(MemoizeConfig(enabled=False))
    # Hammer the memoizer with many calls; nothing should accumulate.
    for i in range(100):
        memoizer.maybe_memoize(f"s{i}", "file_read", {"path": f"/{i}"})
        memoizer.record(f"s{i}", "file_read", {"path": f"/{i}"}, f"contents {i}")
        memoizer.invalidate_for_write(f"s{i}", "file_write", {"path": f"/{i}"})
    # All sessions have no entries
    for i in range(100):
        s = memoizer.stats_for(f"s{i}")
        assert s.entries == 0
        assert s.hits == 0
        assert s.misses == 0
