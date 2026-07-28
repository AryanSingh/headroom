"""Regression tests for safe audit CLI query serialization."""

from __future__ import annotations

from unittest.mock import Mock, patch

from click.testing import CliRunner

from cutctx.cli.audit import audit


def _response(*, payload: dict | None = None, text: str = "") -> Mock:
    response = Mock()
    response.json.return_value = payload or {}
    response.text = text
    response.raise_for_status.return_value = None
    return response


def test_audit_list_passes_filters_as_literal_query_parameters() -> None:
    runner = CliRunner()
    action = "org.created&limit=9999"

    with patch("cutctx.cli.audit.httpx.get", return_value=_response(payload={"events": []})) as get:
        result = runner.invoke(
            audit,
            [
                "list",
                "--action",
                action,
                "--actor",
                "alice@example.com",
                "--limit",
                "7",
                "--admin-key",
                "explicit-key",
            ],
        )

    assert result.exit_code == 0
    get.assert_called_once_with(
        "http://127.0.0.1:8787/audit/events",
        params={"limit": 7, "action": action, "actor": "alice@example.com"},
        headers={"Content-Type": "application/json", "Authorization": "Bearer explicit-key"},
        timeout=10,
    )


def test_audit_export_uses_structured_query_parameters() -> None:
    runner = CliRunner()

    with patch("cutctx.cli.audit.httpx.get", return_value=_response(text="[]")) as get:
        result = runner.invoke(
            audit,
            [
                "export",
                "--format",
                "jsonl",
                "--action",
                "user.read",
                "--limit",
                "12",
                "--admin-key",
                "explicit-key",
            ],
        )

    assert result.exit_code == 0
    get.assert_called_once_with(
        "http://127.0.0.1:8787/audit/export",
        params={"format": "jsonl", "limit": 12, "action": "user.read"},
        headers={"Content-Type": "application/json", "Authorization": "Bearer explicit-key"},
        timeout=30,
    )


def test_audit_stats_uses_structured_query_parameters() -> None:
    runner = CliRunner()

    with patch(
        "cutctx.cli.audit.httpx.get",
        return_value=_response(payload={"events": []}),
    ) as get:
        result = runner.invoke(audit, ["stats", "--json", "--admin-key", "explicit-key"])

    assert result.exit_code == 0
    get.assert_called_once_with(
        "http://127.0.0.1:8787/audit/events",
        params={"limit": 1000},
        headers={"Content-Type": "application/json", "Authorization": "Bearer explicit-key"},
        timeout=10,
    )


def test_audit_discovers_the_local_admin_key(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "admin_key.txt").write_text("discovered-key\n", encoding="utf-8")
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(workspace))
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    runner = CliRunner()

    with patch("cutctx.cli.audit.httpx.get", return_value=_response(payload={"events": []})) as get:
        result = runner.invoke(audit, ["list"])

    assert result.exit_code == 0
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer discovered-key"
