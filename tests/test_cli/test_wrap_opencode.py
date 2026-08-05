"""Tests for `cutctx wrap opencode` command."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import click
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


ZEN_GO_KEY = "sk-zen-go-from-opencode-auth"
AMBIENT_OPENAI_KEY = "sk-ambient-openai-operator-key"


@pytest.fixture
def zen_go_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Pretend opencode has a zen/go credential, without reading the real home."""
    monkeypatch.setattr("cutctx.cli.wrap._opencode_go_api_key", lambda: ZEN_GO_KEY)
    return ZEN_GO_KEY


def test_write_opencode_go_config_override_creates_provider_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
) -> None:
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))

    override_path = wrap_mod._write_opencode_go_config_override(9999, None)

    data = json.loads(override_path.read_text())
    assert data["provider"]["opencode-go"]["options"]["baseURL"] == "http://127.0.0.1:9999/v1"


def test_write_opencode_go_config_override_merges_existing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
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


def test_write_opencode_go_config_override_names_upstream_and_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
) -> None:
    """The override has to be self-sufficient on a shared proxy: the proxy's
    process-wide OpenAI upstream belongs to other clients, so the request names
    zen/go itself, and the proxy rejects a named upstream that arrives without
    a client credential."""
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))

    override_path = wrap_mod._write_opencode_go_config_override(8787, None)

    options = json.loads(override_path.read_text())["provider"]["opencode-go"]["options"]
    assert options["baseURL"] == "http://127.0.0.1:8787/v1"
    assert options["headers"]["x-cutctx-base-url"] == "https://opencode.ai/zen/go/v1"
    assert options["apiKey"] == zen_go_key


def test_write_opencode_go_config_override_header_matches_proxy_contract() -> None:
    """A mismatch in either half is a silent misroute: the proxy ignores an
    unknown header name, and rejects an upstream outside its allowlist."""
    from urllib.parse import urlsplit

    from cutctx.cli import wrap as wrap_mod
    from cutctx.proxy import openai_upstream

    assert wrap_mod._OPENCODE_GO_UPSTREAM_HEADER == openai_upstream.OVERRIDE_HEADER

    upstream = urlsplit(wrap_mod._OPENCODE_GO_UPSTREAM_URL)
    assert upstream.scheme == "https"
    assert upstream.hostname in openai_upstream.DEFAULT_ALLOWED_HOSTS
    assert any(
        upstream.path.startswith(prefix) for prefix in openai_upstream.DEFAULT_ALLOWED_PATH_PREFIXES
    )


def test_write_opencode_go_config_override_reads_key_from_opencode_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end through the real credential lookup, no helper patched."""
    from cutctx.cli import wrap as wrap_mod

    fake_home = tmp_path / "home"
    monkeypatch.setattr(wrap_mod.Path, "home", classmethod(lambda cls: fake_home))
    auth_dir = fake_home / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    (auth_dir / "auth.json").write_text(
        json.dumps({"opencode-go": {"type": "api", "key": ZEN_GO_KEY}})
    )
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))

    override_path = wrap_mod._write_opencode_go_config_override(8787, None)

    options = json.loads(override_path.read_text())["provider"]["opencode-go"]["options"]
    assert options["apiKey"] == ZEN_GO_KEY


def test_write_opencode_go_config_override_never_uses_ambient_openai_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
) -> None:
    """OPENAI_API_KEY authenticates api.openai.com. Sending it to opencode.ai
    would both fail and leak the operator's key to a third party."""
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", AMBIENT_OPENAI_KEY)

    override_path = wrap_mod._write_opencode_go_config_override(8787, None)

    raw = override_path.read_text()
    options = json.loads(raw)["provider"]["opencode-go"]["options"]
    assert options["apiKey"] == zen_go_key
    assert options["apiKey"] != AMBIENT_OPENAI_KEY
    assert AMBIENT_OPENAI_KEY not in raw


