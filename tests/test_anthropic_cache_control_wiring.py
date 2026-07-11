# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""Coverage for actively engineering Anthropic prompt-cache breakpoints.

``AnthropicCacheOptimizer`` (cutctx/cache/anthropic.py) can insert
``cache_control`` blocks, but until now it was registered and never
invoked from any live request handler — every dollar of
``provider_prompt_cache`` savings came from a client (e.g. Claude Code)
setting up its own cache breakpoints; cutctx only ever measured it.

These tests drive real requests through
``AnthropicHandlerMixin.handle_anthropic_messages`` (mirroring the
harness in ``tests/test_anthropic_pre_upstream_backpressure.py``) with
a real ``AnthropicCacheOptimizer`` attached, and assert the body sent
upstream actually carries the breakpoints cutctx inserted.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace

import anyio

from cutctx.cache.anthropic import AnthropicCacheOptimizer
from cutctx.cache.base import CacheConfig
from cutctx.proxy.handlers.anthropic import AnthropicHandlerMixin
from tests.test_anthropic_pre_upstream_backpressure import (
    _build_request,
    _DummyAnthropicHandler,
    _tokenizer_patch,
)

_BIG_SYSTEM = "You are a helpful coding assistant. " * 200
_BIG_TOOLS = [
    {
        "name": f"tool_{i}",
        "description": "does something useful " * 50,
        "input_schema": {"type": "object"},
    }
    for i in range(10)
]


class _CacheCapturingHandler(_DummyAnthropicHandler):
    """Same dummy handler as the backpressure tests, with a real
    ``AnthropicCacheOptimizer`` attached and the upstream-bound body
    captured so tests can assert on what would actually be sent to
    Anthropic."""

    def __init__(
        self, *, cache_control_enabled: bool = True, session_turn_number: int = 1, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.anthropic_cache_optimizer = AnthropicCacheOptimizer(
            CacheConfig(enabled=cache_control_enabled)
        )
        self.sent_bodies: list[dict] = []
        # The shared dummy's session_tracker_store always reports turn 0
        # (a fresh SimpleNamespace per call). Override with a tracker
        # exposing ``session_turn_number`` so tests can simulate being
        # mid-session (turn_number >= 1) versus a session's first request.
        self.session_tracker_store = SimpleNamespace(
            compute_session_id=lambda *a, **k: "sess-1",
            get_or_create=lambda *a, **k: SimpleNamespace(
                _cached_token_count=0,
                _turn_number=session_turn_number,
                get_frozen_message_count=lambda: 0,
                get_last_original_messages=lambda: [],
                get_last_forwarded_messages=lambda: [],
                update_from_response=lambda *a, **k: None,
                record_request=lambda *a, **k: None,
            ),
        )

    async def _retry_request(self, method, url, headers, body, **kwargs):
        self.sent_bodies.append(copy.deepcopy(body))
        return await super()._retry_request(method, url, headers, body, **kwargs)


def _has_cache_control(value) -> bool:
    return AnthropicHandlerMixin._has_cache_control(value)


# --------------------------------------------------------------------------- #
# Unit-level: _apply_anthropic_cache_breakpoints / _has_cache_control         #
# --------------------------------------------------------------------------- #


def test_has_cache_control_detects_nested_client_breakpoints():
    assert not _has_cache_control({"role": "user", "content": "hi"})
    assert _has_cache_control(
        {"content": [{"type": "text", "text": "hi", "cache_control": {"type": "ephemeral"}}]}
    )
    assert _has_cache_control([{"name": "t", "cache_control": {"type": "ephemeral"}}])


def test_apply_cache_breakpoints_caches_large_system_and_tools():
    handler = _DummyAnthropicHandler()
    handler.anthropic_cache_optimizer = AnthropicCacheOptimizer(CacheConfig(enabled=True))
    body = {
        "system": _BIG_SYSTEM,
        "messages": [{"role": "user", "content": "hi"}],
        "tools": _BIG_TOOLS,
    }

    transforms = handler._apply_anthropic_cache_breakpoints(
        body, request_id="r1", model="claude-3-5-sonnet-latest", turn_number=1
    )

    assert transforms == ["anthropic_cache_control:system", "anthropic_cache_control:tools"]
    assert _has_cache_control(body["system"])
    assert "cache_control" in body["tools"][-1]
    # The messages array itself is never touched by this transform.
    assert body["messages"] == [{"role": "user", "content": "hi"}]


def test_apply_cache_breakpoints_skips_small_system_and_tools():
    handler = _DummyAnthropicHandler()
    handler.anthropic_cache_optimizer = AnthropicCacheOptimizer(CacheConfig(enabled=True))
    body = {
        "system": "short prompt",
        "messages": [{"role": "user", "content": "hi"}],
        "tools": [{"name": "t1"}],
    }

    transforms = handler._apply_anthropic_cache_breakpoints(
        body, request_id="r2", model="claude-3-5-sonnet-latest", turn_number=1
    )

    assert transforms == []
    assert body["system"] == "short prompt"
    assert body["tools"] == [{"name": "t1"}]


def test_apply_cache_breakpoints_skips_first_turn_of_session():
    """A cache write costs 1.25x with only future reads (0.1x) to offset
    it. A session that never sends a second request pays that premium for
    nothing, so the very first turn (turn_number=0) must never get a
    breakpoint even when system/tools are large enough to otherwise
    qualify."""
    handler = _DummyAnthropicHandler()
    handler.anthropic_cache_optimizer = AnthropicCacheOptimizer(CacheConfig(enabled=True))
    body = {
        "system": _BIG_SYSTEM,
        "messages": [{"role": "user", "content": "hi"}],
        "tools": _BIG_TOOLS,
    }

    transforms = handler._apply_anthropic_cache_breakpoints(
        body, request_id="r-first-turn", model="claude-3-5-sonnet-latest", turn_number=0
    )

    assert transforms == []
    assert body["system"] == _BIG_SYSTEM
    assert "cache_control" not in body["tools"][-1]


def test_apply_cache_breakpoints_respects_client_placed_breakpoints():
    """If the client already engineered its own cache_control (e.g. Claude
    Code caching its own stable turns), cutctx must not add more — doing
    so risks exceeding Anthropic's 4-breakpoint limit or disturbing a
    cache lineage that's already working."""
    handler = _DummyAnthropicHandler()
    handler.anthropic_cache_optimizer = AnthropicCacheOptimizer(CacheConfig(enabled=True))
    body = {
        "system": _BIG_SYSTEM,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hi", "cache_control": {"type": "ephemeral"}}
                ],
            }
        ],
        "tools": _BIG_TOOLS,
    }

    transforms = handler._apply_anthropic_cache_breakpoints(
        body, request_id="r3", model="claude-3-5-sonnet-latest", turn_number=1
    )

    assert transforms == []
    assert body["system"] == _BIG_SYSTEM


