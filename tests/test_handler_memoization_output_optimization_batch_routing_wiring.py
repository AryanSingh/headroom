# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025-2026 Cutctx Labs
"""TDD coverage for a real gap: WS11 memoization, WS10 output
optimization, and WS13 batch routing all compute real decisions
inside ``handle_anthropic_messages`` (cutctx/proxy/handlers/anthropic.py),
but none of the three ever thread their result into the
``RequestOutcome`` that ``_record_request_outcome`` receives:

- WS11: ``record_tool_results_from_messages`` (cutctx/proxy/memoizer.py)
  returns ``None`` — it records tool results for future lookups but
  never reports how many *already-cached* results it saw in this same
  pass, so ``memoization_hits`` / ``memoization_tokens_saved`` on the
  outcome stay 0 forever.
- WS10: the output-optimizer decision's ``estimated_tokens_saved`` is
  stashed into a local ``request_savings_metadata["output_optimization"]``
  dict, but the outcome's ``savings_metadata`` is built from a
  *separate*, freshly extracted dict that never merges it in — and
  ``_build_savings_breakdown`` doesn't even look at
  ``savings_metadata["output_optimization"]`` (it only reads the typed
  ``output_optimization_tokens_saved`` field). The value is dropped.
- WS13: the batch router's "enqueued" branch returns a 202 response
  immediately with no ``RequestOutcome`` recorded at all, so batch
  routing savings are invisible to the dashboard / savings tracker.

These tests drive real requests through
``AnthropicHandlerMixin.handle_anthropic_messages`` (mirroring the
harness in ``tests/test_anthropic_pre_upstream_backpressure.py``) with
a real ``ToolMemoizer`` / ``OutputOptimizer`` / ``BatchRouter``
attached, and assert the recorded ``RequestOutcome`` actually carries
non-zero values for the three WS10/WS11/WS13 fields.
"""

from __future__ import annotations

import json

import anyio
import pytest

from cutctx.proxy.batch_router import BatchRouter, BatchRouterConfig
from cutctx.proxy.memoizer import MemoizeConfig, ToolMemoizer, record_tool_results_from_messages
from cutctx.proxy.outcome import _build_savings_breakdown
from cutctx.proxy.output_optimizer import OutputOptimizeConfig, OutputOptimizer
from tests.test_anthropic_pre_upstream_backpressure import (
    _build_request,
    _DummyAnthropicHandler,
    _tokenizer_patch,
)


