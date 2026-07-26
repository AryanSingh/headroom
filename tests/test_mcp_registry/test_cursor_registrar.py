"""Tests for the Cursor MCP registrar (app + cursor-agent CLI)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from cutctx.mcp_registry.base import RegisterStatus, ServerSpec
from cutctx.mcp_registry.cursor import (
    CONFIG_FILENAME,
    CursorRegistrar,
    default_config_dir,
)


def _registrar(tmp_path: Path, *, cli: str | None = None) -> CursorRegistrar:
    return CursorRegistrar(config_dir=tmp_path / ".cursor", cursor_agent_cli=cli)


def _make_registrar(tmp_path: Path) -> CursorRegistrar:
    return CursorRegistrar(home_dir=tmp_path)


def _spec(command: str = "/opt/bin/cutctx") -> ServerSpec:
    return ServerSpec(name="cutctx", command=command, args=("mcp", "serve"))


def _config_path(tmp_path: Path) -> Path:
    return tmp_path / ".cursor" / CONFIG_FILENAME


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ----------------------------------------------------------------------
# Paths and detection
# ----------------------------------------------------------------------


def test_default_config_dir_is_dot_cursor(tmp_path: Path) -> None:
    assert default_config_dir(home=tmp_path) == tmp_path / ".cursor"


def test_detect_true_when_config_dir_exists(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()
    assert _registrar(tmp_path).detect() is True


def test_detect_true_when_cursor_dir_exists(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()
    assert CursorRegistrar(home_dir=tmp_path).detect() is True


def test_detect_true_for_cli_only_install(tmp_path: Path) -> None:
    """A CLI-only install has no ~/.cursor yet but does have cursor-agent."""
    with patch("cutctx.mcp_registry.cursor.shutil.which", return_value=None):
        assert _registrar(tmp_path, cli="/usr/local/bin/cursor-agent").detect() is True


def test_detect_false_when_nothing_present(tmp_path: Path) -> None:
    with patch("cutctx.mcp_registry.cursor.shutil.which", return_value=None):
        with patch("cutctx.providers.cursor.cli.find_agent_cli", return_value=None):
            assert _registrar(tmp_path).detect() is False


# ----------------------------------------------------------------------
# Registration
# ----------------------------------------------------------------------


def test_register_writes_mcp_json(tmp_path: Path) -> None:
    result = _registrar(tmp_path).register_server(_spec())

    assert result.status is RegisterStatus.REGISTERED
    config = json.loads(_config_path(tmp_path).read_text())
    assert config["mcpServers"]["cutctx"] == {
        "command": "/opt/bin/cutctx",
        "args": ["mcp", "serve"],
    }


def test_register_server_writes_mcp_json(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    result = reg.register_server(_spec())

    assert result.status is RegisterStatus.REGISTERED
    config_path = tmp_path / ".cursor" / "mcp.json"
    assert config_path.exists()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["cutctx"]["command"] == "/opt/bin/cutctx"


def test_register_server_project_writes_project_mcp_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reg = _make_registrar(tmp_path)
    result = reg.register_server_project(_spec())

    assert result.status is RegisterStatus.REGISTERED
    config_path = tmp_path / ".cursor" / "mcp.json"
    assert config_path.exists()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["cutctx"]["args"] == ["mcp", "serve"]


def test_register_preserves_other_servers(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"mcpServers": {"other": {"command": "npx", "args": ["thing"]}}}))

    _registrar(tmp_path).register_server(_spec())

    servers = json.loads(path.read_text())["mcpServers"]
    assert servers["other"] == {"command": "npx", "args": ["thing"]}
    assert "cutctx" in servers


def test_register_resolves_bare_command_to_absolute_path(tmp_path: Path) -> None:
    """Cursor.app launches from the Dock with a GUI PATH; bare names fail there."""
    with patch("cutctx.mcp_registry.json_registrar.shutil.which", return_value="/venv/bin/cutctx"):
        _registrar(tmp_path).register_server(ServerSpec(name="cutctx", command="cutctx"))

    config = json.loads(_config_path(tmp_path).read_text())
    assert config["mcpServers"]["cutctx"]["command"] == "/venv/bin/cutctx"


def test_register_is_idempotent(tmp_path: Path) -> None:
    reg = _registrar(tmp_path)
    reg.register_server(_spec())
    assert reg.register_server(_spec()).status is RegisterStatus.ALREADY


def test_register_server_is_idempotent(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    first = reg.register_server(_spec())
    second = reg.register_server(_spec())

    assert first.status is RegisterStatus.REGISTERED
    assert second.status is RegisterStatus.ALREADY


def test_register_reports_mismatch_without_force(tmp_path: Path) -> None:
    reg = _registrar(tmp_path)
    reg.register_server(_spec("/old/cutctx"))

    result = reg.register_server(_spec("/new/cutctx"))

    assert result.status is RegisterStatus.MISMATCH
    config = json.loads(_config_path(tmp_path).read_text())
    assert config["mcpServers"]["cutctx"]["command"] == "/old/cutctx"


def test_force_overwrites_mismatch(tmp_path: Path) -> None:
    reg = _registrar(tmp_path)
    reg.register_server(_spec("/old/cutctx"))

    result = reg.register_server(_spec("/new/cutctx"), force=True)

    assert result.status is RegisterStatus.REGISTERED
    config = json.loads(_config_path(tmp_path).read_text())
    assert config["mcpServers"]["cutctx"]["command"] == "/new/cutctx"


def test_unregister_removes_entry(tmp_path: Path) -> None:
    reg = _registrar(tmp_path)
    reg.register_server(_spec())

    assert reg.unregister_server("cutctx") is True
    assert json.loads(_config_path(tmp_path).read_text())["mcpServers"] == {}


def test_unregister_server_removes_entry(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    reg.register_server(_spec())

    assert reg.unregister_server("cutctx") is True
    assert reg.get_server("cutctx") is None


# ----------------------------------------------------------------------
# CLI approval — the step that makes the CLI actually load the server
# ----------------------------------------------------------------------


def test_register_approves_server_for_cursor_agent(tmp_path: Path) -> None:
    """Writing mcp.json alone leaves the CLI at 'needs approval'."""
    with patch("cutctx.mcp_registry.cursor.subprocess.run", return_value=_completed()) as run:
        result = _registrar(tmp_path, cli="/bin/cursor-agent").register_server(_spec())

    run.assert_called_once()
    assert run.call_args[0][0] == ["/bin/cursor-agent", "mcp", "enable", "cutctx"]
    assert result.status is RegisterStatus.REGISTERED
    assert "approved for cursor-agent" in (result.detail or "")


def test_already_registered_still_retries_approval(tmp_path: Path) -> None:
    """A config written by a previous release may never have been approved."""
    reg = _registrar(tmp_path, cli="/bin/cursor-agent")
    with patch("cutctx.mcp_registry.cursor.subprocess.run", return_value=_completed()):
        reg.register_server(_spec())
        with patch("cutctx.mcp_registry.cursor.subprocess.run", return_value=_completed()) as run:
            result = reg.register_server(_spec())

    assert result.status is RegisterStatus.ALREADY
    assert run.call_args[0][0] == ["/bin/cursor-agent", "mcp", "enable", "cutctx"]


def test_registration_succeeds_when_cli_absent(tmp_path: Path) -> None:
    result = _registrar(tmp_path, cli=None).register_server(_spec())

    assert result.status is RegisterStatus.REGISTERED
    assert "approved" not in (result.detail or "")


def test_cli_failure_does_not_fail_registration(tmp_path: Path) -> None:
    """The app approves via its own UI, so a broken CLI is not fatal."""
    with patch(
        "cutctx.mcp_registry.cursor.subprocess.run",
        return_value=_completed(returncode=1, stderr="boom"),
    ):
        result = _registrar(tmp_path, cli="/bin/cursor-agent").register_server(_spec())

    assert result.status is RegisterStatus.REGISTERED
    assert _config_path(tmp_path).exists()


def test_cli_timeout_does_not_fail_registration(tmp_path: Path) -> None:
    with patch(
        "cutctx.mcp_registry.cursor.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="cursor-agent", timeout=20),
    ):
        result = _registrar(tmp_path, cli="/bin/cursor-agent").register_server(_spec())

    assert result.status is RegisterStatus.REGISTERED


def test_unregister_disables_in_cli_first(tmp_path: Path) -> None:
    reg = _registrar(tmp_path, cli="/bin/cursor-agent")
    with patch("cutctx.mcp_registry.cursor.subprocess.run", return_value=_completed()):
        reg.register_server(_spec())

    with patch("cutctx.mcp_registry.cursor.subprocess.run", return_value=_completed()) as run:
        reg.unregister_server("cutctx")

    assert run.call_args[0][0] == ["/bin/cursor-agent", "mcp", "disable", "cutctx"]


# ----------------------------------------------------------------------
# CLI state reporting
# ----------------------------------------------------------------------


def test_cli_server_state_parses_list_output(tmp_path: Path) -> None:
    out = "other: ready\ncutctx: not loaded (needs approval)\n"
    with patch("cutctx.mcp_registry.cursor.subprocess.run", return_value=_completed(stdout=out)):
        state = _registrar(tmp_path, cli="/bin/cursor-agent").cli_server_state("cutctx")

    assert state == "not loaded (needs approval)"


def test_cli_server_state_none_when_absent_from_output(tmp_path: Path) -> None:
    with patch(
        "cutctx.mcp_registry.cursor.subprocess.run",
        return_value=_completed(stdout="other: ready\n"),
    ):
        assert _registrar(tmp_path, cli="/bin/cursor-agent").cli_server_state("cutctx") is None


def test_cli_server_state_none_without_cli(tmp_path: Path) -> None:
    assert _registrar(tmp_path, cli=None).cli_server_state("cutctx") is None


# ----------------------------------------------------------------------
# Gateway wrapping — the only place compression reaches Cursor
# ----------------------------------------------------------------------


def test_gateway_wraps_other_servers_but_not_cutctx(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "cutctx": {"command": "/opt/bin/cutctx", "args": ["mcp", "serve"]},
                    "slack": {"command": "npx", "args": ["-y", "slack-mcp"]},
                    "remote": {"url": "https://example.test/mcp"},
                }
            }
        )
    )
    reg = _registrar(tmp_path)

    statuses = reg.wrap_servers_with_gateway(cutctx_command="/opt/bin/cutctx")

    assert statuses == {
        "cutctx": "skipped (cutctx)",
        "slack": "wrapped",
        "remote": "skipped (not stdio)",
    }
    servers = json.loads(path.read_text())["mcpServers"]
    assert servers["slack"] == {
        "command": "/opt/bin/cutctx",
        "args": ["mcp", "gateway", "--name", "slack", "--", "npx", "-y", "slack-mcp"],
    }
    assert reg.gateway_wrapped_servers() == ["slack"]


def test_gateway_wrap_is_reversible(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    original = {"command": "npx", "args": ["-y", "slack-mcp"], "env": {"TOKEN": "x"}}
    path.write_text(json.dumps({"mcpServers": {"slack": original}}))
    reg = _registrar(tmp_path)

    reg.wrap_servers_with_gateway(cutctx_command="/opt/bin/cutctx")
    assert reg.unwrap_gateway_servers() == ["slack"]

    assert json.loads(path.read_text())["mcpServers"]["slack"] == original


def test_gateway_wrap_backs_up_config(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"mcpServers": {"slack": {"command": "npx"}}}))
    reg = _registrar(tmp_path)

    reg.wrap_servers_with_gateway(cutctx_command="/opt/bin/cutctx")

    assert reg.last_backup_path is not None
    assert reg.last_backup_path.exists()


def test_gateway_wrap_is_idempotent(tmp_path: Path) -> None:
    path = _config_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"mcpServers": {"slack": {"command": "npx"}}}))
    reg = _registrar(tmp_path)

    reg.wrap_servers_with_gateway(cutctx_command="/opt/bin/cutctx")
    statuses = reg.wrap_servers_with_gateway(cutctx_command="/opt/bin/cutctx")

    assert statuses == {"slack": "already"}
