from __future__ import annotations

from unittest.mock import patch

from cutctx.providers.cursor import (
    build_proxy_targets,
    render_cli_setup_lines,
    render_setup_lines,
)
from cutctx.providers.cursor.install import build_install_env


def test_cursor_proxy_targets_use_local_cutctx_proxy() -> None:
    targets = build_proxy_targets(9999)

    assert targets.openai_base_url == "http://127.0.0.1:9999/v1"
    assert targets.anthropic_base_url == "http://127.0.0.1:9999"


def test_cursor_setup_lines_include_both_provider_urls() -> None:
    lines = render_setup_lines(8787)
    joined = "\n".join(lines)

    assert "http://127.0.0.1:8787/v1" in joined
    assert "http://127.0.0.1:8787" in joined


def test_cursor_build_install_env_returns_both_proxy_urls() -> None:
    # Arrange / Act
    env = build_install_env(port=7654, backend="ignored")

    # Assert
    assert env == {
        "OPENAI_BASE_URL": "http://127.0.0.1:7654/v1",
        "ANTHROPIC_BASE_URL": "http://127.0.0.1:7654",
    }


def test_cursor_proxy_targets_apply_project_path_prefix() -> None:
    targets = build_proxy_targets(9999, project="frontend")

    assert targets.openai_base_url == "http://127.0.0.1:9999/p/frontend/v1"
    assert targets.anthropic_base_url == "http://127.0.0.1:9999/p/frontend"


def test_cursor_setup_lines_mention_project_attribution() -> None:
    lines = render_setup_lines(8787, project="frontend")
    joined = "\n".join(lines)

    assert "http://127.0.0.1:8787/p/frontend/v1" in joined
    assert "attributed to project 'frontend'" in joined

    plain = "\n".join(render_setup_lines(8787))
    assert "attributed" not in plain


def test_cursor_cli_setup_lines_state_the_mcp_surface() -> None:
    lines = render_cli_setup_lines(8787, mcp_state="ready")
    joined = "\n".join(lines)

    assert "ready" in joined
    assert "http://127.0.0.1:8787" in joined
    assert "cutctx_compress" in joined


def test_cursor_cli_setup_lines_disclose_what_is_not_routed() -> None:
    """A user who expects proxy savings here must be told they won't get them."""
    joined = "\n".join(render_cli_setup_lines(8787, mcp_state=None))

    assert "Not covered" in joined
    assert "protobuf" in joined
    assert "cutctx wrap claude" in joined


def test_detect_targets_finds_cli_only_cursor_install() -> None:
    """A CLI-only install has cursor-agent but no `cursor` on PATH."""
    from cutctx.install import planner

    def fake_which(binary: str) -> str | None:
        return "/usr/local/bin/cursor-agent" if binary == "cursor-agent" else None

    with patch.object(planner.shutil, "which", side_effect=fake_which):
        assert "cursor" in planner.detect_targets()


def test_detect_targets_omits_cursor_when_neither_binary_present() -> None:
    from cutctx.install import planner

    with patch.object(planner.shutil, "which", return_value=None):
        assert "cursor" not in planner.detect_targets()
