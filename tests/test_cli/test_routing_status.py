"""Tests for the read-only `cutctx routing status` command."""

from __future__ import annotations

from typing import Any

import httpx
from click.testing import CliRunner

from cutctx.cli.main import main


def _response(payload: dict[str, Any], status_code: int = 200):
    class Response:
        def __init__(self) -> None:
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"{status_code} error",
                    request=httpx.Request("GET", "http://cutctx.local"),
                    response=httpx.Response(status_code),
                )

        def json(self) -> dict[str, Any]:
            return payload

    return Response()


def test_routing_status_reports_off_without_mutation(monkeypatch) -> None:
    calls = []

    def get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return _response(
            {
                "schema_version": 1,
                "experience_enabled": True,
                "enabled": False,
                "mode": "off",
                "preset": None,
                "route_count": 0,
                "routes": [],
                "transport_safe_targets": [],
                "decision": None,
                "rollback_available": False,
            }
        )

    monkeypatch.setattr("httpx.get", get)
    result = CliRunner().invoke(
        main,
        ["routing", "status", "--proxy-url", "http://127.0.0.1:8787"],
    )

    assert result.exit_code == 0
    assert "Safe Savings: Off" in result.output
    assert "Requests retain the originally requested model." in result.output
    assert [item[0] for item in calls] == ["GET"]


def test_routing_status_renders_routes_decision_and_confidence(monkeypatch) -> None:
    def get(url, **kwargs):
        return _response(
            {
                "schema_version": 1,
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
                        "low_target_capabilities": ["tools"],
                        "medium_target_capabilities": ["tools"],
                        "low_target_transport_safe": True,
                        "medium_target_transport_safe": False,
                    }
                ],
                "transport_safe_targets": ["gpt-5.4-mini"],
                "decision": {
                    "request_id": "req-1",
                    "requested_model": "gpt-5.6-sol",
                    "effective_model": "gpt-5.4-mini",
                    "candidate_model": "gpt-5.4-mini",
                    "applied": True,
                    "reason": "downgrade_applied",
                    "title": "Safe route applied",
                    "explanation": (
                        "The request passed the configured safety and compatibility "
                        "gates for the selected lower-cost model."
                    ),
                    "scorer": None,
                    "confidence": 0.9,
                    "signals": ["explicit_low_complexity"],
                    "required_capabilities": [],
                    "missing_capabilities": [],
                    "transport": {},
                },
                "rollback_available": True,
            }
        )

    monkeypatch.setattr("httpx.get", get)
    result = CliRunner().invoke(
        main,
        ["routing", "status", "--proxy-url", "http://127.0.0.1:8787"],
    )

    assert result.exit_code == 0
    assert "Safe Savings: Balanced" in result.output
    assert "Preset: codex-gpt54mini-high" in result.output
    assert "gpt-5.6-sol -> gpt-5.4-mini (low, transport-safe)" in result.output
    assert "gpt-5.6-sol -> gpt-5.6-luna (medium, restricted)" in result.output
    assert "Recent decision: applied gpt-5.6-sol -> gpt-5.4-mini" in result.output
    assert "Reason: Safe route applied" in result.output
    assert "Confidence: 0.90" in result.output


def test_routing_status_auth_failure_does_not_print_key(monkeypatch) -> None:
    def get(url, **kwargs):
        return _response({}, status_code=401)

    monkeypatch.setattr("httpx.get", get)
    result = CliRunner().invoke(
        main,
        [
            "routing",
            "status",
            "--proxy-url",
            "http://127.0.0.1:8787",
            "--admin-key",
            "supersecretkey",
        ],
    )

    assert result.exit_code != 0
    assert "Unable to read Safe Savings status" in result.output
    assert "supersecretkey" not in result.output
