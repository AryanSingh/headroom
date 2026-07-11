from __future__ import annotations

from cutctx.install.models import DeploymentManifest
from cutctx.install.runtime import _runtime_env


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
