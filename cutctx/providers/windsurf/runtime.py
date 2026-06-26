"""Runtime helpers for Windsurf integrations."""

from __future__ import annotations

from cutctx.providers.claude import proxy_base_url as claude_proxy_base_url
from cutctx.providers.codex import proxy_base_url as codex_proxy_base_url
from cutctx.proxy.project_context import with_project_prefix


def render_setup_lines(port: int, project: str | None = None) -> list[str]:
    """Render the Windsurf setup instructions for the local proxy."""
    openai_base_url = with_project_prefix(codex_proxy_base_url(port), project)
    anthropic_base_url = with_project_prefix(claude_proxy_base_url(port), project)
    lines = [
        "  Cutctx proxy is running. Configure Windsurf:",
        "",
        "  Option 1 — Settings UI (Cmd+, / Ctrl+,):",
        '    Search for "OpenAI Base URL" and set it to:',
        f"      {openai_base_url}",
        "",
        "  Option 2 — settings.json:",
        '    Add or update the following key:',
        f'      "openai.baseUrl": "{openai_base_url}"',
        "",
        "  For Anthropic models (Claude):",
        "    Open Windsurf Settings > AI section.",
        "    Set the Anthropic Base URL to:",
        f"      {anthropic_base_url}",
    ]
    if project:
        lines += [
            "",
            f"  Dashboard savings will be attributed to project '{project}'",
            "  (the directory this command was run from). Re-run from another",
            "  project directory to get that project's URL.",
        ]
    return lines
