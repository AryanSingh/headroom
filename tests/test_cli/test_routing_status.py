from __future__ import annotations

import httpx
from click.testing import CliRunner

from cutctx.cli.main import main


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_routing_status_displays_live_safe_savings_decision(
    monkeypatch,
) -> None:
    requests: list[tuple[str, dict[str, str], float]] = []

    def fake_get(url: str, *, headers: dict[str, str], timeout: float) -> _Response:
        requests.append((url, headers, timeout))
        return _Response(
            {
                "experience_enabled": True,
                "enabled": True,
                "mode": "balanced",
                "preset": "codex-gpt54mini-high",
                "route_count": 10,
                "decision": {
                    "state": "applied",
                    "reason_title": "Lower-cost route applied",
                    "reason_explanation": "A compatible lower-cost route was selected.",
                },
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = CliRunner().invoke(
        main,
        [
            "routing",
            "status",
            "--proxy-url",
            "http://proxy.example:8787",
            "--admin-key",
            "test-admin-key",
        ],
        env={"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "1"},
    )

    assert result.exit_code == 0, result.output
    assert "Guided Safe Savings: ON" in result.output
    assert "Mode: balanced" in result.output
    assert "Current decision: applied" in result.output
    assert requests == [
        (
            "http://proxy.example:8787/v1/orchestration/safe-savings/status",
            {"x-cutctx-admin-key": "test-admin-key"},
            10.0,
        )
    ]


def test_routing_status_reports_connection_errors_without_exposing_admin_key(
    monkeypatch,
) -> None:
    def failing_get(*args, **kwargs) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", failing_get)

    result = CliRunner().invoke(
        main,
        ["routing", "status", "--admin-key", "test-admin-key"],
        env={"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "1"},
    )

    assert result.exit_code == 1
    assert "Could not retrieve Safe Savings status" in result.output
    assert "test-admin-key" not in result.output


def test_routing_status_rejects_an_invalid_proxy_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: _Response(["not", "an", "object"]),
    )

    result = CliRunner().invoke(
        main,
        ["routing", "status"],
        env={"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "1"},
    )

    assert result.exit_code == 1
    assert "Proxy returned an invalid Safe Savings status response" in result.output
