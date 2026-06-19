"""Tests for `headroom wrap gemini` command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import pytest
from click.testing import CliRunner

from headroom.cli.main import main


def _expected_project_prefix() -> str:
    return f"/p/{quote(Path.cwd().name, safe='')}"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_wrap_gemini_sets_provider_envs(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}

    def fake_launch_tool(**kwargs):  # noqa: ANN003
        captured.update(kwargs)

    with patch("headroom.cli.wrap.shutil.which", return_value="gemini"):
        with patch("headroom.cli.wrap._launch_tool", side_effect=fake_launch_tool):
            result = runner.invoke(main, ["wrap", "gemini", "--no-rtk", "--", "-p", "hello"])

    assert result.exit_code == 0, result.output
    env = captured["env"]
    assert isinstance(env, dict)
    expected = f"http://127.0.0.1:8787{_expected_project_prefix()}"
    assert env["GOOGLE_GEMINI_BASE_URL"] == expected
    assert env["GOOGLE_VERTEX_BASE_URL"] == expected
    assert env["CODE_ASSIST_ENDPOINT"] == expected
    assert captured["tool_label"] == "GEMINI"
    assert captured["agent_type"] == "gemini"
    assert captured["args"] == ("-p", "hello")
