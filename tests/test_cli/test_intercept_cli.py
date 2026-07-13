from __future__ import annotations

from click.testing import CliRunner

from cutctx.cli.main import main


def test_intercept_rejects_unset_experimental_flag(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.delenv("CUTCTX_EXPERIMENTAL", raising=False)

    result = CliRunner().invoke(main, ["intercept", "status"], env={})

    assert result.exit_code != 0
    assert "CUTCTX_EXPERIMENTAL=1" in result.output


def test_intercept_status_requires_opt_in_and_reports_state(monkeypatch) -> None:
    monkeypatch.setattr("sys.platform", "darwin")

    monkeypatch.setattr(
        "cutctx.intercept.macos.status",
        lambda: {
            "hosts_entries": True,
            "pf_daemon": True,
            "tls_cert": True,
            "launchagent_tls": True,
            "bypass_ips": True,
            "node_tls_trust": True,
        },
    )

    result = CliRunner().invoke(main, ["intercept", "status"], env={"CUTCTX_EXPERIMENTAL": "1"})

    assert result.exit_code == 0, result.output
    assert "Fully configured" in result.output
