"""Runtime helpers for Zed editor integrations."""

from __future__ import annotations

from cutctx.providers.claude import proxy_base_url as claude_proxy_base_url
from cutctx.providers.codex import proxy_base_url as codex_proxy_base_url
from cutctx.proxy.project_context import with_project_prefix


def render_setup_lines(port: int, project: str | None = None) -> list[str]:
    """Render the Zed editor setup instructions for the local proxy."""
    openai_base_url = with_project_prefix(codex_proxy_base_url(port), project)
    anthropic_base_url = with_project_prefix(claude_proxy_base_url(port), project)
    lines = [
        "  Cutctx proxy is running. Configure Zed:",
        "",
        "  Edit ~/.config/zed/settings.json and add:",
        "    {",
        '      "language_models": {',
        '        "openai": {',
        f'          "api_url": "{openai_base_url}",',
        '          "available_models": [',
        '            {"name": "gpt-4o", "display_name": "GPT-4o (via Cutctx)", "max_tokens": 128000},',
        '            {"name": "gpt-4o-mini", "display_name": "GPT-4o mini (via Cutctx)", "max_tokens": 128000}',
        "          ]",
        "        },",
        '        "anthropic": {',
        f'          "api_url": "{anthropic_base_url}"',
        "        }",
        "      }",
        "    }",
        "",
        "  For OpenAI-compatible models:",
        f"    api_url: {openai_base_url}",
        "",
        "  For Anthropic models (Claude):",
        f"    api_url: {anthropic_base_url}",
    ]
    if project:
        lines += [
            "",
            f"  Dashboard savings will be attributed to project '{project}'",
            "  (the directory this command was run from). Re-run from another",
            "  project directory to get that project's URL.",
        ]
    return lines
