from __future__ import annotations

import tomllib

from cutctx.mcp_registry import CodexRegistrar
from cutctx.mcp_registry.install import DEFAULT_PROXY_URL, build_cutctx_spec
from cutctx.providers.codex.install import build_provider_section


def test_codex_provider_section_no_requires_openai_auth() -> None:
    """Bug 3 (#406): build_provider_section must NOT include requires_openai_auth.

    Setting requires_openai_auth on a custom [model_providers.cutctx] block
    forces codex to demand OpenAI OAuth login for every Cutctx-routed request.
    Cutctx is a local proxy — it must never carry this flag.
    """
    section = build_provider_section(port=8787, name="OpenAI via Cutctx proxy")

    assert 'name = "OpenAI via Cutctx proxy"' in section
    assert 'base_url = "http://127.0.0.1:8787/v1"' in section
    assert "requires_openai_auth" not in section, (
        f"requires_openai_auth must be absent from the Cutctx provider section; got:\n{section}"
    )
    assert "supports_websockets = true" in section
    assert 'env_key = "OPENAI_API_KEY"' not in section
    assert "[model_providers.cutctx]" in section


def test_codex_provider_section_supports_custom_markers() -> None:
    section = build_provider_section(
        port=9100,
        name="Cutctx init proxy",
        marker_start="# --- start ---",
        marker_end="# --- end ---",
    )

    assert section.startswith("# --- start ---\n")
    assert section.endswith("# --- end ---\n")
    assert 'base_url = "http://127.0.0.1:9100/v1"' in section
    assert 'env_key = "OPENAI_API_KEY"' not in section


def test_cutctx_spec_always_pins_the_proxy_url() -> None:
    """Audit-2026-08-03: the default port used to yield an empty env block."""
    assert build_cutctx_spec(DEFAULT_PROXY_URL).env == {"CUTCTX_PROXY_URL": DEFAULT_PROXY_URL}


def test_wrap_codex_default_port_preserves_cutctx_proxy_url(tmp_path, monkeypatch) -> None:
    """`wrap codex` must not delete the CUTCTX_PROXY_URL a prior run wrote.

    The registrar rewrites the whole ``# --- Cutctx MCP server ---`` block, so
    a spec with an empty ``env`` silently dropped ``[mcp_servers.cutctx.env]``
    and left ``cutctx_retrieve`` with no proxy binding.
    """
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    config_file = tmp_path / "config.toml"

    # Run 1: an ephemeral port, as chosen when 8787 is already in use.
    CodexRegistrar().register_server(build_cutctx_spec("http://127.0.0.1:55756"), force=True)
    assert "CUTCTX_PROXY_URL" in config_file.read_text()

    # Run 2: `cutctx wrap codex` with no --port, i.e. the default.
    CodexRegistrar().register_server(build_cutctx_spec(DEFAULT_PROXY_URL), force=True)

    data = tomllib.loads(config_file.read_text())
    env = data["mcp_servers"]["cutctx"].get("env", {})
    assert env.get("CUTCTX_PROXY_URL") == DEFAULT_PROXY_URL
