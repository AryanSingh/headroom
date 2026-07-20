"""Tests for top-level help and version aliases."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from cutctx.cli.main import main


def test_root_help_short_alias() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["-?"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    assert "--version" in result.output


def test_root_help_groups_commands_by_operator_phase() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0, result.output
    assert "Getting Started:" in result.output
    assert "Daily Use:" in result.output
    assert "Optimize and Evaluate:" in result.output
    assert "Administration:" in result.output
    assert "setup" in result.output
    assert "proxy" in result.output
    assert "config" in result.output
    assert "Unavailable in this installation ('compress')" not in result.output
    assert "  compress" not in result.output


def test_root_without_command_shows_first_run_guidance() -> None:
    runner = CliRunner()
    result = runner.invoke(main)

    assert result.exit_code == 0, result.output
    assert "Welcome to Cutctx" in result.output
    assert "cutctx setup" in result.output
    assert "cutctx config doctor" in result.output


def test_root_version_short_alias() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["-v"])

    assert result.exit_code == 0, result.output
    assert "version" in result.output.lower()


def test_group_help_short_alias() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["wrap", "-?"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    assert "claude" in result.output


def test_wrap_subcommand_help_short_alias_beats_passthrough() -> None:
    runner = CliRunner()
    with patch("cutctx.cli.wrap.shutil.which") as which_mock:
        result = runner.invoke(main, ["wrap", "claude", "-?"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    assert "Launch Claude Code through Cutctx proxy." in result.output
    which_mock.assert_not_called()


def test_subcommand_verbose_flag_still_works() -> None:
    runner = CliRunner()
    completed = SimpleNamespace(returncode=0)

    with patch("cutctx.cli.wrap.shutil.which", return_value="claude"):
        with patch("cutctx.cli.wrap._ensure_proxy", return_value=None):
            with patch("cutctx.cli.wrap._setup_rtk", return_value=None):
                with patch("cutctx.cli.wrap._validate_wrap_client_auth"):
                    with patch("cutctx.cli.wrap.subprocess.run", return_value=completed):
                        result = runner.invoke(main, ["wrap", "claude", "-v"])

    assert result.exit_code == 0, result.output
    assert "CUTCTX WRAP: CLAUDE" in result.output


def test_evals_help_mentions_benchmarks_first_class() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["evals", "-?"])

    assert result.exit_code == 0, result.output
    assert "Memory evaluations and compressor benchmark commands." in result.output
    assert "cutctx evals benchmark" in result.output


def test_proxy_help_mentions_learned_policies_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "-?"])

    assert result.exit_code == 0, result.output
    assert "--enable-learned-policies" in result.output
    assert "CUTCTX_LEARNED_POLICIES" in result.output


def test_proxy_help_mentions_model_routing_preset_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["proxy", "-?"])

    assert result.exit_code == 0, result.output
    assert "--model-routing-preset" in result.output
    assert "CUTCTX_MODEL_ROUTING_PRESET" in result.output
