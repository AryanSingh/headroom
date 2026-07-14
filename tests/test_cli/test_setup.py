"""Regression tests for the unified setup command's completion state."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from cutctx.cli.setup import setup


def _invoke_setup(
    monkeypatch,
    *,
    health_checks: list[dict[str, int | bool | None]],
    started: bool = False,
    args: tuple[str, ...] = (),
):
    monkeypatch.setattr("cutctx.cli.setup._check_cutctx_installed", lambda: True)
    monkeypatch.setattr("cutctx.cli.setup._detect_agents", lambda: [])
    monkeypatch.setattr("cutctx.cli.setup._start_proxy", lambda _port: started)
    checks = iter(health_checks)
    monkeypatch.setattr("cutctx.cli.setup._check_health", lambda _port: next(checks))
    return CliRunner().invoke(setup, list(args))


def test_setup_exits_nonzero_and_explains_recovery_when_unhealthy(monkeypatch) -> None:
    result = _invoke_setup(
        monkeypatch,
        health_checks=[{"running": False, "status": None}] * 2,
    )

    assert result.exit_code == 1, result.output
    assert "Setup needs attention" in result.output
    assert "cutctx proxy --port 8787" in result.output
    assert "https://cutctx.com/docs/troubleshooting" in result.output
    assert "Setup Complete!" not in result.output


def test_setup_succeeds_when_final_health_is_healthy(monkeypatch) -> None:
    result = _invoke_setup(
        monkeypatch,
        health_checks=[
            {"running": False, "status": None},
            {"running": True, "status": 200},
        ],
        started=True,
    )

    assert result.exit_code == 0, result.output
    assert "Setup Complete!" in result.output
    assert "Health: OK" in result.output


def test_setup_succeeds_for_an_already_healthy_proxy(monkeypatch) -> None:
    result = _invoke_setup(
        monkeypatch,
        health_checks=[
            {"running": True, "status": 200},
            {"running": True, "status": 200},
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Already running" in result.output
    assert "Setup Complete!" in result.output


def test_setup_no_start_exits_zero_and_describes_skip(monkeypatch) -> None:
    result = _invoke_setup(
        monkeypatch,
        health_checks=[{"running": False, "status": None}],
        args=("--no-start",),
    )

    assert result.exit_code == 0, result.output
    assert "Setup skipped proxy start." in result.output
    assert "Setup needs attention" not in result.output


def test_readme_promotes_unified_setup_before_manual_agent_wrapping() -> None:
    readme = Path("README.md").read_text()
    quickstart_start = readme.index("## Get started (60 seconds)")
    quickstart_end = readme.index("**Accuracy guard**", quickstart_start)
    quickstart = readme[quickstart_start:quickstart_end]

    assert quickstart.index("cutctx setup") < quickstart.index("cutctx wrap claude")
