# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD tests for the WS10 output-side optimization.

Per artifacts/savings-moat-expansion-specs.md WS10:
- Flag: CUTCTX_OUTPUT_OPT=1 (master) + sub-flags
  - CUTCTX_OUTPUT_DIFF_EDITS: lever 1
  - CUTCTX_OUTPUT_MAXTOK_AUTO: lever 2
  - CUTCTX_OUTPUT_STYLE: lever 3
- Lever 1 (diff-edit steering): when task type is CODE/EDIT, append
  a system-suffix instruction to emit minimal patches. Never modify
  tool schemas. Only on CODE/EDIT tasks.
- Lever 2 (max_tokens auto-tuning): per-(task-type, agent) response
  length quantiles. If client sent no max_tokens or value > 4x p95,
  cap it. On max_tokens-truncated finish, record a miss and raise
  the cap.
- Lever 3 (style shaping): for SEARCH/LIST/SUMMARIZE, inject terse
  instruction. Skip for CODE/DEBUG.
- Safety rail: any guard failure or client retry within same session
  disables levers 1/3 for that session (in-memory circuit breaker).
- Attribution: measured savings = (predicted baseline output tokens
  from quantile model) - actual; recorded as OUTPUT_OPTIMIZATION
  source. Label as estimated in the report.
