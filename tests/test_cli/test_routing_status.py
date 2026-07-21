from __future__ import annotations

from typing import Any

import httpx
from click.testing import CliRunner

from cutctx.cli.main import main


class _Response:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
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
                "route_count": 1,
                "routes": [
                    {
                        "source_model": "gpt-5.6-sol",
                        "low_target_model": "gpt-5.4-mini",
                        "medium_target_model": "gpt-5.6-luna",
                        "low_target_transport_safe": True,
                        "medium_target_transport_safe": False,
                    }
                ],
                "decision": {
                    "requested_model": "gpt-5.6-sol",
                    "effective_model": "gpt-5.4-mini",
                    "applied": True,
                    "title": "Safe route applied",
                    "explanation": "A compatible lower-cost route was selected.",
                    "confidence": 0.9,
                    "signals": ["explicit_low_complexity"],
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
    assert "gpt-5.6-sol -> gpt-5.4-mini (low, transport-safe)" in result.output
    assert "gpt-5.6-sol -> gpt-5.6-luna (medium, restricted)" in result.output
    assert "Recent decision: applied gpt-5.6-sol -> gpt-5.4-mini" in result.output
    assert "Reason: Safe route applied" in result.output
    assert "Confidence: 0.90" in result.output
    assert "Signals: explicit_low_complexity" in result.output
    assert requests == [
        (
            "http://proxy.example:8787/v1/orchestration/safe-savings/status",
            {"x-cutctx-admin-key": "test-admin-key"},
            10.0,
        )
    ]


def test_routing_status_reports_off_without_inventing_routes(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: _Response(
            {
                "experience_enabled": True,
                "enabled": False,
                "mode": "off",
                "preset": None,
                "route_count": 0,
                "routes": [],
                "decision": None,
            }
        ),
    )

    result = CliRunner().invoke(
        main,
        ["routing", "status"],
        env={"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "1"},
    )

    assert result.exit_code == 0, result.output
    assert "Guided Safe Savings: OFF" in result.output
    assert "Requests retain the originally requested model." in result.output
    assert "Eligible exact routes:" not in result.output


def test_routing_status_uses_managed_loopback_admin_key_file(monkeypatch, tmp_path) -> None:
    requests: list[dict[str, str]] = []
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    key_file = tmp_path / "admin_key.txt"
    key_file.write_text("managed-admin-key\n")
    monkeypatch.setattr(
        "cutctx.cli.routing._default_admin_key_path",
        lambda: key_file,
    )

    def fake_get(_url: str, *, headers: dict[str, str], timeout: float) -> _Response:
        requests.append(headers)
        return _Response(
            {
                "enabled": False,
                "mode": "off",
                "route_count": 0,
                "routes": [],
                "decision": None,
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = CliRunner().invoke(
        main,
        ["routing", "status", "--proxy-url", "http://127.0.0.1:8787"],
        env={"CUTCTX_SAFE_SAVINGS_EXPERIENCE": "1"},
    )

    assert result.exit_code == 0, result.output
    assert requests == [{"x-cutctx-admin-key": "managed-admin-key"}]


def test_routing_status_respects_relocated_workspace_admin_key(monkeypatch, tmp_path) -> None:
    requests: list[dict[str, str]] = []
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    workspace = tmp_path / "managed-workspace"
    workspace.mkdir()
    (workspace / "admin_key.txt").write_text("relocated-admin-key\n")

    def fake_get(_url: str, *, headers: dict[str, str], timeout: float) -> _Response:
        requests.append(headers)
        return _Response(
            {
                "enabled": False,
                "mode": "off",
                "route_count": 0,
                "routes": [],
                "decision": None,
            }
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    result = CliRunner().invoke(
        main,
        ["routing", "status", "--proxy-url", "http://localhost:8787"],
        env={
            "CUTCTX_SAFE_SAVINGS_EXPERIENCE": "1",
            "CUTCTX_WORKSPACE_DIR": str(workspace),
        },
    )

    assert result.exit_code == 0, result.output
    assert requests == [{"x-cutctx-admin-key": "relocated-admin-key"}]


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
