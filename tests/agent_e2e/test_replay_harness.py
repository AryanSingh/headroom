from __future__ import annotations

from pathlib import Path

import pytest

from .harness import ReplayHarness

FIXTURES = Path(__file__).with_name("fixtures")


@pytest.mark.timeout(30)
def test_captured_codex_resume_succeeds_after_real_proxy_restart() -> None:
    with ReplayHarness(FIXTURES) as harness:
        result = harness.run("codex-subscription-http-resume")

    assert result.proxy_restarts == 1
    assert len(result.upstream_requests) == 2
    resumed = result.upstream_requests[-1]
    assert resumed["body"]["store"] is False
    assert resumed["body"]["stream"] is True
    assert resumed["body"]["model"] == "gpt-5.4"
    assert resumed["body"]["input"]
    assert resumed["body"]["tools"]
    assert result.terminal_events == ["response.completed", "response.completed"]


@pytest.mark.timeout(30)
def test_claude_full_history_resume_succeeds_after_real_proxy_restart() -> None:
    with ReplayHarness(FIXTURES) as harness:
        result = harness.run("claude-messages-resume")

    assert result.proxy_restarts == 1
    assert len(result.upstream_requests) == 2
    resumed = result.upstream_requests[-1]
    assert resumed["headers"]["anthropic-version"] == "2023-06-01"
    assert "prompt-caching-2024-07-31" in resumed["headers"]["anthropic-beta"]
    assert len(resumed["body"]["messages"]) == 3
    assert result.terminal_events == ["message_stop", "message_stop"]


@pytest.mark.timeout(30)
def test_each_committed_executable_scenario_reaches_strict_upstream() -> None:
    for scenario_id in (
        "codex-protocol-matrix",
        "codex-subscription-http-resume",
        "codex-websocket-direct",
        "claude-messages-resume",
    ):
        with ReplayHarness(FIXTURES) as harness:
            result = harness.run(scenario_id)
        assert result.upstream_requests, scenario_id


@pytest.mark.timeout(30)
def test_subscription_websocket_sanitizes_every_response_create_frame() -> None:
    with ReplayHarness(FIXTURES) as harness:
        result = harness.run("codex-websocket-direct")

    assert len(result.upstream_requests) == 2
    for request in result.upstream_requests:
        assert request["body"]["store"] is False
        assert request["body"]["stream"] is True
    assert result.terminal_events == ["response.completed", "response.completed"]