def test_write_opencode_go_config_override_fails_loudly_without_zen_go_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No zen/go key means no override at all — writing one that inherits
    OPENAI_API_KEY would send the operator's key to opencode.ai."""
    import click

    from cutctx.cli import wrap as wrap_mod

    workspace = tmp_path / "workspace"
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(workspace))
    monkeypatch.setenv("OPENAI_API_KEY", AMBIENT_OPENAI_KEY)
    monkeypatch.setattr("cutctx.cli.wrap._opencode_go_api_key", lambda: None)

    with pytest.raises(click.ClickException) as excinfo:
        wrap_mod._write_opencode_go_config_override(8787, None)

    assert "opencode auth login" in str(excinfo.value)
    assert "OPENAI_API_KEY" in str(excinfo.value)
    assert list((workspace / "opencode").glob("*")) == []
    leaked = AMBIENT_OPENAI_KEY.encode()
    written = [path for path in workspace.rglob("*") if path.is_file()]
    assert [path for path in written if leaked in path.read_bytes()] == []


def test_write_opencode_go_config_override_omits_seat_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
) -> None:
    """The seat token lives in a 0600 file with a 72h expiry; copying it into
    client config would both widen its permissions and bake in an expiry."""
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setenv("CUTCTX_USER_TOKEN", "ctu1.seat-token-should-not-be-copied")

    raw = wrap_mod._write_opencode_go_config_override(8787, None).read_text()

    assert "x-cutctx-user-token" not in raw.lower()
    assert "ctu1." not in raw


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_write_opencode_go_config_override_is_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
) -> None:
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))

    override_path = wrap_mod._write_opencode_go_config_override(8787, None)

    assert override_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_write_opencode_go_config_override_tightens_a_loose_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
) -> None:
    """A file left world-readable by an older build must not stay that way
    once a credential is written into it."""
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))
    stale = tmp_path / "opencode" / "config-override-8787.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}")
    stale.chmod(0o644)

    override_path = wrap_mod._write_opencode_go_config_override(8787, None)

    assert override_path == stale
    assert override_path.stat().st_mode & 0o777 == 0o600


def test_write_opencode_go_config_override_preserves_unrelated_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
) -> None:
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))
    existing = tmp_path / "user-opencode-config.json"
    existing.write_text(
        json.dumps(
            {
                "model": "opencode-go/deepseek-v4-flash",
                "plugin": ["oh-my-opencode-slim"],
                "provider": {
                    "kimi-for-coding": {"options": {"baseURL": "https://kimi.example/v1"}},
                    "opencode-go": {
                        "name": "opencode zen",
                        "options": {
                            "timeout": 120,
                            "headers": {"x-user-header": "keep-me"},
                        },
                    },
                },
            }
        )
    )

    override_path = wrap_mod._write_opencode_go_config_override(9999, str(existing))

    data = json.loads(override_path.read_text())
    assert data["model"] == "opencode-go/deepseek-v4-flash"
    assert data["plugin"] == ["oh-my-opencode-slim"]
    assert data["provider"]["kimi-for-coding"]["options"]["baseURL"] == "https://kimi.example/v1"
    opencode_go = data["provider"]["opencode-go"]
    assert opencode_go["name"] == "opencode zen"
    assert opencode_go["options"]["timeout"] == 120
    assert opencode_go["options"]["headers"]["x-user-header"] == "keep-me"
    assert opencode_go["options"]["headers"]["x-cutctx-base-url"] == (
        "https://opencode.ai/zen/go/v1"
    )
    assert opencode_go["options"]["baseURL"] == "http://127.0.0.1:9999/v1"
    assert opencode_go["options"]["apiKey"] == zen_go_key


@pytest.mark.parametrize("payload", ['["not", "a", "mapping"]', "not json at all", '"scalar"'])
def test_write_opencode_go_config_override_survives_unusable_existing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str, payload: str
) -> None:
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))
    existing = tmp_path / "user-opencode-config.json"
    existing.write_text(payload)

    override_path = wrap_mod._write_opencode_go_config_override(9999, str(existing))

    options = json.loads(override_path.read_text())["provider"]["opencode-go"]["options"]
    assert options["baseURL"] == "http://127.0.0.1:9999/v1"
    assert options["apiKey"] == zen_go_key


