"""Tests for `cutctx wrap opencode` command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cutctx.cli.main import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_wrap_opencode_sets_provider_envs(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}

    def fake_launch_tool(**kwargs):  # noqa: ANN003
        captured.update(kwargs)

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool", side_effect=fake_launch_tool):
            with patch("cutctx.cli.wrap._opencode_go_configured", return_value=False):
                result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["OPENAI_BASE_URL"] == "http://127.0.0.1:8787/v1"
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8787"
    assert env["CUTCTX_BASE_URL"] == "http://127.0.0.1:8787"
    assert captured["tool_label"] == "OPENCODE"
    assert captured["agent_type"] == "opencode"


def test_wrap_opencode_sets_cutctx_base_url_for_custom_port(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}

    def fake_launch_tool(**kwargs):  # noqa: ANN003
        captured.update(kwargs)

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool", side_effect=fake_launch_tool):
            with patch("cutctx.cli.wrap._opencode_go_configured", return_value=False):
                result = runner.invoke(main, ["wrap", "opencode", "--no-rtk", "--port", "9999"])

    assert result.exit_code == 0, result.output
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["CUTCTX_BASE_URL"] == "http://127.0.0.1:9999"


def test_wrap_opencode_installs_plugin(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool"):
            result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    installed = tmp_path / ".opencode" / "plugin" / "cutctx.js"
    assert installed.is_file()
    assert "opencode plugin installed" in result.output


def test_wrap_opencode_skips_plugin_install_when_bundle_missing(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool"):
            with patch("cutctx.cli.wrap._install_opencode_plugin", return_value=None):
                result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert not (tmp_path / ".opencode").exists()


def test_wrap_opencode_warns_when_no_routable_credentials(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """opencode's env vars alone don't route it through the proxy unless it
    has 'anthropic'/'openai' credentials logged in — warn instead of silently
    launching a tool that will never hit the proxy."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool"):
            with patch("cutctx.cli.wrap._opencode_has_routable_credentials", return_value=False):
                with patch("cutctx.cli.wrap._opencode_go_configured", return_value=False):
                    result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert "no 'anthropic' or 'openai' credentials" in result.output
    assert "opencode auth login" in result.output
    assert "kimi-for-coding traffic cannot be routed" in result.output


def test_wrap_opencode_no_warning_with_env_api_key(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool"):
            with patch("cutctx.cli.wrap._opencode_has_routable_credentials", return_value=False):
                result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert "no 'anthropic' or 'openai' credentials" not in result.output


def test_opencode_has_routable_credentials_reads_auth_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cutctx.cli import wrap as wrap_mod

    fake_home = tmp_path
    monkeypatch.setattr(wrap_mod.Path, "home", classmethod(lambda cls: fake_home))

    auth_dir = fake_home / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    auth_path = auth_dir / "auth.json"

    auth_path.write_text('{"kimi-for-coding": {}, "opencode-go": {}}')
    assert wrap_mod._opencode_has_routable_credentials() is False

    auth_path.write_text('{"anthropic": {}, "opencode-go": {}}')
    assert wrap_mod._opencode_has_routable_credentials() is True


def test_opencode_go_configured_reads_auth_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cutctx.cli import wrap as wrap_mod

    fake_home = tmp_path
    monkeypatch.setattr(wrap_mod.Path, "home", classmethod(lambda cls: fake_home))

    auth_dir = fake_home / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    auth_path = auth_dir / "auth.json"

    auth_path.write_text('{"kimi-for-coding": {}}')
    assert wrap_mod._opencode_go_configured() is False

    auth_path.write_text('{"kimi-for-coding": {}, "opencode-go": {}}')
    assert wrap_mod._opencode_go_configured() is True


def test_write_opencode_go_config_override_creates_provider_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))

    override_path = wrap_mod._write_opencode_go_config_override(9999, None)

    data = json.loads(override_path.read_text())
    assert data["provider"]["opencode-go"]["options"]["baseURL"] == "http://127.0.0.1:9999/v1"


def test_write_opencode_go_config_override_merges_existing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))

    existing = tmp_path / "user-opencode-config.json"
    existing.write_text(json.dumps({"model": "opencode-go/deepseek-v4-flash", "lsp": True}))

    override_path = wrap_mod._write_opencode_go_config_override(9999, str(existing))

    data = json.loads(override_path.read_text())
    assert data["model"] == "opencode-go/deepseek-v4-flash"
    assert data["lsp"] is True
    assert data["provider"]["opencode-go"]["options"]["baseURL"] == "http://127.0.0.1:9999/v1"


def test_wrap_opencode_routes_opencode_go_through_proxy(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    def fake_launch_tool(**kwargs):  # noqa: ANN003
        captured.update(kwargs)

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool", side_effect=fake_launch_tool):
            with patch("cutctx.cli.wrap._opencode_has_routable_credentials", return_value=False):
                with patch("cutctx.cli.wrap._opencode_go_configured", return_value=True):
                    result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert "no 'anthropic' or 'openai' credentials" not in result.output
    assert captured["openai_api_url"] == "https://opencode.ai/zen/go/v1"
    env = captured["env"]
    assert isinstance(env, dict)
    override_path = Path(env["OPENCODE_CONFIG"])
    assert override_path.is_file()
    data = json.loads(override_path.read_text())
    assert data["provider"]["opencode-go"]["options"]["baseURL"] == "http://127.0.0.1:8787/v1"


def test_wrap_opencode_auto_reassigns_port_when_shared_proxy_cant_route_opencode_go(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A persistent, shared proxy on the requested port can never honor an
    opencode-go upstream override (DeploymentManifest has no such field) —
    rather than fail or silently misroute, pick a private port for this
    session automatically."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    def fake_launch_tool(**kwargs):  # noqa: ANN003
        captured.update(kwargs)

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool", side_effect=fake_launch_tool):
            with patch("cutctx.cli.wrap._opencode_has_routable_credentials", return_value=False):
                with patch("cutctx.cli.wrap._opencode_go_configured", return_value=True):
                    with patch("cutctx.cli.wrap._find_persistent_manifest", return_value=object()):
                        with patch("cutctx.cli.wrap._find_free_port", return_value=54321):
                            result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert "using a private proxy on port 54321" in result.output
    assert captured["port"] == 54321
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["OPENAI_BASE_URL"] == "http://127.0.0.1:54321/v1"
    assert env["CUTCTX_BASE_URL"] == "http://127.0.0.1:54321"
    override_path = Path(env["OPENCODE_CONFIG"])
    data = json.loads(override_path.read_text())
    assert data["provider"]["opencode-go"]["options"]["baseURL"] == "http://127.0.0.1:54321/v1"
