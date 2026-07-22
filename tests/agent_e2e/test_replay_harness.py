from __future__ import annotations

import json
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
def test_subscription_websocket_compresses_ordinary_output_and_preserves_opaque_resume() -> None:
    scenario_dir = FIXTURES / "codex-websocket-direct"
    original_first = json.loads((scenario_dir / "frame.json").read_text(encoding="utf-8"))[
        "response"
    ]
    original_resume = json.loads((scenario_dir / "resume-frame.json").read_text(encoding="utf-8"))[
        "response"
    ]

    with ReplayHarness(FIXTURES, optimize=True) as harness:
        result = harness.run("codex-websocket-direct")

    assert result.proxy_restarts == 1
    assert len(result.upstream_requests) == 2
    first = result.upstream_requests[0]["body"]
    resumed = result.upstream_requests[1]["body"]
    assert first["store"] is False
    assert first["stream"] is True
    assert first["model"] == original_first["model"]
    assert first["tools"] == original_first["tools"]
    assert first["input"][0]["call_id"] == original_first["input"][0]["call_id"]
    assert len(first["input"][0]["output"].split()) < len(
        original_first["input"][0]["output"].split()
    )
    assert resumed["store"] is False
    assert resumed["stream"] is True
    assert resumed["model"] == original_resume["model"]
    assert resumed["input"] == original_resume["input"]
    assert resumed["tools"] == original_resume["tools"]
    assert result.terminal_events == ["response.completed", "response.completed"]
