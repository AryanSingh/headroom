"""TDD tests for OpenAI chat handler memoization and output optimization.

Tests that the OpenAI chat handler correctly:
1. Captures memoization_hits and memoization_tokens_saved from
   record_tool_results_from_messages() and threads them into RequestOutcome
2. Calls output_optimizer.optimize(request_body=..., session_id=...) with the
   correct API and extracts actions_applied + estimated_tokens_saved.

Both are real bugs that were fixed in anthropic.py and need to be ported to chat.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from cutctx.backends.base import BackendResponse
from cutctx.proxy.memoizer import ToolMemoizer
from cutctx.proxy.output_optimizer import (
    OutputOptimizeConfig,
    OutputOptimizeDecision,
    OutputOptimizer,
)
from cutctx.proxy.server import ProxyConfig, create_app


class _RecordingMetricsRecorder:
    """Stub metrics recorder that captures recorded outcomes."""

    def __init__(self) -> None:
        self.outcomes: list = []

    async def record(self, outcome) -> None:
        self.outcomes.append(outcome)


def _make_config_with_memoizer_and_optimizer(
    memoizer_enabled: bool = True,
    optimizer_enabled: bool = True,
) -> ProxyConfig:
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        backend="anyllm",
        anyllm_provider="openai",
    )
    # Inject memoizer and output optimizer configs if enabled
    if memoizer_enabled:
        config.memoizer_enabled = True
    if optimizer_enabled:
        config.output_optimizer_enabled = True
        config.output_optimizer_config = OutputOptimizeConfig(
            enabled=True,
            enable_diff_edit=True,
            enable_style=True,
        )
    return config


def _make_mock_backend(response_body: dict, status_code: int = 200) -> MagicMock:
    backend = MagicMock()
    backend.name = "anyllm-openai"
    backend.send_openai_message = AsyncMock(
        return_value=BackendResponse(
            body=response_body,
            status_code=status_code,
            headers={"content-type": "application/json"},
        )
    )
    return backend


def _install_memoizer(client: TestClient) -> ToolMemoizer:
    """Install a memoizer on the proxy and return it for inspection."""
    proxy = client.app.state.proxy
    memoizer = ToolMemoizer()
    proxy.memoizer = memoizer
    return memoizer


def _install_output_optimizer(client: TestClient) -> OutputOptimizer:
    """Install an output optimizer on the proxy."""
    proxy = client.app.state.proxy
    config = OutputOptimizeConfig(
        enabled=True,
        enable_diff_edit=True,
        enable_style=True,
    )
    optimizer = OutputOptimizer(config)
    proxy.output_optimizer = optimizer
    return optimizer


def _install_metrics_recorder(client: TestClient) -> _RecordingMetricsRecorder:
    """Replace the metrics recorder with a stub that captures outcomes."""
    proxy = client.app.state.proxy
    recorder = _RecordingMetricsRecorder()
    # Mock the _record_request_outcome method to call our recorder
    original_record = proxy._record_request_outcome
    async def stub_record(outcome):
        recorder.outcomes.append(outcome)
        # Don't call original to avoid database writes
    proxy._record_request_outcome = stub_record
    return recorder


@pytest.mark.asyncio
def test_openai_chat_captures_memoization_hits_and_tokens_saved():
    """The OpenAI chat handler captures memoization hits/tokens from record_tool_results_from_messages()."""
    from cutctx.proxy.memoizer import MemoizeConfig

    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        backend="anyllm",
        anyllm_provider="openai",
    )

    response_body = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Done"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 20,
            "total_tokens": 1020,
        },
    }

    mock_backend = _make_mock_backend(response_body)
    with patch("cutctx.proxy.server.AnyLLMBackend", return_value=mock_backend):
        app = create_app(config)
        with TestClient(app) as client:
            # Install memoizer with enabled=True and search tool allowlisted
            proxy = client.app.state.proxy
            memoizer = ToolMemoizer(
                config=MemoizeConfig(
                    enabled=True,
                    allowlist=frozenset(["search"]),
                )
            )
            proxy.memoizer = memoizer
            metrics_recorder = _install_metrics_recorder(client)

            # Make request with duplicate tool results in message history
            # The record_tool_results_from_messages function will:
            # 1. Process first search result (call-1) -> MISS (not in cache yet) -> record it
            # 2. Process second search result (call-2) -> HIT (now in cache) -> increment hits
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "user", "content": "search for foo twice"},
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "search",
                                        "arguments": '{"query": "foo"}',
                                    },
                                },
                                {
                                    "id": "call-2",
                                    "type": "function",
                                    "function": {
                                        "name": "search",
                                        "arguments": '{"query": "foo"}',
                                    },
                                }
                            ],
                        },
                        {
                            "role": "tool",
                            "tool_call_id": "call-1",
                            "content": '[{"title": "foo result 1"}]',
                        },
                        {
                            "role": "tool",
                            "tool_call_id": "call-2",
                            "content": '[{"title": "foo result 1"}]',
                        },
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "search",
                                "description": "Search for documents",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"}
                                    },
                                },
                            },
                        }
                    ],
                },
                headers={"Authorization": "Bearer test-key"},
            )

    assert resp.status_code == 200, resp.text
    assert len(metrics_recorder.outcomes) > 0

    # Find the outcome
    outcome = metrics_recorder.outcomes[-1]
    # Should have captured memoization hits and tokens saved
    assert outcome.memoization_hits > 0, (
        f"Expected memoization_hits > 0 but got {outcome.memoization_hits}. "
        "Bug: record_tool_results_from_messages() return value was discarded."
    )
    assert outcome.memoization_tokens_saved > 0, (
        f"Expected memoization_tokens_saved > 0 but got {outcome.memoization_tokens_saved}. "
        "Bug: memoization_tokens_saved not captured."
    )


@pytest.mark.asyncio
def test_openai_chat_output_optimizer_uses_correct_api():
    """The OpenAI chat handler uses the correct output_optimizer.optimize() API."""
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        backend="anyllm",
        anyllm_provider="openai",
    )

    response_body = {
        "id": "chatcmpl-2",
        "object": "chat.completion",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Fixed the bug in auth.py"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1500,
            "completion_tokens": 50,
            "total_tokens": 1550,
        },
    }

    mock_backend = _make_mock_backend(response_body)
    with patch("cutctx.proxy.server.AnyLLMBackend", return_value=mock_backend):
        app = create_app(config)
        with TestClient(app) as client:
            # Install output optimizer
            optimizer = _install_output_optimizer(client)
            metrics_recorder = _install_metrics_recorder(client)

            # Make request with a code_edit task to trigger output optimization
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "user", "content": "fix the bug in auth.py"}
                    ],
                },
                headers={"Authorization": "Bearer test-key"},
            )

    assert resp.status_code == 200, resp.text
    assert len(metrics_recorder.outcomes) > 0

    outcome = metrics_recorder.outcomes[-1]
    # Should have applied output optimization (diff_edit lever for code_edit task)
    assert outcome.output_optimization_tokens_saved > 0, (
        f"Expected output_optimization_tokens_saved > 0 but got {outcome.output_optimization_tokens_saved}. "
        "Bug: output_optimizer.optimize() call uses wrong API (messages= instead of request_body=) "
        "and/or wrong field access (.action instead of .actions_applied)."
    )


@pytest.mark.asyncio
def test_openai_chat_handles_output_optimizer_correctly_with_no_actions():
    """When output optimizer finds no actions to apply, tokens_saved should be 0."""
    config = ProxyConfig(
        optimize=False,
        cache_enabled=False,
        rate_limit_enabled=False,
        backend="anyllm",
        anyllm_provider="openai",
    )

    response_body = {
        "id": "chatcmpl-3",
        "object": "chat.completion",
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Result"},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 500,
            "completion_tokens": 20,
            "total_tokens": 520,
        },
    }

    mock_backend = _make_mock_backend(response_body)
    with patch("cutctx.proxy.server.AnyLLMBackend", return_value=mock_backend):
        app = create_app(config)
        with TestClient(app) as client:
            optimizer = _install_output_optimizer(client)
            metrics_recorder = _install_metrics_recorder(client)

            # Make request with a non-matching task (no optimization)
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "user", "content": "what is 2+2?"}
                    ],
                },
                headers={"Authorization": "Bearer test-key"},
            )

    assert resp.status_code == 200, resp.text
    outcome = metrics_recorder.outcomes[-1]
    # Should be 0 since no actions applied
    assert outcome.output_optimization_tokens_saved == 0
