"""Runtime helpers for Cursor integrations."""

from __future__ import annotations

from dataclasses import dataclass

from cutctx.providers.claude import proxy_base_url as claude_proxy_base_url
from cutctx.providers.codex import proxy_base_url as codex_proxy_base_url
from cutctx.providers.cursor.cli import find_agent_cli, find_ide_cli
from cutctx.proxy.project_context import with_project_prefix


@dataclass(frozen=True)
class CursorProxyTargets:
    """Resolved local proxy targets shown in Cursor setup instructions."""

    openai_base_url: str
    anthropic_base_url: str


def build_proxy_targets(port: int, project: str | None = None) -> CursorProxyTargets:
    """Build the local proxy URLs shown to Cursor users.

    ``project`` (the wrap launch directory) is encoded as a ``/p/<name>``
    base-URL prefix because Cursor cannot send custom headers; the proxy
    strips it and attributes savings per project.
    """
    return CursorProxyTargets(
        openai_base_url=with_project_prefix(codex_proxy_base_url(port), project),
        anthropic_base_url=with_project_prefix(claude_proxy_base_url(port), project),
    )


#: Binary name of the Cursor CLI agent. Note this is *not* ``cursor`` — that
#: is the app's shell launcher, which is why plain ``which("cursor")`` misses
#: a CLI-only install.
CLI_BINARY = "cursor-agent"


def render_cli_setup_lines(port: int, *, mcp_state: str | None) -> list[str]:
    """Render what Cutctx does and does not cover for ``cursor-agent``.

    The CLI sends binary protobuf (Connect RPC) to Cursor's own backend, so
    unlike Claude Code there is no base URL to repoint: compression and model
    routing cannot apply to its model traffic. Saying so plainly is the point
    of this block — a user who expects proxy savings here and is not told
    otherwise will read a flat savings chart as a bug.
    """
    lines = [
        "  Cursor CLI is wired to Cutctx over MCP:",
        "",
        f"    cutctx MCP server:  {mcp_state or 'registered in ~/.cursor/mcp.json'}",
        f"    Proxy (MCP backend): http://127.0.0.1:{port}",
        "",
        "  Available in-session: cutctx_compress, cutctx_retrieve, cutctx_scan,",
        "  cutctx_stats, cutctx_audit — plus gateway-compressed output from any",
        "  other MCP server (`cutctx mcp install --gateway`).",
        "",
        "  Not covered: cursor-agent sends binary protobuf to Cursor's own",
        "  backend, so its model traffic cannot be compressed or re-routed by",
        "  the proxy. For the full pipeline use `cutctx wrap claude`, or the",
        "  Cursor app in BYOK mode (`cutctx wrap cursor`).",
    ]
    return lines


def render_setup_lines(port: int, project: str | None = None) -> list[str]:
    """Render the Cursor setup instructions for the local proxy."""
    targets = build_proxy_targets(port, project)
    lines = [
        "  Cutctx proxy is running. Cursor harness configuration applied:",
        "",
        "  Project config:  .cursor/config.json",
        "  Harness hooks:   .cursor/hooks.json",
        "  MCP registry:    .cursor/mcp.json and ~/.cursor/mcp.json (when installed)",
        "",
        "  App (IDE): open this workspace in Cursor — BYOK models use the URLs below.",
        "  CLI: run `cutctx wrap cursor --launch-cli` or pass agent args after `--`.",
        "",
        "  For OpenAI models:",
        f"    Base URL:  {targets.openai_base_url}",
        "    API Key:   your-openai-api-key",
        "",
        "  For Anthropic models:",
        f"    Base URL:  {targets.anthropic_base_url}",
        "    API Key:   your-anthropic-api-key",
        "",
        "  Cursor reads project config automatically. If you use global BYOK",
        "  settings instead, open Cursor Settings > Models and confirm the",
        f"  override base URL matches: {targets.openai_base_url}",
        "",
        "  IDE Agent workaround for built-in model names:",
        "    Add a custom model named cutctx-<slug> (e.g. cutctx-gpt-4o).",
        "    Cursor hijacks gpt-* / claude-* to api2.cursor.sh; the cutctx-",
        "    prefix forces traffic through the BYOK base URL above.",
        "",
        "  CLI subscription:",
        "    `cutctx wrap cursor --launch-cli` routes agent traffic through",
        "    this proxy and forwards subscription API calls to api2.cursor.sh.",
    ]
    agent_cli = find_agent_cli()
    ide_cli = find_ide_cli()
    if agent_cli or ide_cli:
        lines.append("")
        if agent_cli:
            lines.append(f"  Cursor Agent CLI found at: {agent_cli}")
        if ide_cli:
            lines.append(f"  Cursor IDE launcher found at: {ide_cli}")
    if project:
        lines += [
            "",
            f"  Dashboard savings will be attributed to project '{project}'",
            "  (the directory this command was run from). Re-run from another",
            "  project directory to get that project's URL.",
        ]
    return lines
