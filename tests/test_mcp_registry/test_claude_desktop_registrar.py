"""Tests for the Claude Desktop app MCP registrar."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cutctx.mcp_registry.base import RegisterStatus, ServerSpec
from cutctx.mcp_registry.claude_desktop import (
    CONFIG_FILENAME,
    ClaudeDesktopRegistrar,
    default_config_dir,
)


def _make_registrar(tmp_path: Path) -> ClaudeDesktopRegistrar:
    """Build a registrar pointed at ``tmp_path`` as the Claude config dir."""
    return ClaudeDesktopRegistrar(config_dir=tmp_path)


def _spec(command: str = "/opt/bin/cutctx") -> ServerSpec:
    # Absolute command by default so _resolve_command leaves it untouched.
    return ServerSpec(name="cutctx", command=command, args=("mcp", "serve"), env={})


def _config_path(tmp_path: Path) -> Path:
    return tmp_path / CONFIG_FILENAME


# ----------------------------------------------------------------------
# default_config_dir()
# ----------------------------------------------------------------------


def test_config_dir_macos(tmp_path: Path) -> None:
    got = default_config_dir("darwin", home=tmp_path)
    assert got == tmp_path / "Library" / "Application Support" / "Claude"


def test_config_dir_windows_appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    got = default_config_dir("win32", home=tmp_path)
    assert got == tmp_path / "Roaming" / "Claude"


def test_config_dir_linux_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    got = default_config_dir("linux", home=tmp_path)
    assert got == tmp_path / "xdg" / "Claude"


def test_config_dir_linux_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    got = default_config_dir("linux", home=tmp_path)
    assert got == tmp_path / ".config" / "Claude"


# ----------------------------------------------------------------------
# detect()
# ----------------------------------------------------------------------


def test_detect_true_when_config_dir_exists(tmp_path: Path) -> None:
    assert _make_registrar(tmp_path).detect() is True


def test_detect_false_when_config_dir_missing(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path / "nope")
    assert reg.detect() is False


# ----------------------------------------------------------------------
# get_server()
# ----------------------------------------------------------------------


def test_get_server_returns_none_when_unregistered(tmp_path: Path) -> None:
    assert _make_registrar(tmp_path).get_server("cutctx") is None


def test_get_server_reads_config(tmp_path: Path) -> None:
    _config_path(tmp_path).write_text(
        json.dumps(
            {
                "mcpServers": {
                    "cutctx": {
                        "command": "/opt/bin/cutctx",
                        "args": ["mcp", "serve"],
                        "env": {"CUTCTX_PROXY_URL": "http://127.0.0.1:9000"},
                    }
                }
            }
        )
    )
    got = _make_registrar(tmp_path).get_server("cutctx")
    assert got is not None
    assert got.command == "/opt/bin/cutctx"
    assert got.args == ("mcp", "serve")
    assert got.env == {"CUTCTX_PROXY_URL": "http://127.0.0.1:9000"}


# ----------------------------------------------------------------------
# register_server()
# ----------------------------------------------------------------------


def test_register_writes_config(tmp_path: Path) -> None:
    result = _make_registrar(tmp_path).register_server(_spec())
    assert result.status == RegisterStatus.REGISTERED
    assert "restart" in (result.detail or "").lower()
    data = json.loads(_config_path(tmp_path).read_text())
    assert data["mcpServers"]["cutctx"] == {
        "command": "/opt/bin/cutctx",
        "args": ["mcp", "serve"],
    }


def test_register_preserves_other_servers(tmp_path: Path) -> None:
    _config_path(tmp_path).write_text(
        json.dumps({"mcpServers": {"other": {"command": "other"}}, "theme": "dark"})
    )
    result = _make_registrar(tmp_path).register_server(_spec())
    assert result.status == RegisterStatus.REGISTERED
    data = json.loads(_config_path(tmp_path).read_text())
    assert "other" in data["mcpServers"]
    assert data["theme"] == "dark"
    assert "cutctx" in data["mcpServers"]


def test_register_resolves_bare_command_to_absolute_path(tmp_path: Path) -> None:
    # Claude Desktop launches servers with a GUI PATH; bare commands must be
    # resolved while we still have the user's shell PATH.
    with patch("shutil.which", return_value="/home/u/.local/bin/cutctx"):
        result = _make_registrar(tmp_path).register_server(_spec(command="cutctx"))
    assert result.status == RegisterStatus.REGISTERED
    data = json.loads(_config_path(tmp_path).read_text())
    assert data["mcpServers"]["cutctx"]["command"] == "/home/u/.local/bin/cutctx"


def test_register_keeps_bare_command_when_unresolvable(tmp_path: Path) -> None:
    with patch("shutil.which", return_value=None):
        result = _make_registrar(tmp_path).register_server(_spec(command="cutctx"))
    assert result.status == RegisterStatus.REGISTERED
    data = json.loads(_config_path(tmp_path).read_text())
    assert data["mcpServers"]["cutctx"]["command"] == "cutctx"


def test_register_already_when_spec_matches(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    assert reg.register_server(_spec()).status == RegisterStatus.REGISTERED
    assert reg.register_server(_spec()).status == RegisterStatus.ALREADY


def test_register_idempotent_after_command_resolution(tmp_path: Path) -> None:
    # A resolved command must compare equal on the second run — no MISMATCH.
    reg = _make_registrar(tmp_path)
    with patch("shutil.which", return_value="/home/u/.local/bin/cutctx"):
        assert reg.register_server(_spec(command="cutctx")).status == RegisterStatus.REGISTERED
        assert reg.register_server(_spec(command="cutctx")).status == RegisterStatus.ALREADY


def test_register_mismatch_when_spec_differs_no_force(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    reg.register_server(_spec())
    result = reg.register_server(_spec(command="/elsewhere/cutctx"))
    assert result.status == RegisterStatus.MISMATCH
    assert "command" in (result.detail or "")
    data = json.loads(_config_path(tmp_path).read_text())
    assert data["mcpServers"]["cutctx"]["command"] == "/opt/bin/cutctx"  # untouched


def test_register_force_overwrites_mismatch(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    reg.register_server(_spec())
    result = reg.register_server(_spec(command="/elsewhere/cutctx"), force=True)
    assert result.status == RegisterStatus.REGISTERED
    data = json.loads(_config_path(tmp_path).read_text())
    assert data["mcpServers"]["cutctx"]["command"] == "/elsewhere/cutctx"


# ----------------------------------------------------------------------
# unregister_server()
# ----------------------------------------------------------------------


def test_unregister_removes_only_cutctx(tmp_path: Path) -> None:
    _config_path(tmp_path).write_text(
        json.dumps(
            {
                "mcpServers": {
                    "cutctx": {"command": "/opt/bin/cutctx", "args": ["mcp", "serve"]},
                    "other": {"command": "other"},
                }
            }
        )
    )
    reg = _make_registrar(tmp_path)
    assert reg.unregister_server("cutctx") is True
    data = json.loads(_config_path(tmp_path).read_text())
    assert "cutctx" not in data["mcpServers"]
    assert "other" in data["mcpServers"]


def test_unregister_returns_false_when_absent(tmp_path: Path) -> None:
    assert _make_registrar(tmp_path).unregister_server("cutctx") is False


# ----------------------------------------------------------------------
# Robustness: bad JSON should not crash
# ----------------------------------------------------------------------


@pytest.mark.parametrize("contents", ["", "not json", "{", "[]"])
def test_get_server_robust_to_bad_json(tmp_path: Path, contents: str) -> None:
    _config_path(tmp_path).write_text(contents)
    assert _make_registrar(tmp_path).get_server("cutctx") is None
