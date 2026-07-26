"""Tests for the Cursor MCP registrar."""

from __future__ import annotations

import json
from pathlib import Path

from cutctx.mcp_registry.base import RegisterStatus, ServerSpec
from cutctx.mcp_registry.cursor import CursorRegistrar


def _make_registrar(tmp_path: Path) -> CursorRegistrar:
    return CursorRegistrar(home_dir=tmp_path)


def _spec() -> ServerSpec:
    return ServerSpec(
        name="cutctx",
        command="cutctx",
        args=("mcp", "serve"),
        env={},
    )


def test_detect_true_when_cursor_dir_exists(tmp_path: Path) -> None:
    (tmp_path / ".cursor").mkdir()
    assert CursorRegistrar(home_dir=tmp_path).detect() is True


def test_register_server_writes_mcp_json(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    result = reg.register_server(_spec())

    assert result.status is RegisterStatus.REGISTERED
    config_path = tmp_path / ".cursor" / "mcp.json"
    assert config_path.exists()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["cutctx"]["command"] == "cutctx"


def test_register_server_project_writes_project_mcp_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    reg = _make_registrar(tmp_path)
    result = reg.register_server_project(_spec())

    assert result.status is RegisterStatus.REGISTERED
    config_path = tmp_path / ".cursor" / "mcp.json"
    assert config_path.exists()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["cutctx"]["args"] == ["mcp", "serve"]


def test_register_server_is_idempotent(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    first = reg.register_server(_spec())
    second = reg.register_server(_spec())

    assert first.status is RegisterStatus.REGISTERED
    assert second.status is RegisterStatus.ALREADY


def test_unregister_server_removes_entry(tmp_path: Path) -> None:
    reg = _make_registrar(tmp_path)
    reg.register_server(_spec())

    assert reg.unregister_server("cutctx") is True
    assert reg.get_server("cutctx") is None
