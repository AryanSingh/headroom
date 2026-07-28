"""Shared local admin credential discovery contract for CLI clients."""

from __future__ import annotations

from cutctx.cli.admin_auth import admin_headers, resolve_admin_api_key


def test_admin_key_precedence_is_explicit_then_environment_then_local_file(
    tmp_path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "admin_key.txt").write_text("file-key\n", encoding="utf-8")
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(workspace))
    monkeypatch.setenv("CUTCTX_ADMIN_API_KEY", "env-key")

    assert resolve_admin_api_key("explicit-key", "http://127.0.0.1:8787") == "explicit-key"
    assert resolve_admin_api_key(None, "http://127.0.0.1:8787") == "env-key"
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY")
    assert resolve_admin_api_key(None, "http://localhost:8787") == "file-key"


def test_admin_key_file_is_never_forwarded_to_a_remote_proxy(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "admin_key.txt").write_text("local-secret\n", encoding="utf-8")
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(workspace))
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)

    assert resolve_admin_api_key(None, "https://proxy.example.com") is None
    assert admin_headers(None, "https://proxy.example.com") == {"Content-Type": "application/json"}


def test_admin_headers_discovers_loopback_key(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "admin_key.txt").write_text("local-key\n", encoding="utf-8")
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(workspace))
    monkeypatch.delenv("CUTCTX_ADMIN_API_KEY", raising=False)

    assert admin_headers(None, "http://[::1]:8787") == {
        "Content-Type": "application/json",
        "Authorization": "Bearer local-key",
    }