def test_apply_cache_breakpoints_noop_when_optimizer_disabled():
    handler = _DummyAnthropicHandler()
    handler.anthropic_cache_optimizer = AnthropicCacheOptimizer(CacheConfig(enabled=False))
    body = {
        "system": _BIG_SYSTEM,
        "messages": [{"role": "user", "content": "hi"}],
        "tools": _BIG_TOOLS,
    }

    transforms = handler._apply_anthropic_cache_breakpoints(
        body, request_id="r4", model="claude-3-5-sonnet-latest", turn_number=1
    )

    assert transforms == []
    assert body["system"] == _BIG_SYSTEM


def test_apply_cache_breakpoints_noop_when_optimizer_absent():
    """Handlers without ``anthropic_cache_optimizer`` set (e.g. this
    feature disabled entirely, no attribute wired) must no-op rather
    than raise."""
    handler = _DummyAnthropicHandler()
    body = {
        "system": _BIG_SYSTEM,
        "messages": [{"role": "user", "content": "hi"}],
        "tools": _BIG_TOOLS,
    }

    transforms = handler._apply_anthropic_cache_breakpoints(
        body, request_id="r5", model="claude-3-5-sonnet-latest", turn_number=1
    )

    assert transforms == []
    assert body["system"] == _BIG_SYSTEM


# --------------------------------------------------------------------------- #
# End-to-end: the body actually sent upstream carries the breakpoints         #
# --------------------------------------------------------------------------- #


def test_end_to_end_request_gets_cache_control_inserted_before_upstream():
    handler = _CacheCapturingHandler()
    request = _build_request(
        {
            "model": "claude-3-5-sonnet-latest",
            "system": _BIG_SYSTEM,
            "messages": [{"role": "user", "content": "hello"}],
            "tools": _BIG_TOOLS,
        },
        {"authorization": "Bearer sk-ant-api-test"},
    )

    with _tokenizer_patch():
        anyio.run(handler.handle_anthropic_messages, request)

    assert len(handler.sent_bodies) == 1
    sent = handler.sent_bodies[0]
    assert _has_cache_control(sent.get("system"))
    assert "cache_control" in sent["tools"][-1]


def test_end_to_end_request_unmodified_when_cache_control_disabled():
    handler = _CacheCapturingHandler(cache_control_enabled=False)
    request = _build_request(
        {
            "model": "claude-3-5-sonnet-latest",
            "system": _BIG_SYSTEM,
            "messages": [{"role": "user", "content": "hello"}],
            "tools": _BIG_TOOLS,
        },
        {"authorization": "Bearer sk-ant-api-test"},
    )

    with _tokenizer_patch():
        anyio.run(handler.handle_anthropic_messages, request)

    assert len(handler.sent_bodies) == 1
    sent = handler.sent_bodies[0]
    assert not _has_cache_control(sent.get("system"))
    assert "cache_control" not in sent["tools"][-1]


def test_end_to_end_first_turn_of_session_gets_no_cache_control():
    """Even with the optimizer enabled, a session's very first request
    must not pay the cache-write premium — there's no evidence yet that
    there will be a second request to read it back."""
    handler = _CacheCapturingHandler(session_turn_number=0)
    request = _build_request(
        {
            "model": "claude-3-5-sonnet-latest",
            "system": _BIG_SYSTEM,
            "messages": [{"role": "user", "content": "hello"}],
            "tools": _BIG_TOOLS,
        },
        {"authorization": "Bearer sk-ant-api-test"},
    )

    with _tokenizer_patch():
        anyio.run(handler.handle_anthropic_messages, request)

    assert len(handler.sent_bodies) == 1
    sent = handler.sent_bodies[0]
    assert not _has_cache_control(sent.get("system"))
    assert "cache_control" not in sent["tools"][-1]
