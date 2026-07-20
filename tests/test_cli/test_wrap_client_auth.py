from __future__ import annotations

from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cutctx.auth.client_credentials import (
    ClientCredential,
    ClientCredentialStatus,
)
from cutctx.cli import wrap as wrap_mod
from cutctx.cli.main import main


def test_started_proxy_receives_server_side_client_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("CUTCTX_API_KEY", "parent-client-secret")
    monkeypatch.setattr(wrap_mod, "_get_log_path", lambda: tmp_path / "proxy.log")
    monkeypatch.setattr(wrap_mod, "_check_proxy_ready", lambda port: True)
    monkeypatch.setattr(
        wrap_mod.subprocess,
        "Popen",
        lambda command, **kwargs: captured.update(command=command, kwargs=kwargs)
        or SimpleNamespace(poll=lambda: None),
    )

    wrap_mod._start_proxy(8787, client_api_key="client-secret")

    proxy_env = captured["kwargs"]["env"]
    assert proxy_env["CUTCTX_CLIENT_API_KEY"] == "client-secret"
    assert "CUTCTX_API_KEY" not in proxy_env
    assert all("client-secret" not in arg for arg in captured["command"])


def test_common_launcher_injects_client_key_and_validates_before_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        wrap_mod,
        "resolve_client_credential",
        lambda url, **kwargs: ClientCredential(url, "client-secret", "keyring"),
        raising=False,
    )
    monkeypatch.setattr(
        wrap_mod,
        "validate_client_credential",
        lambda url, credential: captured.update(
            validated_url=url,
            validated_value=credential.value,
        )
        or ClientCredentialStatus("valid"),
        raising=False,
    )
    monkeypatch.setattr(wrap_mod, "_register_proxy_client", lambda port: None)
    monkeypatch.setattr(wrap_mod, "_make_cleanup", lambda holder, port: lambda: None)
    monkeypatch.setattr(
        wrap_mod,
        "_ensure_proxy",
        lambda port, no_proxy, **kwargs: captured.update(
            proxy_port=port,
            proxy_kwargs=kwargs,
        ),
    )
    monkeypatch.setattr(
        wrap_mod.subprocess,
        "run",
        lambda command, env: captured.update(command=command, env=env)
        or SimpleNamespace(returncode=0),
    )

    with pytest.raises(SystemExit) as exc_info:
        wrap_mod._launch_tool(
            binary="probe",
            args=(),
            env={},
            port=8787,
            no_proxy=False,
            tool_label="PROBE",
            env_vars_display=["CUTCTX_BASE_URL=http://127.0.0.1:8787"],
        )

    assert exc_info.value.code == 0
    assert captured["env"]["CUTCTX_API_KEY"] == "client-secret"
    assert captured["proxy_kwargs"]["client_api_key"] == "client-secret"
    assert captured["validated_url"] == "http://127.0.0.1:8787"


def test_ephemeral_launcher_uses_requested_port_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origins: list[str] = []
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        wrap_mod,
        "resolve_client_credential",
        lambda url, **kwargs: origins.append(url)
        or ClientCredential(url, "client-secret", "keyring"),
        raising=False,
    )
    monkeypatch.setattr(
        wrap_mod,
        "validate_client_credential",
        lambda url, credential: captured.update(validated_url=url)
        or ClientCredentialStatus("valid"),
        raising=False,
    )
    monkeypatch.setattr(wrap_mod, "_register_proxy_client", lambda port: None)
    monkeypatch.setattr(wrap_mod, "_make_cleanup", lambda holder, port: lambda: None)
    monkeypatch.setattr(
        wrap_mod,
        "_ensure_proxy",
        lambda port, no_proxy, **kwargs: captured.update(
            proxy_port=port,
            proxy_kwargs=kwargs,
        ),
    )
    monkeypatch.setattr(
        wrap_mod.subprocess,
        "run",
        lambda command, env: SimpleNamespace(returncode=0),
    )

    with pytest.raises(SystemExit):
        wrap_mod._launch_tool(
            binary="probe",
            args=(),
            env={},
            port=54321,
            no_proxy=False,
            tool_label="PROBE",
            env_vars_display=[],
            client_credential_origin="http://127.0.0.1:8787",
        )

    assert origins == ["http://127.0.0.1:8787"]
    assert captured["proxy_port"] == 54321
    assert captured["proxy_kwargs"]["client_api_key"] == "client-secret"
    assert captured["validated_url"] == "http://127.0.0.1:54321"


def test_direct_claude_launcher_uses_shared_client_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(wrap_mod.shutil, "which", lambda binary: "/usr/bin/claude")
    monkeypatch.setattr(
        wrap_mod,
        "resolve_client_credential",
        lambda url, **kwargs: ClientCredential(url, "client-secret", "keyring"),
    )
    monkeypatch.setattr(
        wrap_mod,
        "validate_client_credential",
        lambda url, credential: captured.update(validated_url=url)
        or ClientCredentialStatus("valid"),
    )
    monkeypatch.setattr(wrap_mod, "_register_proxy_client", lambda port: None)
    monkeypatch.setattr(wrap_mod, "_make_cleanup", lambda holder, port: lambda: None)
    monkeypatch.setattr(
        wrap_mod,
        "_ensure_proxy",
        lambda port, no_proxy, **kwargs: captured.update(proxy_kwargs=kwargs),
    )
    monkeypatch.setattr(
        wrap_mod.subprocess,
        "run",
        lambda command, env: captured.update(command=command, env=env)
        or SimpleNamespace(returncode=0),
    )

    result = CliRunner().invoke(
        main,
        [
            "wrap",
            "claude",
            "--no-context-tool",
            "--no-mcp",
            "--no-serena",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["env"]["CUTCTX_API_KEY"] == "client-secret"
    assert captured["proxy_kwargs"]["client_api_key"] == "client-secret"
    assert captured["validated_url"] == "http://127.0.0.1:8787"


@pytest.mark.parametrize("state", ["invalid", "expired"])
def test_launcher_stops_before_child_for_rejected_credential(
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    child_started = False
    monkeypatch.setattr(
        wrap_mod,
        "resolve_client_credential",
        lambda url, **kwargs: ClientCredential(url, "client-secret", "keyring"),
        raising=False,
    )
    monkeypatch.setattr(
        wrap_mod,
        "validate_client_credential",
        lambda url, credential: ClientCredentialStatus(state),
        raising=False,
    )
    monkeypatch.setattr(wrap_mod, "_register_proxy_client", lambda port: None)
    monkeypatch.setattr(wrap_mod, "_make_cleanup", lambda holder, port: lambda: None)
    monkeypatch.setattr(wrap_mod, "_ensure_proxy", lambda *args, **kwargs: None)

    def run_child(command, env):
        nonlocal child_started
        child_started = True
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(wrap_mod.subprocess, "run", run_child)

    with pytest.raises(SystemExit) as exc_info:
        wrap_mod._launch_tool(
            binary="probe",
            args=(),
            env={},
            port=8787,
            no_proxy=True,
            tool_label="PROBE",
            env_vars_display=[],
        )

    assert exc_info.value.code == 1
    assert child_started is False
