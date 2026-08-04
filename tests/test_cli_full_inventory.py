from __future__ import annotations

import click
from click.testing import CliRunner

from cutctx.cli.main import main


def _leaf_commands(command: click.Command, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    if not isinstance(command, click.Group):
        return [path]

    context = click.Context(command, info_name=path[-1] if path else "cutctx")
    leaves: list[tuple[str, ...]] = []
    for name in command.list_commands(context):
        child = command.get_command(context, name)
        assert child is not None, f"registered command {path + (name,)} did not load"
        leaves.extend(_leaf_commands(child, path + (name,)))
    return leaves


def test_every_cli_leaf_has_loadable_help_in_an_isolated_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    leaves = _leaf_commands(main)
    assert len(leaves) >= 120, "CLI inventory unexpectedly shrank below the audited 120 leaves"

    runner = CliRunner()
    failures: list[str] = []
    for path in leaves:
        result = runner.invoke(main, [*path, "--help"], catch_exceptions=True)
        if result.exit_code != 0:
            failures.append(
                f"cutctx {' '.join(path)}: exit={result.exit_code}; "
                f"exception={result.exception!r}; output={result.output[-500:]!r}"
            )

    assert not failures, "\n".join(failures)