def test_apply_opencode_go_proxy_config_is_reusable_for_durable_config(
    tmp_path: Path,
) -> None:
    """The same merge is what a durable ~/.config/opencode/opencode.json
    cutover needs, so it stays separable from the wrap-scoped file writer."""
    from cutctx.cli import wrap as wrap_mod

    durable = {
        "$schema": "https://opencode.ai/config.json",
        "model": "opencode-go/deepseek-v4-flash",
        "provider": {"opencode-go": {"options": {"baseURL": "http://127.0.0.1:8790/v1"}}},
    }

    wrap_mod._apply_opencode_go_proxy_config(durable, port=8787, api_key=ZEN_GO_KEY)

    assert durable["$schema"] == "https://opencode.ai/config.json"
    assert durable["model"] == "opencode-go/deepseek-v4-flash"
    options = durable["provider"]["opencode-go"]["options"]
    assert options["baseURL"] == "http://127.0.0.1:8787/v1"
    assert options["headers"]["x-cutctx-base-url"] == "https://opencode.ai/zen/go/v1"
    assert options["apiKey"] == ZEN_GO_KEY


@contextmanager
def _opencode_go_run(
    *,
    capability: bool,
    api_key: str | None,
    captured: dict[str, object],
    manifest: object | None = None,
    free_port: int = 54321,
    reusable: bool = True,
    launch: Callable[..., object] | None = None,
) -> Iterator[None]:
    """Patch `wrap opencode` down to the opencode-go routing decision.

    `capability` is what the proxy on the requested port advertises on
    /health; `api_key` is what opencode has stored for opencode-go; `reusable`
    is whether that proxy can be attached to without `_ensure_proxy` wanting
    to restart it. All three must hold for the session to share the port.
    """

    def fake_launch_tool(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        override = kwargs["env"].get("OPENCODE_CONFIG")
        if override is not None:
            captured["opencode_config"] = json.loads(Path(override).read_text())
        if launch is not None:
            return launch(**kwargs)
        return None

    with ExitStack() as stack:
        stack.enter_context(patch("cutctx.cli.wrap.shutil.which", return_value="opencode"))
        stack.enter_context(patch("cutctx.cli.wrap._launch_tool", side_effect=fake_launch_tool))
        stack.enter_context(
            patch("cutctx.cli.wrap._opencode_has_routable_credentials", return_value=False)
        )
        stack.enter_context(patch("cutctx.cli.wrap._opencode_go_configured", return_value=True))
        stack.enter_context(patch("cutctx.cli.wrap._opencode_go_api_key", return_value=api_key))
        stack.enter_context(
            patch(
                "cutctx.cli.wrap._proxy_supports_per_request_openai_base_url",
                return_value=capability,
            )
        )
        stack.enter_context(
            patch("cutctx.cli.wrap._shared_proxy_is_reusable_as_is", return_value=reusable)
        )
        stack.enter_context(
            patch("cutctx.cli.wrap._find_persistent_manifest", return_value=manifest)
        )
        stack.enter_context(patch("cutctx.cli.wrap._find_free_port", return_value=free_port))
        yield


def test_wrap_opencode_routes_opencode_go_through_proxy(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    with _opencode_go_run(capability=False, api_key="oc-key", captured=captured):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert "no 'anthropic' or 'openai' credentials" not in result.output
    assert captured["openai_api_url"] == "https://opencode.ai/zen/go/v1"
    env = captured["env"]
    assert isinstance(env, dict)
    override_path = Path(env["OPENCODE_CONFIG"])
    assert not override_path.exists()
    data = captured["opencode_config"]
    assert isinstance(data, dict)
    assert data["provider"]["opencode-go"]["options"]["baseURL"] == "http://127.0.0.1:8787/v1"


@pytest.mark.parametrize("launch_raises", [False, True], ids=["success", "exception"])
def test_wrap_opencode_removes_generated_override_after_launch(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launch_raises: bool
) -> None:
    """The generated secret config exists for opencode only, even if launch fails."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    observed_paths: list[Path] = []

    def inspect_launch(**kwargs):  # noqa: ANN003
        override_path = Path(kwargs["env"]["OPENCODE_CONFIG"])
        assert override_path.is_file()
        observed_paths.append(override_path)
        if launch_raises:
            raise RuntimeError("opencode failed to launch")

    with _opencode_go_run(
        capability=False,
        api_key="oc-key",
        captured={},
        launch=inspect_launch,
    ):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == (1 if launch_raises else 0), result.output
    assert len(observed_paths) == 1
    assert not observed_paths[0].exists()


def test_wrap_opencode_auto_reassigns_port_when_shared_proxy_cant_route_opencode_go(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A persistent, shared proxy that doesn't advertise per-request upstream
    overrides can never honor an opencode-go upstream override
    (DeploymentManifest has no such field) — rather than fail or silently
    misroute, pick a private port for this session automatically."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    with _opencode_go_run(capability=False, api_key="oc-key", captured=captured, manifest=object()):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert "using a private proxy on port 54321" in result.output
    assert captured["port"] == 54321
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["OPENAI_BASE_URL"] == "http://127.0.0.1:54321/v1"
    assert env["CUTCTX_BASE_URL"] == "http://127.0.0.1:54321"
    override_path = Path(env["OPENCODE_CONFIG"])
    assert not override_path.exists()
    data = captured["opencode_config"]
    assert isinstance(data, dict)
    assert data["provider"]["opencode-go"]["options"]["baseURL"] == "http://127.0.0.1:54321/v1"


def test_wrap_opencode_stays_on_shared_port_when_proxy_honors_per_request_upstream(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Capability advertised + an opencode-go key to authenticate with: the
    session rides the shared proxy. Passing a process-wide upstream here is
    what used to force the private port, so it must not be passed at all."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    # A persistent manifest is present, i.e. the exact shape that used to
    # trigger the private-port swap.
    with _opencode_go_run(capability=True, api_key="oc-key", captured=captured, manifest=object()):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert "private proxy on port" not in result.output
    assert "honors per-request upstream overrides" in result.output
    assert captured["port"] == 8787
    assert captured["openai_api_url"] is None
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["OPENAI_BASE_URL"] == "http://127.0.0.1:8787/v1"
    assert env["CUTCTX_BASE_URL"] == "http://127.0.0.1:8787"
    override_path = Path(env["OPENCODE_CONFIG"])
    assert not override_path.exists()
    data = captured["opencode_config"]
    assert isinstance(data, dict)
    options = data["provider"]["opencode-go"]["options"]
    assert options["baseURL"] == "http://127.0.0.1:8787/v1"
    # Staying on the shared port is only safe because the override names the
    # upstream per request instead of relying on the proxy's process-wide one.
    assert options["headers"]["x-cutctx-base-url"] == "https://opencode.ai/zen/go/v1"
    assert options["apiKey"] == "oc-key"


def test_wrap_opencode_keeps_private_port_when_no_opencode_go_api_key(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The proxy rejects an override with no client credential (401), so a
    capability alone is not enough to share the port. The session falls back to
    the private port, and then refuses outright rather than launching opencode
    with a credential-less override."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    with _opencode_go_run(capability=True, api_key=None, captured=captured, manifest=object()):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert "honors per-request upstream overrides" not in result.output
    assert "using a private proxy on port 54321" in result.output
    assert "no usable API key" in result.output
    assert captured == {}


def test_wrap_opencode_does_not_probe_capability_without_opencode_go_routing(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No opencode-go routing means no upstream override to place, so the
    shared-port question never arises and /health is left alone."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with patch("cutctx.cli.wrap.shutil.which", return_value="opencode"):
        with patch("cutctx.cli.wrap._launch_tool"):
            with patch("cutctx.cli.wrap._opencode_go_configured", return_value=False):
                with patch("cutctx.cli.wrap._proxy_supports_per_request_openai_base_url") as probe:
                    result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    probe.assert_not_called()


def test_opencode_go_api_key_reads_auth_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cutctx.cli import wrap as wrap_mod

    fake_home = tmp_path
    monkeypatch.setattr(wrap_mod.Path, "home", classmethod(lambda cls: fake_home))

    assert wrap_mod._opencode_go_api_key() is None

    auth_dir = fake_home / ".local" / "share" / "opencode"
    auth_dir.mkdir(parents=True)
    auth_path = auth_dir / "auth.json"

    auth_path.write_text('{"opencode-go": {}}')
    assert wrap_mod._opencode_go_api_key() is None

    auth_path.write_text('{"opencode-go": {"type": "api", "key": "  oc-key  "}}')
    assert wrap_mod._opencode_go_api_key() == "oc-key"

    auth_path.write_text('{"opencode-go": {"type": "oauth", "access": "oc-token"}}')
    assert wrap_mod._opencode_go_api_key() == "oc-token"

    auth_path.write_text("not json")
    assert wrap_mod._opencode_go_api_key() is None


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (None, False),
        ({}, False),
        ({"capabilities": {}}, False),
        ({"capabilities": {"per_request_openai_base_url": False}}, False),
        ({"capabilities": {"per_request_openai_base_url": "true"}}, False),
        ({"capabilities": {"per_request_openai_base_url": True}}, True),
        ({"per_request_openai_base_url": True}, True),
    ],
)
def test_proxy_supports_per_request_openai_base_url(payload: object, expected: bool) -> None:
    from cutctx.cli import wrap as wrap_mod

    with patch("cutctx.cli.wrap._query_proxy_health", return_value=payload):
        assert wrap_mod._proxy_supports_per_request_openai_base_url(8787) is expected


def test_wrap_opencode_shared_port_forbids_touching_the_shared_proxy(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sharing 8787 means codex/claude are on it too. `_ensure_proxy` must be
    told it may only reuse what is already there — with no process-wide
    upstream to trigger it, a version-stale or momentarily unhealthy listener
    would otherwise be restarted with this session's flags."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    with _opencode_go_run(capability=True, api_key="oc-key", captured=captured, manifest=object()):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert captured["port"] == 8787
    assert captured["reuse_only"] is True


def test_wrap_opencode_private_port_still_allows_starting_a_proxy(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The private port is this session's own; nothing else depends on it, so
    the reuse-only restriction must not leak onto that path."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    with _opencode_go_run(capability=False, api_key="oc-key", captured=captured, manifest=object()):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert captured["port"] == 54321
    assert captured["reuse_only"] is False
    assert captured["post_proxy_check"] is None


def test_wrap_opencode_falls_back_to_private_port_when_shared_proxy_needs_restarting(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Capability + key are not enough. A listener `_ensure_proxy` would want
    to restart or recover must be left alone, and the session takes the
    private port while that fallback is still available."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    with _opencode_go_run(
        capability=True,
        api_key="oc-key",
        captured=captured,
        manifest=object(),
        reusable=False,
    ):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    assert "will not restart it" in result.output
    assert "using a private proxy on port 54321" in result.output
    assert captured["port"] == 54321
    assert captured["reuse_only"] is False
    assert captured["openai_api_url"] == "https://opencode.ai/zen/go/v1"


def test_wrap_opencode_rechecks_capability_after_the_proxy_step(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The capability was probed before `_ensure_proxy` ran. The port and the
    config override are committed by the time it returns, so if the listener
    changed underneath us the only honest outcome is to abort — continuing
    would 400 every request."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    captured: dict[str, object] = {}

    with _opencode_go_run(capability=True, api_key="oc-key", captured=captured, manifest=object()):
        result = runner.invoke(main, ["wrap", "opencode", "--no-rtk"])

    assert result.exit_code == 0, result.output
    recheck = captured["post_proxy_check"]
    assert callable(recheck)

    with patch("cutctx.cli.wrap._proxy_supports_per_request_openai_base_url", return_value=True):
        assert recheck() is None

    with patch("cutctx.cli.wrap._proxy_supports_per_request_openai_base_url", return_value=False):
        with pytest.raises(click.ClickException) as excinfo:
            recheck()

    assert "no longer advertises per-request" in str(excinfo.value)
    assert "--port" in str(excinfo.value)


def test_launch_tool_forwards_reuse_only_and_runs_the_post_proxy_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both knobs are useless if `_launch_tool` drops them, and the recheck
    has to run before the tool is spawned, not after."""
    from cutctx.auth.client_credentials import ClientCredential
    from cutctx.cli import wrap as wrap_mod

    calls: list[str] = []
    ensure = Mock(return_value=None)

    def recheck() -> None:
        calls.append("recheck")

    monkeypatch.setattr(wrap_mod, "_register_proxy_client", lambda port: None)
    monkeypatch.setattr(wrap_mod, "_make_cleanup", lambda holder, port: lambda *a: None)
    monkeypatch.setattr(
        wrap_mod,
        "_apply_wrap_client_auth",
        lambda env, origin: ClientCredential(origin, "test-client-key", "keyring"),
    )
    monkeypatch.setattr(wrap_mod, "_validate_wrap_client_auth", lambda *args: None)
    monkeypatch.setattr(wrap_mod, "_ensure_proxy", ensure)
    monkeypatch.setattr(wrap_mod.signal, "signal", lambda sig, fn: None)
    monkeypatch.setattr(
        wrap_mod.subprocess,
        "run",
        lambda *args, **kwargs: calls.append("spawn") or SimpleNamespace(returncode=0),
    )

    with pytest.raises(SystemExit):
        wrap_mod._launch_tool(
            binary="opencode",
            args=(),
            env={},
            port=8787,
            no_proxy=False,
            tool_label="OPENCODE",
            env_vars_display=[],
            reuse_only=True,
            post_proxy_check=recheck,
        )

    assert ensure.call_args.kwargs["reuse_only"] is True
    assert calls == ["recheck", "spawn"]


def _reuse_only_proxy(
    monkeypatch: pytest.MonkeyPatch, *, running: bool, ready: bool = True
) -> dict[str, Mock]:
    """Pin a shared, version-stale persistent deployment on port 8787.

    Version-stale and manifest-backed is precisely the shape that sends
    `_ensure_proxy` into `_restart_persistent_proxy`, so a passing test here
    means the reuse-only guard preempted a restart that would otherwise have
    happened.
    """
    from cutctx.cli import wrap as wrap_mod
    from cutctx.install import health as install_health

    mocks = {"restart": Mock(return_value=True), "recover": Mock(return_value=True)}
    manifest = SimpleNamespace(
        profile="default",
        health_url="http://127.0.0.1:8787/health",
        targets=["codex"],
        preset="persistent-agent",
        supervisor_kind="agent",
    )
    monkeypatch.setattr(wrap_mod, "_find_persistent_manifest", lambda port: manifest)
    monkeypatch.setattr(wrap_mod, "_check_proxy", lambda port: running)
    monkeypatch.setattr(wrap_mod, "_check_proxy_ready", lambda port, *a, **k: ready)
    monkeypatch.setattr(install_health, "probe_ready", lambda url, **kwargs: running)
    monkeypatch.setattr(wrap_mod, "_query_proxy_health", lambda port: {"version": "0.0.1-stale"})
    monkeypatch.setattr(wrap_mod, "_proxy_needs_version_restart", lambda payload: True)
    monkeypatch.setattr(wrap_mod, "_live_proxy_clients", lambda port, exclude_self=False: [])
    monkeypatch.setattr(wrap_mod, "_restart_persistent_proxy", mocks["restart"])
    monkeypatch.setattr(wrap_mod, "_recover_persistent_proxy", mocks["recover"])
    monkeypatch.setattr(
        wrap_mod,
        "_start_proxy",
        Mock(side_effect=AssertionError("reuse-only must not start a proxy")),
    )
    return mocks


def test_ensure_proxy_reuse_only_never_restarts_a_shared_persistent_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Must-fix: with no process-wide upstream to object to, the stale-version
    branch would restart the persistent 8787 deployment — relaunching it with
    this session's flags and taking the override capability away from codex
    and from this session at the same time."""
    from cutctx.cli import wrap as wrap_mod

    mocks = _reuse_only_proxy(monkeypatch, running=True)

    assert wrap_mod._ensure_proxy(8787, False, agent_type="opencode", reuse_only=True) is None
    mocks["restart"].assert_not_called()
    mocks["recover"].assert_not_called()


def test_ensure_proxy_reuse_only_aborts_instead_of_recovering_a_dead_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing to reuse is a hard stop, not an invitation to start one: the
    caller committed to a shared port on the strength of a proxy that was
    healthy a moment ago."""
    from cutctx.cli import wrap as wrap_mod

    mocks = _reuse_only_proxy(monkeypatch, running=False)

    with pytest.raises(click.ClickException) as excinfo:
        wrap_mod._ensure_proxy(8787, False, agent_type="opencode", reuse_only=True)

    assert "will not start, restart or recover" in str(excinfo.value)
    mocks["restart"].assert_not_called()
    mocks["recover"].assert_not_called()


def test_ensure_proxy_without_reuse_only_still_restarts_a_stale_deployment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard is opt-in: every other wrap target keeps today's behavior."""
    from cutctx.cli import wrap as wrap_mod

    mocks = _reuse_only_proxy(monkeypatch, running=True)

    assert wrap_mod._ensure_proxy(8787, False, agent_type="codex") is None
    mocks["restart"].assert_called_once()


@pytest.mark.parametrize(
    ("running", "ready", "version_restart", "expected"),
    [
        (True, True, False, True),
        (True, True, True, False),
        (True, False, False, False),
        (False, True, False, False),
    ],
)
def test_shared_proxy_is_reusable_as_is(
    running: bool, ready: bool, version_restart: bool, expected: bool
) -> None:
    from cutctx.cli import wrap as wrap_mod

    with ExitStack() as stack:
        stack.enter_context(patch("cutctx.cli.wrap._check_proxy", return_value=running))
        stack.enter_context(patch("cutctx.cli.wrap._check_proxy_ready", return_value=ready))
        stack.enter_context(patch("cutctx.cli.wrap._query_proxy_health", return_value={}))
        stack.enter_context(
            patch("cutctx.cli.wrap._proxy_needs_version_restart", return_value=version_restart)
        )
        assert wrap_mod._shared_proxy_is_reusable_as_is(8787) is expected


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits")
def test_write_opencode_go_config_override_is_private_from_the_first_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, zen_go_key: str
) -> None:
    """`os.open`'s mode only applies when it creates the file. A `.tmp` left
    at 0644 by an older build or a crashed run is reopened with that mode, so
    without an explicit narrowing the credential lands in a world-readable
    file and `os.replace` carries 0644 onto the final path."""
    from cutctx.cli import wrap as wrap_mod

    monkeypatch.setenv("CUTCTX_WORKSPACE_DIR", str(tmp_path))
    override_dir = tmp_path / "opencode"
    override_dir.mkdir(parents=True)
    stale_tmp = override_dir / "config-override-8787.json.tmp"
    stale_tmp.write_text("{}")
    stale_tmp.chmod(0o644)

    observed_mode: list[int] = []
    observed_bytes: list[bytes] = []
    real_replace = os.replace

    def spy_replace(src: object, dst: object) -> None:
        observed_mode.append(Path(str(src)).stat().st_mode & 0o777)
        observed_bytes.append(Path(str(src)).read_bytes())
        real_replace(str(src), str(dst))

    monkeypatch.setattr(wrap_mod.os, "replace", spy_replace)
    override_path = wrap_mod._write_opencode_go_config_override(8787, None)
    monkeypatch.undo()

    # The credential is already on disk at the moment the mode is sampled, so
    # 0600 here means it was never readable as 0644 mid-write.
    assert zen_go_key.encode() in observed_bytes[0]
    assert observed_mode == [0o600]
    assert override_path.stat().st_mode & 0o777 == 0o600


def test_opencode_go_can_share_proxy_port_requires_both_halves() -> None:
    from cutctx.cli import wrap as wrap_mod

    for api_key, capability, expected in (
        ("oc-key", True, True),
        ("oc-key", False, False),
        (None, True, False),
        (None, False, False),
    ):
        with patch("cutctx.cli.wrap._opencode_go_api_key", return_value=api_key):
            with patch(
                "cutctx.cli.wrap._proxy_supports_per_request_openai_base_url",
                return_value=capability,
            ):
                assert wrap_mod._opencode_go_can_share_proxy_port(8787) is expected
