"""Regression tests for the unified setup command's completion state."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from cutctx.auth.client_credentials import (
    ClientCredential,
    ClientCredentialStoreError,
)
from cutctx.cli import setup as setup_mod
from cutctx.cli.setup import setup


def _invoke_setup(
    monkeypatch,
    *,
    health_checks: list[dict[str, int | bool | None]],
    started: bool = False,
    args: tuple[str, ...] = (),
):
    credential = ClientCredential(
        "http://127.0.0.1:8787",
        "synthetic-secret",
        "generated",
    )
    monkeypatch.setattr("cutctx.cli.setup._check_cutctx_installed", lambda: True)
    monkeypatch.setattr("cutctx.cli.setup._detect_agents", lambda: [])
    monkeypatch.setattr(
        "cutctx.cli.setup.ensure_local_client_credential",
        lambda _url: credential,
        raising=False,
    )
    monkeypatch.setattr(
        "cutctx.cli.setup._start_proxy",
        lambda _port, _client_api_key: started,
    )
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
    assert (
        "https://github.com/AryanSingh/headroom/blob/main/docs/content/docs/troubleshooting.mdx"
        in result.output
    )
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


def test_setup_bootstraps_client_auth_before_proxy_start(monkeypatch) -> None:
    events: list[tuple[object, ...]] = []
    checks = iter(
        [
            {"running": False, "status": None},
            {"running": True, "status": 200},
        ]
    )
    credential = ClientCredential(
        "http://127.0.0.1:8787",
        "synthetic-secret",
        "generated",
    )
    monkeypatch.setattr(setup_mod, "_check_cutctx_installed", lambda: True)
    monkeypatch.setattr(setup_mod, "_detect_agents", lambda: [])
    monkeypatch.setattr(setup_mod, "_check_health", lambda port: next(checks))
    monkeypatch.setattr(
        setup_mod,
        "ensure_local_client_credential",
        lambda url: events.append(("auth", url)) or credential,
        raising=False,
    )
    monkeypatch.setattr(
        setup_mod,
        "_start_proxy",
        lambda port, client_api_key: events.append(
            ("proxy", port, client_api_key)
        )
        or True,
    )

    result = CliRunner().invoke(setup, ["--no-detect", "--no-mcp"])

    assert result.exit_code == 0, result.output
    assert events == [
        ("auth", "http://127.0.0.1:8787"),
        ("proxy", 8787, "synthetic-secret"),
    ]
    assert "synthetic-secret" not in result.output


def test_setup_fails_closed_when_secure_store_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(setup_mod, "_check_cutctx_installed", lambda: True)
    monkeypatch.setattr(setup_mod, "_detect_agents", lambda: [])
    monkeypatch.setattr(
        setup_mod,
        "ensure_local_client_credential",
        lambda url: (_ for _ in ()).throw(
            ClientCredentialStoreError("secure store unavailable")
        ),
        raising=False,
    )

    result = CliRunner().invoke(setup, ["--no-detect", "--no-mcp"])

    assert result.exit_code != 0
    assert "Secure credential storage is unavailable." in result.output
    assert "CUTCTX_API_KEY" in result.output
    assert "CUTCTX_CLIENT_API_KEY" in result.output


def test_start_proxy_passes_client_key_only_through_server_environment(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("CUTCTX_API_KEY", "parent-client-secret")
    monkeypatch.setattr(
        setup_mod.subprocess,
        "Popen",
        lambda command, **kwargs: captured.update(command=command, kwargs=kwargs)
        or SimpleNamespace(),
    )
    monkeypatch.setattr(setup_mod.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        "httpx.get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200),
    )

    assert setup_mod._start_proxy(8787, "server-client-secret") is True
    assert all("server-client-secret" not in arg for arg in captured["command"])
    child_env = captured["kwargs"]["env"]
    assert child_env["CUTCTX_CLIENT_API_KEY"] == "server-client-secret"
    assert "CUTCTX_API_KEY" not in child_env


def test_readme_promotes_unified_setup_before_manual_agent_wrapping() -> None:
    readme = Path("README.md").read_text()
    quickstart_start = readme.index("## Get started (60 seconds)")
    quickstart_end = readme.index("**Accuracy guard**", quickstart_start)
    quickstart = readme[quickstart_start:quickstart_end]

    assert quickstart.index("cutctx setup") < quickstart.index("cutctx wrap claude")
