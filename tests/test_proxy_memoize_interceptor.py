# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD tests for the WS11 tool-result memoization interceptor.

Per artifacts/savings-moat-expansion-specs.md WS11 step 3 (interception
wiring alongside CCR's tool handling in response_handler.py) and
step 4 (write-invalidation e2e: read → edit → read returns fresh
content).

The interceptor is a thin layer that wraps the existing CCR tool
handling — extending, not duplicating. When the flag is off it is a
no-op (golden contract). When the flag is on, allowlisted tool
calls with cached results are short-circuited with a fabricated
tool_result.

These tests are written BEFORE the implementation, per the user's
TDD requirement.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from cutctx.proxy.memoizer import (
    MemoizeConfig,
    MemoizeStats,
    ToolMemoizer,
)
from cutctx.proxy.memoize_interceptor import (
    MemoizeInterceptor,
    InterceptedToolCall,
    InterceptedToolResult,
)


# ---------------------------------------------------------------------------
# Flag-off golden contract — the spec's permanent test
# ---------------------------------------------------------------------------


def test_default_interceptor_is_a_noop() -> None:
    """A default MemoizeInterceptor (flag off) must be a no-op: any
    response passes through unchanged.
    """
    interceptor = MemoizeInterceptor()
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "file_read",
                                "arguments": json.dumps({"path": "/a"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    out = interceptor.intercept_tool_calls(response, session_id="s1")
    # No replacement
    assert out.replaced == []
    # No fabrication
    assert out.fabricated == []
    # Original response unchanged
    assert out.response is response


def test_flag_off_interceptor_does_not_grow_state() -> None:
    """With flag off, hammer the interceptor with many tool calls;
    nothing should accumulate in the memoizer.
    """
    interceptor = MemoizeInterceptor()
    for i in range(50):
        response = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": f"call_{i}",
                                "type": "function",
                                "function": {
                                    "name": "file_read",
                                    "arguments": json.dumps({"path": f"/{i}"}),
                                },
                            }
                        ]
                    }
                }
            ]
        }
        interceptor.intercept_tool_calls(response, session_id=f"s{i}")
    # All sessions have zero entries
    for i in range(50):
        s = interceptor.memoizer.stats_for(f"s{i}")
        assert s.entries == 0
        assert s.hits == 0
        assert s.misses == 0


# ---------------------------------------------------------------------------
# Flag-on: cache hit fabrication
# ---------------------------------------------------------------------------


def test_interceptor_fabricates_tool_result_on_cache_hit() -> None:
    """When the memoizer has a cached result, the interceptor must
    return a fabricated tool_result for that tool call (the upstream
    call is short-circuited).
    """
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    args = {"path": "/repo/src/auth.py"}
    payload = '{"contents": "import jwt"}'

    # Pre-populate the cache as if a prior call had completed.
    interceptor.memoizer.maybe_memoize("s1", "file_read", args)
    interceptor.memoizer.record("s1", "file_read", args, payload)

    # Now intercept a new response that has the same file_read call.
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_42",
                            "type": "function",
                            "function": {
                                "name": "file_read",
                                "arguments": json.dumps(args),
                            },
                        }
                    ],
                }
            }
        ]
    }
    out = interceptor.intercept_tool_calls(response, session_id="s1")
    # One fabricated tool result
    assert len(out.fabricated) == 1
    fab = out.fabricated[0]
    assert fab.tool_call_id == "call_42"
    assert fab.name == "file_read"
    # The fabricated content must be BYTE-IDENTICAL to the stored payload
    assert fab.content == payload
    # No upstream round-trip (no replacement needed; the call was
    # satisfied locally)
    assert out.replaced == []


