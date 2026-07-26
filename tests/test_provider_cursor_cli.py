"""Tests for Cursor CLI/IDE discovery helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from cutctx.providers.cursor.cli import (
    build_agent_endpoint_url,
    build_agent_launch_args,
    find_agent_cli,
    find_ide_cli,
)


def test_build_agent_endpoint_url_includes_project_prefix() -> None:
    url = build_agent_endpoint_url(port=8787, project="demo")
    assert url == "http://127.0.0.1:8787/p/demo"


def test_build_agent_launch_args_includes_endpoint_and_headers() -> None:
    args = build_agent_launch_args(port=8787, project="demo", extra_args=("fix tests",))
    assert args[0:2] == ("-e", "http://127.0.0.1:8787/p/demo")
    assert "-H" in args
    assert "X-Client: cursor" in args
    assert "X-Cutctx-Project: demo" in args
    assert "--print" in args
    assert args[-1] == "fix tests"


def test_find_agent_cli_uses_probe(monkeypatch, tmp_path: Path) -> None:
    agent_bin = tmp_path / "agent"
    agent_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    agent_bin.chmod(0o755)

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "About Cursor CLI\nCLI Version 1.0.0\n"

        return Result()

    with patch("cutctx.providers.cursor.cli.shutil.which", return_value=str(agent_bin)):
        with patch("cutctx.providers.cursor.cli.subprocess.run", side_effect=fake_run):
            assert find_agent_cli() == agent_bin


def test_probe_accepts_plain_text_about_output(monkeypatch, tmp_path: Path) -> None:
    agent_bin = tmp_path / "cursor-agent"
    agent_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    agent_bin.chmod(0o755)

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "About Cursor CLI\nCLI Version 2026.07.23\n"

        return Result()

    with patch("cutctx.providers.cursor.cli.shutil.which", return_value=str(agent_bin)):
        with patch("cutctx.providers.cursor.cli.subprocess.run", side_effect=fake_run):
            assert find_agent_cli() == agent_bin


def test_find_agent_cli_rejects_non_cursor_agent(monkeypatch, tmp_path: Path) -> None:
    agent_bin = tmp_path / "agent"
    agent_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    agent_bin.chmod(0o755)

    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stdout = "About Grok Agent\n"

        return Result()

    with patch("cutctx.providers.cursor.cli.shutil.which", return_value=str(agent_bin)):
        with patch("cutctx.providers.cursor.cli.subprocess.run", side_effect=fake_run):
            assert find_agent_cli() is None


def test_find_ide_cli_prefers_path(monkeypatch, tmp_path: Path) -> None:
    cursor_bin = tmp_path / "cursor"
    cursor_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    cursor_bin.chmod(0o755)

    with patch("cutctx.providers.cursor.cli.shutil.which", return_value=str(cursor_bin)):
        assert find_ide_cli() == cursor_bin
