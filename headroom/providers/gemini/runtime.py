"""Runtime helpers for Gemini-facing integrations."""

from __future__ import annotations

import os
from collections.abc import Mapping

from headroom.proxy.project_context import with_project_prefix

DEFAULT_API_URL = "https://generativelanguage.googleapis.com"


def proxy_base_url(port: int) -> str:
    """Return the local proxy base URL used by Gemini integrations."""
    return f"http://127.0.0.1:{port}"


def build_launch_env(
    port: int,
    environ: Mapping[str, str] | None = None,
    project: str | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Build environment variables for Gemini CLI through the local proxy.

    Gemini CLI can talk to the Gemini API, Vertex AI, or Cloud Code / Code
    Assist style endpoints. We point all three at the same local proxy base so
    whichever mode the user is authenticated for still routes through CutCtx.

    ``project`` is encoded as a ``/p/<name>`` base-URL prefix because Gemini
    CLI does not provide a reliable custom-header hook for per-project
    attribution.
    """
    env = dict(environ or os.environ)
    base_url = with_project_prefix(proxy_base_url(port), project)
    env["GOOGLE_GEMINI_BASE_URL"] = base_url
    env["GOOGLE_VERTEX_BASE_URL"] = base_url
    env["CODE_ASSIST_ENDPOINT"] = base_url
    return env, [
        f"GOOGLE_GEMINI_BASE_URL={base_url}",
        f"GOOGLE_VERTEX_BASE_URL={base_url}",
        f"CODE_ASSIST_ENDPOINT={base_url}",
    ]