def test_interceptor_passes_through_on_cache_miss() -> None:
    """On a cache miss, the tool call is passed through to the
    upstream (no fabrication). The interceptor does NOT itself record
    — the caller is expected to call `record()` after the upstream
    response arrives. The miss is recorded in stats.
    """
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_99",
                            "type": "function",
                            "function": {
                                "name": "file_read",
                                "arguments": json.dumps({"path": "/new"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    out = interceptor.intercept_tool_calls(response, session_id="s1")
    # Cache miss: no fabrication
    assert out.fabricated == []
    # The call is passed through (not replaced)
    assert out.replaced == []
    # Stats reflect a miss
    assert interceptor.memoizer.stats_for("s1").misses == 1


def test_interceptor_does_not_fabricate_non_allowlisted_tool() -> None:
    """Non-allowlisted tool calls pass through unchanged, even with
    flag on. Per spec: 'Anything not allowlisted is never memoized.'
    """
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_x",
                            "type": "function",
                            "function": {
                                "name": "shell_exec",
                                "arguments": json.dumps({"cmd": "rm -rf /"}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    out = interceptor.intercept_tool_calls(response, session_id="s1")
    assert out.fabricated == []
    assert out.replaced == []
    # passthroughs incremented
    assert interceptor.memoizer.stats_for("s1").passthroughs == 1


# ---------------------------------------------------------------------------
# BDD: end-to-end "read → edit → read returns fresh" scenario
# ---------------------------------------------------------------------------


def test_bdd_read_edit_read_returns_fresh_content() -> None:
    """Spec scenario: 'read → edit → read returns fresh content'.
    The first read is a miss. The second is a hit (cached). The edit
    invalidates. The third read is a miss again. This is the
    correctness-critical test.
    """
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    args = {"path": "/repo/src/auth.py"}
    call_id = "call_1"

    # --- 1. First read: miss ---
    response = {"choices": [{"message": {"tool_calls": [
        {"id": call_id, "type": "function", "function": {
            "name": "file_read", "arguments": json.dumps(args),
        }},
    ]}}]}
    out1 = interceptor.intercept_tool_calls(response, session_id="s1")
    assert out1.fabricated == []  # miss
    # Upstream returns "old contents"; the caller records
    interceptor.memoizer.record("s1", "file_read", args, "old contents")

    # --- 2. Second read: hit (cached) ---
    out2 = interceptor.intercept_tool_calls(response, session_id="s1")
    assert len(out2.fabricated) == 1
    assert out2.fabricated[0].content == "old contents"

    # --- 3. Edit: invalidate ---
    interceptor.invalidate_for_write("s1", "file_edit", args)
    assert interceptor.memoizer.stats_for("s1").invalidations == 1

    # --- 4. Third read: miss again (cache flushed) ---
    out3 = interceptor.intercept_tool_calls(response, session_id="s1")
    assert out3.fabricated == []
    # New upstream value is recorded
    interceptor.memoizer.record("s1", "file_read", args, "new contents")

    # --- 5. Fourth read: hit with new content ---
    out4 = interceptor.intercept_tool_calls(response, session_id="s1")
    assert len(out4.fabricated) == 1
    assert out4.fabricated[0].content == "new contents"


# ---------------------------------------------------------------------------
# BDD: end-to-end "agent reads same file twice" scenario
# ---------------------------------------------------------------------------


def test_bdd_agent_reads_same_file_twice() -> None:
    """Spec scenario: 'agent reads same file twice -> second read served
    locally, upstream sees one fewer round trip'."""
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    args = {"path": "/repo/src/auth.py"}
    response = {"choices": [{"message": {"tool_calls": [
        {"id": "call_1", "type": "function", "function": {
            "name": "file_read", "arguments": json.dumps(args),
        }},
    ]}}]}

    # First read: miss
    out1 = interceptor.intercept_tool_calls(response, session_id="s1")
    assert out1.fabricated == []
    # Upstream returns; caller records
    interceptor.memoizer.record("s1", "file_read", args, "auth.py contents")

    # Second read: hit
    out2 = interceptor.intercept_tool_calls(response, session_id="s1")
    assert len(out2.fabricated) == 1
    assert out2.fabricated[0].content == "auth.py contents"

    # Stats
    s = interceptor.memoizer.stats_for("s1")
    assert s.misses == 1
    assert s.hits == 1
    assert s.entries == 1


# ---------------------------------------------------------------------------
# Mixed tool calls in one response
# ---------------------------------------------------------------------------


def test_interceptor_handles_mixed_tool_calls() -> None:
    """A response with both a cached tool and a non-cached tool must
    fabricate only the cached one and pass through the rest.
    """
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    cached_args = {"path": "/cached"}
    new_args = {"path": "/new"}
    interceptor.memoizer.maybe_memoize("s1", "file_read", cached_args)
    interceptor.memoizer.record("s1", "file_read", cached_args, "CACHED")

    response = {"choices": [{"message": {"tool_calls": [
        {"id": "t1", "type": "function", "function": {
            "name": "file_read", "arguments": json.dumps(cached_args),
        }},
        {"id": "t2", "type": "function", "function": {
            "name": "file_read", "arguments": json.dumps(new_args),
        }},
        {"id": "t3", "type": "function", "function": {
            "name": "shell_exec", "arguments": json.dumps({"cmd": "ls"}),
        }},
    ]}}]}

    out = interceptor.intercept_tool_calls(response, session_id="s1")
    # Only t1 fabricated
    assert len(out.fabricated) == 1
    assert out.fabricated[0].tool_call_id == "t1"
    assert out.fabricated[0].content == "CACHED"
    # The other two pass through
    assert len(out.passthrough_tool_calls) == 2
    passthrough_ids = {tc["id"] for tc in out.passthrough_tool_calls}
    assert passthrough_ids == {"t2", "t3"}


# ---------------------------------------------------------------------------
# Multiple tool calls in one response
# ---------------------------------------------------------------------------


def test_interceptor_handles_multiple_cached_tool_calls() -> None:
    """All cached tool calls in one response are fabricated."""
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    for i in range(3):
        args = {"path": f"/file_{i}"}
        interceptor.memoizer.maybe_memoize("s1", "file_read", args)
        interceptor.memoizer.record("s1", "file_read", args, f"contents {i}")

    response = {"choices": [{"message": {"tool_calls": [
        {"id": f"call_{i}", "type": "function", "function": {
            "name": "file_read", "arguments": json.dumps({"path": f"/file_{i}"}),
        }} for i in range(3)
    ]}}]}

    out = interceptor.intercept_tool_calls(response, session_id="s1")
    assert len(out.fabricated) == 3
    for i, fab in enumerate(out.fabricated):
        assert fab.tool_call_id == f"call_{i}"
        assert fab.content == f"contents {i}"


# ---------------------------------------------------------------------------
# Session isolation
# ---------------------------------------------------------------------------


def test_interceptor_sessions_are_isolated() -> None:
    """A cache hit in session s1 must NOT fabricate for session s2."""
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    args = {"path": "/a"}
    interceptor.memoizer.maybe_memoize("s1", "file_read", args)
    interceptor.memoizer.record("s1", "file_read", args, "in s1")

    response = {"choices": [{"message": {"tool_calls": [
        {"id": "call_1", "type": "function", "function": {
            "name": "file_read", "arguments": json.dumps(args),
        }},
    ]}}]}

    out = interceptor.intercept_tool_calls(response, session_id="s2")
    assert out.fabricated == []  # miss in s2
    assert out.passthrough_tool_calls  # passed through


# ---------------------------------------------------------------------------
# Regression guard: byte-identical to stored payload (no re-serialization)
# ---------------------------------------------------------------------------


def test_interceptor_fabricated_content_is_byte_identical() -> None:
    """The fabricated tool_result content must be byte-identical to
    the stored payload. No JSON round-trip, no whitespace normalization.
    This is the spec's 'pass-through re-serialization byte-identical'
    contract.
    """
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    args = {"path": "/a"}
    # Use a payload with non-canonical whitespace + unicode escapes
    payload = '{"a":  1,  "b":  2,   "c": "\\u00e9"}'  # deliberately ugly whitespace
    interceptor.memoizer.maybe_memoize("s1", "file_read", args)
    interceptor.memoizer.record("s1", "file_read", args, payload)

    response = {"choices": [{"message": {"tool_calls": [
        {"id": "call_1", "type": "function", "function": {
            "name": "file_read", "arguments": json.dumps(args),
        }},
    ]}}]}

    out = interceptor.intercept_tool_calls(response, session_id="s1")
    assert out.fabricated[0].content == payload, (
        "fabricated content must be byte-identical to stored payload"
    )


# ---------------------------------------------------------------------------
# OpenAI function-call format compatibility
# ---------------------------------------------------------------------------


def test_interceptor_handles_openai_function_call_format() -> None:
    """OpenAI's tool_calls format is the most common. The interceptor
    must recognize and fabricate correctly for it.
    """
    interceptor = MemoizeInterceptor(MemoizeConfig(enabled=True))
    args = {"path": "/a"}
    interceptor.memoizer.maybe_memoize("s1", "file_read", args)
    interceptor.memoizer.record("s1", "file_read", args, "CONTENTS")

    response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "file_read",
                                "arguments": json.dumps(args),
                            },
                        }
                    ]
                }
            }
        ]
    }
    out = interceptor.intercept_tool_calls(response, session_id="s1")
    assert len(out.fabricated) == 1
    assert out.fabricated[0].tool_call_id == "call_abc"
    assert out.fabricated[0].content == "CONTENTS"