class _CapturingAnthropicHandler(_DummyAnthropicHandler):
    """Same dummy handler as the backpressure tests, but records every
    ``RequestOutcome`` it is asked to emit instead of forwarding it to
    the real funnel, so tests can assert on the outcome fields."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.recorded_outcomes: list = []

    async def _record_request_outcome(self, outcome) -> None:  # noqa: ANN001
        self.recorded_outcomes.append(outcome)


# --------------------------------------------------------------------------- #
# WS11: memoizer.record_tool_results_from_messages must report hits/tokens    #
# --------------------------------------------------------------------------- #


def test_record_tool_results_from_messages_reports_hit_on_duplicate_call() -> None:
    """A second, identical (tool, args) call in the same message history
    is a memoization hit: the function must report it via its return
    value, not silently swallow it."""
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    session_id = "sess-memo-1"
    messages = [
        {"role": "user", "content": "read file a twice"},
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "file_read",
                    "input": {"path": "/a.txt"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": "FILE-CONTENT-AAAA-BBBB-CCCC-DDDD-EEEE",
                }
            ],
        },
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_2",
                    "name": "file_read",
                    "input": {"path": "/a.txt"},
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_2",
                    "content": "FILE-CONTENT-AAAA-BBBB-CCCC-DDDD-EEEE",
                }
            ],
        },
    ]

    result = record_tool_results_from_messages(memoizer, messages, session_id)

    assert result is not None, (
        "record_tool_results_from_messages returned None — it must return "
        "a (hits, tokens_saved) tuple so callers can attribute WS11 savings"
    )
    hits, tokens_saved = result
    assert hits == 1, f"expected exactly 1 hit (the duplicate call), got {hits}"
    assert tokens_saved > 0, "a hit with non-empty cached payload must report > 0 tokens saved"

    # The memoizer's own stats must also reflect the hit (maybe_memoize
    # was actually consulted, not just record()).
    stats = memoizer.stats_for(session_id)
    assert stats.hits == 1


def test_record_tool_results_from_messages_no_duplicates_reports_zero_hits() -> None:
    """Sanity check: distinct tool calls are never counted as hits."""
    memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    session_id = "sess-memo-2"
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "file_read",
                    "input": {"path": "/a.txt"},
                }
            ],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": "AAAA"}],
        },
    ]
    hits, tokens_saved = record_tool_results_from_messages(memoizer, messages, session_id)
    assert hits == 0
    assert tokens_saved == 0


# --------------------------------------------------------------------------- #
# Handler-level wiring: a full request must thread WS11 + WS10 into the       #
# RequestOutcome actually recorded.                                           #
# --------------------------------------------------------------------------- #


def _duplicate_tool_call_and_fix_request_body() -> dict:
    return {
        "model": "claude-3-5-sonnet-latest",
        "messages": [
            {"role": "user", "content": "read file a twice please"},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "file_read",
                        "input": {"path": "/a.txt"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_1",
                        "content": "FILE-CONTENT-AAAA-BBBB-CCCC-DDDD-EEEE",
                    }
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "call_2",
                        "name": "file_read",
                        "input": {"path": "/a.txt"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_2",
                        "content": "FILE-CONTENT-AAAA-BBBB-CCCC-DDDD-EEEE",
                    }
                ],
            },
            # Last user-authored text drives WS10 task-type detection:
            # "fix" -> code_edit -> diff-edit lever fires.
            {"role": "user", "content": "please fix this bug in my code"},
        ],
    }


def test_memoization_and_output_optimization_threaded_into_request_outcome() -> None:
    """Drive a real (non-streaming) /v1/messages request with a
    duplicate tool call (WS11 hit) and a code-edit task (WS10 diff-edit
    lever) through the handler, and assert the RequestOutcome that
    reaches ``_record_request_outcome`` carries non-zero
    memoization_hits / memoization_tokens_saved /
    output_optimization_tokens_saved.
    """
    handler = _CapturingAnthropicHandler()
    handler.memoizer = ToolMemoizer(MemoizeConfig(enabled=True))
    handler.output_optimizer = OutputOptimizer(
        OutputOptimizeConfig(enabled=True, enable_diff_edit=True)
    )

    request = _build_request(
        _duplicate_tool_call_and_fix_request_body(),
        {"authorization": "Bearer sk-ant-api-test"},
    )

    with _tokenizer_patch():
        anyio.run(handler.handle_anthropic_messages, request)

    assert handler.recorded_outcomes, "handler never recorded a RequestOutcome"
    outcome = handler.recorded_outcomes[-1]

    assert outcome.memoization_hits > 0, (
        "the duplicate file_read call should have registered as a WS11 "
        "memoization hit on the recorded outcome"
    )
    assert outcome.memoization_tokens_saved > 0

    assert outcome.output_optimization_tokens_saved > 0, (
        "the WS10 diff-edit lever's estimated_tokens_saved must reach "
        "the recorded RequestOutcome, not just a local dict that's "
        "never merged into the outcome's savings_metadata"
    )

    # And the funnel's breakdown must actually surface both sources —
    # this is the observable contract the dashboard depends on.
    tokens, _usd, _breakdown = _build_savings_breakdown(outcome)
    from cutctx.savings import SavingsSource

    assert SavingsSource.MEMOIZATION.value in tokens
    assert SavingsSource.OUTPUT_OPTIMIZATION.value in tokens


# --------------------------------------------------------------------------- #
# WS13: an enqueued batch-routing decision must record a RequestOutcome too.  #
# --------------------------------------------------------------------------- #


def test_batch_routing_without_executor_forwards_without_claiming_savings() -> None:
    """Eligible batch traffic must complete synchronously until executable."""
    handler = _CapturingAnthropicHandler()
    handler.batch_router = BatchRouter(BatchRouterConfig(enabled=True))

    request = _build_request(
        {
            # A model litellm's pricing table actually resolves, so
            # ``value_tokens_usd`` doesn't silently fall back to 0.0.
            "model": "claude-sonnet-4-5",
            "messages": [{"role": "user", "content": "hello " * 50}],
        },
        {
            "authorization": "Bearer sk-ant-api-test",
            "x-cutctx-batch": "allow",
        },
    )

    with _tokenizer_patch():
        response = anyio.run(handler.handle_anthropic_messages, request)

    assert response.status_code == 200
    assert handler.recorded_outcomes
    outcome = handler.recorded_outcomes[-1]
    assert outcome.batch_routing_tokens_saved == 0
    assert outcome.batch_routing_usd_saved == 0

    tokens, usd, _breakdown = _build_savings_breakdown(outcome)
    from cutctx.savings import SavingsSource

    assert SavingsSource.BATCH_ROUTING.value not in tokens
    assert SavingsSource.BATCH_ROUTING.value not in usd
