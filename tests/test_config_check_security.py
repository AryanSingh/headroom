from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from cutctx.cli.config_check import config_check


@pytest.fixture(autouse=True)
def _isolated_working_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Avoid inheriting a developer's project-local credentials in CLI tests."""
    monkeypatch.chdir(tmp_path)


def test_network_host_without_auth_is_a_launch_blocker(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    result = CliRunner().invoke(
        config_check, ["--host", "0.0.0.0", "--port", "0", "--production"]
    )

    assert result.exit_code == 1
    assert "admin_auth_required" in result.output


def test_network_host_with_admin_key_passes(monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("CUTCTX_FIREWALL_ENABLED", "1")

    result = CliRunner().invoke(
        config_check, ["--host", "0.0.0.0", "--port", "0", "--production"]
    )

    assert result.exit_code == 0, result.output
    assert "Config looks good!" in result.output


def test_production_validation_requires_firewall(monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "test-admin-key")
    monkeypatch.delenv("CUTCTX_FIREWALL_ENABLED", raising=False)

    result = CliRunner().invoke(
        config_check, ["--host", "0.0.0.0", "--port", "0", "--production", "--format", "json"]
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["issues"][-1]["code"] == "firewall_required"


def test_json_output_is_redacted_and_machine_readable(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    result = CliRunner().invoke(
        config_check, ["--host", "0.0.0.0", "--port", "0", "--format", "json"]
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert payload["issues"][0]["code"] == "admin_auth_required"
    assert "CUTCTX_ADMIN_API_KEY" in payload["issues"][0]["remediation"]


def test_config_check_loads_documented_local_provider_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env.local").write_text("CUTCTX_UPSTREAM_OPENAI_API_KEY=example\n")
    monkeypatch.delenv("CUTCTX_UPSTREAM_OPENAI_API_KEY", raising=False)

    result = CliRunner().invoke(config_check, ["--port", "0"])

    assert result.exit_code == 0, result.output
    assert "OpenAI: configured" in result.output