- Default-off (the spec's flag-off golden contract).

TDD: written first, then cutctx/proxy/output_optimizer.py is made
to satisfy them.
"""

from __future__ import annotations

import pytest

from cutctx.proxy.output_optimizer import (
    DEFAULT_MAXTOK_AUTO_MULTIPLIER,
    DEFAULT_OUTPUT_QUANTILE_PERCENTILE,
    OutputOptimizeConfig,
    OutputOptimizer,
    detect_task_type,
    should_inject_diff_edit,
    should_inject_style,
)

# ---------------------------------------------------------------------------
# Flag-off golden contract — the spec's permanent test
# ---------------------------------------------------------------------------


def test_default_config_is_all_off() -> None:
    """The default OutputOptimizeConfig must be all-off."""
    cfg = OutputOptimizeConfig()
    assert cfg.enabled is False
    assert cfg.enable_diff_edit is False
    assert cfg.enable_maxtok_auto is False
    assert cfg.enable_style is False


def test_master_flag_controls_all_three_levers() -> None:
    """When the master flag is off, all sub-flags are ignored."""
    cfg = OutputOptimizeConfig(
        enabled=False,
        enable_diff_edit=True,  # would otherwise fire
        enable_maxtok_auto=True,
        enable_style=True,
    )
    optimizer = OutputOptimizer(cfg)
    decision = optimizer.optimize(
        request_body={
            "model": "claude-3-opus",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": "fix the bug in auth.py"}],
        },
        session_id="s1",
    )
    # No action taken
    assert decision.actions_applied == []
    # No savings
    assert decision.estimated_tokens_saved == 0


def test_flag_off_passes_request_through_unchanged() -> None:
    """The request body is returned BYTE-IDENTICAL with flag off."""
    cfg = OutputOptimizeConfig()
    optimizer = OutputOptimizer(cfg)
    body = {
        "model": "claude-3-opus",
        "max_tokens": 4096,
        "messages": [
            {"role": "system", "content": "You are a coding agent."},
            {"role": "user", "content": "fix the bug"},
        ],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    assert decision.request_body is body  # same object reference
    assert decision.actions_applied == []


# ---------------------------------------------------------------------------
# Task-type detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "user_msg,expected",
    [
        ("fix the bug in auth.py", "code_edit"),
        ("refactor this function", "code_edit"),
        ("search for 'foo' in src/", "search"),
        ("list all .py files", "list"),
        ("summarize this doc", "summarize"),
        ("debug the failing test", "debug"),
        ("what is the meaning of life", "general"),
    ],
)
def test_detect_task_type_basic(user_msg: str, expected: str) -> None:
    assert detect_task_type(user_msg) == expected


# ---------------------------------------------------------------------------
# Lever 1: diff-edit steering
# ---------------------------------------------------------------------------


def test_diff_edit_only_fires_for_code_edit() -> None:
    """The diff-edit instruction only fires for CODE/EDIT task types."""
    assert should_inject_diff_edit("code_edit") is True
    assert should_inject_diff_edit("debug") is False
    assert should_inject_diff_edit("search") is False
    assert should_inject_diff_edit("summarize") is False
    assert should_inject_diff_edit("list") is False
    assert should_inject_diff_edit("general") is False


def test_diff_edit_appends_to_last_system_message() -> None:
    """The diff-edit instruction is appended to the LAST system
    message (or a new system message if none exists). It is APPENDED,
    not prepended — existing system prompt is preserved."""
    cfg = OutputOptimizeConfig(enabled=True, enable_diff_edit=True)
    optimizer = OutputOptimizer(cfg)
    body = {
        "model": "claude-3-opus",
        "messages": [
            {"role": "system", "content": "You are a coding agent."},
            {"role": "user", "content": "fix the bug in auth.py"},
        ],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    assert "diff_edit" in decision.actions_applied
    # The last system message's content was modified (existing + new suffix)
    last_system = decision.request_body["messages"][0]
    assert last_system["content"].startswith("You are a coding agent.")
    assert "minimal" in last_system["content"].lower() or "patch" in last_system["content"].lower()


def test_diff_edit_creates_system_message_if_none() -> None:
    """If there is no system message, the diff-edit instruction is
    prepended as a new system message."""
    cfg = OutputOptimizeConfig(enabled=True, enable_diff_edit=True)
    optimizer = OutputOptimizer(cfg)
    body = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "fix the bug"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    assert "diff_edit" in decision.actions_applied
    assert decision.request_body["messages"][0]["role"] == "system"


def test_diff_edit_never_modifies_tool_schemas() -> None:
    """Per spec: 'Never modify tool schemas.'"""
    cfg = OutputOptimizeConfig(enabled=True, enable_diff_edit=True)
    optimizer = OutputOptimizer(cfg)
    body = {
        "model": "claude-3-opus",
        "tools": [
            {
                "name": "file_edit",
                "description": "edit a file",
                "input_schema": {"type": "object", "properties": {}},
            }
        ],
        "messages": [{"role": "user", "content": "edit the file"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    # The tools are unchanged
    assert decision.request_body["tools"] == body["tools"]


# ---------------------------------------------------------------------------
# Lever 2: max_tokens auto-tuning
# ---------------------------------------------------------------------------


def test_maxtok_auto_no_cap_when_client_set_explicit() -> None:
    """If the client sent a specific max_tokens, the optimizer does
    not cap it (the spec: 'client sent explicit max_tokens < cap ->
    untouched'). This test asserts the cap does NOT shrink the
    client-set value below the client's request."""
    cfg = OutputOptimizeConfig(enabled=True, enable_maxtok_auto=True)
    optimizer = OutputOptimizer(cfg)
    body = {
        "model": "claude-3-opus",
        "max_tokens": 1000,  # client set a tight limit
        "messages": [{"role": "user", "content": "test"}],
    }
    # First call: no history, no cap
    decision = optimizer.optimize(request_body=body, session_id="s1")
    # No cap applied (no history yet)
    assert decision.actions_applied == [] or "maxtok_cap" not in decision.actions_applied


def test_maxtok_auto_caps_when_no_client_max_tokens() -> None:
    """If the client did not set max_tokens, the optimizer sets a
    default cap based on the model's first request."""
    cfg = OutputOptimizeConfig(enabled=True, enable_maxtok_auto=True)
    optimizer = OutputOptimizer(cfg)
    body = {
        "model": "claude-3-opus",
        # no max_tokens
        "messages": [{"role": "user", "content": "test"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    # A cap was applied
    assert "maxtok_cap" in decision.actions_applied
    assert decision.request_body.get("max_tokens") is not None


def test_maxtok_auto_records_outcomes_for_quantiles() -> None:
    """The optimizer maintains per-(task-type) response-length quantiles
    and uses them to cap subsequent requests."""
    cfg = OutputOptimizeConfig(enabled=True, enable_maxtok_auto=True)
    optimizer = OutputOptimizer(cfg)

    # Simulate 3 prior requests with known output token counts
    for tokens in [100, 150, 200]:
        optimizer.record_outcome(
            session_id="s1",
            task_type="general",
            output_tokens=tokens,
            finish_reason="end_turn",
        )

    # Now a new request without max_tokens
    body = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "test"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    # A cap was applied based on the p95 + 25% headroom
    assert "maxtok_cap" in decision.actions_applied
    cap = decision.request_body.get("max_tokens")
    assert cap is not None
    # p95 of {100, 150, 200} is ~195, +25% = ~244
    # Cap should be in that ballpark
    assert 200 < cap < 500


def test_maxtok_auto_records_truncation_as_miss() -> None:
    """If the upstream finish_reason is max_tokens (truncated), the
    optimizer records this as a 'miss' and raises the cap class."""
    cfg = OutputOptimizeConfig(enabled=True, enable_maxtok_auto=True)
    optimizer = OutputOptimizer(cfg)

    # First request: no cap
    body1 = {"model": "claude-3-opus", "messages": [{"role": "user", "content": "x"}]}
    optimizer.optimize(request_body=body1, session_id="s1")
    # Apply a low cap; the upstream truncates
    cap1 = 50
    optimizer.record_outcome(
        session_id="s1",
        task_type="general",
        output_tokens=50,
        finish_reason="max_tokens",  # truncated
    )
    # Next request: the cap should be raised
    body2 = {"model": "claude-3-opus", "messages": [{"role": "user", "content": "x"}]}
    decision = optimizer.optimize(request_body=body2, session_id="s1")
    cap2 = decision.request_body.get("max_tokens", 0)
    assert cap2 > cap1, "cap should rise after a max_tokens truncation"


# ---------------------------------------------------------------------------
# Lever 3: style shaping
# ---------------------------------------------------------------------------


def test_style_only_fires_for_search_list_summarize() -> None:
    """Style shaping fires for SEARCH / LIST / SUMMARIZE task types.
    It explicitly does NOT fire for CODE / DEBUG.
    """
    assert should_inject_style("search") is True
    assert should_inject_style("list") is True
    assert should_inject_style("summarize") is True
    assert should_inject_style("code_edit") is False
    assert should_inject_style("debug") is False
    assert should_inject_style("general") is False


def test_style_appends_terse_instruction() -> None:
    """When style shaping fires, a terse-output instruction is appended
    to the last system message (or a new one)."""
    cfg = OutputOptimizeConfig(enabled=True, enable_style=True)
    optimizer = OutputOptimizer(cfg)
    body = {
        "model": "claude-3-opus",
        "messages": [
            {"role": "system", "content": "You are a search agent."},
            {"role": "user", "content": "search for 'TODO' in src/"},
        ],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    assert "style_terse" in decision.actions_applied
    last_system = decision.request_body["messages"][0]
    assert last_system["content"].startswith("You are a search agent.")
    assert "terse" in last_system["content"].lower() or "concise" in last_system["content"].lower()


# ---------------------------------------------------------------------------
# Safety rail: guard failure / retry disables levers 1/3
# ---------------------------------------------------------------------------


def test_safety_rail_disables_levers_1_and_3_on_guard_failure() -> None:
    """If a guard failure is recorded, levers 1 (diff_edit) and 3
    (style) are disabled for the session. Lever 2 (max_tokens auto)
    is NOT affected — it has no impact on quality.
    """
    cfg = OutputOptimizeConfig(
        enabled=True, enable_diff_edit=True, enable_maxtok_auto=True, enable_style=True
    )
    optimizer = OutputOptimizer(cfg)
    # Record a guard failure
    optimizer.record_guard_failure(session_id="s1")

    # Subsequent request: diff_edit and style should NOT fire, but
    # max_tokens auto should still work.
    body = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "fix the bug"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    assert "diff_edit" not in decision.actions_applied
    assert "style_terse" not in decision.actions_applied


def test_safety_rail_disables_levers_on_client_retry() -> None:
    """If a client retry is recorded (same session), levers 1 and 3
    are disabled for that session."""
    cfg = OutputOptimizeConfig(enabled=True, enable_diff_edit=True, enable_style=True)
    optimizer = OutputOptimizer(cfg)
    optimizer.record_client_retry(session_id="s1")

    body = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "fix the bug"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    assert "diff_edit" not in decision.actions_applied
    assert "style_terse" not in decision.actions_applied


def test_safety_rail_is_per_session() -> None:
    """A safety-rail trip in session s1 does NOT affect session s2."""
    cfg = OutputOptimizeConfig(enabled=True, enable_diff_edit=True, enable_style=True)
    optimizer = OutputOptimizer(cfg)
    optimizer.record_guard_failure(session_id="s1")

    # Session s2: not affected. Use a search query so that BOTH
    # diff_edit (no, search is not code_edit) and style_terse fire.
    body = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "search for 'TODO' in src/"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s2")
    # Safety rail is per-session: s2 is not affected.
    assert decision.actions_applied == ["style_terse"], (
        f"s2 should fire style_terse (search task type); got {decision.actions_applied}"
    )
    # And the safety-rail stats for s2 are clean
    s2_stats = optimizer.stats_for("s2")
    assert s2_stats.safety_rail_active is False


# ---------------------------------------------------------------------------
# Multi-lever composition
# ---------------------------------------------------------------------------


def test_all_three_levers_can_fire_in_one_request() -> None:
    """Lever 1 (diff_edit) and lever 3 (style_terse) are mutually
    exclusive based on task type (code_edit vs search). But lever 2
    (max_tokens) can fire alongside either. Test that max_tokens
    auto can fire alongside diff_edit."""
    cfg = OutputOptimizeConfig(
        enabled=True, enable_diff_edit=True, enable_maxtok_auto=True, enable_style=True
    )
    optimizer = OutputOptimizer(cfg)
    # Establish a quantile for code_edit
    for tokens in [100, 200, 300]:
        optimizer.record_outcome(
            session_id="s1",
            task_type="code_edit",
            output_tokens=tokens,
            finish_reason="end_turn",
        )
    body = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "fix the bug"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    # diff_edit fires (task type is code_edit)
    assert "diff_edit" in decision.actions_applied
    # maxtok_cap fires (no client max_tokens)
    assert "maxtok_cap" in decision.actions_applied
    # style does NOT fire (task type is code_edit, not search/list/summarize)
    assert "style_terse" not in decision.actions_applied


# ---------------------------------------------------------------------------
# Regression guard: flag-off path is byte-identical
# ---------------------------------------------------------------------------


def test_flag_off_does_not_grow_state() -> None:
    """With flag off, hammer the optimizer with many calls; nothing
    should accumulate in the session quantiles or safety-rail
    circuit breakers."""
    cfg = OutputOptimizeConfig()
    optimizer = OutputOptimizer(cfg)
    for i in range(50):
        body = {
            "model": "claude-3-opus",
            "messages": [{"role": "user", "content": f"call {i}"}],
        }
        optimizer.optimize(request_body=body, session_id=f"s{i}")
        optimizer.record_outcome(
            session_id=f"s{i}",
            task_type="general",
            output_tokens=100,
            finish_reason="end_turn",
        )
        optimizer.record_guard_failure(session_id=f"s{i}")
        optimizer.record_client_retry(session_id=f"s{i}")
    # No session should have any recorded data
    for i in range(50):
        s = optimizer.stats_for(f"s{i}")
        assert s.calls == 0
        assert s.guard_failures == 0
        assert s.client_retries == 0
        assert s.quantile_count == 0


# ---------------------------------------------------------------------------
# Attribution: estimated savings reported
# ---------------------------------------------------------------------------


def test_estimated_savings_is_nonnegative() -> None:
    """The estimated_tokens_saved is the sum of avoided output tokens
    across all levers. Always >= 0 (the optimizer never invents savings)."""
    cfg = OutputOptimizeConfig(enabled=True, enable_diff_edit=True, enable_maxtok_auto=True)
    optimizer = OutputOptimizer(cfg)
    body = {
        "model": "claude-3-opus",
        "messages": [{"role": "user", "content": "fix the bug"}],
    }
    decision = optimizer.optimize(request_body=body, session_id="s1")
    assert decision.estimated_tokens_saved >= 0


# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------


def test_maxtok_default_multiplier_is_4x() -> None:
    """Per spec: 'value > 4x p95 -> cap it.'"""
    assert DEFAULT_MAXTOK_AUTO_MULTIPLIER == 4


def test_output_quantile_default_percentile_is_95() -> None:
    """Per spec: 'p95 + 25% headroom.' 95th percentile."""
    assert DEFAULT_OUTPUT_QUANTILE_PERCENTILE == 95
