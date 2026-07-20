from __future__ import annotations

from dataclasses import replace

from cutctx.auth.client_credentials import ClientCredential
from cutctx.install import runtime
from cutctx.install.models import DeploymentManifest
from cutctx.install.runtime import _runtime_env, build_runtime_command


def _manifest() -> DeploymentManifest:
    return DeploymentManifest(
        profile="test",
        preset="persistent-task",
        runtime_kind="python",
        supervisor_kind="task",
        scope="user",
        provider_mode="openai",
        targets=[],
        port=8787,
        host="127.0.0.1",
        backend="openai",
    )


def test_runtime_env_injects_admin_key_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "env-admin-key")

    env = _runtime_env(_manifest())

    assert env["CUTCTX_ADMIN_API_KEY"] == "env-admin-key"


def test_runtime_env_injects_admin_key_from_workspace_file(monkeypatch, tmp_path) -> None:
    (tmp_path / "admin_key.txt").write_text("file-admin-key\n", encoding="utf-8")
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))

    env = _runtime_env(_manifest())

    assert env["CUTCTX_ADMIN_API_KEY"] == "file-admin-key"


def test_runtime_env_injects_origin_scoped_client_key(monkeypatch) -> None:
    monkeypatch.delenv("CUTCTX_API_KEY", raising=False)
    monkeypatch.delenv("CUTCTX_CLIENT_API_KEY", raising=False)
    monkeypatch.setattr(
        runtime,
        "resolve_client_credential",
        lambda url, **kwargs: ClientCredential(url, "client-secret", "keyring"),
        raising=False,
    )

    env = _runtime_env(_manifest())

    assert env["CUTCTX_CLIENT_API_KEY"] == "client-secret"
    assert "CUTCTX_API_KEY" not in env


def test_container_command_passes_client_key_by_name_not_value(
    monkeypatch,
) -> None:
    manifest = replace(
        _manifest(),
        runtime_kind="docker",
        preset="persistent-docker",
    )
    monkeypatch.setattr(
        runtime,
        "_resolve_client_api_key",
        lambda manifest: "client-secret",
        raising=False,
    )
    monkeypatch.setattr(runtime, "_ensure_host_dirs", lambda: None)

    command = build_runtime_command(manifest)

    pairs = list(zip(command, command[1:]))
    assert ("--env", "CUTCTX_CLIENT_API_KEY") in pairs
    assert all("client-secret" not in arg for arg in command)


def test_persistent_docker_supplies_client_key_in_subprocess_environment(
    monkeypatch,
) -> None:
    manifest = replace(
        _manifest(),
        runtime_kind="docker",
        preset="persistent-docker",
    )
    calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(
        runtime,
        "build_runtime_command",
        lambda manifest: [
            "docker",
            "run",
            "--rm",
            "--name",
            "cutctx-test",
            "--env",
            "CUTCTX_CLIENT_API_KEY",
        ],
    )
    monkeypatch.setattr(
        runtime,
        "_runtime_env",
        lambda manifest: {"CUTCTX_CLIENT_API_KEY": "client-secret"},
    )
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )

    runtime.start_persistent_docker(manifest)

    docker_run, kwargs = calls[-1]
    assert "client-secret" not in docker_run
    assert kwargs["env"]["CUTCTX_CLIENT_API_KEY"] == "client-secret"
