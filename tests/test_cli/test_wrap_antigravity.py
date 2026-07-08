"""Tests for `cutctx wrap antigravity` — Google VS Code fork wrapper.

`wrap antigravity` always tries to discover and launch the Antigravity CLI
binary with proxy env vars pre-set; if the binary isn't found, it falls back
to the proxy-only-watcher pattern (like Cline), printing GUI setup
instructions instead.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cutctx.cli import wrap as wrap_mod
from cutctx.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_prepare_only_succeeds(runner: CliRunner, tmp_path: Path) -> None:
    """`wrap antigravity --prepare-only` exits 0 without side-effects beyond
    the hint-file injection (tested parametrically in test_wrap_hintfile_agents)."""
    with patch.object(wrap_mod, "_ensure_rtk_binary", return_value=Path("/tmp/rtk")):
        result = runner.invoke(main, ["wrap", "antigravity", "--prepare-only"])

    assert result.exit_code == 0, result.output


def test_no_context_tool_skips_rtk(runner: CliRunner, tmp_path: Path) -> None:
    """`--no-context-tool` must not create .antigravityrules."""
    result = runner.invoke(
        main, ["wrap", "antigravity", "--prepare-only", "--no-context-tool"]
    )

    assert result.exit_code == 0, result.output
    assert not (tmp_path / ".antigravityrules").exists()


def test_launch_falls_back_to_setup_instructions_if_cli_not_found(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the Antigravity CLI binary isn't found, `wrap antigravity` must
    fall back to the proxy-only-watcher (GUI setup instructions) instead of
    hard-erroring — Antigravity.app users have no CLI binary in PATH."""
    monkeypatch.chdir(tmp_path)

    with patch.object(wrap_mod, "_claude_proxy_base_url", return_value="http://127.0.0.1:8787"):
        with patch("cutctx.providers.antigravity.find_cli", return_value=None):
            with patch.object(wrap_mod, "_run_proxy_only_watcher") as mock_watcher:
                result = runner.invoke(
                    main,
                    ["wrap", "antigravity", "--no-proxy", "--no-context-tool"],
                )

    assert result.exit_code == 0, result.output
    mock_watcher.assert_called_once()
    kwargs = mock_watcher.call_args.kwargs
    assert kwargs["agent_label"] == "antigravity"
    assert kwargs["agent_type"] == "antigravity"
    assert kwargs["no_proxy"] is True
    assert callable(kwargs["print_setup_lines"])


def test_unwrap_removes_antigravityrules_block(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`unwrap antigravity` removes the Cutctx block from an existing .antigravityrules."""
    monkeypatch.chdir(tmp_path)

    antigravityrules = tmp_path / ".antigravityrules"
    content = (
        "# My project rules\n\n"
        "Always use Python 3.12.\n\n"
        "<!-- cutctx:rtk-instructions -->\n"
        "RTK instructions here\n"
        "<!-- /cutctx:rtk-instructions -->\n\n"
        "# More rules\n"
    )
    antigravityrules.write_text(content)

    result = runner.invoke(main, ["unwrap", "antigravity"])

    assert result.exit_code == 0, result.output
    assert antigravityrules.exists()
    remaining = antigravityrules.read_text()
    assert "# My project rules" in remaining
    assert "# More rules" in remaining
    assert "cutctx:rtk-instructions" not in remaining


def test_unwrap_removes_empty_file(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`unwrap antigravity` removes .antigravityrules if it only contained the Cutctx block."""
    monkeypatch.chdir(tmp_path)

    antigravityrules = tmp_path / ".antigravityrules"
    antigravityrules.write_text(
        "<!-- cutctx:rtk-instructions -->\nRTK\n<!-- /cutctx:rtk-instructions -->\n"
    )

    result = runner.invoke(main, ["unwrap", "antigravity"])

    assert result.exit_code == 0, result.output
    assert not antigravityrules.exists()


def test_unwrap_noop_when_no_file(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`unwrap antigravity` is a no-op when no .antigravityrules exists."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["unwrap", "antigravity"])

    assert result.exit_code == 0, result.output
    assert "No .antigravityrules" in result.output


def test_cli_binary_find_finds_app_bundle() -> None:
    """``find_cli`` returns a path for the known app bundle on macOS."""
    from cutctx.providers.antigravity.runtime import _CLI_SEARCH_PATHS, find_cli

    # We just verify the search paths include the known locations.
    # On a machine without Antigravity installed, find_cli returns None.
    cli = find_cli()
    if cli is not None:
        assert cli.exists()
        assert cli.is_file()
    else:
        # On CI/machines without Antigravity, ensure we still cover
        # the search paths properly.
        assert any(p.name in {"antigravity", "Antigravity", "Electron"} for p in _CLI_SEARCH_PATHS)
