"""Cursor-specific provider helpers."""

from .cli import (
    CURSOR_AGENT_BIN_ENV,
    CURSOR_IDE_BIN_ENV,
    build_agent_endpoint_url,
    build_agent_header_args,
    build_agent_launch_args,
    find_agent_cli,
    find_ide_cli,
)
from .config import (
    CursorConfigResult,
    apply_proxy_config,
    build_proxy_urls,
    cursor_user_settings_path,
    project_config_path,
    project_mcp_path,
    revert_proxy_config,
)
from .hooks import (
    build_hooks_payload,
    ensure_project_hooks,
    project_hooks_path,
    remove_project_hooks,
)
from .runtime import CursorProxyTargets, build_proxy_targets, render_setup_lines
from .upstream import (
    CURSOR_IDE_MODEL_PREFIX,
    CURSOR_TARGET_API_URL_ENV,
    DEFAULT_CURSOR_API_URL,
    is_cursor_client,
    resolve_cursor_target_api_url,
    strip_cursor_ide_model_prefix,
)

__all__ = [
    "CURSOR_AGENT_BIN_ENV",
    "CURSOR_IDE_BIN_ENV",
    "CURSOR_IDE_MODEL_PREFIX",
    "CURSOR_TARGET_API_URL_ENV",
    "DEFAULT_CURSOR_API_URL",
    "CursorConfigResult",
    "CursorProxyTargets",
    "apply_proxy_config",
    "build_agent_endpoint_url",
    "build_agent_header_args",
    "build_agent_launch_args",
    "build_hooks_payload",
    "build_proxy_targets",
    "build_proxy_urls",
    "cursor_user_settings_path",
    "ensure_project_hooks",
    "find_agent_cli",
    "find_ide_cli",
    "is_cursor_client",
    "project_config_path",
    "project_hooks_path",
    "project_mcp_path",
    "remove_project_hooks",
    "render_setup_lines",
    "resolve_cursor_target_api_url",
    "revert_proxy_config",
    "strip_cursor_ide_model_prefix",
]
