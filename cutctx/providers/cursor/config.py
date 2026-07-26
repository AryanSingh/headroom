"""Cursor proxy configuration helpers.

Cursor does not honor ``OPENAI_BASE_URL`` / ``ANTHROPIC_BASE_URL`` the way CLI
agents do. Cutctx writes project-scoped ``.cursor/config.json`` and optional
user ``settings.json`` keys so BYOK traffic can reach the local proxy without
manual copy/paste.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cutctx.providers.claude import proxy_base_url as claude_proxy_base_url
from cutctx.providers.codex import proxy_base_url as codex_proxy_base_url
from cutctx.proxy.project_context import with_project_prefix

_CUTCTX_META_KEY = "_cutctx"
_OPENAI_BASE_URL_KEY = "cursor.openai.apiBaseUrl"
_ANTHROPIC_BASE_URL_KEY = "cursor.anthropic.apiBaseUrl"


@dataclass(frozen=True)
class CursorConfigResult:
    """Outcome of applying Cursor proxy configuration."""

    project_config: Path | None
    user_settings: Path | None
    openai_base_url: str
    anthropic_base_url: str


def cursor_user_settings_path(*, home_dir: Path | None = None) -> Path:
    """Return Cursor's user-level settings.json path for the current OS."""
    home = home_dir if home_dir is not None else Path.home()
    if sys.platform == "darwin":
        return home / "Library/Application Support/Cursor/User/settings.json"
    if os_name_nt():
        appdata = Path.home() / "AppData/Roaming"
        return appdata / "Cursor/User/settings.json"
    return home / ".config/Cursor/User/settings.json"


def os_name_nt() -> bool:
    return sys.platform == "win32"


def project_config_path(cwd: Path | None = None) -> Path:
    """Return the project-scoped Cursor config path."""
    return (cwd or Path.cwd()) / ".cursor" / "config.json"


def project_mcp_path(cwd: Path | None = None) -> Path:
    """Return the project-scoped Cursor MCP config path."""
    return (cwd or Path.cwd()) / ".cursor" / "mcp.json"


def build_proxy_urls(port: int, project: str | None = None) -> tuple[str, str]:
    """Build OpenAI and Anthropic proxy base URLs for Cursor."""
    openai = with_project_prefix(codex_proxy_base_url(port), project)
    anthropic = with_project_prefix(claude_proxy_base_url(port), project)
    return openai, anthropic


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def apply_proxy_config(
    *,
    port: int,
    project: str | None = None,
    cwd: Path | None = None,
    include_user_settings: bool = False,
    home_dir: Path | None = None,
) -> CursorConfigResult:
    """Write Cutctx proxy URLs into Cursor project and optional user config."""
    openai_url, anthropic_url = build_proxy_urls(port, project)
    root = (cwd or Path.cwd()).resolve()
    project_path = project_config_path(root)
    project_payload = _read_json(project_path)
    openai_value = project_payload.get("openai")
    project_payload["openai"] = {
        **(openai_value if isinstance(openai_value, dict) else {}),
        "baseUrl": openai_url,
    }
    anthropic_value = project_payload.get("anthropic")
    project_payload["anthropic"] = {
        **(anthropic_value if isinstance(anthropic_value, dict) else {}),
        "baseUrl": anthropic_url,
    }
    project_payload[_CUTCTX_META_KEY] = {
        "proxy_port": port,
        "project": project,
    }
    _write_json(project_path, project_payload)

    user_path: Path | None = None
    if include_user_settings:
        user_path = cursor_user_settings_path(home_dir=home_dir)
        user_payload = _read_json(user_path)
        user_payload[_OPENAI_BASE_URL_KEY] = openai_url
        user_payload[_ANTHROPIC_BASE_URL_KEY] = anthropic_url
        _write_json(user_path, user_payload)

    return CursorConfigResult(
        project_config=project_path,
        user_settings=user_path,
        openai_base_url=openai_url,
        anthropic_base_url=anthropic_url,
    )


def revert_proxy_config(
    *,
    cwd: Path | None = None,
    include_user_settings: bool = False,
    home_dir: Path | None = None,
) -> bool:
    """Remove Cutctx-managed proxy URLs from Cursor config files."""
    changed = False
    root = (cwd or Path.cwd()).resolve()
    project_path = project_config_path(root)
    if project_path.exists():
        payload = _read_json(project_path)
        meta = payload.get(_CUTCTX_META_KEY)
        if isinstance(meta, dict):
            for provider in ("openai", "anthropic"):
                section = payload.get(provider)
                if isinstance(section, dict):
                    section.pop("baseUrl", None)
                    if not section:
                        payload.pop(provider, None)
                    else:
                        payload[provider] = section
            payload.pop(_CUTCTX_META_KEY, None)
            if payload:
                _write_json(project_path, payload)
            else:
                project_path.unlink(missing_ok=True)
            changed = True

    if include_user_settings:
        user_path = cursor_user_settings_path(home_dir=home_dir)
        if user_path.exists():
            payload = _read_json(user_path)
            if payload.pop(_OPENAI_BASE_URL_KEY, None) is not None:
                changed = True
            if payload.pop(_ANTHROPIC_BASE_URL_KEY, None) is not None:
                changed = True
            if payload:
                _write_json(user_path, payload)
            else:
                user_path.unlink(missing_ok=True)

    return changed


__all__ = [
    "CursorConfigResult",
    "apply_proxy_config",
    "build_proxy_urls",
    "cursor_user_settings_path",
    "project_config_path",
    "project_mcp_path",
    "revert_proxy_config",
]
