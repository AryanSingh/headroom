from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from cutctx.cli.main import main


def _paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    state_path = tmp_path / "state.json"
    agent_path = tmp_path / "LaunchAgents" / "com.cutctx.global-routing.plist"
    monkeypatch.setattr("cutctx.cli.global_routing._state_path", lambda: state_path)
    monkeypatch.setattr("cutctx.cli.global_routing._launchagent_path", lambda: agent_path)
    monkeypatch.setattr("cutctx.cli.global_routing._require_macos", lambda: None)
    return state_path, agent_path


def test_global_install_records_previous_values_and_writes_launchagent(
    monkeypatch, tmp_path: Path
) -> None:
    state_path, agent_path = _paths(monkeypatch, tmp_path)
    environment = {"OPENAI_BASE_URL": "https://old-openai", "ANTHROPIC_BASE_URL": None}
    monkeypatch.setattr("cutctx.cli.global_routing._getenv", environment.get)
    monkeypatch.setattr(
        "cutctx.cli.global_routing._setenv",
        lambda name, value: environment.__setitem__(name, value),
    )
    monkeypatch.setattr(
        "cutctx.cli.global_routing._unsetenv", lambda name: environment.__setitem__(name, None)
    )
    monkeypatch.setattr("cutctx.cli.global_routing._bootstrap_launchagent", lambda: None)
    monkeypatch.setattr("cutctx.cli.global_routing._proxy_ready", lambda port: port == 9999)

    result = CliRunner().invoke(main, ["global", "install", "--port", "9999"])

    assert result.exit_code == 0, result.output
    assert environment == {
        "OPENAI_BASE_URL": "http://127.0.0.1:9999/v1",
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:9999",
    }
    assert agent_path.exists()
    assert json.loads(state_path.read_text()) == {
        "port": 9999,
        "previous": {"OPENAI_BASE_URL": "https://old-openai", "ANTHROPIC_BASE_URL": None},
    }


def test_global_install_requires_ready_proxy(monkeypatch, tmp_path: Path) -> None:
    _paths(monkeypatch, tmp_path)
    monkeypatch.setattr("cutctx.cli.global_routing._proxy_ready", lambda port: False)

    result = CliRunner().invoke(main, ["global", "install"])

    assert result.exit_code != 0
    assert "proxy is not ready" in result.output


def test_global_update_restores_prior_agent_and_values_on_failure(
    monkeypatch, tmp_path: Path
) -> None:
    # Regression guard: a failed port update must retain an already-working
    # global route rather than treating it like a failed first installation.
    state_path, agent_path = _paths(monkeypatch, tmp_path)
    state_path.write_text(
        json.dumps(
            {"port": 8787, "previous": {"OPENAI_BASE_URL": None, "ANTHROPIC_BASE_URL": None}}
        )
    )
    agent_path.parent.mkdir(parents=True)
    agent_path.write_bytes(b"previous-agent")
    environment = {
        "OPENAI_BASE_URL": "http://127.0.0.1:8787/v1",
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787",
    }
    monkeypatch.setattr("cutctx.cli.global_routing._getenv", environment.get)
    monkeypatch.setattr(
        "cutctx.cli.global_routing._setenv",
        lambda name, value: environment.__setitem__(name, value),
    )
    monkeypatch.setattr(
        "cutctx.cli.global_routing._unsetenv", lambda name: environment.__setitem__(name, None)
    )
    monkeypatch.setattr("cutctx.cli.global_routing._proxy_ready", lambda port: True)
    monkeypatch.setattr(
        "cutctx.cli.global_routing._bootstrap_launchagent",
        lambda: (_ for _ in ()).throw(RuntimeError("bootstrap failed")),
    )

    result = CliRunner().invoke(main, ["global", "install", "--port", "9999"])

    assert result.exit_code != 0
    assert agent_path.read_bytes() == b"previous-agent"
    assert environment == {
        "OPENAI_BASE_URL": "http://127.0.0.1:8787/v1",
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787",
    }


def test_global_uninstall_restores_previous_values(monkeypatch, tmp_path: Path) -> None:
    state_path, agent_path = _paths(monkeypatch, tmp_path)
    state_path.write_text(
        json.dumps(
            {
                "port": 8787,
                "previous": {
                    "OPENAI_BASE_URL": None,
                    "ANTHROPIC_BASE_URL": "https://old-anthropic",
                },
            }
        )
    )
    agent_path.parent.mkdir(parents=True)
    agent_path.write_text("agent")
    environment: dict[str, str | None] = {}
    monkeypatch.setattr(
        "cutctx.cli.global_routing._setenv",
        lambda name, value: environment.__setitem__(name, value),
    )
    monkeypatch.setattr(
        "cutctx.cli.global_routing._unsetenv", lambda name: environment.__setitem__(name, None)
    )
    monkeypatch.setattr(
        "cutctx.cli.global_routing._remove_launchagent", lambda: agent_path.unlink()
    )

    result = CliRunner().invoke(main, ["global", "uninstall"])

    assert result.exit_code == 0, result.output
    assert environment == {"OPENAI_BASE_URL": None, "ANTHROPIC_BASE_URL": "https://old-anthropic"}
    assert not state_path.exists()
    assert not agent_path.exists()


def test_global_doctor_reports_healthy_managed_routing(monkeypatch, tmp_path: Path) -> None:
    state_path, agent_path = _paths(monkeypatch, tmp_path)
    state_path.write_text(
        json.dumps(
            {"port": 8787, "previous": {"OPENAI_BASE_URL": None, "ANTHROPIC_BASE_URL": None}}
        )
    )
    agent_path.parent.mkdir(parents=True)
    agent_path.write_text("agent")
    values = {
        "OPENAI_BASE_URL": "http://127.0.0.1:8787/v1",
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787",
    }
    monkeypatch.setattr("cutctx.cli.global_routing._getenv", values.get)
    monkeypatch.setattr("cutctx.cli.global_routing._proxy_ready", lambda port: True)

    result = CliRunner().invoke(main, ["global", "doctor"])

    assert result.exit_code == 0, result.output
    assert "Safety: chatgpt.com is intentionally not transparently intercepted." in result.output
    assert "OK: managed session environment" in result.output


def test_global_status_handles_missing_install(monkeypatch, tmp_path: Path) -> None:
    _paths(monkeypatch, tmp_path)

    result = CliRunner().invoke(main, ["global", "status"])

    assert result.exit_code == 0
    assert result.output.strip() == "Global routing: not installed"
