"""Regression test for a missing `error_category` field on `SessionEvent`.

`SessionEvent` is constructed with `error_category=...` at four call sites —
claude.py:236, codex.py:190/257, gemini.py:285, cursor.py:169/188 — whenever a
plugin detects error content in a transcript. The dataclass previously had no
such field, so every one of those calls raised `TypeError` at runtime. Nothing
catches it: `aggregate_projects()` and `cli/learn.py` call `scan_project()`
with no try/except, so `cutctx learn` crashed outright the moment it processed
a transcript containing real error content — for the exact workload it exists
to handle ("mine failed sessions").
"""

from __future__ import annotations

from cutctx.learn.models import ErrorCategory, SessionEvent


def test_session_event_accepts_error_category():
    event = SessionEvent(
        type="error",
        msg_index=3,
        text="Traceback (most recent call last): ...",
        error_category=ErrorCategory.RUNTIME_ERROR,
    )
    assert event.error_category == ErrorCategory.RUNTIME_ERROR
    assert event.type == "error"
    assert event.msg_index == 3


def test_session_event_error_category_defaults_to_unknown():
    """Every other SessionEvent field is optional with a sensible default;
    error_category must be too, since only the four error-detecting call
    sites pass it explicitly — every other constructor call in the codebase
    (tool_call, user_message, agent_summary events) omits it."""
    event = SessionEvent(type="user_message", msg_index=0, text="hi")
    assert event.error_category == ErrorCategory.UNKNOWN
